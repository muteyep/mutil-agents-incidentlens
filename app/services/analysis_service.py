from __future__ import annotations

from app.graph import run_case
from app.providers.factory import build_llm
from app.services.case_service import CaseNotFoundError, get_case_summary, list_cases
from app.tools.mock_sources import get_case

__all__ = ["CaseNotFoundError", "analyze", "get_case_summary", "list_cases"]


def analyze(case_id: str, mode: str = "multi", use_llm: bool = False) -> dict:
    """Run one RCA case and return an API-friendly payload."""
    import time

    get_case(case_id)  # raises FileNotFoundError -> mapped to 404 by the route
    llm = build_llm() if use_llm else None
    started = time.perf_counter()
    state = run_case(case_id, mode=mode, llm=llm, use_llm_experts=use_llm)
    latency_ms = round((time.perf_counter() - started) * 1000, 2)
    payload = {
        "case_id": case_id,
        "mode": mode,
        "alert": state["alert"],
        "report": state.get("report", ""),
        "critique": state.get("critique", ""),
        "analysis": state.get("analysis", ""),
        "evidences": [item.model_dump() for item in state.get("evidences", [])],
        "hypotheses": [item.model_dump() for item in state.get("hypotheses", [])],
        "usage": state.get("usage", {}),
        "latency_ms": latency_ms,
    }
    try:
        from app.persistence.repository import RunRepository

        payload["run_id"] = RunRepository().save(payload)
    except Exception:  # noqa: BLE001 - analysis must not fail because storage is down
        payload["run_id"] = None
    return payload
