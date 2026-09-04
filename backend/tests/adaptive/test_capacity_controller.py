"""Unit tests for CapacityController in the Adaptive Cache System.

Tests all scaling rules, edge cases, thresholds, bounds clamping, input validation,
immutability invariants, and determinism.
"""

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
    """High utilization (>=85%) with miss_rate > 20% triggers SCALE_UP."""
    workload = make_workload(now, hit_rate=0.70, miss_rate=0.30)
    system = make_system(now, cache_capacity_bytes=1000, cache_usage_bytes=850)

    decision = controller.recommend(workload, system, 500, 2000)

    assert decision.capacity_action == CapacityAction.SCALE_UP
    assert decision.recommended_capacity_bytes == 1200
    assert decision.reason == REASON_SCALE_UP_PRESSURE


def test_critical_utilization_returns_scale_up_even_when_miss_rate_is_low(
    controller: CapacityController, now: datetime
) -> None:
    """Critical utilization (>=90%) triggers SCALE_UP even when miss_rate is low."""
    workload = make_workload(now, hit_rate=0.95, miss_rate=0.05)
    system = make_system(now, cache_capacity_bytes=1000, cache_usage_bytes=900)

    decision = controller.recommend(workload, system, 500, 2000)

    assert decision.capacity_action == CapacityAction.SCALE_UP
    assert decision.recommended_capacity_bytes == 1200
    assert decision.reason == REASON_SCALE_UP_CRITICAL


def test_utilization_between_scale_up_and_scale_down_regions_returns_maintain(
    controller: CapacityController, now: datetime
) -> None:
    """Utilization between 40% and 85% returns MAINTAIN with current capacity."""
    workload = make_workload(now, hit_rate=0.70, miss_rate=0.30)
    system = make_system(now, cache_capacity_bytes=1000, cache_usage_bytes=600)

    decision = controller.recommend(workload, system, 500, 2000)

    assert decision.capacity_action == CapacityAction.MAINTAIN
    assert decision.recommended_capacity_bytes == 1000
    assert decision.reason == REASON_MAINTAIN_NORMAL


def test_low_utilization_with_strong_hit_rate_returns_scale_down(
    controller: CapacityController, now: datetime
) -> None:
    """Low utilization (<=40%) with hit_rate >= 80% triggers SCALE_DOWN."""
    workload = make_workload(now, hit_rate=0.90, miss_rate=0.10)
    system = make_system(now, cache_capacity_bytes=1000, cache_usage_bytes=300)

    decision = controller.recommend(workload, system, 500, 2000)

    assert decision.capacity_action == CapacityAction.SCALE_DOWN
    assert decision.recommended_capacity_bytes == 850
    assert decision.reason == REASON_SCALE_DOWN_LOW_UTILIZATION


def test_low_utilization_without_strong_hit_rate_returns_maintain(
    controller: CapacityController, now: datetime
) -> None:
    """Low utilization (<=40%) without hit_rate >= 80% returns MAINTAIN."""
    workload = make_workload(now, hit_rate=0.75, miss_rate=0.25)
    system = make_system(now, cache_capacity_bytes=1000, cache_usage_bytes=300)

    decision = controller.recommend(workload, system, 500, 2000)

    assert decision.capacity_action == CapacityAction.MAINTAIN
    assert decision.recommended_capacity_bytes == 1000
    assert decision.reason == REASON_MAINTAIN_NORMAL


# ---------------------------------------------------------------------------
# Capacity Calculation & Rounding Tests
# ---------------------------------------------------------------------------


def test_scale_up_recommendation_increases_capacity_by_twenty_percent(
    controller: CapacityController, now: datetime
) -> None:
    """Scale-up increases capacity by exactly ceil(current * 1.20)."""
    workload = make_workload(now, miss_rate=0.25)
    system = make_system(now, cache_capacity_bytes=1000, cache_usage_bytes=900)

    decision = controller.recommend(workload, system, 100, 5000)
    assert decision.recommended_capacity_bytes == 1200


def test_scale_up_rounding_uses_ceil(
    controller: CapacityController, now: datetime
) -> None:
    """Scale-up on fractional result uses math.ceil."""
    workload = make_workload(now, miss_rate=0.25)
    # 1001 * 1.20 = 1201.2 -> ceil is 1202
    system = make_system(now, cache_capacity_bytes=1001, cache_usage_bytes=950)

    decision = controller.recommend(workload, system, 100, 5000)
    assert decision.recommended_capacity_bytes == 1202


def test_scale_down_recommendation_decreases_capacity_by_fifteen_percent(
    controller: CapacityController, now: datetime
) -> None:
    """Scale-down decreases capacity by exactly floor(current * 0.85)."""
    workload = make_workload(now, hit_rate=0.85, miss_rate=0.15)
    system = make_system(now, cache_capacity_bytes=1000, cache_usage_bytes=200)

    decision = controller.recommend(workload, system, 100, 5000)
    assert decision.recommended_capacity_bytes == 850


def test_scale_down_rounding_uses_floor(
    controller: CapacityController, now: datetime
) -> None:
    """Scale-down on fractional result uses math.floor."""
    workload = make_workload(now, hit_rate=0.85, miss_rate=0.15)
    # 1001 * 0.85 = 850.85 -> floor is 850
    system = make_system(now, cache_capacity_bytes=1001, cache_usage_bytes=200)

    decision = controller.recommend(workload, system, 100, 5000)
    assert decision.recommended_capacity_bytes == 850


def test_maintain_preserves_current_capacity(
    controller: CapacityController, now: datetime
) -> None:
    """MAINTAIN action preserves exact current capacity."""
    workload = make_workload(now, hit_rate=0.60, miss_rate=0.40)
    system = make_system(now, cache_capacity_bytes=1420, cache_usage_bytes=710)

    decision = controller.recommend(workload, system, 100, 5000)
    assert decision.recommended_capacity_bytes == 1420


# ---------------------------------------------------------------------------
# Bounds Clamping Tests
# ---------------------------------------------------------------------------


def test_scale_up_capacity_is_capped_at_max_capacity(
    controller: CapacityController, now: datetime
) -> None:
    """Recommended scale-up capacity never exceeds max_capacity_bytes."""
    workload = make_workload(now, miss_rate=0.30)
    # 1000 * 1.20 = 1200, but max is 1100
    system = make_system(now, cache_capacity_bytes=1000, cache_usage_bytes=900)

    decision = controller.recommend(workload, system, 500, 1100)
    assert decision.capacity_action == CapacityAction.SCALE_UP
    assert decision.recommended_capacity_bytes == 1100


def test_scale_down_capacity_is_floored_at_min_capacity(
    controller: CapacityController, now: datetime
) -> None:
    """Recommended scale-down capacity never goes below min_capacity_bytes."""
    workload = make_workload(now, hit_rate=0.90)
    # 1000 * 0.85 = 850, but min is 900
    system = make_system(now, cache_capacity_bytes=1000, cache_usage_bytes=200)

    decision = controller.recommend(workload, system, 900, 2000)
    assert decision.capacity_action == CapacityAction.SCALE_DOWN
    assert decision.recommended_capacity_bytes == 900


def test_maintain_clamped_if_current_outside_bounds(
    controller: CapacityController, now: datetime
) -> None:
    """MAINTAIN clamps capacity if current capacity falls outside [min, max]."""
    workload = make_workload(now, hit_rate=0.50, miss_rate=0.50)
    system = make_system(now, cache_capacity_bytes=300, cache_usage_bytes=150)

    # Current capacity 300 is below min 500
    decision = controller.recommend(workload, system, 500, 1000)
    assert decision.capacity_action == CapacityAction.MAINTAIN
    assert decision.recommended_capacity_bytes == 500


def test_min_capacity_equals_max_capacity_clamps_strictly(
    controller: CapacityController, now: datetime
) -> None:
    """When min_capacity == max_capacity, recommended capacity is strictly locked."""
    workload = make_workload(now, miss_rate=0.50)
    system = make_system(now, cache_capacity_bytes=1000, cache_usage_bytes=950)

    decision = controller.recommend(workload, system, 1000, 1000)
    assert decision.recommended_capacity_bytes == 1000


# ---------------------------------------------------------------------------
# Priority Order Tests
# ---------------------------------------------------------------------------


def test_scale_up_takes_priority_when_multiple_conditions_are_true(
    controller: CapacityController, now: datetime
) -> None:
    """Scale-up conditions take priority over any scale-down conditions."""
    # Critical utilization >= 90% with high hit rate >= 80%
    workload = make_workload(now, hit_rate=0.95, miss_rate=0.05)
    system = make_system(now, cache_capacity_bytes=1000, cache_usage_bytes=950)

    decision = controller.recommend(workload, system, 500, 2000)
    assert decision.capacity_action == CapacityAction.SCALE_UP
    assert decision.recommended_capacity_bytes == 1200


# ---------------------------------------------------------------------------
# Exact Boundary Threshold Tests
# ---------------------------------------------------------------------------


def test_exact_threshold_eighty_five_percent_utilization_with_miss_rate(
    controller: CapacityController, now: datetime
) -> None:
    """Exact utilization threshold 85% triggers SCALE_UP when miss_rate > 20%."""
    workload = make_workload(now, miss_rate=0.21)
    system = make_system(now, cache_capacity_bytes=1000, cache_usage_bytes=850)

    decision = controller.recommend(workload, system, 500, 2000)
    assert decision.capacity_action == CapacityAction.SCALE_UP
    assert decision.recommended_capacity_bytes == 1200


def test_exact_threshold_ninety_percent_utilization(
    controller: CapacityController, now: datetime
) -> None:
    """Exact utilization threshold 90% triggers SCALE_UP."""
    workload = make_workload(now, miss_rate=0.05)
    system = make_system(now, cache_capacity_bytes=1000, cache_usage_bytes=900)

    decision = controller.recommend(workload, system, 500, 2000)
    assert decision.capacity_action == CapacityAction.SCALE_UP
    assert decision.recommended_capacity_bytes == 1200


def test_exact_threshold_forty_percent_utilization(
    controller: CapacityController, now: datetime
) -> None:
    """Exact utilization threshold 40% triggers SCALE_DOWN when hit_rate >= 80%."""
    workload = make_workload(now, hit_rate=0.80)
    system = make_system(now, cache_capacity_bytes=1000, cache_usage_bytes=400)

    decision = controller.recommend(workload, system, 500, 2000)
    assert decision.capacity_action == CapacityAction.SCALE_DOWN
    assert decision.recommended_capacity_bytes == 850


def test_exact_threshold_forty_one_percent_utilization_does_not_scale_down(
    controller: CapacityController, now: datetime
) -> None:
    """Utilization just above 40% (41%) does not trigger SCALE_DOWN."""
    workload = make_workload(now, hit_rate=0.90)
    system = make_system(now, cache_capacity_bytes=1000, cache_usage_bytes=410)

    decision = controller.recommend(workload, system, 500, 2000)
    assert decision.capacity_action == CapacityAction.MAINTAIN
    assert decision.recommended_capacity_bytes == 1000


def test_exact_hit_rate_threshold_eighty_percent(
    controller: CapacityController, now: datetime
) -> None:
    """Exact hit rate 80% (>= 0.80) triggers SCALE_DOWN when low utilization."""
    workload = make_workload(now, hit_rate=0.80)
    system = make_system(now, cache_capacity_bytes=1000, cache_usage_bytes=350)

    decision = controller.recommend(workload, system, 500, 2000)
    assert decision.capacity_action == CapacityAction.SCALE_DOWN
    assert decision.recommended_capacity_bytes == 850


def test_hit_rate_below_eighty_percent_does_not_scale_down(
    controller: CapacityController, now: datetime
) -> None:
    """Hit rate below 80% (79.9%) does not trigger SCALE_DOWN."""
    workload = make_workload(now, hit_rate=0.799)
    system = make_system(now, cache_capacity_bytes=1000, cache_usage_bytes=350)

    decision = controller.recommend(workload, system, 500, 2000)
    assert decision.capacity_action == CapacityAction.MAINTAIN
    assert decision.recommended_capacity_bytes == 1000


def test_exact_miss_rate_threshold_twenty_percent(
    controller: CapacityController, now: datetime
) -> None:
    """Exact miss rate 20% (not > 20%) does NOT trigger SCALE_UP at 85% utilization."""
    workload = make_workload(now, hit_rate=0.80, miss_rate=0.20)
    system = make_system(now, cache_capacity_bytes=1000, cache_usage_bytes=850)

    decision = controller.recommend(workload, system, 500, 2000)
    assert decision.capacity_action == CapacityAction.MAINTAIN
    assert decision.recommended_capacity_bytes == 1000


def test_miss_rate_strictly_greater_than_twenty_percent_triggers_scale_up(
    controller: CapacityController, now: datetime
) -> None:
    """Miss rate strictly > 20% (e.g. 20.1%) triggers SCALE_UP at 85% utilization."""
    workload = make_workload(now, hit_rate=0.79, miss_rate=0.201)
    system = make_system(now, cache_capacity_bytes=1000, cache_usage_bytes=850)

    decision = controller.recommend(workload, system, 500, 2000)
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

    decision = controller.recommend(workload, system, 500, 2000)
    assert decision.capacity_action == CapacityAction.SCALE_UP
    assert decision.recommended_capacity_bytes == 1200


def test_spec_boundary_example_two(
    controller: CapacityController, now: datetime
) -> None:
    """Boundary Example 2 from spec: usage=900, capacity=1000, hit=0.95, miss=0.05."""
    workload = make_workload(now, hit_rate=0.95, miss_rate=0.05)
    system = make_system(now, cache_capacity_bytes=1000, cache_usage_bytes=900)

    decision = controller.recommend(workload, system, 500, 2000)
    assert decision.capacity_action == CapacityAction.SCALE_UP
    assert decision.recommended_capacity_bytes == 1200


def test_spec_boundary_example_three(
    controller: CapacityController, now: datetime
) -> None:
    """Boundary Example 3 from spec: usage=300, capacity=1000, hit=0.90, miss=0.10."""
    workload = make_workload(now, hit_rate=0.90, miss_rate=0.10)
    system = make_system(now, cache_capacity_bytes=1000, cache_usage_bytes=300)

    decision = controller.recommend(workload, system, 500, 2000)
    assert decision.capacity_action == CapacityAction.SCALE_DOWN
    assert decision.recommended_capacity_bytes == 850


def test_spec_boundary_example_four(
    controller: CapacityController, now: datetime
) -> None:
    """Boundary Example 4 from spec: usage=600, capacity=1000, hit=0.70, miss=0.30."""
    workload = make_workload(now, hit_rate=0.70, miss_rate=0.30)
    system = make_system(now, cache_capacity_bytes=1000, cache_usage_bytes=600)

    decision = controller.recommend(workload, system, 500, 2000)
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
    )
    d_down = controller.recommend(
        make_workload(now, hit_rate=0.90, miss_rate=0.10),
        make_system(now, cache_capacity_bytes=1000, cache_usage_bytes=300),
        100,
        2000,
    )
    d_maintain = controller.recommend(
        make_workload(now, hit_rate=0.60, miss_rate=0.40),
        make_system(now, cache_capacity_bytes=1000, cache_usage_bytes=600),
        100,
        2000,
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
