# Single-stage image for App Runner. Pinned amd64 so the image runs identically
# whether built on a Mac (M-series) or this Linux host.
FROM --platform=linux/amd64 python:3.12-slim

WORKDIR /app

# uv is the canonical install path for this project (see CLAUDE.md conventions).
RUN pip install --no-cache-dir uv

# Install dependencies first so the layer is cached when only app code changes.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project

# Application code. Globs are flat-only so the .dockerignore can keep the image
# tight (no .venv, no terraform/, no notebook checkpoints).
COPY server.py ./
COPY backend ./backend
COPY ui ./ui

EXPOSE 8080

CMD ["uv", "run", "uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8080"]
