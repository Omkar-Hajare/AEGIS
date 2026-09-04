import unittest
from unittest.mock import MagicMock

from cache.in_memory import InMemoryCache
from cache.manager import CacheManager, CacheStore
from cache.metadata import CacheObjectMetadata


class TestCacheManager(unittest.TestCase):
    def setUp(self):
        self.store = InMemoryCache()
        self.manager = CacheManager(self.store)

    def test_delegation_get(self):
        """Verify CacheManager.get() delegates directly to the underlying CacheStore."""
        mock_store = MagicMock(spec=CacheStore)
        mock_store.get.return_value = {"key": "value"}
        mgr = CacheManager(mock_store)

        result = mgr.get("sample_key")
        mock_store.get.assert_called_once_with("sample_key")
        self.assertEqual(result, {"key": "value"})

    def test_delegation_set(self):
        """Verify CacheManager.set() delegates directly to the underlying CacheStore."""
        mock_store = MagicMock(spec=CacheStore)
        mgr = CacheManager(mock_store)

        mgr.set("sample_key", [1, 2, 3])
        mock_store.set.assert_called_once_with("sample_key", [1, 2, 3])

    def test_delegation_delete(self):
        """Verify CacheManager.delete() delegates to store and cleans up associated metadata."""
        mock_store = MagicMock(spec=CacheStore)
        mock_store.delete.return_value = True
        mgr = CacheManager(mock_store)

        mgr.create_metadata("target_key", size_bytes=64, retrieval_cost_ms=12.0)
        self.assertIsNotNone(mgr.get_metadata("target_key"))

        deleted = mgr.delete("target_key")
        mock_store.delete.assert_called_once_with("target_key")
        self.assertTrue(deleted)
        self.assertIsNone(mgr.get_metadata("target_key"), "Metadata must be deleted when key is deleted")

    def test_delegation_exists(self):
        """Verify CacheManager.exists() delegates directly to the underlying CacheStore."""
        mock_store = MagicMock(spec=CacheStore)
        mock_store.exists.return_value = True
        mgr = CacheManager(mock_store)

        self.assertTrue(mgr.exists("target_key"))
        mock_store.exists.assert_called_once_with("target_key")

    def test_metadata_independent_from_cached_values(self):
        """Setting cache values does not automatically create metadata, and vice versa."""
        self.manager.set("payload_only", {"foo": "bar"})
        self.assertEqual(self.manager.get("payload_only"), {"foo": "bar"})
        self.assertIsNone(
            self.manager.get_metadata("payload_only"),
            "Cached value should not implicitly produce metadata",
        )

        self.manager.create_metadata("meta_only", size_bytes=100, retrieval_cost_ms=25.0)
        self.assertIsNotNone(self.manager.get_metadata("meta_only"))
        self.assertIsNone(
            self.manager.get("meta_only"),
            "Metadata should not implicitly produce cache value",
        )

    def test_delete_missing_key_does_not_raise(self):
        """Deleting a non-existent key returns False without error."""
        self.assertFalse(self.manager.delete("missing_key"))

    def test_metadata_lifecycle(self):
        """Verify creating, explicitly setting, retrieving, and clearing metadata."""
        meta1 = self.manager.create_metadata("item:1", size_bytes=120, retrieval_cost_ms=15.0)
        self.assertEqual(meta1.key, "item:1")
        self.assertEqual(meta1.access_count, 1)
        self.assertEqual(meta1.miss_count, 1)
        self.assertEqual(meta1.hit_count, 0)

        meta2 = CacheObjectMetadata(key="item:2", size_bytes=240, retrieval_cost_ms=30.0)
        self.manager.set_metadata("item:2", meta2)

        all_meta = self.manager.get_all_metadata()
        self.assertEqual(len(all_meta), 2)
        self.assertIn("item:1", all_meta)
        self.assertIn("item:2", all_meta)

        self.manager.clear_metadata()
        self.assertEqual(self.manager.get_all_metadata(), {})
        self.assertIsNone(self.manager.get_metadata("item:1"))

    def test_metadata_recording_methods(self):
        """Verify manager recording methods update the corresponding metadata counters."""
        self.manager.create_metadata("tracked:1", size_bytes=50, retrieval_cost_ms=10.0)

        self.manager.record_hit("tracked:1")
        meta = self.manager.get_metadata("tracked:1")
        self.assertIsNotNone(meta)
        self.assertEqual(meta.hit_count, 1)
        self.assertEqual(meta.access_count, 2)

        self.manager.record_miss("tracked:1")
        self.assertEqual(meta.miss_count, 2)
        self.assertEqual(meta.access_count, 3)

        self.manager.record_access("tracked:1")
        self.assertEqual(meta.access_count, 4)

        self.manager.record_backend_retrieval("tracked:1", 75.5)
        self.assertEqual(meta.retrieval_cost_ms, 75.5)

    def test_metadata_recording_missing_key_noop(self):
        """Recording access/hit/miss on an untracked key is a safe no-op and does not raise."""
        self.manager.record_access("unknown:key")
        self.manager.record_hit("unknown:key")
        self.manager.record_miss("unknown:key")
        self.manager.record_backend_retrieval("unknown:key", 50.0)
        self.assertIsNone(self.manager.get_metadata("unknown:key"))


if __name__ == "__main__":
    unittest.main()
