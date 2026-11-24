from __future__ import annotations

import argparse
import json
import os

from app.graph import run_case
from app.telemetry.base import Window
from app.telemetry.loki import LokiClient
from app.telemetry.prometheus import PrometheusClient
from app.telemetry.tempo import TempoClient
from app.tools.mock_sources import register_case, unregister_case


def build_live_case(
    service: str,
    services: list[str],
    *,
    window_minutes: int = 15,
    prometheus: PrometheusClient,
    loki: LokiClient,
    tempo: TempoClient,
    topology: dict[str, list[str]] | None = None,
) -> dict:
    """Query live telemetry and shape it exactly like a JSON case."""
    window = Window.last_minutes(window_minutes)
    services = sorted(set(services) | {service})
    payload: dict[str, dict] = {}
    for name in services:
        payload[name] = {
            "metrics": prometheus.query(name, window),
            "logs": loki.query(name, window),
            "traces": tempo.query(name, window),
        }
    return {
        "case_id": f"live_{service}",
        "alert": {
            "title": f"{service} live anomaly",
            "service": service,
            "severity": "P1",
            "started_at": str(int(window.start)),
        },
        "topology": topology or {service: []},
        "ground_truth": {"root_cause_service": "unknown", "fault_type": "unknown"},
        "services": payload,
    }


def clients_from_env() -> tuple[PrometheusClient, LokiClient, TempoClient]:
    prom = os.getenv("PROMETHEUS_URL", "")
    loki = os.getenv("LOKI_URL", "")
    tempo = os.getenv("TEMPO_URL", "")
    missing = [
        name
        for name, value in (("PROMETHEUS_URL", prom), ("LOKI_URL", loki), ("TEMPO_URL", tempo))
        if not value
    ]
    if missing:
        raise SystemExit(f"missing env: {', '.join(missing)}")
    return PrometheusClient(prom), LokiClient(loki), TempoClient(tempo)


def run_live(service: str, services: list[str], window_minutes: int = 15) -> dict:
    prom, loki, tempo = clients_from_env()
    case = build_live_case(
        service,
        services,
        window_minutes=window_minutes,
        prometheus=prom,
        loki=loki,
        tempo=tempo,
    )
    register_case(case)
    try:
        return run_case(case["case_id"], mode="multi")
    finally:
        unregister_case(case["case_id"])


def main() -> None:
    parser = argparse.ArgumentParser(description="Run RCA against live telemetry")
    parser.add_argument("--service", required=True)
    parser.add_argument("--services", default="", help="comma-separated services")
    parser.add_argument("--window", default=15, type=int, help="minutes")
    args = parser.parse_args()
    services = [item.strip() for item in args.services.split(",") if item.strip()]
    result = run_live(args.service, services, args.window)
    print(result["report"])
    print(json.dumps(result.get("critique", ""), ensure_ascii=False))


if __name__ == "__main__":
    main()
