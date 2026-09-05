"""Pydantic response models for cache object inspection routes."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class CacheObjectItem(BaseModel):
    """Public representation of a single resident cache object."""

    key: str = Field(..., description="Cache key identifier")
    size_bytes: int = Field(default=0, description="Payload size in bytes")
    retrieval_cost_ms: float = Field(
        default=0.0, description="Backend retrieval latency in milliseconds"
    )
    version: str = Field(default="v1", description="Object schema version")
    access_count: int = Field(default=1, description="Total access count")
    hit_count: int = Field(default=0, description="Total hit count")
    miss_count: int = Field(default=1, description="Total miss count")
    created_at: datetime = Field(..., description="Timestamp of initial caching")
    last_accessed: datetime = Field(..., description="Timestamp of last access")
    features: dict[str, Any] = Field(
        default_factory=dict, description="Custom feature attributes"
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Additional arbitrary metadata"
    )


class CacheObjectsResponse(BaseModel):
    """Response envelope for currently resident cache objects."""

    objects: list[CacheObjectItem] = Field(
        default_factory=list, description="List of currently resident cache objects"
    )
    object_count: int = Field(
        default=0, description="Total number of currently resident objects"
    )
