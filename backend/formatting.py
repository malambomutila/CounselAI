"""Markdown / table helpers for rendering agent outputs in the UI."""
from __future__ import annotations

from typing import Dict, List


def format_expert(expert: Dict) -> str:
    lines: List[str] = []
    if ql := expert.get("key_legal_questions"):
        lines.append("**Key Legal Questions**")
        lines.extend(f"- {q}" for q in ql)
        lines.append("")
    if al := expert.get("applicable_law"):
        lines.append(f"**Applicable Law**\n{al}\n")
    if pr := expert.get("precedents"):
        lines.append(f"**Relevant Precedents**\n{pr}\n")
    if bp := expert.get("burden_of_proof"):
        lines.append(f"**Burden of Proof**\n{bp}\n")
    if rf := expert.get("critical_risk_factors"):
        lines.append("**Critical Risk Factors**")
        lines.extend(f"- {r}" for r in rf)
    return "\n".join(lines)


def format_judge(result: Dict) -> str:
    lines: List[str] = []
    if fv := result.get("final_verdict"):
        lines.append("**Final Verdict**")
        lines.append(fv)
        lines.append("")
    if sp := result.get("stronger_position"):
        lines.append(f"**Stronger Position:** {sp}\n")
    if ja := result.get("judicial_assessment"):
        lines.append(f"**Reasoning**\n{ja}\n")
    if pv := result.get("plaintiff_vulnerabilities"):
        lines.append("**Plaintiff Vulnerabilities**")
        lines.extend(f"- {v}" for v in pv)
        lines.append("")
    if dv := result.get("defense_vulnerabilities"):
        lines.append("**Defense Vulnerabilities**")
        lines.extend(f"- {v}" for v in dv)
    return "\n".join(lines)


def score_rows(judge_result: Dict) -> List[Dict]:
    """Normalise the Judge's score blob into the shape the frontend expects.

    Returns dicts so they can be rendered as ``r.criterion`` / ``r.plaintiff``
    in TSX. (The pre-Gradio-removal version returned lists for
    ``gr.Dataframe``; not needed any more.)"""
    return [
        {
            "criterion": e.get("criterion", ""),
            "plaintiff": e.get("plaintiff", 0),
            "defense":   e.get("defense", 0),
            "notes":     e.get("notes", ""),
        }
        for e in judge_result.get("scores", [])
    ]


def overall_summary(judge_result: Dict) -> str:
    stronger = judge_result.get("stronger_position", "Unknown")
    verdict = (judge_result.get("final_verdict") or "").strip()
    if verdict:
        # Pull the first sentence (or whole verdict if short) for the summary
        first_sentence = verdict.split(". ", 1)[0].rstrip(".")
        return (
            f"**Final Verdict:** {first_sentence}.\n\n"
            f"**Stronger Position:** {stronger}"
        )
    # Fallback if the model didn't return a verdict
    assessment = judge_result.get("judicial_assessment", "")
    first_line = assessment.split("\n", 1)[0] if assessment else ""
    return f"**Overall Assessment:** {first_line}\n\n**Stronger Position:** {stronger}"
