import time
from typing import Any

from fastapi import APIRouter

from cache.in_memory import InMemoryCache
from cache.manager import CacheManager
from cache.metadata import calculate_payload_size_bytes
from telemetry.collector import telemetry_collector
from workload.product_api import get_product_data
from workload.recommendation_api import get_recommendation_data

router = APIRouter(prefix="/data", tags=["data"])

# Application-level CacheManager using InMemoryCache
cache_manager = CacheManager(InMemoryCache())


@router.get("/product/{product_id}")
def get_product(product_id: str) -> dict[str, Any]:
    telemetry_collector.record_request()
    cache_key = f"product:{product_id}"
    cached_data = cache_manager.get(cache_key)
    if cached_data is not None:
        telemetry_collector.record_cache_hit()
        telemetry_collector.record_key_access(cache_key, hit=True)
        cache_manager.record_hit(cache_key)
        return cached_data

    telemetry_collector.record_cache_miss()
    telemetry_collector.record_key_access(cache_key, hit=False)
    cache_manager.record_miss(cache_key)
    start_time = time.perf_counter()
    data = get_product_data(product_id)
    latency_ms = (time.perf_counter() - start_time) * 1000.0
    telemetry_collector.record_backend_call(latency_ms)

    cache_manager.set(cache_key, data)
    if cache_manager.get_metadata(cache_key) is None:
        size_bytes = calculate_payload_size_bytes(data)
        cache_manager.create_metadata(
            key=cache_key,
            size_bytes=size_bytes,
            retrieval_cost_ms=latency_ms,
        )
    else:
        cache_manager.record_backend_retrieval(cache_key, latency_ms)

    return data


@router.get("/recommendation/{user_id}")
def get_recommendation(user_id: str) -> dict[str, Any]:
    telemetry_collector.record_request()
    cache_key = f"recommendation:{user_id}"
    cached_data = cache_manager.get(cache_key)
    if cached_data is not None:
        telemetry_collector.record_cache_hit()
        telemetry_collector.record_key_access(cache_key, hit=True)
        cache_manager.record_hit(cache_key)
        return cached_data

    telemetry_collector.record_cache_miss()
    telemetry_collector.record_key_access(cache_key, hit=False)
    cache_manager.record_miss(cache_key)
    start_time = time.perf_counter()
    data = get_recommendation_data(user_id)
    latency_ms = (time.perf_counter() - start_time) * 1000.0
    telemetry_collector.record_backend_call(latency_ms)

    cache_manager.set(cache_key, data)
    if cache_manager.get_metadata(cache_key) is None:
        size_bytes = calculate_payload_size_bytes(data)
        cache_manager.create_metadata(
            key=cache_key,
            size_bytes=size_bytes,
            retrieval_cost_ms=latency_ms,
        )
    else:
        cache_manager.record_backend_retrieval(cache_key, latency_ms)

    return data
