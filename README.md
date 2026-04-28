# MoootCourt

A multi-agent legal analysis tool that puts five AI legal specialists on your case simultaneously.

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
   # Create frontend/.env.local with your Clerk publishable key
   echo "NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=pk_test_..." > .env.local
   echo "NEXT_PUBLIC_API_BASE_URL=http://localhost:8080" >> .env.local
   npm run dev
   ```

6. Open [http://localhost:3000](http://localhost:3000) and sign in.

---

## Deploying to EC2

### Stack

- **Backend:** FastAPI served by Gunicorn + Uvicorn workers
- **Frontend:** Next.js standalone build served by Node
- **Reverse proxy:** Caddy (automatic HTTPS via Let's Encrypt)
- **Data:** SQLite on a persistent Docker named volume

### Quick start

1. Provision an EC2 instance (Ubuntu 22.04+, t3.small or larger).

2. Open inbound ports: `22` (SSH), `80`, `443`, and optionally `8080`.

3. Install Docker on the instance:

   ```bash
   sudo apt-get update && sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
   sudo usermod -aG docker $USER
   ```

4. Copy the project to the instance (excluding `.env` and build artifacts):

   ```bash
   rsync -av --exclude='.git' --exclude='node_modules' --exclude='.next' \
     --exclude='__pycache__' --exclude='.env' \
     ./ ubuntu@<EC2_IP>:~/counselai/
   ```

5. On the instance, create `.env` from the template and set the production values:

   ```bash
   cp .env.example .env
   # Edit .env — at minimum set:
   #   COUNSELAI_SITE_ADDRESS, TRUSTED_HOSTS, CLERK_AUTHORIZED_PARTIES,
   #   FORCE_HTTPS, ACME_EMAIL, and all API keys
   ```

6. Create the persistent data directory:

   ```bash
   sudo mkdir -p /var/lib/counselai/data/backups
   sudo chown -R 1000:1000 /var/lib/counselai
   ```

7. Build and start:

   ```bash
   docker compose -f docker-compose.ec2.yml up -d --build
   ```

8. Verify:

   ```bash
   curl http://127.0.0.1:8080/health
   docker compose -f docker-compose.ec2.yml ps
   ```

See `CLAUDE.md` (internal, not committed to git) for the full step-by-step deployment guide including ongoing operations commands.

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
| `COUNSELAI_SITE_ADDRESS` | Domain passed to Caddy (e.g. `your-domain.com`) | EC2 |
| `FORCE_HTTPS` | Redirect HTTP to HTTPS | EC2 with domain |
| `ACME_EMAIL` | Email for Let's Encrypt registration | EC2 with domain |
| `LOG_LEVEL` | Logging verbosity (`INFO`, `DEBUG`, etc.) | No |

Never put real credentials in `.env.example` or any committed file. See `.env.example` for the full list of configurable values.

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
| Infrastructure | Terraform (AWS ECR + IAM + optional EC2) |
