"""Centralized REST API client for the Adaptive Cache Management System.

Handles communication with the FastAPI backend, configuration, timeouts,
and graceful connection error handling without scattering HTTP logic across pages.
Also provides schema-preview and demo fallback functions.
"""

import os
from typing import Any, Optional

import requests

from frontend.mocks import data as mock_data


# Backend URL configurable via environment variable.
# Docker/Kubernetes can override this with BACKEND_URL.
BACKEND_API_URL = os.getenv(
    "BACKEND_URL",
    os.getenv(
        "BACKEND_API_URL",
        "http://localhost:8000",
    ),
).rstrip("/")


DEFAULT_READ_TIMEOUT = 2.5
DEFAULT_ACTION_TIMEOUT = 5.0


def check_backend_health() -> dict | None:
    """Check whether the backend API is reachable."""
    try:
        response = requests.get(
            f"{BACKEND_API_URL}/health",
            timeout=2,
        )

        if response.status_code == 200:
            return response.json()

    except requests.RequestException:
        pass

    return None


class ApiClient:
    """Production-ready HTTP client wrapper with error handling."""

    def __init__(
        self,
        base_url: str = BACKEND_API_URL,
    ):
        self.base_url = base_url.rstrip("/")

    def get(
        self,
        endpoint: str,
        timeout: float = DEFAULT_READ_TIMEOUT,
    ) -> Optional[dict[str, Any]]:
        """Perform GET request with structured error handling."""
        url = f"{self.base_url}/{endpoint.lstrip('/')}"

        try:
            response = requests.get(
                url,
                timeout=timeout,
            )

            if response.status_code == 200:
                return response.json()

            return None

        except (requests.RequestException, ValueError):
            return None

    def post(
        self,
        endpoint: str,
        json_data: dict[str, Any] | None = None,
        timeout: float = DEFAULT_ACTION_TIMEOUT,
    ) -> dict[str, Any] | None:
        """Perform POST request with structured error handling."""
        url = f"{self.base_url}/{endpoint.lstrip('/')}"

        try:
            response = requests.post(
                url,
                json=json_data,
                timeout=timeout,
            )

            if response.status_code in (200, 201):
                return response.json()

            return None

        except (requests.RequestException, ValueError):
            return None

    def check_health(self) -> dict[str, Any]:
        """Check backend health via GET /health."""
        data = self.get(
            "health",
            timeout=1.5,
        )

        if data and data.get("status") == "ok":
            return {
                "is_live": True,
                "status": "ok",
                "service": data.get(
                    "service",
                    "Adaptive Cache System",
                ),
                "version": data.get(
                    "version",
                    "0.1.0",
                ),
                "base_url": self.base_url,
            }

        return {
            "is_live": False,
            "status": "offline",
            "service": "Adaptive Cache System",
            "version": "Local Demo Fallback",
            "base_url": self.base_url,
        }

    def get_runtime_decision(
        self,
        *,
        min_capacity_bytes: int | None = None,
        max_capacity_bytes: int | None = None,
        refresh_after_seconds: float | None = None,
        capacity_mode: str | None = None,
        now: str | None = None,
        decision_id: str | None = None,
    ) -> dict[str, Any] | None:
        """Fetch live adaptive decision from the backend."""
        params: dict[str, Any] = {}

        if min_capacity_bytes is not None:
            params["min_capacity_bytes"] = min_capacity_bytes

        if max_capacity_bytes is not None:
            params["max_capacity_bytes"] = max_capacity_bytes

        if refresh_after_seconds is not None:
            params["refresh_after_seconds"] = refresh_after_seconds

        if capacity_mode is not None:
            params["capacity_mode"] = capacity_mode

        if now is not None:
            params["now"] = now

        if decision_id is not None:
            params["decision_id"] = decision_id

        url = f"{self.base_url}/adaptive/runtime-decision"

        try:
            response = requests.get(
                url,
                params=params,
                timeout=DEFAULT_READ_TIMEOUT,
            )

            if response.status_code == 200:
                return response.json()

            return None

        except (requests.RequestException, ValueError):
            return None

    def get_cache_objects(self) -> dict[str, Any]:
        """Fetch resident cache objects from the backend."""
        data = self.get("cache/objects")

        if (
            data is not None
            and isinstance(data, dict)
            and "objects" in data
        ):
            return {
                "is_live": True,
                "objects": data.get("objects", []),
                "object_count": data.get(
                    "object_count",
                    len(data.get("objects", [])),
                ),
            }

        fallback = getattr(
            mock_data,
            "cache_objects",
            [],
        )

        return {
            "is_live": False,
            "objects": [dict(item) for item in fallback],
            "object_count": len(fallback),
        }

    def get_decision_history(
        self,
        limit: int = 50,
    ) -> dict[str, Any]:
        """Fetch recent adaptive decisions from the backend."""
        endpoint = (
            f"adaptive/decisions?limit={limit}"
            if limit
            else "adaptive/decisions"
        )

        data = self.get(endpoint)

        if (
            data is not None
            and isinstance(data, dict)
            and "decisions" in data
        ):
            return {
                "is_live": True,
                "decisions": data.get("decisions", []),
                "count": data.get(
                    "count",
                    len(data.get("decisions", [])),
                ),
            }

        return {
            "is_live": False,
            "decisions": [],
            "count": 0,
        }


# Singleton instance for centralized use.
api_client = ApiClient()


def check_health() -> dict[str, Any]:
    """Module-level health check function."""
    return api_client.check_health()


def get_runtime_decision(
    *,
    min_capacity_bytes: int | None = None,
    max_capacity_bytes: int | None = None,
    refresh_after_seconds: float | None = None,
    capacity_mode: str | None = None,
    now: str | None = None,
    decision_id: str | None = None,
) -> dict[str, Any] | None:
    """Fetch live adaptive decision from the backend."""
    return api_client.get_runtime_decision(
        min_capacity_bytes=min_capacity_bytes,
        max_capacity_bytes=max_capacity_bytes,
        refresh_after_seconds=refresh_after_seconds,
        capacity_mode=capacity_mode,
        now=now,
        decision_id=decision_id,
    )


def get_decision_history(
    limit: int = 50,
) -> dict[str, Any]:
    """Fetch recent decision history from the backend."""
    return api_client.get_decision_history(limit=limit)


def fetch_resident_cache_objects() -> dict[str, Any]:
    """Fetch resident cache objects from the backend."""
    return api_client.get_cache_objects()


# ----------------------------------------------------------------------
# Schema Architecture & Benchmark Fallbacks
# ----------------------------------------------------------------------


def get_cache_stats() -> dict[str, Any]:
    """Fetch baseline stats for schema preview."""
    return getattr(
        mock_data,
        "cache_stats",
        {},
    )


def get_cache_objects() -> list[dict[str, Any]]:
    """Fetch object entries for schema preview."""
    return getattr(
        mock_data,
        "cache_objects",
        [],
    )


def get_adaptive_decision() -> dict[str, Any]:
    """Fetch decision schema for architecture preview."""
    return getattr(
        mock_data,
        "adaptive_decision",
        {},
    )


def get_workload() -> dict[str, Any]:
    """Fetch workload archetypes for scenario modeling."""
    return getattr(
        mock_data,
        "workload_data",
        {},
    )


def get_performance_history() -> dict[str, Any]:
    """Fetch performance history dataset."""
    return getattr(
        mock_data,
        "performance_history",
        {
            "time": [
                "10:00",
                "10:05",
                "10:10",
                "10:15",
                "10:20",
            ],
            "hit_rate": [
                80.0,
                83.2,
                85.1,
                88.4,
                89.6,
            ],
            "request_rate": [
                1100,
                1150,
                1200,
                1220,
                1250,
            ],
        },
    )


def get_benchmark_results() -> list[dict[str, Any]]:
    """Fetch benchmark comparison evaluation dataset."""
    return getattr(
        mock_data,
        "benchmark_results",
        [
            {
                "policy": "FIFO",
                "hit_rate": 64.2,
                "latency_p95": 58.4,
                "backend_calls": 3580,
                "cost_per_hour": 24.10,
            },
            {
                "policy": "LRU",
                "hit_rate": 78.4,
                "latency_p95": 42.5,
                "backend_calls": 2160,
                "cost_per_hour": 18.40,
            },
            {
                "policy": "LFU",
                "hit_rate": 81.2,
                "latency_p95": 38.1,
                "backend_calls": 1880,
                "cost_per_hour": 16.20,
            },
            {
                "policy": "GDSF",
                "hit_rate": 85.0,
                "latency_p95": 32.0,
                "backend_calls": 1500,
                "cost_per_hour": 13.50,
            },
            {
                "policy": "Adaptive Engine (Satyagrah)",
                "hit_rate": 89.6,
                "latency_p95": 27.3,
                "backend_calls": 1040,
                "cost_per_hour": 11.20,
            },
        ],
    )