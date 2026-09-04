from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from telemetry.observation import Observation


@dataclass(frozen=True)
class WorkloadState:
    """Represents the raw observed state of the workload over a measurement window.

    Conforms to the shared v1 contract. Workload classification is intentionally
    omitted here as it is owned by Person 1's adaptive engine.
    """

    request_rate: float
    hit_rate: float
    miss_rate: float
    backend_latency_ms: float
    window_seconds: float
    timestamp: datetime
    workload_type: str | None = None
    metrics: dict[str, Any] | None = None

    @classmethod
    def from_observation(
        cls,
        observation: Observation,
        workload_type: str | None = None,
        metrics: dict[str, Any] | None = None,
    ) -> "WorkloadState":
        """Build WorkloadState directly from a raw telemetry Observation."""
        return cls(
            request_rate=observation.request_rate,
            hit_rate=observation.hit_rate,
            miss_rate=observation.miss_rate,
            backend_latency_ms=observation.backend_latency_ms,
            window_seconds=observation.window_seconds,
            timestamp=observation.timestamp,
            workload_type=workload_type,
            metrics=metrics,
        )


@dataclass(frozen=True)
class SystemState:
    """Represents the observed state of the cache system and backend resources.

    Conforms to the shared v1 contract. Does not make adaptive decisions, capacity
    actions, or eviction decisions.
    """

    cache_capacity_bytes: int | None
    cache_usage_bytes: int
    object_count: int
    backend_calls: int = 0
    cache_evictions: int = 0
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    window_seconds: float = 0.0
    metrics: dict[str, Any] | None = None

    @classmethod
    def from_cache_and_observation(
        cls,
        cache_manager: Any,
        observation: Observation | None = None,
        cache_capacity_bytes: int | None = None,
        cache_evictions: int = 0,
        metrics: dict[str, Any] | None = None,
    ) -> "SystemState":
        """Build SystemState from current cache manager contents and telemetry observation."""
        if hasattr(cache_manager, "get_all_metadata"):
            all_metadata = cache_manager.get_all_metadata()
            tracked_metadata = [
                meta for key, meta in all_metadata.items()
                if (not hasattr(cache_manager, "exists") or cache_manager.exists(key))
            ]
        elif isinstance(cache_manager, dict):
            tracked_metadata = list(cache_manager.values())
        elif hasattr(cache_manager, "__iter__"):
            tracked_metadata = list(cache_manager)
        else:
            tracked_metadata = []

        cache_usage_bytes = sum(getattr(meta, "size_bytes", 0) for meta in tracked_metadata)
        object_count = len(tracked_metadata)

        if observation is not None:
            backend_calls = observation.backend_calls
            window_seconds = observation.window_seconds
            timestamp = observation.timestamp
        else:
            backend_calls = 0
            window_seconds = 0.0
            timestamp = datetime.now(timezone.utc)

        return cls(
            cache_capacity_bytes=cache_capacity_bytes,
            cache_usage_bytes=cache_usage_bytes,
            object_count=object_count,
            backend_calls=backend_calls,
            cache_evictions=cache_evictions,
            timestamp=timestamp,
            window_seconds=window_seconds,
            metrics=metrics,
        )


def build_workload_state(
    observation: Observation,
    workload_type: str | None = None,
    metrics: dict[str, Any] | None = None,
) -> WorkloadState:
    """Helper function to construct WorkloadState from an Observation."""
    return WorkloadState.from_observation(
        observation=observation,
        workload_type=workload_type,
        metrics=metrics,
    )


def build_system_state(
    cache_manager: Any,
    observation: Observation | None = None,
    cache_capacity_bytes: int | None = None,
    cache_evictions: int = 0,
    metrics: dict[str, Any] | None = None,
) -> SystemState:
    """Helper function to construct SystemState from cache manager and observation."""
    return SystemState.from_cache_and_observation(
        cache_manager=cache_manager,
        observation=observation,
        cache_capacity_bytes=cache_capacity_bytes,
        cache_evictions=cache_evictions,
        metrics=metrics,
    )
