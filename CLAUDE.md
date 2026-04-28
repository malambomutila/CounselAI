# CounselAI — Project Guide

This file is the source of truth for the CounselAI capstone. Read this first
before doing any work in this directory.

---

## What CounselAI is

A multi-agent legal-analysis web app. The user submits a case description, a
legal area, and their position; five specialised LLM agents run as a streamed
pipeline and produce a complete case-prep package. Built as a self-contained
showcase, hosted live on AWS, then torn down after the team demo.

### The five agents (and their roles)

All five agents now run on **OpenAI gpt-4.1** (the user's only paid provider).
The notebook had them split across HuggingFace + OpenRouter; we collapse to
one provider both for cost (user's credits live there) and simplicity (drops
the o3 `supports_json`/`supports_temperature` quirks entirely). Differentiation
comes from system prompts and per-agent temperature.

| Agent | Model | Temp | Job |
|---|---|---|---|
| Plaintiff's Counsel | `gpt-4.1` | 0.7 | Builds the strongest pro-user argument |
| Defense Counsel | `gpt-4.1` | 0.7 | Mounts the toughest counter-argument |
| Expert Witness | `gpt-4.1` | 0.2 | Objective doctrine: statutes, precedents, burden of proof (JSON) |
| Judge | `gpt-4.1` | 0.1 | Scores both sides on 5 criteria, surfaces vulnerabilities (JSON) |
| Legal Strategist | `gpt-4.1` | 0.4 | Synthesises everything into an actionable case memo |

`AgentConfig` shrinks to `(name, model, temperature)` — the
`supports_json`/`supports_temperature` flags can go (gpt-4.1 supports both).
`LLMAdapter` keeps its shape so agents can later swap models per env var if
budget changes.

The pipeline is a **Python generator** that yields after each step, so the
Gradio UI can stream "Plaintiff is arguing… Defense is preparing… Expert is
analysing…" updates as panels fill in.

### Inputs / outputs (initial run)

- **In:** case_description (free text), legal_area (one of 11 enum values),
  user_position (free text)
- **Out:** plaintiff arg, defense arg, expert analysis (formatted from JSON),
  judge assessment (formatted from JSON), 5×4 score table, strategy memo,
  one-line summary

### New scope beyond the notebook

The notebook is a single-shot pipeline with no persistence. The production
app adds three things:

1. **Auth (Clerk)** — every request authenticated; users see only their own
   data. Dev keys for instance `winning-weevil-72.clerk.accounts.dev` are
   already in `.env`.
2. **Conversation history (DynamoDB)** — each pipeline run is saved as a
   "turn" inside a "conversation". Users can browse past conversations from
   a sidebar (ChatGPT-style), reload them, continue them.
3. **Per-agent follow-up + cascade re-run** — under each agent's panel,
   a "Ask follow-up" button lets the user supply more context or ask the
   agent to try again ("find an alternative argument considering X").
   After the targeted agent re-runs, the **other four agents cascade-rerun
   with the updated context** so the whole case package stays coherent.
   Each follow-up is a new turn under the same conversation.

The `pyproject.toml` is currently a kitchen-sink with chromadb, torch,
transformers, langchain, etc. — none of that is actually used by the live
code. We will trim it. Real runtime deps: `gradio`, `fastapi`,
`uvicorn[standard]`, `openai`, `python-dotenv`, `httpx`, `boto3` (for
DynamoDB), `pyjwt[crypto]` (for Clerk JWT verification), `cryptography`
(transitive but worth pinning).

---

## Current state (as of this writing)

- `counselai.ipynb` — single notebook holding the entire app: `AgentConfig`
  dataclass, `LLMAdapter`, five agent classes, the streaming
  `run_case_analysis` generator, formatting helpers, Gradio Blocks UI with a
  custom dark serif theme (`Playfair Display` / `Source Serif 4`), and
  `demo.queue(...).launch()` at the end.
- `pyproject.toml` / `requirements.txt` / `environment.yml` — three different
  dependency manifests, all bloated with notebook experimentation deps. We
  will keep only `pyproject.toml` and trim it.
- `.env` — has the AWS creds (same `IAM_@i_engineer` user used by the alex /
  digital-twin projects), Clerk dev keys for a new instance
  (`winning-weevil-72.clerk.accounts.dev`), an OpenAI key, OpenRouter,
  HuggingFace, and several other API keys carried over from sibling
  projects. Has empty placeholders for `VECTOR_BUCKET`,
  `COUNSEL_API_ENDPOINT`, etc. — leftover from copy-pasting the alex `.env`;
  CounselAI does not need any of those (no DB, no vector store, no SQS, no
  API Gateway). Will be cleaned up.
- `uv.lock` — exists; `uv sync` is the canonical install path.

---

## Target architecture

A **single FastAPI process** that:
- serves a tiny `/` landing page that hosts the Clerk sign-in widget,
- mounts the Gradio Blocks app at `/app` (auth required),
- exposes `/health` for the App Runner health check.

Containerised once, deployed to AWS App Runner. State lives in a single
DynamoDB table. No frontend split, no Lambda, no API Gateway, no RDS.

```
User browser
   │
   ▼  HTTPS  →  /            ─ landing page, Clerk SignIn widget (vanilla JS)
   ▼  HTTPS  →  /app/*       ─ Gradio (Blocks)  ──┐
   ▼  HTTPS  →  /health      ─ JSON ok           │
                                                   │
AWS App Runner ──────────────────────────────────┤  FastAPI + uvicorn
                                                   │
                                ┌──────────────────┘
                                ▼
                  ┌─────────────┴──────────────┐
                  ▼                            ▼
              OpenAI API                  DynamoDB
              (5 agents,                  (conversations,
               gpt-4.1)                    turns, per-user)
```

### Auth: Clerk + Gradio integration

Gradio doesn't speak Clerk natively, but mounting it under FastAPI gives us
a clean seam:

1. **Landing page (`/`)**: served by FastAPI as a static HTML page that loads
   Clerk's vanilla JS SDK (`https://winning-weevil-72.clerk.accounts.dev/clerk.js`)
   and renders `<SignIn />`. After successful sign-in Clerk sets a
   `__session` cookie scoped to our origin (works because we use Clerk dev
   instance which accepts any origin).
2. **Middleware**: a FastAPI middleware on `/app/*` reads the `__session`
   cookie, validates it as a JWT against the Clerk JWKS (cached), and stores
   `user_id = claims["sub"]` on `request.state`. If invalid → redirect to `/`.
3. **In Gradio handlers**: use the `request: gr.Request` parameter to pull
   the resolved user_id from `request.session_hash` (Gradio's per-session
   handle) — but for security, we re-verify the cookie inside each handler
   too, in case middleware was bypassed. A small decorator handles this.

### Storage: DynamoDB single-table

Why DynamoDB and not Aurora/Postgres:
- App Runner is stateless — no persistent volume.
- Aurora Serverless v2 has a $43/month minimum even idle. Way too much for
  a throwaway showcase.
- DynamoDB on-demand: pay-per-request, ~$0 idle, pennies under demo load,
  no cluster to provision/destroy.
- User already has `AmazonDynamoDBFullAccess` via
  `BroadAIEngineerAccess2_DigitalTwin` group — no new IAM needed.

Schema — single table `counselai-{env}`:

| PK | SK | What it is | Attributes |
|---|---|---|---|
| `USER#{user_id}` | `CONV#{conversation_id}` | Conversation header | `title`, `legal_area`, `case_description`, `user_position`, `created_at`, `updated_at`, `turn_count` |
| `USER#{user_id}` | `CONV#{conversation_id}#TURN#{turn_n}` | One pipeline run | `kind` (`initial` \| `followup`), `target_agent` (for follow-ups), `follow_up_text` (for follow-ups), `agents` (map of `plaintiff/defense/expert/judge/strategist` → output blob), `created_at` |

Listing user's conversations: `Query` PK=`USER#{user_id}`, SK begins_with
`CONV#`, filter `:`-not-in-SK (header rows only). Loading a conversation:
`Query` PK + SK begins_with `CONV#{conv_id}`. Strong consistency, single-digit
ms latency.

### Pipeline modes

- **`run_initial(case, area, position)`** — same as the notebook's
  `run_case_analysis`. All 5 agents run from scratch. Saves a new
  conversation header + turn 1.
- **`run_followup(conv_id, target, note)`** — load conversation history,
  re-run the targeted agent with full context + the note, **then** cascade-
  re-run the other four agents with the updated targeted-agent output so
  the package stays coherent. Saves a new turn under the same conversation.
- Both modes are async generators that yield panel updates as each agent
  finishes (same UX as the notebook).

### Why App Runner, not Lambda

| Factor | App Runner | Lambda |
|---|---|---|
| Long-running streaming responses (90s–3min per pipeline) | Native | Requires Function URL with response streaming + careful Mangum/ASGI plumbing |
| Gradio's WebSocket/SSE event loop | Works out of the box | Awkward — needs API Gateway WebSocket or function-url streaming |
| Cold start UX | ~30s on first hit, then warm | ~5s per invocation if cold |
| Cost when idle | Scales to zero in ~5min, then 0 | Truly 0 |
| Cost under demo load | A few cents/hour while warm | Sub-cent per request |
| Operational simplicity | One container, one terraform | Lambda + APIGW + roles + Mangum |
| Time to first deploy | ~20 min | ~45 min |

For a 1–2 day showcase that gets destroyed after, App Runner is the right
call. The tradeoff is ~$5–10/month if left running (1 vCPU, 2 GB,
auto-pausing). Destroyed immediately after the showcase that's a few
dollars total.

### Why not separate Next.js frontend (like alex / digital-twin)

The Gradio UI is already polished — custom CSS, themed panels, streaming
updates, score tables. Re-implementing it in Next.js would be a week of
work for marginal benefit on a throwaway showcase. We keep Gradio.

---

## Target file layout

```
counselai/
├── CLAUDE.md                       ← this file
├── pyproject.toml                  ← trimmed to runtime deps only
├── uv.lock
├── .env.example                    ← non-secret template (committed)
├── .env                            ← real values (gitignored, already present)
├── .gitignore                      ← already present
├── .python-version                 ← 3.11
├── counselai.ipynb                 ← keep as reference; not loaded by app
├── README.md                       ← (optional) public-facing intro
│
├── backend/
│   ├── __init__.py
│   ├── settings.py                 ← env loading, AgentConfig factory
│   ├── adapter.py                  ← LLMAdapter (the universal client)
│   ├── prompts.py                  ← all SYSTEM strings + RUBRIC
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── plaintiff.py
│   │   ├── defense.py
│   │   ├── expert.py
│   │   ├── judge.py
│   │   └── strategist.py
│   ├── pipeline.py                 ← run_initial + run_followup generators
│   ├── formatting.py               ← _format_expert / _format_judge / score_rows
│   ├── store.py                    ← DynamoDB client + conversation/turn CRUD
│   └── auth.py                     ← Clerk JWT verification (JWKS cache)
│
├── ui/
│   ├── __init__.py
│   ├── theme.py                    ← gr.themes.Default + CUSTOM_CSS
│   ├── landing.html                ← Clerk sign-in page (FastAPI serves)
│   └── app.py                      ← gr.Blocks(...) factory: history sidebar,
│                                     5 agent panels with follow-up controls,
│                                     score table, strategy memo
│
├── server.py                       ← FastAPI: /, /health, /app (Gradio),
│                                     Clerk middleware
│
├── Dockerfile                      ← single-stage, python:3.12-slim, uv
├── .dockerignore
│
├── terraform/
│   ├── main.tf                     ← ECR repo, App Runner service, IAM roles
│   ├── variables.tf
│   ├── outputs.tf
│   ├── terraform.tfvars            ← non-secrets, committed-safe
│   └── terraform.tfvars.example
│
└── scripts/
    ├── deploy.sh                   ← build → push → terraform apply
    └── destroy.sh                  ← terraform destroy + drain ECR
```

### Module responsibilities (so refactor is unambiguous)

- `backend/settings.py` — `load_dotenv(override=True)`, validate required env
  vars at import (fail loud), expose typed accessor functions. The five
  `AgentConfig` instances are built here from env vars.
- `backend/adapter.py` — the `LLMAdapter` class **unchanged in spirit**, just
  in its own file. `extract_text` lives here too.
- `backend/prompts.py` — all `SYSTEM = "..."`, `RUBRIC = [...]`, and the long
  user-prompt templates. One source of truth, easy to tweak.
- `backend/agents/*.py` — one class per file, each importing prompts from
  `prompts.py`. Public method is the one named in the notebook (`argue`,
  `analyse`, `evaluate`, `advise`).
- `backend/pipeline.py` — `run_case_analysis(...) -> Generator[...]`. Same
  yield order as the notebook. UI imports this and binds it to the Gradio
  button.
- `backend/formatting.py` — markdown helpers. Pure functions, easy to test.
- `ui/theme.py` — the `THEME` and `CUSTOM_CSS` constants.
- `ui/app.py` — `def build_demo() -> gr.Blocks: ...` returning the wired-up
  Blocks object. No `.launch()` here.
- `server.py` — `app = FastAPI(); app.get("/health"); app =
  gr.mount_gradio_app(app, build_demo(), path="/")`. `if __name__ ==
  "__main__": uvicorn.run(...)` for local dev.

---

## .env strategy

The current `.env` carries baggage from sibling projects. After refactor it
should look like this (placeholders shown — real values stay in `.env`):

```bash
# AWS
AWS_ACCOUNT_ID=637423201002
DEFAULT_AWS_REGION=eu-west-2

# Auth (Clerk dev instance)
NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=pk_test_...
CLERK_SECRET_KEY=sk_test_...
CLERK_JWKS_URL=https://winning-weevil-72.clerk.accounts.dev/.well-known/jwks.json
CLERK_FRONTEND_API_URL=https://winning-weevil-72.clerk.accounts.dev

# LLM (single provider for v1)
OPENAI_API_KEY=sk-proj-...
OPENAI_MODEL=gpt-4.1

# Storage
DDB_TABLE=counselai-dev
DDB_REGION=eu-west-2

# App
GRADIO_SERVER_NAME=0.0.0.0
GRADIO_SERVER_PORT=8080
LOG_LEVEL=INFO

# Filled after `terraform apply`
APP_RUNNER_URL=
ECR_REPOSITORY_URL=
```

Things to drop from the current `.env`: `VECTOR_BUCKET`,
`COUNSEL_API_ENDPOINT`, `COUNSEL_API_KEY`, `AURORA_*`, `SQS_QUEUE_URL`,
`FRONTEND_URL`, `POLYGON_API_KEY`, `OPENROUTER_API_KEY`,
`HUGGING_FACE_TOKEN`, `OLLAMA_API_KEY`, `SERP_API_KEY`, `SERPER_API_KEY`,
`BRAVE_API_KEY`. None of those are used after the OpenAI-only swap.

---

## AWS prerequisites — already satisfied

The `IAM_@i_engineer` user is in three groups (set up during the
alex/digital-twin work):

| Group | Relevant policies for CounselAI |
|---|---|
| `BroadAIEngineerAccess1` | `AmazonEC2ContainerRegistryFullAccess`, `IAMFullAccess`, `AWSAppRunnerFullAccess`, `AmazonEC2FullAccess` |
| `BroadAIEngineerAccess2_DigitalTwin` | `CloudWatchFullAccess`, `AmazonS3FullAccess`, `CloudFrontFullAccess`, **`AmazonDynamoDBFullAccess`** ← used for conversation table |
| `BroadAIEngineerAccess3_Alex` | `SecretsManagerReadWrite` if we later move OpenAI key out of plain env vars |

**No new IAM group is required for CounselAI.** ECR + App Runner +
DynamoDB + CloudWatch logs are all covered by existing groups.

---

## Cost forecast

- App Runner: 1 vCPU + 2 GB, pause-after-idle. Active: ~$0.08/hour.
  Idle (paused): $0. Realistic showcase day: $1–3.
- ECR: a couple of cents.
- CloudWatch logs: pennies.
- DynamoDB on-demand: pennies per million requests; ~$0 idle.
- OpenAI gpt-4.1: usage-based per request, billed against the user's OpenAI
  account (not AWS). A single full pipeline run (5 agents) ≈ $0.05–0.20
  depending on output length; a follow-up + cascade re-run is similar.

**Projected total AWS spend for the showcase: under $5 if torn down within
1–2 days.**

---

## Step-by-step plan

### Phase 1 — local refactor
1. `uv sync` (re-create venv if needed). Confirm Python 3.11 + minimal deps.
2. Trim `pyproject.toml` to only what the live code uses:
   `gradio`, `fastapi`, `uvicorn[standard]`, `openai`, `python-dotenv`,
   `httpx`. Drop chromadb, torch, transformers, langchain*, pandas, numpy,
   matplotlib, plotly, etc. (None of them are imported by the running
   pipeline.) Keep `ipykernel` only if we want the notebook to still open.
3. Create the file layout above by extracting code from the notebook in
   small, mechanical commits.
4. Verify locally: `uv run python server.py` → open `http://localhost:8080`,
   submit a known case, confirm all five panels populate.
5. Add a `tests/` dir with a smoke test that mocks the OpenAI client and
   asserts the pipeline yields 5 stages in the right order. (Cheap
   guardrail; runs in <1s without hitting any provider.)

### Phase 2 — containerise
1. Write `Dockerfile`: `python:3.12-slim` → install `uv` →
   `uv sync --frozen --no-install-project` → copy app → `EXPOSE 8080` →
   `CMD ["uv", "run", "uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8080"]`.
2. `--platform linux/amd64` (M1/Mac safety, not strictly needed on this
   Linux host but keeps the image portable).
3. Add `.dockerignore` (`.venv`, `__pycache__`, `*.ipynb_checkpoints`,
   `.env`, `terraform/`, `.git`).
4. Local test: `docker build -t counselai .` →
   `docker run --rm -p 8080:8080 --env-file .env counselai` → smoke test in
   browser.

### Phase 3 — deploy to AWS App Runner
1. Write `terraform/main.tf` with three resources:
   - `aws_ecr_repository "counselai"`
   - `aws_iam_role "app_runner_access"` (assume role for ECR pull)
   - `aws_apprunner_service "counselai"` with `image_repository`,
     `runtime_environment_variables` (the LLM API keys, sourced from
     `TF_VAR_*` like the digital-twin pattern), CPU/memory (1 vCPU /
     2 GB), `auto_deployments_enabled = false`, and a health check on
     `/health`.
2. `scripts/deploy.sh`:
   - Auto-load `.env` into `TF_VAR_*` (the same regex parser used in
     `digital-twin-aws/scripts/deploy.sh` — handles values with spaces).
   - `terraform init && terraform apply -target=ECR + IAM` (so ECR exists).
   - `aws ecr get-login-password | docker login` → `docker build` →
     `docker push`.
   - `terraform apply` (creates the App Runner service).
   - Echo the service URL.
3. `scripts/destroy.sh`: `aws ecr batch-delete-image …` → `terraform
   destroy`.

### Phase 4 — verify and showcase
1. Hit the App Runner URL from a fresh browser, run a real case end-to-end.
2. Tail CloudWatch logs during the demo:
   `aws logs tail /aws/apprunner/counselai/.../application --follow`
3. Capture the URL for the showcase deck.

### Phase 5 — cleanup
After the showcase: `./scripts/destroy.sh` and confirm in AWS Console that:
- App Runner service deleted
- ECR repo empty/deleted
- No CloudWatch log groups still billing (delete with
  `aws logs delete-log-group` if any remain)

---

## Conventions to keep (carry-over from alex / digital-twin work)

- **Always use `uv`**: `uv add`, `uv run`, `uv sync`. Never `pip install` and
  never bare `python script.py`.
- **Region**: `eu-west-2` everywhere — env, terraform, and any explicit
  boto3 calls.
- **Secrets**: never write live keys into committed files (`.env.example`
  uses placeholders; `.env` is `.gitignore`d). Lambda/App Runner env vars
  set via `TF_VAR_*` from `.env` at deploy time, not from `terraform.tfvars`.
- **Terraform state**: local state file in `terraform/`, gitignored.
- **IAM groups**: never repurpose space in shared groups. New project →
  new group → add the user. (For this project, no new group needed.)

---

## Other Essentials

- Vector store / embedding-based recall of past conversations. Conversations
  live in DynamoDB and are listed by recency. If a user wants "find the
  contract case I worked on last week" we'd add OpenSearch Serverless or
  pgvector | This is a must
- Document parsing (PDF / docx) of case files. Free-text input only. | can be added later
- Search-the-web tool for the Expert Witness agent (Brave/Serper). | This should be added. The API keys are in .env
- Streaming token-by-token from individual agents. The pipeline streams
  stage-by-stage (one full agent output per yield), which is what the
  notebook does and what the follow-up flow extends.
- Observability beyond CloudWatch defaults. No LangFuse/Helicone for v1.
- Multi-region. Single `eu-west-2` deployment. | Single deployment is fine

---

## Decisions confirmed (this session)

1. ✅ **Trim deps aggressively** — done in Phase 1.
2. ✅ **Clerk auth wired up** — using existing dev keys in `.env`, instance
   `winning-weevil-72.clerk.accounts.dev`.
3. ✅ **DynamoDB for chat history** — single table, on-demand billing.
4. ✅ **All agents on OpenAI gpt-4.1** — drops multi-provider quirks. No
   fallback needed (single provider).
5. ✅ **Keep Gradio** — extended with sidebar (history) and per-agent
   follow-up controls.
6. ✅ **Per-agent follow-up with cascade re-run** — targeted agent re-runs
   first, then the other four with the updated context.


## NOTE: 
- DO NOT COMMIT TO GITHUB LET THE HUMAN USER DO SO.