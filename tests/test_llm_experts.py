from __future__ import annotations

from app.agents.llm_experts import LLMLogsExpert, LLMTracesExpert
from app.graph import run_case
from app.providers.fake import FakeLLM


def _state(case_id: str) -> dict:
    return {"case_id": case_id, "evidences": [], "step": 0, "usage": {}}


def test_llm_logs_expert_returns_structured_evidence() -> None:
    llm = FakeLLM('{"summary": "redis memory pressure", "severity": 0.8}')
    update = LLMLogsExpert(llm).run(_state("case_001"))
    assert len(update["evidences"]) == 3
    assert update["evidences"][0].summary == "redis memory pressure"
    assert update["usage"]["prompt_tokens"] == 30
    assert update["usage"]["completion_tokens"] == 15


def test_llm_logs_expert_falls_back_on_invalid_json() -> None:
    llm = FakeLLM("not json")
    update = LLMLogsExpert(llm).run(_state("case_001"))
    assert len(update["evidences"]) == 3
    assert "error/warn" in update["evidences"][0].summary


def test_llm_traces_expert_returns_structured_evidence() -> None:
    llm = FakeLLM('{"summary": "trace latency spike", "severity": 0.7}')
    update = LLMTracesExpert(llm).run(_state("case_001"))
    assert len(update["evidences"]) == 3
    assert update["evidences"][0].summary == "trace latency spike"


def test_llm_run_records_usage_and_keeps_verdict() -> None:
    llm = FakeLLM('{"summary": "llm evidence", "severity": 0.8}')
    result = run_case("case_001", llm=llm, use_llm_experts=True)
    assert result["hypotheses"][0].service == "payment"
    assert result["usage"]["prompt_tokens"] > 0
