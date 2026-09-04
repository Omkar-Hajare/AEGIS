"""Workload scenario implementations for synthetic cache benchmarks."""

from __future__ import annotations

from backend.workload.scenarios.base import BaseScenario
from backend.workload.scenarios.popularity_shift import PopularityShiftScenario
from backend.workload.scenarios.spike import SpikeScenario
from backend.workload.scenarios.steady import SteadyScenario

__all__ = [
    "BaseScenario",
    "PopularityShiftScenario",
    "SpikeScenario",
    "SteadyScenario",
]
