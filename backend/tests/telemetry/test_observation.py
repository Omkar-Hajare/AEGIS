from datetime import datetime, timedelta, timezone
import unittest

from cache.in_memory import InMemoryCache
from cache.manager import CacheManager
from telemetry.collector import TelemetryCollector
from telemetry.observation import Observation


class TestTelemetryObservation(unittest.TestCase):
    def setUp(self):
        self.base_time = datetime(2026, 9, 4, 12, 0, 0, tzinfo=timezone.utc)
        self.current_time = self.base_time
        # Deterministic time provider
        self.collector = TelemetryCollector(time_provider=lambda: self.current_time)

    def advance_time(self, seconds: float):
        self.current_time += timedelta(seconds=seconds)

    def test_empty_collector(self):
        """A. Empty collector: all rates and average latencies must be zero."""
        self.advance_time(10.0)
        obs = self.collector.observe()

        self.assertIsInstance(obs, Observation)
        self.assertEqual(obs.total_requests, 0)
        self.assertEqual(obs.cache_hits, 0)
        self.assertEqual(obs.cache_misses, 0)
        self.assertEqual(obs.backend_calls, 0)
        self.assertEqual(obs.request_rate, 0.0)
        self.assertEqual(obs.hit_rate, 0.0)
        self.assertEqual(obs.miss_rate, 0.0)
        self.assertEqual(obs.backend_latency_ms, 0.0)
        self.assertEqual(obs.window_seconds, 10.0)
        self.assertEqual(obs.current_window_access_counts, {})
        self.assertEqual(obs.previous_window_access_counts, {})

    def test_request_rate(self):
        """B. Request rate: known number of requests over controlled window duration."""
        # 50 requests over 10 seconds -> 5.0 requests/second
        for _ in range(50):
            self.collector.record_request()

        self.advance_time(10.0)
        obs = self.collector.observe()

        self.assertEqual(obs.total_requests, 50)
        self.assertEqual(obs.window_seconds, 10.0)
        self.assertAlmostEqual(obs.request_rate, 5.0)

    def test_hit_rate(self):
        """C. Hit rate: known hits / total requests."""
        # 10 requests: 8 hits, 2 misses
        for _ in range(10):
            self.collector.record_request()
        for _ in range(8):
            self.collector.record_cache_hit()
        for _ in range(2):
            self.collector.record_cache_miss()

        self.advance_time(5.0)
        obs = self.collector.observe()

        self.assertEqual(obs.total_requests, 10)
        self.assertEqual(obs.cache_hits, 8)
        self.assertAlmostEqual(obs.hit_rate, 0.8)

    def test_miss_rate(self):
        """D. Miss rate: known misses / total requests."""
        # 20 requests: 5 misses, 15 hits
        for _ in range(20):
            self.collector.record_request()
        for _ in range(5):
            self.collector.record_cache_miss()
        for _ in range(15):
            self.collector.record_cache_hit()

        self.advance_time(5.0)
        obs = self.collector.observe()

        self.assertEqual(obs.total_requests, 20)
        self.assertEqual(obs.cache_misses, 5)
        self.assertAlmostEqual(obs.miss_rate, 0.25)

    def test_backend_latency(self):
        """E. Backend latency: average of backend calls total latency."""
        self.collector.record_backend_call(20.0)
        self.collector.record_backend_call(40.0)
        self.collector.record_backend_call(60.0)

        self.advance_time(1.0)
        obs = self.collector.observe()

        self.assertEqual(obs.backend_calls, 3)
        self.assertAlmostEqual(obs.backend_latency_ms, 40.0)

    def test_per_key_current_window_access_counts(self):
        """F. Per-key current-window access counts."""
        self.collector.record_key_access("product:1", hit=True)
        self.collector.record_key_access("product:1", hit=True)
        self.collector.record_key_access("product:2", hit=False)

        counts = self.collector.current_window_access_counts
        self.assertEqual(counts["product:1"], 2)
        self.assertEqual(counts["product:2"], 1)

        obs = self.collector.observe()
        self.assertEqual(obs.current_window_access_counts["product:1"], 2)
        self.assertEqual(obs.current_window_access_counts["product:2"], 1)

    def test_window_reset(self):
        """G. Window reset: moves current counts to previous, clears current counters and counts."""
        self.collector.record_request()
        self.collector.record_cache_hit()
        self.collector.record_backend_call(15.0)
        self.collector.record_key_access("product:42", hit=True)
        self.collector.record_key_access("product:42", hit=True)
        self.collector.record_key_access("recommendation:7", hit=False)

        self.advance_time(10.0)

        # Reset window
        self.collector.reset_window()

        # Current window should be reset
        obs_after_reset = self.collector.observe()
        self.assertEqual(obs_after_reset.total_requests, 0)
        self.assertEqual(obs_after_reset.cache_hits, 0)
        self.assertEqual(obs_after_reset.cache_misses, 0)
        self.assertEqual(obs_after_reset.backend_calls, 0)
        self.assertEqual(obs_after_reset.backend_latency_ms, 0.0)
        self.assertEqual(obs_after_reset.current_window_access_counts, {})

        # Previous window counts should contain previous window data
        self.assertEqual(
            obs_after_reset.previous_window_access_counts,
            {"product:42": 2, "recommendation:7": 1},
        )
        self.assertEqual(
            self.collector.previous_window_access_counts,
            {"product:42": 2, "recommendation:7": 1},
        )

    def test_cache_contents_unaffected_by_telemetry_reset(self):
        """H. Cache contents are unaffected by telemetry reset and reset_window."""
        store = InMemoryCache()
        cache = CacheManager(store)
        cache.set("item:100", {"data": "val"})

        self.collector.record_request()
        self.collector.record_key_access("item:100")
        self.collector.reset_window()

        self.assertEqual(cache.get("item:100"), {"data": "val"})

        self.collector.reset()
        self.assertEqual(cache.get("item:100"), {"data": "val"})

    def test_cache_object_metadata_unaffected_by_telemetry_window_reset(self):
        """I. CacheObjectMetadata is unaffected by telemetry window reset."""
        store = InMemoryCache()
        cache = CacheManager(store)
        cache.set("item:200", {"data": "val"})
        meta = cache.create_metadata("item:200", size_bytes=32, retrieval_cost_ms=25.0)

        self.collector.record_request()
        self.collector.record_key_access("item:200")
        self.collector.reset_window()

        retrieved_meta = cache.get_metadata("item:200")
        self.assertIsNotNone(retrieved_meta)
        self.assertEqual(retrieved_meta.key, "item:200")
        self.assertEqual(retrieved_meta.access_count, 1)
        self.assertEqual(retrieved_meta.retrieval_cost_ms, 25.0)

    def test_no_division_by_zero(self):
        """J. No division-by-zero errors: zero elapsed time, zero requests, zero backend calls."""
        # Current time == window_start -> window_seconds == 0.0
        obs = self.collector.observe()
        self.assertEqual(obs.window_seconds, 0.0)
        self.assertEqual(obs.request_rate, 0.0)
        self.assertEqual(obs.hit_rate, 0.0)
        self.assertEqual(obs.miss_rate, 0.0)
        self.assertEqual(obs.backend_latency_ms, 0.0)

        # Requests recorded but zero window time
        self.collector.record_request()
        obs2 = self.collector.observe()
        self.assertEqual(obs2.window_seconds, 0.0)
        self.assertEqual(obs2.request_rate, 0.0)


if __name__ == "__main__":
    unittest.main()
