import unittest

from api.routes.data import cache_manager, get_product, get_recommendation
from telemetry.collector import telemetry_collector


class TestCacheMetadataFlow(unittest.TestCase):
    def setUp(self):
        """Reset cache, metadata, and telemetry before each test to guarantee test isolation."""
        cache_manager._store._store.clear()
        cache_manager.clear_metadata()
        telemetry_collector.reset()

    def test_product_cache_metadata_flow(self):
        """Verify complete product flow: MISS -> HIT -> different key with metadata and telemetry tracking."""
        # --- First request: Cache MISS ---
        res1 = get_product("42")
        self.assertEqual(res1["product_id"], "42")
        self.assertEqual(res1["name"], "Product 42")

        # Verify metadata
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

        # Verify telemetry counters after first request
        snap1 = telemetry_collector.snapshot()
        self.assertEqual(snap1["total_requests"], 1)
        self.assertEqual(snap1["cache_misses"], 1)
        self.assertEqual(snap1["cache_hits"], 0)
        self.assertEqual(snap1["backend_calls"], 1)

        # --- Second request: Cache HIT ---
        res2 = get_product("42")
        self.assertEqual(res2, res1)

        # Verify metadata on HIT
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

        # Verify telemetry counters after second request
        snap2 = telemetry_collector.snapshot()
        self.assertEqual(snap2["total_requests"], 2)
        self.assertEqual(snap2["cache_misses"], 1)
        self.assertEqual(snap2["cache_hits"], 1)
        self.assertEqual(snap2["backend_calls"], 1, "HIT must not increase backend calls")

        # --- Third request: Different product ID (product:99) ---
        res3 = get_product("99")
        self.assertEqual(res3["product_id"], "99")

        # Verify new product has its own independent metadata
        meta_99 = cache_manager.get_metadata("product:99")
        self.assertIsNotNone(meta_99)
        self.assertEqual(meta_99.key, "product:99")
        self.assertEqual(meta_99.access_count, 1)
        self.assertEqual(meta_99.miss_count, 1)
        self.assertEqual(meta_99.hit_count, 0)

        # Verify original product metadata is unaffected
        meta_42 = cache_manager.get_metadata("product:42")
        self.assertEqual(meta_42.access_count, 2)
        self.assertEqual(meta_42.hit_count, 1)

        # Verify overall telemetry
        snap3 = telemetry_collector.snapshot()
        self.assertEqual(snap3["total_requests"], 3)
        self.assertEqual(snap3["cache_misses"], 2)
        self.assertEqual(snap3["cache_hits"], 1)
        self.assertEqual(snap3["backend_calls"], 2)

    def test_recommendation_cache_metadata_flow(self):
        """Verify recommendation cache metadata lifecycle on MISS and subsequent HIT."""
        # First request: Cache MISS
        res1 = get_recommendation("42")
        self.assertEqual(res1["user_id"], "42")
        self.assertIn("recommendations", res1)

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

        snap1 = telemetry_collector.snapshot()
        self.assertEqual(snap1["total_requests"], 1)
        self.assertEqual(snap1["cache_misses"], 1)
        self.assertEqual(snap1["cache_hits"], 0)
        self.assertEqual(snap1["backend_calls"], 1)

        # Second request: Cache HIT
        res2 = get_recommendation("42")
        self.assertEqual(res2, res1)

        meta_hit = cache_manager.get_metadata("recommendation:42")
        self.assertIsNotNone(meta_hit)
        self.assertEqual(meta_hit.access_count, 2)
        self.assertEqual(meta_hit.miss_count, 1)
        self.assertEqual(meta_hit.hit_count, 1)
        self.assertEqual(meta_hit.retrieval_cost_ms, initial_cost)
        self.assertGreaterEqual(meta_hit.last_accessed, initial_last_accessed)

        snap2 = telemetry_collector.snapshot()
        self.assertEqual(snap2["total_requests"], 2)
        self.assertEqual(snap2["cache_misses"], 1)
        self.assertEqual(snap2["cache_hits"], 1)
        self.assertEqual(snap2["backend_calls"], 1)

    def test_cache_deletion_repopulation_flow(self):
        """Verify deleting a cached entry and re-requesting cleanly creates fresh state."""
        # Initial request
        get_product("10")
        self.assertTrue(cache_manager.exists("product:10"))
        self.assertIsNotNone(cache_manager.get_metadata("product:10"))

        # Delete key
        deleted = cache_manager.delete("product:10")
        self.assertTrue(deleted)
        self.assertFalse(cache_manager.exists("product:10"))
        self.assertIsNone(cache_manager.get_metadata("product:10"))

        # Re-request: should trigger MISS, recreate cache entry and metadata
        get_product("10")
        self.assertTrue(cache_manager.exists("product:10"))
        new_meta = cache_manager.get_metadata("product:10")
        self.assertIsNotNone(new_meta)
        self.assertEqual(new_meta.access_count, 1)
        self.assertEqual(new_meta.miss_count, 1)
        self.assertEqual(new_meta.hit_count, 0)


if __name__ == "__main__":
    unittest.main()
