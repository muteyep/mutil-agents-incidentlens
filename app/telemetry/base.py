from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


class TelemetryError(RuntimeError):
    """Any telemetry backend failure."""


@dataclass(frozen=True)
class Window:
    start: float
    end: float

    @classmethod
    def last_minutes(cls, minutes: int) -> Window:
        import time

        end = time.time()
        return cls(start=end - minutes * 60, end=end)


class MetricsSource(Protocol):
    def query(self, service: str, window: Window) -> list[dict]: ...


class LogsSource(Protocol):
    def query(self, service: str, window: Window) -> list[dict]: ...


class TracesSource(Protocol):
    def query(self, service: str, window: Window) -> list[dict]: ...
