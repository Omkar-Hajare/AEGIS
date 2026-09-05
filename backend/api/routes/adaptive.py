"""
FastAPI adapter for the adaptive cache DecisionEngine.

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
    from adaptive.history import DecisionHistory, runtime_decision_history
    from adaptive.service import AdaptiveService
except ImportError:
    from backend.adaptive.engine.decision_engine import (
        DecisionEngine,
    )
    from backend.adaptive.history import (
        DecisionHistory,
        runtime_decision_history,
    )
    from backend.adaptive.service import AdaptiveService

try:
    from api.routes.data import cache_manager as runtime_cache_manager
except ImportError:
    from backend.api.routes.data import (
        cache_manager as runtime_cache_manager,
    )

try:
    from api.schemas.adaptive import DecisionHistoryResponse
except ImportError:
    from backend.api.schemas.adaptive import DecisionHistoryResponse

try:
    from cache.manager import CacheManager
except ImportError:
    from backend.cache.manager import CacheManager

try:
    from telemetry.collector import TelemetryCollector
    from telemetry.collector import (
        telemetry_collector as runtime_telemetry_collector,
    )
except ImportError:
    from backend.telemetry.collector import TelemetryCollector
    from backend.telemetry.collector import (
        telemetry_collector as runtime_telemetry_collector,
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
    from backend.metrics.prometheus import ADAPTIVE_DECISIONS


router = APIRouter(prefix="/adaptive", tags=["adaptive"])


def get_decision_engine() -> DecisionEngine:
    """Dependency provider for DecisionEngine."""
    return DecisionEngine()


def get_runtime_cache_manager() -> CacheManager:
    """Return the shared runtime CacheManager."""
    return runtime_cache_manager


def get_runtime_telemetry_collector() -> TelemetryCollector:
    """Return the shared runtime TelemetryCollector."""
    return runtime_telemetry_collector


def get_decision_history() -> DecisionHistory:
    """Return the shared runtime DecisionHistory."""
    return runtime_decision_history


def get_adaptive_service(
    cache_mgr: CacheManager = Depends(get_runtime_cache_manager),
    collector: TelemetryCollector = Depends(get_runtime_telemetry_collector),
    engine: DecisionEngine = Depends(get_decision_engine),
    history: DecisionHistory = Depends(get_decision_history),
) -> AdaptiveService:
    """Create AdaptiveService with shared runtime state."""
    return AdaptiveService(
        cache_manager=cache_mgr,
        telemetry_collector=collector,
        decision_engine=engine,
        decision_history=history,
    )


class DecisionRequest(BaseModel):
    """Request schema for adaptive decision generation."""

    model_config = ConfigDict(extra="ignore")

    objects: dict[str, CacheObject] | list[CacheObject] = Field(
        ...,
        description=(
            "Candidate cache objects as a key->CacheObject mapping "
            "or list of CacheObjects"
        ),
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
        description="Optional evaluation timestamp override",
    )

    previous_access_counts: dict[str, int] | None = Field(
        default=None,
        description="Optional access counts from prior observation window",
    )

    refresh_after_seconds: float = Field(
        default=300.0,
        gt=0.0,
        description="Base staleness threshold in seconds",
    )

    decision_id: str | None = Field(
        default=None,
        description="Optional custom identifier for this decision event",
    )

    capacity_mode: str | None = Field(
        default=None,
        description="Optional capacity recommendation mode",
    )

    @field_validator(
        "min_capacity_bytes",
        "max_capacity_bytes",
        mode="before",
    )
    @classmethod
    def _reject_bool_for_numeric(cls, v: Any) -> Any:
        if isinstance(v, bool):
            raise ValueError(
                "Boolean values are not allowed for numeric fields"
            )
        return v

    @model_validator(mode="after")
    def _validate_bounds(self) -> DecisionRequest:
        if self.min_capacity_bytes <= 0:
            raise ValueError(
                "min_capacity_bytes must be greater than 0, "
                f"got {self.min_capacity_bytes}"
            )

        if self.max_capacity_bytes <= 0:
            raise ValueError(
                "max_capacity_bytes must be greater than 0, "
                f"got {self.max_capacity_bytes}"
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
)
def compute_decision(
    request: DecisionRequest,
    engine: DecisionEngine = Depends(get_decision_engine),
) -> Decision:
    """Compute an adaptive cache decision."""

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
)
def get_runtime_decision(
    min_capacity_bytes: int = 1_000_000,
    max_capacity_bytes: int = 10_000_000,
    refresh_after_seconds: float | None = None,
    capacity_mode: str = "rule_based",
    now: datetime | None = None,
    decision_id: str | None = None,
    service: AdaptiveService = Depends(get_adaptive_service),
    history: DecisionHistory = Depends(get_decision_history),
) -> Decision:
    """Get an adaptive decision from live runtime state."""

    if min_capacity_bytes <= 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                "min_capacity_bytes must be greater than 0, "
                f"got {min_capacity_bytes}"
            ),
        )

    if max_capacity_bytes <= 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                "max_capacity_bytes must be greater than 0, "
                f"got {max_capacity_bytes}"
            ),
        )

    if min_capacity_bytes > max_capacity_bytes:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"min_capacity_bytes ({min_capacity_bytes}) must be <= "
                f"max_capacity_bytes ({max_capacity_bytes})"
            ),
        )

    if (
        refresh_after_seconds is not None
        and refresh_after_seconds <= 0.0
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                "refresh_after_seconds must be greater than 0, "
                f"got {refresh_after_seconds}"
            ),
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
        history.record(decision)

        return decision

    except (ValueError, TypeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc


@router.get(
    "/decisions",
    response_model=DecisionHistoryResponse,
    summary="Get Recent Adaptive Decisions",
)
def get_adaptive_decisions(
    limit: int = 50,
    history: DecisionHistory = Depends(get_decision_history),
) -> DecisionHistoryResponse:
    """Return recent adaptive decisions."""

    if limit <= 0:
        return DecisionHistoryResponse(
            decisions=[],
            count=0,
        )

    decisions = history.get_recent(limit=limit)

    return DecisionHistoryResponse(
        decisions=decisions,
        count=len(decisions),
    )