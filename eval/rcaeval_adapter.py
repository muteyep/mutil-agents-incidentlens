"""RCAEval -> IncidentLens case adapter.

Supports two layouts:

1. This project's normalized layout (for tests and hand-curated cases):
   metrics.json + logs.csv + traces.csv + ground_truth.json

2. Raw RCAEval layout:
   metrics.csv (wide: time, <service>_<metric>, ...)
   logs.csv    (time,timestamp,container_name,message,level,...)
   traces.csv  (traceID,spanID,serviceName,duration,statusCode,...)
   Directory name encodes `<benchmark>_<service>_<fault>_<instance>`.

Usage:
    python -m eval.rcaeval_adapter --root /path/to/RCAEval --out data/cases --limit 40
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

FAULT_TYPES = {"cpu", "mem", "disk", "delay", "loss", "socket"}
ALIASES = {"frontendservice": "frontend", "frontend-external": "frontend"}
FAULT_MAP = {
    "cpu": "resource_saturation",
    "mem": "resource_saturation",
    "disk": "resource_saturation",
    "delay": "dependency_timeout",
    "loss": "dependency_timeout",
    "socket": "dependency_timeout",
}


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _as_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _normalize_metrics_json(raw: Any) -> dict[str, list[dict]]:
    if isinstance(raw, dict) and "data" in raw:
        raw = raw["data"]
    if isinstance(raw, dict):
        return {
            str(service): [
                {
                    "ts": str(point.get("ts") or point.get("timestamp") or ""),
                    "p99_ms": _as_float(
                        point.get("p99_ms") or point.get("p99") or point.get("latency_ms")
                    ),
                    "error_rate": _as_float(
                        point.get("error_rate") or point.get("error") or point.get("errorRate")
                    ),
                    "cpu": _as_float(point.get("cpu")),
                    "mem": _as_float(point.get("mem")),
                }
                for point in points
            ]
            for service, points in raw.items()
        }
    if isinstance(raw, list):
        grouped: dict[str, list[dict]] = defaultdict(list)
        for row in raw:
            service = str(row.get("service") or row.get("pod") or "unknown")
            grouped[service].append(
                {
                    "ts": str(row.get("ts") or row.get("timestamp") or ""),
                    "p99_ms": _as_float(row.get("p99_ms") or row.get("p99") or row.get("latency_ms")),
                    "error_rate": _as_float(
                        row.get("error_rate") or row.get("error") or row.get("errorRate")
                    ),
                    "cpu": _as_float(row.get("cpu")),
                    "mem": _as_float(row.get("mem")),
                }
            )
        return dict(grouped)
    return {}


def _read_metrics_csv(path: Path) -> dict[str, list[dict]]:
    """Parse RCAEval's wide metrics.csv into per-service points."""
    if not path.exists():
        return {}
    points: dict[str, dict[str, dict]] = defaultdict(dict)
    with path.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            ts = row.get("time") or row.get("timestamp") or ""
            for column, value in row.items():
                if column in {"time", "timestamp"} or value in (None, ""):
                    continue
                service, _, metric = column.rpartition("_")
                if not service:
                    continue
                point = points[service].setdefault(
                    ts, {"ts": ts, "p99_ms": 0.0, "error_rate": 0.0, "cpu": 0.0, "mem": 0.0}
                )
                if metric.startswith("latency"):
                    point["p99_ms"] = max(point["p99_ms"], _as_float(value))
                elif metric == "error":
                    point["error_rate"] = max(point["error_rate"], _as_float(value))
                elif metric == "cpu":
                    point["cpu"] = max(point["cpu"], _as_float(value))
                elif metric == "mem":
                    point["mem"] = max(point["mem"], _as_float(value))
    return {
        service: [values[key] for key in sorted(values)]
        for service, values in points.items()
    }


def _read_logs(path: Path, max_rows: int = 50_000) -> dict[str, list[dict]]:
    if not path.exists():
        return {}
    grouped: dict[str, list[dict]] = defaultdict(list)
    with path.open(encoding="utf-8", newline="") as handle:
        for index, row in enumerate(csv.DictReader(handle)):
            if index >= max_rows:
                break
            service = str(
                row.get("container_name") or row.get("service") or row.get("pod") or "unknown"
            )
            grouped[service].append(
                {
                    "ts": str(row.get("timestamp") or row.get("time") or row.get("ts") or ""),
                    "level": str(row.get("level") or "INFO").upper(),
                    "message": str(row.get("message") or row.get("msg") or ""),
                }
            )
    return dict(grouped)


def _read_traces(path: Path, max_rows: int = 400_000) -> dict[str, list[dict]]:
    if not path.exists():
        return {}
    durations: dict[str, list[float]] = defaultdict(list)
    errors: dict[str, int] = defaultdict(int)
    totals: dict[str, int] = defaultdict(int)
    precomputed: dict[str, float] = {}
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        columns = set(reader.fieldnames or [])
        for index, row in enumerate(reader):
            if index >= max_rows:
                break
            service = str(
                row.get("serviceName") or row.get("service") or row.get("pod") or "unknown"
            )
            if "duration" in columns:
                # RCAEval traces store microseconds.
                duration = _as_float(row.get("duration")) / 1000.0
            else:
                duration = _as_float(row.get("p99_ms") or row.get("duration_ms"))
            durations[service].append(duration)
            totals[service] += 1
            if "error_rate" in columns and "statusCode" not in columns:
                precomputed[service] = max(
                    precomputed.get(service, 0.0), _as_float(row.get("error_rate"))
                )
            else:
                status = _as_float(row.get("statusCode"))
                if status not in (0.0, 0):
                    errors[service] += 1
    result: dict[str, list[dict]] = {}
    for service, values in durations.items():
        values.sort()
        p99 = values[min(len(values) - 1, int(len(values) * 0.99))]
        result[service] = [
            {
                "span": service,
                "p99_ms": round(p99, 3),
                "error_rate": round(
                    precomputed.get(service, errors[service] / max(1, totals[service])), 4
                ),
            }
        ]
    return result


def _canonical(service: str) -> str:
    return ALIASES.get(service, service)


def _merge_aliases(data: dict[str, list[dict]]) -> dict[str, list[dict]]:
    merged: dict[str, list[dict]] = defaultdict(list)
    for service, items in data.items():
        merged[_canonical(service)].extend(items)
    return dict(merged)


def _metrics_for(case_dir: Path) -> dict[str, list[dict]]:
    json_path = case_dir / "metrics.json"
    if json_path.exists():
        return _normalize_metrics_json(_read_json(json_path))
    return _read_metrics_csv(case_dir / "metrics.csv")


def parse_case_name(name: str) -> dict[str, str] | None:
    """Parse `re2-ob_checkoutservice_cpu_1` style directory names."""
    parts = name.split("_")
    for index, part in enumerate(parts):
        if part in FAULT_TYPES and index > 0:
            service = parts[index - 1]
            benchmark = "_".join(parts[: index - 1]) or "rcaeval"
            return {
                "case_id": name,
                "alert_service": service,
                "root_cause_service": service,
                "fault_type": FAULT_MAP.get(part, "unknown"),
                "benchmark": benchmark,
            }
    return None


def load_rcaeval_case(
    case_dir: Path,
    *,
    case_id: str | None = None,
    alert_service: str | None = None,
    root_service: str | None = None,
    fault_type: str | None = None,
    topology: dict[str, list[str]] | None = None,
) -> dict:
    meta: dict[str, Any] = {}
    meta_path = case_dir / "ground_truth.json"
    if meta_path.exists():
        meta = _read_json(meta_path)
    if not meta:
        meta = parse_case_name(case_dir.name) or {}

    metrics = _merge_aliases(_metrics_for(case_dir))
    logs = _merge_aliases(_read_logs(case_dir / "logs.csv"))
    traces = _merge_aliases(_read_traces(case_dir / "traces.csv"))

    services = sorted(
        service
        for service in (set(metrics) | set(logs) | set(traces))
        if not service.endswith("-external")
    )
    if not services:
        raise ValueError(f"no telemetry found in {case_dir}")

    root = root_service or meta.get("root_cause_service") or services[-1]
    alert = alert_service or meta.get("alert_service") or root
    case = {
        "case_id": case_id or meta.get("case_id") or case_dir.name,
        "alert": {
            "title": f"{alert} anomaly",
            "service": alert,
            "severity": "P1",
            "started_at": meta.get("started_at", "1970-01-01T00:00:00Z"),
        },
        "topology": topology or meta.get("topology") or {alert: [root]},
        "ground_truth": {
            "root_cause_service": root,
            "fault_type": fault_type or meta.get("fault_type") or "unknown",
        },
        "services": {
            service: {
                "metrics": metrics.get(service, []),
                "logs": logs.get(service, []),
                "traces": traces.get(service, []),
            }
            for service in services
        },
    }
    return case


def _case_dirs(root: Path) -> list[Path]:
    found: set[Path] = set()
    for pattern in ("metrics.json", "metrics.csv"):
        for path in root.rglob(pattern):
            found.add(path.parent)
    return sorted(found)


def prepare_dataset(root: Path, out_dir: Path, limit: int = 40) -> list[Path]:
    written: list[Path] = []
    for case_dir in _case_dirs(root):
        if len(written) >= limit:
            break
        try:
            case = load_rcaeval_case(case_dir)
        except ValueError:
            continue
        out_dir.mkdir(parents=True, exist_ok=True)
        path = out_dir / f"{case['case_id']}.json"
        path.write_text(json.dumps(case, ensure_ascii=False, indent=2), encoding="utf-8")
        written.append(path)
    return written


def main() -> None:
    parser = argparse.ArgumentParser(description="Convert RCAEval cases to IncidentLens cases")
    parser.add_argument("--root", required=True, type=Path, help="RCAEval dataset root")
    parser.add_argument("--out", default=Path("data/cases"), type=Path)
    parser.add_argument("--limit", default=40, type=int)
    args = parser.parse_args()
    written = prepare_dataset(args.root, args.out, args.limit)
    print(f"converted {len(written)} cases to {args.out}")


if __name__ == "__main__":
    main()
