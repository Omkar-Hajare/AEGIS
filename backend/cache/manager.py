from abc import ABC, abstractmethod
from typing import Any


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

    def get(self, key: str) -> Any | None:
        return self._store.get(key)

    def set(self, key: str, value: Any) -> None:
        self._store.set(key, value)

    def delete(self, key: str) -> bool:
        return self._store.delete(key)

    def exists(self, key: str) -> bool:
        return self._store.exists(key)
