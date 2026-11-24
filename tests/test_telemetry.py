from __future__ import annotations

import httpx

from app.telemetry.base import Window
from app.telemetry.live import build_live_case
from app.telemetry.loki import LokiClient
from app.telemetry.prometheus import PrometheusClient
from app.telemetry.tempo import TempoClient


def _prom_handler(request: httpx.Request) -> httpx.Response:
    query = request.url.params.get("query", "")
    if "histogram_quantile" in query:
        values = [[1700000000, "0.5"]]
    elif "5.." in query:
        values = [[1700000000, "0.2"]]
    else:
        values = [[1700000000, "0.4"]]
    return httpx.Response(200, json={"data": {"result": [{"values": values}]}})


def test_prometheus_client_normalizes_metrics() -> None:
    client = PrometheusClient("http://prom", transport=httpx.MockTransport(_prom_handler))
    points = client.query("checkout", Window(1700000000, 1700000060))
    assert points == [
        {"ts": "1700000000", "p99_ms": 500.0, "error_rate": 0.2, "cpu": 40.0, "mem": 0.0}
    ]


def test_loki_client_parses_streams() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "data": {
                    "result": [
                        {
                            "stream": {"level": "info"},
                            "values": [["1700000000000000000", "checkout error: timeout"]],
                        }
                    ]
                }
            },
        )

    client = LokiClient("http://loki", transport=httpx.MockTransport(handler))
    logs = client.query("checkout", Window(1700000000, 1700000060))
    assert logs[0]["level"] == "ERROR"
    assert "timeout" in logs[0]["message"]


def test_tempo_client_summarizes_durations() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"traces": [{"durationMs": 120}, {"durationMs": 300}, {"durationMs": 80}]},
        )

    client = TempoClient("http://tempo", transport=httpx.MockTransport(handler))
    spans = client.query("checkout", Window(1700000000, 1700000060))
    assert spans[0]["span"] == "checkout"
    assert spans[0]["p99_ms"] == 300.0


class _FakeMetrics:
    def query(self, service: str, window: Window) -> list[dict]:
        return [{"ts": "1", "p99_ms": 100, "error_rate": 0.0, "cpu": 10, "mem": 0}]


class _FakeLogs:
    def query(self, service: str, window: Window) -> list[dict]:
        return [{"ts": "1", "level": "ERROR", "message": "boom"}]


class _FakeTraces:
    def query(self, service: str, window: Window) -> list[dict]:
        return [{"span": service, "p99_ms": 100, "error_rate": 0.1}]


def test_build_live_case_shape() -> None:
    case = build_live_case(
        "checkout",
        ["checkout", "payment"],
        prometheus=_FakeMetrics(),
        loki=_FakeLogs(),
        tempo=_FakeTraces(),
    )
    assert case["case_id"] == "live_checkout"
    assert set(case["services"]) == {"checkout", "payment"}
    assert case["services"]["payment"]["logs"][0]["level"] == "ERROR"
    assert case["ground_truth"]["root_cause_service"] == "unknown"
