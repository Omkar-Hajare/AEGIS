"""FastAPI adapter for the adaptive cache DecisionEngine.

Exposes a thin HTTP adapter layer routing requests to the adaptive
DecisionEngine while preserving frozen v1 contracts and dependency injection.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

try:
    from adaptive.engine.decision_engine import DecisionEngine
except ImportError:
    from backend.adaptive.engine.decision_engine import (
        DecisionEngine,  # type: ignore[no-redef]
    )

from contracts.schemas import (
    CacheObject,
    Decision,
    SystemState,
    WorkloadState,
)

router = APIRouter(prefix="/adaptive", tags=["adaptive"])


def get_decision_engine() -> DecisionEngine:
    """Dependency provider for DecisionEngine, allowing mock/fake override in tests."""
    return DecisionEngine()


class DecisionRequest(BaseModel):
    """Request schema for adaptive decision generation."""

    model_config = ConfigDict(extra="ignore")

    objects: dict[str, CacheObject] | list[CacheObject] = Field(
        ...,
        description="Candidate cache objects as a key->CacheObject mapping or list of CacheObjects",
    )
    workload: WorkloadState = Field(
        ...,
        description="Observed WorkloadState telemetry snapshot",
    )
    system: SystemState = Field(
        ...,
        description="Observed SystemState capacity and usage snapshot",
    )
    min_capacity_bytes: int = Field(
        ...,
        description="Minimum allowed cache capacity in bytes (must be > 0)",
    )
    max_capacity_bytes: int = Field(
        ...,
        description="Maximum allowed cache capacity in bytes (must be > 0)",
    )
    now: datetime | None = Field(
        default=None,
        description="Optional evaluation timestamp override (must be timezone-aware)",
    )
    previous_access_counts: dict[str, int] | None = Field(
        default=None,
        description="Optional access counts from prior observation window",
    )
    refresh_after_seconds: float = Field(
        default=300.0,
        gt=0.0,
        description="Base staleness threshold in seconds (> 0)",
    )
    decision_id: str | None = Field(
        default=None,
        description="Optional custom identifier for this decision event",
    )
    capacity_mode: str | None = Field(
        default=None,
        description="Optional capacity recommendation mode ('continuous' or 'rule_based')",
    )

    @field_validator("min_capacity_bytes", "max_capacity_bytes", mode="before")
    @classmethod
    def _reject_bool_for_numeric(cls, v: Any) -> Any:
        if isinstance(v, bool):
            raise ValueError("Boolean values are not allowed for numeric fields")  # noqa: TRY004
        return v

    @model_validator(mode="after")
    def _validate_bounds(self) -> DecisionRequest:
        if self.min_capacity_bytes <= 0:
            raise ValueError(
                f"min_capacity_bytes must be greater than 0, got {self.min_capacity_bytes}"
            )
        if self.max_capacity_bytes <= 0:
            raise ValueError(
                f"max_capacity_bytes must be greater than 0, got {self.max_capacity_bytes}"
            )
        if self.min_capacity_bytes > self.max_capacity_bytes:
            raise ValueError(
                f"min_capacity_bytes ({self.min_capacity_bytes}) must be <= "
                f"max_capacity_bytes ({self.max_capacity_bytes})"
            )
        return self


@router.post(
    "/decision",
    response_model=Decision,
    summary="Compute Adaptive Cache Decision",
    description="Thin adapter evaluating cache state and telemetry via DecisionEngine to return a Decision.",
)
def compute_decision(
    request: DecisionRequest,
    engine: DecisionEngine = Depends(get_decision_engine),  # noqa: B008
) -> Decision:
    """Route handler delegating decision computation to the injected DecisionEngine."""
    if isinstance(request.objects, list):
        candidate_objects: Mapping[str, CacheObject] = {
            obj.key: obj for obj in request.objects
        }
    else:
        candidate_objects = request.objects

    try:
        return engine.decide(
            objects=candidate_objects,
            workload=request.workload,
            system=request.system,
            min_capacity_bytes=request.min_capacity_bytes,
            max_capacity_bytes=request.max_capacity_bytes,
            now=request.now,
            previous_access_counts=request.previous_access_counts,
            refresh_after_seconds=request.refresh_after_seconds,
            decision_id=request.decision_id,
            capacity_mode=request.capacity_mode,
        )
    except (ValueError, TypeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
