"""Least Recently Used (LRU) baseline cache eviction policy."""

from __future__ import annotations

from collections.abc import Mapping

from contracts.schemas.cache import CacheObject

from .base import BaseEvictionPolicy


class LRUPolicy(BaseEvictionPolicy):
    """Least Recently Used (LRU) cache eviction policy.

    Evicts objects with the oldest last_accessed timestamp first.
    Ties are broken deterministically by ascending object key.
    """

    def _rank_keys(self, objects: Mapping[str, CacheObject]) -> list[str]:
        """Sort object keys by last_accessed ascending, then key ascending."""
        return sorted(objects.keys(), key=lambda k: (objects[k].last_accessed, k))
