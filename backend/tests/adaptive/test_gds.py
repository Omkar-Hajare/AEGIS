"""Unit tests for Greedy-Dual-Size (GDS) inspired baseline cache eviction policy.

Tests priority ranking (retrieval_cost_ms / size_bytes), zero-size handling,
zero-cost handling, capacity freeing, tie-breaking, immutability, determinism,
and cross-policy comparisons against LRU and LFU.
"""

from datetime import datetime, timedelta, timezone

import pytest

from backend.adaptive.policies.gds import GDSPolicy
from backend.adaptive.policies.lfu import LFUPolicy
from backend.adaptive.policies.lru import LRUPolicy
from contracts.schemas.cache import CacheObject


@pytest.fixture
def policy() -> GDSPolicy:
    """Fixture providing a fresh GDSPolicy instance."""
    return GDSPolicy()


@pytest.fixture
def now() -> datetime:
    """Fixture providing a fixed timezone-aware timestamp."""
    return datetime(2026, 9, 4, 12, 0, 0, tzinfo=timezone.utc)


def make_obj(
    key: str,
    size_bytes: int,
    now: datetime,
    access_count: int = 1,
    retrieval_cost_ms: float = 1.0,
) -> CacheObject:
    """Helper to create a CacheObject with key matching."""
    return CacheObject(
        key=key,
        size_bytes=size_bytes,
        access_count=access_count,
        last_accessed=now,
        retrieval_cost_ms=retrieval_cost_ms,
    )


# ---------------------------------------------------------------------------
# Core GDS Priority Eviction Tests
# ---------------------------------------------------------------------------


def test_empty_objects_returns_empty_list(policy: GDSPolicy) -> None:
    """Empty object dictionary returns an empty list."""
    assert policy.select_evictions({}, 1000) == []


def test_under_capacity_returns_empty_list(policy: GDSPolicy, now: datetime) -> None:
    """Under-capacity cache returns an empty list without evicting anything."""
    objects = {
        "A": make_obj("A", 200, now, retrieval_cost_ms=50.0),
        "B": make_obj("B", 300, now, retrieval_cost_ms=10.0),
    }
    assert policy.select_evictions(objects, 600) == []


def test_exact_capacity_returns_empty_list(policy: GDSPolicy, now: datetime) -> None:
    """Cache exactly at capacity returns an empty list."""
    objects = {
        "A": make_obj("A", 250, now, retrieval_cost_ms=25.0),
        "B": make_obj("B", 250, now, retrieval_cost_ms=50.0),
    }
    assert policy.select_evictions(objects, 500) == []


def test_lowest_priority_selected_first(policy: GDSPolicy, now: datetime) -> None:
    """Lowest cost/size priority is evicted first."""
    # pri(cheap_large) = 10 / 500 = 0.02
    # pri(costly_small) = 200 / 100 = 2.0
    # pri(moderate) = 50 / 200 = 0.25
    objects = {
        "cheap_large": make_obj("cheap_large", 500, now, retrieval_cost_ms=10.0),
        "costly_small": make_obj("costly_small", 100, now, retrieval_cost_ms=200.0),
        "moderate": make_obj("moderate", 200, now, retrieval_cost_ms=50.0),
    }
    # usage = 800, target = 500, bytes_to_free = 300. cheap_large frees 500 >= 300.
    evicted = policy.select_evictions(objects, 500)
    assert evicted == ["cheap_large"]


def test_higher_priority_retained_when_lower_are_sufficient(
    policy: GDSPolicy, now: datetime
) -> None:
    """High cost/size objects are retained when lower priority frees enough."""
    # A: pri = 5 / 100 = 0.05
    # B: pri = 20 / 100 = 0.20
    # C: pri = 500 / 100 = 5.00
    objects = {
        "A": make_obj("A", 100, now, retrieval_cost_ms=5.0),
        "B": make_obj("B", 100, now, retrieval_cost_ms=20.0),
        "C": make_obj("C", 100, now, retrieval_cost_ms=500.0),
    }
    # usage = 300, target = 200, bytes_to_free = 100.
    evicted = policy.select_evictions(objects, 200)
    assert evicted == ["A"]
    assert "B" not in evicted
    assert "C" not in evicted


def test_zero_size_receives_infinite_priority_and_never_preferred(
    policy: GDSPolicy, now: datetime
) -> None:
    """Zero-size object receives priority inf so positive-sized objects evict first."""
    objects = {
        "zero_byte": make_obj("zero_byte", 0, now, retrieval_cost_ms=0.0),
        "normal": make_obj("normal", 200, now, retrieval_cost_ms=100.0),
    }
    # usage = 200, target = 100, bytes_to_free = 100.
    # normal has pri 0.5, zero_byte has pri inf. normal is evicted.
    evicted = policy.select_evictions(objects, 100)
    assert evicted == ["normal"]
    assert "zero_byte" not in evicted


def test_zero_retrieval_cost_produces_zero_priority(
    policy: GDSPolicy, now: datetime
) -> None:
    """retrieval_cost_ms=0 with size > 0 yields priority 0.0 and evicts first."""
    objects = {
        "free_obj": make_obj("free_obj", 200, now, retrieval_cost_ms=0.0),
        "costly_obj": make_obj("costly_obj", 200, now, retrieval_cost_ms=50.0),
    }
    # usage = 400, target = 250, bytes_to_free = 150. free_obj has pri 0.0.
    evicted = policy.select_evictions(objects, 250)
    assert evicted == ["free_obj"]


def test_equal_priorities_broken_by_ascending_key(
    policy: GDSPolicy, now: datetime
) -> None:
    """Objects with identical GDS priority are evicted in ascending key order."""
    objects = {
        "z_key": make_obj("z_key", 100, now, retrieval_cost_ms=10.0),
        "a_key": make_obj("a_key", 100, now, retrieval_cost_ms=10.0),
        "m_key": make_obj("m_key", 100, now, retrieval_cost_ms=10.0),
    }
    # all pri = 0.10. usage = 300, target = 150, bytes_to_free = 150.
    evicted = policy.select_evictions(objects, 150)
    assert evicted == ["a_key", "m_key"]


def test_multiple_objects_selected_when_necessary(
    policy: GDSPolicy, now: datetime
) -> None:
    """Multiple objects are selected until bytes_to_free is met."""
    # p1: 10/100 = 0.10, p2: 20/100 = 0.20, p3: 30/100 = 0.30, p4: 400/100 = 4.0
    objects = {
        "p1": make_obj("p1", 100, now, retrieval_cost_ms=10.0),
        "p2": make_obj("p2", 100, now, retrieval_cost_ms=20.0),
        "p3": make_obj("p3", 100, now, retrieval_cost_ms=30.0),
        "p4": make_obj("p4", 100, now, retrieval_cost_ms=400.0),
    }
    # usage = 400, target = 150, bytes_to_free = 250.
    # p1(100) + p2(100) + p3(100) = 300 >= 250.
    evicted = policy.select_evictions(objects, 150)
    assert evicted == ["p1", "p2", "p3"]


def test_gds_specification_example(policy: GDSPolicy, now: datetime) -> None:
    """Verify GDS example from specification."""
    objects = {
        "A": make_obj("A", 1000, now, retrieval_cost_ms=100.0),
        "B": make_obj("B", 100, now, retrieval_cost_ms=100.0),
        "C": make_obj("C", 100, now, retrieval_cost_ms=50.0),
    }
    # pri(A) = 0.10, pri(B) = 1.00, pri(C) = 0.50.
    # usage = 1200, target = 1000, bytes_to_free = 200.
    # A alone frees 1000 >= 200.
    evicted = policy.select_evictions(objects, 1000)
    assert evicted == ["A"]


def test_returned_keys_are_unique_and_in_input(
    policy: GDSPolicy, now: datetime
) -> None:
    """Every returned eviction key is unique and belongs to input objects."""
    objects = {
        f"k_{i}": make_obj(f"k_{i}", 100, now, retrieval_cost_ms=float(i + 1))
        for i in range(10)
    }
    evicted = policy.select_evictions(objects, 500)
    assert len(evicted) == len(set(evicted))
    for k in evicted:
        assert k in objects


# ---------------------------------------------------------------------------
# Immutability & Determinism Tests
# ---------------------------------------------------------------------------


def test_input_objects_mapping_is_not_mutated(policy: GDSPolicy, now: datetime) -> None:
    """The input dictionary is never modified by the policy."""
    objects = {
        "A": make_obj("A", 300, now, retrieval_cost_ms=10.0),
        "B": make_obj("B", 400, now, retrieval_cost_ms=20.0),
    }
    keys_before = list(objects.keys())
    policy.select_evictions(objects, 200)
    assert list(objects.keys()) == keys_before


def test_cache_object_instances_are_not_mutated(
    policy: GDSPolicy, now: datetime
) -> None:
    """CacheObject instances are not modified during eviction selection."""
    obj_a = make_obj("A", 300, now, retrieval_cost_ms=10.0)
    obj_b = make_obj("B", 400, now, retrieval_cost_ms=20.0)
    dump_a = obj_a.model_dump()
    dump_b = obj_b.model_dump()

    policy.select_evictions({"A": obj_a, "B": obj_b}, 200)

    assert obj_a.model_dump() == dump_a
    assert obj_b.model_dump() == dump_b


def test_determinism_same_input_produces_identical_output(
    policy: GDSPolicy, now: datetime
) -> None:
    """Multiple invocations with identical inputs produce identical results."""
    objects = {
        f"k_{i}": make_obj(f"k_{i}", 100, now, retrieval_cost_ms=float(i + 1))
        for i in range(5)
    }
    res1 = policy.select_evictions(objects, 200)
    res2 = policy.select_evictions(objects, 200)
    assert res1 == res2


def test_callable_syntax_matches_method(policy: GDSPolicy, now: datetime) -> None:
    """Policy instance is directly callable."""
    objects = {
        "A": make_obj("A", 300, now, retrieval_cost_ms=10.0),
        "B": make_obj("B", 400, now, retrieval_cost_ms=20.0),
    }
    res1 = policy(objects, 200)
    res2 = policy.select_evictions(objects, 200)
    assert res1 == res2


# ---------------------------------------------------------------------------
# Validation & Error Handling Tests
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("invalid_capacity", [0, -1, -500])
def test_non_positive_target_capacity_raises_error(
    policy: GDSPolicy, now: datetime, invalid_capacity: int
) -> None:
    """target_capacity_bytes <= 0 raises an error."""
    objects = {"A": make_obj("A", 100, now)}
    with pytest.raises((ValueError, TypeError)):
        policy.select_evictions(objects, invalid_capacity)


@pytest.mark.parametrize("bad_arg", [True, False])
def test_boolean_target_capacity_raises_error(
    policy: GDSPolicy, now: datetime, bad_arg: bool
) -> None:
    """Boolean target_capacity_bytes raises an error."""
    objects = {"A": make_obj("A", 100, now)}
    with pytest.raises((ValueError, TypeError)):
        policy.select_evictions(objects, bad_arg)  # type: ignore[arg-type]


@pytest.mark.parametrize("invalid_type", ["1000", 500.5, None, [100]])
def test_non_integer_target_capacity_raises_error(
    policy: GDSPolicy, now: datetime, invalid_type: object
) -> None:
    """Non-integer target_capacity_bytes raises an error."""
    objects = {"A": make_obj("A", 100, now)}
    with pytest.raises((ValueError, TypeError)):
        policy.select_evictions(objects, invalid_type)  # type: ignore[arg-type]


def test_non_mapping_objects_raises_error(policy: GDSPolicy) -> None:
    """Non-mapping objects argument raises an error."""
    with pytest.raises((ValueError, TypeError)):
        policy.select_evictions(["not_a_mapping"], 100)  # type: ignore[arg-type]


def test_non_cache_object_value_raises_error(policy: GDSPolicy) -> None:
    """Non-CacheObject dictionary value raises an error."""
    with pytest.raises((ValueError, TypeError)):
        policy.select_evictions({"A": "not_an_obj"}, 100)  # type: ignore[arg-type]


def test_mapping_key_mismatch_raises_error(policy: GDSPolicy, now: datetime) -> None:
    """Mapping key not matching obj.key raises an error."""
    obj = make_obj("real_key", 100, now)
    with pytest.raises((ValueError, TypeError)):
        policy.select_evictions({"mismatched_key": obj}, 50)


# ---------------------------------------------------------------------------
# Cross-Policy Behavior Tests
# ---------------------------------------------------------------------------


def test_cross_policy_all_three_accept_same_interface(now: datetime) -> None:
    """All three policies accept the same objects and target capacity interface."""
    objects = {
        "A": make_obj("A", 200, now, access_count=5, retrieval_cost_ms=10.0),
        "B": make_obj("B", 300, now, access_count=10, retrieval_cost_ms=50.0),
    }
    lru = LRUPolicy()
    lfu = LFUPolicy()
    gds = GDSPolicy()

    # Under-capacity
    assert lru.select_evictions(objects, 600) == []
    assert lfu.select_evictions(objects, 600) == []
    assert gds.select_evictions(objects, 600) == []

    # Over-capacity: usage = 500, target = 250, bytes_to_free = 250
    # For all three, evicting either A or B is a valid list of keys
    for p in [lru, lfu, gds]:
        evicted = p.select_evictions(objects, 250)
        assert isinstance(evicted, list)
        assert len(evicted) > 0


def test_cross_policy_different_evictions_under_different_policies(
    now: datetime,
) -> None:
    """Same workload produces different eviction choices under LRU, LFU, and GDS."""
    t_old = now - timedelta(hours=10)
    t_mid = now - timedelta(hours=5)
    t_recent = now

    # A: oldest (LRU candidate), high freq (100), high pri (100/100 = 1.0)
    # B: low freq (1) (LFU candidate), recent (t_recent), high pri (100/100 = 1.0)
    # C: mid recency (t_mid), mid freq (50), low pri (1/100 = 0.01) (GDS candidate)
    objects = {
        "A": CacheObject(
            key="A",
            size_bytes=100,
            access_count=100,
            last_accessed=t_old,
            retrieval_cost_ms=100.0,
        ),
        "B": CacheObject(
            key="B",
            size_bytes=100,
            access_count=1,
            last_accessed=t_recent,
            retrieval_cost_ms=100.0,
        ),
        "C": CacheObject(
            key="C",
            size_bytes=100,
            access_count=50,
            last_accessed=t_mid,
            retrieval_cost_ms=1.0,
        ),
    }
    # usage = 300, target = 200, bytes_to_free = 100.
    # LRU should evict oldest: A
    # LFU should evict lowest frequency: B
    # GDS should evict lowest cost/size priority: C
    lru_evicted = LRUPolicy().select_evictions(objects, 200)
    lfu_evicted = LFUPolicy().select_evictions(objects, 200)
    gds_evicted = GDSPolicy().select_evictions(objects, 200)

    assert lru_evicted == ["A"]
    assert lfu_evicted == ["B"]
    assert gds_evicted == ["C"]
