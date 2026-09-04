import unittest

from app.config import Settings
from cache.factory import create_cache_manager, get_cache_store
from cache.in_memory import InMemoryCache
from cache.manager import CacheManager
from cache.redis import RedisCache


class TestCacheFactory(unittest.TestCase):
    def test_default_factory_returns_inmemory_cache(self):
        """Default settings produce an InMemoryCache store."""
        store = get_cache_store()
        self.assertIsInstance(store, InMemoryCache)

    def test_factory_inmemory_explicit(self):
        """Explicitly passing inmemory setting produces an InMemoryCache store."""
        custom_settings = Settings(cache_backend="inmemory")
        store = get_cache_store(custom_settings)
        self.assertIsInstance(store, InMemoryCache)

    def test_factory_redis_selection(self):
        """Setting cache_backend='redis' instantiates RedisCache with configured parameters."""
        custom_settings = Settings(
            cache_backend="redis",
            redis_host="cache.local",
            redis_port=6381,
            redis_db=5,
            redis_password="secret_token",
        )
        store = get_cache_store(custom_settings)
        self.assertIsInstance(store, RedisCache)
        self.assertEqual(store.host, "cache.local")
        self.assertEqual(store.port, 6381)
        self.assertEqual(store.db, 5)
        self.assertEqual(store.password, "secret_token")

    def test_factory_unsupported_backend_raises(self):
        """Unrecognized cache backend raises ValueError."""
        bad_settings = Settings(cache_backend="memcached")
        with self.assertRaises(ValueError) as ctx:
            get_cache_store(bad_settings)
        self.assertIn("Unsupported cache backend", str(ctx.exception))

    def test_create_cache_manager_with_default(self):
        """create_cache_manager returns CacheManager wrapping InMemoryCache by default."""
        manager = create_cache_manager()
        self.assertIsInstance(manager, CacheManager)
        self.assertIsInstance(manager._store, InMemoryCache)

    def test_create_cache_manager_with_redis(self):
        """create_cache_manager returns CacheManager wrapping RedisCache when configured."""
        custom_settings = Settings(cache_backend="redis")
        manager = create_cache_manager(custom_settings)
        self.assertIsInstance(manager, CacheManager)
        self.assertIsInstance(manager._store, RedisCache)


if __name__ == "__main__":
    unittest.main()
