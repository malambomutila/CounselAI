FROM --platform=linux/amd64 python:3.12-slim

WORKDIR /app

RUN apt-get update \
 && apt-get install -y --no-install-recommends ca-certificates curl \
 && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir uv

RUN addgroup --system counselai && adduser --system --ingroup counselai counselai

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project

COPY server.py ./
COPY backend ./backend
COPY scripts/start-prod.sh ./scripts/start-prod.sh

RUN chmod +x ./scripts/start-prod.sh \
 && mkdir -p /var/lib/counselai/data /var/log/counselai \
 && chown -R counselai:counselai /app /var/lib/counselai /var/log/counselai

ENV HOME=/tmp
ENV APP_ENV=production
ENV SERVER_HOST=0.0.0.0
ENV SERVER_PORT=8080
ENV SQLITE_PATH=/var/lib/counselai/data/counselai.sqlite
ENV DATA_ROOT=/var/lib/counselai/data
ENV FORCE_HTTPS=false
ENV PYTHONUNBUFFERED=1

USER counselai

VOLUME ["/var/lib/counselai/data"]

EXPOSE 8080

CMD ["./scripts/start-prod.sh"]
