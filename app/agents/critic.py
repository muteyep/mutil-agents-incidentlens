from __future__ import annotations

from app.agents.base import BaseAgent
from app.analysis.causal import rank_root_causes, weighted_ranking
from app.state import CaseState, Evidence, Hypothesis
from app.tools.mock_sources import get_case


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, value))


def infer_fault_type(evidences: list[Evidence]) -> str:
    text = " ".join(item.summary.lower() for item in evidences if not item.injected)
    if "timeout" in text or "deadline" in text:
        return "dependency_timeout"
    if "nullpointer" in text or "exception" in text or "config" in text:
        return "error_burst"
    if (
        "cpu=" in text
        or "memory" in text
        or "oom" in text
        or "pool" in text
        or "slow query" in text
    ):
        return "resource_saturation"
    return "unknown"


class CriticAgent(BaseAgent):
    """Ranks candidates. The ranking is deterministic; the LLM never decides it."""

    name = "critic"

    def __init__(self, use_causal: bool = True) -> None:
        self.use_causal = use_causal

    def run(self, state: CaseState) -> dict:
        evidences = state.get("evidences", [])
        if not evidences:
            return {
                "hypotheses": [Hypothesis(service="unknown", fault_type="unknown", confidence=0.0)],
                "critique": "no evidence collected",
                "step": state.get("step", 0) + 1,
            }

        if self.use_causal:
            topology = get_case(state["case_id"]).get("topology", {})
            ranked = rank_root_causes(evidences, topology)
            label = "causal"
        else:
            ranked = weighted_ranking(evidences)
            label = "weighted"

        positive = sum(max(0.0, item.score) for item in ranked) or 1.0
        hypotheses: list[Hypothesis] = []
        for item in ranked[:3]:
            service_evidence = [ev for ev in evidences if ev.service == item.service]
            hypotheses.append(
                Hypothesis(
                    service=item.service,
                    fault_type=infer_fault_type(service_evidence),
                    confidence=round(_clamp(max(0.0, item.score) / positive), 2),
                    evidence_ids=[ev.evidence_id for ev in service_evidence],
                )
            )

        critique = f"{label} ranking: " + ", ".join(
            f"{item.service}={item.score:.2f} (self={item.self_score:.2f}, callee={item.callee_max:.2f})"
            for item in ranked[:5]
        )
        return {
            "hypotheses": hypotheses,
            "critique": critique,
            "step": state.get("step", 0) + 1,
        }
