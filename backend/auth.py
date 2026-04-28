"""Clerk JWT verification.

Single public function: ``verify_session_token(token: str) -> dict``.

When ``CLERK_JWKS_URL`` is unset (AUTH_ENABLED == False), all requests are
treated as a single anonymous user — useful for local dev. In that case,
``verify_session_token`` returns a deterministic stub with
``sub = "local-anon"``.

JWKS keys are cached in-process for 1 hour. On signature verification the
right key is selected by ``kid`` (key id) from the JWT header.
"""
from __future__ import annotations

import logging
import threading
import time
from typing import Any, Dict, Optional

import httpx
import jwt
from jwt import PyJWKClient

from backend.settings import AUTH_ENABLED, CLERK_JWKS_URL

logger = logging.getLogger(__name__)


class AuthError(RuntimeError):
    pass


# JWKS client caches the keys internally; we instantiate once.
_jwk_client: Optional[PyJWKClient] = None
_jwk_lock = threading.Lock()


def _client() -> PyJWKClient:
    global _jwk_client
    if _jwk_client is None:
        with _jwk_lock:
            if _jwk_client is None:
                _jwk_client = PyJWKClient(
                    CLERK_JWKS_URL,
                    cache_keys=True,
                    lifespan=3600,
                )
    return _jwk_client


def verify_session_token(token: Optional[str]) -> Dict[str, Any]:
    """Verify a Clerk session JWT and return its claims.

    Raises AuthError on any verification failure (missing, expired,
    bad signature, etc.). When AUTH_ENABLED is False, returns a stub.
    """
    if not AUTH_ENABLED:
        return {"sub": "local-anon", "email": "local@dev"}

    if not token:
        raise AuthError("missing session token")

    try:
        signing_key = _client().get_signing_key_from_jwt(token).key
        claims = jwt.decode(
            token,
            signing_key,
            algorithms=["RS256"],
            options={"verify_aud": False},  # Clerk session tokens don't always set aud
        )
    except jwt.ExpiredSignatureError as exc:
        raise AuthError("token expired") from exc
    except jwt.InvalidTokenError as exc:
        raise AuthError(f"invalid token: {exc}") from exc
    except Exception as exc:  # network / JWKS fetch failures
        logger.exception("Clerk JWKS verification failed")
        raise AuthError(f"verification failed: {exc}") from exc

    if not claims.get("sub"):
        raise AuthError("token missing sub claim")
    return claims


def user_id_from_request(request) -> str:
    """Extract Clerk session token from a Starlette/FastAPI Request and return
    the verified ``sub`` claim. Used by FastAPI middleware AND inside Gradio
    handlers (Gradio's ``gr.Request`` exposes ``.cookies`` and ``.headers``)."""
    token = None

    # Cookie set by Clerk's frontend SDK after sign-in
    cookies = getattr(request, "cookies", None) or {}
    if isinstance(cookies, dict):
        token = cookies.get("__session") or cookies.get("session")

    # Authorization header fallback (useful for API clients / curl tests)
    headers = getattr(request, "headers", None) or {}
    if not token and headers:
        auth = headers.get("authorization") or headers.get("Authorization") or ""
        if auth.lower().startswith("bearer "):
            token = auth.split(None, 1)[1]

    return verify_session_token(token)["sub"]
