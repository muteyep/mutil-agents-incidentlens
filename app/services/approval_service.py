from __future__ import annotations

import logging
import uuid

from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command

from app.hitl import build_approval_graph

logger = logging.getLogger(__name__)


class ApprovalService:
    """In-memory HITL approval graph for the HTTP API.

    Production would swap MemorySaver for SqliteSaver/Postgres and add auth.
    """

    def __init__(self) -> None:
        self._graph = build_approval_graph(MemorySaver())
        from app.persistence.repository import ApprovalRepository

        self._repo = ApprovalRepository()

    def start(self, action: str, risk: str = "high") -> dict:
        thread_id = str(uuid.uuid4())
        result = self._graph.invoke(
            {"action": action, "risk": risk, "approved": False},
            config={"configurable": {"thread_id": thread_id}},
        )
        interrupts = result.get("__interrupt__") or []
        payload = interrupts[0].value if interrupts else None
        try:
            self._repo.save_start(thread_id, action, risk)
        except Exception as exc:  # noqa: BLE001 - HITL must still work without storage
            logger.warning("failed to persist approval start: %s", exc)
        return {"thread_id": thread_id, "status": "pending", "payload": payload}

    def resume(self, thread_id: str, approved: bool) -> dict:
        result = self._graph.invoke(
            Command(resume=approved),
            config={"configurable": {"thread_id": thread_id}},
        )
        decision = bool(result.get("approved", False))
        try:
            self._repo.finish(thread_id, decision)
        except Exception as exc:  # noqa: BLE001
            logger.warning("failed to persist approval finish: %s", exc)
        return {
            "thread_id": thread_id,
            "status": "approved" if decision else "rejected",
            "approved": decision,
        }
