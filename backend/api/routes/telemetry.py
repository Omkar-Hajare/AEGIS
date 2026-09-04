from fastapi import APIRouter

from api.routes.data import cache_manager
from api.schemas.telemetry import (
    SystemStateResponse,
    TelemetryObservationResponse,
    WindowResetResponse,
    WorkloadStateResponse,
)
from telemetry.collector import telemetry_collector
from telemetry.state import build_system_state, build_workload_state

router = APIRouter(prefix="/telemetry", tags=["telemetry"])


@router.get(
    "/observation",
    response_model=TelemetryObservationResponse,
    summary="Get Telemetry Observation",
    description="Retrieve a read-only snapshot of time-windowed metrics and access counts without resetting telemetry.",
)
def get_telemetry_observation() -> TelemetryObservationResponse:
    """Obtain the latest observation from the collector and convert to the public API schema."""
    observation = telemetry_collector.observe()
    return TelemetryObservationResponse.from_observation(observation)


@router.get(
    "/workload",
    response_model=WorkloadStateResponse,
    summary="Get Workload State",
    description="Retrieve the current WorkloadState derived from observation without workload classification.",
)
def get_workload_state() -> WorkloadStateResponse:
    """Build WorkloadState from observation and convert to the public API schema."""
    observation = telemetry_collector.observe()
    workload_state = build_workload_state(observation)
    return WorkloadStateResponse.from_workload_state(workload_state)


@router.get(
    "/system",
    response_model=SystemStateResponse,
    summary="Get System State",
    description="Retrieve the current SystemState derived from cache manager metadata and telemetry observation.",
)
def get_system_state() -> SystemStateResponse:
    """Build SystemState from cache manager metadata and observation and convert to API schema."""
    observation = telemetry_collector.observe()
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
