from __future__ import annotations

from app.graph import run_case


def test_real_rcaeval_sample_is_diagnosed() -> None:
    """RCAEval multi-source sample: checkoutservice CPU saturation."""
    result = run_case("re_sample_checkout_cpu")
    hypothesis = result["hypotheses"][0]
    assert hypothesis.service == "checkoutservice"
    assert hypothesis.fault_type == "resource_saturation"
    assert all(item.severity <= 1.0 for item in result["evidences"])
