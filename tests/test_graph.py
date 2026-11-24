from __future__ import annotations

import pytest

from app.graph import run_case


@pytest.mark.parametrize(
    ("case_id", "service", "fault_type"),
    [
        ("case_001", "payment", "dependency_timeout"),
        ("case_002", "redis", "resource_saturation"),
        ("case_003", "inventory", "error_burst"),
    ],
)
def test_end_to_end_root_cause(case_id: str, service: str, fault_type: str) -> None:
    result = run_case(case_id)
    hypothesis = result["hypotheses"][0]
    assert hypothesis.service == service
    assert hypothesis.fault_type == fault_type
    assert result["report"].startswith("# 告警研判报告")


def test_all_three_experts_contribute() -> None:
    result = run_case("case_001")
    sources = {item.source for item in result["evidences"]}
    assert sources == {"metrics", "logs", "traces"}
    assert len(result["evidences"]) == 9
