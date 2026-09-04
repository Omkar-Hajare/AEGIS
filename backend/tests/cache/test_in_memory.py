import unittest

from cache.in_memory import InMemoryCache
from cache.manager import CacheStore


class TestInMemoryCache(unittest.TestCase):
    def setUp(self):
        self.cache = InMemoryCache()

    def test_implements_cache_store_interface(self):
        """Verify InMemoryCache is an instance of abstract base class CacheStore."""
        self.assertIsInstance(self.cache, CacheStore)

    def test_get_missing_key_returns_none(self):
        """A. get() on non-existent key returns None."""
        self.assertIsNone(self.cache.get("nonexistent_key"))
        self.assertIsNone(self.cache.get(""))

    def test_set_and_get(self):
        """B. set() stores value and get() retrieves it."""
        self.cache.set("greeting", "hello")
        self.assertEqual(self.cache.get("greeting"), "hello")

    def test_overwrite_existing_key(self):
        """C. set() with existing key overwrites the previous value."""
        self.cache.set("key1", "initial")
        self.assertEqual(self.cache.get("key1"), "initial")

        self.cache.set("key1", "updated")
        self.assertEqual(self.cache.get("key1"), "updated")

    def test_exists(self):
        """D. exists() returns True for present keys and False for absent keys."""
        self.assertFalse(self.cache.exists("product:1"))
        self.cache.set("product:1", {"id": 1})
        self.assertTrue(self.cache.exists("product:1"))

    def test_delete_existing_key(self):
        """E. delete() on existing key returns True and removes the item."""
        self.cache.set("temp", 12345)
        self.assertTrue(self.cache.exists("temp"))

        deleted = self.cache.delete("temp")
        self.assertTrue(deleted)
        self.assertFalse(self.cache.exists("temp"))
        self.assertIsNone(self.cache.get("temp"))

    def test_delete_missing_key(self):
        """F. delete() on absent key returns False."""
        self.assertFalse(self.cache.delete("missing"))

    def test_multiple_independent_keys(self):
        """G. Multiple keys operate independently without crosstalk."""
        self.cache.set("alpha", 1)
        self.cache.set("beta", 2)
        self.cache.set("gamma", 3)

        self.assertEqual(self.cache.get("alpha"), 1)
        self.assertEqual(self.cache.get("beta"), 2)
        self.assertEqual(self.cache.get("gamma"), 3)

        self.cache.delete("beta")
        self.assertEqual(self.cache.get("alpha"), 1)
        self.assertIsNone(self.cache.get("beta"))
        self.assertEqual(self.cache.get("gamma"), 3)

    def test_json_compatible_values(self):
        """H. Verify complex JSON-compatible payloads are preserved accurately."""
        payload = {
            "product_id": "999",
            "name": "Super Laptop",
            "price": 999.99,
            "tags": ["tech", "portable", "fast"],
            "specs": {"cpu": "8-core", "ram_gb": 32, "active": True},
        }
        self.cache.set("complex_item", payload)
        retrieved = self.cache.get("complex_item")

        self.assertEqual(retrieved, payload)
        self.assertEqual(retrieved["specs"]["ram_gb"], 32)
        self.assertEqual(retrieved["tags"][1], "portable")


if __name__ == "__main__":
    unittest.main()
