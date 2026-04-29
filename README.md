# MoootCourt

**Live at [https://moootcourt.com](https://moootcourt.com)**

A multi-agent legal analysis tool that puts five AI legal specialists on your case simultaneously.

> Originally built as **CounselAI**, an Andela AI Engineering Bootcamp capstone project.

---

## What it does

You describe a legal case, choose the area of law, state your position, and pick a jurisdiction. MoootCourt then runs a structured analysis through five specialist agents:

1. **Plaintiff's Counsel** — argues the case from the claimant's side
2. **Defense Counsel** — builds the counter-argument
3. **Expert Witness** — provides technical or domain-specific analysis
4. **Judge** — weighs both sides and delivers an assessment
5. **Legal Strategist** — recommends the strongest path forward based on all of the above

The analysis streams in real time. After the initial phase you can trigger the Judge to pronounce final judgment, then ask follow-up questions to any individual agent to pressure-test specific arguments.

All conversations are saved and can be reloaded from the sidebar.

---

## Disclaimer

MoootCourt is a legal research and preparation tool. It is not legal advice and is not a substitute for a licensed attorney. Always consult a qualified legal practitioner before making decisions based on any content generated here.

---

## Running locally

### Requirements

- Python 3.12+
- Node.js 22+
- [uv](https://github.com/astral-sh/uv) (Python package manager)
- A Clerk account (for authentication)
- An OpenAI API key

### Setup

1. Clone the repo and copy the environment template:

   ```bash
   git clone <repo-url>
   cd counselai
   cp .env.example .env
   ```

2. Fill in the required values in `.env`:
   - `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` — from your Clerk dashboard
   - `CLERK_SECRET_KEY` — from your Clerk dashboard
   - `CLERK_JWKS_URL` — from your Clerk instance
   - `OPENAI_API_KEY` — from OpenAI

3. Install backend dependencies:

   ```bash
   uv sync
   ```

4. Start the backend:

   ```bash
   uv run uvicorn server:app --host 0.0.0.0 --port 8080 --reload
   ```

5. In a separate terminal, install and start the frontend:

   ```bash
   cd frontend
   npm install
   ```

   Create `frontend/.env.local`:

   ```
   NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=pk_test_...
   NEXT_PUBLIC_API_BASE_URL=http://localhost:8080
   ```

   Then start the dev server:

   ```bash
   npm run dev
   ```

6. Open [http://localhost:3000](http://localhost:3000) and sign in.

---

## Deploying with Docker

### Requirements

- Docker and Docker Compose
- A domain name pointed at your server
- A Clerk account and OpenAI API key

### Setup

1. Copy the environment template and fill in your values:

   ```bash
   cp .env.example .env
   ```

   Required values for a production deployment:

   | Variable | What to set |
   |---|---|
   | `COUNSELAI_SITE_ADDRESS` | Your domain (e.g. `example.com`) or `:8080` for HTTP-only |
   | `TRUSTED_HOSTS` | `your-domain.com,localhost,127.0.0.1` |
   | `CLERK_AUTHORIZED_PARTIES` | `https://your-domain.com` |
   | `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` | From Clerk dashboard |
   | `CLERK_SECRET_KEY` | From Clerk dashboard |
   | `CLERK_JWKS_URL` | From Clerk dashboard |
   | `OPENAI_API_KEY` | From OpenAI |

2. Create the persistent data directory:

   **Linux / macOS:**
   ```bash
   sudo mkdir -p /var/lib/counselai/data/backups
   sudo chown -R 1000:1000 /var/lib/counselai
   ```

   **Windows (PowerShell as Administrator):**
   ```powershell
   New-Item -ItemType Directory -Force -Path "C:\counselai\data\backups"
   ```
   Then update `SQLITE_PATH` in `.env` to `C:/counselai/data/counselai.sqlite`.

3. Build and start the stack:

   ```bash
   docker compose up -d --build
   ```

4. Verify all three services are healthy:

   ```bash
   docker compose ps
   curl https://your-domain.com/health
   ```

### Managing the stack

```bash
docker compose logs -f          # stream all logs
docker compose logs -f app      # backend only
docker compose logs -f frontend # frontend only
docker compose logs -f caddy    # reverse proxy / HTTPS
docker compose restart          # restart without rebuilding
docker compose down             # stop (data is preserved)
docker compose up -d --build    # rebuild and restart after code changes
```

SQLite data lives in the `counselai_data` Docker named volume and is not affected by restarts or rebuilds. To wipe all data: `docker compose down -v` (destructive).

---

## Environment variables reference

| Variable | Purpose | Required |
|---|---|---|
| `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` | Clerk frontend key | Yes |
| `CLERK_SECRET_KEY` | Clerk backend key | Yes |
| `CLERK_JWKS_URL` | Clerk JWKS endpoint for JWT verification | Yes |
| `CLERK_AUTHORIZED_PARTIES` | Allowed origins for Clerk session tokens | Production |
| `OPENAI_API_KEY` | OpenAI API key | Yes |
| `OPENAI_MODEL` | Model to use (default: `gpt-4.1-mini`) | No |
| `SQLITE_PATH` | Path to SQLite database file | No |
| `TRUSTED_HOSTS` | Hostnames accepted by the backend | Production |
| `COUNSELAI_SITE_ADDRESS` | Domain passed to Caddy (e.g. `example.com`) | Docker |
| `ACME_EMAIL` | Email for Let's Encrypt renewal notices | Optional |
| `LOG_LEVEL` | Logging verbosity (`INFO`, `DEBUG`, etc.) | No |

See `.env.example` for the full list of configurable values. Never commit `.env` or put real credentials in `.env.example`.

---

## Tech stack

| Layer | Technology |
|---|---|
| Backend | Python, FastAPI, Gunicorn, Uvicorn |
| Frontend | Next.js 15, TypeScript, Tailwind CSS |
| Auth | Clerk |
| LLM | OpenAI Chat Completions |
| Data | SQLite (WAL mode) / DynamoDB (optional) |
| Reverse proxy | Caddy |
| Containers | Docker Compose |
| CI | GitHub Actions |
