"""Shared v1 schemas and contracts for the Adaptive Cache System.

This package exposes the frozen v1 data contracts used across components:
- CacheObject: Model representing a cached object and its access statistics.
- WorkloadState: Model representing observations of system workload patterns.
- SystemState: Model representing cache capacity, memory usage, and backend traffic.
- Decision: Model representing the adaptive intelligence engine's output actions.
- WorkloadType: Enumeration of recognized workload patterns.
- CapacityAction: Enumeration of capacity scaling actions.
"""

from .cache import CacheObject
from .decision import Decision
from .enums import CapacityAction, WorkloadType
from .system import SystemState
from .workload import WorkloadState

CONTRACT_VERSION = "v1"

__all__ = [
    "CacheObject",
    "WorkloadState",
    "SystemState",
    "Decision",
    "WorkloadType",
    "CapacityAction",
    "CONTRACT_VERSION",
]
