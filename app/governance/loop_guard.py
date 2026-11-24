from __future__ import annotations

from collections import deque


class LoopGuard:
    """Detect rounds that produce no new evidence."""

    def __init__(self, window: int = 3) -> None:
        self.window = window
        self._seen: set[str] = set()
        self._stale_rounds = 0
        self._history: deque[int] = deque(maxlen=window)

    def observe(self, evidence_ids: set[str]) -> bool:
        """Return True when the run should stop (no progress for `window` rounds)."""
        new_ids = evidence_ids - self._seen
        self._seen.update(evidence_ids)
        if new_ids:
            self._stale_rounds = 0
        else:
            self._stale_rounds += 1
        self._history.append(len(new_ids))
        return self._stale_rounds >= self.window

    @property
    def stale_rounds(self) -> int:
        return self._stale_rounds
