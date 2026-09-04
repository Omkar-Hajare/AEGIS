import time
from typing import Any


def get_recommendation_data(user_id: str) -> dict[str, Any]:
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
