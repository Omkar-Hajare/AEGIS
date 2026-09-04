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
from datetime import datetime

from contracts.schemas.cache import CacheObject
from contracts.schemas.enums import WorkloadType

DEFAULT_REFRESH_AFTER_SECONDS: float = 300.0
DEFAULT_AGGRESSIVE_MULTIPLIER: float = 0.5


class RefreshPolicyValidationError(ValueError, TypeError):
    """Raised when an argument passed to RefreshPolicy is invalid."""


class RefreshPolicy:
    """Pure, deterministic refresh decision policy for cached objects."""

    DEFAULT_REFRESH_AFTER_SECONDS: float = DEFAULT_REFRESH_AFTER_SECONDS
    DEFAULT_AGGRESSIVE_MULTIPLIER: float = DEFAULT_AGGRESSIVE_MULTIPLIER

    @classmethod
    def should_refresh(
        cls,
        object: CacheObject,
        now: datetime,
        workload_type: WorkloadType | str | None = None,
        refresh_after_seconds: float = DEFAULT_REFRESH_AFTER_SECONDS,
    ) -> bool:
        """Decide whether a cached object should be refreshed from its backend source.

        Args:
            object: Target CacheObject instance with timezone-aware last_accessed.
            now: Current timezone-aware reference datetime.
            workload_type: Optional current workload classification.
            refresh_after_seconds: Base staleness threshold in seconds (> 0).

        Returns:
            True if the object has reached or exceeded its effective refresh
            threshold, False otherwise.

        Raises:
            RefreshPolicyValidationError: If arguments are invalid, non-finite,
                or naive datetimes.
        """
        cls._validate_object(object)
        cls._validate_now(now)
        cls._validate_threshold(refresh_after_seconds)

        effective_threshold = cls.refresh_threshold(
            workload_type=workload_type,
            base_threshold_seconds=refresh_after_seconds,
        )

        age_seconds = max(0.0, (now - object.last_accessed).total_seconds())
        return bool(age_seconds >= effective_threshold)

    @classmethod
    def refresh_threshold(
        cls,
        workload_type: WorkloadType | str | None,
        base_threshold_seconds: float = DEFAULT_REFRESH_AFTER_SECONDS,
    ) -> float:
        """Return the effective refresh threshold in seconds for a given workload.

        Workload-specific adaptations:
        - SPIKE: 50% of base threshold (proactively refreshes fast-moving data).
        - POPULARITY_SHIFT: 50% of base threshold (rapidly aligns with shifting demand).
        - COMPUTE_HEAVY: 100% of base threshold (costly regeneration favors
          retention).
        - READ_HEAVY, STEADY, None: 100% of base threshold.

        Args:
            workload_type: Workload classification or None.
            base_threshold_seconds: Base threshold in seconds (> 0).

        Returns:
            Effective threshold in seconds as a float.

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
    ) -> bool:
        """Allow calling the policy instance directly."""
        return self.should_refresh(
            object=object,
            now=now,
            workload_type=workload_type,
            refresh_after_seconds=refresh_after_seconds,
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
