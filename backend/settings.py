"""Centralised env loading + AgentConfig factory."""
from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

# Explicit env vars (e.g. App Runner runtime env, CLI overrides) win over .env.
# The .env file fills in anything not already set.
load_dotenv(override=False)


def _required(name: str) -> str:
    val = os.getenv(name, "").strip()
    if not val:
        raise RuntimeError(f"Missing required env var: {name}")
    return val


def _optional(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


@dataclass(frozen=True)
class AgentConfig:
    """Per-agent LLM configuration. Single OpenAI provider in v1."""
    name: str
    model: str
    temperature: float


# Resolved at import time so failures surface fast (e.g. in container start)
OPENAI_API_KEY = _required("OPENAI_API_KEY")
OPENAI_MODEL = _optional("OPENAI_MODEL", "gpt-4.1")

CLERK_JWKS_URL = _optional("CLERK_JWKS_URL")
CLERK_FRONTEND_API_URL = _optional("CLERK_FRONTEND_API_URL")
NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY = _optional("NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY")
# When CLERK_JWKS_URL is empty, auth is bypassed (local dev / single-user demo).
AUTH_ENABLED = bool(CLERK_JWKS_URL)

# Origins from which Clerk-signed JWTs are allowed. Clerk issues a session
# JWT with an ``azp`` claim equal to the origin that requested it; we refuse
# tokens whose ``azp`` isn't on this list (defence-in-depth — even a valid
# Clerk JWT minted for someone else's frontend should not authenticate ours).
# Empty list means "skip the check" — fine for local dev where Clerk dev
# instances may use a permissive azp.
CLERK_AUTHORIZED_PARTIES = [
    p.strip() for p in _optional("CLERK_AUTHORIZED_PARTIES").split(",") if p.strip()
]

# Persistence has three possible backends, picked in this order:
#   1. SQLite — set SQLITE_PATH to a writable file path (default for local).
#   2. DynamoDB — set DDB_TABLE (and don't set SQLITE_PATH).
#   3. In-memory — both empty, conversations vanish on restart.
SQLITE_PATH = _optional("SQLITE_PATH", "./data/counselai.sqlite")
DDB_TABLE = _optional("DDB_TABLE", "counselai-dev")
DDB_REGION = _optional("DDB_REGION") or _optional("DEFAULT_AWS_REGION", "eu-west-2")

if SQLITE_PATH:
    STORE_BACKEND = "sqlite"
elif DDB_TABLE:
    STORE_BACKEND = "ddb"
else:
    STORE_BACKEND = "memory"

PERSISTENCE_ENABLED = STORE_BACKEND != "memory"

SERVER_HOST = _optional("GRADIO_SERVER_NAME", "0.0.0.0")
SERVER_PORT = int(_optional("GRADIO_SERVER_PORT", "8080"))


def agent_configs() -> dict[str, AgentConfig]:
    """The five agent definitions. Differentiated by system prompt + temperature."""
    m = OPENAI_MODEL
    return {
        "plaintiff":  AgentConfig(name="Plaintiff's Counsel", model=m, temperature=0.7),
        "defense":    AgentConfig(name="Defense Counsel",     model=m, temperature=0.7),
        "expert":     AgentConfig(name="Expert Witness",      model=m, temperature=0.2),
        "judge":      AgentConfig(name="Judge",               model=m, temperature=0.1),
        "strategist": AgentConfig(name="Legal Strategist",    model=m, temperature=0.4),
    }
