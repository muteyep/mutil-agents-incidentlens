from __future__ import annotations

from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command

from app.hitl import build_approval_graph


def test_approval_pauses_and_resumes() -> None:
    graph = build_approval_graph(MemorySaver())
    config = {"configurable": {"thread_id": "approval-1"}}

    paused = graph.invoke(
        {"action": "restart payment", "risk": "high", "approved": False}, config=config
    )
    assert "__interrupt__" in paused

    resumed = graph.invoke(Command(resume=True), config=config)
    assert resumed["approved"] is True


def test_approval_can_be_rejected() -> None:
    graph = build_approval_graph(MemorySaver())
    config = {"configurable": {"thread_id": "approval-2"}}
    graph.invoke({"action": "scale redis", "risk": "medium", "approved": False}, config=config)
    resumed = graph.invoke(Command(resume=False), config=config)
    assert resumed["approved"] is False
