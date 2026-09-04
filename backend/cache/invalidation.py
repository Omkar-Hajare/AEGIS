"""Application-facing cache invalidation boundary.

Provides an explicit, reusable boundary for invalidating cache entries following
successful database write operations, without coupling the cache layer to specific
database models, transactions, or CRUD endpoints.

Consistency Rules:
- A successful database write must invalidate affected cache keys.
- A failed database write must not trigger invalidation.
- This boundary prepares the system for future business write operations.
"""

from __future__ import annotations

from collections.abc import Sequence

try:
    from cache.manager import CacheManager
except ImportError:
    from backend.cache.manager import CacheManager  # type: ignore[no-redef]


class CacheInvalidator:
    """Pure, application-facing cache invalidation coordinator.

    Accepts a CacheManager through dependency injection to perform targeted,
    deterministic cache invalidation.
    """

    def __init__(self, cache_manager: CacheManager) -> None:
        """Initialize CacheInvalidator with an injected CacheManager.

        Args:
            cache_manager: The active CacheManager handling the cache store and metadata.

        Raises:
            TypeError: If cache_manager is not an instance of CacheManager.
        """
        if not isinstance(cache_manager, CacheManager):
            raise TypeError(
                f"cache_manager must be an instance of CacheManager, got {type(cache_manager).__name__}"
            )
        self._cache_manager = cache_manager

    @property
    def cache_manager(self) -> CacheManager:
        """The underlying injected CacheManager instance."""
        return self._cache_manager

    def invalidate_key(self, key: str) -> bool:
        """Invalidate a single cache key and its associated metadata.

        Args:
            key: The cache key to invalidate.

        Returns:
            True if the key was deleted from the underlying cache store, False otherwise.

        Raises:
            TypeError: If key is not a string.
        """
        if isinstance(key, bool) or not isinstance(key, str):
            raise TypeError(f"key must be a string, got {type(key).__name__}")
        return self._cache_manager.invalidate(key)

    def invalidate_keys(self, keys: Sequence[str]) -> list[str]:
        """Invalidate a sequence of cache keys deterministically.

        Args:
            keys: Sequence of cache keys to invalidate.

        Returns:
            List of keys that were actually present and deleted, preserving input order.

        Raises:
            TypeError: If keys is a single string/bytes or not an iterable sequence.
        """
        if isinstance(keys, (str, bytes)):
            raise TypeError("keys must be a sequence of strings, not a single string")

        deleted_keys: list[str] = []
        for key in keys:
            if self.invalidate_key(key):
                deleted_keys.append(key)
        return deleted_keys


def invalidate_key(cache_manager: CacheManager, key: str) -> bool:
    """Convenience helper to invalidate a single key using an injected CacheManager.

    Args:
        cache_manager: The active CacheManager instance.
        key: The cache key to invalidate.

    Returns:
        True if the key was deleted, False otherwise.
    """
    return CacheInvalidator(cache_manager).invalidate_key(key)


def invalidate_keys(cache_manager: CacheManager, keys: Sequence[str]) -> list[str]:
    """Convenience helper to invalidate multiple keys using an injected CacheManager.

    Args:
        cache_manager: The active CacheManager instance.
        keys: Sequence of cache keys to invalidate.

    Returns:
        List of keys that were actually present and deleted.
    """
    return CacheInvalidator(cache_manager).invalidate_keys(keys)
