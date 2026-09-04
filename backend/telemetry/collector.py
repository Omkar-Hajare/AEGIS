from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any

from telemetry.observation import Observation


class TelemetryCollector:
    """Stores raw in-process telemetry observations and computes windowed metrics for the backend."""

    def __init__(self, time_provider: Callable[[], datetime] | None = None) -> None:
        self._time_provider: Callable[[], datetime] = time_provider or (lambda: datetime.now(timezone.utc))
        self._total_requests: int = 0
        self._cache_hits: int = 0
        self._cache_misses: int = 0
        self._backend_calls: int = 0
        self._backend_latency_ms_total: float = 0.0
        self._current_window_access_counts: dict[str, int] = {}
        self._previous_window_access_counts: dict[str, int] = {}
        self._window_start: datetime = self._time_provider()

    # --- Existing Phase 6 API ---

    def record_request(self) -> None:
        """Increment total request count."""
        self._total_requests += 1

    def record_cache_hit(self) -> None:
        """Increment cache hit count."""
        self._cache_hits += 1

    def record_cache_miss(self) -> None:
        """Increment cache miss count."""
        self._cache_misses += 1

    def record_backend_call(self, latency_ms: float) -> None:
        """Increment backend call count and add measured backend latency."""
        self._backend_calls += 1
        self._backend_latency_ms_total += latency_ms

    def snapshot(self) -> dict[str, Any]:
        """Return a copy of current raw telemetry values."""
        return {
            "total_requests": self._total_requests,
            "cache_hits": self._cache_hits,
            "cache_misses": self._cache_misses,
            "backend_calls": self._backend_calls,
            "backend_latency_ms_total": self._backend_latency_ms_total,
        }

    def reset(self, now: datetime | None = None) -> None:
        """Reset in-memory telemetry counters, key counts, and window timestamp to zero."""
        self._total_requests = 0
        self._cache_hits = 0
        self._cache_misses = 0
        self._backend_calls = 0
        self._backend_latency_ms_total = 0.0
        self._current_window_access_counts = {}
        self._previous_window_access_counts = {}
        self._window_start = now or self._time_provider()

    # --- Phase 8 Window & Observation API ---

    def record_key_access(self, key: str, hit: bool = True) -> None:
        """Record a key access for the current observation window."""
        self._current_window_access_counts[key] = (
            self._current_window_access_counts.get(key, 0) + 1
        )

    @property
    def current_window_access_counts(self) -> dict[str, int]:
        """Return a copy of the current window per-key access counts."""
        return dict(self._current_window_access_counts)

    @property
    def previous_window_access_counts(self) -> dict[str, int]:
        """Return a copy of the previous completed window per-key access counts."""
        return dict(self._previous_window_access_counts)

    @property
    def window_start(self) -> datetime:
        """Return the start timestamp of the current observation window."""
        return self._window_start

    def observe(self, now: datetime | None = None) -> Observation:
        """Create an immutable Observation from current window counters without resetting them."""
        current_time = now or self._time_provider()
        raw_window_seconds = (current_time - self._window_start).total_seconds()
        window_seconds = max(0.0, raw_window_seconds)

        # Request rate guarded against division by zero
        if window_seconds > 0.0:
            request_rate = self._total_requests / window_seconds
        else:
            request_rate = 0.0

        # Hit rate & Miss rate guarded against division by zero
        if self._total_requests > 0:
            hit_rate = self._cache_hits / self._total_requests
            miss_rate = self._cache_misses / self._total_requests
        else:
            hit_rate = 0.0
            miss_rate = 0.0

        # Average backend latency guarded against division by zero
        if self._backend_calls > 0:
            backend_latency_ms = self._backend_latency_ms_total / self._backend_calls
        else:
            backend_latency_ms = 0.0

        return Observation(
            request_rate=request_rate,
            hit_rate=hit_rate,
            miss_rate=miss_rate,
            backend_latency_ms=backend_latency_ms,
            window_seconds=window_seconds,
            total_requests=self._total_requests,
            cache_hits=self._cache_hits,
            cache_misses=self._cache_misses,
            backend_calls=self._backend_calls,
            current_window_access_counts=dict(self._current_window_access_counts),
            previous_window_access_counts=dict(self._previous_window_access_counts),
            timestamp=current_time,
        )

    def reset_window(self, now: datetime | None = None) -> None:
        """Start a new observation window: preserves current key counts into previous window."""
        self._previous_window_access_counts = dict(self._current_window_access_counts)
        self._current_window_access_counts = {}
        self._total_requests = 0
        self._cache_hits = 0
        self._cache_misses = 0
        self._backend_calls = 0
        self._backend_latency_ms_total = 0.0
        self._window_start = now or self._time_provider()


# Application-level TelemetryCollector instance
telemetry_collector = TelemetryCollector()
