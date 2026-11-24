from __future__ import annotations

import os

# Keep API tests on an in-memory database.
os.environ.setdefault("DATABASE_URL", "sqlite://")

from fastapi.testclient import TestClient

from app.api.app import app

client = TestClient(app)


def test_health() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_list_cases() -> None:
    response = client.get("/api/cases")
    assert response.status_code == 200
    ids = {item["case_id"] for item in response.json()}
    assert "case_001" in ids
    assert "re_sample_checkout_cpu" in ids


def test_get_case() -> None:
    response = client.get("/api/cases/case_001")
    assert response.status_code == 200
    assert response.json()["root_cause"] == "payment"


def test_get_case_not_found() -> None:
    response = client.get("/api/cases/does-not-exist")
    assert response.status_code == 404


def test_analyze_case() -> None:
    response = client.post("/api/analyze", json={"case_id": "case_001", "mode": "multi"})
    assert response.status_code == 200
    body = response.json()
    assert body["hypotheses"][0]["service"] == "payment"
    assert body["hypotheses"][0]["fault_type"] == "dependency_timeout"
    assert body["report"].startswith("# 告警研判报告")
    assert body["latency_ms"] >= 0
    assert body["run_id"] is not None


def test_runs_endpoint_after_analyze() -> None:
    client.post("/api/analyze", json={"case_id": "case_002", "mode": "multi"})
    response = client.get("/api/runs")
    assert response.status_code == 200
    assert any(item["case_id"] == "case_002" for item in response.json())


def test_analyze_invalid_mode() -> None:
    response = client.post("/api/analyze", json={"case_id": "case_001", "mode": "nope"})
    assert response.status_code == 422


def test_analyze_not_found() -> None:
    response = client.post("/api/analyze", json={"case_id": "does-not-exist"})
    assert response.status_code == 404


def test_approval_flow() -> None:
    start = client.post(
        "/api/approval/start", json={"action": "restart payment", "risk": "high"}
    )
    assert start.status_code == 200
    body = start.json()
    assert body["status"] == "pending"
    assert body["payload"]["action"] == "restart payment"

    resume = client.post(
        f"/api/approval/{body['thread_id']}/resume", json={"approved": True}
    )
    assert resume.status_code == 200
    assert resume.json()["status"] == "approved"
    assert resume.json()["approved"] is True
