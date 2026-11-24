from __future__ import annotations

import pytest

from app.agents.experts import LogsExpert, MetricsExpert, TracesExpert


def _state(case_id: str) -> dict:
    return {"case_id": case_id, "evidences": [], "step": 0}


def test_metrics_expert_ranks_payment_higher_than_checkout() -> None:
    update = MetricsExpert().run(_state("case_001"))
    by_service = {item.service: item for item in update["evidences"]}
    assert by_service["payment"].severity > by_service["checkout"].severity
    assert by_service["payment"].severity == pytest.approx(1.0)


def test_logs_expert_emits_one_evidence_per_service() -> None:
    update = LogsExpert().run(_state("case_001"))
    assert {item.service for item in update["evidences"]} == {"checkout", "payment", "db"}


def test_traces_expert_detects_inventory_error_burst() -> None:
    update = TracesExpert().run(_state("case_003"))
    by_service = {item.service: item for item in update["evidences"]}
    assert by_service["inventory"].severity == pytest.approx(1.0)
    assert by_service["inventory"].severity > by_service["order"].severity
