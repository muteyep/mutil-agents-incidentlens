from __future__ import annotations

from abc import ABC, abstractmethod

from app.state import CaseState


class BaseAgent(ABC):
    """Every agent receives the shared case state and returns a partial update."""

    name: str

    @abstractmethod
    def run(self, state: CaseState) -> dict:
        """Return only the keys this agent owns."""
