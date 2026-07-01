"""
PaddleOCR — wrapper web (FastAPI) — Altcorp Auto Service.

Recursos:
  - OCR multilíngue (idioma selecionável por requisição, com cache de modelos).
  - Imagem anotada (caixas + índice) devolvida em base64.
  - Estatísticas: linhas, palavras, caracteres, confiança média/mínima, tempo.
  - Resultado por linha (texto + confiança + caixa).

Endpoints:
  GET  /            -> UI
  POST /ocr         -> processa e devolve JSON
  GET  /healthz     -> healthcheck (CORS liberado)
  GET  /static/...  -> assets (logos)
"""
import io
import os
import time
import base64

import numpy as np
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Request
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from PIL import Image, ImageDraw, ImageFont

app = FastAPI(title="Altcorp · Auto Service · PaddleOCR", version="2.0.0")

app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)
app.mount("/static", StaticFiles(directory="/app/static"), name="static")

DEFAULT_LANG = os.getenv("PADDLE_OCR_LANG", "pt")
# Idiomas oferecidos na UI (código PaddleOCR -> rótulo)
LANGS = {
    "pt": "Português", "en": "Inglês", "es": "Espanhol",
    "french": "Francês", "german": "Alemão",
    "ch": "Chinês", "japan": "Japonês", "korean": "Coreano",
}
_engines = {}  # cache de instâncias por idioma


def get_ocr(lang: str):
    if lang not in LANGS:
        lang = DEFAULT_LANG
    if lang not in _engines:
        from paddleocr import PaddleOCR
        _engines[lang] = PaddleOCR(use_angle_cls=True, lang=lang, show_log=False)
    return _engines[lang]


def _annotate(image: Image.Image, lines) -> str:
    """Desenha as caixas detectadas e devolve PNG em base64."""
    img = image.convert("RGB").copy()
    draw = ImageDraw.Draw(img, "RGBA")
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 16)
    except Exception:
        font = ImageFont.load_default()
    for i, ln in enumerate(lines, 1):
        pts = [(p[0], p[1]) for p in ln["box"]]
        draw.polygon(pts, outline=(28, 67, 98, 255), width=3)
        draw.polygon(pts, fill=(63, 125, 110, 40))
        x, y = pts[0]
        tag = str(i)
        tw = draw.textlength(tag, font=font)
        draw.rectangle([x, y - 20, x + tw + 10, y], fill=(28, 67, 98, 255))
        draw.text((x + 5, y - 19), tag, fill=(255, 255, 255, 255), font=font)
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


@app.get("/healthz")
def healthz():
    return {"status": "ok", "service": "paddleocr",
            "loaded_langs": list(_engines.keys()), "default_lang": DEFAULT_LANG}


@app.get("/langs")
def langs():
    return {"default": DEFAULT_LANG, "langs": LANGS}


@app.post("/ocr")
async def run_ocr(file: UploadFile = File(...), lang: str = Form(DEFAULT_LANG)):
    if file.content_type and not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Envie um arquivo de imagem.")
    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=400, detail="Arquivo vazio.")
    try:
        image = Image.open(io.BytesIO(raw)).convert("RGB")
    except Exception:
        raise HTTPException(status_code=400, detail="Não foi possível ler a imagem.")

    t0 = time.perf_counter()
    try:
        result = get_ocr(lang).ocr(np.array(image), cls=True)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Falha no OCR: {exc}")
    elapsed = time.perf_counter() - t0

    lines = []
    for page in (result or []):
        for box, (text, conf) in (page or []):
            lines.append({
                "text": text,
                "confidence": round(float(conf), 4),
                "box": [[float(x), float(y)] for x, y in box],
            })

    full_text = "\n".join(l["text"] for l in lines)
    confs = [l["confidence"] for l in lines]
    words = sum(len(l["text"].split()) for l in lines)
    stats = {
        "lines": len(lines),
        "words": words,
        "chars": len(full_text.replace("\n", "")),
        "avg_confidence": round(sum(confs) / len(confs), 4) if confs else 0.0,
        "min_confidence": round(min(confs), 4) if confs else 0.0,
        "process_time": round(elapsed, 2),
    }

    annotated = _annotate(image, lines) if lines else None

    return JSONResponse({
        "lang": lang if lang in LANGS else DEFAULT_LANG,
        "text": full_text,
        "lines": lines,
        "stats": stats,
        "annotated_image": annotated,
    })


@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    opts = "".join(
        f'<option value="{code}"{" selected" if code == DEFAULT_LANG else ""}>{label}</option>'
        for code, label in LANGS.items()
    )
    # Prefixo do gateway (ex.: "/ocr") para o <base href>
    prefix = request.headers.get("x-forwarded-prefix", "").rstrip("/")
    return (HTML_PAGE
            .replace("{{LANG_OPTIONS}}", opts)
            .replace("{{BASE}}", prefix + "/"))


HTML_PAGE = r"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <base href="{{BASE}}" />
  <title>OCR · Auto Service</title>
  <link rel="icon" href="static/favicon.ico" />
  <link rel="preconnect" href="https://fonts.googleapis.com" />
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
  <link href="https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:opsz,wght@12..96,400..800&family=Manrope:wght@400;500;600;700&family=Space+Mono:wght@400;700&display=swap" rel="stylesheet" />
  <style>
    :root{
      --navy:#1c4362; --navy-deep:#10283b; --navy-line:#2b5a7e;
      --paper:#f3efe7; --card:#fbf9f4; --ink:#152430; --muted:#5e6e79; --line:#d8d0c2;
      --accent:#b3812f; --accent-ink:#8c6321;   /* ocre — tema do OCR */
      --err:#b1503f;
      --sans:"Manrope",system-ui,sans-serif; --disp:"Bricolage Grotesque",serif; --mono:"Space Mono",monospace;
    }
    *{box-sizing:border-box;margin:0;padding:0}
    html{scroll-behavior:smooth}
    body{font-family:var(--sans);color:var(--ink);background:var(--paper);min-height:100vh;
      background-image:linear-gradient(rgba(28,67,98,.035) 1px,transparent 1px),linear-gradient(90deg,rgba(28,67,98,.035) 1px,transparent 1px);background-size:26px 26px}
    a{color:inherit}
    .nav{display:flex;align-items:center;justify-content:space-between;padding:16px 26px;background:var(--navy);color:#fff;border-bottom:3px solid var(--navy-deep)}
    .nav__brand{display:flex;align-items:center;gap:12px}
    .nav__brand img{height:30px;display:block}
    .nav__brand .wm{font-family:var(--disp);font-weight:700;font-size:17px}
    .nav__brand .wm small{display:block;font-family:var(--mono);font-size:9.5px;letter-spacing:3px;opacity:.7;font-weight:400}
    .nav__back{font-family:var(--mono);font-size:12px;text-decoration:none;color:#cfe0ec;border:1px solid var(--navy-line);padding:8px 14px;border-radius:2px;transition:.15s}
    .nav__back:hover{background:var(--navy-deep);color:#fff}
    .wrap{max-width:1000px;margin:0 auto;padding:44px 24px 80px}
    .kicker{font-family:var(--mono);font-size:12px;letter-spacing:3px;text-transform:uppercase;color:var(--accent-ink);display:flex;align-items:center;gap:10px}
    .kicker::before{content:"";width:26px;height:2px;background:var(--accent)}
    h1{font-family:var(--disp);font-weight:700;font-size:clamp(30px,5vw,46px);line-height:1.02;margin:14px 0 10px}
    .lede{color:var(--muted);font-size:16px;max-width:640px}
    .panel{background:var(--card);border:1px solid var(--line);border-radius:4px;padding:26px;margin-top:28px;position:relative}
    .panel::before,.panel::after{content:"";position:absolute;width:9px;height:9px;border:2px solid var(--navy)}
    .panel::before{top:-1px;left:-1px;border-right:0;border-bottom:0}
    .panel::after{bottom:-1px;right:-1px;border-left:0;border-top:0}
    .panel__label{font-family:var(--mono);font-size:11px;letter-spacing:2px;text-transform:uppercase;color:var(--muted);margin-bottom:16px}
    .step-n{color:var(--accent);font-weight:700}
    .drop{border:2px dashed var(--line);border-radius:4px;padding:44px 20px;text-align:center;cursor:pointer;transition:.15s;background:var(--paper)}
    .drop:hover,.drop.drag{border-color:var(--accent);background:#f6f0e3}
    .drop .ico{font-size:40px}
    .drop p{color:var(--muted);font-size:14px;margin-top:10px}
    .drop b{color:var(--ink)}
    #fileName{font-family:var(--mono);color:var(--accent-ink);font-size:13px;margin-top:8px}
    input[type=file]{display:none}
    .row{display:flex;align-items:flex-end;gap:16px;flex-wrap:wrap;margin-top:4px}
    .field{display:flex;flex-direction:column;gap:8px}
    .flabel{font-family:var(--mono);font-size:11px;letter-spacing:1.5px;text-transform:uppercase;color:var(--muted)}
    select{font-family:var(--sans);font-size:14px;padding:11px 14px;border:1px solid var(--line);border-radius:3px;background:var(--paper);color:var(--ink);cursor:pointer;min-width:180px}
    .btn{margin-left:auto;padding:14px 26px;border:none;border-radius:3px;background:var(--navy);color:#fff;font-weight:700;font-size:15px;cursor:pointer;font-family:var(--disp);transition:.15s}
    .btn:hover:not(:disabled){background:var(--navy-deep)}
    .btn:disabled{opacity:.45;cursor:not-allowed}
    .status{margin-top:16px;font-size:14px;color:var(--muted);min-height:20px;font-family:var(--mono)}
    .status.err{color:var(--err)}
    .result{display:none}
    .result.show{display:block;animation:fade .35s ease}
    @keyframes fade{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:none}}
    .meta{display:grid;grid-template-columns:repeat(5,1fr);gap:1px;background:var(--line);border:1px solid var(--line);border-radius:4px;overflow:hidden;margin-bottom:20px}
    .meta .cell{background:var(--card);padding:14px 12px;text-align:center}
    .meta .k{font-family:var(--mono);font-size:10px;letter-spacing:1px;text-transform:uppercase;color:var(--muted)}
    .meta .v{font-family:var(--disp);font-weight:700;font-size:22px;margin-top:4px}
    .split{display:grid;grid-template-columns:1fr 1fr;gap:20px}
    .frame{border:1px solid var(--line);border-radius:4px;overflow:hidden;background:var(--card)}
    .frame .cap{font-family:var(--mono);font-size:11px;letter-spacing:1.5px;text-transform:uppercase;color:var(--muted);padding:9px 12px;border-bottom:1px solid var(--line);display:flex;justify-content:space-between}
    .frame .body{padding:12px}
    .frame img{max-width:100%;display:block;margin:0 auto}
    textarea{width:100%;min-height:230px;background:var(--paper);color:var(--ink);border:1px solid var(--line);border-radius:3px;padding:12px;font-family:var(--mono);font-size:13px;line-height:1.6;resize:vertical}
    .tblwrap{max-height:260px;overflow:auto;border:1px solid var(--line);border-radius:4px;margin-top:20px}
    table{width:100%;border-collapse:collapse;font-size:13px}
    th{position:sticky;top:0;background:var(--navy);color:#fff;font-family:var(--mono);font-size:10px;letter-spacing:1px;text-transform:uppercase;padding:10px 12px;text-align:left}
    td{padding:9px 12px;border-bottom:1px solid var(--line)}
    tr:last-child td{border-bottom:0}
    .conf{display:inline-flex;align-items:center;gap:8px;font-family:var(--mono);font-size:12px}
    .bar{width:60px;height:6px;border-radius:3px;background:var(--line);overflow:hidden}
    .bar i{display:block;height:100%}
    .btns{display:flex;gap:12px;margin-top:16px;flex-wrap:wrap}
    .mini{padding:10px 16px;border-radius:3px;border:1px solid var(--line);background:transparent;color:var(--ink);font-family:var(--mono);font-size:12px;cursor:pointer;text-decoration:none;transition:.15s}
    .mini:hover{border-color:var(--accent);color:var(--accent-ink)}
    .mini.solid{background:var(--accent);color:#fff;border-color:var(--accent)}
    .mini.solid:hover{background:var(--accent-ink);color:#fff}
    .spinner{display:inline-block;width:14px;height:14px;border:2px solid #d9cfb6;border-top-color:var(--accent);border-radius:50%;animation:spin .8s linear infinite;vertical-align:-2px;margin-right:6px}
    @keyframes spin{to{transform:rotate(360deg)}}
    footer{text-align:center;padding:30px;color:var(--muted);font-family:var(--mono);font-size:11px;letter-spacing:1px}
    @media (max-width:680px){.split{grid-template-columns:1fr}.meta{grid-template-columns:repeat(2,1fr)}.btn{margin-left:0;width:100%}.wrap{padding:32px 16px 60px}}
  </style>
</head>
<body>
  <nav class="nav">
    <div class="nav__brand"><img src="static/logo-branco.png" alt="Altcorp"><div class="wm">Auto Service<small>ALTCORP</small></div></div>
    <a class="nav__back" href="/">← HUB</a>
  </nav>

  <div class="wrap">
    <div class="kicker">Serviço 04 · Reconhecimento de Texto</div>
    <h1>OCR — Extração de Texto</h1>
    <p class="lede">Extraia texto de imagens e documentos digitalizados em múltiplos idiomas. Veja as regiões detectadas, a confiança por linha e baixe o resultado.</p>

    <form id="form">
      <div class="panel">
        <div class="panel__label"><span class="step-n">01</span> — Envie a imagem</div>
        <label class="drop" id="drop">
          <div class="ico">📄</div>
          <p><b>Clique para escolher</b> ou arraste a imagem aqui</p>
          <p style="font-size:12px">Imagem de documento, foto de texto, captura de tela…</p>
          <div id="fileName"></div>
          <input type="file" id="file" accept="image/*" />
        </label>
        <div class="row">
          <div class="field">
            <span class="flabel">Idioma</span>
            <select id="lang">{{LANG_OPTIONS}}</select>
          </div>
          <button class="btn" id="submit" type="submit" disabled>🔎 Extrair texto</button>
        </div>
        <div class="status" id="status"></div>
      </div>
    </form>

    <div class="result panel" id="result">
      <div class="panel__label"><span class="step-n">02</span> — Resultado</div>
      <div class="meta">
        <div class="cell"><div class="k">Linhas</div><div class="v" id="mLines">—</div></div>
        <div class="cell"><div class="k">Palavras</div><div class="v" id="mWords">—</div></div>
        <div class="cell"><div class="k">Caracteres</div><div class="v" id="mChars">—</div></div>
        <div class="cell"><div class="k">Confiança</div><div class="v" id="mConf">—</div></div>
        <div class="cell"><div class="k">Tempo</div><div class="v" id="mTime">—</div></div>
      </div>

      <div class="split">
        <div class="frame">
          <div class="cap"><span>Regiões detectadas</span></div>
          <div class="body"><img id="annot" alt="Anotado"></div>
        </div>
        <div class="frame">
          <div class="cap"><span>Texto extraído</span></div>
          <div class="body">
            <textarea id="output" readonly></textarea>
            <div class="btns">
              <button class="mini solid" id="copy" type="button">📋 Copiar</button>
              <a class="mini" id="dlTxt">⬇ .txt</a>
              <a class="mini" id="dlJson">⬇ .json</a>
            </div>
          </div>
        </div>
      </div>

      <div class="tblwrap">
        <table>
          <thead><tr><th style="width:44px">#</th><th>Texto</th><th style="width:150px">Confiança</th></tr></thead>
          <tbody id="tbody"></tbody>
        </table>
      </div>
    </div>
  </div>

  <footer>ALTCORP · AUTO SERVICE — PADDLEOCR · FASTAPI</footer>

  <script>
    const $=s=>document.querySelector(s);
    const drop=$("#drop"),fileInput=$("#file"),fileName=$("#fileName"),submit=$("#submit"),
      statusEl=$("#status"),result=$("#result"),output=$("#output"),annot=$("#annot"),tbody=$("#tbody");
    let lastJson=null;

    function fmtBytes(b){b=+b;if(!b)return"";const u=["B","KB","MB"];let i=0;while(b>=1024&&i<u.length-1){b/=1024;i++;}return b.toFixed(b<10&&i>0?1:0)+" "+u[i];}
    function setFile(f){if(!f)return;const dt=new DataTransfer();dt.items.add(f);fileInput.files=dt.files;fileName.textContent="▸ "+f.name+" ("+fmtBytes(f.size)+")";submit.disabled=false;}
    fileInput.addEventListener("change",e=>setFile(e.target.files[0]));
    ["dragover","dragenter"].forEach(ev=>drop.addEventListener(ev,e=>{e.preventDefault();drop.classList.add("drag");}));
    ["dragleave","drop"].forEach(ev=>drop.addEventListener(ev,e=>{e.preventDefault();drop.classList.remove("drag");}));
    drop.addEventListener("drop",e=>setFile(e.dataTransfer.files[0]));

    function confColor(c){ return c>=0.9?"#3f7d6e":c>=0.7?"#b3812f":"#b1503f"; }

    $("#form").addEventListener("submit",async e=>{
      e.preventDefault();
      if(!fileInput.files[0])return;
      submit.disabled=true;result.classList.remove("show");
      statusEl.className="status";
      statusEl.innerHTML='<span class="spinner"></span> Processando… a 1ª execução no idioma baixa os modelos.';
      const fd=new FormData();
      fd.append("file",fileInput.files[0]);
      fd.append("lang",$("#lang").value);
      try{
        const res=await fetch("ocr",{method:"POST",body:fd});
        const data=await res.json();
        if(!res.ok)throw new Error(data.detail||("Erro "+res.status));
        lastJson=data;
        const s=data.stats;
        $("#mLines").textContent=s.lines;
        $("#mWords").textContent=s.words;
        $("#mChars").textContent=s.chars;
        $("#mConf").textContent=(s.avg_confidence*100).toFixed(0)+"%";
        $("#mTime").textContent=s.process_time+"s";
        output.value=data.text||"(nenhum texto detectado)";
        if(data.annotated_image){annot.src=data.annotated_image;annot.style.display="block";}
        else{annot.style.display="none";}
        tbody.innerHTML=data.lines.map((l,i)=>{
          const c=l.confidence,col=confColor(c);
          return `<tr><td>${i+1}</td><td>${l.text.replace(/</g,"&lt;")}</td>
            <td><span class="conf"><span class="bar"><i style="width:${(c*100).toFixed(0)}%;background:${col}"></i></span>${(c*100).toFixed(0)}%</span></td></tr>`;
        }).join("")||`<tr><td colspan="3" style="color:var(--muted)">Nenhuma linha detectada.</td></tr>`;
        // downloads
        $("#dlTxt").href=URL.createObjectURL(new Blob([data.text],{type:"text/plain"}));
        $("#dlTxt").download="ocr.txt";
        $("#dlJson").href=URL.createObjectURL(new Blob([JSON.stringify(data,null,2)],{type:"application/json"}));
        $("#dlJson").download="ocr.json";
        result.classList.add("show");
        statusEl.textContent="✓ Concluído — "+s.lines+" linha(s) em "+s.process_time+"s.";
        result.scrollIntoView({behavior:"smooth",block:"nearest"});
      }catch(err){statusEl.className="status err";statusEl.textContent="✕ "+err.message;}
      finally{submit.disabled=false;}
    });

    $("#copy").addEventListener("click",()=>{output.select();document.execCommand("copy");$("#copy").textContent="✓ Copiado";setTimeout(()=>$("#copy").textContent="📋 Copiar",1500);});
  </script>
</body>
</html>
"""
