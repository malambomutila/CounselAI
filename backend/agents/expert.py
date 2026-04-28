import json
import re
from typing import Dict

from backend.adapter import LLMAdapter
from backend.prompts import EXPERT_SYSTEM, expert_prompt

_EMPTY: Dict = {
    "key_legal_questions":   [],
    "applicable_law":        "",
    "precedents":            "",
    "burden_of_proof":       "",
    "critical_risk_factors": [],
}


def _parse_json(raw: str) -> Dict:
    """Parse JSON, recovering from common LLM output quirks (code fences, prose wrapping)."""
    clean = raw.strip()
    if clean.startswith("```"):
        clean = clean.split("\n", 1)[-1]
    if clean.endswith("```"):
        clean = clean.rsplit("```", 1)[0]
    clean = clean.strip()
    try:
        return json.loads(clean)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", raw, re.DOTALL)
        if m:
            try:
                return json.loads(m.group())
            except json.JSONDecodeError:
                pass
    return {**_EMPTY, "applicable_law": raw}


class ExpertWitness:
    def __init__(self, adapter: LLMAdapter):
        self.adapter = adapter

    def analyse(
        self,
        case: str,
        area: str,
        plaintiff_arg: str,
        defense_arg: str,
        *,
        follow_up: str = "",
    ) -> Dict:
        raw = self.adapter.complete(
            expert_prompt(case, area, plaintiff_arg, defense_arg, follow_up=follow_up),
            system=EXPERT_SYSTEM,
            max_tokens=600,
            json_mode=True,
        )
        return _parse_json(raw)
