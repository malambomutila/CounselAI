FROM --platform=linux/amd64 python:3.12-slim

WORKDIR /app

RUN apt-get update \
 && apt-get install -y --no-install-recommends ca-certificates curl \
 && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir uv

RUN addgroup --system moootcourt && adduser --system --ingroup moootcourt moootcourt

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project

COPY server.py ./
COPY backend ./backend
COPY scripts/start-prod.sh ./scripts/start-prod.sh

RUN chmod +x ./scripts/start-prod.sh \
 && mkdir -p /var/lib/moootcourt/data /var/log/moootcourt \
 && chown -R moootcourt:moootcourt /app /var/lib/moootcourt /var/log/moootcourt

ENV HOME=/tmp
ENV APP_ENV=production
ENV SERVER_HOST=0.0.0.0
ENV SERVER_PORT=8080
ENV SQLITE_PATH=/var/lib/moootcourt/data/moootcourt.sqlite
ENV DATA_ROOT=/var/lib/moootcourt/data
ENV FORCE_HTTPS=false
ENV PYTHONUNBUFFERED=1

USER moootcourt

VOLUME ["/var/lib/moootcourt/data"]

EXPOSE 8080

CMD ["./scripts/start-prod.sh"]
