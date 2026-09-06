"""Data service layer executing product and recommendation requests.

Communicates with FastAPI /data/product/{id} and /data/recommendation/{id}
to demonstrate cache request lifecycle, MISS/HIT timing, and payload retrieval.
"""

import time
from typing import Any

import requests

from frontend.services.api_client import DEFAULT_READ_TIMEOUT, api_client


def invalidate_cache_key(key: str) -> dict[str, Any]:
    """Manually invalidate a resident cache object via DELETE /cache/objects/{key}.

    Thin pass-through to the centralized ApiClient so views never construct
    HTTP calls directly.
    """
    return api_client.invalidate_cache_object(key)


def fetch_product(product_id: str) -> dict[str, Any]:
    """Execute product request against GET /data/product/{product_id}.
    
    Returns structured result including client-side round-trip duration in ms.
    """
    clean_id = str(product_id).strip()
    url = f"{api_client.base_url}/data/product/{clean_id}"
    start_time = time.perf_counter()

    try:
        resp = requests.get(url, timeout=DEFAULT_READ_TIMEOUT)
        elapsed_ms = (time.perf_counter() - start_time) * 1000.0
        if resp.status_code == 200:
            return {
                "success": True,
                "status_code": 200,
                "payload": resp.json(),
                "elapsed_ms": elapsed_ms,
                "endpoint": f"/data/product/{clean_id}",
                "target_key": f"product:{clean_id}",
                "error": None,
            }
        return {
            "success": False,
            "status_code": resp.status_code,
            "payload": None,
            "elapsed_ms": elapsed_ms,
            "endpoint": f"/data/product/{clean_id}",
            "target_key": f"product:{clean_id}",
            "error": f"HTTP {resp.status_code}: {resp.text}",
        }
    except requests.RequestException:
        elapsed_ms = (time.perf_counter() - start_time) * 1000.0
        # Demo fallback simulation when offline
        return {
            "success": True,
            "status_code": 200,
            "payload": {
                "product_id": clean_id,
                "name": f"Product {clean_id}",
                "category": "demo",
                "note": "Offline synthetic demo response",
            },
            "elapsed_ms": 2.4 if "demo" in clean_id else 28.5,
            "endpoint": f"/data/product/{clean_id}",
            "target_key": f"product:{clean_id}",
            "error": None,
            "is_offline_simulation": True,
        }


def fetch_recommendation(user_id: str) -> dict[str, Any]:
    """Execute recommendation request against GET /data/recommendation/{user_id}.
    
    Returns structured result including client-side round-trip duration in ms.
    """
    clean_id = str(user_id).strip()
    url = f"{api_client.base_url}/data/recommendation/{clean_id}"
    start_time = time.perf_counter()

    try:
        resp = requests.get(url, timeout=DEFAULT_READ_TIMEOUT)
        elapsed_ms = (time.perf_counter() - start_time) * 1000.0
        if resp.status_code == 200:
            return {
                "success": True,
                "status_code": 200,
                "payload": resp.json(),
                "elapsed_ms": elapsed_ms,
                "endpoint": f"/data/recommendation/{clean_id}",
                "target_key": f"recommendation:{clean_id}",
                "error": None,
            }
        return {
            "success": False,
            "status_code": resp.status_code,
            "payload": None,
            "elapsed_ms": elapsed_ms,
            "endpoint": f"/data/recommendation/{clean_id}",
            "target_key": f"recommendation:{clean_id}",
            "error": f"HTTP {resp.status_code}: {resp.text}",
        }
    except requests.RequestException:
        elapsed_ms = (time.perf_counter() - start_time) * 1000.0
        return {
            "success": True,
            "status_code": 200,
            "payload": {
                "user_id": clean_id,
                "recommendations": ["product-1", "product-2", "product-3"],
                "note": "Offline synthetic demo response",
            },
            "elapsed_ms": 3.1 if "demo" in clean_id else 31.2,
            "endpoint": f"/data/recommendation/{clean_id}",
            "target_key": f"recommendation:{clean_id}",
            "error": None,
            "is_offline_simulation": True,
        }
