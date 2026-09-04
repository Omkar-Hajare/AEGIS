"""ScenarioGenerator orchestrating synthetic workload sequences.

Provides the primary user-facing generation API for benchmark scenarios.
"""

from __future__ import annotations

import random
from datetime import datetime
from typing import Any

from backend.workload.scenario import (
    PRODUCT_CATALOG_PROFILE,
    ScenarioConfig,
    ScenarioEvent,
    WorkloadProfile,
)
from backend.workload.scenarios import (
    BaseScenario,
    PopularityShiftScenario,
    SpikeScenario,
    SteadyScenario,
)

SCENARIO_REGISTRY: dict[str, type[BaseScenario]] = {
    "steady": SteadyScenario,
    "spike": SpikeScenario,
    "popularity_shift": PopularityShiftScenario,
}


class ScenarioGenerator:
    """Deterministic synthetic workload scenario generator.

    Produces benchmark-ready request event sequences from configured scenario
    patterns using an isolated, reproducible random number generator.
    """

    def __init__(self, config: ScenarioConfig | None = None) -> None:
        """Initialize ScenarioGenerator with configuration.

        Args:
            config: Optional ScenarioConfig. If omitted, uses default steady
                configuration.
        """
        self.config = config or ScenarioConfig()

    def generate(self) -> list[ScenarioEvent]:
        """Generate the synthetic request stream according to configuration.

        Returns:
            Deterministic list of ScenarioEvent objects.

        Raises:
            ValueError: If the configured scenario_type is unknown.
        """
        scenario_key = self.config.scenario_type.lower().strip()
        scenario_cls = SCENARIO_REGISTRY.get(scenario_key)

        if scenario_cls is None:
            raise ValueError(
                f"Unknown scenario_type {self.config.scenario_type!r}. "
                f"Available scenarios: {sorted(SCENARIO_REGISTRY.keys())}"
            )

        rng = random.Random(self.config.seed)
        scenario_instance = scenario_cls()
        return scenario_instance.generate(config=self.config, rng=rng)

    def __call__(self) -> list[ScenarioEvent]:
        """Callable shortcut delegating to generate()."""
        return self.generate()

    @classmethod
    def steady(
        cls,
        seed: int = 42,
        object_count: int = 100,
        request_count: int = 1000,
        request_rate: float = 100.0,
        hot_set_size: int = 10,
        profile: WorkloadProfile | str = PRODUCT_CATALOG_PROFILE,
        start_time: datetime | None = None,
        key_prefix: str = "obj",
        extra_params: dict[str, Any] | None = None,
    ) -> ScenarioGenerator:
        """Helper constructor for a steady workload scenario generator."""
        cfg = ScenarioConfig(
            name="steady",
            scenario_type="steady",
            seed=seed,
            object_count=object_count,
            request_count=request_count,
            request_rate=request_rate,
            hot_set_size=hot_set_size,
            profile=profile,
            start_time=start_time,
            key_prefix=key_prefix,
            extra_params=extra_params,
        )
        return cls(cfg)

    @classmethod
    def spike(
        cls,
        seed: int = 42,
        object_count: int = 100,
        request_count: int = 1000,
        request_rate: float = 100.0,
        hot_set_size: int = 10,
        spike_multiplier: float = 3.0,
        profile: WorkloadProfile | str = PRODUCT_CATALOG_PROFILE,
        start_time: datetime | None = None,
        key_prefix: str = "obj",
        extra_params: dict[str, Any] | None = None,
    ) -> ScenarioGenerator:
        """Helper constructor for a traffic spike scenario generator."""
        cfg = ScenarioConfig(
            name="spike",
            scenario_type="spike",
            seed=seed,
            object_count=object_count,
            request_count=request_count,
            request_rate=request_rate,
            hot_set_size=hot_set_size,
            spike_multiplier=spike_multiplier,
            profile=profile,
            start_time=start_time,
            key_prefix=key_prefix,
            extra_params=extra_params,
        )
        return cls(cfg)

    @classmethod
    def popularity_shift(
        cls,
        seed: int = 42,
        object_count: int = 100,
        request_count: int = 1000,
        request_rate: float = 100.0,
        hot_set_size: int = 10,
        profile: WorkloadProfile | str = PRODUCT_CATALOG_PROFILE,
        start_time: datetime | None = None,
        key_prefix: str = "obj",
        extra_params: dict[str, Any] | None = None,
    ) -> ScenarioGenerator:
        """Helper constructor for a gradual popularity shift scenario generator."""
        cfg = ScenarioConfig(
            name="popularity_shift",
            scenario_type="popularity_shift",
            seed=seed,
            object_count=object_count,
            request_count=request_count,
            request_rate=request_rate,
            hot_set_size=hot_set_size,
            profile=profile,
            start_time=start_time,
            key_prefix=key_prefix,
            extra_params=extra_params,
        )
        return cls(cfg)


def generate_workload(config: ScenarioConfig) -> list[ScenarioEvent]:
    """Generate a workload event stream from configuration."""
    return ScenarioGenerator(config).generate()


def generate_steady_scenario(
    seed: int = 42,
    object_count: int = 100,
    request_count: int = 1000,
    request_rate: float = 100.0,
    hot_set_size: int = 10,
    profile: WorkloadProfile | str = PRODUCT_CATALOG_PROFILE,
    start_time: datetime | None = None,
    key_prefix: str = "obj",
    extra_params: dict[str, Any] | None = None,
) -> list[ScenarioEvent]:
    """Convenience function to generate a steady workload event sequence."""
    generator = ScenarioGenerator.steady(
        seed=seed,
        object_count=object_count,
        request_count=request_count,
        request_rate=request_rate,
        hot_set_size=hot_set_size,
        profile=profile,
        start_time=start_time,
        key_prefix=key_prefix,
        extra_params=extra_params,
    )
    return generator.generate()


def generate_spike_scenario(
    seed: int = 42,
    object_count: int = 100,
    request_count: int = 1000,
    request_rate: float = 100.0,
    hot_set_size: int = 10,
    spike_multiplier: float = 3.0,
    profile: WorkloadProfile | str = PRODUCT_CATALOG_PROFILE,
    start_time: datetime | None = None,
    key_prefix: str = "obj",
    extra_params: dict[str, Any] | None = None,
) -> list[ScenarioEvent]:
    """Convenience function to generate a traffic spike workload event sequence."""
    generator = ScenarioGenerator.spike(
        seed=seed,
        object_count=object_count,
        request_count=request_count,
        request_rate=request_rate,
        hot_set_size=hot_set_size,
        spike_multiplier=spike_multiplier,
        profile=profile,
        start_time=start_time,
        key_prefix=key_prefix,
        extra_params=extra_params,
    )
    return generator.generate()


def generate_popularity_shift_scenario(
    seed: int = 42,
    object_count: int = 100,
    request_count: int = 1000,
    request_rate: float = 100.0,
    hot_set_size: int = 10,
    profile: WorkloadProfile | str = PRODUCT_CATALOG_PROFILE,
    start_time: datetime | None = None,
    key_prefix: str = "obj",
    extra_params: dict[str, Any] | None = None,
) -> list[ScenarioEvent]:
    """Convenience function to generate a popularity shift event sequence."""
    generator = ScenarioGenerator.popularity_shift(
        seed=seed,
        object_count=object_count,
        request_count=request_count,
        request_rate=request_rate,
        hot_set_size=hot_set_size,
        profile=profile,
        start_time=start_time,
        key_prefix=key_prefix,
        extra_params=extra_params,
    )
    return generator.generate()
