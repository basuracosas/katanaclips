import asyncio, json, math, os, re, shutil, subprocess, uuid
from pathlib import Path
from typing import Optional
import aiofiles
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

BASE    = Path(__file__).parent
UPLOADS = BASE / "uploads";  UPLOADS.mkdir(exist_ok=True)
OUTPUTS = BASE / "outputs";  OUTPUTS.mkdir(exist_ok=True)
STATIC  = BASE / "static";   STATIC.mkdir(exist_ok=True)

app = FastAPI(title="KatanaClips API")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

jobs: dict[str, dict] = {}

# ─── helpers ────────────────────────────────────────────────────────────────

def run(cmd: list) -> tuple[int, str, str]:
    r = subprocess.run(cmd, capture_output=True, text=True)
    return r.returncode, r.stdout, r.stderr

def ffprobe_meta(path: Path) -> dict:
    code, out, err = run([
        "ffprobe","-v","quiet","-print_format","json",
        "-show_format","-show_streams", str(path)
    ])
    if code != 0: raise RuntimeError(err[:300])
    d = json.loads(out)
    fmt = d.get("format", {})
    vs  = next((s for s in d.get("streams",[]) if s["codec_type"]=="video"), {})
    as_ = next((s for s in d.get("streams",[]) if s["codec_type"]=="audio"), {})
    fps_raw = vs.get("r_frame_rate","25/1")
    try:
        n,de = fps_raw.split("/"); fps = round(int(n)/int(de),2)
    except: fps = 25
    return {
        "duration": float(fmt.get("duration",0)),
        "size":     int(fmt.get("size",0)),
        "width":    vs.get("width",1920),
        "height":   vs.get("height",1080),
        "fps":      fps,
        "video_codec": vs.get("codec_name",""),
        "audio_codec": as_.get("codec_name",""),
        "bitrate":  int(fmt.get("bit_rate",0)),
        "resolution": f"{vs.get('width','?')}x{vs.get('height','?')}",
    }

def extract_audio(src: Path, out: Path):
    run(["ffmpeg","-y","-i",str(src),"-vn","-ac","1","-ar","16000","-f","wav",str(out)])

# ─── VIRAL MOMENT DETECTION via audio energy ────────────────────────────────
def detect_viral_moments(wav: Path, duration: float, max_clips: int = 5,
                          clip_len: float = 60.0) -> list[dict]:
    """
    Analyse audio energy in windows. High-energy sustained segments = viral.
    Returns list of {start, end, score, reason}.
    """
    code, out, err = run([
        "ffprobe","-v","quiet","-f","lavfi",
        "-i", f"amovie={wav},astats=metadata=1:reset=1",
        "-show_frames","-print_format","json"
    ])
    # Fallback: use ffmpeg volumedetect per window
    segments = _energy_windows(wav, duration, window=3.0)
    if not segments:
        # uniform fallback
        step = max(duration / (max_clips+1), clip_len)
        segments = [{"t": step*i, "energy": 1.0-(i*0.1)} for i in range(max_clips)]

    # Score windows: look for sustained high energy
    clips = []
    used_ranges = []
    segments.sort(key=lambda x: -x["energy"])

    for seg in segments:
        start = max(0, seg["t"] - clip_len * 0.3)
        end   = min(duration, start + clip_len)
        if end - start < 20: continue
        # avoid overlap
        overlap = any(not (end <= u[0] or start >= u[1]) for u in used_ranges)
        if overlap: continue
        used_ranges.append((start, end))
        clips.append({
            "start":  round(start, 2),
            "end":    round(end, 2),
            "score":  round(seg["energy"], 3),
            "reason": _reason(seg["energy"]),
            "label":  f"clip_{len(clips)+1:02d}",
        })
        if len(clips) >= max_clips: break

    clips.sort(key=lambda x: x["start"])
    return clips

def _energy_windows(wav: Path, duration: float, window: float = 3.0) -> list[dict]:
    """Use ffmpeg silencedetect + mean_volume per window."""
    results = []
    try:
        # Get per-second RMS via astats
        cmd = [
            "ffmpeg","-y","-i",str(wav),
            "-af","astats=metadata=1:reset=1,ametadata=print:key=lavfi.astats.Overall.RMS_level:file=-",
            "-f","null","-"
        ]
        code, out, err = run(cmd)
        # parse from stderr (ffmpeg prints metadata there)
        lines = (out + err).split("\n")
        rms_vals = []
        for line in lines:
            if "RMS_level" in line:
                try:
                    val = float(line.split("=")[-1].strip())
                    if val > -120: rms_vals.append(val)
                except: pass

        if not rms_vals:
            raise ValueError("no rms")

        # normalize to 0-1
        mn, mx = min(rms_vals), max(rms_vals)
        rng = mx - mn if mx != mn else 1
        norm = [(v - mn) / rng for v in rms_vals]

        # sliding window average
        w = max(1, int(window))
        for i in range(0, len(norm) - w, max(1, w//2)):
            chunk = norm[i:i+w]
            energy = sum(chunk) / len(chunk)
            results.append({"t": float(i), "energy": energy})
    except Exception as e:
        # absolute fallback: evenly spaced
        n = max(1, int(duration / window))
        results = [{"t": float(i)*window, "energy": 0.5} for i in range(n)]
    return results

def _reason(score: float) -> str:
    if score > 0.8: return "Momento de alta energía — muy viral"
    if score > 0.6: return "Segmento animado — buen engagement"
    if score > 0.4: return "Contenido relevante detectado"
    return "Momento seleccionado por ritmo"

# ─── WHISPER TRANSCRIPTION ───────────────────────────────────────────────────
def transcribe_whisper(wav: Path, language: str = "es") -> list[dict]:
    """Run openai-whisper CLI, return word-level segments [{start,end,text}]."""
    out_dir = wav.parent / f"whisper_{wav.stem}"
    out_dir.mkdir(exist_ok=True)
    code, out, err = run([
        "whisper", str(wav),
        "--language", language,
        "--model", "small",
        "--output_format", "json",
        "--output_dir", str(out_dir),
        "--fp16", "False",
    ])
    json_file = out_dir / (wav.stem + ".json")
    if not json_file.exists():
        return []
    with open(json_file) as f:
        data = json.load(f)
    segments = []
    for seg in data.get("segments", []):
        segments.append({
            "start": round(seg["start"], 3),
            "end":   round(seg["end"], 3),
            "text":  seg["text"].strip(),
        })
    return segments

def segments_to_srt(segments: list[dict]) -> str:
    lines = []
    for i, s in enumerate(segments, 1):
        def ts(t):
            h=int(t//3600); m=int((t%3600)//60); se=int(t%60); ms=int((t%1)*1000)
            return f"{h:02d}:{m:02d}:{se:02d},{ms:03d}"
        lines.append(f"{i}\n{ts(s['start'])} --> {ts(s['end'])}\n{s['text']}\n")
    return "\n".join(lines)

def clip_segments_for(segments: list[dict], start: float, end: float) -> list[dict]:
    result = []
    for s in segments:
        if s["end"] < start or s["start"] > end: continue
        result.append({
            "start": round(s["start"] - start, 3),
            "end":   round(s["end"]   - start, 3),
            "text":  s["text"],
        })
    return result

# ─── FFmpeg clip render ───────────────────────────────────────────────────────
def build_subtitle_filter(segments: list[dict], style: dict) -> str:
    """Build ffmpeg drawtext filters for animated subtitles."""
    color   = style.get("color", "white")
    font    = style.get("font", "Arial")
    size    = int(style.get("size", 52))
    bg      = style.get("bg", "black@0.5")
    pos     = style.get("position", "bottom")  # bottom | center | top
    outline = style.get("outline", 3)

    y_expr = {
        "bottom": "h-th-80",
        "center": "(h-th)/2",
        "top":    "80",
    }.get(pos, "h-th-80")

    parts = []
    for seg in segments:
        text = seg["text"].replace("'", "\\'").replace(":", "\\:").replace(",","\\,")
        if not text.strip(): continue
        enable = f"between(t,{seg['start']:.3f},{seg['end']:.3f})"
        parts.append(
            f"drawtext=text='{text}'"
            f":fontcolor={color}"
            f":fontsize={size}"
            f":font={font}"
            f":x=(w-text_w)/2"
            f":y={y_expr}"
            f":box=1:boxcolor={bg}:boxborderw=12"
            f":borderw={outline}:bordercolor=black"
            f":enable='{enable}'"
        )
    return ",".join(parts) if parts else ""

async def render_clip(
    src: Path, dst: Path,
    start: float, end: float,
    quality: str,
    vertical: bool,
    subtitle_segments: list[dict],
    subtitle_style: dict,
) -> None:
    duration = end - start

    # Step 1: simple cut first (no reencoding) to a temp file
    tmp = dst.with_suffix('.tmp.mp4')
    cut_cmd = [
        'ffmpeg', '-y',
        '-ss', str(start),
        '-t',  str(duration),
        '-i',  str(src),
        '-c',  'copy',
        '-avoid_negative_ts', 'make_zero',
        str(tmp)
    ]
    proc = await asyncio.create_subprocess_exec(
        *cut_cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    _, stderr = await proc.communicate()
    if proc.returncode != 0:
        raise RuntimeError('Cut failed: ' + stderr.decode()[-400:])

    # Step 2: re-encode with optional vertical + quality
    crf = {'h264_720':'23','h264_1080':'20','h264_4k':'18','h265_4k':'20'}.get(quality,'20')

    vf = []
    if vertical:
        vf.append('scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,setsar=1')
    else:
        vf.append({'h264_720':'scale=1280:720','h264_1080':'scale=1920:1080',
                   'h264_4k':'scale=3840:2160','h265_4k':'scale=3840:2160',
                   'copy':'scale=1920:1080'}.get(quality,'scale=1920:1080'))

    if quality == 'copy' and not vertical:
        tmp.rename(dst)
        return

    vcodec = ['libx265','-tag:v','hvc1'] if quality.startswith('h265') else ['libx264','-profile:v','high']

    enc_cmd = [
        'ffmpeg', '-y',
        '-i', str(tmp),
        '-vf', ','.join(vf),
        '-c:v', *vcodec,
        '-crf', crf,
        '-preset', 'fast',
        '-pix_fmt', 'yuv420p',
        '-c:a', 'aac',
        '-b:a', '192k',
        '-movflags', '+faststart',
        str(dst)
    ]
    proc = await asyncio.create_subprocess_exec(
        *enc_cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    _, stderr = await proc.communicate()
    tmp.unlink(missing_ok=True)
    if proc.returncode != 0:
        raise RuntimeError('Encode failed: ' + stderr.decode()[-800:])


async def _run_export(job_id, src, clips, quality, vertical, style):
    job = jobs[job_id]
    for i, clip in enumerate(clips):
        start = float(clip["start"])
        end   = float(clip["end"])
        label = re.sub(r"[^a-zA-Z0-9_\-]","_", clip.get("label",f"clip_{i+1:02d}"))
        subs  = clip.get("subtitle_segments", [])
        out   = OUTPUTS / f"{job_id}_{label}.mp4"
        try:
            await render_clip(src, out, start, end, quality, vertical, subs, style)
            job["results"].append({
                "index": i+1, "label": label,
                "filename": out.name,
                "start": start, "end": end,
                "duration": round(end-start,2),
                "size": out.stat().st_size,
                "url": f"/download/{out.name}",
            })
        except Exception as e:
            import traceback
            job["errors"].append({"index":i+1,"label":label,"error":str(e)})
            job["last_traceback"] = traceback.format_exc()
        job["done"] += 1
        job["progress"] = int((job["done"]/max(job["total"],1))*100)
    job["status"] = "done"


@app.get("/job/{job_id}")
async def get_job(job_id: str):
    job = jobs.get(job_id)
    if not job: raise HTTPException(404,"Job not found")
    return job

@app.get("/download/{filename}")
async def download(filename: str):
    p = OUTPUTS / filename
    if not p.exists(): raise HTTPException(404,"File not found")
    return FileResponse(p, media_type="video/mp4", filename=filename)

@app.get("/srt/{job_id}")
async def get_srt(job_id: str):
    job = jobs.get(job_id)
    if not job or "srt" not in job: raise HTTPException(404)
    from fastapi.responses import PlainTextResponse
    return PlainTextResponse(job["srt"], media_type="text/plain",
        headers={"Content-Disposition":f'attachment; filename="subtitles.srt"'})


