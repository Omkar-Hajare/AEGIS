"""Cost model for the Adaptive Cache System.

Provides pure, data-driven cost and economic evaluation for cached objects:
- Normalized retrieval cost signals across candidate objects.
- Backend cost savings estimation from avoided backend requests.
- Cache memory RAM cost estimation.
- Net economic benefit estimation (Backend Cost Saved - Cache RAM Cost).
- Value density calculation (Score / (Size ^ alpha)).
"""

from __future__ import annotations

import math
from collections.abc import Mapping

from contracts.schemas.cache import CacheObject

BYTES_PER_GB: int = 1_000_000_000
DEFAULT_BACKEND_COST_PER_MS: float = 1.0
DEFAULT_CACHE_RAM_COST_PER_GB_HOUR: float = 0.10
DEFAULT_HOURS: float = 1.0
DEFAULT_ALPHA: float = 1.0
DEFAULT_IDENTICAL_COST_NORMALIZATION: float = 0.5


class CostModelValidationError(ValueError, TypeError):
    """Raised when an argument passed to the cost model is invalid."""


class CostModel:
    """Pure, stateless cost and economic evaluation model for adaptive caching."""

    BYTES_PER_GB: int = BYTES_PER_GB
    DEFAULT_BACKEND_COST_PER_MS: float = DEFAULT_BACKEND_COST_PER_MS
    DEFAULT_CACHE_RAM_COST_PER_GB_HOUR: float = DEFAULT_CACHE_RAM_COST_PER_GB_HOUR
    DEFAULT_HOURS: float = DEFAULT_HOURS
    DEFAULT_ALPHA: float = DEFAULT_ALPHA
    DEFAULT_IDENTICAL_COST_NORMALIZATION: float = DEFAULT_IDENTICAL_COST_NORMALIZATION

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

    @staticmethod
    def estimate_backend_cost_saved(
        object: CacheObject,
        cached_requests: int,
        backend_cost_per_ms: float = DEFAULT_BACKEND_COST_PER_MS,
    ) -> float:
        """Estimate backend regeneration cost avoided by serving requests from cache.

        Formula: retrieval_cost_ms * cached_requests * backend_cost_per_ms

        Args:
            object: Target CacheObject instance.
            cached_requests: Number of requests served from cache (>= 0, non-bool).
            backend_cost_per_ms: Backend cost rate per millisecond of
                retrieval cost (>= 0).

        Returns:
            Calculated cost savings as a float.

        Raises:
            CostModelValidationError: If any argument is invalid or out of bounds.
        """
        if not isinstance(object, CacheObject):
            raise CostModelValidationError(
                f"object must be a CacheObject, got {type(object).__name__}"
            )

        if isinstance(cached_requests, bool) or not isinstance(cached_requests, int):
            raise CostModelValidationError(
                "cached_requests must be an integer, "
                f"got {type(cached_requests).__name__}"
            )
        if cached_requests < 0:
            raise CostModelValidationError(
                f"cached_requests must be non-negative, got {cached_requests}"
            )

        if isinstance(backend_cost_per_ms, bool) or not isinstance(
            backend_cost_per_ms, (int, float)
        ):
            raise CostModelValidationError(
                "backend_cost_per_ms must be numeric, "
                f"got {type(backend_cost_per_ms).__name__}"
            )
        if not math.isfinite(backend_cost_per_ms):
            raise CostModelValidationError(
                f"backend_cost_per_ms must be finite, got {backend_cost_per_ms}"
            )
        if backend_cost_per_ms < 0.0:
            raise CostModelValidationError(
                f"backend_cost_per_ms must be non-negative, got {backend_cost_per_ms}"
            )

        return (
            float(object.retrieval_cost_ms)
            * float(cached_requests)
            * float(backend_cost_per_ms)
        )

    @staticmethod
    def estimate_cache_ram_cost(
        size_bytes: int,
        cache_ram_cost_per_gb_hour: float,
        hours: float = DEFAULT_HOURS,
    ) -> float:
        """Estimate the RAM cost of retaining an object in cache.

        Formula: (size_bytes / 1_000_000_000) * cache_ram_cost_per_gb_hour * hours

        Args:
            size_bytes: Object size in bytes (>= 0, non-bool).
            cache_ram_cost_per_gb_hour: Cost rate per decimal gigabyte-hour (>= 0).
            hours: Retention duration in hours (>= 0).

        Returns:
            Calculated RAM cost as a float.

        Raises:
            CostModelValidationError: If any argument is invalid or out of bounds.
        """
        if isinstance(size_bytes, bool) or not isinstance(size_bytes, int):
            raise CostModelValidationError(
                f"size_bytes must be an integer, got {type(size_bytes).__name__}"
            )
        if size_bytes < 0:
            raise CostModelValidationError(
                f"size_bytes must be non-negative, got {size_bytes}"
            )

        if isinstance(cache_ram_cost_per_gb_hour, bool) or not isinstance(
            cache_ram_cost_per_gb_hour, (int, float)
        ):
            raise CostModelValidationError(
                "cache_ram_cost_per_gb_hour must be numeric, "
                f"got {type(cache_ram_cost_per_gb_hour).__name__}"
            )
        if not math.isfinite(cache_ram_cost_per_gb_hour):
            raise CostModelValidationError(
                "cache_ram_cost_per_gb_hour must be finite, "
                f"got {cache_ram_cost_per_gb_hour}"
            )
        if cache_ram_cost_per_gb_hour < 0.0:
            raise CostModelValidationError(
                "cache_ram_cost_per_gb_hour must be non-negative, "
                f"got {cache_ram_cost_per_gb_hour}"
            )

        if isinstance(hours, bool) or not isinstance(hours, (int, float)):
            raise CostModelValidationError(
                f"hours must be numeric, got {type(hours).__name__}"
            )
        if not math.isfinite(hours):
            raise CostModelValidationError(f"hours must be finite, got {hours}")
        if hours < 0.0:
            raise CostModelValidationError(f"hours must be non-negative, got {hours}")

        return (
            (float(size_bytes) / float(BYTES_PER_GB))
            * float(cache_ram_cost_per_gb_hour)
            * float(hours)
        )

    @classmethod
    def estimate_net_benefit(
        cls,
        object: CacheObject,
        cached_requests: int,
        backend_cost_per_ms: float = DEFAULT_BACKEND_COST_PER_MS,
        cache_ram_cost_per_gb_hour: float = DEFAULT_CACHE_RAM_COST_PER_GB_HOUR,
        hours: float = DEFAULT_HOURS,
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

        Returns:
            Net economic benefit as a float.
        """
        saved = cls.estimate_backend_cost_saved(
            object=object,
            cached_requests=cached_requests,
            backend_cost_per_ms=backend_cost_per_ms,
        )
        ram_cost = cls.estimate_cache_ram_cost(
            size_bytes=object.size_bytes,
            cache_ram_cost_per_gb_hour=cache_ram_cost_per_gb_hour,
            hours=hours,
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
