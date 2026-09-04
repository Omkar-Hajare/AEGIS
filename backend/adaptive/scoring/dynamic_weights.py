"""Dynamic weight model for the Adaptive Cache System.

Derives continuous, normalized feature weights from runtime telemetry,
system state, and object feature distributions without relying on static
WorkloadType-to-weight lookup tables.
"""

from __future__ import annotations

import math
from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from typing import Any

from contracts.schemas.system import SystemState
from contracts.schemas.workload import WorkloadState

# Default baseline weights when all runtime pressures are neutral (0.50).
# Positive weights sum to 0.95; size penalty baseline is 0.05.
BASE_FREQUENCY_WEIGHT: float = 0.30
BASE_RECENCY_WEIGHT: float = 0.25
BASE_RETRIEVAL_COST_WEIGHT: float = 0.25
BASE_POPULARITY_TREND_WEIGHT: float = 0.15
BASE_SIZE_PENALTY_WEIGHT: float = 0.05

# Reference latency for compute pressure scaling (50 ms).
# Latency below 50 ms produces pressure < 0.5; above 50 ms produces pressure > 0.5.
REFERENCE_BACKEND_LATENCY_MS: float = 50.0

# Budget for normalized positive retention weights.
TOTAL_POSITIVE_WEIGHT_BUDGET: float = 0.95


def _safe_float(val: Any, default: float = 0.5) -> float:
    """Safely convert a value to finite float, returning default if invalid."""
    if val is None or isinstance(val, bool):
        return default
    if not isinstance(val, (int, float)):
        return default
    f = float(val)
    if not math.isfinite(f):
        return default
    return f


def _clamp(val: float, low: float = 0.0, high: float = 1.0) -> float:
    """Clamp float value to [low, high]."""
    return max(low, min(high, val))


@dataclass(frozen=True)
class DynamicWeights(Mapping[str, float]):
    """Immutable container for dynamically derived feature weights.

    Provides attribute access, dict-like mapping access, and explainability
    telemetry through the ``pressures`` attribute.
    """

    frequency: float
    recency: float
    retrieval_cost: float
    popularity_trend: float
    size_penalty: float
    pressures: dict[str, float]

    def as_dict(self) -> dict[str, float]:
        """Return the five scoring weights as a standard dictionary."""
        return {
            "frequency": self.frequency,
            "recency": self.recency,
            "retrieval_cost": self.retrieval_cost,
            "popularity_trend": self.popularity_trend,
            "size_penalty": self.size_penalty,
        }

    # Mapping protocol methods for backward-compatible dictionary access:
    def __getitem__(self, key: str) -> float:
        if key in ("frequency", "frequency_weight"):
            return self.frequency
        if key in ("recency", "recency_weight"):
            return self.recency
        if key in ("retrieval_cost", "retrieval_cost_weight"):
            return self.retrieval_cost
        if key in ("popularity_trend", "popularity_trend_weight"):
            return self.popularity_trend
        if key in ("size_penalty", "size", "size_weight"):
            return self.size_penalty
        raise KeyError(key)

    def __iter__(self) -> Iterator[str]:
        return iter(
            [
                "frequency",
                "recency",
                "retrieval_cost",
                "popularity_trend",
                "size_penalty",
            ]
        )

    def __len__(self) -> int:
        return 5


class DynamicWeightModel:
    """Deterministic, pure-mathematical dynamic weight calculation model.

    Computes continuous feature weights directly from observed runtime telemetry
    and active feature distributions. Does NOT use static WorkloadType lookup tables
    or arbitrary categorical if-branches.
    """

    def __init__(
        self,
        base_frequency: float = BASE_FREQUENCY_WEIGHT,
        base_recency: float = BASE_RECENCY_WEIGHT,
        base_retrieval_cost: float = BASE_RETRIEVAL_COST_WEIGHT,
        base_popularity_trend: float = BASE_POPULARITY_TREND_WEIGHT,
        base_size_penalty: float = BASE_SIZE_PENALTY_WEIGHT,
        reference_latency_ms: float = REFERENCE_BACKEND_LATENCY_MS,
    ) -> None:
        """Initialize DynamicWeightModel with baseline parameters."""
        self.base_frequency = base_frequency
        self.base_recency = base_recency
        self.base_retrieval_cost = base_retrieval_cost
        self.base_popularity_trend = base_popularity_trend
        self.base_size_penalty = base_size_penalty
        self.reference_latency_ms = reference_latency_ms

        self.last_weights: DynamicWeights | None = None
        self.last_pressures: dict[str, float] | None = None

    def compute_pressures(
        self,
        features: Mapping[str, Mapping[str, float]] | None = None,
        workload: WorkloadState | None = None,
        system: SystemState | None = None,
        previous_access_counts: Mapping[str, int] | None = None,
    ) -> dict[str, float]:
        """Derive continuous pressure indicators in [0.0, 1.0] from runtime telemetry.

        Signals:
        - latency_pressure: Higher backend latency increases retrieval-cost importance.
        - memory_pressure: Higher cache utilization increases size-penalty weight.
        - trend_pressure: Higher popularity drift/churn elevates trend importance.
        - frequency_pressure: Higher hit-rate or request frequency elevates frequency weight.
        - recency_pressure: Higher miss-rate or sudden burst elevates recency weight.
        """
        # 1. Compute Latency Pressure (retrieval_cost)
        if workload is not None and math.isfinite(workload.backend_latency_ms):
            lat = max(0.0, float(workload.backend_latency_ms))
            latency_pressure = lat / (lat + self.reference_latency_ms)
        elif features:
            avg_cost = sum(
                _safe_float(f.get("retrieval_cost"), 0.5) for f in features.values()
            ) / max(1, len(features))
            latency_pressure = _clamp(avg_cost, 0.0, 1.0)
        else:
            latency_pressure = 0.5

        # 2. Memory Utilization Pressure (size)
        if (
            system is not None
            and system.cache_capacity_bytes > 0
            and math.isfinite(system.cache_usage_bytes)
        ):
            util = max(0.0, system.cache_usage_bytes) / float(
                system.cache_capacity_bytes
            )
            memory_pressure = _clamp(util, 0.0, 1.0)
        elif features:
            avg_size = sum(
                _safe_float(f.get("size"), 0.5) for f in features.values()
            ) / max(1, len(features))
            memory_pressure = _clamp(avg_size, 0.0, 1.0)
        else:
            memory_pressure = 0.5

        # 3. Popularity Trend Pressure (churn / drift)
        trend_pressure = 0.5
        if features:
            divergence = sum(
                abs(_safe_float(f.get("popularity_trend"), 0.5) - 0.5)
                for f in features.values()
            ) / max(1, len(features))
            trend_pressure = _clamp(2.0 * divergence, 0.0, 1.0)

        if workload is not None and workload.metrics:
            shift_score = workload.metrics.get("popularity_shift_score")
            if (
                isinstance(shift_score, (int, float))
                and not isinstance(shift_score, bool)
                and math.isfinite(shift_score)
            ):
                trend_pressure = max(
                    trend_pressure, _clamp(float(shift_score), 0.0, 1.0)
                )

        # 4. Request Rate Surge
        rate_surge = 0.0
        if workload is not None and workload.metrics:
            baseline = workload.metrics.get("request_rate_baseline")
            if (
                isinstance(baseline, (int, float))
                and not isinstance(baseline, bool)
                and baseline > 0.0
                and math.isfinite(workload.request_rate)
                and workload.request_rate > baseline
            ):
                rate_surge = _clamp(
                    (float(workload.request_rate) - baseline) / (2.0 * baseline),
                    0.0,
                    1.0,
                )

        # 5. Frequency Pressure
        # Derived from candidate object access-frequency distribution and repeated access concentration,
        # supplemented by request arrival rate / surge, rather than cache hit rate.
        if features:
            freq_vals = [
                _safe_float(f.get("frequency"), 0.5) for f in features.values()
            ]
            n_freq = len(freq_vals)
            mean_freq = sum(freq_vals) / max(1, n_freq)

            # Repeated access concentration (mean of top quartile highest frequency objects):
            sorted_freq = sorted(freq_vals, reverse=True)
            k_top_freq = max(1, math.ceil(n_freq / 4))
            top_freq_mean = sum(sorted_freq[:k_top_freq]) / k_top_freq

            freq_distribution = 0.5 * mean_freq + 0.5 * top_freq_mean
            frequency_pressure = _clamp(
                0.5 + 0.6 * (freq_distribution - 0.5) + 0.25 * rate_surge,
                0.0,
                1.0,
            )
        else:
            # Deterministic cold-start fallback when features are not available
            hit_rate = 0.5
            if workload is not None and math.isfinite(workload.hit_rate):
                hit_rate = _clamp(float(workload.hit_rate), 0.0, 1.0)
            frequency_pressure = _clamp(
                0.5 + 0.3 * (hit_rate - 0.5) + 0.25 * rate_surge,
                0.0,
                1.0,
            )

        # 6. Recency Pressure
        # Derived from candidate object freshness, newly active working set presence,
        # and traffic arrival bursts, rather than cache miss rate.
        if features:
            rec_vals = [_safe_float(f.get("recency"), 0.5) for f in features.values()]
            n_rec = len(rec_vals)
            mean_rec = sum(rec_vals) / max(1, n_rec)

            sorted_rec = sorted(rec_vals, reverse=True)
            k_top_rec = max(1, math.ceil(n_rec / 4))
            top_rec_mean = sum(sorted_rec[:k_top_rec]) / k_top_rec

            rec_distribution = 0.6 * mean_rec + 0.4 * top_rec_mean

            # Newly active working set detection:
            # Objects active in the current window with 0 or missing prior accesses
            new_working_set_boost = 0.0
            if previous_access_counts is not None and n_rec > 0:
                newly_active_count = sum(
                    1
                    for k, f in features.items()
                    if previous_access_counts.get(k, 0) == 0
                    and _safe_float(f.get("recency"), 0.5) >= 0.5
                )
                new_set_ratio = newly_active_count / float(n_rec)
                new_working_set_boost = 0.25 * _clamp(new_set_ratio, 0.0, 1.0)

            recency_pressure = _clamp(
                0.5
                + 0.6 * (rec_distribution - 0.5)
                + new_working_set_boost
                + 0.25 * rate_surge,
                0.0,
                1.0,
            )
        else:
            # Deterministic cold-start fallback when features are not available
            miss_rate = 0.5
            if workload is not None and math.isfinite(workload.miss_rate):
                miss_rate = _clamp(float(workload.miss_rate), 0.0, 1.0)
            recency_pressure = _clamp(
                0.5 + 0.3 * (miss_rate - 0.5) + 0.25 * rate_surge,
                0.0,
                1.0,
            )

        return {
            "latency_pressure": latency_pressure,
            "memory_pressure": memory_pressure,
            "trend_pressure": trend_pressure,
            "frequency_pressure": frequency_pressure,
            "recency_pressure": recency_pressure,
        }

    def compute_weights(
        self,
        features: Mapping[str, Mapping[str, float]] | None = None,
        workload: WorkloadState | None = None,
        system: SystemState | None = None,
        previous_access_counts: Mapping[str, int] | None = None,
        workload_type: Any = None,
    ) -> DynamicWeights:
        """Derive continuous, normalized scoring weights from runtime telemetry.

        Args:
            features: Optional mapping of cache key -> feature dictionary.
            workload: Optional WorkloadState telemetry snapshot.
            system: Optional SystemState capacity snapshot.
            previous_access_counts: Optional mapping of previous-window access counts.
            workload_type: Optional legacy parameter; preserved for interface
                compatibility, but does NOT select hard-coded weight tables.

        Returns:
            DynamicWeights container with normalized weights and telemetry pressures.
        """
        pressures = self.compute_pressures(
            features=features,
            workload=workload,
            system=system,
            previous_access_counts=previous_access_counts,
        )

        p_lat = pressures["latency_pressure"]
        p_mem = pressures["memory_pressure"]
        p_trend = pressures["trend_pressure"]
        p_freq = pressures["frequency_pressure"]
        p_rec = pressures["recency_pressure"]

        # Exponential modulation around neutral (0.50):
        raw_freq = self.base_frequency * math.exp(0.8 * (p_freq - 0.5))
        raw_rec = self.base_recency * math.exp(0.8 * (p_rec - 0.5))
        raw_cost = self.base_retrieval_cost * math.exp(1.4 * (p_lat - 0.5))
        raw_trend = self.base_popularity_trend * math.exp(1.4 * (p_trend - 0.5))

        pos_sum = raw_freq + raw_rec + raw_cost + raw_trend
        if pos_sum <= 0.0 or not math.isfinite(pos_sum):
            pos_sum = TOTAL_POSITIVE_WEIGHT_BUDGET
            raw_freq = self.base_frequency
            raw_rec = self.base_recency
            raw_cost = self.base_retrieval_cost
            raw_trend = self.base_popularity_trend

        # Normalize positive weights to match budget (0.95)
        norm_factor = TOTAL_POSITIVE_WEIGHT_BUDGET / pos_sum
        w_freq = raw_freq * norm_factor
        w_rec = raw_rec * norm_factor
        w_cost = raw_cost * norm_factor
        w_trend = raw_trend * norm_factor

        # Dynamic size penalty scales with cache memory utilization [0.02, 0.08]
        w_size = _clamp(0.02 + 0.06 * p_mem, 0.01, 0.10)

        weights = DynamicWeights(
            frequency=w_freq,
            recency=w_rec,
            retrieval_cost=w_cost,
            popularity_trend=w_trend,
            size_penalty=w_size,
            pressures=pressures,
        )

        self.last_weights = weights
        self.last_pressures = pressures
        return weights

    def __call__(
        self,
        features: Mapping[str, Mapping[str, float]] | None = None,
        workload: WorkloadState | None = None,
        system: SystemState | None = None,
        previous_access_counts: Mapping[str, int] | None = None,
        workload_type: Any = None,
    ) -> DynamicWeights:
        """Allow calling the model instance directly as a callable."""
        return self.compute_weights(
            features=features,
            workload=workload,
            system=system,
            previous_access_counts=previous_access_counts,
            workload_type=workload_type,
        )
