"""Generate a reproducible synthetic evaluation set.

These cases validate the harness, not real-world accuracy. Replace them with
RCAEval / OpenRCA via `eval/rcaeval_adapter.py` for a public benchmark.
"""

from __future__ import annotations

import json
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parents[1] / "data" / "cases"

PAIRS = [
    ("checkout", "payment"),
    ("search", "redis"),
    ("order", "inventory"),
    ("api", "auth"),
    ("web", "catalog"),
    ("cart", "coupon"),
    ("feed", "ranking"),
    ("profile", "userdb"),
    ("notify", "mq"),
    ("billing", "ledger"),
    ("gateway", "edge"),
    ("session", "cache"),
]
FAULTS = ["dependency_timeout", "resource_saturation", "error_burst"]


def _metrics(p99: float, error: float, cpu: float, ts: str) -> list[dict]:
    return [{"ts": ts, "p99_ms": p99, "error_rate": error, "cpu": cpu}]


def _logs(level: str, messages: list[str], ts: str) -> list[dict]:
    return [{"ts": ts, "level": level, "message": message} for message in messages]


def _traces(p99: float, error: float) -> list[dict]:
    return [{"span": "span", "p99_ms": p99, "error_rate": error}]


def build_case(index: int, caller: str, root: str, fault: str) -> dict:
    ts = "2026-11-10T12:00:00Z"
    if fault == "dependency_timeout":
        # Victim bias: the caller shows *more* errors than the real root cause.
        root_metrics = _metrics(2500, 0.18, 70, ts)
        caller_metrics = _metrics(3200, 0.42, 60, ts)
        root_logs = _logs("ERROR", ["upstream timeout: context deadline exceeded", "gateway timeout"], ts)
        caller_logs = _logs("ERROR", ["upstream timeout calling dependency", "504 from dependency"], ts)
        root_traces = _traces(2400, 0.20)
        caller_traces = _traces(3000, 0.42)
    elif fault == "resource_saturation":
        root_metrics = _metrics(5000, 0.03, 96, ts)
        caller_metrics = _metrics(3200, 0.32, 60, ts)
        root_logs = _logs("ERROR", ["OOM command not allowed: used memory > maxmemory", "memory pressure"], ts)
        caller_logs = _logs("ERROR", ["dependency timeout after 2000ms"], ts)
        root_traces = _traces(2500, 0.05)
        caller_traces = _traces(2800, 0.35)
    else:  # error_burst
        root_metrics = _metrics(220, 0.03, 30, ts)
        caller_metrics = _metrics(800, 0.32, 50, ts)
        root_logs = _logs("ERROR", ["NullPointerException in handler", "missing config: service.token"], ts)
        caller_logs = _logs("ERROR", ["POST /api 500", "downstream call failed"], ts)
        root_traces = _traces(720, 0.5)
        caller_traces = _traces(750, 0.30)

    return {
        "case_id": f"gen_{index:03d}",
        "alert": {
            "title": f"{caller} 服务异常",
            "service": caller,
            "severity": "P1",
            "started_at": ts,
        },
        "topology": {caller: [root], "frontend": [caller]},
        "ground_truth": {"root_cause_service": root, "fault_type": fault},
        "services": {
            caller: {"metrics": caller_metrics, "logs": caller_logs, "traces": caller_traces},
            root: {"metrics": root_metrics, "logs": root_logs, "traces": root_traces},
            "frontend": {
                "metrics": _metrics(150, 0.001, 30, ts),
                "logs": _logs("INFO", ["healthy"], ts),
                "traces": _traces(150, 0.001),
            },
        },
    }


def main() -> None:
    for index, (caller, root) in enumerate(PAIRS, start=1):
        fault = FAULTS[(index - 1) % len(FAULTS)]
        case = build_case(index, caller, root, fault)
        path = DATA_DIR / f"{case['case_id']}.json"
        path.write_text(json.dumps(case, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"generated {len(PAIRS)} cases in {DATA_DIR}")


if __name__ == "__main__":
    main()
