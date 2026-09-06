from abc import ABC, abstractmethod
from typing import Any


class BackendAdapter(ABC):
    """Abstraction over the upstream data source for product/recommendation data.

    Isolates platform-specific retrieval details from the cache and adaptive
    layers, which only ever see the returned dict payloads.
    """

    @abstractmethod
    def get_product(self, product_id: str) -> dict[str, Any]:
        pass

    @abstractmethod
    def get_recommendation(self, user_id: str) -> dict[str, Any]:
        pass
