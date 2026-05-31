import asyncio, json, math, os, re, shutil, subprocess, uuidHTML_PAGE = '<!DOCTYPE html>\n<html lang="es">\n<head>\n<meta charset="UTF-8">\n<meta name="viewport" content="width=device-width, initial-scale=1.0">\n<title>KatanaClips — IA para Creadores</title>\n<link href="https://fonts.googleapis.com/css2?family=Syne:wght@400;600;700;800&family=DM+Sans:wght@300;400;500&display=swap" rel="stylesheet">\n<style>\n*{margin:0;padding:0;box-sizing:border-box}\n:root{\n  --bg:#07070f;--s1:#0f0f1a;--s2:#161624;--s3:#1e1e2e;--s4:#26263a;\n  --border:#2a2a40;--b2:#363650;\n  --accent:#7c3aed;--a2:#a855f7;--a3:#c084fc;\n  --adim:rgba(124,58,237,.14);--aglow:rgba(124,58,237,.3);\n  --text:#f0eeff;--t2:#9090b0;--t3:#55556a;\n  --ok:#34d399;--warn:#fb923c;--err:#f87171;--info:#60a5fa;\n  --r:10px;--r2:16px;--r3:22px;\n}\nhtml{scroll-behavior:smooth}\nbody{background:var(--bg);color:var(--text);font-family:\'DM Sans\',sans-serif;min-height:100vh;overflow-x:hidden}\nh1,h2,h3,.logo{font-family:\'Syne\',sans-serif}\n\n.blob{position:fixed;border-radius:50%;filter:blur(130px);opacity:.07;pointer-events:none}\n.b1{width:700px;height:700px;background:#7c3aed;top:-300px;left:-200px}\n.b2{width:500px;height:500px;background:#a855f7;bottom:-200px;right:-100px}\n\n/* HEADER */\nheader{position:sticky;top:0;z-index:300;background:rgba(7,7,15,.8);backdrop-filter:blur(18px);border-bottom:1px solid var(--border)}\n.hinner{max-width:1160px;margin:0 auto;padding:0 24px;height:58px;display:flex;align-items:center;justify-content:space-between}\n.logo{font-size:19px;font-weight:800;background:linear-gradient(120deg,#a78bfa,#e879f9);-webkit-background-clip:text;-webkit-text-fill-color:transparent;letter-spacing:-.3px}\n.hright{display:flex;align-items:center;gap:10px}\n.hbadge{font-size:10px;padding:3px 10px;border-radius:99px;font-family:\'Syne\',sans-serif;font-weight:700;letter-spacing:.3px;background:var(--adim);border:1px solid var(--aglow);color:var(--a3)}\n#sstat{display:flex;align-items:center;gap:5px;font-size:12px;color:var(--t3)}\n.sdot{width:7px;height:7px;border-radius:50%;background:var(--t3);transition:background .4s;flex-shrink:0}\n.sdot.on{background:var(--ok);box-shadow:0 0 8px var(--ok)}\n.sdot.off{background:var(--err)}\n\n/* MAIN */\nmain{max-width:1160px;margin:0 auto;padding:36px 24px 80px;position:relative;z-index:1}\n\n/* UPLOAD */\n.drop{border:1.5px dashed var(--border);border-radius:var(--r3);padding:64px 36px;text-align:center;cursor:pointer;transition:all .3s;background:var(--s1);position:relative;overflow:hidden}\n.drop::before{content:\'\';position:absolute;inset:0;background:radial-gradient(ellipse at 50% -20%,rgba(124,58,237,.08),transparent 65%);pointer-events:none}\n.drop:hover,.drop.over{border-color:var(--accent);background:rgba(124,58,237,.04)}\n.dicon{width:70px;height:70px;border-radius:18px;background:var(--adim);border:1px solid var(--aglow);display:flex;align-items:center;justify-content:center;margin:0 auto 20px;font-size:30px}\n.drop h2{font-size:22px;font-weight:800;margin-bottom:8px}\n.drop p{color:var(--t2);font-size:15px;margin-bottom:26px}\n.dbtn{display:inline-flex;align-items:center;gap:7px;padding:11px 26px;background:var(--accent);border-radius:var(--r);color:#fff;font-size:14px;font-family:\'Syne\',sans-serif;font-weight:700;cursor:pointer;border:none;transition:all .2s}\n.dbtn:hover{background:#6d28d9;transform:translateY(-1px);box-shadow:0 8px 24px var(--aglow)}\n.dfmts{display:flex;gap:6px;justify-content:center;flex-wrap:wrap;margin-top:20px}\n.dfmt{font-size:11px;padding:3px 11px;background:var(--s2);border:1px solid var(--border);border-radius:99px;color:var(--t3);font-family:\'Syne\',sans-serif;font-weight:600}\n#finput{display:none}\n\n.uprog{display:none;margin-top:22px}\n.upbar{height:4px;background:var(--s3);border-radius:99px;overflow:hidden;margin-bottom:7px}\n.upfill{height:100%;width:0;background:linear-gradient(90deg,var(--accent),var(--a2));border-radius:99px;transition:width .15s}\n.uptxt{font-size:12px;color:var(--t2);text-align:center}\n\n/* EDITOR */\n#editor{display:none;animation:fu .4s ease}\n@keyframes fu{from{opacity:0;transform:translateY(14px)}to{opacity:1;transform:none}}\n\n/* STEPS INDICATOR */\n.steps{display:flex;align-items:center;gap:0;margin-bottom:28px}\n.step{display:flex;align-items:center;gap:8px;font-size:13px;font-family:\'Syne\',sans-serif;font-weight:700;color:var(--t3);cursor:pointer;padding:8px 0}\n.step.active{color:var(--a2)}\n.step.done{color:var(--ok)}\n.snum{width:26px;height:26px;border-radius:50%;background:var(--s3);border:1px solid var(--border);display:flex;align-items:center;justify-content:center;font-size:11px;font-weight:800;flex-shrink:0;transition:all .3s}\n.step.active .snum{background:var(--accent);border-color:var(--accent);color:#fff}\n.step.done .snum{background:var(--ok);border-color:var(--ok);color:#fff}\n.sdiv{flex:1;height:1px;background:var(--border);margin:0 10px}\n\n/* VIDEO PANEL */\n.vpanel{background:var(--s1);border:1px solid var(--border);border-radius:var(--r3);overflow:hidden;margin-bottom:18px}\n.vphead{padding:14px 20px;border-bottom:1px solid var(--border);display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:10px}\n.vfile{display:flex;align-items:center;gap:11px}\n.vico{width:38px;height:38px;border-radius:10px;background:var(--adim);border:1px solid var(--aglow);display:flex;align-items:center;justify-content:center;font-size:17px;flex-shrink:0}\n.vname{font-size:13px;font-weight:700;font-family:\'Syne\',sans-serif;max-width:300px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}\n.vtags{display:flex;gap:6px;flex-wrap:wrap;margin-top:3px}\n.vtag{font-size:10px;padding:2px 8px;border-radius:5px;background:var(--s3);color:var(--t2);border:1px solid var(--border);font-family:\'Syne\',sans-serif;font-weight:600}\n.vtag.hi{background:rgba(124,58,237,.12);border-color:var(--aglow);color:var(--a3)}\nvideo#player{width:100%;display:block;max-height:380px;background:#000;cursor:pointer}\n\n/* ANALYSIS PANEL */\n.apanel{background:var(--s1);border:1px solid var(--border);border-radius:var(--r2);padding:22px;margin-bottom:18px}\n.aphead{display:flex;align-items:center;justify-content:space-between;margin-bottom:18px;flex-wrap:wrap;gap:10px}\n.atitle{font-size:15px;font-weight:700;font-family:\'Syne\',sans-serif}\n.arow{display:grid;grid-template-columns:1fr 1fr 1fr;gap:12px;margin-bottom:16px}\n.afield{display:flex;flex-direction:column;gap:5px}\n.alabel{font-size:11px;font-family:\'Syne\',sans-serif;font-weight:700;color:var(--t3);text-transform:uppercase;letter-spacing:.6px}\nselect,input[type=number]{padding:9px 12px;background:var(--s2);border:1px solid var(--border);border-radius:var(--r);color:var(--text);font-size:13px;font-family:\'DM Sans\',sans-serif;outline:none;-webkit-appearance:none;transition:border .2s}\nselect:focus,input[type=number]:focus{border-color:var(--accent)}\nselect option{background:var(--s2)}\n\n.analyze-btn{width:100%;padding:13px;background:linear-gradient(135deg,var(--accent),#9333ea);border:none;border-radius:var(--r2);color:#fff;font-size:15px;font-family:\'Syne\',sans-serif;font-weight:800;cursor:pointer;transition:all .2s;display:flex;align-items:center;justify-content:center;gap:9px}\n.analyze-btn:hover:not(:disabled){transform:translateY(-1px);box-shadow:0 10px 30px var(--aglow)}\n.analyze-btn:disabled{opacity:.35;cursor:not-allowed;transform:none;box-shadow:none}\n\n/* PROGRESS */\n.progpanel{display:none;background:var(--s1);border:1px solid var(--border);border-radius:var(--r2);padding:22px;margin-bottom:18px}\n.progtitle{font-size:14px;font-weight:700;font-family:\'Syne\',sans-serif;margin-bottom:12px;display:flex;align-items:center;gap:8px}\n.spin{width:14px;height:14px;border:2px solid var(--b2);border-top-color:var(--accent);border-radius:50%;animation:sp .7s linear infinite;flex-shrink:0}\n@keyframes sp{to{transform:rotate(360deg)}}\n.progtrack{height:5px;background:var(--s3);border-radius:99px;overflow:hidden;margin-bottom:7px}\n.progfill{height:100%;background:linear-gradient(90deg,var(--accent),var(--a2));border-radius:99px;width:0;transition:width .4s ease}\n.progstep{font-size:12px;color:var(--t2);display:flex;justify-content:space-between}\n\n/* CLIPS GRID */\n.cgrid-wrap{margin-bottom:18px}\n.cghead{display:flex;align-items:center;justify-content:space-between;margin-bottom:14px;flex-wrap:wrap;gap:8px}\n.cgtitle{font-size:15px;font-weight:700;font-family:\'Syne\',sans-serif}\n.cgactions{display:flex;gap:8px}\n.clips-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:14px}\n\n.clipcard{background:var(--s1);border:1px solid var(--border);border-radius:var(--r2);overflow:hidden;transition:all .25s;cursor:pointer}\n.clipcard:hover{border-color:var(--b2);transform:translateY(-2px)}\n.clipcard.selected{border-color:var(--accent);box-shadow:0 0 0 1px var(--accent)}\n\n.cthumb{height:130px;background:var(--s3);position:relative;overflow:hidden;display:flex;align-items:center;justify-content:center}\n.cthumb video{position:absolute;inset:0;width:100%;height:100%;object-fit:cover}\n.cthumb-ico{font-size:28px;color:var(--t3);z-index:1}\n.cscore{position:absolute;top:8px;right:8px;font-size:10px;padding:3px 9px;border-radius:99px;font-family:\'Syne\',sans-serif;font-weight:800;z-index:5}\n.cscore.high{background:rgba(52,211,153,.2);border:1px solid rgba(52,211,153,.4);color:var(--ok)}\n.cscore.med{background:rgba(251,146,60,.15);border:1px solid rgba(251,146,60,.3);color:var(--warn)}\n.cscore.low{background:rgba(96,165,250,.12);border:1px solid rgba(96,165,250,.25);color:var(--info)}\n.ccheck{position:absolute;top:8px;left:8px;width:22px;height:22px;border-radius:6px;border:2px solid rgba(255,255,255,.4);background:rgba(0,0,0,.4);display:flex;align-items:center;justify-content:center;font-size:12px;z-index:5;transition:all .2s}\n.clipcard.selected .ccheck{background:var(--accent);border-color:var(--accent)}\n.cbody{padding:13px 15px}\n.creason{font-size:11px;color:var(--a3);margin-bottom:6px;font-family:\'Syne\',sans-serif;font-weight:600}\n.ctimes{font-size:13px;font-weight:600;font-family:\'Syne\',sans-serif;margin-bottom:4px}\n.cdur{font-size:11px;color:var(--t2)}\n.cedit{width:100%;margin-top:10px;padding:5px 0;background:transparent;border:none;border-top:1px solid var(--border);color:var(--t2);font-size:11px;font-family:\'DM Sans\',sans-serif;cursor:pointer;transition:color .2s;text-align:center}\n.cedit:hover{color:var(--a3)}\n\n/* EXPORT SETTINGS */\n.exppanel{background:var(--s1);border:1px solid var(--border);border-radius:var(--r2);padding:22px;margin-bottom:18px}\n.expgrid{display:grid;grid-template-columns:1fr 1fr;gap:16px}\n.expcard{background:var(--s2);border:1px solid var(--border);border-radius:var(--r2);padding:18px}\n.ectitle{font-size:12px;font-family:\'Syne\',sans-serif;font-weight:700;color:var(--t3);text-transform:uppercase;letter-spacing:.6px;margin-bottom:14px}\n\n.qgrid{display:grid;grid-template-columns:repeat(5,1fr);gap:5px}\n.qbtn{padding:9px 3px;border:1px solid var(--border);border-radius:9px;cursor:pointer;text-align:center;background:var(--s3);transition:all .2s}\n.qbtn:hover{border-color:var(--b2)}\n.qbtn.active{border-color:var(--accent);background:var(--adim)}\n.qname{font-size:11px;font-family:\'Syne\',sans-serif;font-weight:700;color:var(--text)}\n.qsub{font-size:9px;color:var(--t3);margin-top:1px}\n.qbtn.active .qname{color:var(--a3)}\n\n.togglerow{display:flex;align-items:center;justify-content:space-between;padding:10px 0;border-bottom:1px solid var(--border)}\n.togglerow:last-child{border-bottom:none}\n.tlabel{font-size:13px;color:var(--t2)}\n.tgl{width:38px;height:20px;border-radius:99px;background:var(--s4);border:1px solid var(--border);cursor:pointer;position:relative;transition:background .2s;flex-shrink:0}\n.tgl.on{background:var(--accent);border-color:var(--accent)}\n.tgl::after{content:\'\';position:absolute;top:2px;left:2px;width:14px;height:14px;border-radius:50%;background:#fff;transition:transform .2s}\n.tgl.on::after{transform:translateX(18px)}\n\n/* SUBTITLE EDITOR */\n.subedit{display:none;background:var(--s2);border:1px solid var(--border);border-radius:var(--r);padding:14px;margin-top:12px}\n.subrow{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-bottom:10px}\n.subfield label{font-size:11px;color:var(--t3);font-family:\'Syne\',sans-serif;font-weight:700;display:block;margin-bottom:5px;text-transform:uppercase;letter-spacing:.5px}\n.subfield input,.subfield select{width:100%;padding:8px 10px;background:var(--s3);border:1px solid var(--border);border-radius:var(--r);color:var(--text);font-size:12px;outline:none}\n.subfield input[type=color]{padding:3px;height:34px;cursor:pointer}\n\n/* RESULTS */\n.respanel{display:none;background:var(--s1);border:1px solid var(--border);border-radius:var(--r2);padding:22px;margin-bottom:18px}\n.reshead{display:flex;align-items:center;justify-content:space-between;margin-bottom:16px;flex-wrap:wrap;gap:10px}\n.restitle{font-size:15px;font-weight:700;font-family:\'Syne\',sans-serif}\n.resgrid{display:grid;grid-template-columns:repeat(auto-fill,minmax(210px,1fr));gap:14px}\n.rescard{background:var(--s2);border:1px solid var(--border);border-radius:var(--r2);overflow:hidden}\n.rcthumb{height:115px;background:var(--s3);position:relative;display:flex;align-items:center;justify-content:center;overflow:hidden}\n.rcthumb video{position:absolute;inset:0;width:100%;height:100%;object-fit:cover}\n.rcbadge{position:absolute;top:7px;left:7px;font-size:10px;padding:2px 8px;border-radius:5px;background:rgba(0,0,0,.65);color:#fff;font-family:\'Syne\',sans-serif;font-weight:700;z-index:5}\n.rcbody{padding:12px 13px}\n.rcname{font-size:12px;font-weight:700;font-family:\'Syne\',sans-serif;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;margin-bottom:3px}\n.rcmeta{font-size:11px;color:var(--t2);margin-bottom:9px}\n.rcdl{display:block;width:100%;padding:7px;background:var(--accent);border:none;border-radius:8px;color:#fff;font-size:12px;font-weight:700;font-family:\'Syne\',sans-serif;cursor:pointer;text-align:center;text-decoration:none;transition:background .2s}\n.rcdl:hover{background:#6d28d9}\n.rcdl.err{background:var(--s3);color:var(--t3);cursor:not-allowed}\n\n/* ACTION BAR */\n.actbar{display:flex;gap:10px;justify-content:flex-end;align-items:center;margin-top:4px}\n.btng{padding:11px 22px;background:transparent;border:1px solid var(--border);border-radius:var(--r);color:var(--t2);font-size:13px;font-family:\'Syne\',sans-serif;font-weight:700;cursor:pointer;transition:all .2s}\n.btng:hover{border-color:var(--b2);color:var(--text)}\n.btnp{padding:12px 28px;background:linear-gradient(135deg,var(--accent),#9333ea);border:none;border-radius:var(--r);color:#fff;font-size:14px;font-family:\'Syne\',sans-serif;font-weight:800;cursor:pointer;transition:all .2s;display:flex;align-items:center;gap:8px}\n.btnp:hover:not(:disabled){transform:translateY(-1px);box-shadow:0 8px 28px var(--aglow)}\n.btnp:disabled{opacity:.3;cursor:not-allowed;transform:none;box-shadow:none}\n.bsm{padding:8px 15px;font-size:12px}\n\n/* CLIP EDIT MODAL */\n.modal-bg{display:none;position:fixed;inset:0;background:rgba(0,0,0,.7);z-index:500;align-items:center;justify-content:center}\n.modal-bg.open{display:flex}\n.modal{background:var(--s2);border:1px solid var(--b2);border-radius:var(--r3);padding:28px;width:min(520px,95vw);animation:fu .25s ease}\n.modal h3{font-size:17px;font-family:\'Syne\',sans-serif;font-weight:800;margin-bottom:18px}\n.mrow{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:12px}\n.mfield{display:flex;flex-direction:column;gap:5px}\n.mfield label{font-size:11px;color:var(--t3);font-family:\'Syne\',sans-serif;font-weight:700;text-transform:uppercase;letter-spacing:.5px}\n.mfield input{padding:9px 12px;background:var(--s3);border:1px solid var(--border);border-radius:var(--r);color:var(--text);font-size:13px;font-family:\'DM Sans\',sans-serif;outline:none}\n.mfield input:focus{border-color:var(--accent)}\n.mbtns{display:flex;gap:10px;justify-content:flex-end;margin-top:20px}\n\n/* TOAST */\n#toast{position:fixed;bottom:24px;left:50%;transform:translateX(-50%) translateY(16px);background:var(--s2);border:1px solid var(--b2);border-radius:var(--r);padding:9px 20px;font-size:13px;color:var(--text);z-index:999;opacity:0;transition:all .3s;pointer-events:none;white-space:nowrap}\n#toast.show{opacity:1;transform:translateX(-50%) translateY(0)}\n\n@media(max-width:680px){\n  .arow,.expgrid,.subrow,.mrow{grid-template-columns:1fr}\n  .qgrid{grid-template-columns:repeat(3,1fr)}\n  main{padding:20px 16px 60px}\n}\n</style>\n</head>\n<body>\n<div class="blob b1"></div>\n<div class="blob b2"></div>\n\n<header>\n  <div class="hinner">\n    <div class="logo">⚔ KatanaClips</div>\n    <div class="hright">\n      <div id="sstat"><span class="sdot" id="sdot"></span><span id="stxt">Conectando...</span></div>\n      <span class="hbadge">IA · FFmpeg · Whisper</span>\n    </div>\n  </div>\n</header>\n\n<main>\n  <!-- UPLOAD -->\n  <div id="upload-section">\n    <div style="text-align:center;margin-bottom:32px">\n      <h1 style="font-size:clamp(28px,4vw,46px);font-weight:800;letter-spacing:-1px;line-height:1.1;margin-bottom:10px">\n        Transforma tus videos largos<br>\n        <span style="background:linear-gradient(120deg,#a78bfa,#e879f9,#fb7185);-webkit-background-clip:text;-webkit-text-fill-color:transparent">en clips virales con IA</span>\n      </h1>\n      <p style="color:var(--t2);font-size:16px;max-width:500px;margin:0 auto">\n        Detecta los mejores momentos, agrega subtítulos animados y exporta en 9:16 listo para TikTok, Reels y Shorts.\n      </p>\n    </div>\n    <div class="drop" id="drop">\n      <div class="dicon">🎬</div>\n      <h2>Arrastrá tu video aquí</h2>\n      <p>Podcasts, streams, entrevistas, cursos — hasta 2 horas en 4K</p>\n      <label class="dbtn" for="finput">↑ Seleccionar video</label>\n      <input type="file" id="finput" accept="video/*">\n      <div class="dfmts">\n        <span class="dfmt">MP4</span><span class="dfmt">MOV</span><span class="dfmt">MKV</span>\n        <span class="dfmt">AVI</span><span class="dfmt">4K</span><span class="dfmt">H.264</span><span class="dfmt">H.265</span>\n      </div>\n      <div class="uprog" id="uprog">\n        <div class="upbar"><div class="upfill" id="upfill"></div></div>\n        <div class="uptxt" id="uptxt">Subiendo...</div>\n      </div>\n    </div>\n  </div>\n\n  <!-- EDITOR -->\n  <div id="editor">\n    <!-- Steps -->\n    <div class="steps">\n      <div class="step active" id="st1"><div class="snum">1</div><span>Analizar</span></div>\n      <div class="sdiv"></div>\n      <div class="step" id="st2"><div class="snum">2</div><span>Seleccionar clips</span></div>\n      <div class="sdiv"></div>\n      <div class="step" id="st3"><div class="snum">3</div><span>Exportar</span></div>\n    </div>\n\n    <!-- Video -->\n    <div class="vpanel">\n      <div class="vphead">\n        <div class="vfile">\n          <div class="vico">🎥</div>\n          <div>\n            <div class="vname" id="vname">video.mp4</div>\n            <div class="vtags" id="vtags"></div>\n          </div>\n        </div>\n        <div style="display:flex;gap:8px">\n          <button class="btng bsm" id="prevbtn">▶ Preview</button>\n          <button class="btng bsm" id="changebtn">Cambiar video</button>\n        </div>\n      </div>\n      <video id="player" controls preload="metadata"></video>\n    </div>\n\n    <!-- STEP 1: Analyze -->\n    <div id="step1">\n      <div class="apanel">\n        <div class="aphead">\n          <div class="atitle">🔍 Análisis con IA</div>\n        </div>\n        <div class="arow">\n          <div class="afield">\n            <div class="alabel">Idioma del video</div>\n            <select id="lang">\n              <option value="es">Español</option>\n              <option value="en">Inglés</option>\n              <option value="pt">Portugués</option>\n              <option value="fr">Francés</option>\n            </select>\n          </div>\n          <div class="afield">\n            <div class="alabel">Clips a detectar</div>\n            <input type="number" id="maxclips" value="5" min="1" max="15">\n          </div>\n          <div class="afield">\n            <div class="alabel">Duración por clip (seg)</div>\n            <input type="number" id="cliplen" value="60" min="15" max="180">\n          </div>\n        </div>\n        <button class="analyze-btn" id="analyzebtn">\n          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/></svg>\n          Analizar video con IA\n        </button>\n      </div>\n    </div>\n\n    <!-- STEP 2: Clips selection -->\n    <div id="step2" style="display:none">\n      <div class="cgrid-wrap">\n        <div class="cghead">\n          <div class="cgtitle">✨ Momentos detectados <span id="clipcnt" style="font-size:13px;font-weight:400;color:var(--t3)"></span></div>\n          <div class="cgactions">\n            <button class="btng bsm" id="selallbtn">Seleccionar todos</button>\n            <button class="btng bsm" id="srtbtn" style="display:none">⬇ Descargar .SRT</button>\n          </div>\n        </div>\n        <div class="clips-grid" id="clipsgrid"></div>\n      </div>\n\n      <!-- Export settings -->\n      <div class="exppanel">\n        <div style="font-size:15px;font-weight:700;font-family:\'Syne\',sans-serif;margin-bottom:16px">⚙️ Configuración de exportación</div>\n        <div class="expgrid">\n          <div class="expcard">\n            <div class="ectitle">Calidad de video</div>\n            <div class="qgrid">\n              <div class="qbtn" data-q="copy"><div class="qname">COPY</div><div class="qsub">Sin re-enc</div></div>\n              <div class="qbtn" data-q="h264_720"><div class="qname">720p</div><div class="qsub">H.264</div></div>\n              <div class="qbtn active" data-q="h264_1080"><div class="qname">1080p</div><div class="qsub">H.264</div></div>\n              <div class="qbtn" data-q="h264_4k"><div class="qname">4K</div><div class="qsub">H.264</div></div>\n              <div class="qbtn" data-q="h265_4k"><div class="qname">4K</div><div class="qsub">H.265</div></div>\n            </div>\n          </div>\n          <div class="expcard">\n            <div class="ectitle">Opciones</div>\n            <div class="togglerow">\n              <span class="tlabel">📱 Reencuadre vertical 9:16</span>\n              <div class="tgl on" id="tgl-vert"></div>\n            </div>\n            <div class="togglerow">\n              <span class="tlabel">💬 Subtítulos animados</span>\n              <div class="tgl on" id="tgl-subs"></div>\n            </div>\n            <div class="subedit" id="subedit">\n              <div class="subrow">\n                <div class="subfield">\n                  <label>Color texto</label>\n                  <input type="color" id="sub-color" value="#ffffff">\n                </div>\n                <div class="subfield">\n                  <label>Tamaño fuente</label>\n                  <input type="number" id="sub-size" value="52" min="24" max="96">\n                </div>\n                <div class="subfield">\n                  <label>Posición</label>\n                  <select id="sub-pos">\n                    <option value="bottom">Abajo</option>\n                    <option value="center">Centro</option>\n                    <option value="top">Arriba</option>\n                  </select>\n                </div>\n                <div class="subfield">\n                  <label>Fondo</label>\n                  <select id="sub-bg">\n                    <option value="black@0.5">Negro semi-transparente</option>\n                    <option value="black@0.8">Negro oscuro</option>\n                    <option value="black@0.0">Sin fondo</option>\n                  </select>\n                </div>\n              </div>\n            </div>\n          </div>\n        </div>\n      </div>\n\n      <div class="actbar">\n        <button class="btng" id="backbtn">← Volver</button>\n        <button class="btnp" id="exportbtn" disabled>\n          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>\n          Exportar clips seleccionados\n        </button>\n      </div>\n    </div>\n\n    <!-- STEP 3: Results -->\n    <div id="step3" style="display:none">\n      <div class="respanel" id="respanel" style="display:block">\n        <div class="reshead">\n          <div class="restitle">✅ Clips exportados</div>\n          <div style="display:flex;gap:8px">\n            <button class="btng bsm" id="dlallbtn">⬇ Descargar todos</button>\n            <button class="btng bsm" id="newanalysis">+ Nuevo análisis</button>\n          </div>\n        </div>\n        <div class="resgrid" id="resgrid"></div>\n      </div>\n      <div class="actbar">\n        <button class="btng" id="back2btn">← Editar clips</button>\n        <button class="btng" id="resetbtn">Subir nuevo video</button>\n      </div>\n    </div>\n\n  </div><!-- /editor -->\n\n  <!-- Progress overlay (shared) -->\n  <div class="progpanel" id="progpanel">\n    <div class="progtitle"><div class="spin"></div><span id="progtitle">Procesando...</span></div>\n    <div class="progtrack"><div class="progfill" id="progfill"></div></div>\n    <div class="progstep"><span id="progstep">Iniciando...</span><span id="progpct">0%</span></div>\n  </div>\n\n</main>\n\n<!-- Clip edit modal -->\n<div class="modal-bg" id="modal">\n  <div class="modal">\n    <h3>✏️ Editar clip</h3>\n    <div class="mrow">\n      <div class="mfield"><label>Nombre</label><input type="text" id="m-label"></div>\n      <div class="mfield"><label>Inicio (segundos)</label><input type="number" id="m-start" step="0.1"></div>\n      <div class="mfield"><label>Fin (segundos)</label><input type="number" id="m-end" step="0.1"></div>\n    </div>\n    <div class="mbtns">\n      <button class="btng" id="modal-cancel">Cancelar</button>\n      <button class="btnp" id="modal-save">Guardar</button>\n    </div>\n  </div>\n</div>\n\n<div id="toast"></div>\n\n<script>\nconst API = \'\';\nconst $ = id => document.getElementById(id);\n\n// State\nlet videoId=null, videoMeta={}, detectedClips=[], selectedClips=new Set();\nlet quality=\'h264_1080\', useVertical=true, useSubs=true;\nlet analysisJobId=null, exportJobId=null;\nlet editingClipIdx=null;\n\n// Server health\nasync function checkServer(){\n  try{\n    await fetch(API+\'/docs\',{method:\'HEAD\',signal:AbortSignal.timeout(3000)});\n    $(\'sdot\').className=\'sdot on\'; $(\'stxt\').textContent=\'Servidor online\';\n  }catch{\n    $(\'sdot\').className=\'sdot off\'; $(\'stxt\').textContent=\'Servidor offline\';\n  }\n}\ncheckServer(); setInterval(checkServer,10000);\n\n// Utils\nfunction fmtT(s){const m=Math.floor(s/60),se=(s%60).toFixed(0);return`${m}:${String(se).padStart(2,\'0\')}`}\nfunction fmtSz(b){return b>1e9?(b/1e9).toFixed(2)+\' GB\':b>1e6?(b/1e6).toFixed(1)+\' MB\':(b/1024|0)+\' KB\'}\nfunction toast(msg,d=2800){const el=$(\'toast\');el.textContent=msg;el.classList.add(\'show\');setTimeout(()=>el.classList.remove(\'show\'),d)}\nfunction setStep(n){\n  [\'st1\',\'st2\',\'st3\'].forEach((id,i)=>{\n    const el=$(id); el.className=\'step\'+(i<n-1?\' done\':i===n-1?\' active\':\'\');\n  });\n  $(\'step1\').style.display=n===1?\'block\':\'none\';\n  $(\'step2\').style.display=n===2?\'block\':\'none\';\n  $(\'step3\').style.display=n===3?\'block\':\'none\';\n}\n\n// Upload\nconst drop=$(\'drop\'), finput=$(\'finput\');\ndrop.addEventListener(\'dragover\',e=>{e.preventDefault();drop.classList.add(\'over\')});\ndrop.addEventListener(\'dragleave\',()=>drop.classList.remove(\'over\'));\ndrop.addEventListener(\'drop\',e=>{e.preventDefault();drop.classList.remove(\'over\');const f=e.dataTransfer.files[0];if(f)doUpload(f)});\nfinput.addEventListener(\'change\',()=>{if(finput.files[0])doUpload(finput.files[0])});\n\nasync function doUpload(file){\n  if(!file.type.startsWith(\'video/\'))return toast(\'Solo se aceptan archivos de video.\');\n  const prog=$(\'uprog\'),fill=$(\'upfill\'),txt=$(\'uptxt\');\n  prog.style.display=\'block\';\n  const fd=new FormData(); fd.append(\'file\',file);\n  const xhr=new XMLHttpRequest(); xhr.open(\'POST\',API+\'/upload\');\n  xhr.upload.onprogress=e=>{\n    if(e.lengthComputable){fill.style.width=(e.loaded/e.total*100)+\'%\';txt.textContent=`Subiendo ${fmtSz(e.loaded)} / ${fmtSz(e.total)}`;}\n  };\n  xhr.onload=()=>{\n    prog.style.display=\'none\';fill.style.width=\'0\';\n    if(xhr.status===200){\n      const d=JSON.parse(xhr.responseText);\n      initEditor(d,file);\n    }else{\n      let e=\'Error al subir\';try{e=JSON.parse(xhr.responseText).detail||e;}catch{}\n      toast(\'❌ \'+e,5000);\n    }\n  };\n  xhr.onerror=()=>{prog.style.display=\'none\';toast(\'❌ No se puede conectar al servidor\',5000)};\n  xhr.send(fd);\n}\n\nfunction initEditor(data,file){\n  videoId=data.video_id; videoMeta=data;\n  const player=$(\'player\'); player.src=URL.createObjectURL(file);\n  $(\'vname\').textContent=data.filename||file.name;\n  const res=data.height>=2160?\'4K\':data.height>=1080?\'1080p\':\'720p\';\n  $(\'vtags\').innerHTML=[\n    `<span class="vtag">${fmtT(data.duration)}</span>`,\n    `<span class="vtag hi">${res} · ${data.video_codec.toUpperCase()}</span>`,\n    `<span class="vtag">${data.fps} fps</span>`,\n    `<span class="vtag">${fmtSz(data.size)}</span>`,\n  ].join(\'\');\n  $(\'upload-section\').style.display=\'none\';\n  $(\'editor\').style.display=\'block\';\n  setStep(1);\n  $(\'progpanel\').style.display=\'none\';\n}\n\n$(\'changebtn\').addEventListener(\'click\',()=>{\n  $(\'upload-section\').style.display=\'block\';\n  $(\'editor\').style.display=\'none\';\n  detectedClips=[]; selectedClips.clear(); videoId=null;\n});\n\n$(\'prevbtn\').addEventListener(\'click\',()=>{\n  const p=$(\'player\'); p.currentTime=0; p.play();\n});\n\n// Analyze\n$(\'analyzebtn\').addEventListener(\'click\',async()=>{\n  if(!videoId)return;\n  $(\'analyzebtn\').disabled=true;\n  $(\'progpanel\').style.display=\'block\';\n  $(\'progtitle\').textContent=\'Analizando video con IA...\';\n  setProgress(5,\'Preparando análisis...\');\n\n  const fd=new FormData();\n  fd.append(\'video_id\',videoId);\n  fd.append(\'max_clips\',$(\'maxclips\').value);\n  fd.append(\'clip_len\',$(\'cliplen\').value);\n  fd.append(\'language\',$(\'lang\').value);\n\n  let res; try{res=await fetch(API+\'/analyze\',{method:\'POST\',body:fd});}\n  catch{toast(\'❌ Error de conexión\',5000);$(\'analyzebtn\').disabled=false;return;}\n  const {job_id}=await res.json();\n  analysisJobId=job_id;\n  pollAnalysis();\n});\n\nasync function pollAnalysis(){\n  let data; try{data=await(await fetch(API+`/job/${analysisJobId}`)).json();}\n  catch{setTimeout(pollAnalysis,2000);return;}\n\n  setProgress(data.progress||0, data.step||\'...\');\n  if(data.status===\'done\'){\n    detectedClips=data.clips||[];\n    selectedClips=new Set(detectedClips.map((_,i)=>i));\n    if(data.srt) $(\'srtbtn\').style.display=\'\';\n    renderClipsGrid();\n    $(\'progpanel\').style.display=\'none\';\n    $(\'analyzebtn\').disabled=false;\n    setStep(2);\n    toast(`✨ ${detectedClips.length} momentos detectados`);\n    // store srt\n    window._srt=data.srt||\'\';\n  } else if(data.status===\'error\'){\n    toast(\'❌ \'+data.step,5000);\n    $(\'progpanel\').style.display=\'none\';\n    $(\'analyzebtn\').disabled=false;\n  } else {\n    setTimeout(pollAnalysis,1200);\n  }\n}\n\nfunction setProgress(pct,step){\n  $(\'progfill\').style.width=pct+\'%\';\n  $(\'progstep\').textContent=step;\n  $(\'progpct\').textContent=pct+\'%\';\n}\n\n// Clips grid\nfunction scoreClass(s){return s>0.7?\'high\':s>0.4?\'med\':\'low\'}\nfunction scoreLabel(s){return s>0.7?\'🔥 Viral\':\'⚡ Destacado\'}\n\nfunction renderClipsGrid(){\n  $(\'clipcnt\').textContent=`(${detectedClips.length})`;\n  $(\'clipsgrid\').innerHTML=detectedClips.map((c,i)=>`\n    <div class="clipcard${selectedClips.has(i)?\' selected\':\'\'}" data-i="${i}">\n      <div class="cthumb">\n        <div class="cthumb-ico">🎞</div>\n        <div class="ccheck">${selectedClips.has(i)?\'✓\':\'\'}</div>\n        <div class="cscore ${scoreClass(c.score)}">${scoreLabel(c.score)}</div>\n      </div>\n      <div class="cbody">\n        <div class="creason">${c.reason}</div>\n        <div class="ctimes">${fmtT(c.start)} → ${fmtT(c.end)}</div>\n        <div class="cdur">${fmtT(c.end-c.start)} duración · ${c.subtitle_segments?.length||0} subtítulos</div>\n        <button class="cedit" data-i="${i}">✏️ Editar tiempos y nombre</button>\n      </div>\n    </div>\n  `).join(\'\');\n\n  document.querySelectorAll(\'.clipcard\').forEach(card=>{\n    card.addEventListener(\'click\',e=>{\n      if(e.target.classList.contains(\'cedit\'))return;\n      const i=parseInt(card.dataset.i);\n      if(selectedClips.has(i))selectedClips.delete(i);\n      else selectedClips.add(i);\n      renderClipsGrid();\n      updateExportBtn();\n    });\n  });\n  document.querySelectorAll(\'.cedit\').forEach(btn=>{\n    btn.addEventListener(\'click\',e=>{e.stopPropagation();openModal(parseInt(btn.dataset.i));});\n  });\n  updateExportBtn();\n}\n\nfunction updateExportBtn(){\n  $(\'exportbtn\').disabled=selectedClips.size===0;\n}\n\n$(\'selallbtn\').addEventListener(\'click\',()=>{\n  if(selectedClips.size===detectedClips.length)selectedClips.clear();\n  else detectedClips.forEach((_,i)=>selectedClips.add(i));\n  renderClipsGrid();\n});\n\n$(\'srtbtn\').addEventListener(\'click\',()=>{\n  const blob=new Blob([window._srt||\'\'],{type:\'text/plain\'});\n  const a=document.createElement(\'a\'); a.href=URL.createObjectURL(blob);\n  a.download=\'subtitulos.srt\'; a.click();\n});\n\n// Modal\nfunction openModal(i){\n  editingClipIdx=i;\n  const c=detectedClips[i];\n  $(\'m-label\').value=c.label||`clip_${i+1}`;\n  $(\'m-start\').value=c.start;\n  $(\'m-end\').value=c.end;\n  $(\'modal\').classList.add(\'open\');\n}\n$(\'modal-cancel\').addEventListener(\'click\',()=>$(\'modal\').classList.remove(\'open\'));\n$(\'modal-save\').addEventListener(\'click\',()=>{\n  if(editingClipIdx===null)return;\n  detectedClips[editingClipIdx].label=$(\'m-label\').value.trim()||detectedClips[editingClipIdx].label;\n  detectedClips[editingClipIdx].start=parseFloat($(\'m-start\').value);\n  detectedClips[editingClipIdx].end=parseFloat($(\'m-end\').value);\n  $(\'modal\').classList.remove(\'open\');\n  renderClipsGrid();\n  toast(\'Clip actualizado ✓\');\n});\n\n// Quality\ndocument.querySelectorAll(\'.qbtn\').forEach(b=>{\n  b.addEventListener(\'click\',()=>{\n    document.querySelectorAll(\'.qbtn\').forEach(x=>x.classList.remove(\'active\'));\n    b.classList.add(\'active\'); quality=b.dataset.q;\n  });\n});\n\n// Toggles\nfunction makeTgl(id,cb){\n  const el=$(id);\n  el.addEventListener(\'click\',()=>{el.classList.toggle(\'on\');cb(el.classList.contains(\'on\'));});\n  return ()=>el.classList.contains(\'on\');\n}\nconst getVert=makeTgl(\'tgl-vert\',v=>{useVertical=v});\nconst getSubs=makeTgl(\'tgl-subs\',v=>{\n  useSubs=v;\n  $(\'subedit\').style.display=v?\'block\':\'none\';\n});\n$(\'subedit\').style.display=\'block\';\n\n// Export\n$(\'exportbtn\').addEventListener(\'click\',async()=>{\n  const sel=[...selectedClips].map(i=>detectedClips[i]);\n  if(!sel.length)return;\n  $(\'exportbtn\').disabled=true;\n  $(\'progpanel\').style.display=\'block\';\n  $(\'progtitle\').textContent=\'Exportando clips...\';\n  setProgress(0,\'Preparando...\');\n\n  const style={\n    color: $(\'sub-color\').value,\n    size:  $(\'sub-size\').value,\n    position: $(\'sub-pos\').value,\n    bg:    $(\'sub-bg\').value,\n  };\n\n  const clipsToExport=sel.map(c=>({\n    ...c,\n    subtitle_segments: useSubs?(c.subtitle_segments||[]):[],\n  }));\n\n  const fd=new FormData();\n  fd.append(\'video_id\',videoId);\n  fd.append(\'clips_json\',JSON.stringify(clipsToExport));\n  fd.append(\'quality\',quality);\n  fd.append(\'vertical\',useVertical?\'true\':\'false\');\n  fd.append(\'subtitle_style_json\',JSON.stringify(style));\n\n  let res; try{res=await fetch(API+\'/export\',{method:\'POST\',body:fd});}\n  catch{toast(\'❌ Error de conexión\',5000);$(\'exportbtn\').disabled=false;return;}\n  const {job_id}=await res.json();\n  exportJobId=job_id;\n  pollExport();\n});\n\nasync function pollExport(){\n  let data; try{data=await(await fetch(API+`/job/${exportJobId}`)).json();}\n  catch{setTimeout(pollExport,2000);return;}\n\n  setProgress(data.progress||0,`Clip ${data.done||0}/${data.total||0}...`);\n  if(data.status===\'done\'){\n    $(\'progpanel\').style.display=\'none\';\n    $(\'exportbtn\').disabled=false;\n    showResults(data);\n    setStep(3);\n    toast(`✅ ${data.results?.length||0} clips exportados`);\n  } else if(data.status===\'error\'){\n    toast(\'❌ Error en exportación\',5000);\n    $(\'progpanel\').style.display=\'none\';\n    $(\'exportbtn\').disabled=false;\n  } else {\n    setTimeout(pollExport,1500);\n  }\n}\n\nfunction showResults(data){\n  const all=[...(data.results||[]),...(data.errors||[])].sort((a,b)=>a.index-b.index);\n  $(\'resgrid\').innerHTML=all.map(item=>{\n    if(item.error) return `\n      <div class="rescard">\n        <div class="rcthumb"><span style="font-size:26px;color:var(--err)">⚠️</span></div>\n        <div class="rcbody"><div class="rcname">${item.label}</div><div class="rcmeta">Error al exportar</div><div class="rcdl err">No disponible</div></div>\n      </div>`;\n    return `\n      <div class="rescard">\n        <div class="rcthumb">\n          <span style="font-size:28px;color:var(--t3);z-index:1">🎬</span>\n          <div class="rcbadge">#${item.index}</div>\n          <video src="${API}${item.url}" muted loop preload="none" onmouseenter="this.play()" onmouseleave="this.pause();this.currentTime=0" style="position:absolute;inset:0;width:100%;height:100%;object-fit:cover"></video>\n        </div>\n        <div class="rcbody">\n          <div class="rcname">${item.filename}</div>\n          <div class="rcmeta">${fmtT(item.duration)} · ${fmtSz(item.size)}</div>\n          <a class="rcdl" href="${API}${item.url}" download="${item.filename}">⬇ Descargar</a>\n        </div>\n      </div>`;\n  }).join(\'\');\n}\n\n$(\'dlallbtn\').addEventListener(\'click\',()=>{\n  document.querySelectorAll(\'#resgrid a.rcdl\').forEach((a,i)=>{\n    setTimeout(()=>{const t=document.createElement(\'a\');t.href=a.href;t.download=a.download;t.click();},i*400);\n  });\n});\n\n$(\'backbtn\').addEventListener(\'click\',()=>setStep(1));\n$(\'back2btn\').addEventListener(\'click\',()=>setStep(2));\n$(\'newanalysis\').addEventListener(\'click\',()=>{selectedClips=new Set(detectedClips.map((_,i)=>i));renderClipsGrid();setStep(2);});\n$(\'resetbtn\').addEventListener(\'click\',()=>{\n  $(\'upload-section\').style.display=\'block\';\n  $(\'editor\').style.display=\'none\';\n  videoId=null; detectedClips=[]; selectedClips.clear();\n});\n\nwindow.addEventListener(\'click\',e=>{if(e.target===$(\'modal\'))$(\'modal\').classList.remove(\'open\')});\n</script>\n</body>\n</html>\n'

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
    quality: str,           # copy | h264_720 | h264_1080 | h264_4k | h265_4k
    vertical: bool,         # reframe to 9:16
    subtitle_segments: list[dict],
    subtitle_style: dict,
) -> None:
    duration = end - start
    vf_parts = []

    # 1. Vertical reframe (9:16)
    if vertical:
        # crop to 9:16 from center, then scale
        target_h_map = {"h264_720":"1280","h264_1080":"1920","h264_4k":"3840","h265_4k":"3840","copy":"1920"}
        th = target_h_map.get(quality, "1920")
        tw = str(int(int(th)*9//16))
        vf_parts.append(f"crop=ih*9/16:ih,scale={tw}:{th}:flags=lanczos")
    else:
        scale_map = {
            "h264_720":  "scale=1280:720:flags=lanczos,force_original_aspect_ratio=decrease",
            "h264_1080": "scale=1920:1080:flags=lanczos,force_original_aspect_ratio=decrease",
            "h264_4k":   "scale=3840:2160:flags=lanczos,force_original_aspect_ratio=decrease",
            "h265_4k":   "scale=3840:2160:flags=lanczos,force_original_aspect_ratio=decrease",
        }
        if quality in scale_map:
            vf_parts.append(scale_map[quality])

    # 2. Subtitles
    if subtitle_segments:
        sub_filter = build_subtitle_filter(subtitle_segments, subtitle_style)
        if sub_filter:
            vf_parts.append(sub_filter)

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
    return HTMLResponse(HTML_PAGE)
