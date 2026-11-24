from __future__ import annotations

import pytest

from app.registry import ToolRegistry


def test_register_and_call() -> None:
    registry = ToolRegistry()
    registry.register("add", lambda a, b: a + b)
    assert registry.call("add", a=1, b=2) == 3


def test_duplicate_registration_rejected() -> None:
    registry = ToolRegistry()
    registry.register("x", lambda: 1)
    with pytest.raises(ValueError):
        registry.register("x", lambda: 2)


def test_unknown_tool_rejected() -> None:
    registry = ToolRegistry()
    with pytest.raises(KeyError):
        registry.call("nope")


def test_names_sorted() -> None:
    registry = ToolRegistry()
    registry.register("b", lambda: 1)
    registry.register("a", lambda: 1)
    assert registry.names() == ["a", "b"]
