import json
from typing import Dict

from backend.adapter import LLMAdapter
from backend.prompts import STRATEGIST_SYSTEM, strategist_prompt


class LegalStrategist:
    def __init__(self, adapter: LLMAdapter):
        self.adapter = adapter

    def advise(
        self,
        case: str,
        area: str,
        position: str,
        country: str,
        plaintiff_arg: str,
        defense_arg: str,
        expert_analysis: Dict,
        judge_result: Dict,
        *,
        follow_up: str = "",
    ) -> str:
        expert_summary = json.dumps(expert_analysis, ensure_ascii=False, indent=2)
        judge_summary = json.dumps(judge_result, ensure_ascii=False, indent=2)
        return self.adapter.complete(
            strategist_prompt(case, area, position, country,
                              plaintiff_arg, defense_arg,
                              expert_summary, judge_summary,
                              follow_up=follow_up),
            system=STRATEGIST_SYSTEM,
            max_tokens=700,
        )
