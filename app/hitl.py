from __future__ import annotations

from typing import TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt


class ApprovalState(TypedDict, total=False):
    action: str
    risk: str
    approved: bool


def propose(state: ApprovalState) -> dict:
    return {"risk": state.get("risk", "high")}


def approve(state: ApprovalState) -> dict:
    """Pause the graph until a human resumes it with True/False."""
    decision = interrupt({"action": state["action"], "risk": state.get("risk", "high")})
    return {"approved": bool(decision)}


def build_approval_graph(checkpointer=None):
    graph = StateGraph(ApprovalState)
    graph.add_node("propose", propose)
    graph.add_node("approve", approve)
    graph.add_edge(START, "propose")
    graph.add_edge("propose", "approve")
    graph.add_edge("approve", END)
    return graph.compile(checkpointer=checkpointer)
