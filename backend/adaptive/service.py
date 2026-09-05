"""AdaptiveService bridge for the Adaptive Cache System.

Orchestrates TelemetryCollector, CacheManager, and DecisionEngine to evaluate
runtime cache economics and telemetry into frozen v1 Decision contracts.
This is purely a translation and orchestration layer: it does NOT mutate cache
state, execute decisions, evict objects, or alter backend storage.
"""

from __future__ import annotations

import sys
from collections.abc import Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Ensure backend directory is in sys.path when imported from repository root
_backend_dir = str(Path(__file__).resolve().parent.parent)
if _backend_dir not in sys.path:
    sys.path.insert(0, _backend_dir)

try:
    from backend.adaptive.engine.decision_engine import DecisionEngine
    from backend.adaptive.history import (
        DecisionHistory,
        runtime_decision_history,
    )
except ImportError:
    from adaptive.engine.decision_engine import (  # type: ignore[no-redef]
        DecisionEngine,
    )
    from adaptive.history import (  # type: ignore[no-redef]
        DecisionHistory,
        runtime_decision_history,
    )

try:
    from cache.factory import create_cache_manager
    from cache.manager import CacheManager
    from cache.metadata import CacheObjectMetadata
except ImportError:
    from backend.cache.factory import create_cache_manager  # type: ignore[no-redef]
    from backend.cache.manager import CacheManager  # type: ignore[no-redef]
    from backend.cache.metadata import CacheObjectMetadata  # type: ignore[no-redef]

try:
    from telemetry.collector import TelemetryCollector
    from telemetry.state import build_system_state, build_workload_state
except ImportError:
    from backend.telemetry.collector import TelemetryCollector  # type: ignore[no-redef]
    from backend.telemetry.state import (  # type: ignore[no-redef]
        build_system_state,
        build_workload_state,
    )

from contracts.schemas import (
    CacheObject,
    Decision,
    SystemState,
    WorkloadState,
    WorkloadType,
)


def metadata_to_cache_object(meta: CacheObjectMetadata | Any) -> CacheObject:
    """Convert a CacheObjectMetadata instance into the frozen v1 CacheObject contract.

    Maps all existing metadata fields into the Pydantic CacheObject schema:
    - key
    - size_bytes
    - access_count
    - last_accessed
    - retrieval_cost_ms
    - hit_count
    - miss_count
    - created_at
    - features
    - metadata
    - version
    """
    if isinstance(meta, CacheObject):
        return meta

    return CacheObject(
        key=str(meta.key),
        size_bytes=int(meta.size_bytes),
        access_count=int(meta.access_count),
        last_accessed=meta.last_accessed,
        retrieval_cost_ms=float(meta.retrieval_cost_ms),
        hit_count=getattr(meta, "hit_count", None),
        miss_count=getattr(meta, "miss_count", None),
        created_at=getattr(meta, "created_at", None),
        features=dict(meta.features)
        if getattr(meta, "features", None) is not None
        else None,
        metadata=dict(meta.metadata)
        if getattr(meta, "metadata", None) is not None
        else None,
        version=getattr(meta, "version", "v1"),
    )


def _to_contract_workload_state(raw: Any) -> WorkloadState:
    """Convert internal WorkloadState dataclass to the frozen v1 contract schema."""
    if isinstance(raw, WorkloadState):
        return raw

    workload_type = getattr(raw, "workload_type", None)
    if isinstance(workload_type, str):
        try:
            workload_type = WorkloadType(workload_type)
        except ValueError:
            workload_type = None
    elif not isinstance(workload_type, WorkloadType):
        workload_type = None

    window_seconds = float(getattr(raw, "window_seconds", 60.0))
    if window_seconds <= 0.0:
        window_seconds = 60.0

    return WorkloadState(
        request_rate=float(getattr(raw, "request_rate", 0.0)),
        hit_rate=float(getattr(raw, "hit_rate", 0.0)),
        miss_rate=float(getattr(raw, "miss_rate", 0.0)),
        backend_latency_ms=float(getattr(raw, "backend_latency_ms", 0.0)),
        workload_type=workload_type,
        timestamp=getattr(raw, "timestamp", datetime.now(timezone.utc)),
        window_seconds=window_seconds,
        metrics=dict(raw.metrics)
        if getattr(raw, "metrics", None) is not None
        else None,
        version="v1",
    )


def _to_contract_system_state(raw: Any, default_capacity_bytes: int) -> SystemState:
    """Convert internal SystemState dataclass to the frozen v1 contract schema.

    Distinction:
    - cache_capacity_bytes: Observed/current runtime cache capacity.
    - default_capacity_bytes: Fallback value (typically decision constraint max_capacity_bytes).

    The frozen SystemState contract requires a strictly positive capacity (gt=0).
    When runtime observed capacity is unknown (e.g. CacheManager does not expose an
    explicit capacity, leaving raw.cache_capacity_bytes as None), default_capacity_bytes
    is used as a fallback strictly at this adaptation boundary so downstream components
    receive a valid contract instance.
    """
    if isinstance(raw, SystemState):
        return raw

    capacity = getattr(raw, "cache_capacity_bytes", None)
    if capacity is None or capacity <= 0:
        capacity = default_capacity_bytes

    window_seconds = float(getattr(raw, "window_seconds", 0.0))
    if window_seconds <= 0.0:
        window_seconds = 60.0

    return SystemState(
        cache_capacity_bytes=int(capacity),
        cache_usage_bytes=int(getattr(raw, "cache_usage_bytes", 0)),
        object_count=int(getattr(raw, "object_count", 0)),
        backend_calls=getattr(raw, "backend_calls", 0),
        cache_evictions=getattr(raw, "cache_evictions", 0),
        timestamp=getattr(raw, "timestamp", datetime.now(timezone.utc)),
        window_seconds=window_seconds,
        metrics=dict(raw.metrics)
        if getattr(raw, "metrics", None) is not None
        else None,
        version="v1",
    )


class AdaptiveService:
    """Orchestration bridge connecting TelemetryCollector, CacheManager, and DecisionEngine.

    Gathers current telemetry observations, converts cache metadata to frozen v1 contracts,
    and invokes the adaptive DecisionEngine to produce a deterministic Decision.
    Does not mutate cache state or execute decisions.
    """

    def __init__(
        self,
        cache_manager: CacheManager | None = None,
        telemetry_collector: TelemetryCollector | None = None,
        decision_engine: DecisionEngine | None = None,
        decision_history: DecisionHistory | None = None,
    ) -> None:
        """Initialize the AdaptiveService with optional injected components."""
        self.cache_manager = (
            cache_manager if cache_manager is not None else create_cache_manager()
        )
        self.telemetry_collector = (
            telemetry_collector
            if telemetry_collector is not None
            else TelemetryCollector()
        )
        self.decision_engine = (
            decision_engine if decision_engine is not None else DecisionEngine()
        )
        self.decision_history = (
            decision_history
            if decision_history is not None
            else runtime_decision_history
        )

    def record_decision(self, decision: Decision) -> None:
        """Record a produced Decision contract into the bounded history."""
        self.decision_history.record(decision)

    def decide(
        self,
        *,
        now: datetime | None = None,
        min_capacity_bytes: int = 1_000_000,
        max_capacity_bytes: int = 10_000_000,
        refresh_after_seconds: float | None = None,
        decision_id: str | None = None,
        capacity_mode: str = "rule_based",
    ) -> Decision:
        """Evaluate current telemetry and cache metadata to produce an adaptive Decision.

        Orchestrates:
        1. TelemetryCollector -> obtain current Observation
        2. Build WorkloadState using build_workload_state()
        3. Build SystemState using build_system_state()
        4. Convert states into frozen v1 contracts
        5. Obtain current cache metadata from CacheManager and filter existing entries
        6. Convert each CacheObjectMetadata into frozen v1 CacheObject
        7. Extract previous-window access counts from Observation
        8. Call DecisionEngine.decide(...)
        9. Return the resulting Decision

        This method is purely read-only and does not mutate cache state, evict objects,
        or execute decisions.
        """
        # 1. Obtain current observation from TelemetryCollector
        observation = self.telemetry_collector.observe(now=now)

        # 2. Build WorkloadState using existing build_workload_state
        raw_workload = build_workload_state(observation)
        workload = _to_contract_workload_state(raw_workload)

        # 3. Build SystemState using existing build_system_state.
        # Distinction:
        # - cache_capacity_bytes represents the observed/current runtime cache capacity.
        # - max_capacity_bytes represents the decision engine sizing constraint.
        # The current CacheManager does not expose an actual cache capacity, so we pass
        # any observed capacity if present (or None) to build_system_state() rather than
        # pretending max_capacity_bytes is the observed runtime capacity.
        observed_capacity = getattr(self.cache_manager, "capacity_bytes", None)
        raw_system = build_system_state(
            cache_manager=self.cache_manager,
            observation=observation,
            cache_capacity_bytes=observed_capacity,
        )
        # Because the frozen v1 SystemState contract requires a strictly positive
        # capacity (gt=0), fall back to max_capacity_bytes only at this adaptation
        # boundary when the observed capacity is None or non-positive.
        system = _to_contract_system_state(
            raw_system, default_capacity_bytes=max_capacity_bytes
        )

        # 4. Obtain cache metadata from CacheManager and convert to CacheObject contracts
        objects: dict[str, CacheObject] = {}
        if hasattr(self.cache_manager, "get_all_metadata"):
            all_metadata = self.cache_manager.get_all_metadata()
            for key, meta in all_metadata.items():
                if hasattr(
                    self.cache_manager, "exists"
                ) and not self.cache_manager.exists(key):
                    continue
                objects[key] = metadata_to_cache_object(meta)
        elif isinstance(self.cache_manager, Mapping):
            for key, meta in self.cache_manager.items():
                objects[key] = metadata_to_cache_object(meta)

        # 5. Extract previous-window access counts from Observation
        previous_access_counts = getattr(
            observation, "previous_window_access_counts", None
        )
        if previous_access_counts is None and hasattr(
            self.telemetry_collector, "previous_window_access_counts"
        ):
            previous_access_counts = (
                self.telemetry_collector.previous_window_access_counts
            )

        # 6. Delegate to DecisionEngine
        refresh_threshold = (
            refresh_after_seconds if refresh_after_seconds is not None else 300.0
        )
        return self.decision_engine.decide(
            objects=objects,
            workload=workload,
            system=system,
            min_capacity_bytes=min_capacity_bytes,
            max_capacity_bytes=max_capacity_bytes,
            now=now,
            previous_access_counts=previous_access_counts,
            refresh_after_seconds=refresh_threshold,
            decision_id=decision_id,
            capacity_mode=capacity_mode,
        )


__all__ = ["AdaptiveService", "metadata_to_cache_object"]
