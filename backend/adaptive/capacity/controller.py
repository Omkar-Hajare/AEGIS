"""Capacity controller for the Adaptive Cache System.

Pure Python deterministic controller that evaluates WorkloadState and SystemState
to recommend logical cache capacity adjustments (SCALE_UP, SCALE_DOWN, MAINTAIN).
"""

import math
from typing import Optional

from contracts.schemas.decision import Decision
from contracts.schemas.enums import CapacityAction
from contracts.schemas.system import SystemState
from contracts.schemas.workload import WorkloadState

# Capacity adjustment percentages
SCALE_UP_PERCENTAGE: float = 0.20
SCALE_DOWN_PERCENTAGE: float = 0.15

# Utilization thresholds
HIGH_UTILIZATION_THRESHOLD: float = 0.85
CRITICAL_UTILIZATION_THRESHOLD: float = 0.90
LOW_UTILIZATION_THRESHOLD: float = 0.40

# Metric thresholds
HIGH_HIT_RATE_THRESHOLD: float = 0.80
ELEVATED_MISS_RATE_THRESHOLD: float = 0.20

# Justification reasons
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

    REASON_SCALE_UP_PRESSURE: str = REASON_SCALE_UP_PRESSURE
    REASON_SCALE_UP_CRITICAL: str = REASON_SCALE_UP_CRITICAL
    REASON_SCALE_DOWN_LOW_UTILIZATION: str = REASON_SCALE_DOWN_LOW_UTILIZATION
    REASON_MAINTAIN_NORMAL: str = REASON_MAINTAIN_NORMAL

    def recommend(
        self,
        workload: WorkloadState,
        system: SystemState,
        min_capacity_bytes: int,
        max_capacity_bytes: int,
        decision_id: Optional[str] = None,
    ) -> Decision:
        """Evaluate workload and system state to recommend a capacity decision.

        Args:
            workload: Current snapshot of observed workload metrics.
            system: Current snapshot of system cache usage and capacity.
            min_capacity_bytes: Minimum permitted logical cache capacity in bytes (> 0).
            max_capacity_bytes: Maximum permitted logical cache capacity in bytes (> 0).
            decision_id: Optional unique identifier for this decision.

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
        )

        utilization = system.cache_usage_bytes / system.cache_capacity_bytes

        # Priority 1: Scale-up rules
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
        # Priority 2: Scale-down rule
        elif (
            utilization <= self.LOW_UTILIZATION_THRESHOLD
            and workload.hit_rate >= self.HIGH_HIT_RATE_THRESHOLD
        ):
            action = CapacityAction.SCALE_DOWN
            reason = self.REASON_SCALE_DOWN_LOW_UTILIZATION
            raw_capacity = math.floor(
                system.cache_capacity_bytes * (1.0 - self.SCALE_DOWN_PERCENTAGE)
            )
        # Priority 3: Default maintain rule
        else:
            action = CapacityAction.MAINTAIN
            reason = self.REASON_MAINTAIN_NORMAL
            raw_capacity = system.cache_capacity_bytes

        # Clamp capacity within [min_capacity_bytes, max_capacity_bytes]
        recommended_capacity = max(
            min_capacity_bytes, min(raw_capacity, max_capacity_bytes)
        )

        return Decision(
            object_scores={},
            eviction_keys=[],
            capacity_action=action,
            recommended_capacity_bytes=recommended_capacity,
            reason=reason,
            decision_id=decision_id,
            timestamp=system.timestamp,
            version="v1",
        )

    def __call__(
        self,
        workload: WorkloadState,
        system: SystemState,
        min_capacity_bytes: int,
        max_capacity_bytes: int,
        decision_id: Optional[str] = None,
    ) -> Decision:
        """Allow calling the controller instance directly."""
        return self.recommend(
            workload=workload,
            system=system,
            min_capacity_bytes=min_capacity_bytes,
            max_capacity_bytes=max_capacity_bytes,
            decision_id=decision_id,
        )

    @staticmethod
    def _validate_inputs(
        workload: WorkloadState,
        system: SystemState,
        min_capacity_bytes: int,
        max_capacity_bytes: int,
    ) -> None:
        """Validate controller arguments strictly."""
        if not isinstance(workload, WorkloadState):
            t_name = type(workload).__name__
            raise ValueError(
                f"workload must be an instance of WorkloadState, got {t_name}"
            )
        if not isinstance(system, SystemState):
            t_name = type(system).__name__
            raise ValueError(f"system must be an instance of SystemState, got {t_name}")

        if isinstance(min_capacity_bytes, bool) or not isinstance(
            min_capacity_bytes, int
        ):
            raise ValueError(
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
            raise ValueError(
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
