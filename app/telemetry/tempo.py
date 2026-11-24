from __future__ import annotations

import httpx

from app.telemetry.base import TelemetryError, Window


class TempoClient:
    """Tempo search API client.

    Tempo's search response already contains `durationMs` and the root
    service, so one request is enough for a coarse per-service span summary.
    """

    def __init__(
        self,
        base_url: str,
        *,
        timeout: float = 10.0,
        transport: httpx.BaseTransport | None = None,
        limit: int = 40,
    ) -> None:
        self._client = httpx.Client(
            base_url=base_url.rstrip("/"), timeout=timeout, transport=transport
        )
        self._limit = limit

    def query(self, service: str, window: Window) -> list[dict]:
        try:
            response = self._client.get(
                "/api/search",
                params={
                    "tags": f"service.name={service}",
                    "start": int(window.start),
                    "end": int(window.end),
                    "limit": self._limit,
                },
            )
            response.raise_for_status()
            payload = response.json()
        except Exception as exc:
            raise TelemetryError(f"tempo query failed: {exc}") from exc

        durations = [
            float(trace.get("durationMs", 0))
            for trace in payload.get("traces", [])
            if float(trace.get("durationMs", 0)) > 0
        ]
        if not durations:
            return []
        durations.sort()
        p99 = durations[min(len(durations) - 1, int(len(durations) * 0.99))]
        return [{"span": service, "p99_ms": round(p99, 3), "error_rate": 0.0}]
