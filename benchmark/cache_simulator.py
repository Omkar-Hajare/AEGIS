"""In-memory cache simulator for deterministic benchmark evaluation.

Maintains cache state, usage accounting, capacity boundaries, latency metrics,
and orchestrates evictions with a BenchmarkPolicy.
"""

from __future__ import annotations

import math
from typing import Any

from backend.workload.scenario import ScenarioEvent
from benchmark.models import BenchmarkMetrics, BenchmarkResult
from benchmark.policies import BenchmarkPolicy, get_policy_adapter
from benchmark.results import compute_benchmark_metrics
from contracts.schemas.cache import CacheObject


class CacheSimulator:
    """Deterministic, pure in-memory cache simulator for policy benchmarking."""

    def __init__(
        self,
        capacity_bytes: int,
        policy: BenchmarkPolicy | str,
        hit_latency_ms: float = 1.0,
        min_capacity_bytes: int | None = None,
        max_capacity_bytes: int | None = None,
    ) -> None:
        """Initialize CacheSimulator with capacity, policy, and latency parameters.

        Args:
            capacity_bytes: Configured cache capacity in bytes (> 0).
            policy: Policy adapter instance or registered policy name.
            hit_latency_ms: Simulated cache hit latency in ms (>= 0.0).
            min_capacity_bytes: Optional lower capacity bound for adaptive scaling.
            max_capacity_bytes: Optional upper capacity bound for adaptive scaling.

        Raises:
            ValueError: If capacity or latency values are non-finite or out of bounds.
            TypeError: If arguments have invalid types or booleans are passed.
        """
        self._validate_inputs(
            capacity_bytes=capacity_bytes,
            hit_latency_ms=hit_latency_ms,
            min_capacity_bytes=min_capacity_bytes,
            max_capacity_bytes=max_capacity_bytes,
        )

        self._capacity_bytes = capacity_bytes
        self._hit_latency_ms = float(hit_latency_ms)
        self._min_capacity_bytes = min_capacity_bytes
        self._max_capacity_bytes = max_capacity_bytes

        self.policy: BenchmarkPolicy = get_policy_adapter(policy)
        self.policy.configure_capacity(
            capacity_bytes=self._capacity_bytes,
            min_capacity_bytes=self._min_capacity_bytes,
            max_capacity_bytes=self._max_capacity_bytes,
        )
        self.policy.reset()

        self._cache: dict[str, CacheObject] = {}
        self._total_requests: int = 0
        self._cache_hits: int = 0
        self._cache_misses: int = 0
        self._backend_requests: int = 0
        self._backend_requests_prevented: int = 0
        self._backend_latency_total_ms: float = 0.0
        self._latencies: list[float] = []
        self._eviction_count: int = 0
        self._peak_cache_usage_bytes: int = 0
        self._oversized_requests: int = 0

    @property
    def capacity_bytes(self) -> int:
        """Configured cache capacity in bytes."""
        return self._capacity_bytes

    @property
    def hit_latency_ms(self) -> float:
        """Simulated hit latency in ms."""
        return self._hit_latency_ms

    @property
    def cache(self) -> dict[str, CacheObject]:
        """Current cache objects dictionary."""
        return dict(self._cache)

    @property
    def current_usage_bytes(self) -> int:
        """Current sum of object sizes in bytes."""
        return sum(obj.size_bytes for obj in self._cache.values())

    @property
    def total_requests(self) -> int:
        """Total requests processed."""
        return self._total_requests

    @property
    def cache_hits(self) -> int:
        """Total cache hits."""
        return self._cache_hits

    @property
    def cache_misses(self) -> int:
        """Total cache misses."""
        return self._cache_misses

    @property
    def eviction_count(self) -> int:
        """Total evicted objects."""
        return self._eviction_count

    @property
    def peak_cache_usage_bytes(self) -> int:
        """Peak cache memory usage in bytes observed."""
        return self._peak_cache_usage_bytes

    @property
    def oversized_requests(self) -> int:
        """Number of requests for objects exceeding total cache capacity."""
        return self._oversized_requests

    def process_event(self, event: ScenarioEvent) -> float:
        """Process a single ScenarioEvent through the cache simulator.

        Args:
            event: The synthetic request event to process.

        Returns:
            The simulated request latency in milliseconds.

        Raises:
            TypeError: If event is not a ScenarioEvent instance.
        """
        if not isinstance(event, ScenarioEvent):
            raise TypeError(
                f"event must be a ScenarioEvent, got {type(event).__name__}"
            )

        self._total_requests += 1

        if event.key in self._cache:
            # --- CACHE HIT ---
            self._cache_hits += 1
            self._backend_requests_prevented += 1
            latency = self._hit_latency_ms
            self._latencies.append(latency)

            obj = self._cache[event.key]
            obj.access_count += 1
            obj.last_accessed = event.timestamp
            if obj.hit_count is not None:
                obj.hit_count += 1
            else:
                obj.hit_count = 1

            self.policy.on_hit(event.key, event, self._cache)
            return latency

        # --- CACHE MISS ---
        self._cache_misses += 1
        self._backend_requests += 1
        self._backend_latency_total_ms += event.backend_latency_ms
        latency = self._hit_latency_ms + event.backend_latency_ms
        self._latencies.append(latency)

        self.policy.on_miss(event.key, event, self._cache)

        # Check for oversized object exceeding total cache capacity
        if event.object_size_bytes > self._capacity_bytes:
            self._oversized_requests += 1
            return latency

        # Check if space must be freed
        current_usage = sum(o.size_bytes for o in self._cache.values())
        if current_usage + event.object_size_bytes > self._capacity_bytes:
            target_capacity = self._capacity_bytes - event.object_size_bytes
            evicted_keys = self.policy.select_evictions(
                self._cache, target_capacity, event
            )
            for k in evicted_keys:
                if k in self._cache:
                    del self._cache[k]
                    self._eviction_count += 1

            # Defensive fallback to ensure capacity bound is strictly met
            current_usage = sum(o.size_bytes for o in self._cache.values())
            if current_usage + event.object_size_bytes > self._capacity_bytes:
                for k in sorted(self._cache.keys()):
                    del self._cache[k]
                    self._eviction_count += 1
                    current_usage = sum(o.size_bytes for o in self._cache.values())
                    if current_usage + event.object_size_bytes <= self._capacity_bytes:
                        break

        # Insert admitted object
        new_obj = CacheObject(
            key=event.key,
            size_bytes=event.object_size_bytes,
            access_count=1,
            last_accessed=event.timestamp,
            retrieval_cost_ms=event.retrieval_cost_ms,
            hit_count=0,
            miss_count=1,
            created_at=event.timestamp,
        )
        self._cache[event.key] = new_obj

        # Update peak usage
        new_usage = sum(o.size_bytes for o in self._cache.values())
        self._peak_cache_usage_bytes = max(self._peak_cache_usage_bytes, new_usage)

        return latency

    def get_metrics(self) -> BenchmarkMetrics:
        """Compute and return the current BenchmarkMetrics."""
        return compute_benchmark_metrics(
            total_requests=self._total_requests,
            cache_hits=self._cache_hits,
            cache_misses=self._cache_misses,
            latencies=self._latencies,
            backend_latency_total_ms=self._backend_latency_total_ms,
            eviction_count=self._eviction_count,
            cache_capacity_bytes=self._capacity_bytes,
            peak_cache_usage_bytes=self._peak_cache_usage_bytes,
        )

    def get_result(
        self,
        scenario_name: str,
        workload_profile: str,
        seed: int,
    ) -> BenchmarkResult:
        """Generate a complete BenchmarkResult for this policy simulation run.

        Args:
            scenario_name: Name of the workload scenario.
            workload_profile: Name of the workload profile.
            seed: Scenario generation random seed.

        Returns:
            Validated BenchmarkResult model.
        """
        metadata: dict[str, Any] = {
            "oversized_requests": self._oversized_requests,
            "final_cached_objects": len(self._cache),
            "final_cache_usage_bytes": sum(o.size_bytes for o in self._cache.values()),
            **self.policy.get_metadata(),
        }

        return BenchmarkResult(
            policy_name=self.policy.name,
            scenario_name=scenario_name,
            workload_profile=workload_profile,
            seed=seed,
            cache_capacity_bytes=self._capacity_bytes,
            metrics=self.get_metrics(),
            metadata=metadata,
        )

    def reset(self) -> None:
        """Reset the simulator and policy to initial empty state."""
        self._cache.clear()
        self._total_requests = 0
        self._cache_hits = 0
        self._cache_misses = 0
        self._backend_requests = 0
        self._backend_requests_prevented = 0
        self._backend_latency_total_ms = 0.0
        self._latencies.clear()
        self._eviction_count = 0
        self._peak_cache_usage_bytes = 0
        self._oversized_requests = 0
        self.policy.reset()

    @staticmethod
    def _validate_inputs(
        capacity_bytes: int,
        hit_latency_ms: float,
        min_capacity_bytes: int | None,
        max_capacity_bytes: int | None,
    ) -> None:
        """Strictly validate constructor parameters."""
        if isinstance(capacity_bytes, bool) or not isinstance(capacity_bytes, int):
            raise TypeError(
                "capacity_bytes must be an integer, "
                f"got {type(capacity_bytes).__name__}"
            )
        if capacity_bytes <= 0:
            raise ValueError(
                f"capacity_bytes must be greater than 0, got {capacity_bytes}"
            )

        if isinstance(hit_latency_ms, bool) or not isinstance(
            hit_latency_ms, (int, float)
        ):
            raise TypeError(
                f"hit_latency_ms must be numeric, got {type(hit_latency_ms).__name__}"
            )
        if not math.isfinite(hit_latency_ms):
            raise ValueError(f"hit_latency_ms must be finite, got {hit_latency_ms}")
        if hit_latency_ms < 0.0:
            raise ValueError(
                f"hit_latency_ms must be non-negative, got {hit_latency_ms}"
            )

        if min_capacity_bytes is not None:
            if isinstance(min_capacity_bytes, bool) or not isinstance(
                min_capacity_bytes, int
            ):
                raise TypeError(
                    "min_capacity_bytes must be an integer, "
                    f"got {type(min_capacity_bytes).__name__}"
                )
            if min_capacity_bytes <= 0:
                raise ValueError("min_capacity_bytes must be greater than 0")
            if min_capacity_bytes > capacity_bytes:
                raise ValueError(
                    f"min_capacity_bytes ({min_capacity_bytes}) cannot exceed "
                    f"capacity_bytes ({capacity_bytes})"
                )

        if max_capacity_bytes is not None:
            if isinstance(max_capacity_bytes, bool) or not isinstance(
                max_capacity_bytes, int
            ):
                raise TypeError(
                    "max_capacity_bytes must be an integer, "
                    f"got {type(max_capacity_bytes).__name__}"
                )
            if max_capacity_bytes < capacity_bytes:
                raise ValueError(
                    f"max_capacity_bytes ({max_capacity_bytes}) must be >= "
                    f"capacity_bytes ({capacity_bytes})"
                )
