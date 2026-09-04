from fastapi import APIRouter

from api.schemas.telemetry import TelemetryObservationResponse, WindowResetResponse
from telemetry.collector import telemetry_collector

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
