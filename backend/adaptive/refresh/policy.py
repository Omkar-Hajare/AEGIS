"""Refresh policy for the Adaptive Cache System.

Determines whether cached objects should be refreshed from backend data sources
based on temporal staleness and workload-adaptive thresholds.

Refresh vs. Eviction:
- Refresh indicates data staleness: an object has aged and its content should be
  revalidated or updated from the backend without necessarily dropping it from RAM.
- Eviction manages capacity: when cache RAM is constrained, lower-value objects are
  discarded according to retention score and target capacity.
- Retrieval cost (retrieval_cost_ms) reflects regeneration expense and influences
  eviction priority, but does not dictate whether data is stale.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from datetime import datetime

from contracts.schemas.cache import CacheObject
from contracts.schemas.enums import WorkloadType
from contracts.schemas.system import SystemState
from contracts.schemas.workload import WorkloadState

DEFAULT_REFRESH_AFTER_SECONDS: float = 300.0
DEFAULT_AGGRESSIVE_MULTIPLIER: float = 0.5


class RefreshPolicyValidationError(ValueError, TypeError):
    """Raised when an argument passed to RefreshPolicy is invalid."""


class RefreshPolicy:
    """Pure, deterministic, telemetry-driven refresh decision policy for cached objects.

    Determines whether cached objects should be refreshed from backend data sources
    based on continuous temporal staleness, access frequency, recency, popularity trends,
    retrieval economics, and memory pressure.

    Refresh vs. Eviction:
    - Refresh indicates data staleness: an object has aged and its content should be
      revalidated or updated from the backend without necessarily dropping it from RAM.
    - Eviction manages capacity: when cache RAM is constrained, lower-value objects are
      discarded according to retention score and target capacity.
    - Retrieval cost reflects backend regeneration expense and increases the value of
      keeping an accurate, proactive cached representation.
    """

    DEFAULT_REFRESH_AFTER_SECONDS: float = DEFAULT_REFRESH_AFTER_SECONDS
    DEFAULT_AGGRESSIVE_MULTIPLIER: float = DEFAULT_AGGRESSIVE_MULTIPLIER

    @classmethod
    def compute_urgency(
        cls,
        object: CacheObject,
        now: datetime,
        workload_type: WorkloadType | str | None = None,
        refresh_after_seconds: float = DEFAULT_REFRESH_AFTER_SECONDS,
        *,
        workload: WorkloadState | None = None,
        system: SystemState | None = None,
        features: Mapping[str, float] | None = None,
        previous_access_count: int | None = None,
    ) -> float:
        """Compute the continuous refresh urgency in [0.0, 1.0] for a cached object.

        Higher urgency indicates higher priority to refresh from the backend origin.

        Mathematical Formulation:
            Urgency = clamp(p_age * M_value, 0.0, 1.0)

            1. Temporal Staleness:
               age = max(0.0, (now - object.last_accessed).total_seconds())
               p_age = 1.0 - 2^(-age / tau_eff) in [0.0, 1.0)
               (p_age reaches exactly 0.50 when age == tau_eff)

            2. Contextual Time Constant (tau_eff):
               - If workload telemetry is provided, dynamically compressed by
                 request velocity and write activity.
               - Otherwise falls back to workload_type nominal threshold scaling.

            3. Access Frequency Factor (p_freq):
               - Higher access frequency raises urgency to keep hot items fresh.
               - Normalized against neutral single-access reference.

            4. Popularity Trend Factor (p_trend):
               - Surging access activity raises refresh urgency proactively.
               - Declining activity dampens refresh urgency.

            5. Retrieval Economics (p_cost, p_lat):
               - Expensive-to-regenerate items gain higher refresh urgency to avoid
                 devastating backend misses.
               - Modulated by current backend latency pressure.

            6. Memory Pressure Dampening (delta_mem):
               - Under high memory utilization, refresh urgency for cold objects
                 is suppressed to preserve RAM and backend bandwidth for eviction.

        Args:
            object: Target CacheObject instance with timezone-aware last_accessed.
            now: Current timezone-aware reference datetime.
            workload_type: Optional workload classification for nominal scaling.
            refresh_after_seconds: Base staleness threshold in seconds (> 0).
            workload: Optional WorkloadState for continuous telemetry scaling.
            system: Optional SystemState for memory pressure modulation.
            features: Optional pre-extracted object feature mapping.
            previous_access_count: Optional prior window access count for trend estimation.

        Returns:
            Continuous refresh urgency as a float in [0.0, 1.0].
        """
        cls._validate_object(object)
        cls._validate_now(now)
        cls._validate_threshold(refresh_after_seconds)
        wt = cls._validate_workload_type(workload_type)
        cls._validate_telemetry(workload, system, features, previous_access_count)

        # 1. Temporal age calculation (clamped to >= 0.0 for future timestamps)
        age_seconds = max(0.0, (now - object.last_accessed).total_seconds())
        if age_seconds <= 0.0:
            return 0.0

        # 2. Continuous time constant (tau_eff)
        tau_base = float(refresh_after_seconds)
        if workload is not None and math.isfinite(workload.request_rate):
            # Continuous workload scaling based on request velocity and write activity
            req_rate = max(0.0, float(workload.request_rate))
            p_rate = min(1.0, req_rate / 200.0)

            w_ratio = 0.50
            if workload.metrics and isinstance(workload.metrics, dict):
                w_val = workload.metrics.get("write_ratio")
                if (
                    w_val is not None
                    and isinstance(w_val, (int, float))
                    and math.isfinite(w_val)
                ):
                    w_ratio = max(0.0, min(1.0, float(w_val)))

            scale = 1.0 - 0.40 * p_rate * (0.50 + 0.50 * w_ratio)
            tau_eff = tau_base * scale
        else:
            tau_eff = cls.refresh_threshold(
                workload_type=wt,
                base_threshold_seconds=tau_base,
            )

        # Base temporal staleness: reaches exactly 0.50 when age == tau_eff
        p_age = 1.0 - math.pow(2.0, -age_seconds / tau_eff)

        # 3. Frequency signal (higher access -> higher refresh urgency)
        if features and "frequency" in features:
            p_freq = max(0.0, min(1.0, float(features["frequency"])))
        else:
            cnt = max(0, object.access_count)
            p_freq = cnt / (cnt + 10.0)
        p_freq_ref = 1.0 / (1.0 + 10.0)  # ~0.090909
        delta_freq = 0.50 * (p_freq - p_freq_ref)

        # 4. Popularity trend signal (surging demand -> proactive refresh)
        if features and "popularity_trend" in features:
            p_trend = max(0.0, min(1.0, float(features["popularity_trend"])))
        elif previous_access_count is not None:
            tot = object.access_count + previous_access_count
            diff = object.access_count - previous_access_count
            p_trend = (
                max(0.0, min(1.0, 0.50 + 0.50 * (diff / tot))) if tot > 0 else 0.50
            )
        else:
            p_trend = 0.50
        delta_trend = 0.40 * (p_trend - 0.50)

        # 5. Retrieval cost & backend latency signal
        if features and "retrieval_cost" in features:
            p_cost = max(0.0, min(1.0, float(features["retrieval_cost"])))
        else:
            cost = max(0.0, float(object.retrieval_cost_ms))
            p_cost = cost / (cost + 50.0)
        p_cost_ref = 10.0 / (10.0 + 50.0)  # ~0.166667

        if workload is not None and math.isfinite(workload.backend_latency_ms):
            lat = max(0.0, float(workload.backend_latency_ms))
            p_lat = lat / (lat + 50.0)
        else:
            p_lat = 0.50
        delta_cost = 0.35 * (p_cost - p_cost_ref) * (0.50 + 0.50 * p_lat)

        # 6. Memory pressure signal (suppresses refresh of cold data under RAM constraints)
        if (
            system is not None
            and system.cache_capacity_bytes > 0
            and math.isfinite(system.cache_usage_bytes)
        ):
            util = max(0.0, float(system.cache_usage_bytes)) / float(
                system.cache_capacity_bytes
            )
            m_press = max(0.0, min(1.0, util))
        else:
            m_press = 0.50
        delta_mem = -0.30 * (m_press - 0.50) * (1.0 - p_freq)

        # 7. Value multiplier and final bounded urgency
        m_val = max(
            0.20, min(3.00, 1.0 + delta_freq + delta_trend + delta_cost + delta_mem)
        )
        urgency = max(0.0, min(1.0, p_age * m_val))

        return float(urgency)

    @classmethod
    def should_refresh(
        cls,
        object: CacheObject,
        now: datetime,
        workload_type: WorkloadType | str | None = None,
        refresh_after_seconds: float = DEFAULT_REFRESH_AFTER_SECONDS,
        *,
        workload: WorkloadState | None = None,
        system: SystemState | None = None,
        features: Mapping[str, float] | None = None,
        previous_access_count: int | None = None,
        urgency_threshold: float = 0.50,
    ) -> bool:
        """Decide whether a cached object should be refreshed from its backend source.

        Evaluates continuous refresh urgency against a decision boundary.

        Args:
            object: Target CacheObject instance with timezone-aware last_accessed.
            now: Current timezone-aware reference datetime.
            workload_type: Optional workload classification for nominal scaling.
            refresh_after_seconds: Base staleness threshold in seconds (> 0).
            workload: Optional WorkloadState for continuous telemetry scaling.
            system: Optional SystemState for memory pressure modulation.
            features: Optional pre-extracted object feature mapping.
            previous_access_count: Optional prior window access count for trend estimation.
            urgency_threshold: Decision boundary in [0.0, 1.0] (default 0.50).

        Returns:
            True if computed refresh urgency >= urgency_threshold, False otherwise.

        Raises:
            RefreshPolicyValidationError: If arguments are invalid, non-finite,
                or naive datetimes.
        """
        cls._validate_urgency_threshold(urgency_threshold)

        urgency = cls.compute_urgency(
            object=object,
            now=now,
            workload_type=workload_type,
            refresh_after_seconds=refresh_after_seconds,
            workload=workload,
            system=system,
            features=features,
            previous_access_count=previous_access_count,
        )

        return bool(urgency >= urgency_threshold)

    @classmethod
    def refresh_threshold(
        cls,
        workload_type: WorkloadType | str | None,
        base_threshold_seconds: float = DEFAULT_REFRESH_AFTER_SECONDS,
    ) -> float:
        """Return the nominal refresh threshold in seconds for a given workload.

        Preserved for backwards compatibility with existing consumers and static
        baseline calibration.

        Args:
            workload_type: Workload classification or None.
            base_threshold_seconds: Base threshold in seconds (> 0).

        Returns:
            Nominal threshold in seconds as a float.

        Raises:
            RefreshPolicyValidationError: If workload_type or threshold is invalid.
        """
        cls._validate_threshold(base_threshold_seconds)
        wt = cls._validate_workload_type(workload_type)

        if wt in (WorkloadType.SPIKE, WorkloadType.POPULARITY_SHIFT):
            return float(base_threshold_seconds) * cls.DEFAULT_AGGRESSIVE_MULTIPLIER

        return float(base_threshold_seconds)

    def __call__(
        self,
        object: CacheObject,
        now: datetime,
        workload_type: WorkloadType | str | None = None,
        refresh_after_seconds: float = DEFAULT_REFRESH_AFTER_SECONDS,
        *,
        workload: WorkloadState | None = None,
        system: SystemState | None = None,
        features: Mapping[str, float] | None = None,
        previous_access_count: int | None = None,
        urgency_threshold: float = 0.50,
    ) -> bool:
        """Allow calling the policy instance directly."""
        return self.should_refresh(
            object=object,
            now=now,
            workload_type=workload_type,
            refresh_after_seconds=refresh_after_seconds,
            workload=workload,
            system=system,
            features=features,
            previous_access_count=previous_access_count,
            urgency_threshold=urgency_threshold,
        )

    @staticmethod
    def _validate_object(object: CacheObject) -> None:
        """Validate that object is a valid CacheObject instance."""
        if not isinstance(object, CacheObject):
            raise RefreshPolicyValidationError(
                f"object must be a CacheObject, got {type(object).__name__}"
            )

    @staticmethod
    def _validate_now(now: datetime) -> None:
        """Validate that now is a timezone-aware datetime."""
        if not isinstance(now, datetime):
            raise RefreshPolicyValidationError(
                f"now must be a datetime, got {type(now).__name__}"
            )
        if now.tzinfo is None or now.tzinfo.utcoffset(now) is None:
            raise RefreshPolicyValidationError(
                "now must be a timezone-aware datetime; received naive datetime"
            )

    @staticmethod
    def _validate_threshold(threshold: float) -> None:
        """Validate that threshold is a finite positive numeric value."""
        if isinstance(threshold, bool) or not isinstance(threshold, (int, float)):
            raise RefreshPolicyValidationError(
                f"refresh_after_seconds must be numeric, got {type(threshold).__name__}"
            )
        if not math.isfinite(threshold):
            raise RefreshPolicyValidationError(
                f"refresh_after_seconds must be finite, got {threshold}"
            )
        if threshold <= 0.0:
            raise RefreshPolicyValidationError(
                f"refresh_after_seconds must be greater than 0, got {threshold}"
            )

    @staticmethod
    def _validate_urgency_threshold(urgency_threshold: float) -> None:
        """Validate urgency threshold is a finite number in [0.0, 1.0]."""
        if isinstance(urgency_threshold, bool) or not isinstance(
            urgency_threshold, (int, float)
        ):
            raise RefreshPolicyValidationError(
                f"urgency_threshold must be numeric, got {type(urgency_threshold).__name__}"
            )
        if not math.isfinite(urgency_threshold):
            raise RefreshPolicyValidationError(
                f"urgency_threshold must be finite, got {urgency_threshold}"
            )
        if not (0.0 <= urgency_threshold <= 1.0):
            raise RefreshPolicyValidationError(
                f"urgency_threshold must be in [0.0, 1.0], got {urgency_threshold}"
            )

    @staticmethod
    def _validate_telemetry(
        workload: WorkloadState | None,
        system: SystemState | None,
        features: Mapping[str, float] | None,
        previous_access_count: int | None,
    ) -> None:
        """Validate optional telemetry and contextual parameters."""
        if workload is not None and not isinstance(workload, WorkloadState):
            raise RefreshPolicyValidationError(
                f"workload must be a WorkloadState or None, got {type(workload).__name__}"
            )
        if system is not None and not isinstance(system, SystemState):
            raise RefreshPolicyValidationError(
                f"system must be a SystemState or None, got {type(system).__name__}"
            )
        if features is not None and not isinstance(features, Mapping):
            raise RefreshPolicyValidationError(
                f"features must be a Mapping or None, got {type(features).__name__}"
            )
        if previous_access_count is not None:
            if isinstance(previous_access_count, bool) or not isinstance(
                previous_access_count, int
            ):
                raise RefreshPolicyValidationError(
                    f"previous_access_count must be an integer, got {type(previous_access_count).__name__}"
                )
            if previous_access_count < 0:
                raise RefreshPolicyValidationError(
                    f"previous_access_count must be >= 0, got {previous_access_count}"
                )

    @staticmethod
    def _validate_workload_type(
        workload_type: WorkloadType | str | None,
    ) -> WorkloadType | None:
        """Validate and parse workload type."""
        if workload_type is None:
            return None
        if isinstance(workload_type, WorkloadType):
            return workload_type
        if isinstance(workload_type, str):
            try:
                return WorkloadType(workload_type)
            except ValueError:
                raise RefreshPolicyValidationError(
                    f"Unsupported workload_type: {workload_type!r}"
                )
        raise RefreshPolicyValidationError(
            "workload_type must be WorkloadType, str, or None, "
            f"got {type(workload_type).__name__}"
        )
