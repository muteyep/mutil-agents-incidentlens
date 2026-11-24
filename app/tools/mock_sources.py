"""Offline mock data sources.

Every tool reads one JSON case file under ``data/cases``. In M2 these
functions will be replaced by real Prometheus / Loki / Tempo adapters,
but the agent-facing schemas stay the same.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.registry import tool_registry

DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "cases"
CASE_OVERRIDES: dict[str, dict[str, Any]] = {}


def register_case(case: dict[str, Any]) -> None:
    """Register an in-memory case (used by live telemetry runs)."""
    CASE_OVERRIDES[str(case["case_id"])] = case


def unregister_case(case_id: str) -> None:
    CASE_OVERRIDES.pop(case_id, None)


def get_case(case_id: str) -> dict[str, Any]:
    if case_id in CASE_OVERRIDES:
        return CASE_OVERRIDES[case_id]
    path = DATA_DIR / f"{case_id}.json"
    if not path.exists():
        raise FileNotFoundError(f"case not found: {case_id}")
    return json.loads(path.read_text(encoding="utf-8"))


def query_metrics(case_id: str, service: str) -> list[dict[str, Any]]:
    case = get_case(case_id)
    return list(case.get("services", {}).get(service, {}).get("metrics", []))


def search_logs(case_id: str, service: str) -> list[dict[str, Any]]:
    case = get_case(case_id)
    return list(case.get("services", {}).get(service, {}).get("logs", []))


def get_traces(case_id: str, service: str) -> list[dict[str, Any]]:
    case = get_case(case_id)
    return list(case.get("services", {}).get(service, {}).get("traces", []))


def list_services(case_id: str) -> list[str]:
    case = get_case(case_id)
    return sorted(case.get("services", {}))


tool_registry.register("query_metrics", query_metrics)
tool_registry.register("search_logs", search_logs)
tool_registry.register("get_traces", get_traces)
tool_registry.register("list_services", list_services)
