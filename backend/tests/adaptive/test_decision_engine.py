"""Unit tests for DecisionEngine in the Adaptive Cache System.

Tests end-to-end orchestration, workload classification, utility scoring,
staleness/refresh evaluation, capacity controller recommendations, capacity-driven
evictions, independence of eviction and refresh, input validation, determinism,
and contract immutability.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import datetime, timedelta, timezone
from typing import Any

import pytest

from backend.adaptive.engine.decision_engine import DecisionEngine
from contracts.schemas.cache import CacheObject
from contracts.schemas.decision import Decision
from contracts.schemas.enums import CapacityAction, WorkloadType
from contracts.schemas.system import SystemState
from contracts.schemas.workload import WorkloadState


@pytest.fixture
def engine() -> DecisionEngine:
    """Fixture providing a clean DecisionEngine instance."""
    return DecisionEngine()


@pytest.fixture
def now() -> datetime:
    """Fixture providing a fixed timezone-aware reference datetime."""
    return datetime(2026, 9, 4, 12, 0, 0, tzinfo=timezone.utc)


def make_object(
    key: str,
    size_bytes: int = 100,
    access_count: int = 10,
    retrieval_cost_ms: float = 50.0,
    last_accessed: datetime | None = None,
    created_at: datetime | None = None,
) -> CacheObject:
    """Helper to construct a valid CacheObject."""
    ts = last_accessed or datetime(2026, 9, 4, 11, 58, 0, tzinfo=timezone.utc)
    return CacheObject(
        key=key,
        size_bytes=size_bytes,
        access_count=access_count,
        last_accessed=ts,
        retrieval_cost_ms=retrieval_cost_ms,
        created_at=created_at,
    )


def make_workload(
    timestamp: datetime,
    request_rate: float = 100.0,
    hit_rate: float = 0.5,
    miss_rate: float = 0.5,
    backend_latency_ms: float = 30.0,
    workload_type: WorkloadType = WorkloadType.STEADY,
    window_seconds: float = 60.0,
    metrics: Mapping[str, Any] | None = None,
) -> WorkloadState:
    """Helper to construct a valid WorkloadState."""
    return WorkloadState(
        request_rate=request_rate,
        hit_rate=hit_rate,
        miss_rate=miss_rate,
        backend_latency_ms=backend_latency_ms,
        workload_type=workload_type,
        timestamp=timestamp,
        window_seconds=window_seconds,
        metrics=dict(metrics) if metrics is not None else None,
    )


def make_system(
    timestamp: datetime,
    cache_capacity_bytes: int = 1000,
    cache_usage_bytes: int = 500,
    object_count: int = 5,
    window_seconds: float = 60.0,
) -> SystemState:
    """Helper to construct a valid SystemState."""
    return SystemState(
        cache_capacity_bytes=cache_capacity_bytes,
        cache_usage_bytes=cache_usage_bytes,
        object_count=object_count,
        timestamp=timestamp,
        window_seconds=window_seconds,
    )


# ---------------------------------------------------------------------------
# Initialisation & Calling Interface Tests
# ---------------------------------------------------------------------------


def test_decision_engine_initialization() -> None:
    """Engine initializes with default components when none provided."""
    engine = DecisionEngine()
    assert engine.feature_extractor is not None
    assert engine.workload_analyzer is not None
    assert engine.scorer is not None
    assert engine.refresh_policy is not None
    assert engine.capacity_controller is not None
    assert engine.eviction_policy is not None


def test_engine_callable_matches_decide(engine: DecisionEngine, now: datetime) -> None:
    """Calling the engine instance directly yields the same result as decide()."""
    objs = {"k1": make_object("k1", size_bytes=100)}
    workload = make_workload(now)
    system = make_system(now, cache_capacity_bytes=1000, cache_usage_bytes=500)

    dec1 = engine.decide(
        objects=objs,
        workload=workload,
        system=system,
        min_capacity_bytes=500,
        max_capacity_bytes=2000,
        now=now,
    )
    dec2 = engine(
        objects=objs,
        workload=workload,
        system=system,
        min_capacity_bytes=500,
        max_capacity_bytes=2000,
        now=now,
    )

    assert dec1.decision_id == dec2.decision_id
    assert dec1.recommended_capacity_bytes == dec2.recommended_capacity_bytes
    assert dec1.object_scores == dec2.object_scores
    assert dec1.eviction_keys == dec2.eviction_keys


# ---------------------------------------------------------------------------
# End-to-End Decision Generation Tests
# ---------------------------------------------------------------------------


def test_standard_steady_workload_decision(
    engine: DecisionEngine, now: datetime
) -> None:
    """Standard steady workload produces a valid, complete Decision contract."""
    objs = {
        "k1": make_object(
            "k1", size_bytes=100, access_count=20, retrieval_cost_ms=10.0
        ),
        "k2": make_object(
            "k2", size_bytes=100, access_count=5, retrieval_cost_ms=100.0
        ),
    }
    workload = make_workload(now, hit_rate=0.5, miss_rate=0.5)
    system = make_system(
        now, cache_capacity_bytes=1000, cache_usage_bytes=500, object_count=2
    )

    decision = engine.decide(
        objects=objs,
        workload=workload,
        system=system,
        min_capacity_bytes=500,
        max_capacity_bytes=2000,
        now=now,
    )

    assert isinstance(decision, Decision)
    assert decision.version == "v1"
    assert decision.timestamp == now
    assert decision.capacity_action == CapacityAction.MAINTAIN
    assert decision.recommended_capacity_bytes == 1000
    assert "k1" in decision.object_scores
    assert "k2" in decision.object_scores
    assert decision.eviction_keys == []
    assert decision.decision_id.startswith("dec-")
    assert "Workload=" in decision.reason

    # Metadata checks
    metadata = decision.metadata
    assert metadata["workload_type"] == WorkloadType.STEADY.value
    assert metadata["object_count"] == 2
    assert metadata["current_usage_bytes"] == 200
    assert metadata["target_capacity_bytes"] == 1000
    assert metadata["capacity_action"] == CapacityAction.MAINTAIN.value
    assert metadata["refresh_keys"] == []
    assert metadata["refreshed_count"] == 0
    assert "reason_components" in metadata

    # JSON serializability of metadata
    serialized = json.dumps(decision.metadata)
    assert isinstance(serialized, str)


def test_custom_decision_id_is_preserved(engine: DecisionEngine, now: datetime) -> None:
    """Explicit decision_id is preserved in the Decision contract."""
    objs = {"k1": make_object("k1")}
    workload = make_workload(now)
    system = make_system(now)

    decision = engine.decide(
        objects=objs,
        workload=workload,
        system=system,
        min_capacity_bytes=500,
        max_capacity_bytes=2000,
        now=now,
        decision_id="custom-run-12345",
    )

    assert decision.decision_id == "custom-run-12345"


def test_timestamp_fallback_to_system_state(
    engine: DecisionEngine, now: datetime
) -> None:
    """When now is None, engine defaults to system.timestamp."""
    objs = {"k1": make_object("k1")}
    workload = make_workload(now)
    system = make_system(now)

    decision = engine.decide(
        objects=objs,
        workload=workload,
        system=system,
        min_capacity_bytes=500,
        max_capacity_bytes=2000,
        now=None,
    )

    assert decision.timestamp == now


# ---------------------------------------------------------------------------
# Workload Analyzer Integration Tests
# ---------------------------------------------------------------------------


def test_spike_workload_classification_reflected(
    engine: DecisionEngine, now: datetime
) -> None:
    """High request rate triggers SPIKE classification in Decision metadata."""
    objs = {"k1": make_object("k1")}
    workload = make_workload(
        now, request_rate=600.0, metrics={"request_rate_baseline": 300.0}
    )
    system = make_system(now)

    decision = engine.decide(
        objects=objs,
        workload=workload,
        system=system,
        min_capacity_bytes=500,
        max_capacity_bytes=2000,
        now=now,
    )

    assert decision.metadata["workload_type"] == WorkloadType.SPIKE.value
    assert f"Workload={WorkloadType.SPIKE.value}" in decision.reason


def test_popularity_shift_workload_classification_reflected(
    engine: DecisionEngine, now: datetime
) -> None:
    """High popularity shift score triggers POPULARITY_SHIFT classification."""
    objs = {"k1": make_object("k1")}
    workload = make_workload(now, metrics={"popularity_shift_score": 0.85})
    system = make_system(now)

    decision = engine.decide(
        objects=objs,
        workload=workload,
        system=system,
        min_capacity_bytes=500,
        max_capacity_bytes=2000,
        now=now,
    )

    assert decision.metadata["workload_type"] == WorkloadType.POPULARITY_SHIFT.value
    assert f"Workload={WorkloadType.POPULARITY_SHIFT.value}" in decision.reason


def test_compute_heavy_workload_classification_reflected(
    engine: DecisionEngine, now: datetime
) -> None:
    """High backend latency triggers COMPUTE_HEAVY classification."""
    objs = {"k1": make_object("k1")}
    workload = make_workload(now, backend_latency_ms=250.0)
    system = make_system(now)

    decision = engine.decide(
        objects=objs,
        workload=workload,
        system=system,
        min_capacity_bytes=500,
        max_capacity_bytes=2000,
        now=now,
    )

    assert decision.metadata["workload_type"] == WorkloadType.COMPUTE_HEAVY.value
    assert f"Workload={WorkloadType.COMPUTE_HEAVY.value}" in decision.reason


def test_read_heavy_workload_classification_reflected(
    engine: DecisionEngine, now: datetime
) -> None:
    """High hit rate (>=0.80) triggers READ_HEAVY classification."""
    objs = {"k1": make_object("k1")}
    workload = make_workload(now, request_rate=200.0, hit_rate=0.90, miss_rate=0.10)
    system = make_system(now)

    decision = engine.decide(
        objects=objs,
        workload=workload,
        system=system,
        min_capacity_bytes=500,
        max_capacity_bytes=2000,
        now=now,
    )

    assert decision.metadata["workload_type"] == WorkloadType.READ_HEAVY.value
    assert f"Workload={WorkloadType.READ_HEAVY.value}" in decision.reason


# ---------------------------------------------------------------------------
# Capacity Controller & Eviction Policy Integration Tests
# ---------------------------------------------------------------------------


def test_no_eviction_when_usage_within_capacity(
    engine: DecisionEngine, now: datetime
) -> None:
    """No evictions are selected if current cache usage is <= recommended capacity."""
    objs = {
        "k1": make_object("k1", size_bytes=300),
        "k2": make_object("k2", size_bytes=300),
    }
    workload = make_workload(now)
    system = make_system(
        now, cache_capacity_bytes=1000, cache_usage_bytes=600, object_count=2
    )

    decision = engine.decide(
        objects=objs,
        workload=workload,
        system=system,
        min_capacity_bytes=500,
        max_capacity_bytes=2000,
        now=now,
    )

    assert decision.eviction_keys == []
    assert "no evictions required" in decision.reason


def test_capacity_pressure_triggers_eviction_of_lowest_scoring_object(
    engine: DecisionEngine, now: datetime
) -> None:
    """Usage exceeding recommended capacity triggers eviction of lowest score object."""
    objs = {
        "k_valuable": make_object(
            "k_valuable",
            size_bytes=600,
            access_count=50,
            retrieval_cost_ms=500.0,
            last_accessed=now - timedelta(seconds=10),
        ),
        "k_cheap": make_object(
            "k_cheap",
            size_bytes=600,
            access_count=1,
            retrieval_cost_ms=5.0,
            last_accessed=now - timedelta(seconds=200),
        ),
    }
    workload = make_workload(now)
    system = make_system(
        now, cache_capacity_bytes=1000, cache_usage_bytes=1200, object_count=2
    )

    decision = engine.decide(
        objects=objs,
        workload=workload,
        system=system,
        min_capacity_bytes=500,
        max_capacity_bytes=1000,
        now=now,
    )

    assert "k_cheap" in decision.eviction_keys
    assert "k_valuable" not in decision.eviction_keys
    assert decision.object_scores["k_valuable"] > decision.object_scores["k_cheap"]
    assert len(decision.eviction_keys) == 1
    assert "cache pressure requires 1 evictions" in decision.reason


def test_scale_down_triggers_eviction_when_new_capacity_exceeded(
    engine: DecisionEngine, now: datetime
) -> None:
    """Low utilization triggering SCALE_DOWN evicts objects if new capacity
    is exceeded.
    """
    # Under low utilization (<=40%) and hit_rate >= 0.80, capacity scales down by 15%.
    # If capacity is 1000, scaled down to 850.
    # If usage is 900, usage exceeds 850, so eviction occurs.
    objs = {
        "k1": make_object("k1", size_bytes=500, access_count=1, retrieval_cost_ms=5.0),
        "k2": make_object(
            "k2", size_bytes=400, access_count=20, retrieval_cost_ms=100.0
        ),
    }
    # Utilization = 300 / 1000 = 30% (<=40%) with hit_rate = 0.85 (>=0.80)
    workload = make_workload(now, hit_rate=0.85, miss_rate=0.15)
    system = make_system(
        now, cache_capacity_bytes=1000, cache_usage_bytes=300, object_count=2
    )

    decision = engine.decide(
        objects=objs,
        workload=workload,
        system=system,
        min_capacity_bytes=500,
        max_capacity_bytes=2000,
        now=now,
    )

    assert decision.capacity_action == CapacityAction.SCALE_DOWN
    assert decision.recommended_capacity_bytes == 850
    # Sum of objs is 900 > 850 -> must evict k1 (lower score)
    assert decision.eviction_keys == ["k1"]


# ---------------------------------------------------------------------------
# Refresh Policy Integration Tests
# ---------------------------------------------------------------------------


def test_refresh_keys_populated_for_stale_objects(
    engine: DecisionEngine, now: datetime
) -> None:
    """Objects older than refresh_after_seconds are captured in
    metadata['refresh_keys'].
    """
    objs = {
        "k_fresh": make_object("k_fresh", last_accessed=now - timedelta(seconds=50)),
        "k_stale": make_object("k_stale", last_accessed=now - timedelta(seconds=400)),
    }
    workload = make_workload(now)
    system = make_system(now, cache_capacity_bytes=1000, cache_usage_bytes=200)

    decision = engine.decide(
        objects=objs,
        workload=workload,
        system=system,
        min_capacity_bytes=500,
        max_capacity_bytes=2000,
        now=now,
        refresh_after_seconds=300.0,
    )

    assert decision.metadata["refresh_keys"] == ["k_stale"]
    assert decision.metadata["refreshed_count"] == 1
    assert "1 objects require refresh" in decision.reason


# ---------------------------------------------------------------------------
# Independence of Eviction and Refresh
# ---------------------------------------------------------------------------


def test_stale_object_not_evicted_without_capacity_pressure(
    engine: DecisionEngine, now: datetime
) -> None:
    """Stale object is marked for refresh but NOT evicted if capacity is sufficient."""
    objs = {
        "k_stale": make_object(
            "k_stale",
            size_bytes=100,
            last_accessed=now - timedelta(seconds=600),
        )
    }
    workload = make_workload(now)
    system = make_system(now, cache_capacity_bytes=1000, cache_usage_bytes=100)

    decision = engine.decide(
        objects=objs,
        workload=workload,
        system=system,
        min_capacity_bytes=500,
        max_capacity_bytes=2000,
        now=now,
        refresh_after_seconds=300.0,
    )

    assert decision.metadata["refresh_keys"] == ["k_stale"]
    assert decision.eviction_keys == []


def test_stale_and_evicted_object_reports_both(
    engine: DecisionEngine, now: datetime
) -> None:
    """Under capacity pressure, a stale low-value object is both refreshed
    and evicted.
    """
    objs = {
        "k_fresh_valuable": make_object(
            "k_fresh_valuable",
            size_bytes=600,
            access_count=50,
            retrieval_cost_ms=500.0,
            last_accessed=now - timedelta(seconds=10),
        ),
        "k_stale_cheap": make_object(
            "k_stale_cheap",
            size_bytes=600,
            access_count=1,
            retrieval_cost_ms=5.0,
            last_accessed=now - timedelta(seconds=600),
        ),
    }
    workload = make_workload(now)
    system = make_system(now, cache_capacity_bytes=1000, cache_usage_bytes=1200)

    decision = engine.decide(
        objects=objs,
        workload=workload,
        system=system,
        min_capacity_bytes=500,
        max_capacity_bytes=1000,
        now=now,
        refresh_after_seconds=300.0,
    )

    # Must be in eviction keys
    assert "k_stale_cheap" in decision.eviction_keys
    # Must also be recognized as stale in refresh_keys
    assert "k_stale_cheap" in decision.metadata["refresh_keys"]


# ---------------------------------------------------------------------------
# Edge Cases
# ---------------------------------------------------------------------------


def test_empty_objects_mapping(engine: DecisionEngine, now: datetime) -> None:
    """Empty objects dictionary returns valid Decision with empty collections."""
    workload = make_workload(now)
    system = make_system(
        now, cache_capacity_bytes=1000, cache_usage_bytes=0, object_count=0
    )

    decision = engine.decide(
        objects={},
        workload=workload,
        system=system,
        min_capacity_bytes=500,
        max_capacity_bytes=2000,
        now=now,
    )

    assert decision.object_scores == {}
    assert decision.eviction_keys == []
    assert decision.metadata["refresh_keys"] == []
    assert decision.metadata["object_count"] == 0
    assert decision.metadata["current_usage_bytes"] == 0


def test_previous_access_counts_forwarding(
    engine: DecisionEngine, now: datetime
) -> None:
    """Previous access counts are passed to FeatureExtractor without error."""
    objs = {"k1": make_object("k1", access_count=20)}
    prev_counts = {"k1": 10}
    workload = make_workload(now)
    system = make_system(now)

    decision = engine.decide(
        objects=objs,
        workload=workload,
        system=system,
        min_capacity_bytes=500,
        max_capacity_bytes=2000,
        now=now,
        previous_access_counts=prev_counts,
    )

    assert "k1" in decision.object_scores
    assert 0.0 <= decision.object_scores["k1"] <= 1.0


# ---------------------------------------------------------------------------
# Validation & Error Handling Tests
# ---------------------------------------------------------------------------


def test_invalid_objects_type_raises_type_error(
    engine: DecisionEngine, now: datetime
) -> None:
    """Non-mapping objects argument raises TypeError."""
    workload = make_workload(now)
    system = make_system(now)

    with pytest.raises(TypeError, match="objects must be a mapping"):
        engine.decide(
            objects="not-a-dict",  # type: ignore[arg-type]
            workload=workload,
            system=system,
            min_capacity_bytes=500,
            max_capacity_bytes=2000,
        )


def test_invalid_object_element_raises_type_error(
    engine: DecisionEngine, now: datetime
) -> None:
    """Mapping value not being a CacheObject raises TypeError."""
    workload = make_workload(now)
    system = make_system(now)

    with pytest.raises(TypeError, match="must be a CacheObject"):
        engine.decide(
            objects={"k1": "not-a-cache-object"},  # type: ignore[arg-type]
            workload=workload,
            system=system,
            min_capacity_bytes=500,
            max_capacity_bytes=2000,
        )


def test_mismatched_object_key_raises_value_error(
    engine: DecisionEngine, now: datetime
) -> None:
    """Mismatch between dictionary key and CacheObject.key raises ValueError."""
    workload = make_workload(now)
    system = make_system(now)
    obj = make_object("internal_key")

    with pytest.raises(ValueError, match="does not match CacheObject.key"):
        engine.decide(
            objects={"dict_key": obj},
            workload=workload,
            system=system,
            min_capacity_bytes=500,
            max_capacity_bytes=2000,
        )


def test_invalid_workload_raises_type_error(
    engine: DecisionEngine, now: datetime
) -> None:
    """Invalid workload type raises TypeError."""
    system = make_system(now)

    with pytest.raises(TypeError, match="workload must be a WorkloadState"):
        engine.decide(
            objects={},
            workload="invalid",  # type: ignore[arg-type]
            system=system,
            min_capacity_bytes=500,
            max_capacity_bytes=2000,
        )


def test_invalid_system_raises_type_error(
    engine: DecisionEngine, now: datetime
) -> None:
    """Invalid system type raises TypeError."""
    workload = make_workload(now)

    with pytest.raises(TypeError, match="system must be a SystemState"):
        engine.decide(
            objects={},
            workload=workload,
            system="invalid",  # type: ignore[arg-type]
            min_capacity_bytes=500,
            max_capacity_bytes=2000,
        )


def test_invalid_capacity_bounds_raise_value_error(
    engine: DecisionEngine, now: datetime
) -> None:
    """Capacity bounds <= 0 or min > max raise ValueError."""
    workload = make_workload(now)
    system = make_system(now)

    with pytest.raises(ValueError, match="min_capacity_bytes must be greater than 0"):
        engine.decide(
            objects={},
            workload=workload,
            system=system,
            min_capacity_bytes=0,
            max_capacity_bytes=1000,
        )

    with pytest.raises(ValueError, match="max_capacity_bytes must be greater than 0"):
        engine.decide(
            objects={},
            workload=workload,
            system=system,
            min_capacity_bytes=100,
            max_capacity_bytes=-50,
        )

    with pytest.raises(ValueError, match="must be <= max_capacity_bytes"):
        engine.decide(
            objects={},
            workload=workload,
            system=system,
            min_capacity_bytes=2000,
            max_capacity_bytes=1000,
        )


def test_naive_datetime_raises_value_error(
    engine: DecisionEngine, now: datetime
) -> None:
    """Naive datetime for now raises ValueError."""
    workload = make_workload(now)
    system = make_system(now)
    naive_now = datetime(2026, 9, 4, 12, 0, 0)  # noqa: DTZ001

    with pytest.raises(ValueError, match="naive datetime"):
        engine.decide(
            objects={},
            workload=workload,
            system=system,
            min_capacity_bytes=500,
            max_capacity_bytes=1000,
            now=naive_now,
        )


def test_invalid_refresh_after_seconds_raises_value_error(
    engine: DecisionEngine, now: datetime
) -> None:
    """Negative, zero, or non-finite refresh_after_seconds raises ValueError."""
    workload = make_workload(now)
    system = make_system(now)

    with pytest.raises(
        ValueError, match="refresh_after_seconds must be greater than 0"
    ):
        engine.decide(
            objects={},
            workload=workload,
            system=system,
            min_capacity_bytes=500,
            max_capacity_bytes=1000,
            now=now,
            refresh_after_seconds=0.0,
        )

    with pytest.raises(ValueError, match="refresh_after_seconds must be finite"):
        engine.decide(
            objects={},
            workload=workload,
            system=system,
            min_capacity_bytes=500,
            max_capacity_bytes=1000,
            now=now,
            refresh_after_seconds=float("nan"),
        )


# ---------------------------------------------------------------------------
# Determinism & Immutability Tests
# ---------------------------------------------------------------------------


def test_decision_determinism(engine: DecisionEngine, now: datetime) -> None:
    """Calling decide() repeatedly with identical inputs yields identical Decisions."""
    objs = {
        "k1": make_object("k1", size_bytes=200, access_count=5),
        "k2": make_object("k2", size_bytes=300, access_count=15),
    }
    workload = make_workload(now)
    system = make_system(now, cache_capacity_bytes=1000, cache_usage_bytes=500)

    dec1 = engine.decide(
        objects=objs,
        workload=workload,
        system=system,
        min_capacity_bytes=500,
        max_capacity_bytes=2000,
        now=now,
    )
    dec2 = engine.decide(
        objects=objs,
        workload=workload,
        system=system,
        min_capacity_bytes=500,
        max_capacity_bytes=2000,
        now=now,
    )

    assert dec1 == dec2
    assert dec1.decision_id == dec2.decision_id
    assert dec1.object_scores == dec2.object_scores


def test_input_objects_not_mutated(engine: DecisionEngine, now: datetime) -> None:
    """Engine does not mutate the passed input objects dictionary."""
    objs = {"k1": make_object("k1", access_count=5)}
    workload = make_workload(now)
    system = make_system(now)

    engine.decide(
        objects=objs,
        workload=workload,
        system=system,
        min_capacity_bytes=500,
        max_capacity_bytes=2000,
        now=now,
    )

    assert list(objs.keys()) == ["k1"]
    assert objs["k1"].access_count == 5


def test_refresh_urgencies_in_metadata(engine: DecisionEngine, now: datetime) -> None:
    """Verify decision.metadata contains continuous refresh urgencies for all objects."""
    objs = {
        "k_fresh": make_object("k_fresh", last_accessed=now - timedelta(seconds=10)),
        "k_stale": make_object("k_stale", last_accessed=now - timedelta(seconds=400)),
    }
    workload = make_workload(now)
    system = make_system(now)

    decision = engine.decide(
        objects=objs,
        workload=workload,
        system=system,
        min_capacity_bytes=500,
        max_capacity_bytes=2000,
        now=now,
    )

    assert "refresh_urgencies" in decision.metadata
    urgencies = decision.metadata["refresh_urgencies"]
    assert "k_fresh" in urgencies
    assert "k_stale" in urgencies
    assert 0.0 <= urgencies["k_fresh"] < 0.20
    assert urgencies["k_stale"] >= 0.50
