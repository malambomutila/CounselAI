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
    if sp := result.get("stronger_position"):
        lines.append(f"**Stronger Position:** {sp}\n")
    if ja := result.get("judicial_assessment"):
        lines.append(f"**Judicial Assessment**\n{ja}\n")
    if pv := result.get("plaintiff_vulnerabilities"):
        lines.append("**Plaintiff Vulnerabilities**")
        lines.extend(f"- {v}" for v in pv)
        lines.append("")
    if dv := result.get("defense_vulnerabilities"):
        lines.append("**Defense Vulnerabilities**")
        lines.extend(f"- {v}" for v in dv)
    return "\n".join(lines)


def score_rows(judge_result: Dict) -> List[List]:
    return [
        [e.get("criterion", ""), e.get("plaintiff", ""), e.get("defense", ""), e.get("notes", "")]
        for e in judge_result.get("scores", [])
    ]


def overall_summary(judge_result: Dict) -> str:
    stronger = judge_result.get("stronger_position", "Unknown")
    assessment = judge_result.get("judicial_assessment", "")
    first_line = assessment.split("\n", 1)[0] if assessment else ""
    return f"**Overall Assessment:** {first_line}\n\n**Stronger Position:** {stronger}"
