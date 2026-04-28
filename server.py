"""FastAPI entry point.

Routes:
  GET  /         → Clerk sign-in landing page (HTML, vanilla JS)
  GET  /health   → JSON health probe (used by App Runner)
  ANY  /app/*    → Gradio Blocks app (auth required when AUTH_ENABLED)

Run locally:  uv run uvicorn server:app --host 0.0.0.0 --port 8080
"""
from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
import gradio as gr

from backend.auth import AuthError, verify_session_token
from backend.settings import (
    AUTH_ENABLED,
    CLERK_FRONTEND_API_URL,
    NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY,
    OPENAI_MODEL,
    PERSISTENCE_ENABLED,
    SERVER_HOST,
    SERVER_PORT,
)
from ui.app import build_demo

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


app = FastAPI(title="CounselAI", docs_url=None, redoc_url=None)

# ── Routes ─────────────────────────────────────────────────────────────────

LANDING_PATH = Path(__file__).parent / "ui" / "landing.html"
_LANDING_HTML = LANDING_PATH.read_text(encoding="utf-8")


@app.get("/", response_class=HTMLResponse)
async def landing(request: Request):
    """Serve the Clerk sign-in page. If user already has a valid session, jump
    straight into the app."""
    if AUTH_ENABLED:
        token = request.cookies.get("__session") or request.cookies.get("session")
        if token:
            try:
                verify_session_token(token)
                return RedirectResponse(url="/app", status_code=307)
            except AuthError:
                pass
    else:
        # No auth → no landing page needed; bounce to the app.
        return RedirectResponse(url="/app", status_code=307)

    html = (
        _LANDING_HTML
        .replace("__CLERK_PUBLISHABLE_KEY__", NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY)
        .replace("__CLERK_FRONTEND_API_URL__", CLERK_FRONTEND_API_URL.rstrip("/"))
    )
    return HTMLResponse(content=html)


@app.get("/health")
async def health():
    return JSONResponse({
        "ok": True,
        "auth_enabled": AUTH_ENABLED,
        "persistence_enabled": PERSISTENCE_ENABLED,
        "model": OPENAI_MODEL,
    })


# ── Auth middleware on /app/* ─────────────────────────────────────────────

@app.middleware("http")
async def auth_gate(request: Request, call_next):
    """Block unauthenticated access to /app/* when AUTH_ENABLED. Other paths
    pass through (including / for the sign-in page itself)."""
    path = request.url.path
    if AUTH_ENABLED and path.startswith("/app"):
        token = request.cookies.get("__session") or request.cookies.get("session")
        try:
            verify_session_token(token)
        except AuthError as e:
            # For HTML requests, redirect to the landing page; for XHR/WebSocket,
            # return 401 so the JS can react.
            if "text/html" in (request.headers.get("accept") or "") and path == "/app":
                return RedirectResponse(url="/", status_code=307)
            return JSONResponse({"error": "unauthenticated", "detail": str(e)}, status_code=401)
    return await call_next(request)


# ── Mount Gradio at /app ──────────────────────────────────────────────────

demo = build_demo()
app = gr.mount_gradio_app(app, demo, path="/app")


if __name__ == "__main__":
    import uvicorn
    logger.info("Starting CounselAI on %s:%s (auth=%s, persistence=%s)",
                SERVER_HOST, SERVER_PORT, AUTH_ENABLED, PERSISTENCE_ENABLED)
    uvicorn.run(app, host=SERVER_HOST, port=SERVER_PORT)
