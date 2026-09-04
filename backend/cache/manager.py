from abc import ABC, abstractmethod
from typing import Any

from cache.metadata import CacheObjectMetadata


class CacheStore(ABC):
    @abstractmethod
    def get(self, key: str) -> Any | None:
        pass

    @abstractmethod
    def set(self, key: str, value: Any) -> None:
        pass

    @abstractmethod
    def delete(self, key: str) -> bool:
        pass

    @abstractmethod
    def exists(self, key: str) -> bool:
        pass


class CacheManager:
    def __init__(self, store: CacheStore) -> None:
        self._store = store
        self._metadata: dict[str, CacheObjectMetadata] = {}

    def get(self, key: str) -> Any | None:
        return self._store.get(key)

    def set(self, key: str, value: Any) -> None:
        self._store.set(key, value)

    def delete(self, key: str) -> bool:
        if key in self._metadata:
            del self._metadata[key]
        return self._store.delete(key)

    def exists(self, key: str) -> bool:
        return self._store.exists(key)

    # --- Metadata Management ---

    def create_metadata(
        self,
        key: str,
        size_bytes: int = 0,
        retrieval_cost_ms: float = 0.0,
        features: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> CacheObjectMetadata:
        """Create and store initial metadata for a newly cached object."""
        meta = CacheObjectMetadata(
            key=key,
            size_bytes=size_bytes,
            retrieval_cost_ms=retrieval_cost_ms,
            access_count=1,
            hit_count=0,
            miss_count=1,
            features=features,
            metadata=metadata,
        )
        self._metadata[key] = meta
        return meta

    def set_metadata(self, key: str, metadata: CacheObjectMetadata) -> None:
        """Explicitly set a metadata object for a key."""
        self._metadata[key] = metadata

    def get_metadata(self, key: str) -> CacheObjectMetadata | None:
        """Retrieve metadata for a specific key."""
        return self._metadata.get(key)

    def get_all_metadata(self) -> dict[str, CacheObjectMetadata]:
        """Retrieve a copy of all current cache metadata."""
        return dict(self._metadata)

    def record_access(self, key: str) -> None:
        """Record general access for an existing metadata key."""
        if key in self._metadata:
            self._metadata[key].record_access()

    def record_hit(self, key: str) -> None:
        """Record cache HIT for an existing metadata key."""
        if key in self._metadata:
            self._metadata[key].record_hit()

    def record_miss(self, key: str) -> None:
        """Record cache MISS for an existing metadata key."""
        if key in self._metadata:
            self._metadata[key].record_miss()

    def record_backend_retrieval(self, key: str, latency_ms: float) -> None:
        """Record backend retrieval latency for an existing metadata key."""
        if key in self._metadata:
            self._metadata[key].record_backend_retrieval(latency_ms)

    def clear_metadata(self) -> None:
        """Clear all in-memory metadata (useful for tests)."""
        self._metadata.clear()
