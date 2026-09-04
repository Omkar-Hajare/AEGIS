import time
from typing import Any


def get_product_data(product_id: str) -> dict[str, Any]:
    # Simulate relatively cheap backend retrieval latency (~30ms)
    time.sleep(0.03)
    return {
        "product_id": product_id,
        "name": f"Product {product_id}",
        "category": "demo",
    }
