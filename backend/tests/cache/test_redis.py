import unittest
from unittest.mock import MagicMock

from cache.manager import CacheStore
from cache.redis import RedisCache


class FakeRedisClient:
    """In-memory fake Redis client simulating string operations for testing."""

    def __init__(self):
        self._data: dict[str, str] = {}

    def get(self, key: str) -> str | None:
        return self._data.get(key)

    def set(self, key: str, value: str) -> bool:
        self._data[key] = value
        return True

    def delete(self, key: str) -> int:
        if key in self._data:
            del self._data[key]
            return 1
        return 0

    def exists(self, key: str) -> int:
        return 1 if key in self._data else 0


class TestRedisCache(unittest.TestCase):
    def setUp(self):
        self.fake_client = FakeRedisClient()
        self.cache = RedisCache(client=self.fake_client)

    def test_implements_cache_store_interface(self):
        """Verify RedisCache implements abstract base class CacheStore."""
        self.assertIsInstance(self.cache, CacheStore)

    def test_get_missing_key_returns_none(self):
        """get() on a non-existent key returns None."""
        self.assertIsNone(self.cache.get("nonexistent"))

    def test_set_and_get_primitives(self):
        """Verify storing and retrieving JSON-compatible primitives."""
        self.cache.set("int_key", 42)
        self.assertEqual(self.cache.get("int_key"), 42)

        self.cache.set("str_key", "hello world")
        self.assertEqual(self.cache.get("str_key"), "hello world")

        self.cache.set("float_key", 3.1415)
        self.assertEqual(self.cache.get("float_key"), 3.1415)

        self.cache.set("bool_key", True)
        self.assertEqual(self.cache.get("bool_key"), True)

    def test_set_and_get_json_structures(self):
        """Verify storing and retrieving complex nested dictionaries and lists."""
        payload = {
            "product_id": "item_123",
            "name": "Super Widget",
            "tags": ["fast", "durable"],
            "metadata": {"weight": 1.25, "active": True},
        }
        self.cache.set("product:item_123", payload)
        retrieved = self.cache.get("product:item_123")
        self.assertEqual(retrieved, payload)

    def test_overwrite_existing_key(self):
        """set() with an existing key overwrites the previous value."""
        self.cache.set("key1", {"version": 1})
        self.assertEqual(self.cache.get("key1"), {"version": 1})

        self.cache.set("key1", {"version": 2})
        self.assertEqual(self.cache.get("key1"), {"version": 2})

    def test_exists(self):
        """exists() returns True for present keys and False for missing keys."""
        self.assertFalse(self.cache.exists("check_key"))
        self.cache.set("check_key", "present")
        self.assertTrue(self.cache.exists("check_key"))

    def test_delete_existing_key(self):
        """delete() on an existing key removes it and returns True."""
        self.cache.set("to_delete", "temp")
        self.assertTrue(self.cache.exists("to_delete"))

        deleted = self.cache.delete("to_delete")
        self.assertTrue(deleted)
        self.assertFalse(self.cache.exists("to_delete"))
        self.assertIsNone(self.cache.get("to_delete"))

    def test_delete_missing_key(self):
        """delete() on an absent key returns False."""
        self.assertFalse(self.cache.delete("never_existed"))

    def test_get_corrupted_json_returns_none(self):
        """Corrupted/non-JSON data in Redis is gracefully logged and returns None."""
        self.fake_client._data["corrupted"] = "not a valid json {{{["
        self.assertIsNone(self.cache.get("corrupted"))

    def test_set_non_serializable_raises_type_error(self):
        """Attempting to set non-JSON-serializable objects raises TypeError."""
        with self.assertRaises(TypeError):
            self.cache.set("bad_obj", object())

    def test_custom_client_injection(self):
        """Verify injecting a custom client sets _client without real network calls."""
        mock_client = MagicMock()
        mock_client.get.return_value = '{"injected": true}'
        cache = RedisCache(client=mock_client)
        result = cache.get("test_key")
        mock_client.get.assert_called_once_with("test_key")
        self.assertEqual(result, {"injected": True})

    def test_default_init_stores_parameters(self):
        """Verify RedisCache parameters are stored upon standard initialization."""
        cache = RedisCache(
            host="redis.internal",
            port=6380,
            db=2,
            password="secret_pass",
        )
        self.assertEqual(cache.host, "redis.internal")
        self.assertEqual(cache.port, 6380)
        self.assertEqual(cache.db, 2)
        self.assertEqual(cache.password, "secret_pass")
        self.assertIsNotNone(cache._client)


if __name__ == "__main__":
    unittest.main()
