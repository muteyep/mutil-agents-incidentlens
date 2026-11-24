from __future__ import annotations

from app.agents.base import BaseAgent
from app.state import CaseState
from app.tools.mock_sources import get_case


class SupervisorAgent(BaseAgent):
    """Decides which experts to run. M1: all three, always."""

    name = "supervisor"

    def run(self, state: CaseState) -> dict:
        case = get_case(state["case_id"])
        services = sorted(case.get("services", {}))
        plan = [f"{source}:{','.join(services)}" for source in ("metrics", "logs", "traces")]
        return {"plan": plan, "step": state.get("step", 0) + 1}
