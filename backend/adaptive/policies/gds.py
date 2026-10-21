"""Greedy-Dual-Size (GDS) cost/size baseline cache eviction policy.

Implements standard GreedyDual-Size (Cao & Irani 1997) with a global inflation clock L.
When an object is admitted or hit, its priority is updated to H = L + cost / size.
During eviction, the candidate with the lowest H is evicted, and L advances to H.
"""

from __future__ import annotations

import math
from collections.abc import Mapping

from contracts.schemas.cache import CacheObject

from .base import BaseEvictionPolicy


class GDSPolicy(BaseEvictionPolicy):
    """Greedy-Dual-Size (GDS) cache eviction policy with dynamic inflation clock.

    Maintains a global inflation clock ``L`` representing the maximum cost/size
    potential evicted so far. Each cached object ``p`` is tracked with an
    effective priority:

        H(p) = L + (retrieval_cost_ms / size_bytes)

    - On cache insertion / hit: ``H(p)`` is refreshed to ``L + cost / size``.
    - On cache eviction: the object with minimum ``H`` is chosen, and ``L``
      advances to that minimum priority: ``L = H(evicted)``.
    - Zero-size objects receive positive infinity to prevent division by zero
      and reflect that evicting them frees no capacity.
    - Equal-priority ties are broken deterministically by oldest access
      recency, then ascending object key.
    """

    def __init__(self, initial_L: float = 0.0) -> None:
        """Initialize GDSPolicy with inflation clock at initial_L (default 0.0)."""
        self._clock_L: float = float(initial_L)
        self._priorities: dict[str, float] = {}

    @property
    def clock_L(self) -> float:
        """Current global inflation clock L value."""
        return self._clock_L

    @property
    def priorities(self) -> dict[str, float]:
        """Immutable snapshot of currently tracked object priorities."""
        return dict(self._priorities)

    @staticmethod
    def _calculate_priority(obj: CacheObject, L: float = 0.0) -> float:
        """Calculate retrieval cost per byte priority H = L + cost / size.

        Zero-size objects receive positive infinity to prevent division by zero
        and reflect that evicting them frees no capacity.
        """
        if obj.size_bytes == 0:
            return float("inf")
        ratio = float(obj.retrieval_cost_ms) / float(obj.size_bytes)
        return float(L) + ratio

    def on_hit(self, key: str, obj: CacheObject) -> None:
        """Update object priority upon cache hit: H(key) = L + cost / size."""
        self._priorities[key] = self._calculate_priority(obj, self._clock_L)

    def on_insert(self, key: str, obj: CacheObject) -> None:
        """Assign object priority upon cache admission: H(key) = L + cost / size."""
        self._priorities[key] = self._calculate_priority(obj, self._clock_L)

    def _sync_priorities(self, objects: Mapping[str, CacheObject]) -> None:
        """Synchronize tracked priorities with resident cache objects."""
        # Remove objects no longer in cache
        self._priorities = {k: v for k, v in self._priorities.items() if k in objects}
        # Initialize any new objects not yet tracked
        for k, obj in objects.items():
            if k not in self._priorities:
                self._priorities[k] = self._calculate_priority(obj, self._clock_L)

    def _rank_keys(self, objects: Mapping[str, CacheObject]) -> list[str]:
        """Sort object keys by GDS priority ascending, then last_accessed, then key."""
        self._sync_priorities(objects)
        return sorted(
            objects.keys(),
            key=lambda k: (
                self._priorities.get(k, self._calculate_priority(objects[k], self._clock_L)),
                objects[k].last_accessed,
                k,
            ),
        )

    def select_evictions(
        self,
        objects: Mapping[str, CacheObject],
        target_capacity_bytes: int,
    ) -> list[str]:
        """Select cache object keys to evict until target capacity is reached.

        Advances the inflation clock L to the evicted object's priority H.
        """
        self._validate_inputs(objects, target_capacity_bytes)

        if not objects:
            return []

        current_usage = sum(obj.size_bytes for obj in objects.values())
        if current_usage <= target_capacity_bytes:
            return []

        bytes_to_free = current_usage - target_capacity_bytes
        self._sync_priorities(objects)

        active_objects = dict(objects)
        evicted: list[str] = []
        freed_bytes = 0

        while freed_bytes < bytes_to_free and active_objects:
            # Select candidate with minimum H(p).
            # Tie-breaker: oldest last_accessed first, then ascending key for strict determinism.
            best_key = min(
                active_objects.keys(),
                key=lambda k: (
                    self._priorities[k],
                    active_objects[k].last_accessed,
                    k,
                ),
            )
            evicted_h = self._priorities[best_key]

            # Advance inflation clock L to the evicted object's priority (if finite)
            if math.isfinite(evicted_h):
                self._clock_L = max(self._clock_L, evicted_h)

            evicted.append(best_key)
            freed_bytes += active_objects[best_key].size_bytes
            del active_objects[best_key]

        return evicted

    def reset(self) -> None:
        """Reset inflation clock L to 0.0 and clear object priorities."""
        self._clock_L = 0.0
        self._priorities.clear()
