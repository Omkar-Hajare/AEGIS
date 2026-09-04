import json
import logging
from typing import Any

import redis

from cache.manager import CacheStore

logger = logging.getLogger(__name__)


class RedisCache(CacheStore):
    """Redis-backed CacheStore implementation using JSON serialization."""

    def __init__(
        self,
        host: str = "localhost",
        port: int = 6379,
        db: int = 0,
        password: str | None = None,
        client: Any | None = None,
    ) -> None:
        self.host = host
        self.port = port
        self.db = db
        self.password = password
        if client is not None:
            self._client = client
        else:
            self._client = redis.Redis(
                host=host,
                port=port,
                db=db,
                password=password or None,
                decode_responses=True,
            )

    def get(self, key: str) -> Any | None:
        """Retrieve and deserialize a JSON-compatible value from Redis.

        Returns None if key does not exist or payload cannot be deserialized.
        """
        raw_val = self._client.get(key)
        if raw_val is None:
            return None
        try:
            return json.loads(raw_val)
        except (json.JSONDecodeError, TypeError, UnicodeDecodeError) as e:
            logger.warning("Failed to deserialize Redis value for key %s: %s", key, e)
            return None

    def set(self, key: str, value: Any) -> None:
        """Serialize a JSON-compatible value and store it in Redis.

        Raises TypeError if value cannot be serialized to JSON.
        """
        serialized = json.dumps(value)
        self._client.set(key, serialized)

    def delete(self, key: str) -> bool:
        """Delete a key from Redis. Returns True if key existed, False otherwise."""
        deleted_count = self._client.delete(key)
        return bool(deleted_count > 0)

    def exists(self, key: str) -> bool:
        """Check if a key exists in Redis. Returns True if key exists, False otherwise."""
        exists_count = self._client.exists(key)
        return bool(exists_count > 0)
