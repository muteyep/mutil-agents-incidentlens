"""HuggingFace parquet adapter for RCAEval.

The HF copy stores one directory per case:
    re2ob_checkoutservice_cpu_1/
      metrics.parquet   (wide: time, <service>_<metric>, ...)
      logs.parquet      (timestamp, container_name, message)
      traces.parquet    (optional, large)
      inject_time.txt

This adapter converts a case directory into the JSON shape used by the
agents, and attaches the Online Boutique topology so the causal ranker has
something to work with.
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any

FAULT_MAP = {
    "cpu": "resource_saturation",
    "mem": "resource_saturation",
    "disk": "resource_saturation",
    "delay": "dependency_timeout",
    "loss": "dependency_timeout",
    "socket": "dependency_timeout",
}
FAULT_TYPES = set(FAULT_MAP)

ONLINE_BOUTIQUE_TOPOLOGY = {
    "frontend": [
        "adservice",
        "cartservice",
        "checkoutservice",
        "currencyservice",
        "productcatalogservice",
        "recommendationservice",
        "shippingservice",
    ],
    "checkoutservice": [
        "cartservice",
        "currencyservice",
        "emailservice",
        "paymentservice",
        "productcatalogservice",
        "shippingservice",
    ],
    "cartservice": ["redis"],
    "recommendationservice": ["productcatalogservice"],
}


def parse_hf_case_name(name: str) -> dict[str, str]:
    """Parse `re2ob_checkoutservice_cpu_1` into fields."""
    parts = name.split("_")
    for index, part in enumerate(parts):
        if part in FAULT_TYPES and index > 0:
            service = parts[index - 1]
            return {
                "case_id": name,
                "benchmark": "_".join(parts[: index - 1]),
                "root_cause_service": service,
                "fault_type": FAULT_MAP.get(part, "unknown"),
                "raw_fault": part,
            }
    raise ValueError(f"cannot parse RCAEval case name: {name}")


def _wide_points(rows: list[dict[str, Any]]) -> dict[str, list[dict]]:
    points: dict[str, dict[str, dict]] = defaultdict(dict)
    for row in rows:
        ts = str(row.get("time") or row.get("timestamp") or "")
        for column, value in row.items():
            if column in {"time", "timestamp"} or value is None:
                continue
            service, _, metric = column.rpartition("_")
            if not service:
                continue
            point = points[service].setdefault(
                ts, {"ts": ts, "p99_ms": 0.0, "error_rate": 0.0, "cpu": 0.0, "mem": 0.0}
            )
            try:
                number = float(value)
            except (TypeError, ValueError):
                continue
            if metric.startswith("latency"):
                point["p99_ms"] = max(point["p99_ms"], number)
            elif metric == "error":
                point["error_rate"] = max(point["error_rate"], number)
            elif metric == "cpu":
                point["cpu"] = max(point["cpu"], number)
            elif metric == "mem":
                point["mem"] = max(point["mem"], number)
    return {
        service: [values[key] for key in sorted(values)]
        for service, values in points.items()
    }


def _read_metrics(path: Path) -> dict[str, list[dict]]:
    if not path.exists():
        return {}
    import pyarrow.parquet as pq

    return _wide_points(pq.read_table(path).to_pylist())


def _read_logs(path: Path, max_rows: int = 50_000) -> dict[str, list[dict]]:
    if not path.exists():
        return {}
    import pyarrow.parquet as pq

    grouped: dict[str, list[dict]] = defaultdict(list)
    for index, row in enumerate(pq.read_table(path).to_pylist()):
        if index >= max_rows:
            break
        message = str(row.get("message") or "")
        lowered = message.lower()
        level = str(row.get("level") or "INFO").upper()
        if any(token in lowered for token in ("error", "exception", "fail", "timeout")):
            level = "ERROR"
        grouped[str(row.get("container_name") or "unknown")].append(
            {"ts": str(row.get("timestamp") or ""), "level": level, "message": message}
        )
    return dict(grouped)


def _read_traces(path: Path, max_rows: int = 200_000) -> dict[str, list[dict]]:
    if not path.exists():
        return {}
    import pyarrow.parquet as pq

    durations: dict[str, list[float]] = defaultdict(list)
    errors: dict[str, int] = defaultdict(int)
    totals: dict[str, int] = defaultdict(int)
    for index, row in enumerate(pq.read_table(path).to_pylist()):
        if index >= max_rows:
            break
        service = str(row.get("serviceName") or row.get("service") or "unknown")
        durations[service].append(float(row.get("duration") or 0) / 1000.0)
        totals[service] += 1
        if float(row.get("statusCode") or 0) not in (0.0, 0):
            errors[service] += 1
    result: dict[str, list[dict]] = {}
    for service, values in durations.items():
        values.sort()
        p99 = values[min(len(values) - 1, int(len(values) * 0.99))]
        result[service] = [
            {
                "span": service,
                "p99_ms": round(p99, 3),
                "error_rate": round(errors[service] / max(1, totals[service]), 4),
            }
        ]
    return result


def load_hf_case(case_dir: Path, *, with_traces: bool = True) -> dict:
    meta = parse_hf_case_name(case_dir.name)
    metrics = _read_metrics(case_dir / "metrics.parquet")
    logs = _read_logs(case_dir / "logs.parquet")
    traces = _read_traces(case_dir / "traces.parquet") if with_traces else {}

    services = sorted(
        service
        for service in (set(metrics) | set(logs) | set(traces))
        if not service.endswith("-external")
    )
    if not services:
        raise ValueError(f"no telemetry in {case_dir}")

    benchmark = meta.get("benchmark", "")
    is_online_boutique = benchmark.startswith(("re2ob", "re1ob"))
    alert = "frontend" if is_online_boutique else meta["root_cause_service"]
    topology = (
        ONLINE_BOUTIQUE_TOPOLOGY
        if is_online_boutique
        else {alert: [meta["root_cause_service"]]}
    )
    inject_path = case_dir / "inject_time.txt"
    inject_time = int(inject_path.read_text().strip()) if inject_path.exists() else None
    return {
        "case_id": meta["case_id"],
        "inject_time": inject_time,
        "alert": {
            "title": f"{meta['root_cause_service']} {meta.get('raw_fault', '')}",
            "service": alert,
            "severity": "P1",
            "started_at": "1970-01-01T00:00:00Z",
        },
        "topology": topology,
        "ground_truth": {
            "root_cause_service": meta["root_cause_service"],
            "fault_type": meta["fault_type"],
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


def _downsample(points: list[dict], every: int = 5) -> list[dict]:
    if len(points) <= 30:
        return points
    keep = set(range(0, len(points), every))
    for key in ("p99_ms", "error_rate", "cpu", "mem"):
        keep.add(max(range(len(points)), key=lambda index: float(points[index].get(key, 0))))
    return [points[index] for index in sorted(keep)]


def _compact_case(case: dict) -> dict:
    for data in case["services"].values():
        data["metrics"] = _downsample(data["metrics"])
        for point in data["metrics"]:
            point["p99_ms"] = round(float(point.get("p99_ms", 0)), 2)
            point["error_rate"] = round(float(point.get("error_rate", 0)), 4)
            point["cpu"] = round(float(point.get("cpu", 0)), 2)
            point["mem"] = int(float(point.get("mem", 0)))
        logs = data.get("logs", [])
        errors = [item for item in logs if item.get("level") in {"ERROR", "WARN"}][:100]
        samples = [item for item in logs if item.get("level") not in {"ERROR", "WARN"}][:20]
        data["logs"] = errors + samples
    return case


def prepare_hf_dataset(root: Path, out_dir: Path, limit: int = 40) -> list[Path]:
    written: list[Path] = []
    for case_dir in sorted(root.iterdir()):
        if len(written) >= limit:
            break
        if not case_dir.is_dir() or not (case_dir / "metrics.parquet").exists():
            continue
        try:
            case = _compact_case(load_hf_case(case_dir))
        except ValueError:
            continue
        out_dir.mkdir(parents=True, exist_ok=True)
        path = out_dir / f"{case['case_id']}.json"
        path.write_text(json.dumps(case, ensure_ascii=False), encoding="utf-8")
        written.append(path)
    return written


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Convert HF RCAEval parquet cases")
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--out", default=Path("data/cases"), type=Path)
    parser.add_argument("--limit", default=40, type=int)
    args = parser.parse_args()
    paths = prepare_hf_dataset(args.root, args.out, args.limit)
    print(f"converted {len(paths)} cases to {args.out}")
