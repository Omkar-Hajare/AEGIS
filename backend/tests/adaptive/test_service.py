"""Unit tests for AdaptiveService bridge in the Adaptive Cache System.

Verifies:
- Creation of valid Decision from telemetry and cache metadata
- Conversion of CacheObjectMetadata to frozen v1 CacheObject contract
- Conversion of multiple cache objects
- Pass-through of previous-window access counts
- Correct behavior on empty cache
- Delegation to injected DecisionEngine (mock / fake)
- Cache state immutability (no mutations, evictions, or side effects)
- Forwarding of all optional parameters (now, refresh_after_seconds, decision_id, capacity_mode)
- Filtering of orphaned metadata entries consistent with CacheManager.exists()
- Default dependency injection initialization
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

try:
    from backend.adaptive.engine.decision_engine import DecisionEngine
    from backend.adaptive.service import AdaptiveService, metadata_to_cache_object
except ImportError:
    from adaptive.engine.decision_engine import (  # type: ignore[no-redef]
        DecisionEngine,
    )
    from adaptive.service import (  # type: ignore[no-redef]
        AdaptiveService,
        metadata_to_cache_object,
    )

try:
    from cache.in_memory import InMemoryCache
    from cache.manager import CacheManager
    from cache.metadata import CacheObjectMetadata
except ImportError:
    from backend.cache.in_memory import InMemoryCache  # type: ignore[no-redef]
    from backend.cache.manager import CacheManager  # type: ignore[no-redef]
    from backend.cache.metadata import CacheObjectMetadata  # type: ignore[no-redef]

try:
    from telemetry.collector import TelemetryCollector
    from telemetry.state import build_system_state
except ImportError:
    from backend.telemetry.collector import TelemetryCollector  # type: ignore[no-redef]
    from backend.telemetry.state import (  # type: ignore[no-redef]
        build_system_state,
    )
from contracts.schemas import (
    CacheObject,
    CapacityAction,
    Decision,
    SystemState,
    WorkloadState,
)


@pytest.fixture
def now() -> datetime:
    """Fixture providing a fixed timezone-aware reference datetime."""
    return datetime(2026, 9, 5, 12, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
def in_memory_cache_manager() -> CacheManager:
    """Fixture providing an in-memory CacheManager."""
    store = InMemoryCache()
    return CacheManager(store)


@pytest.fixture
def collector(now: datetime) -> TelemetryCollector:
    """Fixture providing a TelemetryCollector with deterministic clock."""
    return TelemetryCollector(time_provider=lambda: now)


def test_metadata_to_cache_object_full(now: datetime) -> None:
    """Verify complete, lossless mapping of CacheObjectMetadata to frozen CacheObject."""
    meta = CacheObjectMetadata(
        key="doc:42",
        size_bytes=2048,
        retrieval_cost_ms=120.5,
        version="v1",
        access_count=15,
        hit_count=10,
        miss_count=5,
        created_at=now,
        last_accessed=now,
        features={"recency": 0.95, "frequency": 0.8},
        metadata={"tag": "article", "author_id": 99},
    )

    obj = metadata_to_cache_object(meta)

    assert isinstance(obj, CacheObject)
    assert obj.key == "doc:42"
    assert obj.size_bytes == 2048
    assert obj.access_count == 15
    assert obj.last_accessed == now
    assert obj.retrieval_cost_ms == 120.5
    assert obj.hit_count == 10
    assert obj.miss_count == 5
    assert obj.created_at == now
    assert obj.features == {"recency": 0.95, "frequency": 0.8}
    assert obj.metadata == {"tag": "article", "author_id": 99}
    assert obj.version == "v1"


def test_metadata_to_cache_object_idempotent(now: datetime) -> None:
    """Verify metadata_to_cache_object returns an existing CacheObject untouched."""
    original = CacheObject(
        key="already_contract",
        size_bytes=512,
        access_count=3,
        last_accessed=now,
        retrieval_cost_ms=15.0,
    )
    result = metadata_to_cache_object(original)
    assert result is original


def test_service_creates_valid_decision_from_telemetry_and_cache(
    now: datetime,
) -> None:
    """Verify AdaptiveService generates a valid Decision using real components."""
    store = InMemoryCache()
    cache_mgr = CacheManager(store)
    cache_mgr.set("item:100", {"name": "Widget", "price": 19.99})
    cache_mgr.create_metadata(
        key="item:100",
        size_bytes=300,
        retrieval_cost_ms=40.0,
    )

    collector = TelemetryCollector(time_provider=lambda: now)
    collector.record_request()
    collector.record_cache_hit()
    collector.record_backend_call(40.0)

    service = AdaptiveService(
        cache_manager=cache_mgr,
        telemetry_collector=collector,
    )

    decision = service.decide(now=now)

    assert isinstance(decision, Decision)
    assert decision.decision_id.startswith("dec-")
    assert decision.timestamp == now
    assert decision.version == "v1"
    assert "item:100" in decision.object_scores
    assert decision.recommended_capacity_bytes > 0
    assert isinstance(decision.capacity_action, CapacityAction)
    assert decision.metadata is not None
    assert "workload_type" in decision.metadata


def test_multiple_cache_objects_converted_correctly(now: datetime) -> None:
    """Verify all valid cache objects are converted and passed to DecisionEngine."""
    store = InMemoryCache()
    cache_mgr = CacheManager(store)

    for i in range(3):
        key = f"key:{i}"
        store.set(key, f"val_{i}")
        cache_mgr.create_metadata(
            key=key,
            size_bytes=100 * (i + 1),
            retrieval_cost_ms=25.0 * (i + 1),
        )

    mock_engine = MagicMock(spec=DecisionEngine)
    dummy_decision = Decision(
        decision_id="dec-mock-1",
        timestamp=now,
        capacity_action=CapacityAction.MAINTAIN,
        recommended_capacity_bytes=1_000_000,
        object_scores={"key:0": 0.5, "key:1": 0.6, "key:2": 0.7},
        eviction_keys=[],
        reason="Mock decision",
    )
    mock_engine.decide.return_value = dummy_decision

    service = AdaptiveService(
        cache_manager=cache_mgr,
        decision_engine=mock_engine,
    )

    decision = service.decide(now=now)

    assert decision is dummy_decision
    assert mock_engine.decide.call_count == 1
    call_kwargs = mock_engine.decide.call_args.kwargs
    passed_objects = call_kwargs["objects"]

    assert len(passed_objects) == 3
    for i in range(3):
        k = f"key:{i}"
        assert k in passed_objects
        obj = passed_objects[k]
        assert isinstance(obj, CacheObject)
        assert obj.key == k
        assert obj.size_bytes == 100 * (i + 1)
        assert obj.retrieval_cost_ms == 25.0 * (i + 1)


def test_previous_access_counts_passed_through(now: datetime) -> None:
    """Verify observation previous_window_access_counts are forwarded to DecisionEngine."""
    collector = TelemetryCollector(time_provider=lambda: now)
    # Simulate populated previous-window counts
    collector._previous_window_access_counts = {"item:A": 25, "item:B": 8}

    mock_engine = MagicMock(spec=DecisionEngine)
    mock_engine.decide.return_value = Decision(
        decision_id="dec-prev-1",
        timestamp=now,
        capacity_action=CapacityAction.MAINTAIN,
        recommended_capacity_bytes=1_000_000,
        object_scores={},
        eviction_keys=[],
        reason="Mock decision",
    )

    service = AdaptiveService(
        telemetry_collector=collector,
        decision_engine=mock_engine,
    )

    service.decide(now=now)

    call_kwargs = mock_engine.decide.call_args.kwargs
    assert call_kwargs["previous_access_counts"] == {"item:A": 25, "item:B": 8}


def test_empty_cache_works(now: datetime) -> None:
    """Verify AdaptiveService handles empty cache state without error."""
    store = InMemoryCache()
    cache_mgr = CacheManager(store)
    service = AdaptiveService(cache_manager=cache_mgr)

    decision = service.decide(now=now)

    assert isinstance(decision, Decision)
    assert decision.eviction_keys == []
    assert decision.object_scores == {}
    assert decision.recommended_capacity_bytes > 0


def test_injected_decision_engine_called(now: datetime) -> None:
    """Verify an injected mock DecisionEngine receives all expected arguments."""
    mock_engine = MagicMock(spec=DecisionEngine)
    expected_decision = Decision(
        decision_id="dec-custom-42",
        timestamp=now,
        capacity_action=CapacityAction.SCALE_UP,
        recommended_capacity_bytes=5_000_000,
        object_scores={"x": 0.99},
        eviction_keys=[],
        reason="Scale up due to load",
    )
    mock_engine.decide.return_value = expected_decision

    service = AdaptiveService(decision_engine=mock_engine)
    result = service.decide(now=now)

    assert result is expected_decision
    assert mock_engine.decide.call_count == 1
    call_kwargs = mock_engine.decide.call_args.kwargs
    assert isinstance(call_kwargs["workload"], WorkloadState)
    assert isinstance(call_kwargs["system"], SystemState)
    assert call_kwargs["min_capacity_bytes"] == 1_000_000
    assert call_kwargs["max_capacity_bytes"] == 10_000_000
    assert call_kwargs["now"] == now


def test_service_does_not_mutate_cache_state(now: datetime) -> None:
    """Verify AdaptiveService does not modify stored items, metadata, or delete keys."""
    store = InMemoryCache()
    cache_mgr = CacheManager(store)

    store.set("immutable_key_1", {"data": "test1"})
    meta1 = cache_mgr.create_metadata(
        key="immutable_key_1",
        size_bytes=150,
        retrieval_cost_ms=30.0,
    )
    meta1.record_hit()
    meta1.record_hit()

    store.set("immutable_key_2", {"data": "test2"})
    meta2 = cache_mgr.create_metadata(
        key="immutable_key_2",
        size_bytes=250,
        retrieval_cost_ms=50.0,
    )

    before_value_1 = store.get("immutable_key_1")
    before_value_2 = store.get("immutable_key_2")
    before_meta1_access_count = meta1.access_count
    before_meta1_hit_count = meta1.hit_count
    before_meta2_access_count = meta2.access_count
    all_keys_before = set(cache_mgr.get_all_metadata().keys())

    service = AdaptiveService(cache_manager=cache_mgr)
    decision = service.decide(now=now)

    assert isinstance(decision, Decision)

    # Values in store unchanged
    assert store.get("immutable_key_1") == before_value_1
    assert store.get("immutable_key_2") == before_value_2

    # Metadata access counts and stats unchanged
    after_meta1 = cache_mgr.get_metadata("immutable_key_1")
    after_meta2 = cache_mgr.get_metadata("immutable_key_2")
    assert after_meta1 is not None and after_meta2 is not None
    assert after_meta1.access_count == before_meta1_access_count
    assert after_meta1.hit_count == before_meta1_hit_count
    assert after_meta2.access_count == before_meta2_access_count
    assert set(cache_mgr.get_all_metadata().keys()) == all_keys_before


def test_optional_parameters_forwarded_correctly(now: datetime) -> None:
    """Verify now, refresh_after_seconds, decision_id, capacity_mode forwarded."""
    mock_engine = MagicMock(spec=DecisionEngine)
    mock_engine.decide.return_value = Decision(
        decision_id="custom-dec-id",
        timestamp=now,
        capacity_action=CapacityAction.MAINTAIN,
        recommended_capacity_bytes=8_000_000,
        object_scores={},
        eviction_keys=[],
        reason="Custom reason",
    )

    service = AdaptiveService(decision_engine=mock_engine)

    custom_now = datetime(2026, 9, 5, 18, 45, 0, tzinfo=timezone.utc)
    service.decide(
        now=custom_now,
        min_capacity_bytes=500_000,
        max_capacity_bytes=8_000_000,
        refresh_after_seconds=120.0,
        decision_id="custom-dec-id",
        capacity_mode="continuous",
    )

    assert mock_engine.decide.call_count == 1
    call_kwargs = mock_engine.decide.call_args.kwargs
    assert call_kwargs["now"] == custom_now
    assert call_kwargs["min_capacity_bytes"] == 500_000
    assert call_kwargs["max_capacity_bytes"] == 8_000_000
    assert call_kwargs["refresh_after_seconds"] == 120.0
    assert call_kwargs["decision_id"] == "custom-dec-id"
    assert call_kwargs["capacity_mode"] == "continuous"


def test_existing_cache_entries_filtered_consistently(now: datetime) -> None:
    """Verify orphaned metadata (where store.exists is False) is filtered out."""
    store = InMemoryCache()
    cache_mgr = CacheManager(store)

    # 1. Entry exists in both store and metadata
    store.set("active_key", "stored_value")
    cache_mgr.create_metadata(key="active_key", size_bytes=100)

    # 2. Orphaned entry: metadata created, but key never saved into store
    cache_mgr.create_metadata(key="ghost_key", size_bytes=200)

    assert cache_mgr.exists("active_key") is True
    assert cache_mgr.exists("ghost_key") is False

    mock_engine = MagicMock(spec=DecisionEngine)
    mock_engine.decide.return_value = Decision(
        decision_id="dec-filter-1",
        timestamp=now,
        capacity_action=CapacityAction.MAINTAIN,
        recommended_capacity_bytes=1_000_000,
        object_scores={},
        eviction_keys=[],
        reason="Filter test",
    )

    service = AdaptiveService(
        cache_manager=cache_mgr,
        decision_engine=mock_engine,
    )
    service.decide(now=now)

    passed_objects = mock_engine.decide.call_args.kwargs["objects"]
    assert "active_key" in passed_objects
    assert "ghost_key" not in passed_objects
    assert len(passed_objects) == 1

    passed_system: SystemState = mock_engine.decide.call_args.kwargs["system"]
    assert passed_system.object_count == 1
    assert passed_system.cache_usage_bytes == 100


def test_default_dependency_injection_instantiation() -> None:
    """Verify AdaptiveService instantiates with sensible defaults when no args given."""
    service = AdaptiveService()
    assert isinstance(service.cache_manager, CacheManager)
    assert isinstance(service.telemetry_collector, TelemetryCollector)
    assert isinstance(service.decision_engine, DecisionEngine)

    decision = service.decide()
    assert isinstance(decision, Decision)
    assert decision.decision_id.startswith("dec-")


def test_workload_and_system_state_conversion(now: datetime) -> None:
    """Verify telemetry state dataclasses convert strictly into frozen v1 contracts."""
    collector = TelemetryCollector(time_provider=lambda: now)
    collector.record_request()
    collector.record_request()
    collector.record_cache_hit()
    collector.record_cache_miss()
    collector.record_backend_call(50.0)

    store = InMemoryCache()
    cache_mgr = CacheManager(store)
    store.set("k1", "v1")
    cache_mgr.create_metadata("k1", size_bytes=350)

    mock_engine = MagicMock(spec=DecisionEngine)
    mock_engine.decide.return_value = Decision(
        decision_id="dec-state-check",
        timestamp=now,
        capacity_action=CapacityAction.MAINTAIN,
        recommended_capacity_bytes=1_000_000,
        object_scores={},
        eviction_keys=[],
        reason="State check",
    )

    service = AdaptiveService(
        cache_manager=cache_mgr,
        telemetry_collector=collector,
        decision_engine=mock_engine,
    )
    service.decide(now=now)

    call_kwargs = mock_engine.decide.call_args.kwargs
    workload: WorkloadState = call_kwargs["workload"]
    system: SystemState = call_kwargs["system"]

    assert isinstance(workload, WorkloadState)
    assert workload.version == "v1"
    assert workload.hit_rate == 0.5
    assert workload.miss_rate == 0.5
    assert workload.window_seconds > 0.0

    assert isinstance(system, SystemState)
    assert system.version == "v1"
    assert system.object_count == 1
    assert system.cache_usage_bytes == 350
    # cache_capacity_bytes falls back to default_capacity_bytes (10_000_000) at the contract
    # adaptation boundary because the standard CacheManager has no observed capacity (None)
    assert system.cache_capacity_bytes == 10_000_000
    assert system.window_seconds > 0.0


def test_max_capacity_bytes_constraint_distinguished_from_observed_capacity(
    now: datetime,
) -> None:
    """Verify max_capacity_bytes is forwarded to DecisionEngine as a constraint

    and NOT incorrectly treated as observed runtime cache capacity in build_system_state().
    """
    store = InMemoryCache()
    cache_mgr = CacheManager(store)
    store.set("test_key", "value")
    cache_mgr.create_metadata(key="test_key", size_bytes=500)

    mock_engine = MagicMock(spec=DecisionEngine)
    mock_engine.decide.return_value = Decision(
        decision_id="dec-test-constraint",
        timestamp=now,
        capacity_action=CapacityAction.MAINTAIN,
        recommended_capacity_bytes=1_000_000,
        object_scores={},
        eviction_keys=[],
        reason="Constraint test",
    )

    # 1. Standard CacheManager does not expose an actual capacity.
    # Verify build_system_state receives cache_capacity_bytes=None (NOT max_capacity_bytes).
    with patch(
        "backend.adaptive.service.build_system_state",
        wraps=build_system_state,
    ) as mock_build_sys:
        service = AdaptiveService(
            cache_manager=cache_mgr,
            decision_engine=mock_engine,
        )
        service.decide(
            now=now,
            min_capacity_bytes=200_000,
            max_capacity_bytes=7_500_000,
        )

        assert mock_build_sys.call_count == 1
        build_sys_kwargs = mock_build_sys.call_args.kwargs
        assert build_sys_kwargs["cache_capacity_bytes"] is None

        # max_capacity_bytes is preserved and forwarded as DecisionEngine constraint
        assert mock_engine.decide.call_count == 1
        decide_kwargs = mock_engine.decide.call_args.kwargs
        assert decide_kwargs["max_capacity_bytes"] == 7_500_000
        assert decide_kwargs["min_capacity_bytes"] == 200_000

        # SystemState uses max_capacity_bytes strictly as boundary fallback
        system_arg: SystemState = decide_kwargs["system"]
        assert system_arg.cache_capacity_bytes == 7_500_000

    # 2. When CacheManager DOES expose an observed runtime capacity
    cache_mgr.capacity_bytes = 3_000_000  # type: ignore[attr-defined]
    mock_engine.reset_mock()

    with patch(
        "backend.adaptive.service.build_system_state",
        wraps=build_system_state,
    ) as mock_build_sys_with_cap:
        service = AdaptiveService(
            cache_manager=cache_mgr,
            decision_engine=mock_engine,
        )
        service.decide(
            now=now,
            min_capacity_bytes=200_000,
            max_capacity_bytes=7_500_000,
        )

        # build_system_state receives observed capacity (3_000_000), NOT max_capacity_bytes
        assert mock_build_sys_with_cap.call_count == 1
        build_sys_kwargs = mock_build_sys_with_cap.call_args.kwargs
        assert build_sys_kwargs["cache_capacity_bytes"] == 3_000_000

        decide_kwargs = mock_engine.decide.call_args.kwargs
        # max_capacity_bytes is still the decision constraint (7_500_000)
        assert decide_kwargs["max_capacity_bytes"] == 7_500_000
        # SystemState reflects the observed capacity (3_000_000), NOT max_capacity_bytes
        system_arg = decide_kwargs["system"]
        assert system_arg.cache_capacity_bytes == 3_000_000
