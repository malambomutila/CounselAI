import json
import re
from typing import Dict

from backend.adapter import LLMAdapter
from backend.prompts import JUDGE_SYSTEM, judge_prompt

_EMPTY: Dict = {
    "final_verdict":             "",
    "stronger_position":         "Unknown",
    "judicial_assessment":       "",
    "plaintiff_vulnerabilities": [],
    "defense_vulnerabilities":   [],
    "scores":                    [],
}


def _parse_json(raw: str) -> Dict:
    clean = raw.strip()
    if clean.startswith("```"):
        clean = clean.split("\n", 1)[-1]
    if clean.endswith("```"):
        clean = clean.rsplit("```", 1)[0]
    clean = clean.strip()
    try:
        data = json.loads(clean)
        if "scores" in data:
            return data
    except json.JSONDecodeError:
        pass
    m = re.search(r"\{.*\}", raw, re.DOTALL)
    if m:
        try:
            data = json.loads(m.group())
            if "scores" in data:
                return data
        except json.JSONDecodeError:
            pass
    # Do not propagate raw LLM text into rendered fields to prevent XSS.
    return {**_EMPTY, "judicial_assessment": "[Judgment analysis unavailable — please retry.]"}


class Judge:
    def __init__(self, adapter: LLMAdapter):
        self.adapter = adapter

    def evaluate(
        self,
        case: str,
        area: str,
        country: str,
        plaintiff_arg: str,
        defense_arg: str,
        expert_analysis: Dict,
        *,
        follow_up: str = "",
    ) -> Dict:
        expert_summary = json.dumps(expert_analysis, ensure_ascii=False, indent=2)
        raw = self.adapter.complete(
            judge_prompt(case, area, country, plaintiff_arg, defense_arg,
                         expert_summary, follow_up=follow_up),
            system=JUDGE_SYSTEM,
            max_tokens=2000,
            json_mode=True,
        )
        return _parse_json(raw)
