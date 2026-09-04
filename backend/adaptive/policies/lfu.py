"""Least Frequently Used (LFU) baseline cache eviction policy."""

from __future__ import annotations

from collections.abc import Mapping

from contracts.schemas.cache import CacheObject

from .base import BaseEvictionPolicy


class LFUPolicy(BaseEvictionPolicy):
    """Least Frequently Used (LFU) cache eviction policy.

    Evicts objects with the lowest access_count first.
    Ties are broken deterministically by ascending object key.
    """

    def _rank_keys(self, objects: Mapping[str, CacheObject]) -> list[str]:
        """Sort object keys by access_count ascending, then key ascending."""
        return sorted(objects.keys(), key=lambda k: (objects[k].access_count, k))
