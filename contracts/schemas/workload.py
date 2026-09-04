"""WorkloadState contract schema for the Adaptive Cache System.

Frozen v1 contract - do not change field names, meanings, or add required fields.
"""

from datetime import datetime, timezone
from typing import Any, Dict, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .enums import WorkloadType


class WorkloadState(BaseModel):
    """Snapshot of workload observations within a measurement window."""

    model_config = ConfigDict(extra="ignore")

    request_rate: float = Field(
        ..., ge=0.0, description="Incoming request rate (requests per second)"
    )
    hit_rate: float = Field(
        ..., ge=0.0, le=1.0, description="Cache hit rate between 0.0 and 1.0"
    )
    miss_rate: float = Field(
        ..., ge=0.0, le=1.0, description="Cache miss rate between 0.0 and 1.0"
    )
    backend_latency_ms: float = Field(
        ..., ge=0.0, description="Observed average backend latency in milliseconds"
    )
    workload_type: Optional[WorkloadType] = Field(
        default=None, description="Optional classification of current workload pattern"
    )
    timestamp: datetime = Field(..., description="Timestamp of the observation window")
    window_seconds: float = Field(
        ...,
        gt=0.0,
        description="Duration of observation window in seconds (must be > 0)",
    )
    metrics: Optional[Dict[str, Any]] = Field(
        default=None, description="Optional dictionary for additional workload metrics"
    )
    version: str = Field(default="v1", description="Contract schema version identifier")

    @field_validator(
        "request_rate",
        "hit_rate",
        "miss_rate",
        "backend_latency_ms",
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
