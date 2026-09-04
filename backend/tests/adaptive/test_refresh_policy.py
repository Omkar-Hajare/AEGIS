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
