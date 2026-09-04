"""SystemState contract schema for the Adaptive Cache System.

Frozen v1 contract - do not change field names, meanings, or add required fields.
"""

from datetime import datetime, timezone
from typing import Any, Dict, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class SystemState(BaseModel):
    """Snapshot of cache system resource usage and throughput metrics.

    Note: utilization_ratio is deliberately omitted as a stored contract field
    and should be derived dynamically by the adaptive engine when needed.
    """

    model_config = ConfigDict(extra="ignore")

    cache_capacity_bytes: int = Field(
        ..., gt=0, description="Total cache capacity in bytes (must be > 0)"
    )
    cache_usage_bytes: int = Field(
        ..., ge=0, description="Current cache memory usage in bytes"
    )
    object_count: int = Field(
        ..., ge=0, description="Total number of objects stored in cache"
    )
    backend_calls: Optional[int] = Field(
        default=None,
        ge=0,
        description="Total backend calls made during the measurement window",
    )
    cache_evictions: Optional[int] = Field(
        default=None,
        ge=0,
        description="Total cache evictions during the measurement window",
    )
    timestamp: datetime = Field(
        ..., description="Timestamp of the system state snapshot"
    )
    window_seconds: float = Field(
        ..., gt=0.0, description="Measurement window duration in seconds (must be > 0)"
    )
    metrics: Optional[Dict[str, Any]] = Field(
        default=None, description="Optional dictionary for additional system metrics"
    )
    version: str = Field(default="v1", description="Contract schema version identifier")

    @field_validator(
        "cache_capacity_bytes",
        "cache_usage_bytes",
        "object_count",
        "backend_calls",
        "cache_evictions",
        "window_seconds",
        mode="before",
    )
    @classmethod
    def _reject_bool_for_numeric(cls, v: Any) -> Any:
        if isinstance(v, bool):
            raise ValueError("Boolean values are not allowed for numeric fields")
        return v

    @field_validator("timestamp", mode="before")
    @classmethod
    def _reject_numeric_timestamps(cls, v: Any) -> Any:
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            raise ValueError(
                "Numeric timestamps are not allowed; "
                "use timezone-aware datetime or ISO string"
            )
        return v

    @field_validator("timestamp", mode="after")
    @classmethod
    def _ensure_timezone_aware(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            return v.replace(tzinfo=timezone.utc)
        return v
