"""Adaptive Decision Engine for the Adaptive Cache System.

Orchestrates all adaptive intelligence components:
- Feature extraction via FeatureExtractor
- Workload classification via WorkloadAnalyzer
- Retention scoring via AdaptiveScorer
- Staleness and refresh evaluation via RefreshPolicy
- Logical capacity recommendation via CapacityController
- Capacity-driven eviction via EvictionPolicy
"""

from __future__ import annotations

import hashlib
import math
from collections.abc import Mapping
from datetime import datetime

from backend.adaptive.capacity import CapacityController
from backend.adaptive.eviction import EvictionPolicy
from backend.adaptive.features import FeatureExtractor
from backend.adaptive.refresh import RefreshPolicy
from backend.adaptive.scoring import AdaptiveScorer
from backend.adaptive.workload import WorkloadAnalyzer
from contracts.schemas import (
    CacheObject,
    Decision,
    SystemState,
    WorkloadState,
)


class DecisionEngine:
    """Unified adaptive intelligence decision engine.

    Orchestrates feature extraction, workload classification, utility scoring,
    refresh evaluation, eviction selection, and capacity resizing into a
    deterministic Decision contract.
    """

    def __init__(
        self,
        feature_extractor: FeatureExtractor | None = None,
        workload_analyzer: WorkloadAnalyzer | None = None,
        scorer: AdaptiveScorer | None = None,
        refresh_policy: RefreshPolicy | None = None,
        capacity_controller: CapacityController | None = None,
        eviction_policy: EvictionPolicy | None = None,
    ) -> None:
        """Initialize DecisionEngine with optional injected components."""
        self.feature_extractor = feature_extractor or FeatureExtractor()
        self.workload_analyzer = workload_analyzer or WorkloadAnalyzer()
        self.scorer = scorer or AdaptiveScorer()
        self.refresh_policy = refresh_policy or RefreshPolicy()
        self.capacity_controller = capacity_controller or CapacityController()
        self.eviction_policy = eviction_policy or EvictionPolicy()

    def decide(
        self,
        objects: Mapping[str, CacheObject],
        workload: WorkloadState,
        system: SystemState,
        min_capacity_bytes: int,
        max_capacity_bytes: int,
        now: datetime | None = None,
        previous_access_counts: Mapping[str, int] | None = None,
        refresh_after_seconds: float = 300.0,
        decision_id: str | None = None,
    ) -> Decision:
        """Evaluate telemetry and cache state to produce an adaptive Decision.

        Args:
            objects: Mapping of cache key to CacheObject metadata.
            workload: Current observed WorkloadState telemetry snapshot.
            system: Current observed SystemState snapshot.
            min_capacity_bytes: Minimum permissible logical cache capacity (> 0).
            max_capacity_bytes: Maximum permissible logical cache capacity (> 0).
            now: Optional reference evaluation datetime (must be timezone-aware).
                 Defaults to system.timestamp.
            previous_access_counts: Optional mapping of previous-window access counts.
            refresh_after_seconds: Base staleness threshold in seconds (> 0).
            decision_id: Optional explicit unique identifier for the decision.

        Returns:
            Frozen v1 Decision object detailing capacity, scoring, evictions,
            and refresh recommendations.

        Raises:
            ValueError: If inputs, capacity bounds, or timestamps are invalid.
            TypeError: If input mapping or object types are invalid.
        """
        # 1. Validate inputs
        self._validate_inputs(
            objects=objects,
            workload=workload,
            system=system,
            min_capacity_bytes=min_capacity_bytes,
            max_capacity_bytes=max_capacity_bytes,
            now=now,
            refresh_after_seconds=refresh_after_seconds,
        )

        # 2. Determine evaluation timestamp
        eval_time = now if now is not None else system.timestamp

        # 3. Feature extraction
        prev_counts = (
            dict(previous_access_counts) if previous_access_counts is not None else None
        )
        features = self.feature_extractor.extract(
            objects=list(objects.values()),
            now=eval_time,
            window_seconds=workload.window_seconds,
            previous_access_counts=prev_counts,
        )

        # 4. Workload classification
        detected_workload_type = self.workload_analyzer.analyze(workload)

        # 5. Adaptive retention scoring
        scores = self.scorer.score(
            features=features,
            workload_type=detected_workload_type,
        )

        # 6. Staleness / refresh evaluation
        refresh_keys: list[str] = []
        for key in sorted(objects.keys()):
            obj = objects[key]
            if self.refresh_policy.should_refresh(
                object=obj,
                now=eval_time,
                workload_type=detected_workload_type,
                refresh_after_seconds=refresh_after_seconds,
            ):
                refresh_keys.append(key)

        # 7. Capacity recommendation
        capacity_decision = self.capacity_controller.recommend(
            workload=workload,
            system=system,
            min_capacity_bytes=min_capacity_bytes,
            max_capacity_bytes=max_capacity_bytes,
        )
        recommended_capacity = capacity_decision.recommended_capacity_bytes
        capacity_action = capacity_decision.capacity_action

        # 8. Capacity-driven eviction selection
        current_usage = sum(obj.size_bytes for obj in objects.values())
        if current_usage > recommended_capacity and objects:
            eviction_keys = self.eviction_policy.select_evictions(
                scores=scores,
                objects=dict(objects),
                target_capacity_bytes=recommended_capacity,
            )
        else:
            eviction_keys = []

        # 9. Structured metadata
        metadata = {
            "workload_type": detected_workload_type.value,
            "refresh_keys": refresh_keys,
            "refreshed_count": len(refresh_keys),
            "object_count": len(objects),
            "current_usage_bytes": current_usage,
            "target_capacity_bytes": recommended_capacity,
            "capacity_action": capacity_action.value,
            "reason_components": {
                "workload_type": detected_workload_type.value,
                "capacity_action": capacity_action.value,
                "eviction_count": len(eviction_keys),
                "refresh_count": len(refresh_keys),
                "current_usage_bytes": current_usage,
                "target_capacity_bytes": recommended_capacity,
            },
        }

        # 10. Reason formulation
        eviction_desc = (
            f"cache pressure requires {len(eviction_keys)} evictions"
            if eviction_keys
            else "no evictions required"
        )
        refresh_desc = (
            f"{len(refresh_keys)} objects require refresh"
            if refresh_keys
            else "no objects require refresh"
        )
        reason = (
            f"Workload={detected_workload_type.value}; "
            f"{eviction_desc}; "
            f"{refresh_desc}; "
            f"capacity action={capacity_action.value}."
        )

        # 11. Deterministic Decision ID
        if decision_id is not None:
            final_decision_id = decision_id
        else:
            joined_keys = ",".join(sorted(objects.keys()))
            seed = (
                f"{eval_time.isoformat()}-{detected_workload_type.value}-"
                f"{recommended_capacity}-{joined_keys}"
            )
            hash_suffix = hashlib.sha256(seed.encode("utf-8")).hexdigest()[:16]
            final_decision_id = f"dec-{hash_suffix}"

        # 12. Return frozen v1 Decision contract
        return Decision(
            decision_id=final_decision_id,
            timestamp=eval_time,
            capacity_action=capacity_action,
            recommended_capacity_bytes=recommended_capacity,
            object_scores=scores,
            eviction_keys=eviction_keys,
            reason=reason,
            metadata=metadata,
            version="v1",
        )

    def __call__(
        self,
        objects: Mapping[str, CacheObject],
        workload: WorkloadState,
        system: SystemState,
        min_capacity_bytes: int,
        max_capacity_bytes: int,
        now: datetime | None = None,
        previous_access_counts: Mapping[str, int] | None = None,
        refresh_after_seconds: float = 300.0,
        decision_id: str | None = None,
    ) -> Decision:
        """Allow calling the DecisionEngine instance directly."""
        return self.decide(
            objects=objects,
            workload=workload,
            system=system,
            min_capacity_bytes=min_capacity_bytes,
            max_capacity_bytes=max_capacity_bytes,
            now=now,
            previous_access_counts=previous_access_counts,
            refresh_after_seconds=refresh_after_seconds,
            decision_id=decision_id,
        )

    @staticmethod
    def _validate_inputs(
        objects: Mapping[str, CacheObject],
        workload: WorkloadState,
        system: SystemState,
        min_capacity_bytes: int,
        max_capacity_bytes: int,
        now: datetime | None,
        refresh_after_seconds: float,
    ) -> None:
        """Validate all inputs strictly before executing engine pipeline."""
        if not isinstance(objects, (dict, Mapping)):
            raise TypeError(f"objects must be a mapping, got {type(objects).__name__}")

        for key, obj in objects.items():
            if not isinstance(key, str):
                raise TypeError(
                    f"Object key must be a string, got {type(key).__name__}"
                )
            if not isinstance(obj, CacheObject):
                raise TypeError(
                    f"Value for key {key!r} must be a CacheObject, "
                    f"got {type(obj).__name__}"
                )
            if key != obj.key:
                raise ValueError(
                    f"Mapping key {key!r} does not match CacheObject.key {obj.key!r}"
                )

        if not isinstance(workload, WorkloadState):
            raise TypeError(
                f"workload must be a WorkloadState, got {type(workload).__name__}"
            )

        if not isinstance(system, SystemState):
            raise TypeError(
                f"system must be a SystemState, got {type(system).__name__}"
            )

        if isinstance(min_capacity_bytes, bool) or not isinstance(
            min_capacity_bytes, int
        ):
            raise TypeError(
                "min_capacity_bytes must be an integer, "
                f"got {type(min_capacity_bytes).__name__}"
            )
        if min_capacity_bytes <= 0:
            raise ValueError(
                f"min_capacity_bytes must be greater than 0, got {min_capacity_bytes}"
            )

        if isinstance(max_capacity_bytes, bool) or not isinstance(
            max_capacity_bytes, int
        ):
            raise TypeError(
                "max_capacity_bytes must be an integer, "
                f"got {type(max_capacity_bytes).__name__}"
            )
        if max_capacity_bytes <= 0:
            raise ValueError(
                f"max_capacity_bytes must be greater than 0, got {max_capacity_bytes}"
            )

        if min_capacity_bytes > max_capacity_bytes:
            raise ValueError(
                f"min_capacity_bytes ({min_capacity_bytes}) must be <= "
                f"max_capacity_bytes ({max_capacity_bytes})"
            )

        if now is not None:
            if not isinstance(now, datetime):
                raise TypeError(f"now must be a datetime, got {type(now).__name__}")
            if now.tzinfo is None or now.tzinfo.utcoffset(now) is None:
                raise ValueError(
                    "now must be a timezone-aware datetime; received naive datetime"
                )

        if isinstance(refresh_after_seconds, bool) or not isinstance(
            refresh_after_seconds, (int, float)
        ):
            raise TypeError(
                "refresh_after_seconds must be numeric, "
                f"got {type(refresh_after_seconds).__name__}"
            )
        if not math.isfinite(refresh_after_seconds):
            raise ValueError(
                f"refresh_after_seconds must be finite, got {refresh_after_seconds}"
            )
        if refresh_after_seconds <= 0.0:
            raise ValueError(
                "refresh_after_seconds must be greater than 0, "
                f"got {refresh_after_seconds}"
            )
