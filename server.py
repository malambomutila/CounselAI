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
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from backend.api import router as api_router
from backend.settings import (
    AUTH_ENABLED,
    OPENAI_MODEL,
    PERSISTENCE_ENABLED,
    SERVER_HOST,
    SERVER_PORT,
    STORE_BACKEND,
)

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


app = FastAPI(title="CounselAI", docs_url=None, redoc_url=None)

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

app.include_router(api_router)


@app.get("/health")
async def health():
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

    @app.get("/{full_path:path}")
    async def serve_static(full_path: str):
        """Serve the Next.js static export. Tries:
          1. exact file match (for /favicon.ico, /robots.txt, etc.)
          2. <path>.html (Pages Router static-export convention)
          3. fall back to index.html so client-side routing keeps working
             on a hard refresh of /app etc.
        """
        candidate = _STATIC_ROOT / full_path
        if candidate.is_file():
            return FileResponse(candidate)
        html_candidate = _STATIC_ROOT / f"{full_path}.html"
        if html_candidate.is_file():
            return FileResponse(html_candidate)
        index = _STATIC_ROOT / "index.html"
        if index.is_file():
            return FileResponse(index)
        return JSONResponse({"detail": "not found"}, status_code=404)
else:
    logger.info("./static not present — frontend running separately (likely `npm run dev` on :3000)")


if __name__ == "__main__":
    import uvicorn
    logger.info("Starting CounselAI on %s:%s (auth=%s, persistence=%s, store=%s)",
                SERVER_HOST, SERVER_PORT, AUTH_ENABLED, PERSISTENCE_ENABLED,
                STORE_BACKEND)
    uvicorn.run(app, host=SERVER_HOST, port=SERVER_PORT)
