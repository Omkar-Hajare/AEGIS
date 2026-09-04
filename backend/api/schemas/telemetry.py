from datetime import datetime
from pydantic import BaseModel, Field

from telemetry.observation import Observation


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
    timestamp: datetime = Field(..., description="UTC timestamp of the observation snapshot")

    @classmethod
    def from_observation(cls, obs: Observation) -> "TelemetryObservationResponse":
        """Explicit boundary conversion from internal Observation dataclass to API schema."""
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
        )


class WindowResetResponse(BaseModel):
    """Confirmation response returned upon resetting the observation window."""

    status: str = Field(default="ok", description="Status code indicating success")
    message: str = Field(default="telemetry window reset", description="Human-readable confirmation")
