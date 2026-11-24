from __future__ import annotations

import time
from dataclasses import dataclass


class BudgetExceeded(RuntimeError):
    """Raised when a run exceeds any of its budgets."""


@dataclass(frozen=True)
class Budget:
    max_steps: int = 12
    max_tool_calls: int = 60
    max_seconds: float = 120.0


class BudgetTracker:
    def __init__(self, budget: Budget | None = None) -> None:
        self.budget = budget or Budget()
        self.steps = 0
        self.tool_calls = 0
        self._started = time.monotonic()

    def tick_step(self) -> None:
        self.steps += 1
        self.check()

    def tick_tool(self) -> None:
        self.tool_calls += 1
        self.check()

    def elapsed(self) -> float:
        return time.monotonic() - self._started

    def check(self) -> None:
        if self.steps > self.budget.max_steps:
            raise BudgetExceeded(f"step budget exceeded: {self.steps}/{self.budget.max_steps}")
        if self.tool_calls > self.budget.max_tool_calls:
            raise BudgetExceeded(
                f"tool budget exceeded: {self.tool_calls}/{self.budget.max_tool_calls}"
            )
        if self.elapsed() > self.budget.max_seconds:
            raise BudgetExceeded(f"time budget exceeded: {self.elapsed():.1f}s")
