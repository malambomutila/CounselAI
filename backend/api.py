"""JSON + Server-Sent-Events API surface used by the Next.js frontend.

Routes (all under /api):

  GET  /api/me                       → profile chip (sub, email, name)
  GET  /api/conversations            → user's saved conversations (header rows)
  GET  /api/conversations/{conv_id}  → full conversation (header + turns)

  POST /api/initial          → SSE; runs Plaintiff → Defense → Expert.
  POST /api/final-judgment   → SSE; runs Judge → Strategist for an existing turn.
  POST /api/refine           → SSE; re-runs a single agent + cascades.

SSE event format (per W3C):
  event: update
  data:  {"plaintiff": "...", "defense": "...", "expert": "...",
          "judge": "...", "scores": [...], "strategy": "...", "summary": "..."}

  event: done
  data:  {"conversation_id": "abc123"}        # for /api/initial
  data:  {"turn_n": 3}                         # for /api/final-judgment + /api/refine

  event: error
  data:  {"detail": "..."}

Auth: Clerk session token in ``Authorization: Bearer <jwt>``. Verified via the
existing ``backend.auth.user_id_from_request`` (which already understands the
Bearer header in addition to the cookie path used by the deleted Gradio UI).
"""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, Generator, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from backend import store
from backend.auth import (
    AuthError,
    user_id_from_request,
    user_info_from_request,
)
from backend.formatting import (
    format_expert,
    format_judge,
    overall_summary,
    score_rows,
)
from backend.pipeline import (
    JUDGE_PLACEHOLDER,
    STRATEGY_PLACEHOLDER,
    run_initial,
    run_final_judgment,
    run_followup,
)
from backend.prompts import LEGAL_AREAS
from backend.settings import (
    CASE_DESCRIPTION_MAX_CHARS,
    FOLLOW_UP_MAX_CHARS,
    USER_POSITION_MAX_CHARS,
)
from backend.usage import UsageLease, UsageLimitError, release, reserve

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api")


# ── Auth dependency ────────────────────────────────────────────────────────

def require_user(request: Request) -> str:
    """FastAPI dependency: verify the bearer token and return the user_id."""
    try:
        return user_id_from_request(request)
    except AuthError as e:
        raise HTTPException(status_code=401, detail=str(e))


# ── Pydantic models ────────────────────────────────────────────────────────

class InitialRequest(BaseModel):
    case_description: str = Field(..., min_length=1, max_length=CASE_DESCRIPTION_MAX_CHARS)
    legal_area: str
    user_position: str = Field(..., min_length=1, max_length=USER_POSITION_MAX_CHARS)
    country: str = Field(..., min_length=1, description="Jurisdiction whose law applies")


class FinalJudgmentRequest(BaseModel):
    conversation_id: str


class RefineRequest(BaseModel):
    conversation_id: str
    target: Literal["plaintiff", "defense", "expert", "judge", "strategist"]
    follow_up_text: str = Field(..., min_length=1, max_length=FOLLOW_UP_MAX_CHARS)


# ── Helpers ────────────────────────────────────────────────────────────────

def _state_payload(update) -> Dict[str, Any]:
    """Convert the pipeline's positional 7-tuple into a named-field dict so
    the frontend doesn't need to know the magic order."""
    plaintiff, defense, expert, judge_md, scores, strategy, summary = update
    return {
        "plaintiff": plaintiff,
        "defense": defense,
        "expert": expert,
        "judge": judge_md,
        "scores": scores,
        "strategy": strategy,
        "summary": summary,
    }


def _sse_event(event: str, data: Dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


def _legal_areas_or_400(area: str) -> str:
    if area not in LEGAL_AREAS:
        raise HTTPException(status_code=400, detail=f"Unknown legal_area: {area}")
    return area


def _conversation_title(case: str) -> str:
    return (case[:60] + "…") if len(case) > 60 else case


def require_usage_slot(user_id: str = Depends(require_user)) -> UsageLease:
    try:
        return reserve(user_id)
    except UsageLimitError as e:
        raise HTTPException(
            status_code=429,
            detail=e.detail,
            headers={"Retry-After": str(e.retry_after)},
        )


# ── JSON endpoints ─────────────────────────────────────────────────────────

@router.get("/me")
def me(request: Request, user_id: str = Depends(require_user)):
    """Profile info for the sidebar chip."""
    try:
        info = user_info_from_request(request)
    except AuthError as e:
        # Should be unreachable since require_user already passed, but be safe.
        raise HTTPException(status_code=401, detail=str(e))
    return info


@router.get("/legal-areas")
def legal_areas():
    """Static — exposed so the frontend dropdown stays in sync with the
    server-side enum without duplicating the list."""
    return {"areas": LEGAL_AREAS}


@router.get("/conversations")
def list_conversations(user_id: str = Depends(require_user)):
    items = store.list_conversations(user_id)
    return {"conversations": items}


@router.get("/conversations/{conv_id}")
def load_conversation(conv_id: str, user_id: str = Depends(require_user)):
    convo = store.load_conversation(user_id, conv_id)
    if not convo:
        raise HTTPException(status_code=404, detail="conversation not found")

    # Materialise the latest turn into the same named-field shape the SSE
    # stream produces, so the frontend has one render path.
    turns = convo.get("turns") or []
    if not turns:
        return {"header": convo.get("header") or {}, "turns": [], "state": None}

    last = turns[-1]
    agents = last.get("agents") or {}
    state = {
        "plaintiff": agents.get("plaintiff", ""),
        "defense": agents.get("defense", ""),
        "expert": format_expert(agents["expert"]) if agents.get("expert") else "",
        "judge": format_judge(agents["judge"]) if agents.get("judge") else JUDGE_PLACEHOLDER,
        "scores": score_rows(agents["judge"]) if agents.get("judge") else [],
        "strategy": agents.get("strategist", STRATEGY_PLACEHOLDER),
        "summary": overall_summary(agents["judge"]) if agents.get("judge") else "",
    }
    return {
        "header": convo.get("header") or {},
        "turns": turns,
        "state": state,
    }


# ── SSE endpoints ──────────────────────────────────────────────────────────

_SSE_HEADERS = {
    "Cache-Control": "no-cache, no-transform",
    "X-Accel-Buffering": "no",
    "Connection": "keep-alive",
}


@router.post("/initial")
def post_initial(
    req: InitialRequest,
    user_id: str = Depends(require_user),
    lease: UsageLease = Depends(require_usage_slot),
):
    """Phase 1: Plaintiff → Defense → Expert. Persists a new conversation and
    emits its id in the final ``done`` event."""
    area = _legal_areas_or_400(req.legal_area)
    case = req.case_description
    position = req.user_position
    country = req.country

    def event_stream() -> Generator[str, None, None]:
        try:
            gen = run_initial(case, area, position, country)
            final_state: Optional[Dict] = None
            while True:
                try:
                    update = next(gen)
                    yield _sse_event("update", _state_payload(update))
                except StopIteration as stop:
                    final_state = stop.value
                    break

            conv_id = ""
            if final_state:
                try:
                    conv_id = store.create_conversation(
                        user_id,
                        title=_conversation_title(case),
                        legal_area=area,
                        case_description=case,
                        user_position=position,
                        country=country,
                    )
                    store.append_turn(user_id, conv_id, final_state)
                except Exception:
                    logger.exception("failed to persist initial conversation")
            yield _sse_event("done", {"conversation_id": conv_id})
        except ValueError as e:
            logger.warning("run_initial rejected: %s", e)
            yield _sse_event("error", {"detail": str(e)})
        except Exception:
            logger.exception("run_initial crashed")
            yield _sse_event("error", {"detail": "An internal error occurred. Please try again."})
        finally:
            release(lease)

    return StreamingResponse(event_stream(), media_type="text/event-stream",
                             headers=_SSE_HEADERS)


@router.post("/final-judgment")
def post_final_judgment(
    req: FinalJudgmentRequest,
    user_id: str = Depends(require_user),
    lease: UsageLease = Depends(require_usage_slot),
):
    """Phase 2: Judge + Strategist on the latest turn of an existing conversation."""
    convo = store.load_conversation(user_id, req.conversation_id)
    if not convo or not convo.get("turns"):
        raise HTTPException(status_code=404, detail="conversation has no turns")
    prev_turn = convo["turns"][-1]

    def event_stream() -> Generator[str, None, None]:
        try:
            gen = run_final_judgment(prev_turn)
            final_state: Optional[Dict] = None
            while True:
                try:
                    update = next(gen)
                    yield _sse_event("update", _state_payload(update))
                except StopIteration as stop:
                    final_state = stop.value
                    break
            turn_n = -1
            if final_state:
                try:
                    turn_n = store.append_turn(user_id, req.conversation_id, final_state)
                except Exception:
                    logger.exception("failed to persist final-judgment turn")
            yield _sse_event("done", {"turn_n": turn_n,
                                       "conversation_id": req.conversation_id})
        except ValueError as e:
            logger.warning("run_final_judgment rejected: %s", e)
            yield _sse_event("error", {"detail": str(e)})
        except Exception:
            logger.exception("run_final_judgment crashed")
            yield _sse_event("error", {"detail": "An internal error occurred. Please try again."})
        finally:
            release(lease)

    return StreamingResponse(event_stream(), media_type="text/event-stream",
                             headers=_SSE_HEADERS)


@router.post("/refine")
def post_refine(
    req: RefineRequest,
    user_id: str = Depends(require_user),
    lease: UsageLease = Depends(require_usage_slot),
):
    """Re-run a single agent + cascade through downstream agents."""
    convo = store.load_conversation(user_id, req.conversation_id)
    if not convo or not convo.get("turns"):
        raise HTTPException(status_code=404, detail="conversation has no turns")
    prev_turn = convo["turns"][-1]

    def event_stream() -> Generator[str, None, None]:
        try:
            gen = run_followup(prev_turn, req.target, req.follow_up_text)
            final_state: Optional[Dict] = None
            while True:
                try:
                    update = next(gen)
                    yield _sse_event("update", _state_payload(update))
                except StopIteration as stop:
                    final_state = stop.value
                    break
            turn_n = -1
            if final_state:
                try:
                    turn_n = store.append_turn(user_id, req.conversation_id, final_state)
                except Exception:
                    logger.exception("failed to persist refine turn")
            yield _sse_event("done", {"turn_n": turn_n,
                                       "conversation_id": req.conversation_id})
        except ValueError as e:
            logger.warning("run_followup rejected: %s", e)
            yield _sse_event("error", {"detail": str(e)})
        except Exception:
            logger.exception("run_followup crashed")
            yield _sse_event("error", {"detail": "An internal error occurred. Please try again."})
        finally:
            release(lease)

    return StreamingResponse(event_stream(), media_type="text/event-stream",
                             headers=_SSE_HEADERS)
