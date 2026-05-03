"""Centralised env loading + AgentConfig factory."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

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


def _optional_int(name: str, default: int) -> int:
    raw = _optional(name, str(default))
    try:
        return int(raw)
    except ValueError as exc:
        raise RuntimeError(f"Invalid integer env var {name}={raw!r}") from exc


def _optional_bool(name: str, default: bool = False) -> bool:
    raw = _optional(name, "true" if default else "false").lower()
    return raw in {"1", "true", "yes", "on"}


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
SQLITE_PATH = _optional("SQLITE_PATH", "./data/moootcourt.sqlite")
DDB_TABLE = _optional("DDB_TABLE", "moootcourt-dev")
DDB_REGION = _optional("DDB_REGION") or _optional("DEFAULT_AWS_REGION", "eu-west-2")

if SQLITE_PATH:
    sqlite_parent = Path(SQLITE_PATH).expanduser().resolve().parent
    sqlite_parent.mkdir(parents=True, exist_ok=True)

if SQLITE_PATH:
    STORE_BACKEND = "sqlite"
elif DDB_TABLE:
    STORE_BACKEND = "ddb"
else:
    STORE_BACKEND = "memory"

PERSISTENCE_ENABLED = STORE_BACKEND != "memory"

SERVER_HOST = _optional("SERVER_HOST", _optional("GRADIO_SERVER_NAME", "0.0.0.0"))
SERVER_PORT = _optional_int("SERVER_PORT", _optional_int("GRADIO_SERVER_PORT", 8080))

APP_ENV = _optional("APP_ENV", "development")
DEBUG = _optional_bool("DEBUG", False)
LOG_LEVEL = _optional("LOG_LEVEL", "INFO")

TRUSTED_HOSTS = [
    h.strip() for h in _optional("TRUSTED_HOSTS", "*").split(",") if h.strip()
]
FORCE_HTTPS = _optional_bool("FORCE_HTTPS", False)
SECURE_HEADERS_ENABLED = _optional_bool("SECURE_HEADERS_ENABLED", True)
FORWARDED_ALLOW_IPS = _optional("FORWARDED_ALLOW_IPS", "127.0.0.1")

CASE_DESCRIPTION_MAX_CHARS = _optional_int("CASE_DESCRIPTION_MAX_CHARS", 12000)
USER_POSITION_MAX_CHARS = _optional_int("USER_POSITION_MAX_CHARS", 500)
FOLLOW_UP_MAX_CHARS = _optional_int("FOLLOW_UP_MAX_CHARS", 2000)

RATE_LIMIT_ENABLED = _optional_bool("RATE_LIMIT_ENABLED", True)
RATE_LIMIT_MAX_REQUESTS_PER_HOUR = _optional_int("RATE_LIMIT_MAX_REQUESTS_PER_HOUR", 12)
RATE_LIMIT_MAX_REQUESTS_PER_DAY = _optional_int("RATE_LIMIT_MAX_REQUESTS_PER_DAY", 40)
RATE_LIMIT_MAX_CONCURRENT_REQUESTS = _optional_int("RATE_LIMIT_MAX_CONCURRENT_REQUESTS", 1)
RATE_LIMIT_COOLDOWN_MINUTES = _optional_int("RATE_LIMIT_COOLDOWN_MINUTES", 30)

SQLITE_BACKUP_DIR = _optional("SQLITE_BACKUP_DIR", "")
DATA_ROOT = _optional("DATA_ROOT", str(Path(SQLITE_PATH).expanduser().resolve().parent if SQLITE_PATH else "./data"))

CONTENT_SECURITY_POLICY = _optional(
    "CONTENT_SECURITY_POLICY",
    (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' https://*.clerk.accounts.dev; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "font-src 'self' https://fonts.gstatic.com data:; "
        "img-src 'self' data: https:; "
        "connect-src 'self' https://*.clerk.accounts.dev; "
        "object-src 'none'; "
        "base-uri 'self'; "
        "frame-ancestors 'none'; "
        "form-action 'self'"
    ),
)


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
