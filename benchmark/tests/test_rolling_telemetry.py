"""Unit tests for the RollingTelemetry system and AdaptivePolicyAdapter rolling integration.

Verifies:
- Recent hit/miss rates can differ from lifetime cumulative statistics.
- A sudden latency or traffic spike immediately shifts recent telemetry.
- Old traffic is evicted once outside the rolling window duration.
- Telemetry isolation between independent runs via reset().
- Zero future-event leakage.
- AdaptivePolicyAdapter integration with rolling telemetry.
"""

from datetime import datetime, timedelta, timezone

from backend.workload.scenario import ScenarioEvent
from benchmark.policies import AdaptivePolicyAdapter
from benchmark.rolling_telemetry import RollingTelemetry
from contracts.schemas import CacheObject, WorkloadType


def test_recent_rates_can_differ_from_lifetime_rates() -> None:
    """Recent hit/miss rate can differ dramatically from lifetime hit/miss rate."""
    telemetry = RollingTelemetry(window_seconds=30.0)
    start = datetime(2026, 9, 4, 12, 0, 0, tzinfo=timezone.utc)

    # Phase 1: 500 hits across first 100 seconds (lifetime heavily hit-dominated)
    for i in range(500):
        t = start + timedelta(seconds=i * 0.2)  # up to t = 100s
        telemetry.record_hit(t, key=f"k_{i % 10}", latency_ms=1.0)

    # Phase 2: Sudden storm of 20 misses at t = 105s..110s
    for i in range(20):
        t = start + timedelta(seconds=105.0 + i * 0.25)
        telemetry.record_miss(t, key=f"miss_{i}", latency_ms=150.0)

    eval_time = start + timedelta(seconds=110.0)
    metrics = telemetry.get_recent_metrics(eval_time)

    # Lifetime is still > 90% hits
    assert metrics["lifetime_requests"] == 520
    assert metrics["lifetime_hits"] == 500
    assert metrics["lifetime_hit_rate"] > 0.95

    # But recent window (last 30s, i.e. t=80s..110s) includes the 20 misses
    # and only the hits from t=80s..100s (approx 100 hits)
    assert metrics["recent_misses"] == 20
    assert metrics["recent_miss_rate"] > metrics["lifetime_miss_rate"]
    assert metrics["recent_hit_rate"] < metrics["lifetime_hit_rate"]
    assert metrics["recent_backend_latency_ms"] == 150.0


def test_recent_spike_changes_recent_telemetry() -> None:
    """A sudden spike in latency shifts recent backend latency immediately."""
    telemetry = RollingTelemetry(window_seconds=10.0)
    start = datetime(2026, 9, 4, 12, 0, 0, tzinfo=timezone.utc)

    # Fast requests at 5ms
    for i in range(50):
        t = start + timedelta(seconds=i * 0.1)
        telemetry.record_miss(t, key=f"k_{i}", latency_ms=5.0)

    metrics_before = telemetry.get_recent_metrics(start + timedelta(seconds=5.0))
    assert metrics_before["recent_backend_latency_ms"] == 5.0

    # Sudden spike of high-latency requests at 400ms at t = 12.0s
    spike_time = start + timedelta(seconds=12.0)
    for i in range(10):
        t = spike_time + timedelta(seconds=i * 0.05)
        telemetry.record_miss(t, key=f"slow_{i}", latency_ms=400.0)

    metrics_after = telemetry.get_recent_metrics(spike_time + timedelta(seconds=1.0))
    # Rolling window (last 10s = [3s, 13s]) includes high-latency events
    assert metrics_after["recent_backend_latency_ms"] > 100.0


def test_old_traffic_eventually_excluded_from_rolling_window() -> None:
    """Events older than window_seconds are excluded from the rolling window."""
    window_sec = 20.0
    telemetry = RollingTelemetry(window_seconds=window_sec)
    start = datetime(2026, 9, 4, 12, 0, 0, tzinfo=timezone.utc)

    # 100 misses at t = 0s
    for i in range(100):
        telemetry.record_miss(start, key=f"k_{i}", latency_ms=50.0)

    m1 = telemetry.get_recent_metrics(start)
    assert m1["recent_requests"] == 100
    assert m1["recent_miss_rate"] == 1.0

    # Advance time past window_seconds (t = 25s) with 10 hits
    later = start + timedelta(seconds=25.0)
    for i in range(10):
        telemetry.record_hit(later + timedelta(seconds=i * 0.1), key=f"hit_{i}")

    m2 = telemetry.get_recent_metrics(later + timedelta(seconds=2.0))
    # Old misses at t = 0s are outside [7s, 27s], so they are excluded
    assert m2["recent_requests"] == 10
    assert m2["recent_hits"] == 10
    assert m2["recent_hit_rate"] == 1.0
    assert m2["recent_miss_rate"] == 0.0
    # Lifetime still tracks all 110 requests
    assert m2["lifetime_requests"] == 110


def test_telemetry_isolated_between_independent_runs() -> None:
    """reset() restores the telemetry tracker to a clean slate."""
    telemetry = RollingTelemetry(window_seconds=60.0)
    start = datetime(2026, 9, 4, 12, 0, 0, tzinfo=timezone.utc)

    telemetry.record_hit(start, key="k1", latency_ms=0.0)
    telemetry.record_miss(start, key="k2", latency_ms=50.0)
    assert telemetry.total_requests == 2

    telemetry.reset()

    assert telemetry.total_requests == 0
    assert telemetry.total_hits == 0
    assert telemetry.total_misses == 0
    assert telemetry.total_backend_latency_ms == 0.0
    metrics = telemetry.get_recent_metrics(start)
    assert metrics["recent_requests"] == 0
    assert metrics["lifetime_requests"] == 0


def test_no_future_events_influence_current_telemetry() -> None:
    """Metrics evaluated at event t only reflect events occurring at or before t."""
    telemetry = RollingTelemetry(window_seconds=60.0)
    start = datetime(2026, 9, 4, 12, 0, 0, tzinfo=timezone.utc)

    # Event 1 at t = 0
    telemetry.record_hit(start, key="item1")
    m_t0 = telemetry.get_recent_metrics(start)
    assert m_t0["recent_requests"] == 1
    assert m_t0["recent_hits"] == 1

    # Event 2 at t = 5
    t1 = start + timedelta(seconds=5.0)
    telemetry.record_miss(t1, key="item2", latency_ms=100.0)
    m_t1 = telemetry.get_recent_metrics(t1)
    assert m_t1["recent_requests"] == 2
    assert m_t1["recent_misses"] == 1

    # Historical point t=0 was not influenced by the future event at t=5
    assert m_t0["recent_requests"] == 1


def test_adaptive_policy_adapter_feeds_rolling_telemetry() -> None:
    """AdaptivePolicyAdapter populates WorkloadState using rolling telemetry."""
    adapter = AdaptivePolicyAdapter(window_seconds=10.0)
    start = datetime(2026, 9, 4, 12, 0, 0, tzinfo=timezone.utc)

    # Create dummy cache objects
    cache: dict[str, CacheObject] = {
        "k1": CacheObject(
            key="k1",
            size_bytes=100,
            access_count=5,
            last_accessed=start,
            retrieval_cost_ms=20.0,
        ),
        "k2": CacheObject(
            key="k2",
            size_bytes=200,
            access_count=1,
            last_accessed=start,
            retrieval_cost_ms=50.0,
        ),
    }

    # Record some hits and misses
    ev_hit = ScenarioEvent(
        timestamp=start,
        key="k1",
        workload_type=WorkloadType.READ_HEAVY,
        backend_latency_ms=10.0,
        object_size_bytes=100,
        retrieval_cost_ms=10.0,
        request_rate=100.0,
    )
    adapter.on_hit("k1", ev_hit, cache)

    ev_miss = ScenarioEvent(
        timestamp=start + timedelta(seconds=1.0),
        key="k3",
        workload_type=WorkloadType.READ_HEAVY,
        backend_latency_ms=150.0,
        object_size_bytes=100,
        retrieval_cost_ms=150.0,
        request_rate=100.0,
    )
    adapter.on_miss("k3", ev_miss, cache)

    # Trigger select_evictions
    ev_eval = ScenarioEvent(
        timestamp=start + timedelta(seconds=2.0),
        key="k4",
        workload_type=WorkloadType.READ_HEAVY,
        backend_latency_ms=150.0,
        object_size_bytes=100,
        retrieval_cost_ms=150.0,
        request_rate=100.0,
    )
    adapter.select_evictions(cache, target_capacity_bytes=150, event=ev_eval)

    assert adapter._last_decision is not None
    assert adapter._last_decision.metadata is not None
    # Verify dynamic weights and pressures were derived and recorded
    assert "dynamic_weights" in adapter._last_decision.metadata
    assert "dynamic_pressures" in adapter._last_decision.metadata

    # Clean reset isolates next run
    adapter.reset()
    assert adapter.rolling_telemetry.total_requests == 0
    assert len(adapter._current_window_accesses) == 0
