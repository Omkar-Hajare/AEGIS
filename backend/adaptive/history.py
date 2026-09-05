"""In-memory bounded decision history for the Adaptive Cache System.

Thread-safe, synchronous, and bounded to the most recent decisions (default 50).
Always returns newest decisions first.
"""

from __future__ import annotations

import threading
from collections import deque

from contracts.schemas import Decision


class DecisionHistory:
    """Bounded, thread-safe in-memory store for recent adaptive decisions."""

    def __init__(self, maxlen: int = 50) -> None:
        self._maxlen = maxlen
        self._decisions: deque[Decision] = deque(maxlen=maxlen)
        self._lock = threading.Lock()

    @property
    def maxlen(self) -> int:
        return self._maxlen

    def record(self, decision: Decision) -> None:
        """Record a successful Decision. Newest decisions are placed at index 0."""
        with self._lock:
            self._decisions.appendleft(decision)

    def get_recent(self, limit: int | None = None) -> list[Decision]:
        """Return decisions newest-first, optionally capped by limit."""
        with self._lock:
            items = list(self._decisions)
            if limit is not None and limit > 0:
                return items[:limit]
            return items

    def clear(self) -> None:
        """Clear all recorded decisions."""
        with self._lock:
            self._decisions.clear()

    def __len__(self) -> int:
        with self._lock:
            return len(self._decisions)


runtime_decision_history = DecisionHistory(maxlen=50)

__all__ = ["DecisionHistory", "runtime_decision_history"]
