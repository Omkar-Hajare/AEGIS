"""Unit tests for Least Recently Used (LRU) baseline cache eviction policy.

Tests recency ranking, capacity freeing, tie-breaking, bounds validation,
immutability, and determinism.
"""

from datetime import datetime, timedelta, timezone

import pytest

from backend.adaptive.policies.lru import LRUPolicy
from contracts.schemas.cache import CacheObject


@pytest.fixture
def policy() -> LRUPolicy:
    """Fixture providing a fresh LRUPolicy instance."""
    return LRUPolicy()


@pytest.fixture
def now() -> datetime:
    """Fixture providing a fixed timezone-aware timestamp."""
    return datetime(2026, 9, 4, 12, 0, 0, tzinfo=timezone.utc)


def make_obj(
    key: str,
    size_bytes: int,
    last_accessed: datetime,
    access_count: int = 1,
    retrieval_cost_ms: float = 1.0,
) -> CacheObject:
    """Helper to create a CacheObject with key matching."""
    return CacheObject(
        key=key,
        size_bytes=size_bytes,
        access_count=access_count,
        last_accessed=last_accessed,
        retrieval_cost_ms=retrieval_cost_ms,
    )


# ---------------------------------------------------------------------------
# Core LRU Eviction Tests
# ---------------------------------------------------------------------------


def test_empty_objects_returns_empty_list(policy: LRUPolicy) -> None:
    """Empty object dictionary returns an empty list."""
    assert policy.select_evictions({}, 1000) == []


def test_under_capacity_returns_empty_list(policy: LRUPolicy, now: datetime) -> None:
    """Under-capacity cache returns an empty list without evicting anything."""
    objects = {
        "A": make_obj("A", 200, now),
        "B": make_obj("B", 300, now),
    }
    assert policy.select_evictions(objects, 600) == []


def test_exact_capacity_returns_empty_list(policy: LRUPolicy, now: datetime) -> None:
    """Cache exactly at capacity returns an empty list."""
    objects = {
        "A": make_obj("A", 250, now),
        "B": make_obj("B", 250, now),
    }
    assert policy.select_evictions(objects, 500) == []


def test_single_oldest_object_satisfies_capacity(
    policy: LRUPolicy, now: datetime
) -> None:
    """Oldest accessed object is evicted first and alone frees required bytes."""
    t0 = now - timedelta(minutes=20)
    t1 = now - timedelta(minutes=10)
    t2 = now

    objects = {
        "A": make_obj("A", 300, t0),
        "B": make_obj("B", 200, t1),
        "C": make_obj("C", 200, t2),
    }
    # usage = 700, target = 500, bytes_to_free = 200. A frees 300 >= 200.
    evicted = policy.select_evictions(objects, 500)
    assert evicted == ["A"]


def test_multiple_oldest_objects_selected_when_necessary(
    policy: LRUPolicy, now: datetime
) -> None:
    """Evicts oldest objects in order until required capacity is freed."""
    t0 = now - timedelta(minutes=30)
    t1 = now - timedelta(minutes=20)
    t2 = now - timedelta(minutes=10)
    t3 = now

    objects = {
        "A": make_obj("A", 100, t0),
        "B": make_obj("B", 150, t1),
        "C": make_obj("C", 200, t2),
        "D": make_obj("D", 300, t3),
    }
    # usage = 750, target = 450, bytes_to_free = 300.
    # A frees 100, B frees 150 (total 250 < 300), C frees 200 (total 450 >= 300).
    evicted = policy.select_evictions(objects, 450)
    assert evicted == ["A", "B", "C"]


def test_all_objects_evicted_when_target_capacity_is_very_low(
    policy: LRUPolicy, now: datetime
) -> None:
    """All objects are selected when target capacity is smaller than any subset."""
    t0 = now - timedelta(minutes=10)
    t1 = now

    objects = {
        "A": make_obj("A", 100, t0),
        "B": make_obj("B", 100, t1),
    }
    evicted = policy.select_evictions(objects, 1)
    assert evicted == ["A", "B"]


def test_newest_objects_retained_when_older_are_sufficient(
    policy: LRUPolicy, now: datetime
) -> None:
    """Newest objects are preserved when older objects satisfy the freed bytes."""
    t_old = now - timedelta(hours=2)
    t_mid = now - timedelta(hours=1)
    t_new = now

    objects = {
        "fresh": make_obj("fresh", 500, t_new),
        "mid": make_obj("mid", 300, t_mid),
        "stale": make_obj("stale", 400, t_old),
    }
    # usage = 1200, target = 800, bytes_to_free = 400. Stale frees 400.
    evicted = policy.select_evictions(objects, 800)
    assert evicted == ["stale"]
    assert "fresh" not in evicted
    assert "mid" not in evicted


def test_equal_timestamps_broken_by_ascending_key(
    policy: LRUPolicy, now: datetime
) -> None:
    """Objects with identical last_accessed are evicted in ascending key order."""
    objects = {
        "z_key": make_obj("z_key", 100, now),
        "a_key": make_obj("a_key", 100, now),
        "m_key": make_obj("m_key", 100, now),
    }
    # usage = 300, target = 150, bytes_to_free = 150.
    # a_key frees 100, m_key frees 100 (total 200 >= 150).
    evicted = policy.select_evictions(objects, 150)
    assert evicted == ["a_key", "m_key"]


def test_returned_keys_are_unique_and_in_input(
    policy: LRUPolicy, now: datetime
) -> None:
    """Every returned eviction key is unique and belongs to input objects."""
    objects = {
        f"k_{i}": make_obj(f"k_{i}", 100, now - timedelta(minutes=i)) for i in range(10)
    }
    evicted = policy.select_evictions(objects, 500)
    assert len(evicted) == len(set(evicted))
    for k in evicted:
        assert k in objects


def test_lru_specification_example(policy: LRUPolicy) -> None:
    """Verify LRU example from specification."""
    t_1000 = datetime(2026, 9, 4, 10, 0, tzinfo=timezone.utc)
    t_1005 = datetime(2026, 9, 4, 10, 5, tzinfo=timezone.utc)
    t_1010 = datetime(2026, 9, 4, 10, 10, tzinfo=timezone.utc)

    objects = {
        "A": make_obj("A", 300, t_1000),
        "B": make_obj("B", 400, t_1005),
        "C": make_obj("C", 200, t_1010),
    }
    # usage = 900, target = 400, bytes_to_free = 500 -> A(300) + B(400) = 700 >= 500
    evicted = policy.select_evictions(objects, 400)
    assert evicted == ["A", "B"]


# ---------------------------------------------------------------------------
# Immutability & Determinism Tests
# ---------------------------------------------------------------------------


def test_input_objects_mapping_is_not_mutated(policy: LRUPolicy, now: datetime) -> None:
    """The input dictionary is never modified by the policy."""
    objects = {
        "A": make_obj("A", 300, now - timedelta(minutes=5)),
        "B": make_obj("B", 400, now),
    }
    keys_before = list(objects.keys())
    policy.select_evictions(objects, 200)
    assert list(objects.keys()) == keys_before


def test_cache_object_instances_are_not_mutated(
    policy: LRUPolicy, now: datetime
) -> None:
    """CacheObject instances are not modified during eviction selection."""
    obj_a = make_obj("A", 300, now - timedelta(minutes=5))
    obj_b = make_obj("B", 400, now)
    dump_a = obj_a.model_dump()
    dump_b = obj_b.model_dump()

    policy.select_evictions({"A": obj_a, "B": obj_b}, 200)

    assert obj_a.model_dump() == dump_a
    assert obj_b.model_dump() == dump_b


def test_determinism_same_input_produces_identical_output(
    policy: LRUPolicy, now: datetime
) -> None:
    """Multiple invocations with identical inputs produce identical results."""
    objects = {
        f"k_{i}": make_obj(f"k_{i}", 100, now - timedelta(minutes=i)) for i in range(5)
    }
    res1 = policy.select_evictions(objects, 200)
    res2 = policy.select_evictions(objects, 200)
    assert res1 == res2


def test_callable_syntax_matches_method(policy: LRUPolicy, now: datetime) -> None:
    """Policy instance is directly callable."""
    objects = {
        "A": make_obj("A", 300, now - timedelta(minutes=5)),
        "B": make_obj("B", 400, now),
    }
    res1 = policy(objects, 200)
    res2 = policy.select_evictions(objects, 200)
    assert res1 == res2


# ---------------------------------------------------------------------------
# Validation & Error Handling Tests
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("invalid_capacity", [0, -1, -500])
def test_non_positive_target_capacity_raises_error(
    policy: LRUPolicy, now: datetime, invalid_capacity: int
) -> None:
    """target_capacity_bytes <= 0 raises an error."""
    objects = {"A": make_obj("A", 100, now)}
    with pytest.raises((ValueError, TypeError)):
        policy.select_evictions(objects, invalid_capacity)


@pytest.mark.parametrize("bad_arg", [True, False])
def test_boolean_target_capacity_raises_error(
    policy: LRUPolicy, now: datetime, bad_arg: bool
) -> None:
    """Boolean target_capacity_bytes raises an error."""
    objects = {"A": make_obj("A", 100, now)}
    with pytest.raises((ValueError, TypeError)):
        policy.select_evictions(objects, bad_arg)  # type: ignore[arg-type]


@pytest.mark.parametrize("invalid_type", ["1000", 500.5, None, [100]])
def test_non_integer_target_capacity_raises_error(
    policy: LRUPolicy, now: datetime, invalid_type: object
) -> None:
    """Non-integer target_capacity_bytes raises an error."""
    objects = {"A": make_obj("A", 100, now)}
    with pytest.raises((ValueError, TypeError)):
        policy.select_evictions(objects, invalid_type)  # type: ignore[arg-type]


def test_non_mapping_objects_raises_error(policy: LRUPolicy) -> None:
    """Non-mapping objects argument raises an error."""
    with pytest.raises((ValueError, TypeError)):
        policy.select_evictions(["not_a_mapping"], 100)  # type: ignore[arg-type]


def test_non_cache_object_value_raises_error(policy: LRUPolicy) -> None:
    """Non-CacheObject dictionary value raises an error."""
    with pytest.raises((ValueError, TypeError)):
        policy.select_evictions({"A": "not_an_obj"}, 100)  # type: ignore[arg-type]


def test_mapping_key_mismatch_raises_error(policy: LRUPolicy, now: datetime) -> None:
    """Mapping key not matching obj.key raises an error."""
    obj = make_obj("real_key", 100, now)
    with pytest.raises((ValueError, TypeError)):
        policy.select_evictions({"mismatched_key": obj}, 50)
