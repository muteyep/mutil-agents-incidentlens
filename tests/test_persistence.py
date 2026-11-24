from __future__ import annotations

import pytest

from app.persistence.db import init_db, reset_db
from app.persistence.repository import ApprovalRepository, RunRepository


@pytest.fixture(autouse=True)
def fresh_db():
    reset_db()
    init_db("sqlite://")
    yield
    reset_db()


def test_run_repository_roundtrip() -> None:
    repo = RunRepository()
    run_id = repo.save(
        {
            "case_id": "case_001",
            "mode": "multi",
            "report": "# report",
            "evidences": [{"service": "payment"}],
            "hypotheses": [
                {"service": "payment", "fault_type": "dependency_timeout", "confidence": 0.58}
            ],
            "latency_ms": 3.2,
        }
    )
    assert run_id > 0
    items = repo.list()
    assert items[0]["case_id"] == "case_001"
    assert items[0]["root_cause"] == "payment"
    assert repo.get(run_id)["fault_type"] == "dependency_timeout"


def test_approval_repository_roundtrip() -> None:
    repo = ApprovalRepository()
    repo.save_start("thread-1", "restart payment", "high")
    assert repo.get("thread-1")["status"] == "pending"

    repo.finish("thread-1", True)
    record = repo.get("thread-1")
    assert record["status"] == "approved"
    assert record["approved"] is True


def test_approval_repository_missing_thread() -> None:
    assert ApprovalRepository().get("missing") is None
