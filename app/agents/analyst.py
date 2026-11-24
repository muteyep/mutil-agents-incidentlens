from __future__ import annotations

from app.agents.base import BaseAgent
from app.providers.base import LLMError, LLMProvider
from app.state import CaseState

SYSTEM = (
    "你是资深 SRE。只能基于给定证据写 2-3 句研判结论和 1 条处置建议，"
    "不要编造未提供的服务、数字或时间。"
)


class AnalystAgent(BaseAgent):
    """Turns deterministic evidence + ranking into a readable analysis.

    The root cause is already decided by the causal ranker. The LLM only
    explains it, so a bad generation cannot change the verdict.
    """

    name = "analyst"

    def __init__(self, llm: LLMProvider | None = None) -> None:
        self._llm = llm

    def run(self, state: CaseState) -> dict:
        hypothesis = state["hypotheses"][0]
        top = [item for item in state["evidences"] if item.service == hypothesis.service]
        evidence_text = "\n".join(f"- [{item.source}] {item.summary}" for item in top)

        if self._llm is None:
            return {
                "analysis": self._rule_based(hypothesis.service, hypothesis.fault_type, top),
                "usage": {"prompt_tokens": 0, "completion_tokens": 0, "cost_usd": 0.0},
            }

        prompt = (
            f"根因候选：{hypothesis.service}\n"
            f"故障类型：{hypothesis.fault_type}\n"
            f"证据：\n{evidence_text}\n"
            "请给出研判说明和处置建议。"
        )
        try:
            response = self._llm.generate(
                [{"role": "system", "content": SYSTEM}, {"role": "user", "content": prompt}],
                temperature=0.2,
            )
            return {
                "analysis": response.content.strip(),
                "usage": {
                    "prompt_tokens": response.prompt_tokens,
                    "completion_tokens": response.completion_tokens,
                    "cost_usd": response.cost_usd,
                },
            }
        except LLMError:
            return {
                "analysis": self._rule_based(hypothesis.service, hypothesis.fault_type, top),
                "usage": {"prompt_tokens": 0, "completion_tokens": 0, "cost_usd": 0.0},
            }

    @staticmethod
    def _rule_based(service: str, fault_type: str, top: list) -> str:
        summaries = "；".join(item.summary for item in top[:3])
        return f"根因指向 {service}（{fault_type}）。主要证据：{summaries}。"
