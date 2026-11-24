from __future__ import annotations

from app.runtime import run_persistent


def test_persistent_run_completes() -> None:
    result = run_persistent("case_001", thread_id="test-persistent-001")
    assert result["hypotheses"][0].service == "payment"
    assert result["report"].startswith("# 告警研判报告")
