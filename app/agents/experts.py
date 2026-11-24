from __future__ import annotations

import statistics

from app.agents.base import BaseAgent
from app.guardrails.injection import scan
from app.registry import tool_registry
from app.state import CaseState, Evidence
from app.tools.mock_sources import list_services


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, value))


def _windowed_z(points: list[dict], inject_time: float) -> float | None:
    """Compare a post-injection window against the pre-injection baseline."""
    baseline = [p for p in points if float(p["ts"]) < inject_time - 30]
    incident = [p for p in points if inject_time <= float(p["ts"]) <= inject_time + 300]
    if len(baseline) < 3 or not incident:
        return None
    scores: list[float] = []
    for key in ("p99_ms", "error_rate", "cpu", "mem"):
        base = [float(p.get(key, 0.0)) for p in baseline]
        live = [float(p.get(key, 0.0)) for p in incident]
        median = statistics.median(base)
        mad = statistics.median(abs(value - median) for value in base)
        peak = max(live)
        if mad > 0:
            z = 0.6745 * (peak - median) / mad
        else:
            std = statistics.pstdev(base)
            z = (peak - median) / std if std > 0 else 0.0
        effect = (peak - median) / max(abs(median), 1e-9)
        scores.append(z * min(1.0, effect / 2.0))
    return max(scores)


def _robust_z(values: list[float]) -> float:
    """Max deviation from the median in MAD units, weighted by effect size."""
    if not values:
        return 0.0
    median = statistics.median(values)
    mad = statistics.median(abs(value - median) for value in values)
    peak = max(values)
    if mad > 0:
        base = 0.6745 * (peak - median) / mad
    else:
        std = statistics.pstdev(values)
        base = (peak - median) / std if std > 0 else 0.0
    effect = (peak - median) / max(abs(median), 1e-9)
    return base * min(1.0, effect / 2.0)


class MetricsExpert(BaseAgent):
    name = "metrics"

    def build(
        self, service: str, points: list[dict], inject_time: float | None = None
    ) -> Evidence:
        max_p99 = max(point["p99_ms"] for point in points)
        max_error = max(point["error_rate"] for point in points)
        max_cpu = max(point.get("cpu", 0.0) for point in points)
        windowed = _windowed_z(points, inject_time) if inject_time else None
        if windowed is not None:
            severity = _clamp(windowed / 20.0)
            summary = f"win_z={windowed:.1f} p99={max_p99}ms error_rate={max_error:.0%} cpu={max_cpu:.0f}%"
        elif len(points) >= 5:
            zscores = [
                _robust_z([float(point.get(key, 0.0)) for point in points])
                for key in ("p99_ms", "error_rate", "cpu", "mem")
            ]
            peak_z = max(zscores)
            severity = _clamp(peak_z / 20.0)
            summary = (
                f"z={peak_z:.1f} p99={max_p99}ms error_rate={max_error:.0%} "
                f"cpu={max_cpu:.0f}%"
            )
        else:
            severity = _clamp(max_p99 / 5000 * 0.6 + max_error * 2 + max_cpu / 100 * 0.3)
            summary = f"p99={max_p99}ms error_rate={max_error:.0%} cpu={max_cpu:.0f}%"
        return Evidence(
            evidence_id=f"ev-metrics-{service}",
            source="metrics",
            service=service,
            summary=summary,
            severity=severity,
        )

    def run(self, state: CaseState) -> dict:
        case_id = state["case_id"]
        inject_time = state.get("inject_time")
        evidences: list[Evidence] = []
        for service in list_services(case_id):
            points = tool_registry.call("query_metrics", case_id=case_id, service=service)
            if points:
                evidences.append(self.build(service, points, inject_time))
        return {"evidences": evidences}


class LogsExpert(BaseAgent):
    name = "logs"

    def build(self, service: str, logs: list[dict]) -> Evidence:
        errors = [item for item in logs if item.get("level") in {"ERROR", "WARN"}]
        flags: list[str] = []
        for item in logs:
            flags.extend(scan(item.get("message", "")))
        injected = bool(flags)
        severity = _clamp(len(errors) / max(1, len(logs)) + (0.2 if errors else 0.0))
        if injected:
            severity = _clamp(severity * 0.5)
        top = errors[0]["message"] if errors else "no error logs"
        prefix = "[injection-suspected] " if injected else ""
        return Evidence(
            evidence_id=f"ev-logs-{service}",
            source="logs",
            service=service,
            summary=f"{prefix}{len(errors)}/{len(logs)} error/warn; top={top[:90]}",
            severity=severity,
            injected=injected,
        )

    def run(self, state: CaseState) -> dict:
        case_id = state["case_id"]
        evidences: list[Evidence] = []
        for service in list_services(case_id):
            logs = tool_registry.call("search_logs", case_id=case_id, service=service)
            if logs:
                evidences.append(self.build(service, logs))
        return {"evidences": evidences}


class TracesExpert(BaseAgent):
    name = "traces"

    def build(self, service: str, spans: list[dict]) -> Evidence:
        max_p99 = max(span["p99_ms"] for span in spans)
        max_error = max(span["error_rate"] for span in spans)
        severity = _clamp(max_p99 / 5000 * 0.5 + max_error * 2)
        return Evidence(
            evidence_id=f"ev-traces-{service}",
            source="traces",
            service=service,
            summary=f"span p99={max_p99}ms error_rate={max_error:.0%}",
            severity=severity,
        )

    def run(self, state: CaseState) -> dict:
        case_id = state["case_id"]
        evidences: list[Evidence] = []
        for service in list_services(case_id):
            spans = tool_registry.call("get_traces", case_id=case_id, service=service)
            if spans:
                evidences.append(self.build(service, spans))
        return {"evidences": evidences}
