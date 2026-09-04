"""Feature extraction engine for the Adaptive Cache System.

Converts CacheObject metadata and observation window context into
pure, deterministic, normalized adaptive features in the range [0.0, 1.0].
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from datetime import datetime, timezone

from contracts.schemas import CacheObject


def _clamp(value: float, min_val: float = 0.0, max_val: float = 1.0) -> float:
    """Clamps a floating-point value to the range [min_val, max_val]."""
    return max(min_val, min(max_val, value))


def _min_max_normalize(values: Sequence[float]) -> list[float]:
    """Min-max normalizes a sequence of numeric values into [0.0, 1.0].

    Formula: (value - min_value) / (max_value - min_value)
    If min_value == max_value (all equal or single object), returns 0.5.
    """
    if not values:
        return []

    min_val = min(values)
    max_val = max(values)

    if (
        math.isclose(min_val, max_val, rel_tol=1e-9, abs_tol=1e-12)
        or min_val == max_val
    ):
        return [0.5] * len(values)

    denominator = max_val - min_val
    return [_clamp((v - min_val) / denominator, 0.0, 1.0) for v in values]


class FeatureExtractor:
    """Pure, deterministic feature extractor for adaptive caching.

    Extracts five normalized features for each CacheObject:
    - frequency: access frequency normalized across the observation set
    - recency: how recently an object was accessed relative to the window
    - retrieval_cost: backend fetch/recompute cost normalized across the set
    - size: memory footprint pressure normalized across the set
    - popularity_trend: directional shift in access count vs. previous window
    """

    @staticmethod
    def extract(
        objects: list[CacheObject] | None = None,
        now: datetime | None = None,
        window_seconds: float | None = None,
        previous_access_counts: dict[str, int] | None = None,
        *,
        cache_objects: list[CacheObject] | None = None,
    ) -> dict[str, dict[str, float]]:
        """Extracts normalized features for a collection of CacheObjects.

        Args:
            objects: List of CacheObject instances to extract features for.
            now: Current timestamp (timezone-aware datetime).
            window_seconds: Observation window duration in seconds (> 0).
            previous_access_counts: Optional mapping of object key to access
                count in the preceding observation window.
            cache_objects: Alternative keyword alias for `objects`.

        Returns:
            Dictionary mapping cache key -> dict of feature name -> float in [0, 1].

        Raises:
            ValueError: If window_seconds is <= 0 or now is None.
        """
        if window_seconds is None or window_seconds <= 0.0:
            raise ValueError(f"window_seconds must be > 0, got {window_seconds}")

        if now is None:
            raise ValueError("now timestamp must be provided as a datetime")

        target_objects = objects if objects is not None else cache_objects
        if not target_objects:
            return {}

        now_dt = now if now.tzinfo is not None else now.replace(tzinfo=timezone.utc)

        # 1. Frequency: access_count / window_seconds, min-max normalized
        raw_frequencies = [obj.access_count / window_seconds for obj in target_objects]
        norm_frequencies = _min_max_normalize(raw_frequencies)

        # 2. Retrieval Cost: retrieval_cost_ms, min-max normalized
        raw_costs = [float(obj.retrieval_cost_ms) for obj in target_objects]
        norm_costs = _min_max_normalize(raw_costs)

        # 3. Size: size_bytes, min-max normalized
        raw_sizes = [float(obj.size_bytes) for obj in target_objects]
        norm_sizes = _min_max_normalize(raw_sizes)

        # 4 & 5. Recency and Popularity Trend (computed per object)
        result: dict[str, dict[str, float]] = {}

        for idx, obj in enumerate(target_objects):
            # Recency formula: max(0, 1 - age_seconds / window_seconds)
            last_accessed_dt = (
                obj.last_accessed
                if obj.last_accessed.tzinfo is not None
                else obj.last_accessed.replace(tzinfo=timezone.utc)
            )
            age_seconds = max(0.0, (now_dt - last_accessed_dt).total_seconds())
            recency = _clamp(max(0.0, 1.0 - (age_seconds / window_seconds)), 0.0, 1.0)

            # Popularity Trend:
            # raw_change = (current_count - prev_count) / max(prev_count, 1)
            # trend_score = clamp(0.5 + 0.5 * tanh(raw_change), 0.0, 1.0)
            if previous_access_counts is None or obj.key not in previous_access_counts:
                popularity_trend = 0.5
            else:
                prev_count = previous_access_counts[obj.key]
                curr_count = obj.access_count
                raw_change = (curr_count - prev_count) / max(prev_count, 1)
                popularity_trend = _clamp(0.5 + 0.5 * math.tanh(raw_change), 0.0, 1.0)

            result[obj.key] = {
                "frequency": norm_frequencies[idx],
                "recency": recency,
                "retrieval_cost": norm_costs[idx],
                "size": norm_sizes[idx],
                "popularity_trend": popularity_trend,
            }

        return result
