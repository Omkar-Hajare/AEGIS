"""Lightweight, pure-Python rolling telemetry for the Adaptive Cache System.

Provides bounded, sliding-window observation of recent request traffic,
hit/miss ratios, request rates, and backend latencies to ensure adaptive
decisions respond to current conditions rather than lifetime averages.
"""

from __future__ import annotations

from collections import deque
from datetime import datetime, timedelta, timezone
from typing import Any, NamedTuple


class _EventRecord(NamedTuple):
    timestamp: datetime
    hit: bool
    latency_ms: float
    key: str


class RollingTelemetry:
    """Bounded, time-windowed rolling telemetry tracker.

    Maintains a sliding window of events over the last `window_seconds` seconds
    and accumulates tumble-window summaries (previous completed window).

    Guarantees:
    - Pure Python with bounded memory (maxlen on deque).
    - O(1) amortized updates and window eviction.
    - Zero future-event leakage (only observes events at or before current timestamp).
    - Thread-safe / per-instance isolation (no global state).
    """

    def __init__(
        self,
        window_seconds: float = 60.0,
        max_events: int = 5000,
    ) -> None:
        """Initialize rolling telemetry tracker.

        Args:
            window_seconds: Duration of trailing observation window in seconds.
            max_events: Maximum number of events retained in sliding deque.
        """
        self.window_seconds: float = max(0.001, float(window_seconds))
        self.max_events: int = max(10, int(max_events))

        # Sliding window buffer: deque of _EventRecord
        self._events: deque[_EventRecord] = deque(maxlen=self.max_events)

        # Lifetime counters
        self.total_requests: int = 0
        self.total_hits: int = 0
        self.total_misses: int = 0
        self.total_backend_latency_ms: float = 0.0

        # Tumbling window state (for previous-window metrics)
        self._window_start_time: datetime | None = None
        self._curr_win_requests: int = 0
        self._curr_win_hits: int = 0
        self._curr_win_misses: int = 0
        self._curr_win_latency_ms: float = 0.0

        self._prev_win_requests: int = 0
        self._prev_win_hits: int = 0
        self._prev_win_misses: int = 0
        self._prev_win_latency_ms: float = 0.0
        self._prev_win_duration: float = 0.0

        self._last_observed_time: datetime | None = None

    def _ensure_utc(self, dt: datetime) -> datetime:
        """Ensure timestamp has a timezone (defaults to UTC)."""
        return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)

    def _update_tumbling_window(self, timestamp: datetime) -> None:
        """Advance tumbling window when duration threshold is crossed."""
        if self._window_start_time is None:
            self._window_start_time = timestamp
            return
        elapsed = (timestamp - self._window_start_time).total_seconds()
        if elapsed >= self.window_seconds:
            duration = max(elapsed, 0.001)
            self._prev_win_requests = self._curr_win_requests
            self._prev_win_hits = self._curr_win_hits
            self._prev_win_misses = self._curr_win_misses
            self._prev_win_latency_ms = self._curr_win_latency_ms
            self._prev_win_duration = duration

            self._curr_win_requests = 0
            self._curr_win_hits = 0
            self._curr_win_misses = 0
            self._curr_win_latency_ms = 0.0
            self._window_start_time = timestamp

    def _prune_expired(self, now: datetime) -> None:
        """Evict events from sliding buffer that fall outside the trailing window."""
        cutoff = now - timedelta(seconds=self.window_seconds)
        while self._events and self._events[0].timestamp < cutoff:
            self._events.popleft()

    def record_hit(
        self,
        timestamp: datetime,
        key: str = "",
        latency_ms: float = 0.0,
    ) -> None:
        """Record a simulated cache hit at the specified timestamp.

        Args:
            timestamp: The timestamp of the request event.
            key: Optional cache object key.
            latency_ms: Hit latency in ms (default 0.0).
        """
        ts = self._ensure_utc(timestamp)
        self._update_tumbling_window(ts)
        self._prune_expired(ts)

        self.total_requests += 1
        self.total_hits += 1

        self._curr_win_requests += 1
        self._curr_win_hits += 1

        self._events.append(
            _EventRecord(
                timestamp=ts,
                hit=True,
                latency_ms=max(0.0, float(latency_ms)),
                key=key,
            )
        )
        self._last_observed_time = ts

    def record_miss(
        self,
        timestamp: datetime,
        key: str = "",
        latency_ms: float = 0.0,
    ) -> None:
        """Record a simulated cache miss at the specified timestamp.

        Args:
            timestamp: The timestamp of the request event.
            key: Optional cache object key.
            latency_ms: Measured backend latency in ms.
        """
        ts = self._ensure_utc(timestamp)
        lat = max(0.0, float(latency_ms))
        self._update_tumbling_window(ts)
        self._prune_expired(ts)

        self.total_requests += 1
        self.total_misses += 1
        self.total_backend_latency_ms += lat

        self._curr_win_requests += 1
        self._curr_win_misses += 1
        self._curr_win_latency_ms += lat

        self._events.append(
            _EventRecord(
                timestamp=ts,
                hit=False,
                latency_ms=lat,
                key=key,
            )
        )
        self._last_observed_time = ts

    def get_recent_metrics(
        self,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        """Compute rolling telemetry metrics evaluated at `now`.

        Args:
            now: Evaluation timestamp. If omitted, uses the last observed event time.

        Returns:
            Dictionary with recent request count, hit/miss rates, request rate,
            backend latency, and lifetime comparison statistics.
        """
        eval_time = (
            self._ensure_utc(now)
            if now is not None
            else (self._last_observed_time or datetime.now(timezone.utc))
        )
        self._prune_expired(eval_time)

        recent_requests = len(self._events)
        if recent_requests > 0:
            recent_hits = sum(1 for e in self._events if e.hit)
            recent_misses = recent_requests - recent_hits
            recent_hit_rate = recent_hits / float(recent_requests)
            recent_miss_rate = recent_misses / float(recent_requests)

            miss_latencies = [e.latency_ms for e in self._events if not e.hit]
            if miss_latencies:
                recent_backend_lat = sum(miss_latencies) / float(len(miss_latencies))
            elif self.total_misses > 0:
                recent_backend_lat = self.total_backend_latency_ms / float(
                    self.total_misses
                )
            else:
                recent_backend_lat = 5.0

            span = (
                self._events[-1].timestamp - self._events[0].timestamp
            ).total_seconds()
            if span > 0.0:
                recent_request_rate = recent_requests / span
            else:
                recent_request_rate = float(recent_requests)
        else:
            recent_hits = 0
            recent_misses = 0
            recent_hit_rate = (
                (self.total_hits / float(self.total_requests))
                if self.total_requests > 0
                else 0.0
            )
            recent_miss_rate = (
                (self.total_misses / float(self.total_requests))
                if self.total_requests > 0
                else 1.0
            )
            recent_backend_lat = (
                (self.total_backend_latency_ms / float(self.total_misses))
                if self.total_misses > 0
                else 5.0
            )
            recent_request_rate = 0.0

        # Tumbling window metrics:
        prev_request_rate = (
            (self._prev_win_requests / self._prev_win_duration)
            if self._prev_win_duration > 0.0
            else 0.0
        )
        prev_backend_lat = (
            (self._prev_win_latency_ms / float(self._prev_win_misses))
            if self._prev_win_misses > 0
            else 0.0
        )

        return {
            "recent_requests": recent_requests,
            "recent_hits": recent_hits,
            "recent_misses": recent_misses,
            "recent_hit_rate": recent_hit_rate,
            "recent_miss_rate": recent_miss_rate,
            "recent_backend_latency_ms": recent_backend_lat,
            "recent_request_rate": recent_request_rate,
            "lifetime_requests": self.total_requests,
            "lifetime_hits": self.total_hits,
            "lifetime_misses": self.total_misses,
            "lifetime_hit_rate": (
                (self.total_hits / float(self.total_requests))
                if self.total_requests > 0
                else 0.0
            ),
            "lifetime_miss_rate": (
                (self.total_misses / float(self.total_requests))
                if self.total_requests > 0
                else 1.0
            ),
            "previous_window_request_rate": prev_request_rate,
            "previous_window_backend_latency_ms": prev_backend_lat,
        }

    def reset(self) -> None:
        """Reset internal sliding window, tumbling counters, and lifetime stats."""
        self._events.clear()
        self.total_requests = 0
        self.total_hits = 0
        self.total_misses = 0
        self.total_backend_latency_ms = 0.0

        self._window_start_time = None
        self._curr_win_requests = 0
        self._curr_win_hits = 0
        self._curr_win_misses = 0
        self._curr_win_latency_ms = 0.0

        self._prev_win_requests = 0
        self._prev_win_hits = 0
        self._prev_win_misses = 0
        self._prev_win_latency_ms = 0.0
        self._prev_win_duration = 0.0

        self._last_observed_time = None
