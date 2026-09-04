"""Steady workload scenario implementation.

Generates request streams with constant request arrival rate and stable
popularity distribution across the entire observation window.
"""

from __future__ import annotations

import random
from datetime import timedelta

from backend.workload.scenario import ScenarioConfig, ScenarioEvent
from backend.workload.scenarios.base import BaseScenario


class SteadyScenario(BaseScenario):
    """Deterministic steady-state workload scenario generator.

    Maintains a stable arrival rate and a consistent object popularity
    distribution without phase transitions or abrupt traffic fluctuations.
    """

    def generate(
        self, config: ScenarioConfig, rng: random.Random
    ) -> list[ScenarioEvent]:
        """Generate a steady synthetic request sequence.

        Args:
            config: Scenario configuration parameters.
            rng: Seeded random.Random instance for determinism.

        Returns:
            List of generated ScenarioEvents.
        """
        keys = [f"{config.key_prefix}_{i}" for i in range(config.object_count)]
        weights = self._calculate_weights(config)

        # Pre-select all keys deterministically using injected RNG
        chosen_keys = rng.choices(keys, weights=weights, k=config.request_count)

        interval_seconds = (
            1.0 / config.request_rate if config.request_rate > 0.0 else 1.0
        )
        current_time = config.start_time
        events: list[ScenarioEvent] = []

        profile = config.profile
        for key in chosen_keys:
            events.append(
                ScenarioEvent(
                    timestamp=current_time,
                    key=key,
                    workload_type=profile.workload_type,
                    backend_latency_ms=profile.default_backend_latency_ms,
                    object_size_bytes=profile.default_object_size_bytes,
                    retrieval_cost_ms=profile.default_retrieval_cost_ms,
                    request_rate=config.request_rate,
                    metadata={"phase": "steady", "scenario": "steady"},
                )
            )
            current_time += timedelta(seconds=interval_seconds)

        return events

    @staticmethod
    def _calculate_weights(config: ScenarioConfig) -> list[float]:
        """Compute relative selection weights for objects."""
        n = config.object_count
        k = config.hot_set_size
        extra = config.extra_params or {}

        # Optional Zipfian distribution
        if extra.get("distribution") == "zipf":
            s = float(extra.get("zipf_exponent", 1.0))
            return [1.0 / ((i + 1) ** s) for i in range(n)]

        # Default: 2-tier 80/20 hot/cold distribution
        if k >= n:
            return [1.0 / n] * n

        hot_ratio = float(extra.get("hot_ratio", 0.80))
        cold_ratio = 1.0 - hot_ratio

        hot_weight = hot_ratio / k
        cold_weight = cold_ratio / (n - k)

        return [hot_weight if i < k else cold_weight for i in range(n)]
