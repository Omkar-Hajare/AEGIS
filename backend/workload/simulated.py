import time
from typing import Any

from workload.adapter import BackendAdapter


class SimulatedBackendAdapter(BackendAdapter):
    """Default backend adapter: in-process synthetic data source.

    Preserves the original product/recommendation simulation behavior
    (approximate latency and payload shape) used before the adapter
    boundary was introduced.
    """

    def get_product(self, product_id: str) -> dict[str, Any]:
        # Simulate relatively cheap backend retrieval latency (~30ms)
        time.sleep(0.03)
        return {
            "product_id": product_id,
            "name": f"Product {product_id}",
            "category": "demo",
        }

    def get_recommendation(self, user_id: str) -> dict[str, Any]:
        # Simulate expensive recommendation computation latency (~600ms)
        time.sleep(0.6)
        return {
            "user_id": user_id,
            "recommendations": [
                "product-1",
                "product-2",
                "product-3",
            ],
        }
