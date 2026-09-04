"""Capacity-driven adaptive cache eviction policy with economic value density.

Selects cache objects for eviction by evaluating their dynamic retention value
per unit of cache memory (value density), taking into account memory pressure,
object size, retrieval cost, and runtime backend latency.
"""

from __future__ import annotations

import math
from collections.abc import Mapping

from backend.cost.model import CostModel
from contracts.schemas import CacheObject
from contracts.schemas.system import SystemState
from contracts.schemas.workload import WorkloadState


def _clamp(val: float, low: float = 0.0, high: float = 1.0) -> float:
    """Clamp a floating point value to [low, high]."""
    return max(low, min(high, val))


class EvictionPolicy:
    """Deterministic, economic-aware adaptive cache eviction selector.

    Capacity determines how many bytes need to be freed; economic value density
    determines which objects are evicted first. Objects providing low retention
    value per byte of memory under current system pressure are evicted first,
    while objects that are expensive to regenerate or highly valuable are protected.
    """

    def __init__(self, cost_model: CostModel | None = None) -> None:
        """Initialize EvictionPolicy with an optional CostModel."""
        self.cost_model = cost_model or CostModel()
        self.last_value_densities: dict[str, float] | None = None
        self.last_retention_values: dict[str, float] | None = None

    def select_evictions(
        self,
        scores: dict[str, float],
        objects: dict[str, CacheObject],
        target_capacity_bytes: int,
        workload: WorkloadState | None = None,
        system: SystemState | None = None,
        cost_model: CostModel | None = None,
    ) -> list[str]:
        """Selects cache objects for eviction to satisfy target capacity.

        Evaluates candidate objects by economic value density:
            value_density = retention_value / (effective_size ^ alpha)
        where:
        - retention_value combines the dynamic multi-factor utility score with
          a retrieval cost protection factor scaled by backend latency.
        - alpha scales with current memory pressure so large objects require
          stronger retention value to survive when cache memory is scarce.

        Args:
            scores: Mapping of cache object key to retention score [0.0, 1.0].
            objects: Mapping of cache object key to CacheObject metadata.
            target_capacity_bytes: Maximum allowed cache capacity in bytes (> 0).
            workload: Optional observed WorkloadState telemetry snapshot.
            system: Optional observed SystemState capacity snapshot.
            cost_model: Optional explicit CostModel override.

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
            raise ValueError(  # noqa: TRY004
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
            raise ValueError(  # noqa: TRY004
                f"scores must be a mapping, got {type(scores).__name__}"
            )
        if not isinstance(objects, (dict, Mapping)):
            raise ValueError(  # noqa: TRY004
                f"objects must be a mapping, got {type(objects).__name__}"
            )

        # 3. Handle empty inputs
        if not objects and not scores:
            self.last_value_densities = None
            self.last_retention_values = None
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
                raise ValueError(  # noqa: TRY004
                    f"Score for key {key!r} must be numeric, got "
                    f"{type(score_val).__name__}"
                )
            if score_val < 0.0 or score_val > 1.0:
                raise ValueError(
                    f"Score for key {key!r} must be in [0.0, 1.0], got {score_val}"
                )

        for key, obj in objects.items():
            if not isinstance(obj, CacheObject):
                raise ValueError(  # noqa: TRY004
                    f"Value for key {key!r} must be a CacheObject, got "
                    f"{type(obj).__name__}"
                )

        # 6. Calculate usage and capacity gap
        current_usage = sum(obj.size_bytes for obj in objects.values())
        if current_usage <= target_capacity_bytes:
            self.last_value_densities = None
            self.last_retention_values = None
            return []

        bytes_to_free = current_usage - target_capacity_bytes

        # 7. Derive economic parameters and value density
        model = cost_model or self.cost_model

        # Memory pressure determines size sensitivity exponent alpha
        if (
            system is not None
            and system.cache_capacity_bytes > 0
            and math.isfinite(system.cache_usage_bytes)
        ):
            memory_pressure = _clamp(
                float(system.cache_usage_bytes) / float(system.cache_capacity_bytes),
                0.0,
                1.0,
            )
        else:
            memory_pressure = _clamp(
                float(bytes_to_free) / float(max(1, current_usage)),
                0.0,
                1.0,
            )

        # Size penalty exponent alpha scales continuously with memory pressure [0.08, 0.38].
        # In conjunction with the DynamicWeightModel size penalty in the utility score,
        # keeping alpha in [0.08, 0.38] prevents large high-utility objects from being
        # double-penalized to the point of starving against nearly useless tiny objects,
        # while ensuring that size becomes substantially more influential under high memory pressure.
        alpha = _clamp(0.08 + 0.30 * memory_pressure, 0.05, 0.40)

        # Latency pressure scales retrieval-cost retention protection
        if workload is not None and math.isfinite(workload.backend_latency_ms):
            lat = max(0.0, float(workload.backend_latency_ms))
            latency_pressure = lat / (lat + 50.0)
        else:
            latency_pressure = 0.5

        # Normalize retrieval costs across active candidate set
        norm_costs = model.normalize_retrieval_costs(objects)

        # Compute retention value and value density for each candidate
        densities: dict[str, float] = {}
        retention_values: dict[str, float] = {}

        for key, obj in objects.items():
            score = float(scores[key])
            c_norm = norm_costs.get(key, 0.5)

            # High retrieval cost objects receive an economic boost under latency pressure
            cost_boost = 1.0 + 0.30 * latency_pressure * (c_norm - 0.5)
            ret_val = _clamp(score * cost_boost, 0.0001, 1.0)
            retention_values[key] = ret_val

            # Value density: retention value per byte of memory
            effective_size = max(1, obj.size_bytes)
            densities[key] = model.value_density(
                ret_val,
                effective_size,
                alpha=alpha,
            )

        self.last_value_densities = densities
        self.last_retention_values = retention_values

        # 8. Deterministic sorting: lowest value density first, then ascending key tie-breaker
        sorted_keys = sorted(objects.keys(), key=lambda k: (densities[k], k))

        # 9. Greedily select lowest-density candidates until bytes_to_free satisfied
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
        workload: WorkloadState | None = None,
        system: SystemState | None = None,
        cost_model: CostModel | None = None,
    ) -> list[str]:
        """Callable interface forwarding to select_evictions()."""
        return self.select_evictions(
            scores=scores,
            objects=objects,
            target_capacity_bytes=target_capacity_bytes,
            workload=workload,
            system=system,
            cost_model=cost_model,
        )
