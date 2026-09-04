"""Unit tests for cache invalidation boundary.

Tests cover:
- CacheInvalidator initialization and validation
- invalidate_key() delegation and return values
- invalidate_keys() deterministic invalidation and return list of actually deleted keys
- Handling of non-existent/missing keys
- Type errors for invalid keys or parameters
- Standalone helper functions invalidate_key and invalidate_keys
- Cache consistency flow: invalidation on simulated successful write vs no invalidation on failed write
- Existing cache operations remain unaffected
"""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from cache.in_memory import InMemoryCache
from cache.invalidation import CacheInvalidator, invalidate_key, invalidate_keys
from cache.manager import CacheManager


class TestCacheInvalidator(unittest.TestCase):
    def setUp(self) -> None:
        self.store = InMemoryCache()
        self.manager = CacheManager(self.store)
        self.invalidator = CacheInvalidator(self.manager)

    def test_initialization_success(self) -> None:
        """CacheInvalidator initializes with valid CacheManager."""
        self.assertIs(self.invalidator.cache_manager, self.manager)

    def test_initialization_invalid_type_raises(self) -> None:
        """CacheInvalidator raises TypeError if passed an invalid manager."""
        with self.assertRaises(TypeError):
            CacheInvalidator("not_a_cache_manager")  # type: ignore[arg-type]
        with self.assertRaises(TypeError):
            CacheInvalidator(None)  # type: ignore[arg-type]

    def test_invalidate_key_success(self) -> None:
        """invalidate_key deletes existing key and metadata, returning True."""
        self.manager.set("user:101", {"name": "Alice"})
        self.manager.create_metadata("user:101", size_bytes=50, retrieval_cost_ms=10.0)

        self.assertTrue(self.manager.exists("user:101"))
        self.assertIsNotNone(self.manager.get_metadata("user:101"))

        result = self.invalidator.invalidate_key("user:101")
        self.assertTrue(result)
        self.assertFalse(self.manager.exists("user:101"))
        self.assertIsNone(self.manager.get("user:101"))
        self.assertIsNone(self.manager.get_metadata("user:101"))

    def test_invalidate_key_missing_returns_false(self) -> None:
        """invalidate_key returns False when key does not exist."""
        result = self.invalidator.invalidate_key("missing:key")
        self.assertFalse(result)

    def test_invalidate_key_invalid_type_raises(self) -> None:
        """invalidate_key raises TypeError if key is not a string."""
        with self.assertRaises(TypeError):
            self.invalidator.invalidate_key(123)  # type: ignore[arg-type]
        with self.assertRaises(TypeError):
            self.invalidator.invalidate_key(None)  # type: ignore[arg-type]
        with self.assertRaises(TypeError):
            self.invalidator.invalidate_key(True)  # type: ignore[arg-type]

    def test_invalidate_key_delegation(self) -> None:
        """invalidate_key delegates to CacheManager.invalidate()."""
        mock_mgr = MagicMock(spec=CacheManager)
        mock_mgr.invalidate.return_value = True
        invalidator = CacheInvalidator(mock_mgr)

        res = invalidator.invalidate_key("product:42")
        self.assertTrue(res)
        mock_mgr.invalidate.assert_called_once_with("product:42")

    def test_invalidate_keys_all_exist(self) -> None:
        """invalidate_keys invalidates all existing keys and returns list of all deleted keys."""
        keys = ["item:1", "item:2", "item:3"]
        for k in keys:
            self.manager.set(k, f"val_{k}")
            self.manager.create_metadata(k, size_bytes=20)

        deleted = self.invalidator.invalidate_keys(keys)
        self.assertEqual(deleted, keys)
        for k in keys:
            self.assertFalse(self.manager.exists(k))
            self.assertIsNone(self.manager.get_metadata(k))

    def test_invalidate_keys_partial_exist(self) -> None:
        """invalidate_keys only returns keys that were actually present and deleted."""
        self.manager.set("existing:1", "data1")
        self.manager.set("existing:2", "data2")

        # Query a mix of present and absent keys
        query_keys = ["existing:1", "missing:1", "existing:2", "missing:2"]
        deleted = self.invalidator.invalidate_keys(query_keys)

        self.assertEqual(deleted, ["existing:1", "existing:2"])
        self.assertFalse(self.manager.exists("existing:1"))
        self.assertFalse(self.manager.exists("existing:2"))

    def test_invalidate_keys_none_exist(self) -> None:
        """invalidate_keys returns an empty list if none of the keys exist."""
        deleted = self.invalidator.invalidate_keys(["none:1", "none:2"])
        self.assertEqual(deleted, [])

    def test_invalidate_keys_empty_sequence(self) -> None:
        """invalidate_keys returns an empty list when given an empty sequence."""
        self.assertEqual(self.invalidator.invalidate_keys([]), [])
        self.assertEqual(self.invalidator.invalidate_keys(()), [])

    def test_invalidate_keys_invalid_type_raises(self) -> None:
        """invalidate_keys raises TypeError if passed a string or non-sequence."""
        with self.assertRaises(TypeError):
            self.invalidator.invalidate_keys("not_a_sequence")  # type: ignore[arg-type]
        with self.assertRaises(TypeError):
            self.invalidator.invalidate_keys(b"bytes_sequence")  # type: ignore[arg-type]

    def test_invalidate_keys_deterministic_order(self) -> None:
        """invalidate_keys preserves the exact ordering of input sequence."""
        for i in range(5):
            self.manager.set(f"k:{i}", i)

        order = ["k:3", "k:1", "k:4", "k:0", "k:2"]
        deleted = self.invalidator.invalidate_keys(order)
        self.assertEqual(deleted, order)

    def test_standalone_helpers(self) -> None:
        """Standalone invalidate_key and invalidate_keys helpers function identically."""
        self.manager.set("standalone:1", "v1")
        self.manager.set("standalone:2", "v2")

        # Standalone single key
        res1 = invalidate_key(self.manager, "standalone:1")
        self.assertTrue(res1)
        self.assertFalse(self.manager.exists("standalone:1"))

        # Standalone multiple keys
        res2 = invalidate_keys(self.manager, ["standalone:2", "standalone:missing"])
        self.assertEqual(res2, ["standalone:2"])
        self.assertFalse(self.manager.exists("standalone:2"))

    def test_cache_consistency_workflow_simulation(self) -> None:
        """Simulate cache-aside write consistency pattern:
        1. Successful database write triggers cache invalidation -> cache is cleared.
        2. Failed database write does not trigger cache invalidation -> cache remains intact.
        """
        key = "account:1001"
        self.manager.set(key, {"balance": 100})
        self.manager.create_metadata(key, size_bytes=64)

        # Simulation 1: Database write succeeds -> invalidate cache
        def update_balance_success(new_balance: int) -> None:
            # Simulated DB write succeeds; cache invalidation boundary invoked upon success
            self.invalidator.invalidate_key(key)

        update_balance_success(150)
        self.assertIsNone(
            self.manager.get(key), "Cache must be invalidated after successful write"
        )
        self.assertIsNone(self.manager.get_metadata(key))

        # Re-populate cache after read
        self.manager.set(key, {"balance": 150})

        # Simulation 2: Database write fails -> invalidation must NOT be invoked
        def update_balance_failure(new_balance: int) -> None:
            try:
                # Simulated DB write failure
                raise RuntimeError("DB connection timeout")
            except RuntimeError:
                # On failure, invalidation is skipped
                pass

        update_balance_failure(200)
        self.assertEqual(
            self.manager.get(key),
            {"balance": 150},
            "Cache must retain previous value when database write fails",
        )

    def test_existing_cache_behavior_remains_unchanged(self) -> None:
        """Verifies get, set, exists, and metadata lifecycle are completely unaffected."""
        self.manager.set("item:test", 42)
        self.assertEqual(self.manager.get("item:test"), 42)
        self.assertTrue(self.manager.exists("item:test"))

        meta = self.manager.create_metadata("item:test", size_bytes=10)
        self.assertEqual(meta.key, "item:test")
        self.assertIsNotNone(self.manager.get_metadata("item:test"))

        # Delete still works as before
        self.assertTrue(self.manager.delete("item:test"))
        self.assertFalse(self.manager.exists("item:test"))
        self.assertIsNone(self.manager.get_metadata("item:test"))


if __name__ == "__main__":
    unittest.main()
