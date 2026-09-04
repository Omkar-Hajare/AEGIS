"""Cost model for the Adaptive Cache System.

Provides pure, platform-aware cost and economic evaluation for cached objects:
- Normalized retrieval cost signals across candidate objects.
- Backend cost savings estimation from avoided backend requests and execution latency.
- Cache memory RAM cost estimation.
- Net economic benefit estimation (Backend Cost Saved - Cache RAM Cost).
- Value density calculation (Score / (Size ^ alpha)).

Note:
    All cost metrics and profile parameters represent configurable, simulated
    economic models for algorithmic decision-making and benchmark demonstrations.
    They do NOT represent actual or contractual vendor/cloud pricing.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from typing import Any

from backend.cost.cost_profile import CostModelValidationError, CostProfile
from backend.cost.profiles import DEFAULT_PROFILE
from contracts.schemas.cache import CacheObject

BYTES_PER_GB: int = 1_000_000_000
DEFAULT_BACKEND_COST_PER_REQUEST: float = 0.0
DEFAULT_BACKEND_COST_PER_MS: float = 1.0
DEFAULT_CACHE_RAM_COST_PER_GB_HOUR: float = 0.10
DEFAULT_HOURS: float = 1.0
DEFAULT_ALPHA: float = 1.0
DEFAULT_IDENTICAL_COST_NORMALIZATION: float = 0.5

__all__ = [
    "BYTES_PER_GB",
    "DEFAULT_ALPHA",
    "DEFAULT_BACKEND_COST_PER_MS",
    "DEFAULT_BACKEND_COST_PER_REQUEST",
    "DEFAULT_CACHE_RAM_COST_PER_GB_HOUR",
    "DEFAULT_HOURS",
    "DEFAULT_IDENTICAL_COST_NORMALIZATION",
    "CostModel",
    "CostModelValidationError",
]


class CostModel:
    """Pure, platform-aware cost and economic evaluation model for adaptive caching."""

    BYTES_PER_GB: int = BYTES_PER_GB
    DEFAULT_BACKEND_COST_PER_REQUEST: float = DEFAULT_BACKEND_COST_PER_REQUEST
    DEFAULT_BACKEND_COST_PER_MS: float = DEFAULT_BACKEND_COST_PER_MS
    DEFAULT_CACHE_RAM_COST_PER_GB_HOUR: float = DEFAULT_CACHE_RAM_COST_PER_GB_HOUR
    DEFAULT_HOURS: float = DEFAULT_HOURS
    DEFAULT_ALPHA: float = DEFAULT_ALPHA
    DEFAULT_IDENTICAL_COST_NORMALIZATION: float = DEFAULT_IDENTICAL_COST_NORMALIZATION

    def __init__(self, profile: CostProfile | None = None) -> None:
        """Initialize CostModel with an optional platform CostProfile.

        Args:
            profile: Optional platform CostProfile specifying cost parameters.
                If None, DEFAULT_PROFILE is used.

        Raises:
            CostModelValidationError: If profile is not a CostProfile instance.
        """
        if profile is not None and not isinstance(profile, CostProfile):
            raise CostModelValidationError(
                f"profile must be a CostProfile instance, got {type(profile).__name__}"
            )
        self.profile: CostProfile = profile or DEFAULT_PROFILE

    @staticmethod
    def normalize_retrieval_costs(
        objects: Mapping[str, CacheObject],
    ) -> dict[str, float]:
        """Return min-max normalized retrieval costs in [0, 1] for all objects.

        Args:
            objects: Mapping of cache object key to CacheObject metadata.

        Returns:
            Dictionary mapping cache keys to normalized retrieval costs in [0, 1].
            Returns empty dict for empty input, or 0.5 for all objects if costs
            are identical.

        Raises:
            CostModelValidationError: If objects is not a mapping or contains
                invalid entries.
        """
        if not isinstance(objects, (dict, Mapping)):
            raise CostModelValidationError(
                f"objects must be a mapping, got {type(objects).__name__}"
            )

        if not objects:
            return {}

        costs: dict[str, float] = {}
        for key, obj in objects.items():
            if not isinstance(key, str):
                raise CostModelValidationError(
                    f"Object key must be a string, got {type(key).__name__}"
                )
            if not isinstance(obj, CacheObject):
                raise CostModelValidationError(
                    f"Object value for key {key!r} must be a CacheObject, "
                    f"got {type(obj).__name__}"
                )
            if key != obj.key:
                raise CostModelValidationError(
                    f"Mapping key {key!r} does not match CacheObject.key {obj.key!r}"
                )
            costs[key] = float(obj.retrieval_cost_ms)

        min_cost = min(costs.values())
        max_cost = max(costs.values())

        if min_cost == max_cost:
            return {k: DEFAULT_IDENTICAL_COST_NORMALIZATION for k in costs}

        cost_range = max_cost - min_cost
        return {k: (c - min_cost) / cost_range for k, c in costs.items()}

    def estimate_backend_cost_saved(
        self,
        object: CacheObject,
        cached_requests: int,
        backend_cost_per_ms: float | None = None,
        backend_cost_per_request: float | None = None,
    ) -> float:
        """Estimate backend regeneration cost avoided by serving requests from cache.

        Formula:
            saved = cached_requests * (cost_per_request + retrieval_cost_ms * cost_per_ms)

        Args:
            object: Target CacheObject instance.
            cached_requests: Number of requests served from cache (>= 0, non-bool).
            backend_cost_per_ms: Variable cost rate per millisecond of retrieval cost (>= 0).
                If None, uses active CostProfile.backend_cost_per_ms.
            backend_cost_per_request: Base overhead cost rate per avoided request (>= 0).
                If None, uses active CostProfile.backend_cost_per_request.

        Returns:
            Calculated cost savings as a float.

        Raises:
            CostModelValidationError: If any argument is invalid or out of bounds.
        """
        # Support invocation both as instance method and direct static/class call
        if not isinstance(self, CostModel):
            actual_obj: Any = self
            actual_requests: Any = object
            cost_ms_arg = (
                DEFAULT_BACKEND_COST_PER_MS
                if cached_requests is None
                else cached_requests
            )
            cost_req_arg = (
                DEFAULT_BACKEND_COST_PER_REQUEST
                if backend_cost_per_ms is None
                else backend_cost_per_ms
            )
            profile_cost_ms = DEFAULT_BACKEND_COST_PER_MS
            profile_cost_req = DEFAULT_BACKEND_COST_PER_REQUEST
        else:
            actual_obj = object
            actual_requests = cached_requests
            cost_ms_arg = backend_cost_per_ms
            cost_req_arg = backend_cost_per_request
            profile_cost_ms = self.profile.backend_cost_per_ms
            profile_cost_req = self.profile.backend_cost_per_request

        if not isinstance(actual_obj, CacheObject):
            raise CostModelValidationError(
                f"object must be a CacheObject, got {type(actual_obj).__name__}"
            )

        if isinstance(actual_requests, bool) or not isinstance(actual_requests, int):
            raise CostModelValidationError(
                "cached_requests must be an integer, "
                f"got {type(actual_requests).__name__}"
            )
        if actual_requests < 0:
            raise CostModelValidationError(
                f"cached_requests must be non-negative, got {actual_requests}"
            )

        # Resolve effective cost rates
        if cost_ms_arg is None:
            effective_cost_ms = float(profile_cost_ms)
        else:
            if isinstance(cost_ms_arg, bool) or not isinstance(
                cost_ms_arg, (int, float)
            ):
                raise CostModelValidationError(
                    "backend_cost_per_ms must be numeric, "
                    f"got {type(cost_ms_arg).__name__}"
                )
            if not math.isfinite(cost_ms_arg):
                raise CostModelValidationError(
                    f"backend_cost_per_ms must be finite, got {cost_ms_arg}"
                )
            if cost_ms_arg < 0.0:
                raise CostModelValidationError(
                    f"backend_cost_per_ms must be non-negative, got {cost_ms_arg}"
                )
            effective_cost_ms = float(cost_ms_arg)

        if cost_req_arg is None:
            effective_cost_req = float(profile_cost_req)
        else:
            if isinstance(cost_req_arg, bool) or not isinstance(
                cost_req_arg, (int, float)
            ):
                raise CostModelValidationError(
                    "backend_cost_per_request must be numeric, "
                    f"got {type(cost_req_arg).__name__}"
                )
            if not math.isfinite(cost_req_arg):
                raise CostModelValidationError(
                    f"backend_cost_per_request must be finite, got {cost_req_arg}"
                )
            if cost_req_arg < 0.0:
                raise CostModelValidationError(
                    f"backend_cost_per_request must be non-negative, got {cost_req_arg}"
                )
            effective_cost_req = float(cost_req_arg)

        avoided_request_overhead = float(actual_requests) * effective_cost_req
        avoided_latency_cost = (
            float(actual_obj.retrieval_cost_ms)
            * float(actual_requests)
            * effective_cost_ms
        )
        return avoided_request_overhead + avoided_latency_cost

    def estimate_cache_ram_cost(
        self,
        size_bytes: int,
        cache_ram_cost_per_gb_hour: float | None = None,
        hours: float = DEFAULT_HOURS,
    ) -> float:
        """Estimate the RAM cost of retaining an object in cache.

        Formula: (size_bytes / 1_000_000_000) * cache_ram_cost_per_gb_hour * hours

        Args:
            size_bytes: Object size in bytes (>= 0, non-bool).
            cache_ram_cost_per_gb_hour: Cost rate per decimal gigabyte-hour (>= 0).
                If None, uses active CostProfile.cache_memory_cost_per_gb_hour.
            hours: Retention duration in hours (>= 0).

        Returns:
            Calculated RAM cost as a float.

        Raises:
            CostModelValidationError: If any argument is invalid or out of bounds.
        """
        # Support invocation both as instance method and direct static/class call
        if not isinstance(self, CostModel):
            actual_size: Any = self
            rate_arg = cache_ram_cost_per_gb_hour
            hours_arg = hours
            profile_rate = DEFAULT_CACHE_RAM_COST_PER_GB_HOUR
        else:
            actual_size = size_bytes
            rate_arg = cache_ram_cost_per_gb_hour
            hours_arg = hours
            profile_rate = self.profile.cache_memory_cost_per_gb_hour

        if isinstance(actual_size, bool) or not isinstance(actual_size, int):
            raise CostModelValidationError(
                f"size_bytes must be an integer, got {type(actual_size).__name__}"
            )
        if actual_size < 0:
            raise CostModelValidationError(
                f"size_bytes must be non-negative, got {actual_size}"
            )

        if rate_arg is None:
            effective_rate = float(profile_rate)
        else:
            if isinstance(rate_arg, bool) or not isinstance(rate_arg, (int, float)):
                raise CostModelValidationError(
                    "cache_ram_cost_per_gb_hour must be numeric, "
                    f"got {type(rate_arg).__name__}"
                )
            if not math.isfinite(rate_arg):
                raise CostModelValidationError(
                    f"cache_ram_cost_per_gb_hour must be finite, got {rate_arg}"
                )
            if rate_arg < 0.0:
                raise CostModelValidationError(
                    f"cache_ram_cost_per_gb_hour must be non-negative, got {rate_arg}"
                )
            effective_rate = float(rate_arg)

        if isinstance(hours_arg, bool) or not isinstance(hours_arg, (int, float)):
            raise CostModelValidationError(
                f"hours must be numeric, got {type(hours_arg).__name__}"
            )
        if not math.isfinite(hours_arg):
            raise CostModelValidationError(f"hours must be finite, got {hours_arg}")
        if hours_arg < 0.0:
            raise CostModelValidationError(
                f"hours must be non-negative, got {hours_arg}"
            )

        return (
            (float(actual_size) / float(BYTES_PER_GB))
            * effective_rate
            * float(hours_arg)
        )

    def estimate_net_benefit(
        self,
        object: CacheObject,
        cached_requests: int,
        backend_cost_per_ms: float | None = None,
        cache_ram_cost_per_gb_hour: float | None = None,
        hours: float = DEFAULT_HOURS,
        backend_cost_per_request: float | None = None,
    ) -> float:
        """Estimate net economic benefit of retaining an object in cache.

        Formula: Net Benefit = Backend Cost Saved - Cache RAM Cost

        Positive values indicate retaining the object is economically advantageous.
        Negative values indicate RAM retention cost exceeds backend regeneration
        savings.

        Args:
            object: Target CacheObject instance.
            cached_requests: Number of requests served from cache.
            backend_cost_per_ms: Backend cost rate per millisecond.
            cache_ram_cost_per_gb_hour: RAM cost rate per GB-hour.
            hours: Duration in hours.
            backend_cost_per_request: Base overhead cost rate per avoided request.

        Returns:
            Net economic benefit as a float.
        """
        model_instance = self if isinstance(self, CostModel) else CostModel()
        actual_obj = object if isinstance(self, CostModel) else self
        actual_requests = cached_requests if isinstance(self, CostModel) else object
        actual_cost_ms = (
            backend_cost_per_ms if isinstance(self, CostModel) else cached_requests
        )
        actual_ram_rate = (
            cache_ram_cost_per_gb_hour
            if isinstance(self, CostModel)
            else backend_cost_per_ms
        )
        actual_hours = (
            hours if isinstance(self, CostModel) else cache_ram_cost_per_gb_hour
        )
        actual_cost_req = (
            backend_cost_per_request if isinstance(self, CostModel) else hours
        )

        eff_hours = DEFAULT_HOURS if actual_hours is None else actual_hours

        saved = model_instance.estimate_backend_cost_saved(
            object=actual_obj,
            cached_requests=actual_requests,
            backend_cost_per_ms=actual_cost_ms,
            backend_cost_per_request=actual_cost_req,
        )
        ram_cost = model_instance.estimate_cache_ram_cost(
            size_bytes=actual_obj.size_bytes,
            cache_ram_cost_per_gb_hour=actual_ram_rate,
            hours=eff_hours,
        )
        return saved - ram_cost

    @staticmethod
    def value_density(
        score: float,
        size_bytes: int,
        alpha: float = DEFAULT_ALPHA,
    ) -> float:
        """Calculate value density of a cache object: Score / (Size ^ alpha).

        Args:
            score: Normalized utility score in [0, 1].
            size_bytes: Object size in bytes (> 0, non-bool).
            alpha: Size penalty scaling exponent (> 0, finite, non-bool).

        Returns:
            Value density as a float.

        Raises:
            CostModelValidationError: If any argument is invalid or out of bounds.
        """
        if isinstance(score, bool) or not isinstance(score, (int, float)):
            raise CostModelValidationError(
                f"score must be numeric, got {type(score).__name__}"
            )
        if not math.isfinite(score):
            raise CostModelValidationError(f"score must be finite, got {score}")
        if score < 0.0 or score > 1.0:
            raise CostModelValidationError(f"score must be in [0, 1], got {score}")

        if isinstance(size_bytes, bool) or not isinstance(size_bytes, int):
            raise CostModelValidationError(
                f"size_bytes must be an integer, got {type(size_bytes).__name__}"
            )
        if size_bytes <= 0:
            raise CostModelValidationError(
                f"size_bytes must be a positive integer, got {size_bytes}"
            )

        if isinstance(alpha, bool) or not isinstance(alpha, (int, float)):
            raise CostModelValidationError(
                f"alpha must be numeric, got {type(alpha).__name__}"
            )
        if not math.isfinite(alpha):
            raise CostModelValidationError(f"alpha must be finite, got {alpha}")
        if alpha <= 0.0:
            raise CostModelValidationError(
                f"alpha must be a positive number, got {alpha}"
            )

        return float(score) / (float(size_bytes) ** float(alpha))
