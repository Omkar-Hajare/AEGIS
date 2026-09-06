"""Telemetry service layer consuming live FastAPI telemetry endpoints.

Provides read-only observation, workload, and system state snapshots,
as well as window reset triggers adhering strictly to backend contracts.
"""

from typing import Any

import streamlit as st

from frontend.mocks.data import cache_stats
from frontend.services.api_client import api_client

# Short TTL so rapid successive Streamlit reruns (e.g. multiple widgets
# reading telemetry within the same interaction) share one backend round
# trip, without the dashboard ever looking more than ~2s stale.
_LIVE_TTL_SECONDS = 2


@st.cache_data(ttl=_LIVE_TTL_SECONDS, show_spinner=False)
def get_telemetry_observation() -> dict[str, Any]:
    """Fetch live time-windowed observation from GET /telemetry/observation.

    Falls back gracefully to mock trace if backend is unreachable.
    """
    data = api_client.get("telemetry/observation")
    if data:
        data["is_live"] = True
        return data

    # Honest demo fallback
    return {
        "version": "v1-demo",
        "request_rate": cache_stats.get("requests_per_second", 1250) / 60.0,
        "hit_rate": cache_stats.get("hit_rate", 89.6) / 100.0,
        "miss_rate": (100.0 - cache_stats.get("hit_rate", 89.6)) / 100.0,
        "backend_latency_ms": cache_stats.get("p95_latency_ms", 27.3),
        "window_seconds": 60.0,
        "total_requests": cache_stats.get("total_objects", 1240),
        "cache_hits": int(cache_stats.get("total_objects", 1240) * 0.896),
        "cache_misses": int(cache_stats.get("total_objects", 1240) * 0.104),
        "backend_calls": cache_stats.get("backend_calls", 156),
        "current_window_access_counts": {
            "product:101": 42,
            "recommendation:user_88": 28,
            "pricing:surge": 19,
        },
        "previous_window_access_counts": {},
        "timestamp": "2026-09-04T21:00:00Z",
        "is_live": False,
    }


@st.cache_data(ttl=_LIVE_TTL_SECONDS, show_spinner=False)
def get_workload_state() -> dict[str, Any]:
    """Fetch observed WorkloadState from GET /telemetry/workload."""
    data = api_client.get("telemetry/workload")
    if data:
        data["is_live"] = True
        return data

    return {
        "version": "v1-demo",
        "request_rate": cache_stats.get("requests_per_second", 1250) / 60.0,
        "hit_rate": cache_stats.get("hit_rate", 89.6) / 100.0,
        "miss_rate": (100.0 - cache_stats.get("hit_rate", 89.6)) / 100.0,
        "backend_latency_ms": cache_stats.get("p95_latency_ms", 27.3),
        "workload_type": None,  # Follow rule: None unless classified
        "timestamp": "2026-09-04T21:00:00Z",
        "window_seconds": 60.0,
        "metrics": None,
        "is_live": False,
    }


@st.cache_data(ttl=_LIVE_TTL_SECONDS, show_spinner=False)
def get_system_state() -> dict[str, Any]:
    """Fetch observed SystemState from GET /telemetry/system."""
    data = api_client.get("telemetry/system")
    if data:
        data["is_live"] = True
        return data

    return {
        "version": "v1-demo",
        "cache_capacity_bytes": None,  # Follow rule: None = Unconstrained
        "cache_usage_bytes": int(cache_stats.get("cache_usage", 72.4) * 1024 * 1024),
        "object_count": cache_stats.get("total_objects", 1240),
        "backend_calls": cache_stats.get("backend_calls", 156),
        "cache_evictions": 0,
        "timestamp": "2026-09-04T21:00:00Z",
        "window_seconds": 60.0,
        "metrics": None,
        "is_live": False,
    }


def reset_telemetry_window() -> dict[str, Any]:
    """Trigger observation window rotation and counter reset via POST /telemetry/window/reset."""
    result = api_client.post("telemetry/window/reset")
    # Drop the short-lived telemetry cache so the reset is reflected on the
    # very next read instead of serving a pre-reset snapshot for up to 2s.
    get_telemetry_observation.clear()
    get_workload_state.clear()
    get_system_state.clear()
    if result:
        return result
    return {"status": "ok", "message": "Demo telemetry window rotated (offline)"}
