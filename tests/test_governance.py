from __future__ import annotations

import pytest

from app.governance.budget import Budget, BudgetExceeded, BudgetTracker
from app.governance.loop_guard import LoopGuard


def test_step_budget_exceeded() -> None:
    tracker = BudgetTracker(Budget(max_steps=1))
    tracker.tick_step()
    with pytest.raises(BudgetExceeded):
        tracker.tick_step()


def test_tool_budget_exceeded() -> None:
    tracker = BudgetTracker(Budget(max_tool_calls=1))
    tracker.tick_tool()
    with pytest.raises(BudgetExceeded):
        tracker.tick_tool()


def test_loop_guard_detects_no_progress() -> None:
    guard = LoopGuard(window=2)
    assert guard.observe({"a"}) is False
    assert guard.observe({"a"}) is False
    assert guard.observe({"a"}) is True


def test_loop_guard_resets_on_new_evidence() -> None:
    guard = LoopGuard(window=2)
    guard.observe({"a"})
    guard.observe({"a"})
    assert guard.observe({"a", "b"}) is False
    assert guard.stale_rounds == 0
