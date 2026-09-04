"""Capacity-driven adaptive cache eviction policy.

Selects the lowest-scoring cache objects for eviction until the total
cache usage is at or below the requested target capacity.
"""

from __future__ import annotations

from typing import Mapping

from contracts.schemas import CacheObject


class EvictionPolicy:
    """Deterministic, capacity-driven cache eviction selector.

    Capacity determines how many bytes need to be freed; retention score
    determines which objects are evicted first.
    """

    def select_evictions(
        self,
        scores: dict[str, float],
        objects: dict[str, CacheObject],
        target_capacity_bytes: int,
    ) -> list[str]:
        """Selects cache objects for eviction to satisfy target capacity.

        Args:
            scores: Mapping of cache object key to retention score [0.0, 1.0].
            objects: Mapping of cache object key to CacheObject metadata.
            target_capacity_bytes: Maximum allowed cache capacity in bytes (> 0).

        Returns:
            List of object keys chosen for eviction, ordered by selection.

        Raises:
            ValueError: If target_capacity_bytes is non-numeric, boolean, or <= 0;
                if scores are invalid, boolean, non-numeric, or outside [0.0, 1.0];
                if objects are not CacheObjects; or if keys do not match.
        """
        # 1. Validate target_capacity_bytes
        if isinstance(target_capacity_bytes, bool) or not isinstance(
            target_capacity_bytes, (int, float)
        ):
            raise ValueError(
                "target_capacity_bytes must be numeric, got "
                f"{type(target_capacity_bytes).__name__}"
            )
        if target_capacity_bytes <= 0:
            raise ValueError(
                "target_capacity_bytes must be greater than 0, got "
                f"{target_capacity_bytes}"
            )

        # 2. Validate input mapping types
        if not isinstance(scores, (dict, Mapping)):
            raise ValueError(f"scores must be a mapping, got {type(scores).__name__}")
        if not isinstance(objects, (dict, Mapping)):
            raise ValueError(f"objects must be a mapping, got {type(objects).__name__}")

        # 3. Handle empty inputs
        if not objects and not scores:
            return []

        # 4. Validate key alignment
        missing_scores = [k for k in objects if k not in scores]
        if missing_scores:
            raise ValueError(f"Missing scores for objects: {sorted(missing_scores)}")

        extra_scores = [k for k in scores if k not in objects]
        if extra_scores:
            raise ValueError(
                f"Scores provided for unknown objects: {sorted(extra_scores)}"
            )

        # 5. Validate scores and objects
        for key, score_val in scores.items():
            if isinstance(score_val, bool) or not isinstance(score_val, (int, float)):
                raise ValueError(
                    f"Score for key {key!r} must be numeric, got "
                    f"{type(score_val).__name__}"
                )
            if score_val < 0.0 or score_val > 1.0:
                raise ValueError(
                    f"Score for key {key!r} must be in [0.0, 1.0], got {score_val}"
                )

        for key, obj in objects.items():
            if not isinstance(obj, CacheObject):
                raise ValueError(
                    f"Value for key {key!r} must be a CacheObject, got "
                    f"{type(obj).__name__}"
                )

        # 6. Calculate usage and capacity gap
        current_usage = sum(obj.size_bytes for obj in objects.values())
        if current_usage <= target_capacity_bytes:
            return []

        bytes_to_free = current_usage - target_capacity_bytes

        # 7. Deterministic sorting: ascending score, then ascending key tie-breaker
        sorted_keys = sorted(objects.keys(), key=lambda k: (scores[k], k))

        # 8. Greedily select lowest-scoring candidates until bytes_to_free satisfied
        eviction_keys: list[str] = []
        freed_bytes = 0

        for key in sorted_keys:
            eviction_keys.append(key)
            freed_bytes += objects[key].size_bytes
            if freed_bytes >= bytes_to_free:
                break

        return eviction_keys

    def __call__(
        self,
        scores: dict[str, float],
        objects: dict[str, CacheObject],
        target_capacity_bytes: int,
    ) -> list[str]:
        """Callable interface forwarding to select_evictions()."""
        return self.select_evictions(scores, objects, target_capacity_bytes)
