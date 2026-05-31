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
    vf_parts = []

    # 1. Vertical reframe 9:16
    if vertical:
        scale_map = {
            "h264_720":  (720, 1280),
            "h264_1080": (1080, 1920),
            "h264_4k":   (2160, 3840),
            "h265_4k":   (2160, 3840),
            "copy":      (1080, 1920),
        }
        tw, th = scale_map.get(quality, (1080, 1920))
        vf_parts.append(f"crop=iw:iw*16/9,scale={tw}:{th}:flags=lanczos")
    else:
        hscale = {
            "h264_720":  "scale=1280:720:flags=lanczos",
            "h264_1080": "scale=1920:1080:flags=lanczos",
            "h264_4k":   "scale=3840:2160:flags=lanczos",
            "h265_4k":   "scale=3840:2160:flags=lanczos",
        }
        if quality in hscale:
            vf_parts.append(hscale[quality])

    # 2. Subtitles
    if subtitle_segments:
        try:
            sub_filter = build_subtitle_filter(subtitle_segments, subtitle_style)
            if sub_filter:
                vf_parts.append(sub_filter)
        except Exception:
            pass

    # Codec
    crf_map = {"h264_720":"23","h264_1080":"20","h264_4k":"18","h265_4k":"20"}
    crf = crf_map.get(quality, "20")

    if quality == "copy" and not vertical and not subtitle_segments:
        codec_args = ["-c","copy","-avoid_negative_ts","make_zero"]
    elif quality.startswith("h265"):
        codec_args = ["-c:v","libx265","-tag:v","hvc1","-crf",crf,"-preset","fast",
                      "-c:a","aac","-b:a","192k","-movflags","+faststart"]
    else:
        codec_args = ["-c:v","libx264","-profile:v","high","-crf",crf,"-preset","fast",
                      "-c:a","aac","-b:a","192k","-movflags","+faststart"]

    cmd = ["ffmpeg","-y","-ss",str(start),"-t",str(duration),"-i",str(src)]
    if vf_parts:
        cmd += ["-vf", ",".join(vf_parts)]
    cmd += codec_args + ["-avoid_negative_ts","make_zero", str(dst)]

    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await proc.communicate()
    if proc.returncode != 0:
        raise RuntimeError(stderr.decode()[-600:])

# ─── API routes ───────────────────────────────────────────────────────────────

@app.post("/upload")
async def upload_video(file: UploadFile = File(...)):
    ext  = Path(file.filename or "video.mp4").suffix.lower() or ".mp4"
    vid  = uuid.uuid4().hex
    dest = UPLOADS / f"{vid}{ext}"
    async with aiofiles.open(dest,"wb") as f:
        while chunk := await file.read(2*1024*1024):
            await f.write(chunk)
    try:
        meta = ffprobe_meta(dest)
    except Exception as e:
        dest.unlink(missing_ok=True)
        raise HTTPException(400, str(e))
    return {"video_id": vid, "filename": file.filename, "ext": ext, **meta}


@app.post("/analyze")
async def analyze_video(
    video_id:  str  = Form(...),
    max_clips: int  = Form(5),
    clip_len:  float= Form(60.0),
    language:  str  = Form("es"),
):
    """Transcribe + detect viral moments. Returns segments + suggested clips."""
    candidates = list(UPLOADS.glob(f"{video_id}.*"))
    if not candidates: raise HTTPException(404,"Video not found")
    src = candidates[0]

    job_id = uuid.uuid4().hex
    jobs[job_id] = {"status":"analyzing","step":"Extrayendo audio...","progress":5,
                    "segments":[],"clips":[],"srt":""}
    asyncio.create_task(_run_analysis(job_id, src, max_clips, clip_len, language))
    return {"job_id": job_id}


async def _run_analysis(job_id, src, max_clips, clip_len, language):
    job = jobs[job_id]
    try:
        wav = UPLOADS / f"{src.stem}_mono.wav"

        job["step"] = "Extrayendo audio..."; job["progress"] = 10
        await asyncio.get_event_loop().run_in_executor(None, extract_audio, src, wav)

        job["step"] = "Transcribiendo con Whisper..."; job["progress"] = 30
        meta = await asyncio.get_event_loop().run_in_executor(None, ffprobe_meta, src)
        duration = meta["duration"]

        # Try whisper; graceful fallback if not installed
        try:
            segments = await asyncio.get_event_loop().run_in_executor(
                None, transcribe_whisper, wav, language)
        except Exception:
            segments = []

        job["step"] = "Detectando momentos virales..."; job["progress"] = 70
        clips = await asyncio.get_event_loop().run_in_executor(
            None, detect_viral_moments, wav, duration, max_clips, clip_len)

        # Attach subtitle segments to each clip
        for c in clips:
            c["subtitle_segments"] = clip_segments_for(segments, c["start"], c["end"])

        srt = segments_to_srt(segments)
        job.update({"status":"done","progress":100,"step":"Análisis completo",
                    "segments":segments,"clips":clips,"srt":srt,"duration":duration})
        wav.unlink(missing_ok=True)
    except Exception as e:
        job.update({"status":"error","step":str(e),"progress":0})


@app.post("/export")
async def export_clips(
    video_id:        str  = Form(...),
    clips_json:      str  = Form(...),
    quality:         str  = Form("h264_1080"),
    vertical:        str  = Form("true"),
    subtitle_style_json: str = Form("{}"),
):
    candidates = list(UPLOADS.glob(f"{video_id}.*"))
    if not candidates: raise HTTPException(404,"Video not found")
    src = candidates[0]

    clips  = json.loads(clips_json)
    style  = json.loads(subtitle_style_json)
    vert   = vertical.lower() == "true"

    job_id = uuid.uuid4().hex
    jobs[job_id] = {"status":"exporting","total":len(clips),"done":0,
                    "progress":0,"results":[],"errors":[]}
    asyncio.create_task(_run_export(job_id, src, clips, quality, vert, style))
    return {"job_id": job_id}


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
            job["errors"].append({"index":i+1,"label":label,"error":str(e)[:200]})
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



from fastapi.responses import HTMLResponse

@app.get("/")
async def root():
    return HTMLResponse("""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>KatanaClips — IA para Creadores</title>
<link href="https://fonts.googleapis.com/css2?family=Syne:wght@400;600;700;800&family=DM+Sans:wght@300;400;500&display=swap" rel="stylesheet">
<style>
*{margin:0;padding:0;box-sizing:border-box}
:root{
  --bg:#07070f;--s1:#0f0f1a;--s2:#161624;--s3:#1e1e2e;--s4:#26263a;
  --border:#2a2a40;--b2:#363650;
  --accent:#7c3aed;--a2:#a855f7;--a3:#c084fc;
  --adim:rgba(124,58,237,.14);--aglow:rgba(124,58,237,.3);
  --text:#f0eeff;--t2:#9090b0;--t3:#55556a;
  --ok:#34d399;--warn:#fb923c;--err:#f87171;--info:#60a5fa;
  --r:10px;--r2:16px;--r3:22px;
}
html{scroll-behavior:smooth}
body{background:var(--bg);color:var(--text);font-family:'DM Sans',sans-serif;min-height:100vh;overflow-x:hidden}
h1,h2,h3,.logo{font-family:'Syne',sans-serif}

.blob{position:fixed;border-radius:50%;filter:blur(130px);opacity:.07;pointer-events:none}
.b1{width:700px;height:700px;background:#7c3aed;top:-300px;left:-200px}
.b2{width:500px;height:500px;background:#a855f7;bottom:-200px;right:-100px}

/* HEADER */
header{position:sticky;top:0;z-index:300;background:rgba(7,7,15,.8);backdrop-filter:blur(18px);border-bottom:1px solid var(--border)}
.hinner{max-width:1160px;margin:0 auto;padding:0 24px;height:58px;display:flex;align-items:center;justify-content:space-between}
.logo{font-size:19px;font-weight:800;background:linear-gradient(120deg,#a78bfa,#e879f9);-webkit-background-clip:text;-webkit-text-fill-color:transparent;letter-spacing:-.3px}
.hright{display:flex;align-items:center;gap:10px}
.hbadge{font-size:10px;padding:3px 10px;border-radius:99px;font-family:'Syne',sans-serif;font-weight:700;letter-spacing:.3px;background:var(--adim);border:1px solid var(--aglow);color:var(--a3)}
#sstat{display:flex;align-items:center;gap:5px;font-size:12px;color:var(--t3)}
.sdot{width:7px;height:7px;border-radius:50%;background:var(--t3);transition:background .4s;flex-shrink:0}
.sdot.on{background:var(--ok);box-shadow:0 0 8px var(--ok)}
.sdot.off{background:var(--err)}

/* MAIN */
main{max-width:1160px;margin:0 auto;padding:36px 24px 80px;position:relative;z-index:1}

/* UPLOAD */
.drop{border:1.5px dashed var(--border);border-radius:var(--r3);padding:64px 36px;text-align:center;cursor:pointer;transition:all .3s;background:var(--s1);position:relative;overflow:hidden}
.drop::before{content:'';position:absolute;inset:0;background:radial-gradient(ellipse at 50% -20%,rgba(124,58,237,.08),transparent 65%);pointer-events:none}
.drop:hover,.drop.over{border-color:var(--accent);background:rgba(124,58,237,.04)}
.dicon{width:70px;height:70px;border-radius:18px;background:var(--adim);border:1px solid var(--aglow);display:flex;align-items:center;justify-content:center;margin:0 auto 20px;font-size:30px}
.drop h2{font-size:22px;font-weight:800;margin-bottom:8px}
.drop p{color:var(--t2);font-size:15px;margin-bottom:26px}
.dbtn{display:inline-flex;align-items:center;gap:7px;padding:11px 26px;background:var(--accent);border-radius:var(--r);color:#fff;font-size:14px;font-family:'Syne',sans-serif;font-weight:700;cursor:pointer;border:none;transition:all .2s}
.dbtn:hover{background:#6d28d9;transform:translateY(-1px);box-shadow:0 8px 24px var(--aglow)}
.dfmts{display:flex;gap:6px;justify-content:center;flex-wrap:wrap;margin-top:20px}
.dfmt{font-size:11px;padding:3px 11px;background:var(--s2);border:1px solid var(--border);border-radius:99px;color:var(--t3);font-family:'Syne',sans-serif;font-weight:600}
#finput{display:none}

.uprog{display:none;margin-top:22px}
.upbar{height:4px;background:var(--s3);border-radius:99px;overflow:hidden;margin-bottom:7px}
.upfill{height:100%;width:0;background:linear-gradient(90deg,var(--accent),var(--a2));border-radius:99px;transition:width .15s}
.uptxt{font-size:12px;color:var(--t2);text-align:center}

/* EDITOR */
#editor{display:none;animation:fu .4s ease}
@keyframes fu{from{opacity:0;transform:translateY(14px)}to{opacity:1;transform:none}}

/* STEPS INDICATOR */
.steps{display:flex;align-items:center;gap:0;margin-bottom:28px}
.step{display:flex;align-items:center;gap:8px;font-size:13px;font-family:'Syne',sans-serif;font-weight:700;color:var(--t3);cursor:pointer;padding:8px 0}
.step.active{color:var(--a2)}
.step.done{color:var(--ok)}
.snum{width:26px;height:26px;border-radius:50%;background:var(--s3);border:1px solid var(--border);display:flex;align-items:center;justify-content:center;font-size:11px;font-weight:800;flex-shrink:0;transition:all .3s}
.step.active .snum{background:var(--accent);border-color:var(--accent);color:#fff}
.step.done .snum{background:var(--ok);border-color:var(--ok);color:#fff}
.sdiv{flex:1;height:1px;background:var(--border);margin:0 10px}

/* VIDEO PANEL */
.vpanel{background:var(--s1);border:1px solid var(--border);border-radius:var(--r3);overflow:hidden;margin-bottom:18px}
.vphead{padding:14px 20px;border-bottom:1px solid var(--border);display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:10px}
.vfile{display:flex;align-items:center;gap:11px}
.vico{width:38px;height:38px;border-radius:10px;background:var(--adim);border:1px solid var(--aglow);display:flex;align-items:center;justify-content:center;font-size:17px;flex-shrink:0}
.vname{font-size:13px;font-weight:700;font-family:'Syne',sans-serif;max-width:300px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.vtags{display:flex;gap:6px;flex-wrap:wrap;margin-top:3px}
.vtag{font-size:10px;padding:2px 8px;border-radius:5px;background:var(--s3);color:var(--t2);border:1px solid var(--border);font-family:'Syne',sans-serif;font-weight:600}
.vtag.hi{background:rgba(124,58,237,.12);border-color:var(--aglow);color:var(--a3)}
video#player{width:100%;display:block;max-height:380px;background:#000;cursor:pointer}

/* ANALYSIS PANEL */
.apanel{background:var(--s1);border:1px solid var(--border);border-radius:var(--r2);padding:22px;margin-bottom:18px}
.aphead{display:flex;align-items:center;justify-content:space-between;margin-bottom:18px;flex-wrap:wrap;gap:10px}
.atitle{font-size:15px;font-weight:700;font-family:'Syne',sans-serif}
.arow{display:grid;grid-template-columns:1fr 1fr 1fr;gap:12px;margin-bottom:16px}
.afield{display:flex;flex-direction:column;gap:5px}
.alabel{font-size:11px;font-family:'Syne',sans-serif;font-weight:700;color:var(--t3);text-transform:uppercase;letter-spacing:.6px}
select,input[type=number]{padding:9px 12px;background:var(--s2);border:1px solid var(--border);border-radius:var(--r);color:var(--text);font-size:13px;font-family:'DM Sans',sans-serif;outline:none;-webkit-appearance:none;transition:border .2s}
select:focus,input[type=number]:focus{border-color:var(--accent)}
select option{background:var(--s2)}

.analyze-btn{width:100%;padding:13px;background:linear-gradient(135deg,var(--accent),#9333ea);border:none;border-radius:var(--r2);color:#fff;font-size:15px;font-family:'Syne',sans-serif;font-weight:800;cursor:pointer;transition:all .2s;display:flex;align-items:center;justify-content:center;gap:9px}
.analyze-btn:hover:not(:disabled){transform:translateY(-1px);box-shadow:0 10px 30px var(--aglow)}
.analyze-btn:disabled{opacity:.35;cursor:not-allowed;transform:none;box-shadow:none}

/* PROGRESS */
.progpanel{display:none;background:var(--s1);border:1px solid var(--border);border-radius:var(--r2);padding:22px;margin-bottom:18px}
.progtitle{font-size:14px;font-weight:700;font-family:'Syne',sans-serif;margin-bottom:12px;display:flex;align-items:center;gap:8px}
.spin{width:14px;height:14px;border:2px solid var(--b2);border-top-color:var(--accent);border-radius:50%;animation:sp .7s linear infinite;flex-shrink:0}
@keyframes sp{to{transform:rotate(360deg)}}
.progtrack{height:5px;background:var(--s3);border-radius:99px;overflow:hidden;margin-bottom:7px}
.progfill{height:100%;background:linear-gradient(90deg,var(--accent),var(--a2));border-radius:99px;width:0;transition:width .4s ease}
.progstep{font-size:12px;color:var(--t2);display:flex;justify-content:space-between}

/* CLIPS GRID */
.cgrid-wrap{margin-bottom:18px}
.cghead{display:flex;align-items:center;justify-content:space-between;margin-bottom:14px;flex-wrap:wrap;gap:8px}
.cgtitle{font-size:15px;font-weight:700;font-family:'Syne',sans-serif}
.cgactions{display:flex;gap:8px}
.clips-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:14px}

.clipcard{background:var(--s1);border:1px solid var(--border);border-radius:var(--r2);overflow:hidden;transition:all .25s;cursor:pointer}
.clipcard:hover{border-color:var(--b2);transform:translateY(-2px)}
.clipcard.selected{border-color:var(--accent);box-shadow:0 0 0 1px var(--accent)}

.cthumb{height:130px;background:var(--s3);position:relative;overflow:hidden;display:flex;align-items:center;justify-content:center}
.cthumb video{position:absolute;inset:0;width:100%;height:100%;object-fit:cover}
.cthumb-ico{font-size:28px;color:var(--t3);z-index:1}
.cscore{position:absolute;top:8px;right:8px;font-size:10px;padding:3px 9px;border-radius:99px;font-family:'Syne',sans-serif;font-weight:800;z-index:5}
.cscore.high{background:rgba(52,211,153,.2);border:1px solid rgba(52,211,153,.4);color:var(--ok)}
.cscore.med{background:rgba(251,146,60,.15);border:1px solid rgba(251,146,60,.3);color:var(--warn)}
.cscore.low{background:rgba(96,165,250,.12);border:1px solid rgba(96,165,250,.25);color:var(--info)}
.ccheck{position:absolute;top:8px;left:8px;width:22px;height:22px;border-radius:6px;border:2px solid rgba(255,255,255,.4);background:rgba(0,0,0,.4);display:flex;align-items:center;justify-content:center;font-size:12px;z-index:5;transition:all .2s}
.clipcard.selected .ccheck{background:var(--accent);border-color:var(--accent)}
.cbody{padding:13px 15px}
.creason{font-size:11px;color:var(--a3);margin-bottom:6px;font-family:'Syne',sans-serif;font-weight:600}
.ctimes{font-size:13px;font-weight:600;font-family:'Syne',sans-serif;margin-bottom:4px}
.cdur{font-size:11px;color:var(--t2)}
.cedit{width:100%;margin-top:10px;padding:5px 0;background:transparent;border:none;border-top:1px solid var(--border);color:var(--t2);font-size:11px;font-family:'DM Sans',sans-serif;cursor:pointer;transition:color .2s;text-align:center}
.cedit:hover{color:var(--a3)}

/* EXPORT SETTINGS */
.exppanel{background:var(--s1);border:1px solid var(--border);border-radius:var(--r2);padding:22px;margin-bottom:18px}
.expgrid{display:grid;grid-template-columns:1fr 1fr;gap:16px}
.expcard{background:var(--s2);border:1px solid var(--border);border-radius:var(--r2);padding:18px}
.ectitle{font-size:12px;font-family:'Syne',sans-serif;font-weight:700;color:var(--t3);text-transform:uppercase;letter-spacing:.6px;margin-bottom:14px}

.qgrid{display:grid;grid-template-columns:repeat(5,1fr);gap:5px}
.qbtn{padding:9px 3px;border:1px solid var(--border);border-radius:9px;cursor:pointer;text-align:center;background:var(--s3);transition:all .2s}
.qbtn:hover{border-color:var(--b2)}
.qbtn.active{border-color:var(--accent);background:var(--adim)}
.qname{font-size:11px;font-family:'Syne',sans-serif;font-weight:700;color:var(--text)}
.qsub{font-size:9px;color:var(--t3);margin-top:1px}
.qbtn.active .qname{color:var(--a3)}

.togglerow{display:flex;align-items:center;justify-content:space-between;padding:10px 0;border-bottom:1px solid var(--border)}
.togglerow:last-child{border-bottom:none}
.tlabel{font-size:13px;color:var(--t2)}
.tgl{width:38px;height:20px;border-radius:99px;background:var(--s4);border:1px solid var(--border);cursor:pointer;position:relative;transition:background .2s;flex-shrink:0}
.tgl.on{background:var(--accent);border-color:var(--accent)}
.tgl::after{content:'';position:absolute;top:2px;left:2px;width:14px;height:14px;border-radius:50%;background:#fff;transition:transform .2s}
.tgl.on::after{transform:translateX(18px)}

/* SUBTITLE EDITOR */
.subedit{display:none;background:var(--s2);border:1px solid var(--border);border-radius:var(--r);padding:14px;margin-top:12px}
.subrow{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-bottom:10px}
.subfield label{font-size:11px;color:var(--t3);font-family:'Syne',sans-serif;font-weight:700;display:block;margin-bottom:5px;text-transform:uppercase;letter-spacing:.5px}
.subfield input,.subfield select{width:100%;padding:8px 10px;background:var(--s3);border:1px solid var(--border);border-radius:var(--r);color:var(--text);font-size:12px;outline:none}
.subfield input[type=color]{padding:3px;height:34px;cursor:pointer}

/* RESULTS */
.respanel{display:none;background:var(--s1);border:1px solid var(--border);border-radius:var(--r2);padding:22px;margin-bottom:18px}
.reshead{display:flex;align-items:center;justify-content:space-between;margin-bottom:16px;flex-wrap:wrap;gap:10px}
.restitle{font-size:15px;font-weight:700;font-family:'Syne',sans-serif}
.resgrid{display:grid;grid-template-columns:repeat(auto-fill,minmax(210px,1fr));gap:14px}
.rescard{background:var(--s2);border:1px solid var(--border);border-radius:var(--r2);overflow:hidden}
.rcthumb{height:115px;background:var(--s3);position:relative;display:flex;align-items:center;justify-content:center;overflow:hidden}
.rcthumb video{position:absolute;inset:0;width:100%;height:100%;object-fit:cover}
.rcbadge{position:absolute;top:7px;left:7px;font-size:10px;padding:2px 8px;border-radius:5px;background:rgba(0,0,0,.65);color:#fff;font-family:'Syne',sans-serif;font-weight:700;z-index:5}
.rcbody{padding:12px 13px}
.rcname{font-size:12px;font-weight:700;font-family:'Syne',sans-serif;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;margin-bottom:3px}
.rcmeta{font-size:11px;color:var(--t2);margin-bottom:9px}
.rcdl{display:block;width:100%;padding:7px;background:var(--accent);border:none;border-radius:8px;color:#fff;font-size:12px;font-weight:700;font-family:'Syne',sans-serif;cursor:pointer;text-align:center;text-decoration:none;transition:background .2s}
.rcdl:hover{background:#6d28d9}
.rcdl.err{background:var(--s3);color:var(--t3);cursor:not-allowed}

/* ACTION BAR */
.actbar{display:flex;gap:10px;justify-content:flex-end;align-items:center;margin-top:4px}
.btng{padding:11px 22px;background:transparent;border:1px solid var(--border);border-radius:var(--r);color:var(--t2);font-size:13px;font-family:'Syne',sans-serif;font-weight:700;cursor:pointer;transition:all .2s}
.btng:hover{border-color:var(--b2);color:var(--text)}
.btnp{padding:12px 28px;background:linear-gradient(135deg,var(--accent),#9333ea);border:none;border-radius:var(--r);color:#fff;font-size:14px;font-family:'Syne',sans-serif;font-weight:800;cursor:pointer;transition:all .2s;display:flex;align-items:center;gap:8px}
.btnp:hover:not(:disabled){transform:translateY(-1px);box-shadow:0 8px 28px var(--aglow)}
.btnp:disabled{opacity:.3;cursor:not-allowed;transform:none;box-shadow:none}
.bsm{padding:8px 15px;font-size:12px}

/* CLIP EDIT MODAL */
.modal-bg{display:none;position:fixed;inset:0;background:rgba(0,0,0,.7);z-index:500;align-items:center;justify-content:center}
.modal-bg.open{display:flex}
.modal{background:var(--s2);border:1px solid var(--b2);border-radius:var(--r3);padding:28px;width:min(520px,95vw);animation:fu .25s ease}
.modal h3{font-size:17px;font-family:'Syne',sans-serif;font-weight:800;margin-bottom:18px}
.mrow{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:12px}
.mfield{display:flex;flex-direction:column;gap:5px}
.mfield label{font-size:11px;color:var(--t3);font-family:'Syne',sans-serif;font-weight:700;text-transform:uppercase;letter-spacing:.5px}
.mfield input{padding:9px 12px;background:var(--s3);border:1px solid var(--border);border-radius:var(--r);color:var(--text);font-size:13px;font-family:'DM Sans',sans-serif;outline:none}
.mfield input:focus{border-color:var(--accent)}
.mbtns{display:flex;gap:10px;justify-content:flex-end;margin-top:20px}

/* TOAST */
#toast{position:fixed;bottom:24px;left:50%;transform:translateX(-50%) translateY(16px);background:var(--s2);border:1px solid var(--b2);border-radius:var(--r);padding:9px 20px;font-size:13px;color:var(--text);z-index:999;opacity:0;transition:all .3s;pointer-events:none;white-space:nowrap}
#toast.show{opacity:1;transform:translateX(-50%) translateY(0)}

@media(max-width:680px){
  .arow,.expgrid,.subrow,.mrow{grid-template-columns:1fr}
  .qgrid{grid-template-columns:repeat(3,1fr)}
  main{padding:20px 16px 60px}
}
</style>
</head>
<body>
<div class="blob b1"></div>
<div class="blob b2"></div>

<header>
  <div class="hinner">
    <div class="logo">⚔ KatanaClips</div>
    <div class="hright">
      <div id="sstat"><span class="sdot" id="sdot"></span><span id="stxt">Conectando...</span></div>
      <span class="hbadge">IA · FFmpeg · Whisper</span>
    </div>
  </div>
</header>

<main>
  <!-- UPLOAD -->
  <div id="upload-section">
    <div style="text-align:center;margin-bottom:32px">
      <h1 style="font-size:clamp(28px,4vw,46px);font-weight:800;letter-spacing:-1px;line-height:1.1;margin-bottom:10px">
        Transforma tus videos largos<br>
        <span style="background:linear-gradient(120deg,#a78bfa,#e879f9,#fb7185);-webkit-background-clip:text;-webkit-text-fill-color:transparent">en clips virales con IA</span>
      </h1>
      <p style="color:var(--t2);font-size:16px;max-width:500px;margin:0 auto">
        Detecta los mejores momentos, agrega subtítulos animados y exporta en 9:16 listo para TikTok, Reels y Shorts.
      </p>
    </div>
    <div class="drop" id="drop">
      <div class="dicon">🎬</div>
      <h2>Arrastrá tu video aquí</h2>
      <p>Podcasts, streams, entrevistas, cursos — hasta 2 horas en 4K</p>
      <label class="dbtn" for="finput">↑ Seleccionar video</label>
      <input type="file" id="finput" accept="video/*">
      <div class="dfmts">
        <span class="dfmt">MP4</span><span class="dfmt">MOV</span><span class="dfmt">MKV</span>
        <span class="dfmt">AVI</span><span class="dfmt">4K</span><span class="dfmt">H.264</span><span class="dfmt">H.265</span>
      </div>
      <div class="uprog" id="uprog">
        <div class="upbar"><div class="upfill" id="upfill"></div></div>
        <div class="uptxt" id="uptxt">Subiendo...</div>
      </div>
    </div>
  </div>

  <!-- EDITOR -->
  <div id="editor">
    <!-- Steps -->
    <div class="steps">
      <div class="step active" id="st1"><div class="snum">1</div><span>Analizar</span></div>
      <div class="sdiv"></div>
      <div class="step" id="st2"><div class="snum">2</div><span>Seleccionar clips</span></div>
      <div class="sdiv"></div>
      <div class="step" id="st3"><div class="snum">3</div><span>Exportar</span></div>
    </div>

    <!-- Video -->
    <div class="vpanel">
      <div class="vphead">
        <div class="vfile">
          <div class="vico">🎥</div>
          <div>
            <div class="vname" id="vname">video.mp4</div>
            <div class="vtags" id="vtags"></div>
          </div>
        </div>
        <div style="display:flex;gap:8px">
          <button class="btng bsm" id="prevbtn">▶ Preview</button>
          <button class="btng bsm" id="changebtn">Cambiar video</button>
        </div>
      </div>
      <video id="player" controls preload="metadata"></video>
    </div>

    <!-- STEP 1: Analyze -->
    <div id="step1">
      <div class="apanel">
        <div class="aphead">
          <div class="atitle">🔍 Análisis con IA</div>
        </div>
        <div class="arow">
          <div class="afield">
            <div class="alabel">Idioma del video</div>
            <select id="lang">
              <option value="es">Español</option>
              <option value="en">Inglés</option>
              <option value="pt">Portugués</option>
              <option value="fr">Francés</option>
            </select>
          </div>
          <div class="afield">
            <div class="alabel">Clips a detectar</div>
            <input type="number" id="maxclips" value="5" min="1" max="15">
          </div>
          <div class="afield">
            <div class="alabel">Duración por clip (seg)</div>
            <input type="number" id="cliplen" value="60" min="15" max="180">
          </div>
        </div>
        <button class="analyze-btn" id="analyzebtn">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/></svg>
          Analizar video con IA
        </button>
      </div>
    </div>

    <!-- STEP 2: Clips selection -->
    <div id="step2" style="display:none">
      <div class="cgrid-wrap">
        <div class="cghead">
          <div class="cgtitle">✨ Momentos detectados <span id="clipcnt" style="font-size:13px;font-weight:400;color:var(--t3)"></span></div>
          <div class="cgactions">
            <button class="btng bsm" id="selallbtn">Seleccionar todos</button>
            <button class="btng bsm" id="srtbtn" style="display:none">⬇ Descargar .SRT</button>
          </div>
        </div>
        <div class="clips-grid" id="clipsgrid"></div>
      </div>

      <!-- Export settings -->
      <div class="exppanel">
        <div style="font-size:15px;font-weight:700;font-family:'Syne',sans-serif;margin-bottom:16px">⚙️ Configuración de exportación</div>
        <div class="expgrid">
          <div class="expcard">
            <div class="ectitle">Calidad de video</div>
            <div class="qgrid">
              <div class="qbtn" data-q="copy"><div class="qname">COPY</div><div class="qsub">Sin re-enc</div></div>
              <div class="qbtn" data-q="h264_720"><div class="qname">720p</div><div class="qsub">H.264</div></div>
              <div class="qbtn active" data-q="h264_1080"><div class="qname">1080p</div><div class="qsub">H.264</div></div>
              <div class="qbtn" data-q="h264_4k"><div class="qname">4K</div><div class="qsub">H.264</div></div>
              <div class="qbtn" data-q="h265_4k"><div class="qname">4K</div><div class="qsub">H.265</div></div>
            </div>
          </div>
          <div class="expcard">
            <div class="ectitle">Opciones</div>
            <div class="togglerow">
              <span class="tlabel">📱 Reencuadre vertical 9:16</span>
              <div class="tgl on" id="tgl-vert"></div>
            </div>
            <div class="togglerow">
              <span class="tlabel">💬 Subtítulos animados</span>
              <div class="tgl on" id="tgl-subs"></div>
            </div>
            <div class="subedit" id="subedit">
              <div class="subrow">
                <div class="subfield">
                  <label>Color texto</label>
                  <input type="color" id="sub-color" value="#ffffff">
                </div>
                <div class="subfield">
                  <label>Tamaño fuente</label>
                  <input type="number" id="sub-size" value="52" min="24" max="96">
                </div>
                <div class="subfield">
                  <label>Posición</label>
                  <select id="sub-pos">
                    <option value="bottom">Abajo</option>
                    <option value="center">Centro</option>
                    <option value="top">Arriba</option>
                  </select>
                </div>
                <div class="subfield">
                  <label>Fondo</label>
                  <select id="sub-bg">
                    <option value="black@0.5">Negro semi-transparente</option>
                    <option value="black@0.8">Negro oscuro</option>
                    <option value="black@0.0">Sin fondo</option>
                  </select>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div class="actbar">
        <button class="btng" id="backbtn">← Volver</button>
        <button class="btnp" id="exportbtn" disabled>
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
          Exportar clips seleccionados
        </button>
      </div>
    </div>

    <!-- STEP 3: Results -->
    <div id="step3" style="display:none">
      <div class="respanel" id="respanel" style="display:block">
        <div class="reshead">
          <div class="restitle">✅ Clips exportados</div>
          <div style="display:flex;gap:8px">
            <button class="btng bsm" id="dlallbtn">⬇ Descargar todos</button>
            <button class="btng bsm" id="newanalysis">+ Nuevo análisis</button>
          </div>
        </div>
        <div class="resgrid" id="resgrid"></div>
      </div>
      <div class="actbar">
        <button class="btng" id="back2btn">← Editar clips</button>
        <button class="btng" id="resetbtn">Subir nuevo video</button>
      </div>
    </div>

  </div><!-- /editor -->

  <!-- Progress overlay (shared) -->
  <div class="progpanel" id="progpanel">
    <div class="progtitle"><div class="spin"></div><span id="progtitle">Procesando...</span></div>
    <div class="progtrack"><div class="progfill" id="progfill"></div></div>
    <div class="progstep"><span id="progstep">Iniciando...</span><span id="progpct">0%</span></div>
  </div>

</main>

<!-- Clip edit modal -->
<div class="modal-bg" id="modal">
  <div class="modal">
    <h3>✏️ Editar clip</h3>
    <div class="mrow">
      <div class="mfield"><label>Nombre</label><input type="text" id="m-label"></div>
      <div class="mfield"><label>Inicio (segundos)</label><input type="number" id="m-start" step="0.1"></div>
      <div class="mfield"><label>Fin (segundos)</label><input type="number" id="m-end" step="0.1"></div>
    </div>
    <div class="mbtns">
      <button class="btng" id="modal-cancel">Cancelar</button>
      <button class="btnp" id="modal-save">Guardar</button>
    </div>
  </div>
</div>

<div id="toast"></div>

<script>
const API = '';
const $ = id => document.getElementById(id);

// State
let videoId=null, videoMeta={}, detectedClips=[], selectedClips=new Set();
let quality='h264_1080', useVertical=true, useSubs=true;
let analysisJobId=null, exportJobId=null;
let editingClipIdx=null;

// Server health
async function checkServer(){
  try{
    await fetch(API+'/docs',{method:'HEAD',signal:AbortSignal.timeout(3000)});
    $('sdot').className='sdot on'; $('stxt').textContent='Servidor online';
  }catch{
    $('sdot').className='sdot off'; $('stxt').textContent='Servidor offline';
  }
}
checkServer(); setInterval(checkServer,10000);

// Utils
function fmtT(s){const m=Math.floor(s/60),se=(s%60).toFixed(0);return`${m}:${String(se).padStart(2,'0')}`}
function fmtSz(b){return b>1e9?(b/1e9).toFixed(2)+' GB':b>1e6?(b/1e6).toFixed(1)+' MB':(b/1024|0)+' KB'}
function toast(msg,d=2800){const el=$('toast');el.textContent=msg;el.classList.add('show');setTimeout(()=>el.classList.remove('show'),d)}
function setStep(n){
  ['st1','st2','st3'].forEach((id,i)=>{
    const el=$(id); el.className='step'+(i<n-1?' done':i===n-1?' active':'');
  });
  $('step1').style.display=n===1?'block':'none';
  $('step2').style.display=n===2?'block':'none';
  $('step3').style.display=n===3?'block':'none';
}

// Upload
const drop=$('drop'), finput=$('finput');
drop.addEventListener('dragover',e=>{e.preventDefault();drop.classList.add('over')});
drop.addEventListener('dragleave',()=>drop.classList.remove('over'));
drop.addEventListener('drop',e=>{e.preventDefault();drop.classList.remove('over');const f=e.dataTransfer.files[0];if(f)doUpload(f)});
finput.addEventListener('change',()=>{if(finput.files[0])doUpload(finput.files[0])});

async function doUpload(file){
  if(!file.type.startsWith('video/'))return toast('Solo se aceptan archivos de video.');
  const prog=$('uprog'),fill=$('upfill'),txt=$('uptxt');
  prog.style.display='block';
  const fd=new FormData(); fd.append('file',file);
  const xhr=new XMLHttpRequest(); xhr.open('POST',API+'/upload');
  xhr.upload.onprogress=e=>{
    if(e.lengthComputable){fill.style.width=(e.loaded/e.total*100)+'%';txt.textContent=`Subiendo ${fmtSz(e.loaded)} / ${fmtSz(e.total)}`;}
  };
  xhr.onload=()=>{
    prog.style.display='none';fill.style.width='0';
    if(xhr.status===200){
      const d=JSON.parse(xhr.responseText);
      initEditor(d,file);
    }else{
      let e='Error al subir';try{e=JSON.parse(xhr.responseText).detail||e;}catch{}
      toast('❌ '+e,5000);
    }
  };
  xhr.onerror=()=>{prog.style.display='none';toast('❌ No se puede conectar al servidor',5000)};
  xhr.send(fd);
}

function initEditor(data,file){
  videoId=data.video_id; videoMeta=data;
  const player=$('player'); player.src=URL.createObjectURL(file);
  $('vname').textContent=data.filename||file.name;
  const res=data.height>=2160?'4K':data.height>=1080?'1080p':'720p';
  $('vtags').innerHTML=[
    `<span class="vtag">${fmtT(data.duration)}</span>`,
    `<span class="vtag hi">${res} · ${data.video_codec.toUpperCase()}</span>`,
    `<span class="vtag">${data.fps} fps</span>`,
    `<span class="vtag">${fmtSz(data.size)}</span>`,
  ].join('');
  $('upload-section').style.display='none';
  $('editor').style.display='block';
  setStep(1);
  $('progpanel').style.display='none';
}

$('changebtn').addEventListener('click',()=>{
  $('upload-section').style.display='block';
  $('editor').style.display='none';
  detectedClips=[]; selectedClips.clear(); videoId=null;
});

$('prevbtn').addEventListener('click',()=>{
  const p=$('player'); p.currentTime=0; p.play();
});

// Analyze
$('analyzebtn').addEventListener('click',async()=>{
  if(!videoId)return;
  $('analyzebtn').disabled=true;
  $('progpanel').style.display='block';
  $('progtitle').textContent='Analizando video con IA...';
  setProgress(5,'Preparando análisis...');

  const fd=new FormData();
  fd.append('video_id',videoId);
  fd.append('max_clips',$('maxclips').value);
  fd.append('clip_len',$('cliplen').value);
  fd.append('language',$('lang').value);

  let res; try{res=await fetch(API+'/analyze',{method:'POST',body:fd});}
  catch{toast('❌ Error de conexión',5000);$('analyzebtn').disabled=false;return;}
  const {job_id}=await res.json();
  analysisJobId=job_id;
  pollAnalysis();
});

async function pollAnalysis(){
  let data; try{data=await(await fetch(API+`/job/${analysisJobId}`)).json();}
  catch{setTimeout(pollAnalysis,2000);return;}

  setProgress(data.progress||0, data.step||'...');
  if(data.status==='done'){
    detectedClips=data.clips||[];
    selectedClips=new Set(detectedClips.map((_,i)=>i));
    if(data.srt) $('srtbtn').style.display='';
    renderClipsGrid();
    $('progpanel').style.display='none';
    $('analyzebtn').disabled=false;
    setStep(2);
    toast(`✨ ${detectedClips.length} momentos detectados`);
    // store srt
    window._srt=data.srt||'';
  } else if(data.status==='error'){
    toast('❌ '+data.step,5000);
    $('progpanel').style.display='none';
    $('analyzebtn').disabled=false;
  } else {
    setTimeout(pollAnalysis,1200);
  }
}

function setProgress(pct,step){
  $('progfill').style.width=pct+'%';
  $('progstep').textContent=step;
  $('progpct').textContent=pct+'%';
}

// Clips grid
function scoreClass(s){return s>0.7?'high':s>0.4?'med':'low'}
function scoreLabel(s){return s>0.7?'🔥 Viral':'⚡ Destacado'}

function renderClipsGrid(){
  $('clipcnt').textContent=`(${detectedClips.length})`;
  $('clipsgrid').innerHTML=detectedClips.map((c,i)=>`
    <div class="clipcard${selectedClips.has(i)?' selected':''}" data-i="${i}">
      <div class="cthumb">
        <div class="cthumb-ico">🎞</div>
        <div class="ccheck">${selectedClips.has(i)?'✓':''}</div>
        <div class="cscore ${scoreClass(c.score)}">${scoreLabel(c.score)}</div>
      </div>
      <div class="cbody">
        <div class="creason">${c.reason}</div>
        <div class="ctimes">${fmtT(c.start)} → ${fmtT(c.end)}</div>
        <div class="cdur">${fmtT(c.end-c.start)} duración · ${c.subtitle_segments?.length||0} subtítulos</div>
        <button class="cedit" data-i="${i}">✏️ Editar tiempos y nombre</button>
      </div>
    </div>
  `).join('');

  document.querySelectorAll('.clipcard').forEach(card=>{
    card.addEventListener('click',e=>{
      if(e.target.classList.contains('cedit'))return;
      const i=parseInt(card.dataset.i);
      if(selectedClips.has(i))selectedClips.delete(i);
      else selectedClips.add(i);
      renderClipsGrid();
      updateExportBtn();
    });
  });
  document.querySelectorAll('.cedit').forEach(btn=>{
    btn.addEventListener('click',e=>{e.stopPropagation();openModal(parseInt(btn.dataset.i));});
  });
  updateExportBtn();
}

function updateExportBtn(){
  $('exportbtn').disabled=selectedClips.size===0;
}

$('selallbtn').addEventListener('click',()=>{
  if(selectedClips.size===detectedClips.length)selectedClips.clear();
  else detectedClips.forEach((_,i)=>selectedClips.add(i));
  renderClipsGrid();
});

$('srtbtn').addEventListener('click',()=>{
  const blob=new Blob([window._srt||''],{type:'text/plain'});
  const a=document.createElement('a'); a.href=URL.createObjectURL(blob);
  a.download='subtitulos.srt'; a.click();
});

// Modal
function openModal(i){
  editingClipIdx=i;
  const c=detectedClips[i];
  $('m-label').value=c.label||`clip_${i+1}`;
  $('m-start').value=c.start;
  $('m-end').value=c.end;
  $('modal').classList.add('open');
}
$('modal-cancel').addEventListener('click',()=>$('modal').classList.remove('open'));
$('modal-save').addEventListener('click',()=>{
  if(editingClipIdx===null)return;
  detectedClips[editingClipIdx].label=$('m-label').value.trim()||detectedClips[editingClipIdx].label;
  detectedClips[editingClipIdx].start=parseFloat($('m-start').value);
  detectedClips[editingClipIdx].end=parseFloat($('m-end').value);
  $('modal').classList.remove('open');
  renderClipsGrid();
  toast('Clip actualizado ✓');
});

// Quality
document.querySelectorAll('.qbtn').forEach(b=>{
  b.addEventListener('click',()=>{
    document.querySelectorAll('.qbtn').forEach(x=>x.classList.remove('active'));
    b.classList.add('active'); quality=b.dataset.q;
  });
});

// Toggles
function makeTgl(id,cb){
  const el=$(id);
  el.addEventListener('click',()=>{el.classList.toggle('on');cb(el.classList.contains('on'));});
  return ()=>el.classList.contains('on');
}
const getVert=makeTgl('tgl-vert',v=>{useVertical=v});
const getSubs=makeTgl('tgl-subs',v=>{
  useSubs=v;
  $('subedit').style.display=v?'block':'none';
});
$('subedit').style.display='block';

// Export
$('exportbtn').addEventListener('click',async()=>{
  const sel=[...selectedClips].map(i=>detectedClips[i]);
  if(!sel.length)return;
  $('exportbtn').disabled=true;
  $('progpanel').style.display='block';
  $('progtitle').textContent='Exportando clips...';
  setProgress(0,'Preparando...');

  const style={
    color: $('sub-color').value,
    size:  $('sub-size').value,
    position: $('sub-pos').value,
    bg:    $('sub-bg').value,
  };

  const clipsToExport=sel.map(c=>({
    ...c,
    subtitle_segments: useSubs?(c.subtitle_segments||[]):[],
  }));

  const fd=new FormData();
  fd.append('video_id',videoId);
  fd.append('clips_json',JSON.stringify(clipsToExport));
  fd.append('quality',quality);
  fd.append('vertical',useVertical?'true':'false');
  fd.append('subtitle_style_json',JSON.stringify(style));

  let res; try{res=await fetch(API+'/export',{method:'POST',body:fd});}
  catch{toast('❌ Error de conexión',5000);$('exportbtn').disabled=false;return;}
  const {job_id}=await res.json();
  exportJobId=job_id;
  pollExport();
});

async function pollExport(){
  let data; try{data=await(await fetch(API+`/job/${exportJobId}`)).json();}
  catch{setTimeout(pollExport,2000);return;}

  setProgress(data.progress||0,`Clip ${data.done||0}/${data.total||0}...`);
  if(data.status==='done'){
    $('progpanel').style.display='none';
    $('exportbtn').disabled=false;
    showResults(data);
    setStep(3);
    toast(`✅ ${data.results?.length||0} clips exportados`);
  } else if(data.status==='error'){
    toast('❌ Error en exportación',5000);
    $('progpanel').style.display='none';
    $('exportbtn').disabled=false;
  } else {
    setTimeout(pollExport,1500);
  }
}

function showResults(data){
  const all=[...(data.results||[]),...(data.errors||[])].sort((a,b)=>a.index-b.index);
  $('resgrid').innerHTML=all.map(item=>{
    if(item.error) return `
      <div class="rescard">
        <div class="rcthumb"><span style="font-size:26px;color:var(--err)">⚠️</span></div>
        <div class="rcbody"><div class="rcname">${item.label}</div><div class="rcmeta">Error al exportar</div><div class="rcdl err">No disponible</div></div>
      </div>`;
    return `
      <div class="rescard">
        <div class="rcthumb">
          <span style="font-size:28px;color:var(--t3);z-index:1">🎬</span>
          <div class="rcbadge">#${item.index}</div>
          <video src="${API}${item.url}" muted loop preload="none" onmouseenter="this.play()" onmouseleave="this.pause();this.currentTime=0" style="position:absolute;inset:0;width:100%;height:100%;object-fit:cover"></video>
        </div>
        <div class="rcbody">
          <div class="rcname">${item.filename}</div>
          <div class="rcmeta">${fmtT(item.duration)} · ${fmtSz(item.size)}</div>
          <a class="rcdl" href="${API}${item.url}" download="${item.filename}">⬇ Descargar</a>
        </div>
      </div>`;
  }).join('');
}

$('dlallbtn').addEventListener('click',()=>{
  document.querySelectorAll('#resgrid a.rcdl').forEach((a,i)=>{
    setTimeout(()=>{const t=document.createElement('a');t.href=a.href;t.download=a.download;t.click();},i*400);
  });
});

$('backbtn').addEventListener('click',()=>setStep(1));
$('back2btn').addEventListener('click',()=>setStep(2));
$('newanalysis').addEventListener('click',()=>{selectedClips=new Set(detectedClips.map((_,i)=>i));renderClipsGrid();setStep(2);});
$('resetbtn').addEventListener('click',()=>{
  $('upload-section').style.display='block';
  $('editor').style.display='none';
  videoId=null; detectedClips=[]; selectedClips.clear();
});

window.addEventListener('click',e=>{if(e.target===$('modal'))$('modal').classList.remove('open')});
</script>
</body>
</html>
""")

