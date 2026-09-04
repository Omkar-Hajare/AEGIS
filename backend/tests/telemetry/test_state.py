from dataclasses import FrozenInstanceError
from datetime import datetime, timezone
import unittest

from cache.in_memory import InMemoryCache
from cache.manager import CacheManager
from cache.metadata import CacheObjectMetadata
from telemetry.observation import Observation
from telemetry.state import SystemState, WorkloadState, build_system_state, build_workload_state


class TestWorkloadAndSystemState(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 9, 4, 15, 0, 0, tzinfo=timezone.utc)
        self.sample_observation = Observation(
            request_rate=25.0,
            hit_rate=0.8,
            miss_rate=0.2,
            backend_latency_ms=35.5,
            window_seconds=10.0,
            total_requests=250,
            cache_hits=200,
            cache_misses=50,
            backend_calls=50,
            current_window_access_counts={"item:1": 10},
            previous_window_access_counts={"item:1": 5},
            timestamp=self.now,
        )

    def test_workload_state_mapping(self):
        """A. WorkloadState correctly maps all direct fields from Observation."""
        ws = WorkloadState.from_observation(self.sample_observation)

        self.assertEqual(ws.request_rate, 25.0)
        self.assertEqual(ws.hit_rate, 0.8)
        self.assertEqual(ws.miss_rate, 0.2)
        self.assertEqual(ws.backend_latency_ms, 35.5)
        self.assertEqual(ws.window_seconds, 10.0)
        self.assertEqual(ws.timestamp, self.now)
        self.assertIsNone(ws.metrics)

        # Helper function build_workload_state check
        ws2 = build_workload_state(self.sample_observation)
        self.assertEqual(ws, ws2)

    def test_workload_type_remains_unset(self):
        """B. workload_type is None unless explicitly supplied."""
        ws_default = WorkloadState.from_observation(self.sample_observation)
        self.assertIsNone(ws_default.workload_type)

        # Only set if explicitly provided
        ws_explicit = WorkloadState.from_observation(
            self.sample_observation, workload_type="READ_HEAVY"
        )
        self.assertEqual(ws_explicit.workload_type, "READ_HEAVY")

    def test_system_state_construction(self):
        """C. SystemState construction maps cache and observation metrics."""
        store = InMemoryCache()
        cache = CacheManager(store)
        cache.set("k1", {"id": 1})
        cache.create_metadata("k1", size_bytes=150, retrieval_cost_ms=20.0)
        cache.set("k2", {"id": 2})
        cache.create_metadata("k2", size_bytes=250, retrieval_cost_ms=30.0)

        ss = SystemState.from_cache_and_observation(
            cache_manager=cache,
            observation=self.sample_observation,
            cache_capacity_bytes=10_000_000,
        )

        self.assertEqual(ss.cache_capacity_bytes, 10_000_000)
        self.assertEqual(ss.cache_usage_bytes, 400)
        self.assertEqual(ss.object_count, 2)
        self.assertEqual(ss.backend_calls, 50)
        self.assertEqual(ss.window_seconds, 10.0)
        self.assertEqual(ss.timestamp, self.now)

        # Check build_system_state function helper
        ss2 = build_system_state(
            cache_manager=cache,
            observation=self.sample_observation,
            cache_capacity_bytes=10_000_000,
        )
        self.assertEqual(ss, ss2)

    def test_cache_usage_calculation(self):
        """D. cache_usage_bytes is the sum of size_bytes across objects (e.g. 100 + 250 + 650 = 1000)."""
        store = InMemoryCache()
        cache = CacheManager(store)
        cache.set("p1", {"val": 1})
        cache.create_metadata("p1", size_bytes=100, retrieval_cost_ms=10.0)
        cache.set("p2", {"val": 2})
        cache.create_metadata("p2", size_bytes=250, retrieval_cost_ms=20.0)
        cache.set("p3", {"val": 3})
        cache.create_metadata("p3", size_bytes=650, retrieval_cost_ms=30.0)

        ss = SystemState.from_cache_and_observation(cache, self.sample_observation)
        self.assertEqual(ss.cache_usage_bytes, 1000)
        self.assertEqual(ss.object_count, 3)

    def test_empty_cache(self):
        """E. Empty cache yields object_count = 0 and cache_usage_bytes = 0."""
        store = InMemoryCache()
        cache = CacheManager(store)

        ss = SystemState.from_cache_and_observation(cache)
        self.assertEqual(ss.object_count, 0)
        self.assertEqual(ss.cache_usage_bytes, 0)
        self.assertEqual(ss.backend_calls, 0)
        self.assertEqual(ss.window_seconds, 0.0)

    def test_eviction_count_zero(self):
        """F. Eviction count is zero when no eviction mechanism exists."""
        store = InMemoryCache()
        cache = CacheManager(store)

        ss = SystemState.from_cache_and_observation(cache, self.sample_observation)
        self.assertEqual(ss.cache_evictions, 0)

    def test_no_adaptive_calculations(self):
        """G. Verify state construction does not generate adaptive calculations."""
        ws = WorkloadState.from_observation(self.sample_observation)
        ss = SystemState.from_cache_and_observation(InMemoryCache(), self.sample_observation)

        # Verify no adaptive fields exist on WorkloadState
        self.assertFalse(hasattr(ws, "score"))
        self.assertFalse(hasattr(ws, "frequency"))
        self.assertFalse(hasattr(ws, "popularity_trend"))
        self.assertFalse(hasattr(ws, "capacity_decision"))
        self.assertFalse(hasattr(ws, "eviction_keys"))

        # Verify no adaptive fields exist on SystemState
        self.assertFalse(hasattr(ss, "score"))
        self.assertFalse(hasattr(ss, "frequency"))
        self.assertFalse(hasattr(ss, "capacity_decision"))
        self.assertFalse(hasattr(ss, "eviction_recommendation"))

    def test_cache_isolation(self):
        """H. Creating WorkloadState and SystemState does not mutate cache contents."""
        store = InMemoryCache()
        cache = CacheManager(store)
        cache.set("item:safe", {"name": "Protected"})
        cache.create_metadata("item:safe", size_bytes=77, retrieval_cost_ms=12.0)

        # Construct states
        WorkloadState.from_observation(self.sample_observation)
        SystemState.from_cache_and_observation(cache, self.sample_observation)

        # Cache content must be untouched
        self.assertTrue(cache.exists("item:safe"))
        self.assertEqual(cache.get("item:safe"), {"name": "Protected"})

    def test_metadata_isolation(self):
        """I. Creating state objects must not modify CacheObjectMetadata counters."""
        meta = CacheObjectMetadata(
            key="meta:1",
            size_bytes=50,
            retrieval_cost_ms=15.0,
            access_count=5,
            hit_count=3,
            miss_count=2,
        )
        store = InMemoryCache()
        cache = CacheManager(store)
        cache.set("meta:1", {"data": 1})
        cache.set_metadata("meta:1", meta)

        initial_access = meta.access_count
        initial_hits = meta.hit_count
        initial_misses = meta.miss_count
        initial_last_accessed = meta.last_accessed

        # Construct state
        SystemState.from_cache_and_observation(cache, self.sample_observation)

        # Metadata object must be completely untouched
        self.assertEqual(meta.access_count, initial_access)
        self.assertEqual(meta.hit_count, initial_hits)
        self.assertEqual(meta.miss_count, initial_misses)
        self.assertEqual(meta.last_accessed, initial_last_accessed)

    def test_immutability(self):
        """J. Frozen dataclasses prevent field mutation."""
        ws = WorkloadState.from_observation(self.sample_observation)
        with self.assertRaises(FrozenInstanceError):
            ws.request_rate = 999.0  # type: ignore

        ss = SystemState.from_cache_and_observation(InMemoryCache())
        with self.assertRaises(FrozenInstanceError):
            ss.cache_usage_bytes = 9999  # type: ignore


if __name__ == "__main__":
    unittest.main()
