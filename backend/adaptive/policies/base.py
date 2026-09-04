"""Base class for baseline cache eviction policies."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Mapping

from contracts.schemas.cache import CacheObject


class PolicyValidationError(ValueError, TypeError):
    """Raised when an argument passed to an eviction policy is invalid."""


class BaseEvictionPolicy(ABC):
    """Abstract base class for baseline cache eviction policies.

    Provides common input validation, capacity tracking, and eviction selection loop.
    Subclasses only need to implement `_rank_keys`.
    """

    def select_evictions(
        self,
        objects: Mapping[str, CacheObject],
        target_capacity_bytes: int,
    ) -> list[str]:
        """Select cache object keys to evict until target capacity is reached.

        Args:
            objects: Mapping of cache key to CacheObject instance.
            target_capacity_bytes: Desired maximum cache capacity in bytes (> 0).

        Returns:
            List of object keys selected for eviction in policy priority order.

        Raises:
            ValueError: If target_capacity_bytes is invalid or key mismatch occurs.
            TypeError: If objects or items have invalid types.
        """
        self._validate_inputs(objects, target_capacity_bytes)

        if not objects:
            return []

        current_usage = sum(obj.size_bytes for obj in objects.values())
        if current_usage <= target_capacity_bytes:
            return []

        bytes_to_free = current_usage - target_capacity_bytes
        ranked_keys = self._rank_keys(objects)

        evicted: list[str] = []
        freed_bytes = 0
        for key in ranked_keys:
            evicted.append(key)
            freed_bytes += objects[key].size_bytes
            if freed_bytes >= bytes_to_free:
                break

        return evicted

    def __call__(
        self,
        objects: Mapping[str, CacheObject],
        target_capacity_bytes: int,
    ) -> list[str]:
        """Allow calling the policy instance directly."""
        return self.select_evictions(objects, target_capacity_bytes)

    @abstractmethod
    def _rank_keys(self, objects: Mapping[str, CacheObject]) -> list[str]:
        """Rank cache object keys in eviction order (first to evict first)."""
        ...

    @staticmethod
    def _validate_inputs(
        objects: Mapping[str, CacheObject],
        target_capacity_bytes: int,
    ) -> None:
        """Validate input arguments strictly."""
        if isinstance(target_capacity_bytes, bool) or not isinstance(
            target_capacity_bytes, int
        ):
            raise PolicyValidationError(
                "target_capacity_bytes must be an integer, "
                f"got {type(target_capacity_bytes).__name__}"
            )
        if target_capacity_bytes <= 0:
            raise PolicyValidationError(
                "target_capacity_bytes must be greater than 0, "
                f"got {target_capacity_bytes}"
            )

        if not isinstance(objects, (dict, Mapping)):
            raise PolicyValidationError(
                f"objects must be a mapping, got {type(objects).__name__}"
            )

        for key, obj in objects.items():
            if not isinstance(key, str):
                raise PolicyValidationError(
                    f"Object key must be a string, got {type(key).__name__}"
                )
            if not isinstance(obj, CacheObject):
                raise PolicyValidationError(
                    f"Value for key {key!r} must be a CacheObject, "
                    f"got {type(obj).__name__}"
                )
            if key != obj.key:
                raise PolicyValidationError(
                    f"Mapping key {key!r} does not match CacheObject.key {obj.key!r}"
                )
