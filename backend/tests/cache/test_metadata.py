from datetime import datetime, timezone
import time
import unittest

from cache.in_memory import InMemoryCache
from cache.manager import CacheManager
from cache.metadata import CacheObjectMetadata, calculate_payload_size_bytes


class TestCacheMetadata(unittest.TestCase):
    def test_create_metadata_defaults(self):
        """Create a new metadata object and verify v1, default counters, and UTC timezone."""
        meta = CacheObjectMetadata(
            key="product:1",
            size_bytes=128,
            retrieval_cost_ms=35.5,
        )
        self.assertEqual(meta.key, "product:1")
        self.assertEqual(meta.size_bytes, 128)
        self.assertEqual(meta.retrieval_cost_ms, 35.5)
        self.assertEqual(meta.version, "v1")
        self.assertEqual(meta.access_count, 1)
        self.assertEqual(meta.miss_count, 1)
        self.assertEqual(meta.hit_count, 0)
        self.assertIsInstance(meta.created_at, datetime)
        self.assertIsInstance(meta.last_accessed, datetime)
        self.assertEqual(meta.created_at.tzinfo, timezone.utc)
        self.assertEqual(meta.last_accessed.tzinfo, timezone.utc)

    def test_record_access_updates_counter_and_timestamp(self):
        """Verify record_access updates access_count and last_accessed deterministically."""
        base_time = datetime(2026, 9, 4, 12, 0, 0, tzinfo=timezone.utc)
        later_time = datetime(2026, 9, 4, 12, 0, 1, tzinfo=timezone.utc)
        meta = CacheObjectMetadata(
            key="item:1",
            size_bytes=50,
            retrieval_cost_ms=10.0,
            created_at=base_time,
            last_accessed=base_time,
        )
        self.assertEqual(meta.access_count, 1)
        self.assertEqual(meta.last_accessed, base_time)

        meta.record_access(now=later_time)
        self.assertEqual(meta.access_count, 2)
        self.assertEqual(meta.last_accessed, later_time)

    def test_record_hit_updates_access_and_hit_count(self):
        """Verify record_hit updates access_count and hit_count, preserving retrieval latency."""
        meta = CacheObjectMetadata(key="item:2", size_bytes=50, retrieval_cost_ms=10.0)
        initial_access = meta.access_count
        initial_hits = meta.hit_count
        initial_misses = meta.miss_count

        meta.record_hit()

        self.assertEqual(meta.access_count, initial_access + 1)
        self.assertEqual(meta.hit_count, initial_hits + 1)
        self.assertEqual(meta.miss_count, initial_misses)
        self.assertEqual(meta.retrieval_cost_ms, 10.0, "HIT must not change retrieval latency")

    def test_record_miss_updates_access_and_miss_count(self):
        """Verify record_miss updates access_count and miss_count."""
        meta = CacheObjectMetadata(key="item:3", size_bytes=50, retrieval_cost_ms=10.0)
        initial_access = meta.access_count
        initial_hits = meta.hit_count
        initial_misses = meta.miss_count

        meta.record_miss()

        self.assertEqual(meta.access_count, initial_access + 1)
        self.assertEqual(meta.miss_count, initial_misses + 1)
        self.assertEqual(meta.hit_count, initial_hits)
        self.assertEqual(meta.retrieval_cost_ms, 10.0, "MISS alone does not alter retrieval latency until recorded")

    def test_record_backend_retrieval_updates_latency(self):
        """Verify backend retrieval records latency."""
        meta = CacheObjectMetadata(key="item:4", size_bytes=50, retrieval_cost_ms=10.0)
        self.assertEqual(meta.retrieval_cost_ms, 10.0)

        meta.record_backend_retrieval(42.8)
        self.assertEqual(meta.retrieval_cost_ms, 42.8)

    def test_metadata_storage_independence(self):
        """Verify CacheObjectMetadata is independent from actual cache storage mechanism."""
        meta = CacheObjectMetadata(key="independent:key", size_bytes=100, retrieval_cost_ms=20.0)
        meta.record_hit()
        meta.record_miss()
        self.assertEqual(meta.key, "independent:key")
        self.assertEqual(meta.access_count, 3)

    def test_size_calculation(self):
        """Verify calculate_payload_size_bytes returns deterministic UTF-8 byte length."""
        payload = {"product_id": "42", "name": "Product 42"}
        size = calculate_payload_size_bytes(payload)
        self.assertIsInstance(size, int)
        self.assertGreater(size, 0)
        # Should be deterministic
        self.assertEqual(size, calculate_payload_size_bytes(payload))

    def test_cache_manager_metadata_operations(self):
        """Verify metadata can be created, retrieved by key, and retrieved as all metadata."""
        store = InMemoryCache()
        manager = CacheManager(store)

        self.assertIsNone(manager.get_metadata("key:1"))
        self.assertEqual(manager.get_all_metadata(), {})

        created = manager.create_metadata(
            key="key:1",
            size_bytes=64,
            retrieval_cost_ms=25.0,
        )
        self.assertEqual(created.key, "key:1")

        retrieved = manager.get_metadata("key:1")
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.key, "key:1")
        self.assertEqual(retrieved.retrieval_cost_ms, 25.0)

        # Update via manager methods
        manager.record_hit("key:1")
        self.assertEqual(retrieved.hit_count, 1)
        self.assertEqual(retrieved.access_count, 2)

        manager.record_miss("key:1")
        self.assertEqual(retrieved.miss_count, 2)
        self.assertEqual(retrieved.access_count, 3)

        manager.record_backend_retrieval("key:1", 55.0)
        self.assertEqual(retrieved.retrieval_cost_ms, 55.0)

        # All metadata
        all_meta = manager.get_all_metadata()
        self.assertIn("key:1", all_meta)
        self.assertEqual(len(all_meta), 1)

        # Clear metadata
        manager.clear_metadata()
        self.assertIsNone(manager.get_metadata("key:1"))
        self.assertEqual(manager.get_all_metadata(), {})


if __name__ == "__main__":
    unittest.main()
