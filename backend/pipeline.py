"""The 5-agent legal-debate pipeline, split into two phases.

Phase 1 (`run_initial`) — Plaintiff → Defense → Expert.
Phase 2 (`run_final_judgment`) — Judge → Strategist (triggered explicitly so
the user has a chance to refine P/D/E first).

Both are Python generators yielding 7-tuples of partial UI state so Gradio
can stream panel updates as each agent finishes:

  (plaintiff_md, defense_md, expert_md, judge_md, score_rows, strategy_md, summary_md)

A third entry point, `run_followup`, re-runs a single agent with extra
context and cascades through downstream agents that already have outputs.
Cascade scope adapts to the current phase: before final judgment, only
P/D/E are touched; after, J/S are included.
"""
from __future__ import annotations

import logging
from typing import Dict, Generator, Optional, Tuple

from backend.adapter import LLMAdapter
from backend.agents import (
    PlaintiffCounsel, DefenseCounsel, ExpertWitness, Judge, LegalStrategist,
)
from backend.formatting import format_expert, format_judge, score_rows, overall_summary
from backend.settings import agent_configs

logger = logging.getLogger(__name__)

# 7-tuple matching the Gradio outputs in ui/app.py
PipelineUpdate = Tuple[str, str, str, str, list, str, str]

# Module-level singletons — adapters are stateless and the OpenAI client is reused.
_configs = agent_configs()
plaintiff_counsel = PlaintiffCounsel(LLMAdapter(_configs["plaintiff"]))
defense_counsel   = DefenseCounsel(LLMAdapter(_configs["defense"]))
expert_witness    = ExpertWitness(LLMAdapter(_configs["expert"]))
judge             = Judge(LLMAdapter(_configs["judge"]))
strategist        = LegalStrategist(LLMAdapter(_configs["strategist"]))


# Cascade order: each agent's input depends on agents to its left.
AGENT_ORDER = ["plaintiff", "defense", "expert", "judge", "strategist"]
_PRE_JUDGMENT = {"plaintiff", "defense", "expert"}

# Placeholder text shown in the Judge / Strategist panels before the user
# clicks "Pronounce Final Judgment".
JUDGE_PLACEHOLDER    = "_Awaiting final judgment. Refine the arguments above, then pronounce judgment when ready._"
STRATEGY_PLACEHOLDER = "_The strategic memo will be generated alongside the final judgment._"


def _validate(case: str, position: str, country: str) -> Optional[PipelineUpdate]:
    if not case.strip():
        return ("Please describe your case to begin.", "", "", "", [], "", "")
    if not position.strip():
        return ("Please describe your position in this case.", "", "", "", [], "", "")
    if not (country or "").strip():
        return ("Please specify the country whose law applies.", "", "", "", [], "", "")
    return None


def _empty(plaintiff_msg: str = "") -> PipelineUpdate:
    return (plaintiff_msg, "", "", JUDGE_PLACEHOLDER, [], STRATEGY_PLACEHOLDER, "")


def _agent_error(name: str, exc: Exception) -> ValueError:
    logger.exception("%s agent failed", name)
    return ValueError(f"{name} failed to respond. Please try again.")


# ── Phase 1 ────────────────────────────────────────────────────────────────

def run_initial(
    case: str,
    area: str,
    position: str,
    country: str,
) -> Generator[PipelineUpdate, None, Dict]:
    """Phase 1: Plaintiff → Defense → Expert.

    Yields progressive states; final yield leaves Judge/Strategist panels
    showing placeholders that prompt the user to pronounce judgment.
    """
    err = _validate(case, position, country)
    if err is not None:
        yield err
        return {}

    yield _empty("Plaintiff's Counsel is building your argument...")
    try:
        p_arg = plaintiff_counsel.argue(case, area, position, country)
    except Exception as exc:
        raise _agent_error("Plaintiff's Counsel", exc) from exc

    yield (p_arg, "Defense Counsel is preparing counter-arguments...",
           "", JUDGE_PLACEHOLDER, [], STRATEGY_PLACEHOLDER, "")
    try:
        d_arg = defense_counsel.argue(case, area, position, country)
    except Exception as exc:
        raise _agent_error("Defense Counsel", exc) from exc

    yield (p_arg, d_arg, "Expert Witness is analysing applicable law and precedents...",
           JUDGE_PLACEHOLDER, [], STRATEGY_PLACEHOLDER, "")
    try:
        expert = expert_witness.analyse(case, area, country, p_arg, d_arg)
    except Exception as exc:
        raise _agent_error("Expert Witness", exc) from exc
    expert_md = format_expert(expert)

    yield (p_arg, d_arg, expert_md, JUDGE_PLACEHOLDER, [], STRATEGY_PLACEHOLDER,
           "_Phase 1 complete. Refine the arguments above, then pronounce final judgment when ready._")

    return {
        "case_description": case,
        "legal_area": area,
        "user_position": position,
        "country": country,
        "agents": {
            "plaintiff": p_arg,
            "defense":   d_arg,
            "expert":    expert,
        },
    }


# ── Phase 2 ────────────────────────────────────────────────────────────────

def run_final_judgment(
    prev_turn: Dict,
) -> Generator[PipelineUpdate, None, Dict]:
    """Phase 2: Judge + Strategist run using whatever P/D/E outputs are
    currently in prev_turn (which may include user refinements)."""
    if not prev_turn or "agents" not in prev_turn:
        raise ValueError("run_final_judgment requires a completed phase-1 turn")

    agents = dict(prev_turn["agents"])
    for required in ("plaintiff", "defense", "expert"):
        if required not in agents:
            raise ValueError(f"prev_turn missing agent: {required}")

    case = prev_turn["case_description"]
    area = prev_turn["legal_area"]
    position = prev_turn["user_position"]
    country = prev_turn.get("country", "")

    p_md = agents["plaintiff"]
    d_md = agents["defense"]
    e_md = format_expert(agents["expert"])

    yield (p_md, d_md, e_md, "Judge is evaluating argument strength...", [],
           STRATEGY_PLACEHOLDER, "")
    try:
        judge_result = judge.evaluate(case, area, country, agents["plaintiff"],
                                      agents["defense"], agents["expert"])
    except Exception as exc:
        raise _agent_error("Judge", exc) from exc
    j_md = format_judge(judge_result)
    rows = score_rows(judge_result)
    agents["judge"] = judge_result

    yield (p_md, d_md, e_md, j_md, rows,
           "Legal Strategist is preparing your case memo...", "")
    try:
        strategy = strategist.advise(case, area, position, country,
                                     agents["plaintiff"], agents["defense"],
                                     agents["expert"], judge_result)
    except Exception as exc:
        raise _agent_error("Legal Strategist", exc) from exc
    agents["strategist"] = strategy

    summary = overall_summary(judge_result)
    yield (p_md, d_md, e_md, j_md, rows, strategy, summary)

    return {**prev_turn, "agents": agents}


# ── Phase 3: targeted follow-up with adaptive cascade ──────────────────────

def _has_judgment(prev_turn: Dict) -> bool:
    """True iff phase 2 has run for this turn."""
    agents = prev_turn.get("agents") or {}
    return "judge" in agents and "strategist" in agents


def run_followup(
    prev_turn: Dict,
    target: str,
    follow_up_text: str,
) -> Generator[PipelineUpdate, None, Dict]:
    """Re-run `target` with extra context, then cascade through whichever
    downstream agents already have outputs.

    - target ∈ {plaintiff, defense, expert}: re-run target. The opposing
      side (for plaintiff/defense) reacts. Then expert cascades. If judgment
      has already been pronounced, judge + strategist also re-cascade.
    - target ∈ {judge, strategist}: requires phase 2 to have run. Re-runs
      target and any downstream agents.
    """
    if target not in AGENT_ORDER:
        raise ValueError(f"Unknown agent: {target}")
    if not follow_up_text.strip():
        raise ValueError("Follow-up text is empty")
    if target in {"judge", "strategist"} and not _has_judgment(prev_turn):
        raise ValueError(
            f"Cannot refine {target} before final judgment has been pronounced."
        )

    case = prev_turn["case_description"]
    area = prev_turn["legal_area"]
    position = prev_turn["user_position"]
    country = prev_turn.get("country", "")
    agents = dict(prev_turn["agents"])
    judgment_present = _has_judgment(prev_turn)

    # Render starting state from the previous turn
    p_md = agents.get("plaintiff", "")
    d_md = agents.get("defense", "")
    e_md = format_expert(agents.get("expert", {})) if agents.get("expert") else ""
    j_md = format_judge(agents["judge"]) if judgment_present else JUDGE_PLACEHOLDER
    rows = score_rows(agents["judge"]) if judgment_present else []
    s_md = agents.get("strategist") if judgment_present else STRATEGY_PLACEHOLDER
    sum_md = overall_summary(agents["judge"]) if judgment_present else ""

    # Step 1: re-run the targeted agent with the follow-up note
    if target == "plaintiff":
        yield (f"Plaintiff's Counsel is reconsidering with: '{follow_up_text}'...",
               d_md, e_md, j_md, rows, s_md, sum_md)
        try:
            agents["plaintiff"] = plaintiff_counsel.argue(case, area, position, country,
                                                         follow_up=follow_up_text)
        except Exception as exc:
            raise _agent_error("Plaintiff's Counsel", exc) from exc
    elif target == "defense":
        yield (p_md, f"Defense Counsel is reconsidering with: '{follow_up_text}'...",
               e_md, j_md, rows, s_md, sum_md)
        try:
            agents["defense"] = defense_counsel.argue(case, area, position, country,
                                                      follow_up=follow_up_text)
        except Exception as exc:
            raise _agent_error("Defense Counsel", exc) from exc
    elif target == "expert":
        yield (p_md, d_md, f"Expert Witness is re-analysing with: '{follow_up_text}'...",
               j_md, rows, s_md, sum_md)
        try:
            agents["expert"] = expert_witness.analyse(case, area, country,
                                                      agents["plaintiff"],
                                                      agents["defense"],
                                                      follow_up=follow_up_text)
        except Exception as exc:
            raise _agent_error("Expert Witness", exc) from exc
    elif target == "judge":
        yield (p_md, d_md, e_md, f"Judge is re-evaluating with: '{follow_up_text}'...",
               rows, s_md, sum_md)
        try:
            agents["judge"] = judge.evaluate(case, area, country,
                                             agents["plaintiff"],
                                             agents["defense"],
                                             agents["expert"],
                                             follow_up=follow_up_text)
        except Exception as exc:
            raise _agent_error("Judge", exc) from exc
    elif target == "strategist":
        yield (p_md, d_md, e_md, j_md, rows,
               f"Legal Strategist is revising with: '{follow_up_text}'...", sum_md)
        try:
            agents["strategist"] = strategist.advise(case, area, position, country,
                                                     agents["plaintiff"],
                                                     agents["defense"],
                                                     agents["expert"],
                                                     agents["judge"],
                                                     follow_up=follow_up_text)
        except Exception as exc:
            raise _agent_error("Legal Strategist", exc) from exc

    # Step 2: cascade — re-run downstream agents whose inputs have changed
    target_idx = AGENT_ORDER.index(target)
    p_md = agents["plaintiff"]
    d_md = agents["defense"]
    e_md = format_expert(agents["expert"])
    j_md = format_judge(agents["judge"]) if judgment_present else JUDGE_PLACEHOLDER
    rows = score_rows(agents["judge"]) if judgment_present else []
    s_md = agents.get("strategist") if judgment_present else STRATEGY_PLACEHOLDER
    sum_md = overall_summary(agents["judge"]) if judgment_present else ""

    # Plaintiff/defense are mutually adversarial: refining one means the other
    # should react. The expert then re-incorporates both updated arguments.
    if target == "plaintiff":
        yield (p_md, "Defense Counsel is updating its counter-argument...",
               e_md, j_md, rows, s_md, sum_md)
        try:
            agents["defense"] = defense_counsel.argue(case, area, position, country)
        except Exception as exc:
            raise _agent_error("Defense Counsel", exc) from exc
        d_md = agents["defense"]
    elif target == "defense":
        yield ("Plaintiff's Counsel is updating its argument...", d_md,
               e_md, j_md, rows, s_md, sum_md)
        try:
            agents["plaintiff"] = plaintiff_counsel.argue(case, area, position, country)
        except Exception as exc:
            raise _agent_error("Plaintiff's Counsel", exc) from exc
        p_md = agents["plaintiff"]

    if target_idx < AGENT_ORDER.index("expert"):
        yield (p_md, d_md, "Expert Witness is re-analysing with updated arguments...",
               j_md, rows, s_md, sum_md)
        try:
            agents["expert"] = expert_witness.analyse(case, area, country,
                                                      agents["plaintiff"],
                                                      agents["defense"])
        except Exception as exc:
            raise _agent_error("Expert Witness", exc) from exc
        e_md = format_expert(agents["expert"])

    # Judge/strategist only cascade if judgment has already been pronounced.
    if judgment_present and target_idx < AGENT_ORDER.index("judge"):
        yield (p_md, d_md, e_md, "Judge is re-evaluating updated arguments...",
               rows, s_md, sum_md)
        try:
            agents["judge"] = judge.evaluate(case, area, country,
                                             agents["plaintiff"],
                                             agents["defense"],
                                             agents["expert"])
        except Exception as exc:
            raise _agent_error("Judge", exc) from exc
        j_md = format_judge(agents["judge"])
        rows = score_rows(agents["judge"])
        sum_md = overall_summary(agents["judge"])

    if judgment_present and target_idx < AGENT_ORDER.index("strategist"):
        yield (p_md, d_md, e_md, j_md, rows,
               "Legal Strategist is updating the memo...", sum_md)
        try:
            agents["strategist"] = strategist.advise(case, area, position, country,
                                                     agents["plaintiff"],
                                                     agents["defense"],
                                                     agents["expert"],
                                                     agents["judge"])
        except Exception as exc:
            raise _agent_error("Legal Strategist", exc) from exc
        s_md = agents["strategist"]

    # Final state matches whichever phase we're in
    if not judgment_present:
        s_md = STRATEGY_PLACEHOLDER
        j_md = JUDGE_PLACEHOLDER
        rows = []
        sum_md = ""

    yield (p_md, d_md, e_md, j_md, rows, s_md, sum_md)

    return {
        "case_description": case,
        "legal_area": area,
        "user_position": position,
        "country": country,
        "agents": agents,
        "follow_up": {"target": target, "text": follow_up_text},
    }
