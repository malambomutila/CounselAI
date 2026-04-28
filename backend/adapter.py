"""LLMAdapter — thin wrapper over the OpenAI Chat Completions client.

Single-provider in v1 (OpenAI). The `LLMAdapter` shape is preserved so
agents can later swap providers via env vars without touching their code.
"""
from __future__ import annotations

import logging
from typing import Optional

import httpx
from openai import OpenAI

from backend.settings import OPENAI_API_KEY, AgentConfig

logger = logging.getLogger(__name__)

# Module-level singleton — OpenAI's client is thread-safe and reuses connections
_client: Optional[OpenAI] = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(
            api_key=OPENAI_API_KEY,
            # 5s to connect, 120s to read the full response (judge uses up to
            # 2000 tokens so needs breathing room). max_retries=2 gives one
            # automatic retry with exponential backoff on 429 / 5xx.
            timeout=httpx.Timeout(120.0, connect=5.0),
            max_retries=2,
        )
    return _client


class LLMAdapter:
    def __init__(self, config: AgentConfig):
        self.config = config
        self.client = _get_client()

    def complete(
        self,
        prompt: str,
        *,
        system: Optional[str] = None,
        max_tokens: int = 600,
        json_mode: bool = False,
    ) -> str:
        messages: list[dict] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        params: dict = dict(
            model=self.config.model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=self.config.temperature,
        )
        if json_mode:
            params["response_format"] = {"type": "json_object"}

        try:
            response = self.client.chat.completions.create(**params)
        except Exception:
            logger.exception("OpenAI request failed for agent=%s", self.config.name)
            raise

        content = response.choices[0].message.content or ""
        return content.strip()
