from typing import Any

from fastapi import APIRouter

from cache.in_memory import InMemoryCache
from cache.manager import CacheManager
from workload.product_api import get_product_data
from workload.recommendation_api import get_recommendation_data

router = APIRouter(prefix="/data", tags=["data"])

# Application-level CacheManager using InMemoryCache
cache_manager = CacheManager(InMemoryCache())


@router.get("/product/{product_id}")
def get_product(product_id: str) -> dict[str, Any]:
    cache_key = f"product:{product_id}"
    cached_data = cache_manager.get(cache_key)
    if cached_data is not None:
        return cached_data

    data = get_product_data(product_id)
    cache_manager.set(cache_key, data)
    return data


@router.get("/recommendation/{user_id}")
def get_recommendation(user_id: str) -> dict[str, Any]:
    cache_key = f"recommendation:{user_id}"
    cached_data = cache_manager.get(cache_key)
    if cached_data is not None:
        return cached_data

    data = get_recommendation_data(user_id)
    cache_manager.set(cache_key, data)
    return data
