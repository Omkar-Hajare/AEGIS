"""Unit tests for CapacityController in the Adaptive Cache System.

Tests all scaling rules, edge cases, thresholds, bounds clamping, input validation,
immutability invariants, and determinism.
"""

import math
from datetime import datetime, timezone

import pytest

from backend.adaptive.capacity.controller import (
    CRITICAL_UTILIZATION_THRESHOLD,
    ELEVATED_MISS_RATE_THRESHOLD,
    HIGH_HIT_RATE_THRESHOLD,
    HIGH_UTILIZATION_THRESHOLD,
    LOW_UTILIZATION_THRESHOLD,
    REASON_MAINTAIN_NORMAL,
    REASON_SCALE_DOWN_LOW_UTILIZATION,
    REASON_SCALE_UP_CRITICAL,
    REASON_SCALE_UP_PRESSURE,
    SCALE_DOWN_PERCENTAGE,
    SCALE_UP_PERCENTAGE,
    CapacityController,
)
from backend.adaptive.engine.decision_engine import DecisionEngine
from contracts.schemas.cache import CacheObject
from contracts.schemas.enums import CapacityAction, WorkloadType
from contracts.schemas.system import SystemState
from contracts.schemas.workload import WorkloadState


@pytest.fixture
def controller() -> CapacityController:
    """Fixture providing a clean CapacityController instance."""
    return CapacityController()


@pytest.fixture
def now() -> datetime:
    """Fixture providing a fixed timezone-aware timestamp."""
    return datetime(2026, 9, 4, 12, 0, 0, tzinfo=timezone.utc)


def make_workload(
    now: datetime,
    hit_rate: float = 0.5,
    miss_rate: float = 0.5,
    request_rate: float = 100.0,
    backend_latency_ms: float = 20.0,
) -> WorkloadState:
    """Helper to create a valid WorkloadState."""
    return WorkloadState(
        request_rate=request_rate,
        hit_rate=hit_rate,
        miss_rate=miss_rate,
        backend_latency_ms=backend_latency_ms,
        workload_type=WorkloadType.STEADY,
        timestamp=now,
        window_seconds=60.0,
    )


def make_system(
    now: datetime,
    cache_capacity_bytes: int = 1000,
    cache_usage_bytes: int = 500,
    object_count: int = 10,
) -> SystemState:
    """Helper to create a valid SystemState."""
    return SystemState(
        cache_capacity_bytes=cache_capacity_bytes,
        cache_usage_bytes=cache_usage_bytes,
        object_count=object_count,
        timestamp=now,
        window_seconds=60.0,
    )


# ---------------------------------------------------------------------------
# Core Rule Tests
# ---------------------------------------------------------------------------


def test_high_utilization_with_elevated_miss_rate_returns_scale_up(
    controller: CapacityController, now: datetime
) -> None:
    """High utilization (>=85%) with miss_rate > 20% triggers SCALE_UP in rule_based mode."""
    workload = make_workload(now, hit_rate=0.70, miss_rate=0.30)
    system = make_system(now, cache_capacity_bytes=1000, cache_usage_bytes=850)

    decision = controller.recommend(workload, system, 500, 2000, mode="rule_based")

    assert decision.capacity_action == CapacityAction.SCALE_UP
    assert decision.recommended_capacity_bytes == 1200
    assert decision.reason == REASON_SCALE_UP_PRESSURE


def test_critical_utilization_returns_scale_up_even_when_miss_rate_is_low(
    controller: CapacityController, now: datetime
) -> None:
    """Critical utilization (>=90%) triggers SCALE_UP even when miss_rate is low in rule_based mode."""
    workload = make_workload(now, hit_rate=0.95, miss_rate=0.05)
    system = make_system(now, cache_capacity_bytes=1000, cache_usage_bytes=900)

    decision = controller.recommend(workload, system, 500, 2000, mode="rule_based")

    assert decision.capacity_action == CapacityAction.SCALE_UP
    assert decision.recommended_capacity_bytes == 1200
    assert decision.reason == REASON_SCALE_UP_CRITICAL


def test_utilization_between_scale_up_and_scale_down_regions_returns_maintain(
    controller: CapacityController, now: datetime
) -> None:
    """Utilization between 40% and 85% returns MAINTAIN with current capacity in rule_based mode."""
    workload = make_workload(now, hit_rate=0.70, miss_rate=0.30)
    system = make_system(now, cache_capacity_bytes=1000, cache_usage_bytes=600)

    decision = controller.recommend(workload, system, 500, 2000, mode="rule_based")

    assert decision.capacity_action == CapacityAction.MAINTAIN
    assert decision.recommended_capacity_bytes == 1000
    assert decision.reason == REASON_MAINTAIN_NORMAL


def test_low_utilization_with_strong_hit_rate_returns_scale_down(
    controller: CapacityController, now: datetime
) -> None:
    """Low utilization (<=40%) with hit_rate >= 80% triggers SCALE_DOWN in rule_based mode."""
    workload = make_workload(now, hit_rate=0.90, miss_rate=0.10)
    system = make_system(now, cache_capacity_bytes=1000, cache_usage_bytes=300)

    decision = controller.recommend(workload, system, 500, 2000, mode="rule_based")

    assert decision.capacity_action == CapacityAction.SCALE_DOWN
    assert decision.recommended_capacity_bytes == 850
    assert decision.reason == REASON_SCALE_DOWN_LOW_UTILIZATION


def test_low_utilization_without_strong_hit_rate_returns_maintain(
    controller: CapacityController, now: datetime
) -> None:
    """Low utilization (<=40%) without hit_rate >= 80% returns MAINTAIN in rule_based mode."""
    workload = make_workload(now, hit_rate=0.75, miss_rate=0.25)
    system = make_system(now, cache_capacity_bytes=1000, cache_usage_bytes=300)

    decision = controller.recommend(workload, system, 500, 2000, mode="rule_based")

    assert decision.capacity_action == CapacityAction.MAINTAIN
    assert decision.recommended_capacity_bytes == 1000
    assert decision.reason == REASON_MAINTAIN_NORMAL


# ---------------------------------------------------------------------------
# Capacity Calculation & Rounding Tests
# ---------------------------------------------------------------------------


def test_scale_up_recommendation_increases_capacity_by_twenty_percent(
    controller: CapacityController, now: datetime
) -> None:
    """Scale-up increases capacity by exactly ceil(current * 1.20) in rule_based mode."""
    workload = make_workload(now, miss_rate=0.25)
    system = make_system(now, cache_capacity_bytes=1000, cache_usage_bytes=900)

    decision = controller.recommend(workload, system, 100, 5000, mode="rule_based")
    assert decision.recommended_capacity_bytes == 1200


def test_scale_up_rounding_uses_ceil(
    controller: CapacityController, now: datetime
) -> None:
    """Scale-up on fractional result uses math.ceil in rule_based mode."""
    workload = make_workload(now, miss_rate=0.25)
    # 1001 * 1.20 = 1201.2 -> ceil is 1202
    system = make_system(now, cache_capacity_bytes=1001, cache_usage_bytes=950)

    decision = controller.recommend(workload, system, 100, 5000, mode="rule_based")
    assert decision.recommended_capacity_bytes == 1202


def test_scale_down_recommendation_decreases_capacity_by_fifteen_percent(
    controller: CapacityController, now: datetime
) -> None:
    """Scale-down decreases capacity by exactly floor(current * 0.85) in rule_based mode."""
    workload = make_workload(now, hit_rate=0.85, miss_rate=0.15)
    system = make_system(now, cache_capacity_bytes=1000, cache_usage_bytes=200)

    decision = controller.recommend(workload, system, 100, 5000, mode="rule_based")
    assert decision.recommended_capacity_bytes == 850


def test_scale_down_rounding_uses_floor(
    controller: CapacityController, now: datetime
) -> None:
    """Scale-down on fractional result uses math.floor in rule_based mode."""
    workload = make_workload(now, hit_rate=0.85, miss_rate=0.15)
    # 1001 * 0.85 = 850.85 -> floor is 850
    system = make_system(now, cache_capacity_bytes=1001, cache_usage_bytes=200)

    decision = controller.recommend(workload, system, 100, 5000, mode="rule_based")
    assert decision.recommended_capacity_bytes == 850


def test_maintain_preserves_current_capacity(
    controller: CapacityController, now: datetime
) -> None:
    """MAINTAIN action preserves exact current capacity in rule_based mode."""
    workload = make_workload(now, hit_rate=0.60, miss_rate=0.40)
    system = make_system(now, cache_capacity_bytes=1420, cache_usage_bytes=710)

    decision = controller.recommend(workload, system, 100, 5000, mode="rule_based")
    assert decision.recommended_capacity_bytes == 1420


# ---------------------------------------------------------------------------
# Bounds Clamping Tests
# ---------------------------------------------------------------------------


def test_scale_up_capacity_is_capped_at_max_capacity(
    controller: CapacityController, now: datetime
) -> None:
    """Recommended scale-up capacity never exceeds max_capacity_bytes in rule_based mode."""
    workload = make_workload(now, miss_rate=0.30)
    # 1000 * 1.20 = 1200, but max is 1100
    system = make_system(now, cache_capacity_bytes=1000, cache_usage_bytes=900)

    decision = controller.recommend(workload, system, 500, 1100, mode="rule_based")
    assert decision.capacity_action == CapacityAction.SCALE_UP
    assert decision.recommended_capacity_bytes == 1100


def test_scale_down_capacity_is_floored_at_min_capacity(
    controller: CapacityController, now: datetime
) -> None:
    """Recommended scale-down capacity never goes below min_capacity_bytes in rule_based mode."""
    workload = make_workload(now, hit_rate=0.90)
    # 1000 * 0.85 = 850, but min is 900
    system = make_system(now, cache_capacity_bytes=1000, cache_usage_bytes=200)

    decision = controller.recommend(workload, system, 900, 2000, mode="rule_based")
    assert decision.capacity_action == CapacityAction.SCALE_DOWN
    assert decision.recommended_capacity_bytes == 900


def test_maintain_clamped_if_current_outside_bounds(
    controller: CapacityController, now: datetime
) -> None:
    """MAINTAIN clamps capacity if current capacity falls outside [min, max] in rule_based mode."""
    workload = make_workload(now, hit_rate=0.50, miss_rate=0.50)
    system = make_system(now, cache_capacity_bytes=300, cache_usage_bytes=150)

    # Current capacity 300 is below min 500
    decision = controller.recommend(workload, system, 500, 1000, mode="rule_based")
    assert decision.capacity_action == CapacityAction.MAINTAIN
    assert decision.recommended_capacity_bytes == 500


def test_min_capacity_equals_max_capacity_clamps_strictly(
    controller: CapacityController, now: datetime
) -> None:
    """When min_capacity == max_capacity, recommended capacity is strictly locked."""
    workload = make_workload(now, miss_rate=0.50)
    system = make_system(now, cache_capacity_bytes=1000, cache_usage_bytes=950)

    decision = controller.recommend(workload, system, 1000, 1000, mode="rule_based")
    assert decision.recommended_capacity_bytes == 1000


# ---------------------------------------------------------------------------
# Priority Order Tests
# ---------------------------------------------------------------------------


def test_scale_up_takes_priority_when_multiple_conditions_are_true(
    controller: CapacityController, now: datetime
) -> None:
    """Scale-up conditions take priority over any scale-down conditions in rule_based mode."""
    # Critical utilization >= 90% with high hit rate >= 80%
    workload = make_workload(now, hit_rate=0.95, miss_rate=0.05)
    system = make_system(now, cache_capacity_bytes=1000, cache_usage_bytes=950)

    decision = controller.recommend(workload, system, 500, 2000, mode="rule_based")
    assert decision.capacity_action == CapacityAction.SCALE_UP
    assert decision.recommended_capacity_bytes == 1200


# ---------------------------------------------------------------------------
# Exact Boundary Threshold Tests
# ---------------------------------------------------------------------------


def test_exact_threshold_eighty_five_percent_utilization_with_miss_rate(
    controller: CapacityController, now: datetime
) -> None:
    """Exact utilization threshold 85% triggers SCALE_UP when miss_rate > 20% in rule_based mode."""
    workload = make_workload(now, miss_rate=0.21)
    system = make_system(now, cache_capacity_bytes=1000, cache_usage_bytes=850)

    decision = controller.recommend(workload, system, 500, 2000, mode="rule_based")
    assert decision.capacity_action == CapacityAction.SCALE_UP
    assert decision.recommended_capacity_bytes == 1200


def test_exact_threshold_ninety_percent_utilization(
    controller: CapacityController, now: datetime
) -> None:
    """Exact utilization threshold 90% triggers SCALE_UP in rule_based mode."""
    workload = make_workload(now, miss_rate=0.05)
    system = make_system(now, cache_capacity_bytes=1000, cache_usage_bytes=900)

    decision = controller.recommend(workload, system, 500, 2000, mode="rule_based")
    assert decision.capacity_action == CapacityAction.SCALE_UP
    assert decision.recommended_capacity_bytes == 1200


def test_exact_threshold_forty_percent_utilization(
    controller: CapacityController, now: datetime
) -> None:
    """Exact utilization threshold 40% triggers SCALE_DOWN when hit_rate >= 80% in rule_based mode."""
    workload = make_workload(now, hit_rate=0.80)
    system = make_system(now, cache_capacity_bytes=1000, cache_usage_bytes=400)

    decision = controller.recommend(workload, system, 500, 2000, mode="rule_based")
    assert decision.capacity_action == CapacityAction.SCALE_DOWN
    assert decision.recommended_capacity_bytes == 850


def test_exact_threshold_forty_one_percent_utilization_does_not_scale_down(
    controller: CapacityController, now: datetime
) -> None:
    """Utilization just above 40% (41%) does not trigger SCALE_DOWN in rule_based mode."""
    workload = make_workload(now, hit_rate=0.90)
    system = make_system(now, cache_capacity_bytes=1000, cache_usage_bytes=410)

    decision = controller.recommend(workload, system, 500, 2000, mode="rule_based")
    assert decision.capacity_action == CapacityAction.MAINTAIN
    assert decision.recommended_capacity_bytes == 1000


def test_exact_hit_rate_threshold_eighty_percent(
    controller: CapacityController, now: datetime
) -> None:
    """Exact hit rate 80% (>= 0.80) triggers SCALE_DOWN when low utilization in rule_based mode."""
    workload = make_workload(now, hit_rate=0.80)
    system = make_system(now, cache_capacity_bytes=1000, cache_usage_bytes=350)

    decision = controller.recommend(workload, system, 500, 2000, mode="rule_based")
    assert decision.capacity_action == CapacityAction.SCALE_DOWN
    assert decision.recommended_capacity_bytes == 850


def test_hit_rate_below_eighty_percent_does_not_scale_down(
    controller: CapacityController, now: datetime
) -> None:
    """Hit rate below 80% (79.9%) does not trigger SCALE_DOWN in rule_based mode."""
    workload = make_workload(now, hit_rate=0.799)
    system = make_system(now, cache_capacity_bytes=1000, cache_usage_bytes=350)

    decision = controller.recommend(workload, system, 500, 2000, mode="rule_based")
    assert decision.capacity_action == CapacityAction.MAINTAIN
    assert decision.recommended_capacity_bytes == 1000


def test_exact_miss_rate_threshold_twenty_percent(
    controller: CapacityController, now: datetime
) -> None:
    """Exact miss rate 20% (not > 20%) does NOT trigger SCALE_UP at 85% utilization in rule_based mode."""
    workload = make_workload(now, hit_rate=0.80, miss_rate=0.20)
    system = make_system(now, cache_capacity_bytes=1000, cache_usage_bytes=850)

    decision = controller.recommend(workload, system, 500, 2000, mode="rule_based")
    assert decision.capacity_action == CapacityAction.MAINTAIN
    assert decision.recommended_capacity_bytes == 1000


def test_miss_rate_strictly_greater_than_twenty_percent_triggers_scale_up(
    controller: CapacityController, now: datetime
) -> None:
    """Miss rate strictly > 20% (e.g. 20.1%) triggers SCALE_UP at 85% utilization in rule_based mode."""
    workload = make_workload(now, hit_rate=0.79, miss_rate=0.201)
    system = make_system(now, cache_capacity_bytes=1000, cache_usage_bytes=850)

    decision = controller.recommend(workload, system, 500, 2000, mode="rule_based")
    assert decision.capacity_action == CapacityAction.SCALE_UP
    assert decision.recommended_capacity_bytes == 1200


# ---------------------------------------------------------------------------
# Boundary Specification Examples
# ---------------------------------------------------------------------------


def test_spec_boundary_example_one(
    controller: CapacityController, now: datetime
) -> None:
    """Boundary Example 1 from specification: usage=850, capacity=1000, miss=0.30."""
    workload = make_workload(now, hit_rate=0.70, miss_rate=0.30)
    system = make_system(now, cache_capacity_bytes=1000, cache_usage_bytes=850)

    decision = controller.recommend(workload, system, 500, 2000, mode="rule_based")
    assert decision.capacity_action == CapacityAction.SCALE_UP
    assert decision.recommended_capacity_bytes == 1200


def test_spec_boundary_example_two(
    controller: CapacityController, now: datetime
) -> None:
    """Boundary Example 2 from spec: usage=900, capacity=1000, hit=0.95, miss=0.05."""
    workload = make_workload(now, hit_rate=0.95, miss_rate=0.05)
    system = make_system(now, cache_capacity_bytes=1000, cache_usage_bytes=900)

    decision = controller.recommend(workload, system, 500, 2000, mode="rule_based")
    assert decision.capacity_action == CapacityAction.SCALE_UP
    assert decision.recommended_capacity_bytes == 1200


def test_spec_boundary_example_three(
    controller: CapacityController, now: datetime
) -> None:
    """Boundary Example 3 from spec: usage=300, capacity=1000, hit=0.90, miss=0.10."""
    workload = make_workload(now, hit_rate=0.90, miss_rate=0.10)
    system = make_system(now, cache_capacity_bytes=1000, cache_usage_bytes=300)

    decision = controller.recommend(workload, system, 500, 2000, mode="rule_based")
    assert decision.capacity_action == CapacityAction.SCALE_DOWN
    assert decision.recommended_capacity_bytes == 850


def test_spec_boundary_example_four(
    controller: CapacityController, now: datetime
) -> None:
    """Boundary Example 4 from spec: usage=600, capacity=1000, hit=0.70, miss=0.30."""
    workload = make_workload(now, hit_rate=0.70, miss_rate=0.30)
    system = make_system(now, cache_capacity_bytes=1000, cache_usage_bytes=600)

    decision = controller.recommend(workload, system, 500, 2000, mode="rule_based")
    assert decision.capacity_action == CapacityAction.MAINTAIN
    assert decision.recommended_capacity_bytes == 1000


# ---------------------------------------------------------------------------
# Validation & Error Handling Tests
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("invalid_min", [0, -1, -500])
def test_non_positive_min_capacity_raises_value_error(
    controller: CapacityController, now: datetime, invalid_min: int
) -> None:
    """min_capacity_bytes <= 0 raises ValueError."""
    workload = make_workload(now)
    system = make_system(now)

    with pytest.raises(ValueError, match="min_capacity_bytes must be greater than 0"):
        controller.recommend(workload, system, invalid_min, 2000)


@pytest.mark.parametrize("invalid_max", [0, -1, -500])
def test_non_positive_max_capacity_raises_value_error(
    controller: CapacityController, now: datetime, invalid_max: int
) -> None:
    """max_capacity_bytes <= 0 raises ValueError."""
    workload = make_workload(now)
    system = make_system(now)

    with pytest.raises(ValueError, match="max_capacity_bytes must be greater than 0"):
        controller.recommend(workload, system, 100, invalid_max)


def test_min_greater_than_max_capacity_raises_value_error(
    controller: CapacityController, now: datetime
) -> None:
    """min_capacity_bytes > max_capacity_bytes raises ValueError."""
    workload = make_workload(now)
    system = make_system(now)

    with pytest.raises(
        ValueError,
        match="min_capacity_bytes .* must be less than or equal to max_capacity_bytes",
    ):
        controller.recommend(workload, system, 2000, 1000)


@pytest.mark.parametrize("bad_arg", [True, False])
def test_boolean_min_capacity_raises_value_error(
    controller: CapacityController, now: datetime, bad_arg: bool
) -> None:
    """Boolean min_capacity_bytes raises ValueError."""
    workload = make_workload(now)
    system = make_system(now)

    with pytest.raises(ValueError, match="min_capacity_bytes must be an integer"):
        controller.recommend(workload, system, bad_arg, 2000)  # type: ignore[arg-type]


@pytest.mark.parametrize("bad_arg", [True, False])
def test_boolean_max_capacity_raises_value_error(
    controller: CapacityController, now: datetime, bad_arg: bool
) -> None:
    """Boolean max_capacity_bytes raises ValueError."""
    workload = make_workload(now)
    system = make_system(now)

    with pytest.raises(ValueError, match="max_capacity_bytes must be an integer"):
        controller.recommend(workload, system, 100, bad_arg)  # type: ignore[arg-type]


@pytest.mark.parametrize("invalid_type", ["1000", 500.5, None, [100]])
def test_non_integer_min_capacity_raises_value_error(
    controller: CapacityController, now: datetime, invalid_type: object
) -> None:
    """Non-integer min_capacity_bytes raises ValueError."""
    workload = make_workload(now)
    system = make_system(now)

    with pytest.raises(ValueError, match="min_capacity_bytes must be an integer"):
        controller.recommend(workload, system, invalid_type, 2000)  # type: ignore[arg-type]


@pytest.mark.parametrize("invalid_type", ["2000", 2000.5, None, [2000]])
def test_non_integer_max_capacity_raises_value_error(
    controller: CapacityController, now: datetime, invalid_type: object
) -> None:
    """Non-integer max_capacity_bytes raises ValueError."""
    workload = make_workload(now)
    system = make_system(now)

    with pytest.raises(ValueError, match="max_capacity_bytes must be an integer"):
        controller.recommend(workload, system, 100, invalid_type)  # type: ignore[arg-type]


def test_invalid_workload_instance_raises_value_error(
    controller: CapacityController, now: datetime
) -> None:
    """Non-WorkloadState instance raises ValueError."""
    system = make_system(now)

    with pytest.raises(
        ValueError, match="workload must be an instance of WorkloadState"
    ):
        controller.recommend({"hit_rate": 0.9}, system, 100, 2000)  # type: ignore[arg-type]


def test_invalid_system_instance_raises_value_error(
    controller: CapacityController, now: datetime
) -> None:
    """Non-SystemState instance raises ValueError."""
    workload = make_workload(now)

    with pytest.raises(ValueError, match="system must be an instance of SystemState"):
        controller.recommend(workload, {"usage": 500}, 100, 2000)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Immutability & Determinism Tests
# ---------------------------------------------------------------------------


def test_input_workload_state_is_not_mutated(
    controller: CapacityController, now: datetime
) -> None:
    """WorkloadState is never modified by CapacityController."""
    workload = make_workload(now, hit_rate=0.85, miss_rate=0.15)
    snapshot = workload.model_dump()

    controller.recommend(workload, make_system(now), 100, 2000)

    assert workload.model_dump() == snapshot


def test_input_system_state_is_not_mutated(
    controller: CapacityController, now: datetime
) -> None:
    """SystemState is never modified by CapacityController."""
    system = make_system(now, cache_capacity_bytes=1000, cache_usage_bytes=600)
    snapshot = system.model_dump()

    controller.recommend(make_workload(now), system, 100, 2000)

    assert system.model_dump() == snapshot


def test_determinism_same_input_produces_identical_output(
    controller: CapacityController, now: datetime
) -> None:
    """Repeated calls with identical input produce identical Decisions."""
    workload = make_workload(now, hit_rate=0.85, miss_rate=0.15)
    system = make_system(now, cache_capacity_bytes=1000, cache_usage_bytes=900)

    d1 = controller.recommend(workload, system, 100, 2000)
    d2 = controller.recommend(workload, system, 100, 2000)

    assert d1 == d2
    assert d1.model_dump() == d2.model_dump()


# ---------------------------------------------------------------------------
# Decision Contract Verification Tests
# ---------------------------------------------------------------------------


def test_decision_contract_version_is_v1(
    controller: CapacityController, now: datetime
) -> None:
    """Decision output explicitly specifies version v1."""
    decision = controller.recommend(make_workload(now), make_system(now), 100, 2000)
    assert decision.version == "v1"


def test_empty_default_decision_collections_remain_empty(
    controller: CapacityController, now: datetime
) -> None:
    """object_scores and eviction_keys in Decision are empty collections."""
    decision = controller.recommend(make_workload(now), make_system(now), 100, 2000)
    assert decision.object_scores == {}
    assert decision.eviction_keys == []


def test_decision_contains_useful_reason_string(
    controller: CapacityController, now: datetime
) -> None:
    """Decision contains a non-empty human-readable reason string."""
    decision = controller.recommend(make_workload(now), make_system(now), 100, 2000)
    assert isinstance(decision.reason, str)
    assert len(decision.reason.strip()) > 0


def test_decision_id_is_passed_through(
    controller: CapacityController, now: datetime
) -> None:
    """Optional decision_id is preserved in output Decision."""
    decision = controller.recommend(
        make_workload(now),
        make_system(now),
        100,
        2000,
        decision_id="decision-abc-123",
    )
    assert decision.decision_id == "decision-abc-123"


def test_decision_timestamp_matches_system_timestamp(
    controller: CapacityController, now: datetime
) -> None:
    """Decision timestamp preserves system snapshot timestamp deterministically."""
    system = make_system(now)
    decision = controller.recommend(make_workload(now), system, 100, 2000)
    assert decision.timestamp == system.timestamp


def test_callable_syntax_matches_recommend_method(
    controller: CapacityController, now: datetime
) -> None:
    """CapacityController instance can be called directly as a callable."""
    workload = make_workload(now)
    system = make_system(now)

    d1 = controller(workload, system, 100, 2000)
    d2 = controller.recommend(workload, system, 100, 2000)

    assert d1 == d2


def test_all_three_capacity_actions_are_represented(
    controller: CapacityController, now: datetime
) -> None:
    """Ensure SCALE_UP, SCALE_DOWN, and MAINTAIN are all produced across scenarios."""
    d_up = controller.recommend(
        make_workload(now, miss_rate=0.30),
        make_system(now, cache_capacity_bytes=1000, cache_usage_bytes=900),
        100,
        2000,
        mode="rule_based",
    )
    d_down = controller.recommend(
        make_workload(now, hit_rate=0.90, miss_rate=0.10),
        make_system(now, cache_capacity_bytes=1000, cache_usage_bytes=300),
        100,
        2000,
        mode="rule_based",
    )
    d_maintain = controller.recommend(
        make_workload(now, hit_rate=0.60, miss_rate=0.40),
        make_system(now, cache_capacity_bytes=1000, cache_usage_bytes=600),
        100,
        2000,
        mode="rule_based",
    )

    actions = {d_up.capacity_action, d_down.capacity_action, d_maintain.capacity_action}
    assert actions == {
        CapacityAction.SCALE_UP,
        CapacityAction.SCALE_DOWN,
        CapacityAction.MAINTAIN,
    }


def test_constants_exposed_on_controller_class_and_module() -> None:
    """Constants are defined on module level and class attributes."""
    assert CapacityController.SCALE_UP_PERCENTAGE == SCALE_UP_PERCENTAGE == 0.20
    assert CapacityController.SCALE_DOWN_PERCENTAGE == SCALE_DOWN_PERCENTAGE == 0.15
    assert (
        CapacityController.HIGH_UTILIZATION_THRESHOLD
        == HIGH_UTILIZATION_THRESHOLD
        == 0.85
    )
    assert (
        CapacityController.CRITICAL_UTILIZATION_THRESHOLD
        == CRITICAL_UTILIZATION_THRESHOLD
        == 0.90
    )
    assert (
        CapacityController.LOW_UTILIZATION_THRESHOLD
        == LOW_UTILIZATION_THRESHOLD
        == 0.40
    )
    assert CapacityController.HIGH_HIT_RATE_THRESHOLD == HIGH_HIT_RATE_THRESHOLD == 0.80
    assert (
        CapacityController.ELEVATED_MISS_RATE_THRESHOLD
        == ELEVATED_MISS_RATE_THRESHOLD
        == 0.20
    )


# ---------------------------------------------------------------------------
# Continuous Mode & Pressure Calculation Tests (Step 1-5 Requirements)
# ---------------------------------------------------------------------------


def test_compute_pressure_returns_value_in_zero_to_one(
    controller: CapacityController, now: datetime
) -> None:
    """Requirement 1: compute_pressure returns value in [0,1]."""
    scenarios = [
        (
            make_workload(
                now,
                hit_rate=0.9,
                miss_rate=0.1,
                request_rate=10,
                backend_latency_ms=5,
            ),
            make_system(now, cache_capacity_bytes=1000, cache_usage_bytes=100),
        ),
        (
            make_workload(
                now,
                hit_rate=0.5,
                miss_rate=0.5,
                request_rate=100,
                backend_latency_ms=50,
            ),
            make_system(now, cache_capacity_bytes=1000, cache_usage_bytes=500),
        ),
        (
            make_workload(
                now,
                hit_rate=0.1,
                miss_rate=0.9,
                request_rate=1000,
                backend_latency_ms=200,
            ),
            make_system(now, cache_capacity_bytes=1000, cache_usage_bytes=950),
        ),
    ]
    for wl, sys in scenarios:
        pressure = controller.compute_pressure(wl, sys)
        assert isinstance(pressure, float)
        assert 0.0 <= pressure <= 1.0


def test_zero_utilization_and_zero_telemetry_produces_low_pressure(
    controller: CapacityController, now: datetime
) -> None:
    """Requirement 2: zero utilization and zero telemetry produces low pressure."""
    workload = make_workload(
        now, hit_rate=1.0, miss_rate=0.0, request_rate=0.0, backend_latency_ms=0.0
    )
    system = make_system(now, cache_capacity_bytes=1000, cache_usage_bytes=0)

    pressure = controller.compute_pressure(workload, system)
    assert pressure == 0.0


def test_increasing_memory_utilization_increases_pressure(
    controller: CapacityController, now: datetime
) -> None:
    """Requirement 3: increasing memory utilization increases pressure."""
    wl = make_workload(
        now, hit_rate=0.5, miss_rate=0.5, request_rate=50, backend_latency_ms=20
    )
    p_low = controller.compute_pressure(
        wl, make_system(now, cache_capacity_bytes=1000, cache_usage_bytes=200)
    )
    p_mid = controller.compute_pressure(
        wl, make_system(now, cache_capacity_bytes=1000, cache_usage_bytes=500)
    )
    p_high = controller.compute_pressure(
        wl, make_system(now, cache_capacity_bytes=1000, cache_usage_bytes=900)
    )

    assert p_low < p_mid < p_high


def test_increasing_miss_rate_increases_pressure_when_memory_utilization_is_nonzero(
    controller: CapacityController, now: datetime
) -> None:
    """Requirement 4: increasing miss rate increases pressure when memory utilization is nonzero."""
    system = make_system(now, cache_capacity_bytes=1000, cache_usage_bytes=600)
    p_low_miss = controller.compute_pressure(
        make_workload(
            now,
            hit_rate=0.90,
            miss_rate=0.10,
            request_rate=100,
            backend_latency_ms=30,
        ),
        system,
    )
    p_high_miss = controller.compute_pressure(
        make_workload(
            now,
            hit_rate=0.20,
            miss_rate=0.80,
            request_rate=100,
            backend_latency_ms=30,
        ),
        system,
    )
    assert p_low_miss < p_high_miss


def test_high_memory_plus_high_miss_rate_produces_stronger_pressure_than_either_signal_alone(
    controller: CapacityController, now: datetime
) -> None:
    """Requirement 5: high memory plus high miss rate produces stronger pressure than either signal alone."""
    req = 50.0
    lat = 20.0
    sys_low = make_system(now, cache_capacity_bytes=1000, cache_usage_bytes=100)
    wl_low_miss = make_workload(
        now, hit_rate=0.90, miss_rate=0.10, request_rate=req, backend_latency_ms=lat
    )

    # High memory only (mem=0.9, miss=0.1)
    sys_high = make_system(now, cache_capacity_bytes=1000, cache_usage_bytes=900)
    p_high_mem_only = controller.compute_pressure(wl_low_miss, sys_high)

    # High miss only (mem=0.1, miss=0.9)
    wl_high_miss = make_workload(
        now, hit_rate=0.10, miss_rate=0.90, request_rate=req, backend_latency_ms=lat
    )
    p_high_miss_only = controller.compute_pressure(wl_high_miss, sys_low)

    # Both high (mem=0.9, miss=0.9)
    p_both_high = controller.compute_pressure(wl_high_miss, sys_high)

    assert p_both_high > p_high_mem_only
    assert p_both_high > p_high_miss_only


def test_increasing_request_rate_increases_pressure(
    controller: CapacityController, now: datetime
) -> None:
    """Requirement 6: increasing request rate increases pressure."""
    system = make_system(now, cache_capacity_bytes=1000, cache_usage_bytes=500)
    p_10 = controller.compute_pressure(
        make_workload(
            now,
            request_rate=10.0,
            hit_rate=0.5,
            miss_rate=0.5,
            backend_latency_ms=20,
        ),
        system,
    )
    p_100 = controller.compute_pressure(
        make_workload(
            now,
            request_rate=100.0,
            hit_rate=0.5,
            miss_rate=0.5,
            backend_latency_ms=20,
        ),
        system,
    )
    p_500 = controller.compute_pressure(
        make_workload(
            now,
            request_rate=500.0,
            hit_rate=0.5,
            miss_rate=0.5,
            backend_latency_ms=20,
        ),
        system,
    )
    assert p_10 < p_100 < p_500


def test_traffic_surge_increases_request_rate_pressure(
    controller: CapacityController, now: datetime
) -> None:
    """Requirement 7: traffic surge increases request-rate pressure."""
    system = make_system(now, cache_capacity_bytes=1000, cache_usage_bytes=500)
    wl_no_surge = make_workload(
        now, request_rate=200.0, hit_rate=0.5, miss_rate=0.5, backend_latency_ms=30
    )
    wl_surge = WorkloadState(
        request_rate=200.0,
        hit_rate=0.5,
        miss_rate=0.5,
        backend_latency_ms=30.0,
        workload_type=WorkloadType.SPIKE,
        timestamp=now,
        window_seconds=60.0,
        metrics={"previous_window_request_rate": 50.0},
    )

    p_no_surge = controller.compute_pressure(wl_no_surge, system)
    p_surge = controller.compute_pressure(wl_surge, system)

    assert p_surge > p_no_surge
    assert p_surge <= 1.0


def test_increasing_backend_latency_increases_pressure(
    controller: CapacityController, now: datetime
) -> None:
    """Requirement 8: increasing backend latency increases pressure."""
    system = make_system(now, cache_capacity_bytes=1000, cache_usage_bytes=500)
    wl_fast = make_workload(
        now,
        request_rate=100.0,
        hit_rate=0.5,
        miss_rate=0.5,
        backend_latency_ms=10.0,
    )
    wl_slow = make_workload(
        now,
        request_rate=100.0,
        hit_rate=0.5,
        miss_rate=0.5,
        backend_latency_ms=150.0,
    )

    assert controller.compute_pressure(wl_fast, system) < controller.compute_pressure(
        wl_slow, system
    )


def test_pressure_is_deterministic_for_identical_inputs(
    controller: CapacityController, now: datetime
) -> None:
    """Requirement 9: pressure is deterministic for identical inputs."""
    workload = make_workload(
        now,
        request_rate=120.0,
        hit_rate=0.6,
        miss_rate=0.4,
        backend_latency_ms=35.0,
    )
    system = make_system(now, cache_capacity_bytes=1000, cache_usage_bytes=650)

    pressures = [controller.compute_pressure(workload, system) for _ in range(10)]
    assert all(p == pressures[0] for p in pressures)


def test_pressure_remains_bounded_with_extreme_input_values(
    controller: CapacityController, now: datetime
) -> None:
    """Requirement 10: pressure remains bounded with extreme input values."""
    extreme_workload = WorkloadState(
        request_rate=10_000_000.0,
        hit_rate=0.0,
        miss_rate=1.0,
        backend_latency_ms=10_000_000.0,
        workload_type=WorkloadType.SPIKE,
        timestamp=now,
        window_seconds=60.0,
        metrics={"previous_window_request_rate": 1.0},
    )
    extreme_system = make_system(
        now, cache_capacity_bytes=1000, cache_usage_bytes=50_000
    )

    p_high = controller.compute_pressure(extreme_workload, extreme_system)
    assert 0.0 <= p_high <= 1.0

    zero_workload = make_workload(
        now, request_rate=0.0, hit_rate=1.0, miss_rate=0.0, backend_latency_ms=0.0
    )
    zero_system = make_system(now, cache_capacity_bytes=1000, cache_usage_bytes=0)

    p_low = controller.compute_pressure(zero_workload, zero_system)
    assert 0.0 <= p_low <= 1.0


def test_pressure_decreases_when_workload_pressure_recovers(
    controller: CapacityController, now: datetime
) -> None:
    """Requirement 11: pressure decreases when workload pressure recovers."""
    stressed_wl = make_workload(
        now,
        request_rate=400.0,
        hit_rate=0.2,
        miss_rate=0.8,
        backend_latency_ms=120.0,
    )
    stressed_sys = make_system(now, cache_capacity_bytes=1000, cache_usage_bytes=900)
    p_stressed = controller.compute_pressure(stressed_wl, stressed_sys)

    recovered_wl = make_workload(
        now,
        request_rate=50.0,
        hit_rate=0.9,
        miss_rate=0.1,
        backend_latency_ms=15.0,
    )
    recovered_sys = make_system(now, cache_capacity_bytes=1000, cache_usage_bytes=300)
    p_recovered = controller.compute_pressure(recovered_wl, recovered_sys)

    assert p_recovered < p_stressed


def test_pressure_near_equilibrium_produces_maintain(
    controller: CapacityController, now: datetime
) -> None:
    """Requirement 12: pressure near equilibrium produces MAINTAIN."""
    workload = make_workload(
        now,
        request_rate=100.0,
        hit_rate=0.65,
        miss_rate=0.35,
        backend_latency_ms=30.0,
    )
    system = make_system(now, cache_capacity_bytes=1000, cache_usage_bytes=650)

    p = controller.compute_pressure(workload, system)
    assert 0.45 <= p <= 0.65

    decision = controller.recommend(workload, system, 100, 5000, mode="continuous")
    assert decision.capacity_action == CapacityAction.MAINTAIN
    assert decision.recommended_capacity_bytes == 1000


def test_higher_pressure_produces_a_larger_scale_up_percentage(
    controller: CapacityController, now: datetime
) -> None:
    """Requirement 13: higher pressure produces a larger scale-up percentage."""
    # Modest scale-up (P_cap > 0.65)
    wl_modest = make_workload(
        now,
        request_rate=200.0,
        hit_rate=0.3,
        miss_rate=0.7,
        backend_latency_ms=80.0,
    )
    sys_modest = make_system(now, cache_capacity_bytes=1000, cache_usage_bytes=850)
    p_modest = controller.compute_pressure(wl_modest, sys_modest)
    assert p_modest > 0.65

    d_modest = controller.recommend(wl_modest, sys_modest, 100, 5000, mode="continuous")
    scale_up_modest = (d_modest.recommended_capacity_bytes - 1000) / 1000

    # Extreme scale-up (higher pressure)
    wl_high = make_workload(
        now,
        request_rate=1000.0,
        hit_rate=0.05,
        miss_rate=0.95,
        backend_latency_ms=300.0,
    )
    sys_high = make_system(now, cache_capacity_bytes=1000, cache_usage_bytes=980)
    p_high = controller.compute_pressure(wl_high, sys_high)
    assert p_high > p_modest

    d_high = controller.recommend(wl_high, sys_high, 100, 5000, mode="continuous")
    scale_up_high = (d_high.recommended_capacity_bytes - 1000) / 1000

    assert scale_up_high > scale_up_modest
    assert 0.05 <= scale_up_modest <= 0.35
    assert 0.05 <= scale_up_high <= 0.35


def test_lower_pressure_produces_a_larger_scale_down_percentage(
    controller: CapacityController, now: datetime
) -> None:
    """Requirement 14: lower pressure produces a larger scale-down percentage."""
    # Modest contraction: P_cap just below 0.45
    wl_mild = make_workload(
        now,
        request_rate=90.0,
        hit_rate=0.85,
        miss_rate=0.15,
        backend_latency_ms=25.0,
    )
    sys_mild = make_system(now, cache_capacity_bytes=1000, cache_usage_bytes=300)
    p_mild = controller.compute_pressure(wl_mild, sys_mild)
    assert p_mild < 0.45

    d_mild = controller.recommend(wl_mild, sys_mild, 100, 5000, mode="continuous")
    scale_down_mild = (1000 - d_mild.recommended_capacity_bytes) / 1000

    # Severe contraction: very low pressure (near 0)
    wl_severe = make_workload(
        now, request_rate=5.0, hit_rate=0.99, miss_rate=0.01, backend_latency_ms=1.0
    )
    sys_severe = make_system(now, cache_capacity_bytes=1000, cache_usage_bytes=50)
    p_severe = controller.compute_pressure(wl_severe, sys_severe)
    assert p_severe < p_mild

    d_severe = controller.recommend(wl_severe, sys_severe, 100, 5000, mode="continuous")
    scale_down_severe = (1000 - d_severe.recommended_capacity_bytes) / 1000

    assert scale_down_severe > scale_down_mild
    assert 0.05 <= scale_down_mild <= 0.25
    assert 0.05 <= scale_down_severe <= 0.25


def test_scale_up_result_respects_maximum_capacity(
    controller: CapacityController, now: datetime
) -> None:
    """Requirement 15: scale-up result respects maximum capacity."""
    wl = make_workload(
        now, request_rate=1000.0, miss_rate=0.9, backend_latency_ms=200.0
    )
    sys = make_system(now, cache_capacity_bytes=1000, cache_usage_bytes=950)

    # Max capacity only allows expansion to 1080
    decision = controller.recommend(
        wl, sys, min_capacity_bytes=500, max_capacity_bytes=1080, mode="continuous"
    )
    assert decision.capacity_action == CapacityAction.SCALE_UP
    assert decision.recommended_capacity_bytes == 1080


def test_scale_down_result_respects_minimum_capacity(
    controller: CapacityController, now: datetime
) -> None:
    """Requirement 16: scale-down result respects minimum capacity."""
    wl = make_workload(
        now, request_rate=5.0, hit_rate=0.99, miss_rate=0.01, backend_latency_ms=1.0
    )
    sys = make_system(now, cache_capacity_bytes=1000, cache_usage_bytes=50)

    # Min capacity only allows contraction down to 960
    decision = controller.recommend(
        wl, sys, min_capacity_bytes=960, max_capacity_bytes=2000, mode="continuous"
    )
    assert decision.capacity_action == CapacityAction.SCALE_DOWN
    assert decision.recommended_capacity_bytes == 960


def test_very_small_capacities_remain_valid(
    controller: CapacityController, now: datetime
) -> None:
    """Requirement 17: very small capacities remain valid."""
    wl_up = make_workload(
        now, request_rate=500.0, miss_rate=0.9, backend_latency_ms=200.0
    )
    sys_small = make_system(now, cache_capacity_bytes=10, cache_usage_bytes=9)
    d_up = controller.recommend(
        wl_up, sys_small, min_capacity_bytes=1, max_capacity_bytes=50, mode="continuous"
    )

    assert d_up.capacity_action == CapacityAction.SCALE_UP
    assert isinstance(d_up.recommended_capacity_bytes, int)
    assert 1 <= d_up.recommended_capacity_bytes <= 50

    wl_down = make_workload(
        now, request_rate=1.0, hit_rate=0.99, miss_rate=0.01, backend_latency_ms=1.0
    )
    d_down = controller.recommend(
        wl_down,
        sys_small,
        min_capacity_bytes=1,
        max_capacity_bytes=50,
        mode="continuous",
    )

    assert d_down.capacity_action == CapacityAction.SCALE_DOWN
    assert isinstance(d_down.recommended_capacity_bytes, int)
    assert 1 <= d_down.recommended_capacity_bytes <= 10


def test_ceil_floor_behavior_is_deterministic(
    controller: CapacityController, now: datetime
) -> None:
    """Requirement 18: ceil/floor behavior is deterministic."""
    wl_up = make_workload(
        now, request_rate=200.0, miss_rate=0.7, backend_latency_ms=100.0
    )
    sys = make_system(now, cache_capacity_bytes=1003, cache_usage_bytes=900)

    p_up = controller.compute_pressure(wl_up, sys)
    scale_up_pct = 0.05 + 0.30 * ((p_up - 0.65) / 0.35)
    expected_ceil = math.ceil(1003 * (1.0 + scale_up_pct))

    d_up = controller.recommend(wl_up, sys, 100, 5000, mode="continuous")
    assert d_up.recommended_capacity_bytes == expected_ceil

    wl_down = make_workload(
        now, request_rate=10.0, hit_rate=0.95, miss_rate=0.05, backend_latency_ms=5.0
    )
    sys_low = make_system(now, cache_capacity_bytes=1003, cache_usage_bytes=100)

    p_down = controller.compute_pressure(wl_down, sys_low)
    scale_down_pct = 0.05 + 0.20 * ((0.45 - p_down) / 0.45)
    expected_floor = math.floor(1003 * (1.0 - scale_down_pct))

    d_down = controller.recommend(wl_down, sys_low, 100, 5000, mode="continuous")
    assert d_down.recommended_capacity_bytes == expected_floor


def test_rule_based_mode_preserves_the_old_behavior(
    controller: CapacityController, now: datetime
) -> None:
    """Requirement 19: rule_based mode preserves the old behavior."""
    # 1. High utilization >= 85% and miss > 20% -> +20% (1200)
    wl_up = make_workload(now, miss_rate=0.25)
    sys_up = make_system(now, cache_capacity_bytes=1000, cache_usage_bytes=850)
    d_up = controller.recommend(wl_up, sys_up, 100, 5000, mode="rule_based")
    assert d_up.capacity_action == CapacityAction.SCALE_UP
    assert d_up.recommended_capacity_bytes == 1200
    assert d_up.metadata["capacity_mode"] == "rule_based"

    # 2. Low utilization <= 40% and hit >= 80% -> -15% (850)
    wl_down = make_workload(now, hit_rate=0.85, miss_rate=0.15)
    sys_down = make_system(now, cache_capacity_bytes=1000, cache_usage_bytes=300)
    d_down = controller.recommend(wl_down, sys_down, 100, 5000, mode="rule_based")
    assert d_down.capacity_action == CapacityAction.SCALE_DOWN
    assert d_down.recommended_capacity_bytes == 850
    assert d_down.metadata["capacity_mode"] == "rule_based"


def test_continuous_mode_is_the_default(
    controller: CapacityController, now: datetime
) -> None:
    """Requirement 20: continuous mode is the default on CapacityController."""
    workload = make_workload(now)
    system = make_system(now)

    decision = controller.recommend(workload, system, 100, 2000)
    assert decision.metadata is not None
    assert decision.metadata.get("capacity_mode") == "continuous"


def test_decision_engine_exposes_capacity_pressure_in_metadata(now: datetime) -> None:
    """Requirement 21: DecisionEngine exposes capacity_pressure in metadata."""
    engine = DecisionEngine()
    objs = {
        "k1": CacheObject(
            key="k1",
            size_bytes=100,
            access_count=10,
            last_accessed=now,
            retrieval_cost_ms=50.0,
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
    )
    assert "capacity_pressure" in decision.metadata
    p = decision.metadata["capacity_pressure"]
    assert isinstance(p, float)
    assert 0.0 <= p <= 1.0
    assert "capacity_mode" in decision.metadata
    assert "target_capacity_bytes" in decision.metadata


def test_decision_engine_recommended_capacity_bytes_remains_contract_compatible(
    now: datetime,
) -> None:
    """Requirement 22: DecisionEngine recommended_capacity_bytes remains contract-compatible."""
    engine = DecisionEngine()
    objs = {
        "k1": CacheObject(
            key="k1",
            size_bytes=100,
            access_count=10,
            last_accessed=now,
            retrieval_cost_ms=50.0,
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
    )
    assert isinstance(decision.recommended_capacity_bytes, int)
    assert 500 <= decision.recommended_capacity_bytes <= 2000
    assert decision.capacity_action in (
        CapacityAction.SCALE_UP,
        CapacityAction.SCALE_DOWN,
        CapacityAction.MAINTAIN,
    )
