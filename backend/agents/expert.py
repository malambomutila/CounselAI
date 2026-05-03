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
    # Do not propagate raw LLM text into rendered fields to prevent XSS.
    return {**_EMPTY, "applicable_law": "[Expert analysis unavailable — please retry.]"}


class ExpertWitness:
    def __init__(self, adapter: LLMAdapter):
        self.adapter = adapter

    def analyse(
        self,
        case: str,
        area: str,
        country: str,
        plaintiff_arg: str,
        defense_arg: str,
        *,
        follow_up: str = "",
    ) -> Dict:
        raw = self.adapter.complete(
            expert_prompt(case, area, country, plaintiff_arg, defense_arg,
                          follow_up=follow_up),
            system=EXPERT_SYSTEM,
            max_tokens=900,
            json_mode=True,
        )
        return _parse_json(raw)
