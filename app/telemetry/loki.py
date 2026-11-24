from __future__ import annotations

import httpx

from app.telemetry.base import TelemetryError, Window


class LokiClient:
    def __init__(
        self,
        base_url: str,
        *,
        timeout: float = 10.0,
        transport: httpx.BaseTransport | None = None,
        limit: int = 200,
    ) -> None:
        self._client = httpx.Client(
            base_url=base_url.rstrip("/"), timeout=timeout, transport=transport
        )
        self._limit = limit

    def query(self, service: str, window: Window) -> list[dict]:
        try:
            response = self._client.get(
                "/loki/api/v1/query_range",
                params={
                    "query": f'{{service="{service}"}}',
                    "start": int(window.start * 1_000_000_000),
                    "end": int(window.end * 1_000_000_000),
                    "limit": self._limit,
                    "direction": "backward",
                },
            )
            response.raise_for_status()
            payload = response.json()
        except Exception as exc:
            raise TelemetryError(f"loki query failed: {exc}") from exc

        entries: list[dict] = []
        for stream in payload.get("data", {}).get("result", []):
            labels = stream.get("stream", {})
            for ts, line in stream.get("values", []):
                level = str(labels.get("level", "INFO")).upper()
                if "error" in line.lower() or "exception" in line.lower():
                    level = "ERROR"
                entries.append({"ts": ts, "level": level, "message": line})
        return entries[-self._limit :]
