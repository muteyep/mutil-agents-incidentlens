from __future__ import annotations

from app.graph import run_case


def test_prompt_injection_in_logs_does_not_change_verdict() -> None:
    result = run_case("case_injection")
    assert result["hypotheses"][0].service == "redis"
    assert result["hypotheses"][0].fault_type == "resource_saturation"
    assert any(evidence.injected for evidence in result["evidences"])


def test_injected_evidence_is_marked_and_downweighted() -> None:
    result = run_case("case_injection")
    logs = [item for item in result["evidences"] if item.source == "logs"]
    checkout = next(item for item in logs if item.service == "checkout")
    assert checkout.injected is True
    assert "[injection-suspected]" in checkout.summary
