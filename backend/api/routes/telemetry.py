import json
import logging
import os
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

try:
    from database.connection import get_db
    from database.repositories.telemetry import TelemetryRepository
    from telemetry.collector import telemetry_collector
    from telemetry.observation import Observation
    from telemetry.state import build_system_state, build_workload_state

    from api.routes.data import cache_manager
    from api.schemas.telemetry import (
        CacheHitRatioResponse,
        SystemStateResponse,
        TelemetryObservationResponse,
        WindowResetResponse,
        WorkloadStateResponse,
    )
except ImportError:
    from backend.api.routes.data import cache_manager  # type: ignore[no-redef]
    from backend.api.schemas.telemetry import (  # type: ignore[no-redef]
        CacheHitRatioResponse,
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


def _query_prometheus_scalar(query: str, timeout: float = 1.2) -> float | None:
    """Execute a PromQL query against the Prometheus HTTP API and return a scalar float."""
    if "PYTEST_CURRENT_TEST" in os.environ or os.getenv("TESTING", "").lower() in ("1", "true", "yes"):
        return None

    prom_hosts = [
        os.getenv("PROMETHEUS_URL", "").strip(),
        "http://adaptive-monitoring-kube-p-prometheus.monitoring:9090",
        "http://adaptive-monitoring-kube-p-prometheus.monitoring.svc.cluster.local:9090",
        "http://localhost:9091",
        "http://localhost:9090",
    ]
    params = urllib.parse.urlencode({"query": query})
    for base in prom_hosts:
        if not base:
            continue
        url = f"{base.rstrip('/')}/api/v1/query?{params}"
        try:
            req = urllib.request.Request(url, headers={"Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                if resp.status == 200:
                    payload = json.loads(resp.read().decode("utf-8"))
                    results = payload.get("data", {}).get("result", [])
                    if results:
                        return float(results[0]["value"][1])
                    return 0.0
        except Exception as exc:  # noqa: BLE001
            logger.debug("Failed to query Prometheus at %s: %s", base, exc)
            continue
    return None


@router.get(
    "/cache-hit-ratio",
    response_model=CacheHitRatioResponse,
    summary="Get Canonical Aggregated Cache Hit Ratio",
    description="Retrieve canonical aggregated cache hits, misses, and hit ratio across all backend pods for the observation window.",
)
def get_cache_hit_ratio(
    window_seconds: float = Query(default=300.0, ge=1.0, description="Duration of observation window in seconds"),
) -> CacheHitRatioResponse:
    """Return aggregated cache hit ratio across all pods using canonical formula."""
    window_str = f"{max(1, int(window_seconds))}s"
    hits_scalar = _query_prometheus_scalar(f"sum(increase(cache_hits_total[{window_str}]))")
    misses_scalar = _query_prometheus_scalar(f"sum(increase(cache_misses_total[{window_str}]))")
    reqs_scalar = _query_prometheus_scalar(f"sum(increase(requests_total[{window_str}]))")

    if hits_scalar is not None and misses_scalar is not None:
        cache_hits = max(0, int(round(hits_scalar)))
        cache_misses = max(0, int(round(misses_scalar)))
        if reqs_scalar is not None:
            total_requests = max(int(round(reqs_scalar)), cache_hits + cache_misses)
        else:
            total_requests = cache_hits + cache_misses
    else:
        # Graceful fallback to in-memory collector (e.g. unit tests or when Prometheus is offline)
        cache_hits = telemetry_collector._cache_hits
        cache_misses = telemetry_collector._cache_misses
        total_requests = max(telemetry_collector._total_requests, cache_hits + cache_misses)

    total_cache_ops = cache_hits + cache_misses
    if total_cache_ops > 0:
        cache_hit_ratio = round((cache_hits / total_cache_ops) * 100.0, 2)
    else:
        cache_hit_ratio = 0.0

    cache_hit_ratio = min(100.0, max(0.0, cache_hit_ratio))
    end_time = datetime.now(timezone.utc)
    start_time = end_time - timedelta(seconds=window_seconds)

    return CacheHitRatioResponse(
        total_requests=total_requests,
        cache_hits=cache_hits,
        cache_misses=cache_misses,
        cache_hit_ratio=cache_hit_ratio,
        observation_window_start=start_time,
        observation_window_end=end_time,
    )

