from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass(frozen=True)
class Observation:
    """Represents raw measurements and rates over an observation window.

    All rates and average latencies are guarded against division by zero.
    """

    request_rate: float
    hit_rate: float
    miss_rate: float
    backend_latency_ms: float
    window_seconds: float
    total_requests: int
    cache_hits: int
    cache_misses: int
    backend_calls: int
    current_window_access_counts: dict[str, int] = field(default_factory=dict)
    previous_window_access_counts: dict[str, int] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
