"""Decision contract schema for the Adaptive Cache System.

Frozen v1 contract - do not change field names, meanings, or add required fields.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .enums import CapacityAction


class Decision(BaseModel):
    """Output decision produced by the adaptive intelligence engine.

    Specifies prioritized object utility scores, candidates chosen for eviction,
    capacity resizing actions, and an explanatory justification.
    """

    model_config = ConfigDict(extra="ignore")

    object_scores: Dict[str, float] = Field(
        ..., description="Mapping of cache key to numeric priority/utility score"
    )
    eviction_keys: List[str] = Field(
        ..., description="List of cache keys recommended for eviction (strings only)"
    )
    capacity_action: CapacityAction = Field(
        ...,
        description="Recommended capacity scaling action",
    )
    recommended_capacity_bytes: int = Field(
        ..., gt=0, description="Recommended total cache capacity in bytes (must be > 0)"
    )
    reason: str = Field(
        ..., description="Human-readable explanation or justification for the decision"
    )
    decision_id: Optional[str] = Field(
        default=None, description="Optional unique identifier for this decision event"
    )
    timestamp: datetime = Field(
        ..., description="Timestamp of when the decision was generated"
    )
    metadata: Optional[Dict[str, Any]] = Field(
        default=None, description="Optional dictionary for additional decision metadata"
    )
    version: str = Field(default="v1", description="Contract schema version identifier")

    @field_validator("recommended_capacity_bytes", mode="before")
    @classmethod
    def _reject_bool_for_numeric(cls, v: Any) -> Any:
        if isinstance(v, bool):
            raise ValueError("Boolean values are not allowed for numeric fields")
        return v

    @field_validator("object_scores", mode="before")
    @classmethod
    def _validate_scores_numeric(cls, v: Any) -> Any:
        if not isinstance(v, dict):
            raise TypeError(
                "object_scores must be a mapping/dictionary of key to numeric score"
            )
        for key, score in v.items():
            if not isinstance(key, str):
                raise TypeError(
                    f"Object score key must be a string, got {type(key).__name__}"
                )
            if isinstance(score, bool) or not isinstance(score, (int, float)):
                t_name = type(score).__name__
                raise ValueError(
                    f"Object score value for key {key!r} must be numeric, got {t_name}"
                )
        return v

    @field_validator("eviction_keys", mode="before")
    @classmethod
    def _validate_eviction_keys_strings(cls, v: Any) -> Any:
        if not isinstance(v, (list, tuple)):
            raise TypeError("eviction_keys must be a list of strings")
        for idx, key in enumerate(v):
            if not isinstance(key, str):
                t_name = type(key).__name__
                raise ValueError(
                    f"Eviction key at index {idx} must be a string, got {t_name}"
                )
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
