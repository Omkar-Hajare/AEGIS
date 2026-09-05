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
    from adaptive.service import AdaptiveService
except ImportError:
    from backend.adaptive.engine.decision_engine import (
        DecisionEngine,  # type: ignore[no-redef]
    )
    from backend.adaptive.service import (
        AdaptiveService,  # type: ignore[no-redef]
    )

try:
    from api.routes.data import cache_manager as runtime_cache_manager
except ImportError:
    from backend.api.routes.data import (
        cache_manager as runtime_cache_manager,  # type: ignore[no-redef]
    )

try:
    from cache.manager import CacheManager
except ImportError:
    from backend.cache.manager import (
        CacheManager,  # type: ignore[no-redef]
    )

try:
    from telemetry.collector import (
        TelemetryCollector,
    )
    from telemetry.collector import (
        telemetry_collector as runtime_telemetry_collector,
    )
except ImportError:
    from backend.telemetry.collector import (
        TelemetryCollector,  # type: ignore[no-redef]
    )
    from backend.telemetry.collector import (
        telemetry_collector as runtime_telemetry_collector,  # type: ignore[no-redef]
    )

from contracts.schemas import (
    CacheObject,
    Decision,
    SystemState,
    WorkloadState,
)

try:
    from metrics.prometheus import ADAPTIVE_DECISIONS
except ImportError:
    from backend.metrics.prometheus import ADAPTIVE_DECISIONS  # type: ignore[no-redef]

router = APIRouter(prefix="/adaptive", tags=["adaptive"])


def get_decision_engine() -> DecisionEngine:
    """Dependency provider for DecisionEngine, allowing mock/fake override in tests."""
    return DecisionEngine()


def get_runtime_cache_manager() -> CacheManager:
    """Dependency provider returning the shared runtime CacheManager."""
    return runtime_cache_manager


def get_runtime_telemetry_collector() -> TelemetryCollector:
    """Dependency provider returning the shared runtime TelemetryCollector."""
    return runtime_telemetry_collector


def get_adaptive_service(
    cache_mgr: CacheManager = Depends(get_runtime_cache_manager),  # noqa: B008
    collector: TelemetryCollector = Depends(get_runtime_telemetry_collector),  # noqa: B008
    engine: DecisionEngine = Depends(get_decision_engine),  # noqa: B008
) -> AdaptiveService:
    """Dependency provider for AdaptiveService wired with shared runtime state."""
    return AdaptiveService(
        cache_manager=cache_mgr,
        telemetry_collector=collector,
        decision_engine=engine,
    )


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
        decision = engine.decide(
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
        ADAPTIVE_DECISIONS.inc()
        return decision
    except (ValueError, TypeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc


@router.get(
    "/runtime-decision",
    response_model=Decision,
    summary="Get Runtime Adaptive Decision",
    description="Retrieve the current adaptive cache decision derived from live telemetry and cache state.",
)
def get_runtime_decision(
    min_capacity_bytes: int = 1_000_000,
    max_capacity_bytes: int = 10_000_000,
    refresh_after_seconds: float | None = None,
    capacity_mode: str = "rule_based",
    now: datetime | None = None,
    decision_id: str | None = None,
    service: AdaptiveService = Depends(get_adaptive_service),  # noqa: B008
) -> Decision:
    """Retrieve current adaptive cache decision using live runtime telemetry and cache state."""
    if min_capacity_bytes <= 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"min_capacity_bytes must be greater than 0, got {min_capacity_bytes}",
        )
    if max_capacity_bytes <= 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"max_capacity_bytes must be greater than 0, got {max_capacity_bytes}",
        )
    if min_capacity_bytes > max_capacity_bytes:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"min_capacity_bytes ({min_capacity_bytes}) must be <= max_capacity_bytes ({max_capacity_bytes})",
        )
    if refresh_after_seconds is not None and refresh_after_seconds <= 0.0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"refresh_after_seconds must be greater than 0, got {refresh_after_seconds}",
        )

    try:
        decision = service.decide(
            now=now,
            min_capacity_bytes=min_capacity_bytes,
            max_capacity_bytes=max_capacity_bytes,
            refresh_after_seconds=refresh_after_seconds,
            decision_id=decision_id,
            capacity_mode=capacity_mode,
        )
        ADAPTIVE_DECISIONS.inc()
        return decision
    except (ValueError, TypeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
