"""The 5-agent legal-debate pipeline.

Two entry points, both Python generators that yield 7-tuples of partial UI
state so Gradio can stream panel updates as each agent finishes:

  (plaintiff_md, defense_md, expert_md, judge_md, score_rows, strategy_md, summary_md)

- run_initial(case, area, position) — first run, all agents from scratch.
- run_followup(prev_turn, target, follow_up_text) — re-run a targeted agent
  with extra context, then cascade through the other four so the case
  package stays coherent.
"""
from __future__ import annotations

from typing import Dict, Generator, Tuple, Optional

from backend.adapter import LLMAdapter
from backend.agents import (
    PlaintiffCounsel, DefenseCounsel, ExpertWitness, Judge, LegalStrategist,
)
from backend.formatting import format_expert, format_judge, score_rows, overall_summary
from backend.settings import agent_configs

# 7-tuple matching the Gradio outputs in ui/app.py
PipelineUpdate = Tuple[str, str, str, str, list, str, str]

# Module-level singletons — adapters are stateless and OpenAI client is reused.
_configs = agent_configs()
plaintiff_counsel = PlaintiffCounsel(LLMAdapter(_configs["plaintiff"]))
defense_counsel   = DefenseCounsel(LLMAdapter(_configs["defense"]))
expert_witness    = ExpertWitness(LLMAdapter(_configs["expert"]))
judge             = Judge(LLMAdapter(_configs["judge"]))
strategist        = LegalStrategist(LLMAdapter(_configs["strategist"]))


def _empty_update(plaintiff_msg: str = "") -> PipelineUpdate:
    return (plaintiff_msg, "", "", "", [], "", "")


# Sentinel agents in cascade order. Targeted agent re-runs first; the rest
# follow because their outputs depend on it.
AGENT_ORDER = ["plaintiff", "defense", "expert", "judge", "strategist"]


def _validate(case: str, position: str) -> Optional[PipelineUpdate]:
    if not case.strip():
        return ("Please describe your case to begin.", "", "", "", [], "", "")
    if not position.strip():
        return ("Please describe your position in this case.", "", "", "", [], "", "")
    return None


def run_initial(
    case: str,
    area: str,
    position: str,
) -> Generator[PipelineUpdate, None, Dict]:
    """First-time run. Yields 6 progressive states; final yield includes the
    completed turn dict (also returned via StopIteration.value)."""
    err = _validate(case, position)
    if err is not None:
        yield err
        return {}

    yield _empty_update("Plaintiff's Counsel is building your argument...")
    p_arg = plaintiff_counsel.argue(case, area, position)

    yield (p_arg, "Defense Counsel is preparing counter-arguments...", "", "", [], "", "")
    d_arg = defense_counsel.argue(case, area, position)

    yield (p_arg, d_arg, "Expert Witness is analysing applicable law and precedents...",
           "", [], "", "")
    expert = expert_witness.analyse(case, area, p_arg, d_arg)
    expert_md = format_expert(expert)

    yield (p_arg, d_arg, expert_md, "Judge is evaluating argument strength...",
           [], "", "")
    judge_result = judge.evaluate(case, area, p_arg, d_arg, expert)
    judge_md = format_judge(judge_result)
    rows = score_rows(judge_result)

    yield (p_arg, d_arg, expert_md, judge_md, rows,
           "Legal Strategist is preparing your case memo...", "")
    strategy = strategist.advise(case, area, position,
                                 p_arg, d_arg, expert, judge_result)

    summary = overall_summary(judge_result)
    yield (p_arg, d_arg, expert_md, judge_md, rows, strategy, summary)

    return {
        "case_description": case,
        "legal_area": area,
        "user_position": position,
        "agents": {
            "plaintiff":  p_arg,
            "defense":    d_arg,
            "expert":     expert,
            "judge":      judge_result,
            "strategist": strategy,
        },
    }


def run_followup(
    prev_turn: Dict,
    target: str,
    follow_up_text: str,
) -> Generator[PipelineUpdate, None, Dict]:
    """Re-run a targeted agent with extra context, then cascade through the
    other four. `prev_turn` is the dict returned by the previous run.

    Cascade order is fixed (plaintiff → defense → expert → judge → strategist)
    because each agent's input depends on earlier agents' outputs. The
    target agent runs first regardless of position; downstream agents then
    re-run with the target's new output replacing the previous one.
    """
    if target not in AGENT_ORDER:
        raise ValueError(f"Unknown agent: {target}")
    if not follow_up_text.strip():
        raise ValueError("Follow-up text is empty")

    case = prev_turn["case_description"]
    area = prev_turn["legal_area"]
    position = prev_turn["user_position"]
    agents = dict(prev_turn["agents"])  # local mutable copy

    # Render starting state from the previous turn
    p_md = agents["plaintiff"]
    d_md = agents["defense"]
    e_md = format_expert(agents["expert"])
    j_md = format_judge(agents["judge"])
    rows = score_rows(agents["judge"])
    s_md = agents["strategist"]
    sum_md = overall_summary(agents["judge"])

    # Step 1: re-run the targeted agent with the follow-up note
    if target == "plaintiff":
        yield (f"Plaintiff's Counsel is reconsidering with: '{follow_up_text}'...",
               d_md, e_md, j_md, rows, s_md, sum_md)
        agents["plaintiff"] = plaintiff_counsel.argue(case, area, position,
                                                     follow_up=follow_up_text)
    elif target == "defense":
        yield (p_md, f"Defense Counsel is reconsidering with: '{follow_up_text}'...",
               e_md, j_md, rows, s_md, sum_md)
        agents["defense"] = defense_counsel.argue(case, area, position,
                                                  follow_up=follow_up_text)
    elif target == "expert":
        yield (p_md, d_md, f"Expert Witness is re-analysing with: '{follow_up_text}'...",
               j_md, rows, s_md, sum_md)
        agents["expert"] = expert_witness.analyse(case, area,
                                                  agents["plaintiff"],
                                                  agents["defense"],
                                                  follow_up=follow_up_text)
    elif target == "judge":
        yield (p_md, d_md, e_md, f"Judge is re-evaluating with: '{follow_up_text}'...",
               rows, s_md, sum_md)
        agents["judge"] = judge.evaluate(case, area,
                                         agents["plaintiff"],
                                         agents["defense"],
                                         agents["expert"],
                                         follow_up=follow_up_text)
    elif target == "strategist":
        yield (p_md, d_md, e_md, j_md, rows,
               f"Legal Strategist is revising with: '{follow_up_text}'...", sum_md)
        agents["strategist"] = strategist.advise(case, area, position,
                                                 agents["plaintiff"],
                                                 agents["defense"],
                                                 agents["expert"],
                                                 agents["judge"],
                                                 follow_up=follow_up_text)

    # Step 2: cascade — re-run agents that come AFTER the target in dependency
    # order, since their input has now changed.
    target_idx = AGENT_ORDER.index(target)
    p_md = agents["plaintiff"]
    d_md = agents["defense"]
    e_md = format_expert(agents["expert"])
    j_md = format_judge(agents["judge"])
    rows = score_rows(agents["judge"])
    s_md = agents["strategist"]
    sum_md = overall_summary(agents["judge"])

    # If plaintiff or defense was the target, re-run defense or plaintiff too
    # (so the opposing side reacts to the new argument).
    if target == "plaintiff":
        yield (p_md, "Defense Counsel is updating its counter-argument...",
               e_md, j_md, rows, s_md, sum_md)
        agents["defense"] = defense_counsel.argue(case, area, position)
        d_md = agents["defense"]
    elif target == "defense":
        yield ("Plaintiff's Counsel is updating its argument...", d_md,
               e_md, j_md, rows, s_md, sum_md)
        agents["plaintiff"] = plaintiff_counsel.argue(case, area, position)
        p_md = agents["plaintiff"]

    # Cascade expert/judge/strategist whenever target was upstream of them
    if target_idx <= AGENT_ORDER.index("expert"):
        yield (p_md, d_md, "Expert Witness is re-analysing with updated arguments...",
               j_md, rows, s_md, sum_md)
        agents["expert"] = expert_witness.analyse(case, area,
                                                  agents["plaintiff"],
                                                  agents["defense"])
        e_md = format_expert(agents["expert"])

    if target_idx <= AGENT_ORDER.index("judge"):
        yield (p_md, d_md, e_md, "Judge is re-evaluating updated arguments...",
               rows, s_md, sum_md)
        agents["judge"] = judge.evaluate(case, area,
                                         agents["plaintiff"],
                                         agents["defense"],
                                         agents["expert"])
        j_md = format_judge(agents["judge"])
        rows = score_rows(agents["judge"])
        sum_md = overall_summary(agents["judge"])

    if target_idx <= AGENT_ORDER.index("strategist"):
        yield (p_md, d_md, e_md, j_md, rows,
               "Legal Strategist is updating the memo...", sum_md)
        agents["strategist"] = strategist.advise(case, area, position,
                                                 agents["plaintiff"],
                                                 agents["defense"],
                                                 agents["expert"],
                                                 agents["judge"])
        s_md = agents["strategist"]

    yield (p_md, d_md, e_md, j_md, rows, s_md, sum_md)

    return {
        "case_description": case,
        "legal_area": area,
        "user_position": position,
        "agents": agents,
        "follow_up": {"target": target, "text": follow_up_text},
    }
