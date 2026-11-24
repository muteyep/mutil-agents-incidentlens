from __future__ import annotations

import sqlite3
from pathlib import Path

from langgraph.checkpoint.sqlite import SqliteSaver

from app.graph import build_graph, run_case
from app.providers.base import LLMProvider

_CHECKPOINT_CONN: sqlite3.Connection | None = None


def get_checkpointer(path: str | Path = "data/checkpoints.sqlite"):
    """Reuse one SQLite connection so the saver survives across calls."""
    global _CHECKPOINT_CONN
    if _CHECKPOINT_CONN is None:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        _CHECKPOINT_CONN = sqlite3.connect(str(path), check_same_thread=False)
    return SqliteSaver(_CHECKPOINT_CONN)


def run_persistent(
    case_id: str,
    *,
    mode: str = "multi",
    llm: LLMProvider | None = None,
    thread_id: str | None = None,
):
    """Run with a durable checkpoint. Re-invoking the same thread resumes it."""
    graph = build_graph(mode, checkpointer=get_checkpointer(), llm=llm)
    config = {"configurable": {"thread_id": thread_id or case_id}}
    return graph.invoke({"case_id": case_id, "evidences": [], "step": 0}, config=config)


def resume_persistent(thread_id: str, value):
    graph = build_graph("multi", checkpointer=get_checkpointer())
    from langgraph.types import Command

    return graph.invoke(Command(resume=value), config={"configurable": {"thread_id": thread_id}})


__all__ = ["get_checkpointer", "resume_persistent", "run_case", "run_persistent"]
