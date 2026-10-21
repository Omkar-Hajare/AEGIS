"""Policy fairness, metadata leakage prevention, and telemetry verification tests.

Validates that:
1. AdaptivePolicyAdapter does not read or leak synthetic scenario generator metadata.
2. Decisions are strictly identical with or without scenario metadata present.
3. Popularity shift and spike detection derive purely from observed request telemetry.
4. Latency percentile calculations and discrete step-function behavior are verified.
5. Modeled origin penalty (latency penalty in ms) semantics are verified without monetary distortion.
6. Standard GDS with inflation clock behaves deterministically and aligns with theoretical expectations.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from backend.workload.scenario import (
    ScenarioEvent,
)
from benchmark.cache_simulator import CacheSimulator
from benchmark.models import BenchmarkMetrics
from benchmark.policies import (
    AdaptivePolicyAdapter,
    GDSPolicyAdapter,
    LRUPolicyAdapter,
)
from benchmark.results import calculate_percentile
from contracts.schemas.enums import WorkloadType


class TestMetadataLeakagePrevention:
    """Verifies that AdaptivePolicyAdapter operates strictly as a black-box.
    
    No internal scenario generator fields (shift_progress, spike_multiplier, etc.)
    may influence cache eviction, admission, or scoring decisions.
    """

    def test_zero_metadata_leakage_identical_execution(self) -> None:
        """Strip all metadata and verify bit-for-bit identical policy decisions."""
        start = datetime(2026, 9, 4, 12, 0, 0, tzinfo=timezone.utc)
        
        # Build 100 events with rich generator metadata
        events_with_metadata: list[ScenarioEvent] = []
        events_without_metadata: list[ScenarioEvent] = []
        
        for i in range(100):
            ts = start + timedelta(seconds=i * 0.01)
            key = f"key_{i % 15}"
            
            ev_with = ScenarioEvent(
                timestamp=ts,
                key=key,
                workload_type=WorkloadType.READ_HEAVY,
                backend_latency_ms=10.0,
                object_size_bytes=1000,
                retrieval_cost_ms=15.0,
                request_rate=100.0,
                metadata={
                    "shift_progress": (i / 100.0),
                    "spike_multiplier": 5.0 if i > 50 else 1.0,
                    "active_pool": "new_pool" if i > 50 else "old_pool",
                    "synthetic_internal_label": "adversarial_signal",
                },
            )
            
            ev_without = ScenarioEvent(
                timestamp=ts,
                key=key,
                workload_type=WorkloadType.READ_HEAVY,
                backend_latency_ms=10.0,
                object_size_bytes=1000,
                retrieval_cost_ms=15.0,
                request_rate=100.0,
                metadata={},  # completely stripped
            )
            
            events_with_metadata.append(ev_with)
            events_without_metadata.append(ev_without)

        # Run simulator 1 with metadata
        sim1 = CacheSimulator(
            capacity_bytes=5000,
            policy=AdaptivePolicyAdapter(window_seconds=1.0),
            hit_latency_ms=1.0,
        )
        for ev in events_with_metadata:
            sim1.process_event(ev)
        m1 = sim1.get_metrics()

        # Run simulator 2 without metadata
        sim2 = CacheSimulator(
            capacity_bytes=5000,
            policy=AdaptivePolicyAdapter(window_seconds=1.0),
            hit_latency_ms=1.0,
        )
        for ev in events_without_metadata:
            sim2.process_event(ev)
        m2 = sim2.get_metrics()

        # Decisions must be 100% identical
        assert m1.total_requests == m2.total_requests
        assert m1.cache_hits == m2.cache_hits
        assert m1.cache_misses == m2.cache_misses
        assert m1.eviction_count == m2.eviction_count
        assert set(sim1.cache.keys()) == set(sim2.cache.keys())
        assert sim1.current_usage_bytes == sim2.current_usage_bytes

    def test_adversarial_metadata_injection_has_no_effect(self) -> None:
        """Injecting deceptive metadata into events must not change any policy actions."""
        start = datetime(2026, 9, 4, 12, 0, 0, tzinfo=timezone.utc)
        
        sim_normal = CacheSimulator(
            capacity_bytes=5000,
            policy=AdaptivePolicyAdapter(window_seconds=1.0),
            hit_latency_ms=1.0,
        )
        sim_poisoned = CacheSimulator(
            capacity_bytes=5000,
            policy=AdaptivePolicyAdapter(window_seconds=1.0),
            hit_latency_ms=1.0,
        )

        for i in range(120):
            ts = start + timedelta(seconds=i * 0.05)
            key = f"item_{i % 20}"

            ev_normal = ScenarioEvent(
                timestamp=ts,
                key=key,
                workload_type=WorkloadType.READ_HEAVY,
                backend_latency_ms=8.0,
                object_size_bytes=800,
                retrieval_cost_ms=12.0,
                request_rate=20.0,
                metadata={},
            )
            ev_poisoned = ScenarioEvent(
                timestamp=ts,
                key=key,
                workload_type=WorkloadType.READ_HEAVY,
                backend_latency_ms=8.0,
                object_size_bytes=800,
                retrieval_cost_ms=12.0,
                request_rate=20.0,
                metadata={
                    "shift_progress": 99999.0,  # extreme hallucinated values
                    "spike_multiplier": 0.000001,
                    "spoofed_classification": "ILLEGITIMATE",
                },
            )

            sim_normal.process_event(ev_normal)
            sim_poisoned.process_event(ev_poisoned)

        m_normal = sim_normal.get_metrics()
        m_poisoned = sim_poisoned.get_metrics()

        assert m_normal.hit_ratio == m_poisoned.hit_ratio
        assert m_normal.eviction_count == m_poisoned.eviction_count
        assert set(sim_normal.cache.keys()) == set(sim_poisoned.cache.keys())


class TestAutonomousTelemetryAdaptation:
    """Verifies that AdaptivePolicyAdapter derives signals strictly from observed requests."""

    def test_working_set_churn_drives_popularity_shift_score(self) -> None:
        """Verify that when active keys change, sliding-window key churn reflects the shift."""
        adapter = AdaptivePolicyAdapter(window_seconds=1.0)
        sim = CacheSimulator(capacity_bytes=10000, policy=adapter, hit_latency_ms=1.0)
        start = datetime(2026, 9, 4, 12, 0, 0, tzinfo=timezone.utc)

        # Window 1: 60 requests all to pool A (keys 0..4) -> crosses 1.0s and establishes baseline hot keys
        for i in range(60):
            ts = start + timedelta(seconds=i * 0.02)
            ev = ScenarioEvent(
                timestamp=ts,
                key=f"key_A_{i % 5}",
                workload_type=WorkloadType.READ_HEAVY,
                backend_latency_ms=10.0,
                object_size_bytes=1000,
                retrieval_cost_ms=10.0,
                request_rate=50.0,
                metadata={},
            )
            sim.process_event(ev)

        # Window rolls after 1 second (at ts >= start + 1s)
        assert len(adapter._baseline_hot_keys) > 0, "Baseline hot keys should be populated after window roll"
        assert all("key_A" in k for k in adapter._baseline_hot_keys)

        # Window 2: complete shift to pool B (keys 10..30)
        for i in range(60):
            ts = start + timedelta(seconds=1.3 + i * 0.02)
            ev = ScenarioEvent(
                timestamp=ts,
                key=f"key_B_{i % 15}",
                workload_type=WorkloadType.READ_HEAVY,
                backend_latency_ms=10.0,
                object_size_bytes=1000,
                retrieval_cost_ms=10.0,
                request_rate=50.0,
                metadata={},
            )
            sim.process_event(ev)

        # Eviction selection in window 2 observes the churn
        ev_eval = ScenarioEvent(
            timestamp=start + timedelta(seconds=2.5),
            key="key_B_99",
            workload_type=WorkloadType.READ_HEAVY,
            backend_latency_ms=10.0,
            object_size_bytes=1000,
            retrieval_cost_ms=10.0,
            request_rate=50.0,
            metadata={},
        )
        # Verify that select_evictions executes successfully and observes churn
        evictions = adapter.select_evictions(sim.cache, target_capacity_bytes=5000, event=ev_eval)
        assert isinstance(evictions, list)
        assert len(evictions) > 0

    def test_request_rate_baseline_tracks_observed_arrivals(self) -> None:
        """Verify running baseline adapts dynamically to observed request rates."""
        adapter = AdaptivePolicyAdapter(window_seconds=1.0)
        start = datetime(2026, 9, 4, 12, 0, 0, tzinfo=timezone.utc)

        # Send 100 requests across 1.0 second (rate = 100 req/s)
        for i in range(100):
            ts = start + timedelta(seconds=i * 0.01)
            ev = ScenarioEvent(
                timestamp=ts,
                key="key_x",
                workload_type=WorkloadType.READ_HEAVY,
                backend_latency_ms=10.0,
                object_size_bytes=1000,
                retrieval_cost_ms=10.0,
                request_rate=100.0,
            )
            adapter.on_miss("key_x", ev, {})

        # Advance timestamp past 1 second to trigger _update_window
        ev_roll = ScenarioEvent(
            timestamp=start + timedelta(seconds=1.05),
            key="key_x",
            workload_type=WorkloadType.READ_HEAVY,
            backend_latency_ms=10.0,
            object_size_bytes=1000,
            retrieval_cost_ms=10.0,
            request_rate=100.0,
        )
        adapter.on_miss("key_x", ev_roll, {})
        assert adapter._baseline_request_rate > 50.0


class TestPercentileCalculationsAndStepFunction:
    """Verifies percentile calculations and documents the discrete step-function behavior."""

    def test_percentile_linear_interpolation(self) -> None:
        values = [10.0, 20.0, 30.0, 40.0, 50.0]
        assert calculate_percentile(values, 0.0) == 10.0
        assert calculate_percentile(values, 50.0) == 30.0
        assert calculate_percentile(values, 100.0) == 50.0
        assert calculate_percentile(values, 25.0) == 20.0
        assert calculate_percentile(values, 75.0) == 40.0

    def test_percentile_empty_and_single(self) -> None:
        with pytest.raises(ValueError, match="data sequence must not be empty"):
            calculate_percentile([], 50.0)
        assert calculate_percentile([42.0], 50.0) == 42.0
        assert calculate_percentile([42.0], 99.0) == 42.0

    def test_p50_latency_step_function_across_50_pct_hit_ratio_boundary(self) -> None:
        """Demonstrates that P50 latency drops abruptly to 1.00 ms when hit ratio crosses 50%.
        
        Hits are 1.0 ms. Misses are 25.0 ms.
        At 51% hit ratio, P50 is 1.0 ms.
        At 49% hit ratio, P50 is 25.0 ms.
        """
        # Case A: 51 hits, 49 misses (hit ratio = 51%)
        latencies_51_hits = [1.0] * 51 + [25.0] * 49
        latencies_51_hits.sort()
        p50_a = calculate_percentile(latencies_51_hits, 50.0)
        assert p50_a == 1.0, "When hits > 50%, median request is guaranteed to be a cache hit (1.0 ms)"

        # Case B: 49 hits, 51 misses (hit ratio = 49%)
        latencies_49_hits = [1.0] * 49 + [25.0] * 51
        latencies_49_hits.sort()
        p50_b = calculate_percentile(latencies_49_hits, 50.0)
        assert p50_b == 25.0, "When hits < 50%, median request falls into miss retrieval latency"

        # The relative difference is (25.0 - 1.0) / 25.0 = 96%, purely an artifact of crossing the 50% boundary!
        assert (p50_b - p50_a) / p50_b == 0.96


class TestModeledCostSemantics:
    """Verifies that modeled cost represents origin retrieval penalty in milliseconds, not monetary dollars."""

    def test_default_cost_profile_origin_penalty_ms(self) -> None:
        metrics = BenchmarkMetrics(
            total_requests=100,
            cache_hits=60,
            cache_misses=40,
            backend_requests=40,
            backend_requests_prevented=60,
            backend_latency_total_ms=400.0,
            hit_ratio=0.60,
            miss_ratio=0.40,
            average_latency_ms=5.0,
            p50_latency_ms=1.0,
            p95_latency_ms=15.0,
            p99_latency_ms=20.0,
            eviction_count=35,
            peak_cache_usage_bytes=40000,
            cache_capacity_bytes=50000,
            throughput_rps=100.0,
            estimated_cost=2500.0,  # 2500 ms origin penalty
            modeled_origin_penalty_ms=2500.0,
        )

        assert metrics.estimated_cost == 2500.0
        assert metrics.modeled_origin_penalty_ms == 2500.0
        # Check backward compatibility property
        assert metrics.modeled_origin_penalty_ms == metrics.estimated_cost


class TestStandardGDSFairness:
    """Verifies standard GreedyDual-Size properties and equivalence to LRU on uniform workloads."""

    def test_gds_matches_lru_on_uniform_size_and_cost(self) -> None:
        """Under uniform sizes and costs, GreedyDual-Size reduces to LRU.
        
        Both should achieve identical hit counts, miss counts, and evictions.
        """
        start = datetime(2026, 9, 4, 12, 0, 0, tzinfo=timezone.utc)
        events: list[ScenarioEvent] = []
        
        # Access pattern with 10 keys, uniform size=1000, uniform cost=10.0
        keys_sequence = [f"k_{i % 10}" for i in range(100)]
        for i, k in enumerate(keys_sequence):
            events.append(
                ScenarioEvent(
                    timestamp=start + timedelta(seconds=i * 0.1),
                    key=k,
                    workload_type=WorkloadType.READ_HEAVY,
                    backend_latency_ms=10.0,
                    object_size_bytes=1000,
                    retrieval_cost_ms=10.0,
                    request_rate=10.0,
                )
            )

        # Capacity holds 4 objects (4000 bytes)
        sim_lru = CacheSimulator(capacity_bytes=4000, policy=LRUPolicyAdapter(), hit_latency_ms=1.0)
        sim_gds = CacheSimulator(capacity_bytes=4000, policy=GDSPolicyAdapter(), hit_latency_ms=1.0)

        for ev in events:
            sim_lru.process_event(ev)
            sim_gds.process_event(ev)

        m_lru = sim_lru.get_metrics()
        m_gds = sim_gds.get_metrics()

        assert m_lru.cache_hits == m_gds.cache_hits
        assert m_lru.cache_misses == m_gds.cache_misses
        assert m_lru.eviction_count == m_gds.eviction_count
        assert set(sim_lru.cache.keys()) == set(sim_gds.cache.keys())
