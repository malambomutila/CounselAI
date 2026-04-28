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

DDB_TABLE = _optional("DDB_TABLE", "counselai-dev")
DDB_REGION = _optional("DDB_REGION") or _optional("DEFAULT_AWS_REGION", "eu-west-2")
# When DDB_TABLE is empty, persistence is bypassed (in-memory mode).
PERSISTENCE_ENABLED = bool(DDB_TABLE)

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
