"""Telemetry service layer consuming live FastAPI telemetry endpoints.

Provides read-only observation, workload, and system state snapshots,
as well as window reset triggers adhering strictly to backend contracts.
"""

from datetime import datetime, timedelta, timezone
from typing import Any

import streamlit as st

from frontend.mocks.data import cache_stats
from frontend.services.api_client import api_client

# 5-second TTL matches Grafana's 5s refresh interval and Prometheus scrape interval.
_LIVE_TTL_SECONDS = 5


@st.cache_data(ttl=_LIVE_TTL_SECONDS, show_spinner=False)
def get_cache_hit_ratio(window_seconds: float = 300.0) -> dict[str, Any]:
    """Fetch canonical aggregated cache hit ratio from GET /telemetry/cache-hit-ratio.

    Calculated from aggregated counters across all backend pods over the observation window.
    Falls back gracefully to demo calculations if backend is unreachable.
    """
    data = api_client.get(f"telemetry/cache-hit-ratio?window_seconds={window_seconds}")
    if data:
        data["is_live"] = True
        return data

    now = datetime.now(timezone.utc)
    start = now - timedelta(seconds=window_seconds)
    total_obj = cache_stats.get("total_objects", 1240)
    hits = int(total_obj * 0.896)
    misses = int(total_obj * 0.104)
    total = hits + misses
    ratio = round((hits / total) * 100.0, 2) if total > 0 else 0.0

    return {
        "total_requests": total,
        "cache_hits": hits,
        "cache_misses": misses,
        "cache_hit_ratio": min(100.0, max(0.0, ratio)),
        "observation_window_start": start.isoformat(),
        "observation_window_end": now.isoformat(),
        "window_seconds": window_seconds,
        "is_live": False,
    }


@st.cache_data(ttl=_LIVE_TTL_SECONDS, show_spinner=False)
def get_telemetry_observation(window_seconds: float = 300.0) -> dict[str, Any]:
    """Fetch live time-windowed observation from GET /telemetry/observation.

    Integrates canonical aggregated cache hit ratio from all backend pods over the
    selected observation window. Falls back gracefully to mock trace if backend is unreachable.
    """
    data = api_client.get("telemetry/observation")
    hit_ratio_data = get_cache_hit_ratio(window_seconds=window_seconds)

    if data:
        data["is_live"] = True
        # Overlay canonical aggregated hit/miss metrics across all pods for the selected window
        data["cache_hits"] = hit_ratio_data["cache_hits"]
        data["cache_misses"] = hit_ratio_data["cache_misses"]
        data["total_requests"] = hit_ratio_data["total_requests"]
        data["cache_hit_ratio"] = hit_ratio_data["cache_hit_ratio"]
        data["hit_rate"] = hit_ratio_data["cache_hit_ratio"] / 100.0
        data["miss_rate"] = (
            (100.0 - hit_ratio_data["cache_hit_ratio"]) / 100.0
            if (hit_ratio_data["cache_hits"] + hit_ratio_data["cache_misses"]) > 0
            else 0.0
        )
        data["observation_window_start"] = hit_ratio_data["observation_window_start"]
        data["observation_window_end"] = hit_ratio_data["observation_window_end"]
        data["window_seconds"] = window_seconds
        return data

    now = datetime.now(timezone.utc)
    start = now - timedelta(seconds=window_seconds)
    total_obj = cache_stats.get("total_objects", 1240)
    hits = hit_ratio_data.get("cache_hits", int(total_obj * 0.896))
    misses = hit_ratio_data.get("cache_misses", int(total_obj * 0.104))
    total = hits + misses
    ratio = hit_ratio_data.get("cache_hit_ratio", round((hits / total) * 100.0, 2) if total > 0 else 0.0)

    # Honest demo fallback
    return {
        "version": "v1-demo",
        "request_rate": cache_stats.get("requests_per_second", 1250) / 60.0,
        "hit_rate": ratio / 100.0,
        "miss_rate": (100.0 - ratio) / 100.0 if total > 0 else 0.0,
        "cache_hit_ratio": ratio,
        "backend_latency_ms": cache_stats.get("p95_latency_ms", 27.3),
        "window_seconds": window_seconds,
        "total_requests": total,
        "cache_hits": hits,
        "cache_misses": misses,
        "observation_window_start": start.isoformat(),
        "observation_window_end": now.isoformat(),
        "backend_calls": cache_stats.get("backend_calls", 156),
        "current_window_access_counts": {
            "product:101": 42,
            "recommendation:user_88": 28,
            "pricing:surge": 19,
        },
        "previous_window_access_counts": {},
        "timestamp": now.isoformat(),
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
    get_cache_hit_ratio.clear()
    get_workload_state.clear()
    get_system_state.clear()
    if result:
        return result
    return {"status": "ok", "message": "Demo telemetry window rotated (offline)"}
