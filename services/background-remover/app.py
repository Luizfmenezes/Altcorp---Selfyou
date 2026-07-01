"""
Background Remover — wrapper web (Flask) — Altcorp Auto Service.

Recursos:
  - Remoção de fundo via CLI 'backgroundremover' (modelos u2net / u2netp /
    u2net_human_seg).
  - Alpha matting opcional (bordas mais suaves).
  - Substituição de fundo: transparente | branco | cor sólida (hex).
  - Metadados no cabeçalho da resposta (tempo, modelo, dimensões, tamanhos).

Endpoints:
  GET  /            -> UI
  POST /remove      -> processa e devolve PNG/JPEG
  GET  /healthz     -> healthcheck (CORS liberado para o Hub)
  GET  /static/...  -> assets (logos)
"""
import io
import os
import re
import time
import uuid
import subprocess

from flask import (
    Flask, request, send_file, render_template, jsonify, after_this_request
)
from werkzeug.utils import secure_filename
from PIL import Image

app = Flask(__name__)

UPLOAD_DIR = "/app/uploads"
RESULT_DIR = "/app/results"
ALLOWED = {"png", "jpg", "jpeg", "webp", "bmp"}
MODELS = {"u2net", "u2netp", "u2net_human_seg"}
MAX_MB = 25
HEX_RE = re.compile(r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")

app.config["MAX_CONTENT_LENGTH"] = MAX_MB * 1024 * 1024
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(RESULT_DIR, exist_ok=True)


@app.after_request
def add_cors(resp):
    # Permite que o Hub (localhost:8080) consulte o /healthz
    resp.headers["Access-Control-Allow-Origin"] = "*"
    resp.headers["Access-Control-Expose-Headers"] = (
        "X-Process-Time, X-Model, X-Dimensions, X-Orig-Bytes, "
        "X-Out-Bytes, X-Output-Format, X-Background"
    )
    return resp


def _allowed(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED


def _hex_to_rgb(value: str):
    value = value.lstrip("#")
    if len(value) == 3:
        value = "".join(c * 2 for c in value)
    return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4))


@app.get("/")
def index():
    # Prefixo do gateway (ex.: "/bg") para montar o <base href> corretamente
    prefix = request.headers.get("X-Forwarded-Prefix", "").rstrip("/")
    return render_template("index.html", max_mb=MAX_MB, prefix=prefix)


@app.get("/healthz")
def healthz():
    return jsonify(status="ok", service="background-remover", models=sorted(MODELS)), 200


@app.post("/remove")
def remove_background():
    if "image" not in request.files:
        return jsonify(error="Nenhum arquivo enviado (campo 'image')."), 400

    file = request.files["image"]
    if file.filename == "":
        return jsonify(error="Nome de arquivo vazio."), 400
    if not _allowed(file.filename):
        return jsonify(error=f"Formato não suportado. Use: {', '.join(sorted(ALLOWED))}."), 400

    # --- Parâmetros ------------------------------------------------------
    model = request.form.get("model", "u2net")
    if model not in MODELS:
        model = "u2net"
    alpha_matting = request.form.get("alpha_matting", "false").lower() in ("1", "true", "on", "yes")
    background = request.form.get("background", "transparent").strip().lower()
    # background: "transparent" | "white" | "#RRGGBB"
    bg_rgb = None
    if background == "white":
        bg_rgb = (255, 255, 255)
    elif HEX_RE.match(background):
        bg_rgb = _hex_to_rgb(background)
    elif background != "transparent":
        background = "transparent"

    token = uuid.uuid4().hex
    safe_name = secure_filename(file.filename)
    in_path = os.path.join(UPLOAD_DIR, f"{token}_{safe_name}")
    cut_path = os.path.join(RESULT_DIR, f"{token}.png")
    final_path = cut_path
    file.save(in_path)
    orig_bytes = os.path.getsize(in_path)

    @after_this_request
    def _cleanup(response):
        for p in {in_path, cut_path, final_path}:
            try:
                if os.path.exists(p):
                    os.remove(p)
            except OSError:
                pass
        return response

    # --- Remoção de fundo ------------------------------------------------
    cmd = ["backgroundremover", "-i", in_path, "-m", model]
    if alpha_matting:
        cmd += ["-a", "-ae", "15"]
    cmd += ["-o", cut_path]

    t0 = time.perf_counter()
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=550)
    except subprocess.TimeoutExpired:
        return jsonify(error="Processamento excedeu o tempo limite."), 504
    if proc.returncode != 0 or not os.path.exists(cut_path):
        return jsonify(
            error="Falha ao remover o fundo.",
            detail=(proc.stderr or proc.stdout or "").strip()[-800:],
        ), 500

    out_format = "png"
    mimetype = "image/png"

    # --- Substituição de fundo (opcional) --------------------------------
    with Image.open(cut_path) as cut:
        cut = cut.convert("RGBA")
        dimensions = f"{cut.width}x{cut.height}"
        if bg_rgb is not None:
            bg = Image.new("RGBA", cut.size, bg_rgb + (255,))
            bg.alpha_composite(cut)
            composed = bg.convert("RGB")
            final_path = os.path.join(RESULT_DIR, f"{token}_final.jpg")
            composed.save(final_path, "JPEG", quality=92)
            out_format = "jpg"
            mimetype = "image/jpeg"
        else:
            final_path = cut_path  # PNG transparente

    elapsed = time.perf_counter() - t0
    out_bytes = os.path.getsize(final_path)

    base = os.path.splitext(safe_name)[0]
    download_name = f"{base}_sem_fundo.{out_format}"
    resp = send_file(final_path, mimetype=mimetype, as_attachment=False,
                     download_name=download_name)
    resp.headers["X-Process-Time"] = f"{elapsed:.2f}"
    resp.headers["X-Model"] = model
    resp.headers["X-Dimensions"] = dimensions
    resp.headers["X-Orig-Bytes"] = str(orig_bytes)
    resp.headers["X-Out-Bytes"] = str(out_bytes)
    resp.headers["X-Output-Format"] = out_format
    resp.headers["X-Background"] = background
    return resp


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
