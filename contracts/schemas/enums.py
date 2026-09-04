"""Shared enumeration contracts for the Adaptive Cache System.

Frozen v1 contracts - values and names are fixed.
"""

from enum import Enum


class WorkloadType(str, Enum):
    """Classification of workload patterns observed by the system."""

    STEADY = "STEADY"
    READ_HEAVY = "READ_HEAVY"
    COMPUTE_HEAVY = "COMPUTE_HEAVY"
    SPIKE = "SPIKE"
    POPULARITY_SHIFT = "POPULARITY_SHIFT"


class CapacityAction(str, Enum):
    """Action recommendation for cache capacity adjustments."""

    MAINTAIN = "MAINTAIN"
    SCALE_UP = "SCALE_UP"
    SCALE_DOWN = "SCALE_DOWN"
