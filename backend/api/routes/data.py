import logging
import time
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

try:
    from cache.factory import create_cache_manager
    from cache.metadata import CacheObjectMetadata, calculate_payload_size_bytes
    from database.connection import get_db
    from database.repositories.cache_metadata import CacheMetadataRepository
    from metrics.prometheus import (
        BACKEND_LATENCY,
        BACKEND_REQUESTS,
        CACHE_HITS,
        CACHE_MISSES,
    )
    from telemetry.collector import telemetry_collector
    from workload.product_api import get_product_data
    from workload.recommendation_api import get_recommendation_data
except ImportError:
    from backend.cache.factory import create_cache_manager  # type: ignore[no-redef]
    from backend.cache.metadata import (  # type: ignore[no-redef]
        CacheObjectMetadata,
        calculate_payload_size_bytes,
    )
    from backend.database.connection import get_db  # type: ignore[no-redef]
    from backend.database.repositories.cache_metadata import (  # type: ignore[no-redef]
        CacheMetadataRepository,
    )
    from backend.metrics.prometheus import (  # type: ignore[no-redef]
        BACKEND_LATENCY,
        BACKEND_REQUESTS,
        CACHE_HITS,
        CACHE_MISSES,
    )
    from backend.telemetry.collector import (  # type: ignore[no-redef]
        telemetry_collector,
    )
    from backend.workload.product_api import (  # type: ignore[no-redef]
        get_product_data,
    )
    from backend.workload.recommendation_api import (  # type: ignore[no-redef]
        get_recommendation_data,
    )


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/data", tags=["data"])

# Shared application-level CacheManager.
cache_manager = create_cache_manager()


def _persist_cache_metadata(db: Any, meta: CacheObjectMetadata) -> None:
    """Persist CacheObjectMetadata without failing the request on DB errors."""
    if not isinstance(db, Session):
        return

    try:
        repo = CacheMetadataRepository(db)
        repo.save(meta)
        db.commit()
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "Failed to persist cache metadata for '%s': %s",
            meta.key,
            exc,
        )
        try:
            db.rollback()
        except Exception as rollback_exc:  # noqa: BLE001
            logger.debug(
                "Rollback failed for cache metadata '%s': %s",
                meta.key,
                rollback_exc,
            )


def _delete_persisted_cache_metadata(db: Any, key: str) -> None:
    """Delete persistent cache metadata without failing the request on DB errors."""
    if not isinstance(db, Session):
        return

    try:
        repo = CacheMetadataRepository(db)
        repo.delete(key)
        db.commit()
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "Failed to delete persisted metadata for '%s': %s",
            key,
            exc,
        )
        try:
            db.rollback()
        except Exception as rollback_exc:  # noqa: BLE001
            logger.debug(
                "Rollback failed for deleted metadata '%s': %s",
                key,
                rollback_exc,
            )


def invalidate_cached_key(key: str, db: Any = None) -> bool:
    """Invalidate a key from CacheManager and remove its persistent metadata."""
    had_metadata = cache_manager.get_metadata(key) is not None
    deleted = cache_manager.delete(key)

    if (deleted or had_metadata) and db is not None:
        _delete_persisted_cache_metadata(db, key)

    return deleted or had_metadata


@router.get("/product/{product_id}")
def get_product(
    product_id: str,
    db: Session = Depends(get_db),  # noqa: B008
) -> dict[str, Any]:
    telemetry_collector.record_request()

    cache_key = f"product:{product_id}"
    cached_data = cache_manager.get(cache_key)

    if cached_data is not None:
        telemetry_collector.record_cache_hit()
        telemetry_collector.record_key_access(cache_key, hit=True)
        cache_manager.record_hit(cache_key)
        CACHE_HITS.inc()

        return cached_data

    telemetry_collector.record_cache_miss()
    telemetry_collector.record_key_access(cache_key, hit=False)
    cache_manager.record_miss(cache_key)
    CACHE_MISSES.inc()

    start_time = time.perf_counter()

    data = get_product_data(product_id)

    latency_ms = (time.perf_counter() - start_time) * 1000.0

    telemetry_collector.record_backend_call(latency_ms)

    BACKEND_REQUESTS.inc()
    BACKEND_LATENCY.observe(latency_ms / 1000.0)

    cache_manager.set(cache_key, data)

    meta = cache_manager.get_metadata(cache_key)

    if meta is None:
        size_bytes = calculate_payload_size_bytes(data)

        meta = cache_manager.create_metadata(
            key=cache_key,
            size_bytes=size_bytes,
            retrieval_cost_ms=latency_ms,
        )
    else:
        cache_manager.record_backend_retrieval(
            cache_key,
            latency_ms,
        )
        meta = cache_manager.get_metadata(cache_key)

    if meta is not None:
        _persist_cache_metadata(db, meta)

    return data


@router.get("/recommendation/{user_id}")
def get_recommendation(
    user_id: str,
    db: Session = Depends(get_db),  # noqa: B008
) -> dict[str, Any]:
    telemetry_collector.record_request()

    cache_key = f"recommendation:{user_id}"
    cached_data = cache_manager.get(cache_key)

    if cached_data is not None:
        telemetry_collector.record_cache_hit()
        telemetry_collector.record_key_access(cache_key, hit=True)
        cache_manager.record_hit(cache_key)
        CACHE_HITS.inc()

        return cached_data

    telemetry_collector.record_cache_miss()
    telemetry_collector.record_key_access(cache_key, hit=False)
    cache_manager.record_miss(cache_key)
    CACHE_MISSES.inc()

    start_time = time.perf_counter()

    data = get_recommendation_data(user_id)

    latency_ms = (time.perf_counter() - start_time) * 1000.0

    telemetry_collector.record_backend_call(latency_ms)

    BACKEND_REQUESTS.inc()
    BACKEND_LATENCY.observe(latency_ms / 1000.0)

    cache_manager.set(cache_key, data)

    meta = cache_manager.get_metadata(cache_key)

    if meta is None:
        size_bytes = calculate_payload_size_bytes(data)

        meta = cache_manager.create_metadata(
            key=cache_key,
            size_bytes=size_bytes,
            retrieval_cost_ms=latency_ms,
        )
    else:
        cache_manager.record_backend_retrieval(
            cache_key,
            latency_ms,
        )
        meta = cache_manager.get_metadata(cache_key)

    if meta is not None:
        _persist_cache_metadata(db, meta)

    return data


@router.delete("/product/{product_id}")
def delete_product(
    product_id: str,
    db: Session = Depends(get_db),  # noqa: B008
) -> dict[str, Any]:
    cache_key = f"product:{product_id}"

    deleted = invalidate_cached_key(cache_key, db)

    return {
        "key": cache_key,
        "deleted": deleted,
    }


@router.delete("/recommendation/{user_id}")
def delete_recommendation(
    user_id: str,
    db: Session = Depends(get_db),  # noqa: B008
) -> dict[str, Any]:
    cache_key = f"recommendation:{user_id}"

    deleted = invalidate_cached_key(cache_key, db)

    return {
        "key": cache_key,
        "deleted": deleted,
    }
