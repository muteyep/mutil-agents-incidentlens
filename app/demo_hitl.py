from __future__ import annotations

from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command

from app.hitl import build_approval_graph


def main() -> None:
    graph = build_approval_graph(MemorySaver())
    config = {"configurable": {"thread_id": "demo-approval"}}

    paused = graph.invoke(
        {"action": "restart payment", "risk": "high", "approved": False}, config=config
    )
    print("paused:", paused)

    resumed = graph.invoke(Command(resume=True), config=config)
    print("resumed:", resumed)


if __name__ == "__main__":
    main()
