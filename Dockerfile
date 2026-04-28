# ── Stage 1: Next.js static export ────────────────────────────────────────
FROM node:22-alpine AS frontend-builder

WORKDIR /app

COPY frontend/package.json frontend/package-lock.json* ./
RUN npm ci || npm install

COPY frontend/ .

# NEXT_PUBLIC_* values are baked into the client bundle at build time and are
# safe to bake in (publishable key is designed to be public).
ARG NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY
ENV NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=$NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY
# Empty in prod → frontend hits /api at the same origin as the bundle.
ARG NEXT_PUBLIC_API_BASE_URL=
ENV NEXT_PUBLIC_API_BASE_URL=$NEXT_PUBLIC_API_BASE_URL

RUN npm run build
# Produces ./out — the static HTML/JS export

# ── Stage 2: Python runtime ───────────────────────────────────────────────
FROM --platform=linux/amd64 python:3.12-slim

WORKDIR /app

RUN pip install --no-cache-dir uv

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project

COPY server.py ./
COPY backend ./backend

# Drop the Next.js bundle into ./static — server.py mounts /_next from
# ./static/_next and serves *.html / index.html for client-side routes.
COPY --from=frontend-builder /app/out ./static

EXPOSE 8080

CMD ["uv", "run", "uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8080"]
