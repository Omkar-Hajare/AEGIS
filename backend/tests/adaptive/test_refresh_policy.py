"""Unit tests for RefreshPolicy in the Adaptive Cache System.

Tests staleness calculation, age clamping, workload-specific threshold adaptations,
invalid argument validation, immutability, determinism, and timezone handling.
"""

from datetime import datetime, timedelta, timezone

import pytest

from backend.adaptive.refresh.policy import (
    DEFAULT_AGGRESSIVE_MULTIPLIER,
    DEFAULT_REFRESH_AFTER_SECONDS,
    RefreshPolicy,
    RefreshPolicyValidationError,
)
from contracts.schemas.cache import CacheObject
from contracts.schemas.enums import WorkloadType


@pytest.fixture
def policy() -> RefreshPolicy:
    """Fixture providing a fresh RefreshPolicy instance."""
    return RefreshPolicy()


@pytest.fixture
def now() -> datetime:
    """Fixture providing a fixed timezone-aware reference datetime."""
    return datetime(2026, 9, 4, 12, 0, 0, tzinfo=timezone.utc)


def make_obj(
    key: str = "test_key",
    last_accessed: datetime | None = None,
    size_bytes: int = 1000,
    retrieval_cost_ms: float = 10.0,
    access_count: int = 1,
) -> CacheObject:
    """Helper to create a CacheObject with key matching."""
    ts = last_accessed or datetime(2026, 9, 4, 12, 0, 0, tzinfo=timezone.utc)
    return CacheObject(
        key=key,
        size_bytes=size_bytes,
        access_count=access_count,
        last_accessed=ts,
        retrieval_cost_ms=retrieval_cost_ms,
    )


# ---------------------------------------------------------------------------
# Core Staleness & Threshold Tests
# ---------------------------------------------------------------------------


def test_object_younger_than_threshold_returns_false(
    policy: RefreshPolicy, now: datetime
) -> None:
    """Object accessed 100s ago is younger than 300s threshold -> False."""
    obj = make_obj(last_accessed=now - timedelta(seconds=100))
    assert not policy.should_refresh(obj, now=now, refresh_after_seconds=300.0)


def test_object_exactly_at_threshold_returns_true(
    policy: RefreshPolicy, now: datetime
) -> None:
    """Object accessed exactly 300s ago equals threshold -> True."""
    obj = make_obj(last_accessed=now - timedelta(seconds=300))
    assert policy.should_refresh(obj, now=now, refresh_after_seconds=300.0)


def test_object_older_than_threshold_returns_true(
    policy: RefreshPolicy, now: datetime
) -> None:
    """Object accessed 500s ago exceeds 300s threshold -> True."""
    obj = make_obj(last_accessed=now - timedelta(seconds=500))
    assert policy.should_refresh(obj, now=now, refresh_after_seconds=300.0)


def test_zero_age_returns_false(policy: RefreshPolicy, now: datetime) -> None:
    """Object accessed right now (age = 0s) -> False."""
    obj = make_obj(last_accessed=now)
    assert not policy.should_refresh(obj, now=now, refresh_after_seconds=300.0)


def test_future_last_accessed_is_clamped_to_zero_age(
    policy: RefreshPolicy, now: datetime
) -> None:
    """Object with future timestamp is clamped to age 0 and returns False."""
    future_time = now + timedelta(hours=1)
    obj = make_obj(last_accessed=future_time)
    assert not policy.should_refresh(obj, now=now, refresh_after_seconds=300.0)


# ---------------------------------------------------------------------------
# Workload-Specific Threshold Adaptation Tests
# ---------------------------------------------------------------------------


def test_steady_workload_uses_base_threshold(
    policy: RefreshPolicy, now: datetime
) -> None:
    """STEADY workload preserves 100% of base threshold."""
    # Age 250s with base 300s -> False under STEADY
    obj = make_obj(last_accessed=now - timedelta(seconds=250))
    assert not policy.should_refresh(
        obj, now=now, workload_type=WorkloadType.STEADY, refresh_after_seconds=300.0
    )
    assert policy.refresh_threshold(WorkloadType.STEADY, 300.0) == 300.0


def test_read_heavy_workload_uses_base_threshold(
    policy: RefreshPolicy, now: datetime
) -> None:
    """READ_HEAVY workload preserves 100% of base threshold."""
    obj = make_obj(last_accessed=now - timedelta(seconds=250))
    assert not policy.should_refresh(
        obj,
        now=now,
        workload_type=WorkloadType.READ_HEAVY,
        refresh_after_seconds=300.0,
    )
    assert policy.refresh_threshold(WorkloadType.READ_HEAVY, 300.0) == 300.0


def test_compute_heavy_workload_uses_base_threshold(
    policy: RefreshPolicy, now: datetime
) -> None:
    """COMPUTE_HEAVY preserves base threshold because regeneration is costly."""
    obj = make_obj(last_accessed=now - timedelta(seconds=250))
    assert not policy.should_refresh(
        obj,
        now=now,
        workload_type=WorkloadType.COMPUTE_HEAVY,
        refresh_after_seconds=300.0,
    )
    assert policy.refresh_threshold(WorkloadType.COMPUTE_HEAVY, 300.0) == 300.0


def test_spike_workload_uses_fifty_percent_threshold(
    policy: RefreshPolicy, now: datetime
) -> None:
    """SPIKE uses aggressive 50% threshold (e.g. 150s instead of 300s)."""
    # Age 160s: > 150s (SPIKE threshold) -> True, but < 300s (base threshold)
    obj = make_obj(last_accessed=now - timedelta(seconds=160))
    assert policy.should_refresh(
        obj, now=now, workload_type=WorkloadType.SPIKE, refresh_after_seconds=300.0
    )
    assert policy.refresh_threshold(WorkloadType.SPIKE, 300.0) == 150.0

    # Age 140s: < 150s (SPIKE threshold) -> False
    fresh_obj = make_obj(last_accessed=now - timedelta(seconds=140))
    assert not policy.should_refresh(
        fresh_obj,
        now=now,
        workload_type=WorkloadType.SPIKE,
        refresh_after_seconds=300.0,
    )


def test_popularity_shift_uses_fifty_percent_threshold(
    policy: RefreshPolicy, now: datetime
) -> None:
    """POPULARITY_SHIFT uses aggressive 50% threshold."""
    obj = make_obj(last_accessed=now - timedelta(seconds=160))
    assert policy.should_refresh(
        obj,
        now=now,
        workload_type=WorkloadType.POPULARITY_SHIFT,
        refresh_after_seconds=300.0,
    )
    assert policy.refresh_threshold(WorkloadType.POPULARITY_SHIFT, 300.0) == 150.0


def test_none_workload_uses_base_threshold(
    policy: RefreshPolicy, now: datetime
) -> None:
    """workload_type=None preserves 100% of base threshold."""
    obj = make_obj(last_accessed=now - timedelta(seconds=250))
    assert not policy.should_refresh(
        obj, now=now, workload_type=None, refresh_after_seconds=300.0
    )
    assert policy.refresh_threshold(None, 300.0) == 300.0


def test_string_workload_type_is_accepted(policy: RefreshPolicy, now: datetime) -> None:
    """String representation of WorkloadType is parsed and accepted."""
    obj = make_obj(last_accessed=now - timedelta(seconds=160))
    assert policy.should_refresh(
        obj, now=now, workload_type="SPIKE", refresh_after_seconds=300.0
    )
    assert policy.refresh_threshold("STEADY", 300.0) == 300.0


# ---------------------------------------------------------------------------
# Custom Threshold & Edge Cases
# ---------------------------------------------------------------------------


def test_custom_threshold(policy: RefreshPolicy, now: datetime) -> None:
    """Custom refresh_after_seconds is honored directly."""
    obj = make_obj(last_accessed=now - timedelta(seconds=50))
    assert not policy.should_refresh(obj, now=now, refresh_after_seconds=60.0)
    assert policy.should_refresh(obj, now=now, refresh_after_seconds=40.0)


def test_timezone_aware_comparison_across_different_timezones(
    policy: RefreshPolicy,
) -> None:
    """Different timezone offsets are compared correctly without offset errors."""
    # 12:00 UTC == 17:30 IST (+05:30)
    ist = timezone(timedelta(hours=5, minutes=30))
    last_acc = datetime(2026, 9, 4, 12, 0, 0, tzinfo=timezone.utc)
    now_ist = datetime(2026, 9, 4, 17, 35, 0, tzinfo=ist)  # 5 minutes later

    obj = make_obj(last_accessed=last_acc)
    # Age is 300 seconds -> exactly threshold 300s
    assert policy.should_refresh(obj, now=now_ist, refresh_after_seconds=300.0)


# ---------------------------------------------------------------------------
# Validation & Error Handling Tests
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("invalid_threshold", [0.0, -1.0, -300.0, -0.01])
def test_non_positive_threshold_raises_error(
    policy: RefreshPolicy, now: datetime, invalid_threshold: float
) -> None:
    """refresh_after_seconds <= 0 raises RefreshPolicyValidationError."""
    obj = make_obj(last_accessed=now)
    with pytest.raises(RefreshPolicyValidationError):
        policy.should_refresh(obj, now=now, refresh_after_seconds=invalid_threshold)


@pytest.mark.parametrize("bad_arg", [True, False, "300", [300], None])
def test_bool_or_non_numeric_threshold_raises_error(
    policy: RefreshPolicy, now: datetime, bad_arg: object
) -> None:
    """Boolean or non-numeric threshold raises RefreshPolicyValidationError."""
    obj = make_obj(last_accessed=now)
    with pytest.raises(RefreshPolicyValidationError):
        policy.should_refresh(obj, now=now, refresh_after_seconds=bad_arg)  # type: ignore[arg-type]


@pytest.mark.parametrize("bad_val", [float("inf"), float("-inf"), float("nan")])
def test_non_finite_threshold_raises_error(
    policy: RefreshPolicy, now: datetime, bad_val: float
) -> None:
    """Infinite or NaN threshold raises RefreshPolicyValidationError."""
    obj = make_obj(last_accessed=now)
    with pytest.raises(RefreshPolicyValidationError):
        policy.should_refresh(obj, now=now, refresh_after_seconds=bad_val)


def test_naive_datetime_for_now_raises_error(
    policy: RefreshPolicy,
) -> None:
    """Naive datetime for now raises RefreshPolicyValidationError."""
    naive_now = datetime(2026, 9, 4, 12, 0, 0)  # noqa: DTZ001
    obj = make_obj()
    with pytest.raises(RefreshPolicyValidationError, match="timezone-aware"):
        policy.should_refresh(obj, now=naive_now)


def test_non_datetime_now_raises_error(policy: RefreshPolicy) -> None:
    """Non-datetime now raises RefreshPolicyValidationError."""
    obj = make_obj()
    with pytest.raises(RefreshPolicyValidationError):
        policy.should_refresh(obj, now="2026-09-04T12:00:00Z")  # type: ignore[arg-type]


def test_invalid_workload_type_raises_error(
    policy: RefreshPolicy, now: datetime
) -> None:
    """Unsupported workload_type raises RefreshPolicyValidationError."""
    obj = make_obj(last_accessed=now)
    with pytest.raises(RefreshPolicyValidationError, match="workload_type"):
        policy.should_refresh(obj, now=now, workload_type="INVALID_WORKLOAD")  # type: ignore[arg-type]


def test_non_cache_object_raises_error(policy: RefreshPolicy, now: datetime) -> None:
    """Non-CacheObject argument raises RefreshPolicyValidationError."""
    with pytest.raises(RefreshPolicyValidationError):
        policy.should_refresh("not_an_obj", now=now)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Immutability, Determinism, and Invariants
# ---------------------------------------------------------------------------


def test_input_object_is_not_mutated(policy: RefreshPolicy, now: datetime) -> None:
    """Target CacheObject is never modified by should_refresh."""
    obj = make_obj(last_accessed=now - timedelta(seconds=200))
    dump_before = obj.model_dump()

    policy.should_refresh(obj, now=now, workload_type=WorkloadType.SPIKE)

    assert obj.model_dump() == dump_before


def test_determinism_same_input_produces_identical_decision(
    policy: RefreshPolicy, now: datetime
) -> None:
    """Identical inputs produce identical boolean outcomes."""
    obj = make_obj(last_accessed=now - timedelta(seconds=200))
    r1 = policy.should_refresh(obj, now=now, workload_type=WorkloadType.SPIKE)
    r2 = policy.should_refresh(obj, now=now, workload_type=WorkloadType.SPIKE)
    assert r1 is r2 is True


def test_callable_syntax_matches_method(policy: RefreshPolicy, now: datetime) -> None:
    """Calling policy(...) instance directly forwards to should_refresh."""
    obj = make_obj(last_accessed=now - timedelta(seconds=200))
    r1 = policy(obj, now=now)
    r2 = policy.should_refresh(obj, now=now)
    assert r1 == r2


def test_class_method_direct_call(now: datetime) -> None:
    """RefreshPolicy.should_refresh can be called directly without instantiation."""
    obj = make_obj(last_accessed=now - timedelta(seconds=500))
    assert RefreshPolicy.should_refresh(obj, now=now) is True


def test_constants_defined() -> None:
    """Constants are exposed on module and class level."""
    assert (
        RefreshPolicy.DEFAULT_REFRESH_AFTER_SECONDS
        == DEFAULT_REFRESH_AFTER_SECONDS
        == 300.0
    )
    assert (
        RefreshPolicy.DEFAULT_AGGRESSIVE_MULTIPLIER
        == DEFAULT_AGGRESSIVE_MULTIPLIER
        == 0.5
    )


# ---------------------------------------------------------------------------
# Step 3: Continuous Telemetry-Driven Refresh Urgency Tests
# ---------------------------------------------------------------------------


def test_fresh_object_has_low_refresh_urgency(
    policy: RefreshPolicy, now: datetime
) -> None:
    """Fresh object (age = 5s) has very low urgency (< 0.05) and is not refreshed."""
    obj = make_obj(last_accessed=now - timedelta(seconds=5), access_count=100)
    urgency = policy.compute_urgency(obj, now=now, refresh_after_seconds=300.0)
    assert 0.0 <= urgency < 0.05
    assert not policy.should_refresh(obj, now=now, refresh_after_seconds=300.0)


def test_stale_object_has_high_refresh_urgency(
    policy: RefreshPolicy, now: datetime
) -> None:
    """Stale object (age = 500s) has high urgency (> 0.60) and is refreshed."""
    obj = make_obj(last_accessed=now - timedelta(seconds=500), access_count=1)
    urgency = policy.compute_urgency(obj, now=now, refresh_after_seconds=300.0)
    assert urgency > 0.60
    assert policy.should_refresh(obj, now=now, refresh_after_seconds=300.0)


def test_increasing_access_frequency_increases_refresh_urgency(
    policy: RefreshPolicy, now: datetime
) -> None:
    """At moderate age (150s), higher access frequency strictly increases urgency."""
    obj_low = make_obj(last_accessed=now - timedelta(seconds=150), access_count=1)
    obj_med = make_obj(last_accessed=now - timedelta(seconds=150), access_count=15)
    obj_high = make_obj(last_accessed=now - timedelta(seconds=150), access_count=80)

    u_low = policy.compute_urgency(obj_low, now=now, refresh_after_seconds=300.0)
    u_med = policy.compute_urgency(obj_med, now=now, refresh_after_seconds=300.0)
    u_high = policy.compute_urgency(obj_high, now=now, refresh_after_seconds=300.0)

    assert u_low < u_med < u_high


def test_newly_active_object_increases_urgency_via_previous_counts(
    policy: RefreshPolicy, now: datetime
) -> None:
    """Object with sudden surge (prev=0 -> curr=30) has higher urgency than steady object."""
    surge_obj = make_obj(last_accessed=now - timedelta(seconds=150), access_count=30)
    steady_obj = make_obj(last_accessed=now - timedelta(seconds=150), access_count=30)

    u_surge = policy.compute_urgency(
        surge_obj, now=now, refresh_after_seconds=300.0, previous_access_count=0
    )
    u_steady = policy.compute_urgency(
        steady_obj, now=now, refresh_after_seconds=300.0, previous_access_count=30
    )

    assert u_surge > u_steady


def test_positive_popularity_trend_increases_refresh_urgency(
    policy: RefreshPolicy, now: datetime
) -> None:
    """Pre-extracted popularity trend continuously modulates urgency."""
    obj = make_obj(last_accessed=now - timedelta(seconds=150), access_count=10)

    u_declining = policy.compute_urgency(
        obj, now=now, features={"popularity_trend": 0.1}
    )
    u_neutral = policy.compute_urgency(obj, now=now, features={"popularity_trend": 0.5})
    u_surging = policy.compute_urgency(obj, now=now, features={"popularity_trend": 0.9})

    assert u_declining < u_neutral < u_surging


def test_high_retrieval_cost_increases_refresh_urgency(
    policy: RefreshPolicy, now: datetime
) -> None:
    """Expensive-to-regenerate items have higher refresh urgency than cheap ones."""
    cheap_obj = make_obj(
        last_accessed=now - timedelta(seconds=150),
        access_count=10,
        retrieval_cost_ms=5.0,
    )
    expensive_obj = make_obj(
        last_accessed=now - timedelta(seconds=150),
        access_count=10,
        retrieval_cost_ms=350.0,
    )

    u_cheap = policy.compute_urgency(cheap_obj, now=now, refresh_after_seconds=300.0)
    u_expensive = policy.compute_urgency(
        expensive_obj, now=now, refresh_after_seconds=300.0
    )

    assert u_expensive > u_cheap


def test_high_backend_latency_increases_retrieval_cost_sensitivity(
    policy: RefreshPolicy, now: datetime
) -> None:
    """High backend latency magnifies the urgency benefit of expensive items."""
    from contracts.schemas.workload import WorkloadState

    expensive_obj = make_obj(
        last_accessed=now - timedelta(seconds=150),
        access_count=10,
        retrieval_cost_ms=300.0,
    )
    fast_workload = WorkloadState(
        request_rate=100.0,
        hit_rate=0.8,
        miss_rate=0.2,
        backend_latency_ms=10.0,
        timestamp=now,
        window_seconds=60.0,
    )
    slow_workload = WorkloadState(
        request_rate=100.0,
        hit_rate=0.8,
        miss_rate=0.2,
        backend_latency_ms=250.0,
        timestamp=now,
        window_seconds=60.0,
    )

    u_fast = policy.compute_urgency(
        expensive_obj, now=now, workload=fast_workload, refresh_after_seconds=300.0
    )
    u_slow = policy.compute_urgency(
        expensive_obj, now=now, workload=slow_workload, refresh_after_seconds=300.0
    )

    assert u_slow > u_fast


def test_memory_pressure_suppresses_cold_object_refresh_urgency(
    policy: RefreshPolicy, now: datetime
) -> None:
    """Under severe cache RAM pressure, cold object refresh urgency is dampened."""
    from contracts.schemas.system import SystemState

    cold_obj = make_obj(
        last_accessed=now - timedelta(seconds=270),
        access_count=1,
        retrieval_cost_ms=10.0,
    )
    low_mem_system = SystemState(
        cache_capacity_bytes=10000,
        cache_usage_bytes=2000,  # 20% utilization
        object_count=10,
        timestamp=now,
        window_seconds=60.0,
    )
    high_mem_system = SystemState(
        cache_capacity_bytes=10000,
        cache_usage_bytes=9500,  # 95% utilization
        object_count=50,
        timestamp=now,
        window_seconds=60.0,
    )

    u_low_press = policy.compute_urgency(
        cold_obj, now=now, system=low_mem_system, refresh_after_seconds=300.0
    )
    u_high_press = policy.compute_urgency(
        cold_obj, now=now, system=high_mem_system, refresh_after_seconds=300.0
    )

    assert u_high_press < u_low_press


def test_no_universal_fixed_age_rule_between_hot_and_cold_objects(
    policy: RefreshPolicy, now: datetime
) -> None:
    """Two objects with identical age (170s) can yield different refresh decisions based on runtime value."""
    # Base threshold is 300s. At 170s, a standard TTL rule would treat both identically as False.
    cold_obj = make_obj(
        last_accessed=now - timedelta(seconds=170),
        access_count=1,
        retrieval_cost_ms=5.0,
    )
    hot_surging_obj = make_obj(
        last_accessed=now - timedelta(seconds=170),
        access_count=50,
        retrieval_cost_ms=250.0,
    )

    features_hot = {
        "frequency": 0.85,
        "popularity_trend": 0.90,
        "retrieval_cost": 0.80,
    }

    should_refresh_cold = policy.should_refresh(
        cold_obj, now=now, refresh_after_seconds=300.0
    )
    should_refresh_hot = policy.should_refresh(
        hot_surging_obj,
        now=now,
        refresh_after_seconds=300.0,
        features=features_hot,
    )

    assert not should_refresh_cold
    assert should_refresh_hot


def test_zero_retrieval_cost_is_safe_and_finite(
    policy: RefreshPolicy, now: datetime
) -> None:
    """Zero retrieval cost produces a valid, finite urgency score."""
    obj = make_obj(
        last_accessed=now - timedelta(seconds=200),
        access_count=5,
        retrieval_cost_ms=0.0,
    )
    urgency = policy.compute_urgency(obj, now=now, refresh_after_seconds=300.0)
    assert 0.0 <= urgency <= 1.0


def test_extreme_retrieval_cost_remains_bounded(
    policy: RefreshPolicy, now: datetime
) -> None:
    """Extreme retrieval cost (e.g. 1,000,000 ms) is strictly bounded in [0.0, 1.0]."""
    obj = make_obj(
        last_accessed=now - timedelta(seconds=200),
        access_count=5,
        retrieval_cost_ms=1_000_000.0,
    )
    urgency = policy.compute_urgency(obj, now=now, refresh_after_seconds=300.0)
    assert 0.0 <= urgency <= 1.0


def test_future_timestamp_clamped_to_zero_urgency(
    policy: RefreshPolicy, now: datetime
) -> None:
    """Future last_accessed timestamp evaluates to 0.0 urgency."""
    future_obj = make_obj(
        last_accessed=now + timedelta(minutes=10),
        access_count=100,
        retrieval_cost_ms=500.0,
    )
    urgency = policy.compute_urgency(future_obj, now=now)
    assert urgency == 0.0
    assert not policy.should_refresh(future_obj, now=now)


def test_custom_urgency_threshold(policy: RefreshPolicy, now: datetime) -> None:
    """Configurable urgency_threshold allows tuning decision boundaries."""
    obj = make_obj(last_accessed=now - timedelta(seconds=200), access_count=10)
    urgency = policy.compute_urgency(obj, now=now, refresh_after_seconds=300.0)

    assert policy.should_refresh(
        obj, now=now, refresh_after_seconds=300.0, urgency_threshold=urgency - 0.05
    )
    assert not policy.should_refresh(
        obj, now=now, refresh_after_seconds=300.0, urgency_threshold=urgency + 0.05
    )


def test_invalid_telemetry_raises_validation_error(
    policy: RefreshPolicy, now: datetime
) -> None:
    """Invalid telemetry arguments raise RefreshPolicyValidationError."""
    obj = make_obj(last_accessed=now)

    with pytest.raises(RefreshPolicyValidationError):
        policy.compute_urgency(obj, now=now, workload="invalid_workload")  # type: ignore[arg-type]

    with pytest.raises(RefreshPolicyValidationError):
        policy.compute_urgency(obj, now=now, system="invalid_system")  # type: ignore[arg-type]

    with pytest.raises(RefreshPolicyValidationError):
        policy.compute_urgency(obj, now=now, features="not_a_mapping")  # type: ignore[arg-type]

    with pytest.raises(RefreshPolicyValidationError):
        policy.compute_urgency(obj, now=now, previous_access_count=-5)

    with pytest.raises(RefreshPolicyValidationError):
        policy.should_refresh(obj, now=now, urgency_threshold=1.5)
