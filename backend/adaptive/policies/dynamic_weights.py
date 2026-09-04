"""Re-export DynamicWeightModel for compatibility across adaptive subpackages."""

from backend.adaptive.scoring.dynamic_weights import (
    BASE_FREQUENCY_WEIGHT,
    BASE_POPULARITY_TREND_WEIGHT,
    BASE_RECENCY_WEIGHT,
    BASE_RETRIEVAL_COST_WEIGHT,
    BASE_SIZE_PENALTY_WEIGHT,
    DynamicWeightModel,
    DynamicWeights,
)

__all__ = [
    "BASE_FREQUENCY_WEIGHT",
    "BASE_POPULARITY_TREND_WEIGHT",
    "BASE_RECENCY_WEIGHT",
    "BASE_RETRIEVAL_COST_WEIGHT",
    "BASE_SIZE_PENALTY_WEIGHT",
    "DynamicWeightModel",
    "DynamicWeights",
]
