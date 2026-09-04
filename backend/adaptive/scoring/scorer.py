"""Deterministic adaptive scoring engine for cache retention prioritization.

Computes normalized retention scores [0.0, 1.0] for cached objects based on
extracted features and active WorkloadType weights.
"""

from __future__ import annotations

from types import MappingProxyType
from typing import Mapping

from contracts.schemas import WorkloadType

# Centralized immutable weight definitions per WorkloadType
SCORING_WEIGHTS: Mapping[WorkloadType, Mapping[str, float]] = MappingProxyType(
    {
        WorkloadType.STEADY: MappingProxyType(
            {
                "frequency": 0.30,
                "recency": 0.25,
                "retrieval_cost": 0.25,
                "popularity_trend": 0.15,
                "size_penalty": 0.05,
            }
        ),
        WorkloadType.READ_HEAVY: MappingProxyType(
            {
                "frequency": 0.40,
                "recency": 0.30,
                "retrieval_cost": 0.15,
                "popularity_trend": 0.10,
                "size_penalty": 0.05,
            }
        ),
        WorkloadType.COMPUTE_HEAVY: MappingProxyType(
            {
                "frequency": 0.20,
                "recency": 0.15,
                "retrieval_cost": 0.45,
                "popularity_trend": 0.15,
                "size_penalty": 0.05,
            }
        ),
        WorkloadType.SPIKE: MappingProxyType(
            {
                "frequency": 0.35,
                "recency": 0.35,
                "retrieval_cost": 0.15,
                "popularity_trend": 0.10,
                "size_penalty": 0.05,
            }
        ),
        WorkloadType.POPULARITY_SHIFT: MappingProxyType(
            {
                "frequency": 0.20,
                "recency": 0.20,
                "retrieval_cost": 0.15,
                "popularity_trend": 0.40,
                "size_penalty": 0.05,
            }
        ),
    }
)

REQUIRED_FEATURES: tuple[str, ...] = (
    "frequency",
    "recency",
    "retrieval_cost",
    "size",
    "popularity_trend",
)


class AdaptiveScorer:
    """Calculates normalized cache retention scores.

    Evaluates object value using workload-dependent feature weights.
    Higher score indicates higher retention value; lower score indicates
    a stronger candidate for eviction.
    """

    WEIGHTS: Mapping[WorkloadType, Mapping[str, float]] = SCORING_WEIGHTS
    REQUIRED_FEATURES: tuple[str, ...] = REQUIRED_FEATURES

    def score(
        self,
        features: dict[str, dict[str, float]],
        workload_type: WorkloadType,
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
            workload_type: Active WorkloadType enum value.

        Returns:
            Mapping of object key -> normalized retention score float.

        Raises:
            ValueError: If workload_type is invalid, if required features are
                missing, or if feature values are non-numeric, boolean, or
                outside [0.0, 1.0].
        """
        # Validate workload_type
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

        if workload_type not in self.WEIGHTS:
            raise ValueError(f"Unsupported workload_type: {workload_type}")

        if not features:
            return {}

        weights = self.WEIGHTS[workload_type]
        scores: dict[str, float] = {}

        for key, feat_dict in features.items():
            if not isinstance(feat_dict, (dict, Mapping)):
                raise ValueError(
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
                    raise ValueError(
                        f"Feature {req_feat!r} for key {key!r} must be numeric, "
                        f"got {type(val).__name__}"
                    )
                if val < 0.0 or val > 1.0:
                    raise ValueError(
                        f"Feature {req_feat!r} for key {key!r} must be in "
                        f"range [0.0, 1.0], got {val}"
                    )

            # Calculate raw retention score
            raw_score = (
                weights["frequency"] * feat_dict["frequency"]
                + weights["recency"] * feat_dict["recency"]
                + weights["retrieval_cost"] * feat_dict["retrieval_cost"]
                + weights["popularity_trend"] * feat_dict["popularity_trend"]
                - weights["size_penalty"] * feat_dict["size"]
            )

            # Clamp to [0.0, 1.0]
            scores[key] = max(0.0, min(1.0, float(raw_score)))

        return scores

    def __call__(
        self,
        features: dict[str, dict[str, float]],
        workload_type: WorkloadType,
    ) -> dict[str, float]:
        """Callable interface forwarding to score()."""
        return self.score(features, workload_type)
