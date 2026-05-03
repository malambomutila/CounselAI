.PHONY: install dev-backend dev-frontend dev build run prod-up prod-down prod-logs backup-sqlite clean

# ── Local dev (no Docker) ─────────────────────────────────────────────────

install:
	uv sync
	cd frontend && npm install

dev-backend:
	set -a && source .env && set +a && \
	  uv run uvicorn server:app --host 0.0.0.0 --port 8080 --reload

dev-frontend:
	cd frontend && npm run dev

# Run both together. Frontend on :3000, backend on :8080.
# In another terminal: `make dev-backend`. Then here: `make dev-frontend`.
dev: dev-frontend

# ── Docker local run ──────────────────────────────────────────────────────

build:
	export $$(grep -v '^#' .env | xargs) && \
	docker build \
	  --build-arg NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY="$$NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY" \
	  -t moootcourt:latest .

run:
	export $$(grep -v '^#' .env | xargs) && \
	docker run --rm -p 8080:8080 \
	  -e CLERK_JWKS_URL="$$CLERK_JWKS_URL" \
	  -e CLERK_FRONTEND_API_URL="$$CLERK_FRONTEND_API_URL" \
	  -e NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY="$$NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY" \
	  -e CLERK_SECRET_KEY="$$CLERK_SECRET_KEY" \
	  -e OPENAI_API_KEY="$$OPENAI_API_KEY" \
	  -e OPENAI_MODEL="$$OPENAI_MODEL" \
	  -e DDB_TABLE="$$DDB_TABLE" \
	  -e DDB_REGION="$$DDB_REGION" \
	  moootcourt:latest

prod-up:
	docker compose up -d --build

prod-down:
	docker compose down

prod-logs:
	docker compose logs -f

backup-sqlite:
	mkdir -p data/backups
	test -f data/moootcourt.sqlite && cp data/moootcourt.sqlite data/backups/moootcourt-$$(date +%Y%m%d%H%M%S).sqlite

# ── Tidy ──────────────────────────────────────────────────────────────────

clean:
	rm -rf frontend/.next frontend/out frontend/node_modules
	rm -rf .pytest_cache **/__pycache__ **/.mypy_cache
