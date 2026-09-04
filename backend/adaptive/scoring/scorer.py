"""Deterministic adaptive scoring engine for cache retention prioritization.

Computes normalized retention scores [0.0, 1.0] for cached objects based on
extracted features and dynamic, runtime telemetry-derived weights.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from backend.adaptive.scoring.dynamic_weights import (
    DynamicWeightModel,
    DynamicWeights,
)
from contracts.schemas import WorkloadType
from contracts.schemas.system import SystemState
from contracts.schemas.workload import WorkloadState

REQUIRED_FEATURES: tuple[str, ...] = (
    "frequency",
    "recency",
    "retrieval_cost",
    "size",
    "popularity_trend",
)


class AdaptiveScorer:
    """Calculates normalized cache retention scores.

    Evaluates object value using continuous, runtime-driven feature weights
    derived from observed system telemetry and active feature distributions.
    Higher score indicates higher retention value; lower score indicates
    a stronger candidate for eviction.
    """

    REQUIRED_FEATURES: tuple[str, ...] = REQUIRED_FEATURES

    def __init__(self, weight_model: DynamicWeightModel | None = None) -> None:
        """Initialize AdaptiveScorer with an optional DynamicWeightModel."""
        self.weight_model = weight_model or DynamicWeightModel()
        self.last_weights: DynamicWeights | None = None
        self.last_pressures: dict[str, float] | None = None

    def score(
        self,
        features: dict[str, dict[str, float]],
        workload_type: WorkloadType | str | None = None,
        workload: WorkloadState | None = None,
        system: SystemState | None = None,
        weights: Mapping[str, float] | None = None,
        previous_access_counts: Mapping[str, int] | None = None,
    ) -> dict[str, float]:
        """Calculates retention scores for all provided cache objects.

        Formula:
            score = (
                frequency_weight * frequency
                + recency_weight * recency
                + retrieval_cost_weight * retrieval_cost
                + popularity_weight * popularity_trend
                - size_penalty_weight * size
            )
            clamped to [0.0, 1.0].

        Args:
            features: Mapping of object key -> mapping of feature name -> float.
            workload_type: Optional WorkloadType enum value or string (validated
                for backward compatibility).
            workload: Optional WorkloadState telemetry snapshot.
            system: Optional SystemState capacity snapshot.
            weights: Optional explicit weights override. If omitted, weights are
                dynamically derived from runtime telemetry by DynamicWeightModel.
            previous_access_counts: Optional mapping of previous-window access counts.

        Returns:
            Mapping of object key -> normalized retention score float.

        Raises:
            ValueError: If workload_type is an invalid string, if required
                features are missing, or if feature values are non-numeric,
                boolean, or outside [0.0, 1.0].
        """
        # Validate workload_type if provided (preserves contract validation)
        if workload_type is not None:
            if isinstance(workload_type, str) and not isinstance(
                workload_type, WorkloadType
            ):
                try:
                    workload_type = WorkloadType(workload_type)
                except ValueError:
                    raise ValueError(f"Unsupported workload_type: {workload_type!r}")
            elif not isinstance(workload_type, WorkloadType):
                raise ValueError(
                    "Invalid workload_type: expected WorkloadType, got "
                    f"{type(workload_type).__name__}"
                )

        if not features:
            return {}

        # Validate feature structure and value ranges
        for key, feat_dict in features.items():
            if not isinstance(feat_dict, (dict, Mapping)):
                raise ValueError(  # noqa: TRY004
                    f"Feature mapping for key {key!r} must be a dict, got "
                    f"{type(feat_dict).__name__}"
                )

            # Validate that all required features are present
            for req_feat in self.REQUIRED_FEATURES:
                if req_feat not in feat_dict:
                    raise ValueError(
                        f"Object {key!r} is missing required feature: {req_feat!r}"
                    )

            # Validate feature types and ranges
            for req_feat in self.REQUIRED_FEATURES:
                val = feat_dict[req_feat]
                if isinstance(val, bool) or not isinstance(val, (int, float)):
                    raise ValueError(  # noqa: TRY004
                        f"Feature {req_feat!r} for key {key!r} must be numeric, "
                        f"got {type(val).__name__}"
                    )
                if val < 0.0 or val > 1.0:
                    raise ValueError(
                        f"Feature {req_feat!r} for key {key!r} must be in "
                        f"range [0.0, 1.0], got {val}"
                    )

        # Derive dynamic weights from telemetry and feature pressure
        if weights is None:
            computed_weights = self.weight_model.compute_weights(
                features=features,
                workload=workload,
                system=system,
                previous_access_counts=previous_access_counts,
                workload_type=workload_type,
            )
            self.last_weights = computed_weights
            self.last_pressures = computed_weights.pressures
            active_weights: Mapping[str, float] = computed_weights
        else:
            active_weights = weights

        scores: dict[str, float] = {}
        for key, feat_dict in features.items():
            raw_score = (
                active_weights["frequency"] * feat_dict["frequency"]
                + active_weights["recency"] * feat_dict["recency"]
                + active_weights["retrieval_cost"] * feat_dict["retrieval_cost"]
                + active_weights["popularity_trend"] * feat_dict["popularity_trend"]
                - active_weights["size_penalty"] * feat_dict["size"]
            )
            scores[key] = max(0.0, min(1.0, float(raw_score)))

        return scores

    def __call__(
        self,
        features: dict[str, dict[str, float]],
        workload_type: WorkloadType | str | None = None,
        workload: WorkloadState | None = None,
        system: SystemState | None = None,
        weights: Mapping[str, float] | None = None,
        previous_access_counts: Mapping[str, int] | None = None,
        **kwargs: Any,
    ) -> dict[str, float]:
        """Callable interface forwarding to score()."""
        return self.score(
            features=features,
            workload_type=workload_type,
            workload=workload,
            system=system,
            weights=weights,
            previous_access_counts=previous_access_counts,
        )
