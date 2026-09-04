"""Spike workload scenario implementation.

Generates request streams with three distinct temporal phases:
1. Baseline: Standard arrival rate and normal object popularity.
2. Spike: Elevated arrival rate and sharp concentration on hot subset.
3. Recovery: Return toward baseline arrival rate and normal distribution.
"""

from __future__ import annotations

import random
from datetime import timedelta

from backend.workload.scenario import ScenarioConfig, ScenarioEvent
from backend.workload.scenarios.base import BaseScenario


class SpikeScenario(BaseScenario):
    """Deterministic traffic spike workload scenario generator.

    Simulates a sudden surge in traffic volume and request concentration
    on a hot subset of cache objects followed by a recovery phase.
    """

    def generate(
        self, config: ScenarioConfig, rng: random.Random
    ) -> list[ScenarioEvent]:
        """Generate a synthetic request sequence featuring a traffic spike.

        Args:
            config: Scenario configuration parameters.
            rng: Seeded random.Random instance for determinism.

        Returns:
            List of generated ScenarioEvents across baseline, spike, and recovery.
        """
        keys = [f"{config.key_prefix}_{i}" for i in range(config.object_count)]
        n = config.object_count
        k = config.hot_set_size

        # Compute weights for baseline/recovery vs spike
        base_weights = self._calculate_weights(n, k, hot_ratio=0.40)
        spike_weights = self._calculate_weights(n, k, hot_ratio=0.95)

        # Allocate request counts across the three phases
        m_base, m_spike, m_rec = self._partition_requests(config.request_count)

        phases: list[tuple[str, int, list[float], float, float]] = [
            (
                "baseline",
                m_base,
                base_weights,
                config.request_rate,
                1.0,
            ),
            (
                "spike",
                m_spike,
                spike_weights,
                config.request_rate * config.spike_multiplier,
                config.spike_multiplier,
            ),
            (
                "recovery",
                m_rec,
                base_weights,
                config.request_rate,
                1.0,
            ),
        ]

        events: list[ScenarioEvent] = []
        current_time = config.start_time
        profile = config.profile

        for phase_name, count, weights, rate, mult in phases:
            if count <= 0:
                continue

            chosen_keys = rng.choices(keys, weights=weights, k=count)
            interval_seconds = 1.0 / rate if rate > 0.0 else 1.0

            for key in chosen_keys:
                events.append(
                    ScenarioEvent(
                        timestamp=current_time,
                        key=key,
                        workload_type=profile.workload_type,
                        backend_latency_ms=profile.default_backend_latency_ms,
                        object_size_bytes=profile.default_object_size_bytes,
                        retrieval_cost_ms=profile.default_retrieval_cost_ms,
                        request_rate=rate,
                        metadata={
                            "phase": phase_name,
                            "scenario": "spike",
                            "spike_multiplier": mult,
                        },
                    )
                )
                current_time += timedelta(seconds=interval_seconds)

        return events

    @staticmethod
    def _partition_requests(total: int) -> tuple[int, int, int]:
        """Divide total request count into baseline, spike, and recovery."""
        if total <= 1:
            return 0, total, 0
        if total == 2:
            return 1, 1, 0

        m_base = max(1, int(total * 0.30))
        m_spike = max(1, int(total * 0.40))
        m_rec = total - m_base - m_spike

        if m_rec < 1:
            m_spike = max(1, m_spike - 1)
            m_rec = total - m_base - m_spike

        return m_base, m_spike, m_rec

    @staticmethod
    def _calculate_weights(n: int, k: int, hot_ratio: float) -> list[float]:
        """Compute relative selection weights for objects."""
        if k >= n:
            return [1.0 / n] * n

        cold_ratio = 1.0 - hot_ratio
        hot_weight = hot_ratio / k
        cold_weight = cold_ratio / (n - k)

        return [hot_weight if i < k else cold_weight for i in range(n)]
