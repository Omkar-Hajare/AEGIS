"""Data models and configurations for synthetic workload scenarios.

Represents generated request events, workload profiles, and scenario
generation parameters for deterministic benchmark evaluation.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from contracts.schemas.enums import WorkloadType


class WorkloadProfile(BaseModel):
    """Workload profile defining default object and latency characteristics."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str = Field(..., min_length=1, description="Unique profile identifier")
    workload_type: WorkloadType = Field(
        ..., description="Target workload pattern classification"
    )
    default_backend_latency_ms: float = Field(
        ..., ge=0.0, description="Default backend compute/fetch latency in ms"
    )
    default_object_size_bytes: int = Field(
        ..., ge=0, description="Default payload size in bytes"
    )
    default_retrieval_cost_ms: float = Field(
        ..., ge=0.0, description="Default regeneration expense in ms"
    )

    @field_validator(
        "default_backend_latency_ms",
        "default_object_size_bytes",
        "default_retrieval_cost_ms",
        mode="before",
    )
    @classmethod
    def _reject_bool_for_numeric(cls, v: Any) -> Any:
        if isinstance(v, bool):
            raise TypeError("Boolean values are not allowed for numeric fields")
        return v


PRODUCT_CATALOG_PROFILE = WorkloadProfile(
    name="product_catalog",
    workload_type=WorkloadType.READ_HEAVY,
    default_backend_latency_ms=5.0,
    default_object_size_bytes=2048,
    default_retrieval_cost_ms=5.0,
)

RECOMMENDATIONS_PROFILE = WorkloadProfile(
    name="recommendations",
    workload_type=WorkloadType.COMPUTE_HEAVY,
    default_backend_latency_ms=200.0,
    default_object_size_bytes=25600,
    default_retrieval_cost_ms=200.0,
)

PROFILES: dict[str, WorkloadProfile] = {
    "product_catalog": PRODUCT_CATALOG_PROFILE,
    "recommendations": RECOMMENDATIONS_PROFILE,
}


def get_workload_profile(profile_or_name: str | WorkloadProfile) -> WorkloadProfile:
    """Resolve a profile instance from a string name or existing instance.

    Args:
        profile_or_name: Either a WorkloadProfile or profile name string.

    Returns:
        Resolved WorkloadProfile instance.

    Raises:
        ValueError: If profile name is unknown.
        TypeError: If input is neither str nor WorkloadProfile.
    """
    if isinstance(profile_or_name, WorkloadProfile):
        return profile_or_name
    if isinstance(profile_or_name, str):
        normalized = profile_or_name.lower().strip()
        if normalized in PROFILES:
            return PROFILES[normalized]
        raise ValueError(
            f"Unknown workload profile {profile_or_name!r}. "
            f"Available profiles: {sorted(PROFILES.keys())}"
        )
    raise TypeError(
        f"Expected str or WorkloadProfile, got {type(profile_or_name).__name__}"
    )


class ScenarioEvent(BaseModel):
    """Represents a single generated synthetic request event.

    Encapsulates all metadata required by benchmark runners to derive
    WorkloadState, CacheObject instances, access statistics, and telemetry.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    timestamp: datetime = Field(
        ..., description="Timezone-aware timestamp of the request event"
    )
    key: str = Field(..., min_length=1, description="Target cache object key")
    workload_type: WorkloadType = Field(
        ..., description="Workload pattern classification"
    )
    backend_latency_ms: float = Field(
        ..., ge=0.0, description="Simulated backend fetch/compute latency in ms"
    )
    object_size_bytes: int = Field(
        ..., ge=0, description="Size of the requested cached object in bytes"
    )
    retrieval_cost_ms: float = Field(
        ..., ge=0.0, description="Cost to regenerate the object in ms"
    )
    request_rate: float = Field(
        ..., ge=0.0, description="Instantaneous arrival rate in requests per second"
    )
    metadata: dict[str, Any] | None = Field(
        default=None, description="Optional scenario metadata (e.g. phase, shift)"
    )

    @field_validator("timestamp", mode="before")
    @classmethod
    def _validate_timestamp(cls, v: Any) -> Any:
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            raise TypeError("Numeric timestamps are not allowed; use aware datetime")
        if isinstance(v, datetime) and (
            v.tzinfo is None or v.tzinfo.utcoffset(v) is None
        ):
            raise ValueError(
                "timestamp must be a timezone-aware datetime; received naive datetime"
            )
        return v

    @field_validator(
        "backend_latency_ms",
        "object_size_bytes",
        "retrieval_cost_ms",
        "request_rate",
        mode="before",
    )
    @classmethod
    def _reject_bool_for_numeric(cls, v: Any) -> Any:
        if isinstance(v, bool):
            raise TypeError("Boolean values are not allowed for numeric fields")
        return v

    @field_validator("metadata", mode="before")
    @classmethod
    def _copy_metadata(cls, v: Any) -> dict[str, Any] | None:
        if v is not None:
            if not isinstance(v, (dict, Mapping)):
                raise TypeError(f"metadata must be a mapping, got {type(v).__name__}")
            return dict(v)
        return None


DEFAULT_START_TIME = datetime(2026, 9, 4, 12, 0, 0, tzinfo=timezone.utc)


class ScenarioConfig(BaseModel):
    """Configuration parameters for deterministic scenario generation."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str = Field(default="steady", description="Scenario pattern name")
    scenario_type: str = Field(
        default="steady",
        description="Scenario pattern type: 'steady', 'spike', or 'popularity_shift'",
    )
    seed: int = Field(
        default=42, description="Random seed ensuring deterministic generation"
    )
    object_count: int = Field(
        default=100, ge=1, description="Total number of unique cacheable objects"
    )
    request_count: int = Field(
        default=1000, ge=1, description="Total number of request events to generate"
    )
    request_rate: float = Field(
        default=100.0, ge=0.0, description="Base request rate in requests per second"
    )
    duration_seconds: float = Field(
        default=60.0, gt=0.0, description="Total duration or measurement window"
    )
    hot_set_size: int = Field(
        default=10, ge=1, description="Number of objects comprising the hot subset"
    )
    spike_multiplier: float = Field(
        default=3.0, gt=0.0, description="Traffic multiplier during spike phase"
    )
    profile: WorkloadProfile = Field(
        default=PRODUCT_CATALOG_PROFILE, description="Workload latency and size profile"
    )
    start_time: datetime = Field(
        default=DEFAULT_START_TIME,
        description="Timezone-aware start datetime for generated events",
    )
    key_prefix: str = Field(
        default="obj", min_length=1, description="Prefix for generated cache keys"
    )
    extra_params: dict[str, Any] | None = Field(
        default=None, description="Optional scenario-specific parameters"
    )

    @field_validator(
        "seed",
        "object_count",
        "request_count",
        "request_rate",
        "duration_seconds",
        "hot_set_size",
        "spike_multiplier",
        mode="before",
    )
    @classmethod
    def _reject_bool_for_numeric(cls, v: Any) -> Any:
        if isinstance(v, bool):
            raise TypeError("Boolean values are not allowed for numeric fields")
        return v

    @field_validator("profile", mode="before")
    @classmethod
    def _resolve_profile(cls, v: Any) -> WorkloadProfile:
        if isinstance(v, (str, WorkloadProfile)):
            return get_workload_profile(v)
        raise TypeError(
            f"profile must be a WorkloadProfile or str, got {type(v).__name__}"
        )

    @field_validator("start_time", mode="before")
    @classmethod
    def _validate_start_time(cls, v: Any) -> Any:
        if v is None:
            return DEFAULT_START_TIME
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            raise TypeError("Numeric timestamps are not allowed; use aware datetime")
        if isinstance(v, datetime) and (
            v.tzinfo is None or v.tzinfo.utcoffset(v) is None
        ):
            raise ValueError(
                "start_time must be a timezone-aware datetime; received naive datetime"
            )
        return v

    @field_validator("extra_params", mode="before")
    @classmethod
    def _copy_extra_params(cls, v: Any) -> dict[str, Any] | None:
        if v is not None:
            if not isinstance(v, (dict, Mapping)):
                raise TypeError(
                    f"extra_params must be a mapping, got {type(v).__name__}"
                )
            return dict(v)
        return None

    @model_validator(mode="before")
    @classmethod
    def _handle_duration_alias(cls, values: Any) -> Any:
        if isinstance(values, dict) and "duration_seconds" not in values:
            if "window_seconds" in values:
                values = dict(values)
                values["duration_seconds"] = values.pop("window_seconds")
            elif "duration" in values:
                values = dict(values)
                values["duration_seconds"] = values.pop("duration")
        return values

    @model_validator(mode="after")
    def _validate_cross_field_bounds(self) -> ScenarioConfig:
        if self.hot_set_size > self.object_count:
            raise ValueError(
                f"hot_set_size ({self.hot_set_size}) cannot exceed "
                f"object_count ({self.object_count})"
            )
        if not math.isfinite(self.request_rate):
            raise ValueError("request_rate must be finite")
        if not math.isfinite(self.duration_seconds):
            raise ValueError("duration_seconds must be finite")
        if not math.isfinite(self.spike_multiplier):
            raise ValueError("spike_multiplier must be finite")
        return self

    @property
    def window_seconds(self) -> float:
        """Alias for duration_seconds to match telemetry contracts."""
        return self.duration_seconds
