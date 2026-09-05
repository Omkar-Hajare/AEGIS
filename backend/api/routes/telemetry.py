import logging
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

try:
    from database.connection import get_db
    from database.repositories.telemetry import TelemetryRepository
    from telemetry.collector import telemetry_collector
    from telemetry.observation import Observation
    from telemetry.state import build_system_state, build_workload_state

    from api.routes.data import cache_manager
    from api.schemas.telemetry import (
        SystemStateResponse,
        TelemetryObservationResponse,
        WindowResetResponse,
        WorkloadStateResponse,
    )
except ImportError:
    from backend.api.routes.data import cache_manager  # type: ignore[no-redef]
    from backend.api.schemas.telemetry import (  # type: ignore[no-redef]
        SystemStateResponse,
        TelemetryObservationResponse,
        WindowResetResponse,
        WorkloadStateResponse,
    )
    from backend.database.connection import get_db  # type: ignore[no-redef]
    from backend.database.repositories.telemetry import (  # type: ignore[no-redef]
        TelemetryRepository,
    )
    from backend.telemetry.collector import (  # type: ignore[no-redef]
        telemetry_collector,
    )
    from backend.telemetry.observation import (  # type: ignore[no-redef]
        Observation,
    )
    from backend.telemetry.state import (  # type: ignore[no-redef]
        build_system_state,
        build_workload_state,
    )

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/telemetry", tags=["telemetry"])


def _persist_telemetry_observation(db: Any, observation: Observation) -> None:
    """Persist Observation snapshot using TelemetryRepository without failing on error."""
    if not isinstance(db, Session):
        return
    try:
        repo = TelemetryRepository(db)
        repo.save_observation(observation)
        db.commit()
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to persist telemetry observation: %s", exc)
        try:
            db.rollback()
        except Exception as rb_exc:  # noqa: BLE001
            logger.debug("Rollback failed for telemetry observation: %s", rb_exc)


@router.get(
    "/observation",
    response_model=TelemetryObservationResponse,
    summary="Get Telemetry Observation",
    description="Retrieve a read-only snapshot of time-windowed metrics and access counts without resetting telemetry.",
)
def get_telemetry_observation(
    db: Session = Depends(get_db),  # noqa: B008
) -> TelemetryObservationResponse:
    """Obtain the latest observation from the collector and convert to the public API schema."""
    observation = telemetry_collector.observe()
    _persist_telemetry_observation(db, observation)
    return TelemetryObservationResponse.from_observation(observation)


@router.get(
    "/workload",
    response_model=WorkloadStateResponse,
    summary="Get Workload State",
    description="Retrieve the current WorkloadState derived from observation without workload classification.",
)
def get_workload_state(
    db: Session = Depends(get_db),  # noqa: B008
) -> WorkloadStateResponse:
    """Build WorkloadState from observation and convert to the public API schema."""
    observation = telemetry_collector.observe()
    _persist_telemetry_observation(db, observation)
    workload_state = build_workload_state(observation)
    return WorkloadStateResponse.from_workload_state(workload_state)


@router.get(
    "/system",
    response_model=SystemStateResponse,
    summary="Get System State",
    description="Retrieve the current SystemState derived from cache manager metadata and telemetry observation.",
)
def get_system_state(
    db: Session = Depends(get_db),  # noqa: B008
) -> SystemStateResponse:
    """Build SystemState from cache manager metadata and observation and convert to API schema."""
    observation = telemetry_collector.observe()
    _persist_telemetry_observation(db, observation)
    system_state = build_system_state(cache_manager=cache_manager, observation=observation)
    return SystemStateResponse.from_system_state(system_state)


@router.post(
    "/window/reset",
    response_model=WindowResetResponse,
    summary="Reset Telemetry Observation Window",
    description="Rotate the active observation window into the previous window and reset window counters. Does not clear cache data or object metadata.",
)
def reset_telemetry_window() -> WindowResetResponse:
    """Rotate observation window in collector and return confirmation."""
    telemetry_collector.reset_window()
    return WindowResetResponse(status="ok", message="telemetry window reset")
