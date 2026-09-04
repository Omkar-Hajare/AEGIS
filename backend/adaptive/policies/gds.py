"""Greedy-Dual-Size (GDS) inspired cost/size baseline cache eviction policy."""

from __future__ import annotations

from collections.abc import Mapping

from contracts.schemas.cache import CacheObject

from .base import BaseEvictionPolicy


class GDSPolicy(BaseEvictionPolicy):
    """Stateless Greedy-Dual-Size (GDS) inspired cache eviction policy.

    Evicts objects with the lowest retrieval-cost-per-byte
    (retrieval_cost_ms / size_bytes) priority first. Zero-size objects receive
    infinite priority so they are never preferred for eviction when positive-sized
    candidates exist. Ties are broken deterministically by ascending object key.
    """

    @staticmethod
    def _calculate_priority(obj: CacheObject) -> float:
        """Calculate retrieval cost per byte priority.

        Zero-size objects receive positive infinity to prevent division by zero
        and reflect that evicting them frees no capacity.
        """
        if obj.size_bytes == 0:
            return float("inf")
        return float(obj.retrieval_cost_ms) / float(obj.size_bytes)

    def _rank_keys(self, objects: Mapping[str, CacheObject]) -> list[str]:
        """Sort object keys by GDS priority ascending, then key ascending."""
        return sorted(
            objects.keys(),
            key=lambda k: (self._calculate_priority(objects[k]), k),
        )
