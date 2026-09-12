from datetime import datetime
from typing import Any
from pydantic import BaseModel, Field

from telemetry.observation import Observation
from telemetry.state import SystemState, WorkloadState


class TelemetryObservationResponse(BaseModel):
    """Public API response model representing time-windowed telemetry observations."""

    version: str = Field(default="v1", description="Telemetry observation schema version")
    request_rate: float = Field(..., description="Requests per second in the window")
    hit_rate: float = Field(..., description="Ratio of cache hits to total requests (0.0 - 1.0)")
    miss_rate: float = Field(..., description="Ratio of cache misses to total requests (0.0 - 1.0)")
    backend_latency_ms: float = Field(..., description="Average backend retrieval latency in milliseconds")
    window_seconds: float = Field(..., description="Duration of observation window in seconds")
    total_requests: int = Field(..., description="Total requests recorded in current window")
    cache_hits: int = Field(..., description="Total cache hits in current window")
    cache_misses: int = Field(..., description="Total cache misses in current window")
    backend_calls: int = Field(..., description="Total backend simulator calls in current window")
    current_window_access_counts: dict[str, int] = Field(
        default_factory=dict,
        description="Per-key access counts for the current active observation window",
    )
    previous_window_access_counts: dict[str, int] = Field(
        default_factory=dict,
        description="Per-key access counts from the immediately preceding completed observation window",
    )
    cache_hit_ratio: float | None = Field(
        default=None,
        description="Canonical cache hit ratio percentage (0.0 - 100.0)",
    )
    observation_window_start: datetime | None = Field(
        default=None,
        description="Observation window start timestamp",
    )
    observation_window_end: datetime | None = Field(
        default=None,
        description="Observation window end timestamp",
    )
    timestamp: datetime = Field(..., description="UTC timestamp of the observation snapshot")

    @classmethod
    def from_observation(cls, obs: Observation) -> "TelemetryObservationResponse":
        """Explicit boundary conversion from internal Observation dataclass to API schema."""
        total_cache_ops = obs.cache_hits + obs.cache_misses
        ratio = round((obs.cache_hits / total_cache_ops) * 100.0, 2) if total_cache_ops > 0 else 0.0
        return cls(
            version="v1",
            request_rate=obs.request_rate,
            hit_rate=obs.hit_rate,
            miss_rate=obs.miss_rate,
            backend_latency_ms=obs.backend_latency_ms,
            window_seconds=obs.window_seconds,
            total_requests=obs.total_requests,
            cache_hits=obs.cache_hits,
            cache_misses=obs.cache_misses,
            backend_calls=obs.backend_calls,
            current_window_access_counts=dict(obs.current_window_access_counts),
            previous_window_access_counts=dict(obs.previous_window_access_counts),
            timestamp=obs.timestamp,
            cache_hit_ratio=min(100.0, max(0.0, ratio)),
            observation_window_start=getattr(obs, "window_start", None),
            observation_window_end=obs.timestamp,
        )


class CacheHitRatioResponse(BaseModel):
    """Public API response model representing canonical aggregated cache hit ratio metrics."""

    total_requests: int = Field(..., description="Total requests during the observation window")
    cache_hits: int = Field(..., description="Aggregated cache hits during the observation window")
    cache_misses: int = Field(..., description="Aggregated cache misses during the observation window")
    cache_hit_ratio: float = Field(..., description="Aggregated cache hit ratio percentage (0.0 - 100.0)")
    observation_window_start: datetime = Field(..., description="Start of observation window")
    observation_window_end: datetime = Field(..., description="End of observation window")


class WorkloadStateResponse(BaseModel):
    """Public API response model representing the observed WorkloadState."""

    version: str = Field(default="v1", description="Workload state schema version")
    request_rate: float = Field(..., description="Requests per second in the window")
    hit_rate: float = Field(..., description="Ratio of cache hits to total requests (0.0 - 1.0)")
    miss_rate: float = Field(..., description="Ratio of cache misses to total requests (0.0 - 1.0)")
    backend_latency_ms: float = Field(..., description="Average backend retrieval latency in milliseconds")
    workload_type: str | None = Field(
        default=None,
        description="Optional workload classification (None unless explicitly classified)",
    )
    timestamp: datetime = Field(..., description="UTC timestamp of the workload state observation")
    window_seconds: float = Field(..., description="Duration of observation window in seconds")
    metrics: dict[str, Any] | None = Field(
        default=None,
        description="Optional additional raw metrics dictionary",
    )

    @classmethod
    def from_workload_state(cls, state: WorkloadState) -> "WorkloadStateResponse":
        """Explicit boundary conversion from internal WorkloadState dataclass to API schema."""
        return cls(
            version="v1",
            request_rate=state.request_rate,
            hit_rate=state.hit_rate,
            miss_rate=state.miss_rate,
            backend_latency_ms=state.backend_latency_ms,
            workload_type=state.workload_type,
            timestamp=state.timestamp,
            window_seconds=state.window_seconds,
            metrics=state.metrics,
        )


class SystemStateResponse(BaseModel):
    """Public API response model representing the observed SystemState."""

    version: str = Field(default="v1", description="System state schema version")
    cache_capacity_bytes: int | None = Field(
        default=None,
        description="Configured logical cache capacity in bytes, or None if unconstrained",
    )
    cache_usage_bytes: int = Field(..., description="Sum of payload sizes of currently tracked cached objects")
    object_count: int = Field(..., description="Count of currently tracked cached objects")
    backend_calls: int = Field(..., description="Total backend calls in observation window")
    cache_evictions: int = Field(default=0, description="Observed cache evictions in window (0 if none)")
    timestamp: datetime = Field(..., description="UTC timestamp of the system state snapshot")
    window_seconds: float = Field(..., description="Duration of observation window in seconds")
    metrics: dict[str, Any] | None = Field(
        default=None,
        description="Optional additional raw metrics dictionary",
    )

    @classmethod
    def from_system_state(cls, state: SystemState) -> "SystemStateResponse":
        """Explicit boundary conversion from internal SystemState dataclass to API schema."""
        return cls(
            version="v1",
            cache_capacity_bytes=state.cache_capacity_bytes,
            cache_usage_bytes=state.cache_usage_bytes,
            object_count=state.object_count,
            backend_calls=state.backend_calls,
            cache_evictions=state.cache_evictions,
            timestamp=state.timestamp,
            window_seconds=state.window_seconds,
            metrics=state.metrics,
        )


class WindowResetResponse(BaseModel):
    """Confirmation response returned upon resetting the observation window."""

    status: str = Field(default="ok", description="Status code indicating success")
    message: str = Field(default="telemetry window reset", description="Human-readable confirmation")
