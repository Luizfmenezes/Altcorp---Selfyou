"""
Auth Gateway — serviço de login único (Flask) — Altcorp Auto Service.

Fluxo (forward-auth com Nginx auth_request):
  - GET  /auth    -> 200 se a sessão for válida, senão 401 (usado pelo Nginx)
  - GET  /login   -> tela de login
  - POST /login   -> valida usuário/senha do .env, grava cookie de sessão
  - GET  /logout  -> encerra a sessão
  - GET  /healthz -> healthcheck

Usuário e senha únicos vêm de AUTH_USER / AUTH_PASSWORD (.env).
A sessão é um cookie assinado (itsdangerous), com expiração.
"""
import os

from flask import (
    Flask, request, redirect, render_template, make_response
)
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired

app = Flask(__name__)

USER = os.getenv("AUTH_USER", "admin")
PASSWORD = os.getenv("AUTH_PASSWORD", "admin")
SECRET = os.getenv("AUTH_SECRET_KEY", "change-this-secret")
COOKIE = os.getenv("AUTH_COOKIE_NAME", "as_session")
MAX_AGE = int(os.getenv("AUTH_SESSION_HOURS", "12")) * 3600
SECURE = os.getenv("AUTH_COOKIE_SECURE", "false").lower() in ("1", "true", "yes", "on")

signer = URLSafeTimedSerializer(SECRET, salt="auto-service-auth")


def _valid(token: str) -> bool:
    if not token:
        return False
    try:
        data = signer.loads(token, max_age=MAX_AGE)
        return data.get("u") == USER
    except (BadSignature, SignatureExpired, Exception):
        return False


def _safe_next(nxt: str) -> str:
    """Evita open-redirect: só aceita caminhos locais."""
    if not nxt or not nxt.startswith("/") or nxt.startswith("//"):
        return "/"
    return nxt


@app.get("/auth")
def auth():
    return ("", 200) if _valid(request.cookies.get(COOKIE)) else ("", 401)


@app.get("/login")
def login_get():
    if _valid(request.cookies.get(COOKIE)):
        return redirect(_safe_next(request.args.get("next", "/")))
    return render_template("login.html", error=None,
                           next=request.args.get("next", ""))


@app.post("/login")
def login_post():
    username = request.form.get("username", "")
    password = request.form.get("password", "")
    nxt = _safe_next(request.form.get("next", "/"))
    if username == USER and password == PASSWORD:
        token = signer.dumps({"u": username})
        resp = make_response(redirect(nxt))
        resp.set_cookie(COOKIE, token, max_age=MAX_AGE, httponly=True,
                        samesite="Lax", secure=SECURE, path="/")
        return resp
    return render_template("login.html",
                           error="Usuário ou senha inválidos.", next=nxt), 401


@app.get("/logout")
def logout():
    resp = make_response(redirect("/login"))
    resp.delete_cookie(COOKIE, path="/")
    return resp


@app.get("/healthz")
def healthz():
    return {"status": "ok", "service": "auth"}


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
