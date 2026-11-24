from __future__ import annotations

from collections import defaultdict

import httpx

from app.telemetry.base import TelemetryError, Window


class PrometheusClient:
    """Thin Prometheus query_range client.

    Metric names are configurable because every deployment names them
    differently; the defaults match the OpenTelemetry demo conventions.
    """

    def __init__(
        self,
        base_url: str,
        *,
        timeout: float = 10.0,
        transport: httpx.BaseTransport | None = None,
        latency_metric: str = "http_request_duration_seconds_bucket",
        request_metric: str = "http_requests_total",
        cpu_metric: str = "container_cpu_usage_seconds_total",
    ) -> None:
        self._client = httpx.Client(
            base_url=base_url.rstrip("/"), timeout=timeout, transport=transport
        )
        self._latency = latency_metric
        self._requests = request_metric
        self._cpu = cpu_metric

    def _query_range(self, promql: str, window: Window) -> list[tuple[float, float]]:
        try:
            response = self._client.get(
                "/api/v1/query_range",
                params={
                    "query": promql,
                    "start": window.start,
                    "end": window.end,
                    "step": "15s",
                },
            )
            response.raise_for_status()
            payload = response.json()
        except Exception as exc:
            raise TelemetryError(f"prometheus query failed: {exc}") from exc
        results = payload.get("data", {}).get("result", [])
        if not results:
            return []
        return [(float(ts), float(value)) for ts, value in results[0].get("values", [])]

    def query(self, service: str, window: Window) -> list[dict]:
        latency = self._query_range(
            f'histogram_quantile(0.99, sum(rate({self._latency}{{service="{service}"}}[1m])) by (le))',
            window,
        )
        errors = self._query_range(
            f'sum(rate({self._requests}{{service="{service}",status=~"5.."}}[1m]))'
            f' / sum(rate({self._requests}{{service="{service}"}}[1m]))',
            window,
        )
        cpu = self._query_range(
            f'sum(rate({self._cpu}{{pod=~"{service}.*"}}[1m]))', window
        )
        points: dict[float, dict] = defaultdict(
            lambda: {"ts": "", "p99_ms": 0.0, "error_rate": 0.0, "cpu": 0.0, "mem": 0.0}
        )
        for ts, value in latency:
            points[ts]["ts"] = str(int(ts))
            points[ts]["p99_ms"] = round(value * 1000, 3)
        for ts, value in errors:
            points[ts]["ts"] = str(int(ts))
            points[ts]["error_rate"] = round(value, 4)
        for ts, value in cpu:
            points[ts]["ts"] = str(int(ts))
            points[ts]["cpu"] = round(value * 100, 3)
        return [points[key] for key in sorted(points)]
