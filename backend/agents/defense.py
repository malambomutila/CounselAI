from backend.adapter import LLMAdapter
from backend.prompts import DEFENSE_SYSTEM, defense_prompt


class DefenseCounsel:
    def __init__(self, adapter: LLMAdapter):
        self.adapter = adapter

    def argue(self, case: str, area: str, position: str, country: str,
              *, follow_up: str = "") -> str:
        return self.adapter.complete(
            defense_prompt(case, area, position, country, follow_up=follow_up),
            system=DEFENSE_SYSTEM,
            max_tokens=600,
        )
