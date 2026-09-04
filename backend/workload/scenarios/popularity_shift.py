"""Popularity shift workload scenario implementation.

Generates request streams where item popularity evolves smoothly across time:
1. Initial distribution: Requests favor an initial hot subset.
2. Transition: Popularity shifts progressively from initial to final subset.
3. Final distribution: Requests favor a distinctly different final hot subset.
"""

from __future__ import annotations

import random
from datetime import timedelta

from backend.workload.scenario import ScenarioConfig, ScenarioEvent
from backend.workload.scenarios.base import BaseScenario


class PopularityShiftScenario(BaseScenario):
    """Deterministic gradual popularity shift workload scenario generator.

    Simulates a gradual shift in user preferences over time, transitioning
    traffic concentration from one set of items toward another set.
    """

    def generate(
        self, config: ScenarioConfig, rng: random.Random
    ) -> list[ScenarioEvent]:
        """Generate a synthetic request sequence featuring a gradual popularity shift.

        Args:
            config: Scenario configuration parameters.
            rng: Seeded random.Random instance for determinism.

        Returns:
            List of generated ScenarioEvents across initial, transition, and
            final phases.
        """
        keys = [f"{config.key_prefix}_{i}" for i in range(config.object_count)]
        n = config.object_count
        k = config.hot_set_size

        init_indices, final_indices = self._determine_hot_subsets(n, k)
        m_init, m_trans, m_final = self._partition_requests(config.request_count)

        events: list[ScenarioEvent] = []
        current_time = config.start_time
        interval_seconds = (
            1.0 / config.request_rate if config.request_rate > 0.0 else 1.0
        )
        profile = config.profile

        # Phase 1: Initial distribution
        init_weights = self._calculate_shift_weights(
            n, init_indices, final_indices, alpha=0.0
        )
        for _ in range(m_init):
            key = rng.choices(keys, weights=init_weights, k=1)[0]
            events.append(
                ScenarioEvent(
                    timestamp=current_time,
                    key=key,
                    workload_type=profile.workload_type,
                    backend_latency_ms=profile.default_backend_latency_ms,
                    object_size_bytes=profile.default_object_size_bytes,
                    retrieval_cost_ms=profile.default_retrieval_cost_ms,
                    request_rate=config.request_rate,
                    metadata={
                        "phase": "initial_distribution",
                        "scenario": "popularity_shift",
                        "shift_progress": 0.0,
                    },
                )
            )
            current_time += timedelta(seconds=interval_seconds)

        # Phase 2: Progressive transition
        for j in range(m_trans):
            alpha = j / (m_trans - 1) if m_trans > 1 else 0.5
            trans_weights = self._calculate_shift_weights(
                n, init_indices, final_indices, alpha=alpha
            )
            key = rng.choices(keys, weights=trans_weights, k=1)[0]
            events.append(
                ScenarioEvent(
                    timestamp=current_time,
                    key=key,
                    workload_type=profile.workload_type,
                    backend_latency_ms=profile.default_backend_latency_ms,
                    object_size_bytes=profile.default_object_size_bytes,
                    retrieval_cost_ms=profile.default_retrieval_cost_ms,
                    request_rate=config.request_rate,
                    metadata={
                        "phase": "transition",
                        "scenario": "popularity_shift",
                        "shift_progress": round(alpha, 4),
                    },
                )
            )
            current_time += timedelta(seconds=interval_seconds)

        # Phase 3: Final distribution
        final_weights = self._calculate_shift_weights(
            n, init_indices, final_indices, alpha=1.0
        )
        for _ in range(m_final):
            key = rng.choices(keys, weights=final_weights, k=1)[0]
            events.append(
                ScenarioEvent(
                    timestamp=current_time,
                    key=key,
                    workload_type=profile.workload_type,
                    backend_latency_ms=profile.default_backend_latency_ms,
                    object_size_bytes=profile.default_object_size_bytes,
                    retrieval_cost_ms=profile.default_retrieval_cost_ms,
                    request_rate=config.request_rate,
                    metadata={
                        "phase": "final_distribution",
                        "scenario": "popularity_shift",
                        "shift_progress": 1.0,
                    },
                )
            )
            current_time += timedelta(seconds=interval_seconds)

        return events

    @staticmethod
    def _determine_hot_subsets(n: int, k: int) -> tuple[set[int], set[int]]:
        """Identify initial and final hot item index sets."""
        if n == 1:
            return {0}, {0}
        if n <= k:
            return {0}, {n - 1}

        # Prefer completely disjoint sets when n >= 2*k
        actual_k = min(k, n // 2) if n >= 2 else 1
        init_set = set(range(actual_k))
        final_set = set(range(n - actual_k, n))

        return init_set, final_set

    @staticmethod
    def _calculate_shift_weights(
        n: int, init_set: set[int], final_set: set[int], alpha: float
    ) -> list[float]:
        """Calculate per-object weights interpolated by shift parameter alpha."""
        if n == 1 or init_set == final_set:
            return [1.0 / n] * n

        cold_set = set(range(n)) - init_set - final_set

        # Smooth linear interpolation between initial and final hot preferences
        prob_init = 0.80 * (1.0 - alpha) + 0.05 * alpha
        prob_final = 0.05 * (1.0 - alpha) + 0.80 * alpha

        if cold_set:
            prob_cold = max(0.0, 1.0 - prob_init - prob_final)
            cold_weight = prob_cold / len(cold_set)
        else:
            # Re-normalize if all items are partitioned between init and final
            total_prob = prob_init + prob_final
            prob_init /= total_prob
            prob_final /= total_prob
            cold_weight = 0.0

        init_weight = prob_init / len(init_set)
        final_weight = prob_final / len(final_set)

        weights: list[float] = []
        for i in range(n):
            if i in init_set:
                weights.append(init_weight)
            elif i in final_set:
                weights.append(final_weight)
            else:
                weights.append(cold_weight)

        return weights

    @staticmethod
    def _partition_requests(total: int) -> tuple[int, int, int]:
        """Divide total request count into initial, transition, and final phases."""
        if total <= 1:
            return total, 0, 0
        if total == 2:
            return 1, 0, 1

        m_init = max(1, int(total * 0.30))
        m_trans = max(1, int(total * 0.40))
        m_final = total - m_init - m_trans

        if m_final < 1:
            m_trans = max(1, m_trans - 1)
            m_final = total - m_init - m_trans

        return m_init, m_trans, m_final
