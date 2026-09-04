"""Unit tests for synthetic workload scenarios in the Adaptive Cache System.

Tests configuration validation, determinism, distribution patterns, phase transitions,
profiles, telemetry compatibility, and edge cases for steady, spike, and
popularity shift workloads.
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from backend.workload.generator import (
    ScenarioGenerator,
    generate_popularity_shift_scenario,
    generate_spike_scenario,
    generate_steady_scenario,
    generate_workload,
)
from backend.workload.scenario import (
    PRODUCT_CATALOG_PROFILE,
    RECOMMENDATIONS_PROFILE,
    ScenarioConfig,
    ScenarioEvent,
)
from contracts.schemas.cache import CacheObject
from contracts.schemas.enums import WorkloadType
from contracts.schemas.workload import WorkloadState


@pytest.fixture
def now() -> datetime:
    """Fixed reference timezone-aware datetime."""
    return datetime(2026, 9, 4, 12, 0, 0, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# Configuration Validation Tests
# ---------------------------------------------------------------------------


def test_scenario_config_valid_defaults() -> None:
    """Default ScenarioConfig is valid and populates sensible defaults."""
    cfg = ScenarioConfig()
    assert cfg.object_count == 100
    assert cfg.request_count == 1000
    assert cfg.request_rate == 100.0
    assert cfg.duration_seconds == 60.0
    assert cfg.window_seconds == 60.0
    assert cfg.hot_set_size == 10
    assert cfg.spike_multiplier == 3.0
    assert cfg.profile == PRODUCT_CATALOG_PROFILE
    assert cfg.start_time.tzinfo is not None


def test_scenario_config_positive_counts_required() -> None:
    """Zero or negative object_count and request_count raise ValidationError."""
    with pytest.raises(ValidationError):
        ScenarioConfig(object_count=0)

    with pytest.raises(ValidationError):
        ScenarioConfig(request_count=-10)


def test_scenario_config_hot_set_size_cannot_exceed_object_count() -> None:
    """hot_set_size > object_count raises ValueError."""
    with pytest.raises(ValidationError, match="cannot exceed object_count"):
        ScenarioConfig(object_count=10, hot_set_size=20)


def test_scenario_config_rejects_negative_or_zero_spike_multiplier() -> None:
    """Non-positive spike multiplier raises ValidationError."""
    with pytest.raises(ValidationError):
        ScenarioConfig(spike_multiplier=0.0)

    with pytest.raises(ValidationError):
        ScenarioConfig(spike_multiplier=-2.0)


def test_scenario_config_rejects_bool_for_numeric_fields() -> None:
    """Boolean values are rejected where numeric values are expected."""
    with pytest.raises((ValidationError, TypeError)):
        ScenarioConfig(seed=True)  # type: ignore[arg-type]

    with pytest.raises((ValidationError, TypeError)):
        ScenarioConfig(object_count=False)  # type: ignore[arg-type]

    with pytest.raises((ValidationError, TypeError)):
        ScenarioConfig(request_rate=True)  # type: ignore[arg-type]

    with pytest.raises((ValidationError, TypeError)):
        ScenarioConfig(hot_set_size=False)  # type: ignore[arg-type]


def test_scenario_config_rejects_naive_start_time() -> None:
    """Naive datetime for start_time raises ValueError."""
    naive_dt = datetime(2026, 9, 4, 12, 0, 0)  # noqa: DTZ001
    with pytest.raises(ValidationError, match="naive datetime"):
        ScenarioConfig(start_time=naive_dt)


def test_scenario_config_profile_string_resolution() -> None:
    """String profile names are resolved automatically to WorkloadProfile."""
    cfg_prod = ScenarioConfig(profile="product_catalog")
    assert cfg_prod.profile == PRODUCT_CATALOG_PROFILE

    cfg_rec = ScenarioConfig(profile="recommendations")
    assert cfg_rec.profile == RECOMMENDATIONS_PROFILE


def test_scenario_config_unknown_profile_raises_error() -> None:
    """Unknown profile name raises ValueError."""
    with pytest.raises(ValidationError, match="Unknown workload profile"):
        ScenarioConfig(profile="non_existent_profile")


def test_scenario_config_window_seconds_alias() -> None:
    """Specifying window_seconds or duration initializes duration_seconds."""
    cfg1 = ScenarioConfig.model_validate({"duration": 90.0})
    assert cfg1.duration_seconds == 90.0
    assert cfg1.window_seconds == 90.0

    cfg2 = ScenarioConfig.model_validate({"window_seconds": 120.0})
    assert cfg2.duration_seconds == 120.0
    assert cfg2.window_seconds == 120.0


# ---------------------------------------------------------------------------
# ScenarioEvent Validation Tests
# ---------------------------------------------------------------------------


def test_scenario_event_immutability(now: datetime) -> None:
    """ScenarioEvent is frozen and cannot be mutated."""
    event = ScenarioEvent(
        timestamp=now,
        key="test_key",
        workload_type=WorkloadType.READ_HEAVY,
        backend_latency_ms=5.0,
        object_size_bytes=2048,
        retrieval_cost_ms=5.0,
        request_rate=100.0,
    )
    with pytest.raises(ValidationError):
        event.key = "modified_key"  # type: ignore[misc]


def test_scenario_event_rejects_naive_timestamp() -> None:
    """ScenarioEvent rejects naive datetime."""
    naive_dt = datetime(2026, 9, 4, 12, 0, 0)  # noqa: DTZ001
    with pytest.raises(ValidationError, match="naive datetime"):
        ScenarioEvent(
            timestamp=naive_dt,
            key="k",
            workload_type=WorkloadType.READ_HEAVY,
            backend_latency_ms=5.0,
            object_size_bytes=100,
            retrieval_cost_ms=5.0,
            request_rate=100.0,
        )


def test_scenario_event_rejects_negative_numerics(now: datetime) -> None:
    """ScenarioEvent rejects negative latencies, sizes, and rates."""
    with pytest.raises(ValidationError):
        ScenarioEvent(
            timestamp=now,
            key="k",
            workload_type=WorkloadType.READ_HEAVY,
            backend_latency_ms=-1.0,
            object_size_bytes=100,
            retrieval_cost_ms=5.0,
            request_rate=100.0,
        )


def test_scenario_event_metadata_defensive_copy(now: datetime) -> None:
    """Mutating caller's metadata dictionary does not affect the ScenarioEvent."""
    meta = {"phase": "test"}
    event = ScenarioEvent(
        timestamp=now,
        key="k",
        workload_type=WorkloadType.READ_HEAVY,
        backend_latency_ms=5.0,
        object_size_bytes=100,
        retrieval_cost_ms=5.0,
        request_rate=100.0,
        metadata=meta,
    )
    meta["phase"] = "mutated"
    assert event.metadata is not None
    assert event.metadata["phase"] == "test"


# ---------------------------------------------------------------------------
# Determinism Tests
# ---------------------------------------------------------------------------


def test_determinism_with_identical_seed() -> None:
    """Same configuration with the same seed produces the exact same event stream."""
    cfg1 = ScenarioConfig(seed=123, scenario_type="steady", request_count=200)
    cfg2 = ScenarioConfig(seed=123, scenario_type="steady", request_count=200)

    events1 = ScenarioGenerator(cfg1).generate()
    events2 = ScenarioGenerator(cfg2).generate()

    assert len(events1) == len(events2) == 200
    assert events1 == events2


def test_different_seeds_produce_different_sequences() -> None:
    """Different seeds generate different request sequences."""
    cfg1 = ScenarioConfig(seed=42, scenario_type="steady", request_count=100)
    cfg2 = ScenarioConfig(seed=999, scenario_type="steady", request_count=100)

    events1 = ScenarioGenerator(cfg1).generate()
    events2 = ScenarioGenerator(cfg2).generate()

    keys1 = [e.key for e in events1]
    keys2 = [e.key for e in events2]

    assert keys1 != keys2


# ---------------------------------------------------------------------------
# Steady Scenario Tests
# ---------------------------------------------------------------------------


def test_steady_scenario_stable_request_rate(now: datetime) -> None:
    """Steady scenario maintains constant arrival rate and regular intervals."""
    rate = 250.0
    events = generate_steady_scenario(
        seed=42, request_count=50, request_rate=rate, start_time=now
    )

    assert len(events) == 50
    expected_interval = timedelta(seconds=1.0 / rate)

    for i, event in enumerate(events):
        assert event.request_rate == rate
        assert event.metadata is not None
        assert event.metadata["phase"] == "steady"
        if i > 0:
            diff = event.timestamp - events[i - 1].timestamp
            assert abs(diff.total_seconds() - expected_interval.total_seconds()) < 1e-6


def test_steady_scenario_stable_popularity_distribution() -> None:
    """Steady scenario object frequencies remain stable between halves."""
    events = generate_steady_scenario(
        seed=42, object_count=50, request_count=1000, hot_set_size=5
    )

    half = len(events) // 2
    first_half_counts = Counter(e.key for e in events[:half])
    second_half_counts = Counter(e.key for e in events[half:])

    # Top accessed keys in the first half should also be dominant in second half
    top_first = {k for k, _ in first_half_counts.most_common(5)}
    top_second = {k for k, _ in second_half_counts.most_common(5)}

    # Strong overlap between the two halves
    overlap = len(top_first.intersection(top_second))
    assert overlap >= 4


# ---------------------------------------------------------------------------
# Traffic Spike Scenario Tests
# ---------------------------------------------------------------------------


def test_spike_scenario_contains_baseline_spike_recovery_phases() -> None:
    """Spike scenario contains baseline, spike, and recovery phases in order."""
    events = generate_spike_scenario(seed=42, request_count=300, spike_multiplier=3.0)

    phases = [e.metadata["phase"] for e in events if e.metadata]
    assert "baseline" in phases
    assert "spike" in phases
    assert "recovery" in phases

    # Verify chronological ordering of phases
    first_spike_idx = phases.index("spike")
    last_spike_idx = len(phases) - 1 - phases[::-1].index("spike")
    first_recovery_idx = phases.index("recovery")

    assert first_spike_idx > 0
    assert first_recovery_idx > last_spike_idx


def test_spike_concentrates_requests_on_hot_objects() -> None:
    """Spike phase concentrates requests heavily on the hot subset."""
    hot_set_size = 5
    events = generate_spike_scenario(
        seed=42,
        object_count=50,
        request_count=500,
        hot_set_size=hot_set_size,
        spike_multiplier=4.0,
    )

    hot_keys = {f"obj_{i}" for i in range(hot_set_size)}

    baseline_events = [
        e for e in events if e.metadata and e.metadata["phase"] == "baseline"
    ]
    spike_events = [e for e in events if e.metadata and e.metadata["phase"] == "spike"]

    base_hot_hits = sum(1 for e in baseline_events if e.key in hot_keys)
    spike_hot_hits = sum(1 for e in spike_events if e.key in hot_keys)

    base_hot_ratio = base_hot_hits / len(baseline_events)
    spike_hot_ratio = spike_hot_hits / len(spike_events)

    # Spike hot ratio must be significantly higher than baseline
    assert spike_hot_ratio > 0.85
    assert spike_hot_ratio > base_hot_ratio


def test_spike_is_measurably_stronger_than_baseline() -> None:
    """Request rate during spike equals baseline rate multiplied by spike multiplier."""
    base_rate = 50.0
    multiplier = 3.5
    events = generate_spike_scenario(
        seed=42,
        request_count=300,
        request_rate=base_rate,
        spike_multiplier=multiplier,
    )

    for event in events:
        assert event.metadata is not None
        if event.metadata["phase"] == "baseline":
            assert event.request_rate == base_rate
        elif event.metadata["phase"] == "spike":
            assert event.request_rate == base_rate * multiplier
        elif event.metadata["phase"] == "recovery":
            assert event.request_rate == base_rate


# ---------------------------------------------------------------------------
# Popularity Shift Scenario Tests
# ---------------------------------------------------------------------------


def test_popularity_shift_different_initial_and_final_hot_sets() -> None:
    """Initial distribution favors a different hot subset than final distribution."""
    events = generate_popularity_shift_scenario(
        seed=42, object_count=50, request_count=600, hot_set_size=5
    )

    initial_events = [
        e
        for e in events
        if e.metadata and e.metadata["phase"] == "initial_distribution"
    ]
    final_events = [
        e for e in events if e.metadata and e.metadata["phase"] == "final_distribution"
    ]

    init_top = {k for k, _ in Counter(e.key for e in initial_events).most_common(5)}
    final_top = {k for k, _ in Counter(e.key for e in final_events).most_common(5)}

    # Initial and final dominant keys must be completely disjoint
    assert len(init_top.intersection(final_top)) == 0


def test_popularity_shift_changes_progressively() -> None:
    """Shift progress monotonically advances from 0.0 to 1.0 across transition."""
    events = generate_popularity_shift_scenario(
        seed=42, object_count=50, request_count=300, hot_set_size=5
    )

    progress_values = [
        e.metadata["shift_progress"]
        for e in events
        if e.metadata and "shift_progress" in e.metadata
    ]

    assert progress_values[0] == 0.0
    assert progress_values[-1] == 1.0

    # Ensure progress values never decrease
    for i in range(1, len(progress_values)):
        assert progress_values[i] >= progress_values[i - 1]


# ---------------------------------------------------------------------------
# Workload Profile Tests
# ---------------------------------------------------------------------------


def test_product_catalog_profile_defaults() -> None:
    """Product catalog profile specifies approximately 5 ms latency and 2 KB payload."""
    p = PRODUCT_CATALOG_PROFILE
    assert p.workload_type == WorkloadType.READ_HEAVY
    assert p.default_backend_latency_ms == 5.0
    assert p.default_object_size_bytes == 2048
    assert p.default_retrieval_cost_ms == 5.0


def test_recommendations_profile_defaults() -> None:
    """Recommendations profile specifies approximately 200 ms and 25 KB."""
    p = RECOMMENDATIONS_PROFILE
    assert p.workload_type == WorkloadType.COMPUTE_HEAVY
    assert p.default_backend_latency_ms == 200.0
    assert p.default_object_size_bytes == 25600
    assert p.default_retrieval_cost_ms == 200.0


def test_generator_inherits_profile_attributes() -> None:
    """Generated events inherit profile workload_type, size, and latency."""
    events = generate_steady_scenario(
        seed=42, request_count=10, profile=RECOMMENDATIONS_PROFILE
    )

    for event in events:
        assert event.workload_type == WorkloadType.COMPUTE_HEAVY
        assert event.backend_latency_ms == 200.0
        assert event.object_size_bytes == 25600
        assert event.retrieval_cost_ms == 200.0


# ---------------------------------------------------------------------------
# Telemetry & Benchmark Compatibility Tests
# ---------------------------------------------------------------------------


def test_timestamps_are_timezone_aware_and_ordered(now: datetime) -> None:
    """All generated events have timezone-aware timestamps in ascending order."""
    events = generate_spike_scenario(seed=42, request_count=100, start_time=now)

    for i, event in enumerate(events):
        assert event.timestamp.tzinfo is not None
        if i > 0:
            assert event.timestamp >= events[i - 1].timestamp


def test_generated_numeric_attributes_are_non_negative() -> None:
    """Object size, retrieval cost, latency, and request rate are non-negative."""
    events = generate_steady_scenario(seed=42, request_count=100)

    for event in events:
        assert event.object_size_bytes >= 0
        assert event.retrieval_cost_ms >= 0.0
        assert event.backend_latency_ms >= 0.0
        assert event.request_rate >= 0.0


def test_benchmark_runner_compatibility_and_reuse() -> None:
    """The exact same sequence can construct CacheObjects and WorkloadState."""
    events = generate_steady_scenario(seed=42, request_count=50)

    # Simulate future benchmark consumption: build cache objects & workload state
    seen_objects: dict[str, CacheObject] = {}
    for event in events:
        if event.key not in seen_objects:
            seen_objects[event.key] = CacheObject(
                key=event.key,
                size_bytes=event.object_size_bytes,
                access_count=1,
                last_accessed=event.timestamp,
                retrieval_cost_ms=event.retrieval_cost_ms,
            )
        else:
            obj = seen_objects[event.key]
            seen_objects[event.key] = obj.model_copy(
                update={
                    "access_count": obj.access_count + 1,
                    "last_accessed": event.timestamp,
                }
            )

    assert len(seen_objects) > 0

    # Build WorkloadState from latest event
    latest = events[-1]
    workload_state = WorkloadState(
        request_rate=latest.request_rate,
        hit_rate=0.8,
        miss_rate=0.2,
        backend_latency_ms=latest.backend_latency_ms,
        workload_type=latest.workload_type,
        timestamp=latest.timestamp,
        window_seconds=60.0,
    )
    assert workload_state.request_rate == latest.request_rate
    assert workload_state.workload_type == latest.workload_type


# ---------------------------------------------------------------------------
# Edge Cases
# ---------------------------------------------------------------------------


def test_single_object_and_request() -> None:
    """Minimum configuration with 1 object and 1 request executes without error."""
    for stype in ("steady", "spike", "popularity_shift"):
        cfg = ScenarioConfig(
            scenario_type=stype,
            object_count=1,
            request_count=1,
            hot_set_size=1,
        )
        events = ScenarioGenerator(cfg).generate()
        assert len(events) == 1
        assert events[0].key == "obj_0"


def test_generator_callable_interface() -> None:
    """ScenarioGenerator instance is directly callable."""
    generator = ScenarioGenerator.steady(request_count=5)
    events = generator()
    assert len(events) == 5


def test_unknown_scenario_type_raises_value_error() -> None:
    """Configuring an invalid scenario_type raises ValueError on generate()."""
    cfg = ScenarioConfig(scenario_type="invalid_type")  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="Unknown scenario_type"):
        ScenarioGenerator(cfg).generate()


def test_generate_workload_convenience_function() -> None:
    """generate_workload dispatches properly using passed config."""
    cfg = ScenarioConfig(request_count=20)
    events = generate_workload(cfg)
    assert len(events) == 20
