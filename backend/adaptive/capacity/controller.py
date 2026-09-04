"""Capacity controller for the Adaptive Cache System.

Pure Python deterministic controller that evaluates WorkloadState and SystemState
to recommend logical cache capacity adjustments (SCALE_UP, SCALE_DOWN, MAINTAIN)
using continuous telemetry-driven pressure signals or backward-compatible rules.
"""

from __future__ import annotations

import math
from collections.abc import Mapping

from contracts.schemas.decision import Decision
from contracts.schemas.enums import CapacityAction
from contracts.schemas.system import SystemState
from contracts.schemas.workload import WorkloadState

# Rule-based legacy adjustment percentages
SCALE_UP_PERCENTAGE: float = 0.20
SCALE_DOWN_PERCENTAGE: float = 0.15

# Rule-based legacy utilization thresholds
HIGH_UTILIZATION_THRESHOLD: float = 0.85
CRITICAL_UTILIZATION_THRESHOLD: float = 0.90
LOW_UTILIZATION_THRESHOLD: float = 0.40

# Rule-based legacy metric thresholds
HIGH_HIT_RATE_THRESHOLD: float = 0.80
ELEVATED_MISS_RATE_THRESHOLD: float = 0.20

# Continuous calibration parameters (documented and tunable)
REQUEST_RATE_REFERENCE: float = 100.0
LATENCY_REFERENCE_MS: float = 50.0
MEMORY_WEIGHT: float = 0.40
MEMORY_MISS_INTERACTION_WEIGHT: float = 0.25
REQUEST_RATE_WEIGHT: float = 0.20
LATENCY_WEIGHT: float = 0.15
MAX_SURGE_PRESSURE_BOOST: float = 0.10

# Continuous scaling decision boundaries & adjustment ranges
PRESSURE_SCALE_UP_THRESHOLD: float = 0.65
PRESSURE_SCALE_DOWN_THRESHOLD: float = 0.45
MIN_SCALE_UP_PERCENTAGE: float = 0.05
MAX_SCALE_UP_PERCENTAGE: float = 0.35
MIN_SCALE_DOWN_PERCENTAGE: float = 0.05
MAX_SCALE_DOWN_PERCENTAGE: float = 0.25

# Rule-based justification reasons
REASON_SCALE_UP_PRESSURE: str = (
    "High cache utilization combined with elevated miss rate indicates cache pressure."
)
REASON_SCALE_UP_CRITICAL: str = "Cache utilization is critically high."
REASON_SCALE_DOWN_LOW_UTILIZATION: str = (
    "Cache utilization is low while cache hit rate remains strong."
)
REASON_MAINTAIN_NORMAL: str = (
    "Cache utilization and performance metrics are within normal operating thresholds."
)


class CapacityController:
    """Stateless, deterministic capacity controller for adaptive cache sizing."""

    SCALE_UP_PERCENTAGE: float = SCALE_UP_PERCENTAGE
    SCALE_DOWN_PERCENTAGE: float = SCALE_DOWN_PERCENTAGE
    HIGH_UTILIZATION_THRESHOLD: float = HIGH_UTILIZATION_THRESHOLD
    CRITICAL_UTILIZATION_THRESHOLD: float = CRITICAL_UTILIZATION_THRESHOLD
    LOW_UTILIZATION_THRESHOLD: float = LOW_UTILIZATION_THRESHOLD
    HIGH_HIT_RATE_THRESHOLD: float = HIGH_HIT_RATE_THRESHOLD
    ELEVATED_MISS_RATE_THRESHOLD: float = ELEVATED_MISS_RATE_THRESHOLD

    REQUEST_RATE_REFERENCE: float = REQUEST_RATE_REFERENCE
    LATENCY_REFERENCE_MS: float = LATENCY_REFERENCE_MS
    MEMORY_WEIGHT: float = MEMORY_WEIGHT
    MEMORY_MISS_INTERACTION_WEIGHT: float = MEMORY_MISS_INTERACTION_WEIGHT
    REQUEST_RATE_WEIGHT: float = REQUEST_RATE_WEIGHT
    LATENCY_WEIGHT: float = LATENCY_WEIGHT
    MAX_SURGE_PRESSURE_BOOST: float = MAX_SURGE_PRESSURE_BOOST

    PRESSURE_SCALE_UP_THRESHOLD: float = PRESSURE_SCALE_UP_THRESHOLD
    PRESSURE_SCALE_DOWN_THRESHOLD: float = PRESSURE_SCALE_DOWN_THRESHOLD
    MIN_SCALE_UP_PERCENTAGE: float = MIN_SCALE_UP_PERCENTAGE
    MAX_SCALE_UP_PERCENTAGE: float = MAX_SCALE_UP_PERCENTAGE
    MIN_SCALE_DOWN_PERCENTAGE: float = MIN_SCALE_DOWN_PERCENTAGE
    MAX_SCALE_DOWN_PERCENTAGE: float = MAX_SCALE_DOWN_PERCENTAGE

    REASON_SCALE_UP_PRESSURE: str = REASON_SCALE_UP_PRESSURE
    REASON_SCALE_UP_CRITICAL: str = REASON_SCALE_UP_CRITICAL
    REASON_SCALE_DOWN_LOW_UTILIZATION: str = REASON_SCALE_DOWN_LOW_UTILIZATION
    REASON_MAINTAIN_NORMAL: str = REASON_MAINTAIN_NORMAL

    @classmethod
    def compute_pressure(
        cls,
        workload: WorkloadState,
        system: SystemState,
    ) -> float:
        """Compute the continuous capacity pressure in [0.0, 1.0].

        Signals:
        - p_mem: Cache memory utilization in [0.0, 1.0]
        - p_miss: Cache miss rate in [0.0, 1.0]
        - p_rate: Normalized request rate with bounded traffic surge boost
        - p_lat: Normalized backend latency representing miss penalty

        Formula:
            P_cap = clamp(0.40*p_mem + 0.25*(p_mem*p_miss) + 0.20*p_rate + 0.15*p_lat, 0.0, 1.0)
        """
        if not isinstance(workload, WorkloadState):
            raise ValueError(  # noqa: TRY004
                f"workload must be an instance of WorkloadState, got {type(workload).__name__}"
            )
        if not isinstance(system, SystemState):
            raise ValueError(  # noqa: TRY004
                f"system must be an instance of SystemState, got {type(system).__name__}"
            )

        # 1. Memory utilization signal
        if system.cache_capacity_bytes > 0:
            util = float(system.cache_usage_bytes) / float(system.cache_capacity_bytes)
            p_mem = max(0.0, min(1.0, util))
        else:
            p_mem = 0.50

        # 2. Miss rate signal
        p_miss = max(0.0, min(1.0, float(workload.miss_rate)))

        # 3. Request rate & traffic surge signal
        req = max(0.0, float(workload.request_rate))
        p_rate = req / (req + cls.REQUEST_RATE_REFERENCE)

        # Check for traffic surge in workload.metrics
        if workload.metrics and isinstance(workload.metrics, Mapping):
            prev_rate_val = workload.metrics.get("previous_window_request_rate")
            if (
                prev_rate_val is not None
                and isinstance(prev_rate_val, (int, float))
                and math.isfinite(prev_rate_val)
                and prev_rate_val > 0.0
                and req > prev_rate_val
            ):
                surge_ratio = (req - float(prev_rate_val)) / float(prev_rate_val)
                surge_boost = min(
                    cls.MAX_SURGE_PRESSURE_BOOST,
                    cls.MAX_SURGE_PRESSURE_BOOST * min(1.0, surge_ratio),
                )
                p_rate = min(1.0, p_rate + surge_boost)

        # 4. Backend latency signal
        lat = max(0.0, float(workload.backend_latency_ms))
        p_lat = lat / (lat + cls.LATENCY_REFERENCE_MS)

        # 5. Composite pressure calculation
        p_cap = (
            cls.MEMORY_WEIGHT * p_mem
            + cls.MEMORY_MISS_INTERACTION_WEIGHT * (p_mem * p_miss)
            + cls.REQUEST_RATE_WEIGHT * p_rate
            + cls.LATENCY_WEIGHT * p_lat
        )

        return float(max(0.0, min(1.0, p_cap)))

    def recommend(
        self,
        workload: WorkloadState,
        system: SystemState,
        min_capacity_bytes: int,
        max_capacity_bytes: int,
        decision_id: str | None = None,
        mode: str = "continuous",
    ) -> Decision:
        """Evaluate workload and system state to recommend a capacity decision.

        Args:
            workload: Current snapshot of observed workload metrics.
            system: Current snapshot of system cache usage and capacity.
            min_capacity_bytes: Minimum permitted logical cache capacity in bytes (> 0).
            max_capacity_bytes: Maximum permitted logical cache capacity in bytes (> 0).
            decision_id: Optional unique identifier for this decision.
            mode: Capacity recommendation mode ('continuous' or 'rule_based').

        Returns:
            Decision model containing recommended action, bounded capacity, and reason.

        Raises:
            ValueError: If any arguments are invalid, out of bounds, or boolean.
        """
        self._validate_inputs(
            workload=workload,
            system=system,
            min_capacity_bytes=min_capacity_bytes,
            max_capacity_bytes=max_capacity_bytes,
            mode=mode,
        )

        pressure = self.compute_pressure(workload=workload, system=system)

        if mode == "continuous":
            if pressure > self.PRESSURE_SCALE_UP_THRESHOLD:
                # Continuous expansion scaling: [0.05, 0.35]
                span = 1.0 - self.PRESSURE_SCALE_UP_THRESHOLD
                norm_p = (pressure - self.PRESSURE_SCALE_UP_THRESHOLD) / span
                scale_up_pct = self.MIN_SCALE_UP_PERCENTAGE + (
                    self.MAX_SCALE_UP_PERCENTAGE - self.MIN_SCALE_UP_PERCENTAGE
                ) * min(1.0, max(0.0, norm_p))

                action = CapacityAction.SCALE_UP
                raw_capacity = math.ceil(
                    system.cache_capacity_bytes * (1.0 + scale_up_pct)
                )
                reason = (
                    f"Continuous capacity pressure ({pressure:.4f}) exceeds expansion "
                    f"threshold {self.PRESSURE_SCALE_UP_THRESHOLD:.2f} "
                    f"(scaling by +{scale_up_pct:.1%})."
                )
            elif pressure < self.PRESSURE_SCALE_DOWN_THRESHOLD:
                # Continuous contraction scaling: [0.05, 0.25]
                span = self.PRESSURE_SCALE_DOWN_THRESHOLD
                norm_p = (self.PRESSURE_SCALE_DOWN_THRESHOLD - pressure) / span
                scale_down_pct = self.MIN_SCALE_DOWN_PERCENTAGE + (
                    self.MAX_SCALE_DOWN_PERCENTAGE - self.MIN_SCALE_DOWN_PERCENTAGE
                ) * min(1.0, max(0.0, norm_p))

                action = CapacityAction.SCALE_DOWN
                raw_capacity = math.floor(
                    system.cache_capacity_bytes * (1.0 - scale_down_pct)
                )
                reason = (
                    f"Continuous capacity pressure ({pressure:.4f}) indicates underutilization "
                    f"below threshold {self.PRESSURE_SCALE_DOWN_THRESHOLD:.2f} "
                    f"(scaling by -{scale_down_pct:.1%})."
                )
            else:
                action = CapacityAction.MAINTAIN
                raw_capacity = system.cache_capacity_bytes
                reason = (
                    f"Continuous capacity pressure ({pressure:.4f}) is within equilibrium band "
                    f"[{self.PRESSURE_SCALE_DOWN_THRESHOLD:.2f}, {self.PRESSURE_SCALE_UP_THRESHOLD:.2f}]."
                )
        else:
            # Rule-based backward-compatible legacy mode
            utilization = system.cache_usage_bytes / system.cache_capacity_bytes

            if (
                utilization >= self.HIGH_UTILIZATION_THRESHOLD
                and workload.miss_rate > self.ELEVATED_MISS_RATE_THRESHOLD
            ):
                action = CapacityAction.SCALE_UP
                reason = self.REASON_SCALE_UP_PRESSURE
                raw_capacity = math.ceil(
                    system.cache_capacity_bytes * (1.0 + self.SCALE_UP_PERCENTAGE)
                )
            elif utilization >= self.CRITICAL_UTILIZATION_THRESHOLD:
                action = CapacityAction.SCALE_UP
                reason = self.REASON_SCALE_UP_CRITICAL
                raw_capacity = math.ceil(
                    system.cache_capacity_bytes * (1.0 + self.SCALE_UP_PERCENTAGE)
                )
            elif (
                utilization <= self.LOW_UTILIZATION_THRESHOLD
                and workload.hit_rate >= self.HIGH_HIT_RATE_THRESHOLD
            ):
                action = CapacityAction.SCALE_DOWN
                reason = self.REASON_SCALE_DOWN_LOW_UTILIZATION
                raw_capacity = math.floor(
                    system.cache_capacity_bytes * (1.0 - self.SCALE_DOWN_PERCENTAGE)
                )
            else:
                action = CapacityAction.MAINTAIN
                reason = self.REASON_MAINTAIN_NORMAL
                raw_capacity = system.cache_capacity_bytes

        # Clamp capacity strictly within [min_capacity_bytes, max_capacity_bytes]
        recommended_capacity = max(
            min_capacity_bytes, min(raw_capacity, max_capacity_bytes)
        )

        metadata = {
            "capacity_pressure": round(pressure, 4),
            "capacity_mode": mode,
            "target_capacity_bytes": recommended_capacity,
            "action": action.value,
        }

        return Decision(
            object_scores={},
            eviction_keys=[],
            capacity_action=action,
            recommended_capacity_bytes=recommended_capacity,
            reason=reason,
            decision_id=decision_id,
            timestamp=system.timestamp,
            metadata=metadata,
            version="v1",
        )

    def __call__(
        self,
        workload: WorkloadState,
        system: SystemState,
        min_capacity_bytes: int,
        max_capacity_bytes: int,
        decision_id: str | None = None,
        mode: str = "continuous",
    ) -> Decision:
        """Allow calling the controller instance directly."""
        return self.recommend(
            workload=workload,
            system=system,
            min_capacity_bytes=min_capacity_bytes,
            max_capacity_bytes=max_capacity_bytes,
            decision_id=decision_id,
            mode=mode,
        )

    @staticmethod
    def _validate_inputs(
        workload: WorkloadState,
        system: SystemState,
        min_capacity_bytes: int,
        max_capacity_bytes: int,
        mode: str = "continuous",
    ) -> None:
        """Validate controller arguments strictly."""
        if not isinstance(workload, WorkloadState):
            t_name = type(workload).__name__
            raise ValueError(  # noqa: TRY004
                f"workload must be an instance of WorkloadState, got {t_name}"
            )
        if not isinstance(system, SystemState):
            t_name = type(system).__name__
            raise ValueError(  # noqa: TRY004
                f"system must be an instance of SystemState, got {t_name}"
            )

        if isinstance(min_capacity_bytes, bool) or not isinstance(
            min_capacity_bytes, int
        ):
            raise ValueError(  # noqa: TRY004
                "min_capacity_bytes must be an integer, "
                f"got {type(min_capacity_bytes).__name__}"
            )
        if min_capacity_bytes <= 0:
            raise ValueError(
                f"min_capacity_bytes must be greater than 0, got {min_capacity_bytes}"
            )

        if isinstance(max_capacity_bytes, bool) or not isinstance(
            max_capacity_bytes, int
        ):
            raise ValueError(  # noqa: TRY004
                "max_capacity_bytes must be an integer, "
                f"got {type(max_capacity_bytes).__name__}"
            )
        if max_capacity_bytes <= 0:
            raise ValueError(
                f"max_capacity_bytes must be greater than 0, got {max_capacity_bytes}"
            )

        if min_capacity_bytes > max_capacity_bytes:
            raise ValueError(
                f"min_capacity_bytes ({min_capacity_bytes}) must be "
                f"less than or equal to max_capacity_bytes ({max_capacity_bytes})"
            )

        if system.cache_capacity_bytes <= 0:
            raise ValueError(
                "system.cache_capacity_bytes must be greater than 0, "
                f"got {system.cache_capacity_bytes}"
            )
        if system.cache_usage_bytes < 0:
            raise ValueError(
                "system.cache_usage_bytes must be non-negative, "
                f"got {system.cache_usage_bytes}"
            )

        if not isinstance(mode, str) or mode not in ("continuous", "rule_based"):
            raise ValueError(f"mode must be 'continuous' or 'rule_based', got {mode!r}")
