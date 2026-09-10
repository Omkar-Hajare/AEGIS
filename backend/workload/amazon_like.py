import time
from typing import Any

from workload.adapter import BackendAdapter


class AmazonLikeAdapter(BackendAdapter):
    """Alternate simulated backend adapter demonstrating platform swap-ability.

    This is a synthetic stand-in for a large-catalog, externally-hosted
    commerce platform. It performs no real network calls and has no
    affiliation with Amazon; it exists only to prove that the adaptive
    engine keeps working unchanged when the upstream data source changes.
    """

    def get_product(self, product_id: str) -> dict[str, Any]:
        # Simulate a slightly higher-latency external catalog lookup (~45ms)
        time.sleep(0.045)
        return {
            "product_id": product_id,
            "name": f"Marketplace Item {product_id}",
            "category": "marketplace",
            "source": "amazon_like",
        }

    def get_recommendation(self, user_id: str) -> dict[str, Any]:
        # Simulate a heavier external recommendation service (~750ms)
        time.sleep(0.75)
        return {
            "user_id": user_id,
            "recommendations": [
                "marketplace-item-1",
                "marketplace-item-2",
                "marketplace-item-3",
                "marketplace-item-4",
            ],
            "source": "amazon_like",
        }
