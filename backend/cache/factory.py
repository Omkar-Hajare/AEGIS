from app.config import Settings
from app.config import settings as default_settings

from cache.in_memory import InMemoryCache
from cache.manager import CacheManager, CacheStore
from cache.redis import RedisCache


def get_cache_store(settings: Settings | None = None) -> CacheStore:
    """Instantiate and return a CacheStore based on the configured CACHE_BACKEND."""
    cfg = settings or default_settings
    backend = cfg.cache_backend.lower().strip()

    if backend == "inmemory":
        return InMemoryCache()
    elif backend == "redis":
        return RedisCache(
            host=cfg.redis_host,
            port=cfg.redis_port,
            db=cfg.redis_db,
            password=cfg.redis_password or None,
        )
    else:
        raise ValueError(f"Unsupported cache backend: '{cfg.cache_backend}'")


def create_cache_manager(settings: Settings | None = None) -> CacheManager:
    """Create a CacheManager configured with the selected CacheStore."""
    store = get_cache_store(settings)
    return CacheManager(store)
