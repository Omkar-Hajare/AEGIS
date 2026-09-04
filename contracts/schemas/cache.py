"""CacheObject contract schema for the Adaptive Cache System.

Frozen v1 contract - do not change field names, meanings, or add required fields.
"""

from datetime import datetime, timezone
from typing import Any, Dict, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class CacheObject(BaseModel):
    """Represents a cached item, its access statistics, and optional derived features.

    Derived features such as frequency, recency, trend, etc. are optional and
    stored in the `features` dictionary rather than as mandatory contract fields.
    """

    model_config = ConfigDict(extra="ignore")

    key: str = Field(..., description="Unique cache object key")
    size_bytes: int = Field(..., ge=0, description="Size of the cached object in bytes")
    access_count: int = Field(
        ..., ge=0, description="Total access count for the object"
    )
    last_accessed: datetime = Field(
        ..., description="Timestamp of the most recent access"
    )
    retrieval_cost_ms: float = Field(
        ..., ge=0.0, description="Cost to compute/fetch from backend in milliseconds"
    )
    hit_count: Optional[int] = Field(
        default=None, ge=0, description="Optional cache hit count for this object"
    )
    miss_count: Optional[int] = Field(
        default=None, ge=0, description="Optional cache miss count for this object"
    )
    created_at: Optional[datetime] = Field(
        default=None, description="Optional timestamp when the object was cached"
    )
    features: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Optional dictionary for derived features",
    )
    metadata: Optional[Dict[str, Any]] = Field(
        default=None, description="Optional dictionary for additional metadata"
    )
    version: str = Field(default="v1", description="Contract schema version identifier")

    @field_validator(
        "size_bytes",
        "access_count",
        "hit_count",
        "miss_count",
        "retrieval_cost_ms",
        mode="before",
    )
    @classmethod
    def _reject_bool_for_numeric(cls, v: Any) -> Any:
        if isinstance(v, bool):
            raise ValueError("Boolean values are not allowed for numeric fields")
        return v

    @field_validator("last_accessed", "created_at", mode="before")
    @classmethod
    def _reject_numeric_timestamps(cls, v: Any) -> Any:
        if v is None:
            return None
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            raise ValueError(
                "Numeric timestamps are not allowed; "
                "use timezone-aware datetime or ISO string"
            )
        return v

    @field_validator("last_accessed", "created_at", mode="after")
    @classmethod
    def _ensure_timezone_aware(cls, v: Optional[datetime]) -> Optional[datetime]:
        if v is None:
            return None
        if v.tzinfo is None:
            return v.replace(tzinfo=timezone.utc)
        return v
