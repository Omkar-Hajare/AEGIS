"""FastAPI route exposing currently resident cache objects and metadata.

Adheres strictly to CacheManager abstraction without direct DB/Redis coupling.
Filters out non-resident or orphaned metadata keys.
"""

from typing import Any

from fastapi import APIRouter, Depends

try:
    from cache.manager import CacheManager
    from cache.metadata import CacheObjectMetadata

    from api.routes.data import cache_manager as runtime_cache_manager
    from api.schemas.cache import CacheObjectsResponse
except ImportError:
    from backend.api.routes.data import (
        cache_manager as runtime_cache_manager,  # type: ignore[no-redef]
    )
    from backend.api.schemas.cache import (
        CacheObjectsResponse,  # type: ignore[no-redef]
    )
    from backend.cache.manager import (
        CacheManager,  # type: ignore[no-redef]
    )
    from backend.cache.metadata import (
        CacheObjectMetadata,  # type: ignore[no-redef]
    )

router = APIRouter(prefix="/cache", tags=["cache"])


def get_cache_manager() -> CacheManager:
    """Dependency provider for the shared runtime CacheManager."""
    return runtime_cache_manager


def _serialize_metadata(meta: CacheObjectMetadata) -> dict[str, Any]:
    return {
        "key": meta.key,
        "size_bytes": meta.size_bytes,
        "retrieval_cost_ms": meta.retrieval_cost_ms,
        "version": meta.version,
        "access_count": meta.access_count,
        "hit_count": meta.hit_count,
        "miss_count": meta.miss_count,
        "created_at": meta.created_at,
        "last_accessed": meta.last_accessed,
        "features": meta.features if meta.features is not None else {},
        "metadata": meta.metadata if meta.metadata is not None else {},
    }


@router.get("/objects", response_model=CacheObjectsResponse)
def get_resident_cache_objects(
    manager: CacheManager = Depends(get_cache_manager),  # noqa: B008
) -> dict[str, Any]:
    """Retrieve all currently resident cache objects and their metadata.

    Returns only keys that are presently resident in the underlying store.
    Any metadata for non-resident/orphaned keys is excluded.
    """
    all_metadata = manager.get_all_metadata()
    resident_objects: list[dict[str, Any]] = []

    for key, meta in all_metadata.items():
        if not manager.exists(key):
            continue
        resident_objects.append(_serialize_metadata(meta))

    return {
        "objects": resident_objects,
        "object_count": len(resident_objects),
    }
