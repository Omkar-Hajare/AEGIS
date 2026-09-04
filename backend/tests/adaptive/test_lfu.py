"""Unit tests for Least Frequently Used (LFU) baseline cache eviction policy.

Tests frequency ranking, zero-count behavior, capacity freeing, tie-breaking,
bounds validation, immutability, and determinism.
"""

from datetime import datetime, timezone

import pytest

from backend.adaptive.policies.lfu import LFUPolicy
from contracts.schemas.cache import CacheObject


@pytest.fixture
def policy() -> LFUPolicy:
    """Fixture providing a fresh LFUPolicy instance."""
    return LFUPolicy()


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
    hit_count: int | None = None,
    miss_count: int | None = None,
) -> CacheObject:
    """Helper to create a CacheObject with key matching."""
    return CacheObject(
        key=key,
        size_bytes=size_bytes,
        access_count=access_count,
        last_accessed=now,
        retrieval_cost_ms=retrieval_cost_ms,
        hit_count=hit_count,
        miss_count=miss_count,
    )


# ---------------------------------------------------------------------------
# Core LFU Eviction Tests
# ---------------------------------------------------------------------------


def test_empty_objects_returns_empty_list(policy: LFUPolicy) -> None:
    """Empty object dictionary returns an empty list."""
    assert policy.select_evictions({}, 1000) == []


def test_under_capacity_returns_empty_list(policy: LFUPolicy, now: datetime) -> None:
    """Under-capacity cache returns an empty list without evicting anything."""
    objects = {
        "A": make_obj("A", 200, now, access_count=10),
        "B": make_obj("B", 300, now, access_count=5),
    }
    assert policy.select_evictions(objects, 600) == []


def test_exact_capacity_returns_empty_list(policy: LFUPolicy, now: datetime) -> None:
    """Cache exactly at capacity returns an empty list."""
    objects = {
        "A": make_obj("A", 250, now, access_count=10),
        "B": make_obj("B", 250, now, access_count=5),
    }
    assert policy.select_evictions(objects, 500) == []


def test_single_lowest_frequency_object_satisfies_capacity(
    policy: LFUPolicy, now: datetime
) -> None:
    """Lowest frequency object is evicted first and alone frees required bytes."""
    objects = {
        "A": make_obj("A", 300, now, access_count=2),
        "B": make_obj("B", 200, now, access_count=10),
        "C": make_obj("C", 200, now, access_count=20),
    }
    # usage = 700, target = 500, bytes_to_free = 200. A frees 300 >= 200.
    evicted = policy.select_evictions(objects, 500)
    assert evicted == ["A"]


def test_multiple_lowest_frequency_objects_selected_when_necessary(
    policy: LFUPolicy, now: datetime
) -> None:
    """Evicts lowest frequency objects in order until required capacity is freed."""
    objects = {
        "popular": make_obj("popular", 300, now, access_count=100),
        "low1": make_obj("low1", 100, now, access_count=2),
        "low2": make_obj("low2", 150, now, access_count=5),
        "low3": make_obj("low3", 200, now, access_count=8),
    }
    # usage = 750, target = 450, bytes_to_free = 300.
    # low1 frees 100, low2 frees 150 (total 250), low3 frees 200 (total 450 >= 300).
    evicted = policy.select_evictions(objects, 450)
    assert evicted == ["low1", "low2", "low3"]


def test_zero_access_count_evicted_first(policy: LFUPolicy, now: datetime) -> None:
    """access_count=0 is valid and evicted before any positive access count."""
    objects = {
        "never_used": make_obj("never_used", 200, now, access_count=0),
        "used_once": make_obj("used_once", 200, now, access_count=1),
        "used_many": make_obj("used_many", 200, now, access_count=10),
    }
    # usage = 600, target = 450, bytes_to_free = 150.
    evicted = policy.select_evictions(objects, 450)
    assert evicted == ["never_used"]


def test_all_objects_evicted_when_target_capacity_is_very_low(
    policy: LFUPolicy, now: datetime
) -> None:
    """All objects are selected when target capacity is smaller than any subset."""
    objects = {
        "A": make_obj("A", 100, now, access_count=5),
        "B": make_obj("B", 100, now, access_count=10),
    }
    evicted = policy.select_evictions(objects, 1)
    assert evicted == ["A", "B"]


def test_higher_frequency_objects_retained_when_lower_are_sufficient(
    policy: LFUPolicy, now: datetime
) -> None:
    """Higher frequency objects retained when lower frequency ones satisfy capacity."""
    objects = {
        "infrequent": make_obj("infrequent", 400, now, access_count=1),
        "moderate": make_obj("moderate", 300, now, access_count=50),
        "frequent": make_obj("frequent", 500, now, access_count=500),
    }
    # usage = 1200, target = 800, bytes_to_free = 400.
    evicted = policy.select_evictions(objects, 800)
    assert evicted == ["infrequent"]
    assert "moderate" not in evicted
    assert "frequent" not in evicted


def test_equal_access_counts_broken_by_ascending_key(
    policy: LFUPolicy, now: datetime
) -> None:
    """Objects with identical access_count are evicted in ascending key order."""
    objects = {
        "z_key": make_obj("z_key", 100, now, access_count=5),
        "a_key": make_obj("a_key", 100, now, access_count=5),
        "m_key": make_obj("m_key", 100, now, access_count=5),
    }
    # usage = 300, target = 150, bytes_to_free = 150.
    evicted = policy.select_evictions(objects, 150)
    assert evicted == ["a_key", "m_key"]


def test_hit_count_and_miss_count_do_not_override_access_count(
    policy: LFUPolicy, now: datetime
) -> None:
    """access_count is the primary signal; hit/miss not used for LFU ranking."""
    objects = {
        "A": make_obj("A", 200, now, access_count=2, hit_count=100, miss_count=100),
        "B": make_obj("B", 200, now, access_count=5, hit_count=0, miss_count=0),
    }
    # usage = 400, target = 250, bytes_to_free = 150. A has lower access_count.
    evicted = policy.select_evictions(objects, 250)
    assert evicted == ["A"]


def test_returned_keys_are_unique_and_in_input(
    policy: LFUPolicy, now: datetime
) -> None:
    """Every returned eviction key is unique and belongs to input objects."""
    objects = {
        f"k_{i}": make_obj(f"k_{i}", 100, now, access_count=i) for i in range(10)
    }
    evicted = policy.select_evictions(objects, 500)
    assert len(evicted) == len(set(evicted))
    for k in evicted:
        assert k in objects


def test_lfu_specification_example(policy: LFUPolicy, now: datetime) -> None:
    """Verify LFU example from specification."""
    objects = {
        "A": make_obj("A", 300, now, access_count=10),
        "B": make_obj("B", 400, now, access_count=2),
        "C": make_obj("C", 200, now, access_count=5),
    }
    # usage = 900, target = 400, bytes_to_free = 500 -> B(400) + C(200) = 600 >= 500
    evicted = policy.select_evictions(objects, 400)
    assert evicted == ["B", "C"]


# ---------------------------------------------------------------------------
# Immutability & Determinism Tests
# ---------------------------------------------------------------------------


def test_input_objects_mapping_is_not_mutated(policy: LFUPolicy, now: datetime) -> None:
    """The input dictionary is never modified by the policy."""
    objects = {
        "A": make_obj("A", 300, now, access_count=2),
        "B": make_obj("B", 400, now, access_count=5),
    }
    keys_before = list(objects.keys())
    policy.select_evictions(objects, 200)
    assert list(objects.keys()) == keys_before


def test_cache_object_instances_are_not_mutated(
    policy: LFUPolicy, now: datetime
) -> None:
    """CacheObject instances are not modified during eviction selection."""
    obj_a = make_obj("A", 300, now, access_count=2)
    obj_b = make_obj("B", 400, now, access_count=5)
    dump_a = obj_a.model_dump()
    dump_b = obj_b.model_dump()

    policy.select_evictions({"A": obj_a, "B": obj_b}, 200)

    assert obj_a.model_dump() == dump_a
    assert obj_b.model_dump() == dump_b


def test_determinism_same_input_produces_identical_output(
    policy: LFUPolicy, now: datetime
) -> None:
    """Multiple invocations with identical inputs produce identical results."""
    objects = {f"k_{i}": make_obj(f"k_{i}", 100, now, access_count=i) for i in range(5)}
    res1 = policy.select_evictions(objects, 200)
    res2 = policy.select_evictions(objects, 200)
    assert res1 == res2


def test_callable_syntax_matches_method(policy: LFUPolicy, now: datetime) -> None:
    """Policy instance is directly callable."""
    objects = {
        "A": make_obj("A", 300, now, access_count=2),
        "B": make_obj("B", 400, now, access_count=5),
    }
    res1 = policy(objects, 200)
    res2 = policy.select_evictions(objects, 200)
    assert res1 == res2


# ---------------------------------------------------------------------------
# Validation & Error Handling Tests
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("invalid_capacity", [0, -1, -500])
def test_non_positive_target_capacity_raises_error(
    policy: LFUPolicy, now: datetime, invalid_capacity: int
) -> None:
    """target_capacity_bytes <= 0 raises an error."""
    objects = {"A": make_obj("A", 100, now)}
    with pytest.raises((ValueError, TypeError)):
        policy.select_evictions(objects, invalid_capacity)


@pytest.mark.parametrize("bad_arg", [True, False])
def test_boolean_target_capacity_raises_error(
    policy: LFUPolicy, now: datetime, bad_arg: bool
) -> None:
    """Boolean target_capacity_bytes raises an error."""
    objects = {"A": make_obj("A", 100, now)}
    with pytest.raises((ValueError, TypeError)):
        policy.select_evictions(objects, bad_arg)  # type: ignore[arg-type]


@pytest.mark.parametrize("invalid_type", ["1000", 500.5, None, [100]])
def test_non_integer_target_capacity_raises_error(
    policy: LFUPolicy, now: datetime, invalid_type: object
) -> None:
    """Non-integer target_capacity_bytes raises an error."""
    objects = {"A": make_obj("A", 100, now)}
    with pytest.raises((ValueError, TypeError)):
        policy.select_evictions(objects, invalid_type)  # type: ignore[arg-type]


def test_non_mapping_objects_raises_error(policy: LFUPolicy) -> None:
    """Non-mapping objects argument raises an error."""
    with pytest.raises((ValueError, TypeError)):
        policy.select_evictions(["not_a_mapping"], 100)  # type: ignore[arg-type]


def test_non_cache_object_value_raises_error(policy: LFUPolicy) -> None:
    """Non-CacheObject dictionary value raises an error."""
    with pytest.raises((ValueError, TypeError)):
        policy.select_evictions({"A": "not_an_obj"}, 100)  # type: ignore[arg-type]


def test_mapping_key_mismatch_raises_error(policy: LFUPolicy, now: datetime) -> None:
    """Mapping key not matching obj.key raises an error."""
    obj = make_obj("real_key", 100, now)
    with pytest.raises((ValueError, TypeError)):
        policy.select_evictions({"mismatched_key": obj}, 50)
