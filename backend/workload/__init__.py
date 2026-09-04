"""Synthetic workload scenarios module for the Adaptive Cache System.

Provides deterministic request generation tools for evaluating cache policies
against steady, traffic spike, and gradual popularity shift workloads.
"""

from __future__ import annotations

from backend.workload.generator import (
    ScenarioGenerator,
    generate_popularity_shift_scenario,
    generate_spike_scenario,
    generate_steady_scenario,
    generate_workload,
)
from backend.workload.scenario import (
    PRODUCT_CATALOG_PROFILE,
    PROFILES,
    RECOMMENDATIONS_PROFILE,
    ScenarioConfig,
    ScenarioEvent,
    WorkloadProfile,
    get_workload_profile,
)
from backend.workload.scenarios import (
    BaseScenario,
    PopularityShiftScenario,
    SpikeScenario,
    SteadyScenario,
)

__all__ = [
    "PRODUCT_CATALOG_PROFILE",
    "PROFILES",
    "RECOMMENDATIONS_PROFILE",
    "BaseScenario",
    "PopularityShiftScenario",
    "ScenarioConfig",
    "ScenarioEvent",
    "ScenarioGenerator",
    "SpikeScenario",
    "SteadyScenario",
    "WorkloadProfile",
    "generate_popularity_shift_scenario",
    "generate_spike_scenario",
    "generate_steady_scenario",
    "generate_workload",
    "get_workload_profile",
]
