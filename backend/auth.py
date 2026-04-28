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

from backend.settings import (
    AUTH_ENABLED,
    CLERK_AUTHORIZED_PARTIES,
    CLERK_FRONTEND_API_URL,
    CLERK_JWKS_URL,
)

# Tokens issued more than CLOCK_SKEW_SECONDS in the past or future are still
# accepted. Clerk and our process clocks can drift slightly; without leeway,
# fresh tokens occasionally bounce.
_CLOCK_SKEW_SECONDS = 30

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

    Performed checks (in order):
      1. signature against the JWKS keyed by the JWT's ``kid``
      2. algorithm pinned to RS256 (blocks alg-confusion attacks)
      3. ``exp`` / ``nbf`` / ``iat`` standard time claims, with a small leeway
      4. ``iss`` matches our Clerk frontend API URL (rejects tokens issued by
         any other Clerk instance)
      5. ``azp`` (authorized party) is on the allow-list (rejects tokens
         minted for someone else's frontend even if from the same Clerk app)
      6. ``sub`` is present

    Raises AuthError on any failure. When AUTH_ENABLED is False, returns a
    stub (used by local dev when CLERK_JWKS_URL is unset).
    """
    if not AUTH_ENABLED:
        return {"sub": "local-anon", "email": "local@dev"}

    if not token:
        raise AuthError("missing session token")

    issuer = CLERK_FRONTEND_API_URL.rstrip("/") if CLERK_FRONTEND_API_URL else None

    try:
        signing_key = _client().get_signing_key_from_jwt(token).key
        claims = jwt.decode(
            token,
            signing_key,
            algorithms=["RS256"],
            issuer=issuer,
            leeway=_CLOCK_SKEW_SECONDS,
            options={
                "verify_signature": True,
                "verify_exp": True,
                "verify_nbf": True,
                "verify_iat": True,
                "verify_iss": bool(issuer),
                # Clerk session tokens don't set aud; verifying it would
                # always fail. azp is the equivalent claim and we check it
                # explicitly below.
                "verify_aud": False,
                "require": ["exp", "iat", "sub"],
            },
        )
    except jwt.ExpiredSignatureError as exc:
        raise AuthError("token expired") from exc
    except jwt.InvalidIssuerError as exc:
        raise AuthError(f"invalid issuer: {exc}") from exc
    except jwt.InvalidTokenError as exc:
        raise AuthError(f"invalid token: {exc}") from exc
    except Exception as exc:  # network / JWKS fetch failures
        logger.exception("Clerk JWKS verification failed")
        raise AuthError(f"verification failed: {exc}") from exc

    # Authorized-party (origin) allow-list. Skip the check if no parties are
    # configured (dev-time convenience) — explicit configuration in prod.
    if CLERK_AUTHORIZED_PARTIES:
        azp = claims.get("azp")
        if azp and azp not in CLERK_AUTHORIZED_PARTIES:
            raise AuthError(f"unauthorized party: {azp}")

    if not claims.get("sub"):
        raise AuthError("token missing sub claim")
    return claims


def _extract_token(request) -> Optional[str]:
    """Pull the Clerk session token from a request — cookie first, then
    ``Authorization: Bearer …`` fallback."""
    token = None
    cookies = getattr(request, "cookies", None) or {}
    if isinstance(cookies, dict):
        token = cookies.get("__session") or cookies.get("session")
    headers = getattr(request, "headers", None) or {}
    if not token and headers:
        auth = headers.get("authorization") or headers.get("Authorization") or ""
        if auth.lower().startswith("bearer "):
            token = auth.split(None, 1)[1]
    return token


def user_id_from_request(request) -> str:
    """Verified Clerk ``sub`` claim from a Starlette/FastAPI/Gradio request."""
    return verify_session_token(_extract_token(request))["sub"]


def user_info_from_request(request) -> Dict[str, Any]:
    """Verified Clerk claims with display fields normalised. Returns sub,
    email, and a best-effort display name. Default Clerk session JWTs do
    not include email — to populate it, configure a custom JWT template
    at https://dashboard.clerk.com/...→ Sessions → Customize and add
    ``email`` / ``full_name`` to the public claims."""
    claims = verify_session_token(_extract_token(request))
    email = (
        claims.get("email")
        or claims.get("primary_email_address")
        or claims.get("email_address")
        or ""
    )
    name = (
        claims.get("name")
        or claims.get("full_name")
        or claims.get("first_name")
        or ""
    )
    return {"sub": claims.get("sub", ""), "email": email, "name": name}
