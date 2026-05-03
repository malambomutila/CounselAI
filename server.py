"""FastAPI entry point.

Routes:
  GET  /api/*    → JSON + SSE API used by the Next.js frontend
  GET  /health   → liveness probe (App Runner)
  GET  /*        → static Next.js export (only present inside the Docker image)

Local dev:
  - Backend:  uv run uvicorn server:app --host 0.0.0.0 --port 8080 --reload
  - Frontend: cd frontend && npm run dev   (Next.js on :3000, hits FastAPI on :8080)

In production the Next.js bundle is built into ./static at image build time
and FastAPI serves it under ``/`` via a catch-all FileResponse. CORS allows
the Next.js dev server origin so local end-to-end works without a proxy.
"""
from __future__ import annotations

import logging
import os
import uuid
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.middleware.httpsredirect import HTTPSRedirectMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from backend.api import router as api_router
from backend.settings import (
    APP_ENV,
    CONTENT_SECURITY_POLICY,
    AUTH_ENABLED,
    FORCE_HTTPS,
    LOG_LEVEL,
    OPENAI_MODEL,
    PERSISTENCE_ENABLED,
    SECURE_HEADERS_ENABLED,
    SERVER_HOST,
    SERVER_PORT,
    STORE_BACKEND,
    TRUSTED_HOSTS,
)
from backend.usage import reset_active_requests

logging.basicConfig(
    level=LOG_LEVEL,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


app = FastAPI(title="MoootCourt", docs_url=None, redoc_url=None)


class RequestIDMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        request_id = str(uuid.uuid4())
        # Make the ID available to log-formatters and downstream handlers.
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault(
            "Permissions-Policy",
            "camera=(), geolocation=(), microphone=()",
        )
        response.headers.setdefault("Cross-Origin-Opener-Policy", "same-origin")
        response.headers.setdefault("Cross-Origin-Resource-Policy", "same-origin")
        response.headers.setdefault("Content-Security-Policy", CONTENT_SECURITY_POLICY)
        return response

# CORS — Next.js dev server (3000) hits FastAPI on a different port. In prod
# both are served from the same origin so the wildcard is harmless. Bearer
# tokens travel in the Authorization header, not in cookies, so we don't need
# allow_credentials.
_cors_origins = os.getenv(
    "CORS_ORIGINS",
    "http://localhost:3000,http://127.0.0.1:3000",
).split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in _cors_origins if o.strip()],
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)
app.add_middleware(GZipMiddleware, minimum_size=1024)

if TRUSTED_HOSTS and TRUSTED_HOSTS != ["*"]:
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=TRUSTED_HOSTS)

if FORCE_HTTPS:
    app.add_middleware(HTTPSRedirectMiddleware)

if SECURE_HEADERS_ENABLED:
    app.add_middleware(SecurityHeadersMiddleware)

app.add_middleware(RequestIDMiddleware)

app.include_router(api_router)
reset_active_requests()


@app.get("/health")
async def health():
    # Expose system detail only in non-production; load-balancer probes only
    # need the 200 status — revealing internals aids attackers in production.
    if APP_ENV == "production":
        return JSONResponse({"ok": True})
    return JSONResponse({
        "ok": True,
        "auth_enabled": AUTH_ENABLED,
        "persistence_enabled": PERSISTENCE_ENABLED,
        "store_backend": STORE_BACKEND,
        "model": OPENAI_MODEL,
    })


# ── Static Next.js bundle ─────────────────────────────────────────────────
# In dev (no ./static dir) the frontend runs on :3000 — `next dev`. In prod
# the Docker image's stage 1 produces ./static and we serve it here.

_STATIC_ROOT = Path(__file__).parent / "static"

if _STATIC_ROOT.exists():
    # Next.js's static-export hashed asset bundle.
    app.mount(
        "/_next",
        StaticFiles(directory=str(_STATIC_ROOT / "_next")),
        name="next-assets",
    )

    _STATIC_ROOT_RESOLVED = _STATIC_ROOT.resolve()

    def _safe_static_file(path: Path) -> bool:
        """Return True only if path resolves to a file inside _STATIC_ROOT."""
        try:
            return path.resolve().is_file() and path.resolve().is_relative_to(_STATIC_ROOT_RESOLVED)
        except (ValueError, OSError):
            return False

    @app.get("/{full_path:path}")
    async def serve_static(full_path: str):
        """Serve the Next.js static export. Tries:
          1. exact file match (for /favicon.ico, /robots.txt, etc.)
          2. <path>.html (Pages Router static-export convention)
          3. fall back to index.html so client-side routing keeps working
             on a hard refresh of /app etc.
        """
        candidate = _STATIC_ROOT / full_path
        if _safe_static_file(candidate):
            return FileResponse(candidate)
        html_candidate = _STATIC_ROOT / f"{full_path}.html"
        if _safe_static_file(html_candidate):
            return FileResponse(html_candidate)
        index = _STATIC_ROOT / "index.html"
        if index.is_file():
            return FileResponse(index)
        return JSONResponse({"detail": "not found"}, status_code=404)
else:
    logger.info("./static not present — frontend running separately (likely `npm run dev` on :3000)")


if __name__ == "__main__":
    import uvicorn
    logger.info("Starting MoootCourt on %s:%s (auth=%s, persistence=%s, store=%s)",
                SERVER_HOST, SERVER_PORT, AUTH_ENABLED, PERSISTENCE_ENABLED,
                STORE_BACKEND)
    uvicorn.run(app, host=SERVER_HOST, port=SERVER_PORT)
