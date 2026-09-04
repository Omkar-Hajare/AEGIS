import time
import unittest

from api.routes.data import cache_manager, get_product, get_recommendation
from telemetry.collector import telemetry_collector


class TestCacheMetadataFlow(unittest.TestCase):
    def setUp(self):
        """Reset cache, metadata, and telemetry before each test."""
        cache_manager._store._store.clear()
        cache_manager.clear_metadata()
        telemetry_collector.reset()

    def test_product_cache_metadata_flow(self):
        """Verify product cache metadata lifecycle on MISS and subsequent HIT."""
        # First request: Cache MISS
        res1 = get_product("42")
        self.assertEqual(res1["product_id"], "42")

        meta = cache_manager.get_metadata("product:42")
        self.assertIsNotNone(meta, "Metadata should exist after first request")
        self.assertEqual(meta.key, "product:42")
        self.assertEqual(meta.version, "v1")
        self.assertEqual(meta.access_count, 1)
        self.assertEqual(meta.miss_count, 1)
        self.assertEqual(meta.hit_count, 0)
        self.assertGreater(meta.retrieval_cost_ms, 0.0)
        self.assertGreater(meta.size_bytes, 0)
        initial_retrieval_cost = meta.retrieval_cost_ms
        initial_last_accessed = meta.last_accessed

        # Second request: Cache HIT
        time.sleep(0.002)
        res2 = get_product("42")
        self.assertEqual(res2, res1)

        meta_hit = cache_manager.get_metadata("product:42")
        self.assertIsNotNone(meta_hit)
        self.assertEqual(meta_hit.access_count, 2)
        self.assertEqual(meta_hit.miss_count, 1, "miss_count should remain unchanged on HIT")
        self.assertEqual(meta_hit.hit_count, 1, "hit_count should become 1 on HIT")
        self.assertEqual(
            meta_hit.retrieval_cost_ms,
            initial_retrieval_cost,
            "retrieval_cost_ms should remain unchanged on HIT",
        )
        self.assertGreaterEqual(meta_hit.last_accessed, initial_last_accessed)

    def test_recommendation_cache_metadata_flow(self):
        """Verify recommendation cache metadata lifecycle on MISS and subsequent HIT."""
        # First request: Cache MISS
        res1 = get_recommendation("42")
        self.assertEqual(res1["user_id"], "42")

        meta = cache_manager.get_metadata("recommendation:42")
        self.assertIsNotNone(meta, "Metadata should exist after first recommendation request")
        self.assertEqual(meta.key, "recommendation:42")
        self.assertEqual(meta.version, "v1")
        self.assertEqual(meta.access_count, 1)
        self.assertEqual(meta.miss_count, 1)
        self.assertEqual(meta.hit_count, 0)
        self.assertGreater(meta.retrieval_cost_ms, 400.0)  # simulator pauses ~600ms
        self.assertGreater(meta.size_bytes, 0)
        initial_cost = meta.retrieval_cost_ms
        initial_last_accessed = meta.last_accessed

        # Second request: Cache HIT
        time.sleep(0.002)
        res2 = get_recommendation("42")
        self.assertEqual(res2, res1)

        meta_hit = cache_manager.get_metadata("recommendation:42")
        self.assertIsNotNone(meta_hit)
        self.assertEqual(meta_hit.access_count, 2)
        self.assertEqual(meta_hit.miss_count, 1)
        self.assertEqual(meta_hit.hit_count, 1)
        self.assertEqual(meta_hit.retrieval_cost_ms, initial_cost)
        self.assertGreaterEqual(meta_hit.last_accessed, initial_last_accessed)


if __name__ == "__main__":
    unittest.main()
