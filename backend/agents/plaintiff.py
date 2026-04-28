from backend.adapter import LLMAdapter
from backend.prompts import PLAINTIFF_SYSTEM, plaintiff_prompt


class PlaintiffCounsel:
    def __init__(self, adapter: LLMAdapter):
        self.adapter = adapter

    def argue(self, case: str, area: str, position: str, country: str,
              *, follow_up: str = "") -> str:
        return self.adapter.complete(
            plaintiff_prompt(case, area, position, country, follow_up=follow_up),
            system=PLAINTIFF_SYSTEM,
            max_tokens=600,
        )
