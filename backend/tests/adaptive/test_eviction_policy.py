"""Unit tests for the capacity-driven EvictionPolicy.

Verifies deterministic eviction selection, capacity arithmetic, sorting,
error handling, and input immutability.
"""

from copy import deepcopy
from datetime import datetime, timezone

import pytest

from backend.adaptive.eviction import EvictionPolicy
from contracts.schemas import CacheObject


@pytest.fixture
def policy() -> EvictionPolicy:
    """Provides a fresh EvictionPolicy instance."""
    return EvictionPolicy()


@pytest.fixture
def now() -> datetime:
    """Provides a consistent timezone-aware timestamp for CacheObject fixtures."""
    return datetime(2026, 9, 4, 12, 0, 0, tzinfo=timezone.utc)


def test_under_capacity_cache_returns_empty_list(
    policy: EvictionPolicy, now: datetime
) -> None:
    """Under-capacity cache (usage < target) returns []."""
    objects = {
        "A": CacheObject(
            key="A",
            size_bytes=200,
            access_count=5,
            last_accessed=now,
            retrieval_cost_ms=10.0,
        ),
        "B": CacheObject(
            key="B",
            size_bytes=300,
            access_count=2,
            last_accessed=now,
            retrieval_cost_ms=15.0,
        ),
    }
    scores = {"A": 0.80, "B": 0.40}
    # usage = 500, target = 1000 -> under capacity
    assert policy.select_evictions(scores, objects, 1000) == []


def test_exactly_at_capacity_cache_returns_empty_list(
    policy: EvictionPolicy, now: datetime
) -> None:
    """Exactly-at-capacity cache (usage == target) returns []."""
    objects = {
        "A": CacheObject(
            key="A",
            size_bytes=500,
            access_count=1,
            last_accessed=now,
            retrieval_cost_ms=10.0,
        ),
        "B": CacheObject(
            key="B",
            size_bytes=500,
            access_count=1,
            last_accessed=now,
            retrieval_cost_ms=10.0,
        ),
    }
    scores = {"A": 0.50, "B": 0.50}
    # usage = 1000, target = 1000
    assert policy.select_evictions(scores, objects, 1000) == []


def test_over_capacity_single_lowest_scoring_eviction(
    policy: EvictionPolicy, now: datetime
) -> None:
    """Example 1 from specification: over-capacity cache evicts lowest score.

    Eviction stops when sufficient bytes are freed.
    """
    objects = {
        "A": CacheObject(
            key="A",
            size_bytes=300,
            access_count=1,
            last_accessed=now,
            retrieval_cost_ms=1.0,
        ),
        "B": CacheObject(
            key="B",
            size_bytes=400,
            access_count=1,
            last_accessed=now,
            retrieval_cost_ms=1.0,
        ),
        "C": CacheObject(
            key="C",
            size_bytes=200,
            access_count=1,
            last_accessed=now,
            retrieval_cost_ms=1.0,
        ),
        "D": CacheObject(
            key="D",
            size_bytes=300,
            access_count=1,
            last_accessed=now,
            retrieval_cost_ms=1.0,
        ),
    }
    scores = {"A": 0.90, "B": 0.20, "C": 0.40, "D": 0.70}
    # usage = 1200, target = 1000, bytes_to_free = 200. B frees 400.
    evictions = policy.select_evictions(scores, objects, 1000)
    assert evictions == ["B"]


def test_over_capacity_multiple_lowest_scoring_evictions(
    policy: EvictionPolicy, now: datetime
) -> None:
    """Example 3 from specification: evicts multiple lowest-scoring objects.

    Continues until required bytes are freed.
    """
    objects = {
        "A": CacheObject(
            key="A",
            size_bytes=150,
            access_count=1,
            last_accessed=now,
            retrieval_cost_ms=1.0,
        ),
        "B": CacheObject(
            key="B",
            size_bytes=150,
            access_count=1,
            last_accessed=now,
            retrieval_cost_ms=1.0,
        ),
        "C": CacheObject(
            key="C",
            size_bytes=150,
            access_count=1,
            last_accessed=now,
            retrieval_cost_ms=1.0,
        ),
    }
    scores = {"A": 0.10, "B": 0.20, "C": 0.30}
    # usage = 450, target = 200, bytes_to_free = 250 -> A(150) + B(150) = 300 >= 250
    evictions = policy.select_evictions(scores, objects, 200)
    assert evictions == ["A", "B"]


def test_larger_object_satisfies_freed_capacity_by_itself(
    policy: EvictionPolicy, now: datetime
) -> None:
    """A larger object with low score can satisfy the entire required capacity alone."""
    objects = {
        "heavy_low": CacheObject(
            key="heavy_low",
            size_bytes=600,
            access_count=1,
            last_accessed=now,
            retrieval_cost_ms=1.0,
        ),
        "light_mid": CacheObject(
            key="light_mid",
            size_bytes=100,
            access_count=1,
            last_accessed=now,
            retrieval_cost_ms=1.0,
        ),
        "light_high": CacheObject(
            key="light_high",
            size_bytes=100,
            access_count=1,
            last_accessed=now,
            retrieval_cost_ms=1.0,
        ),
    }
    scores = {"heavy_low": 0.10, "light_mid": 0.50, "light_high": 0.90}
    # usage = 800, target = 500, bytes_to_free = 300. heavy_low frees 600.
    evictions = policy.select_evictions(scores, objects, 500)
    assert evictions == ["heavy_low"]


def test_objects_selected_by_lowest_score_first(
    policy: EvictionPolicy, now: datetime
) -> None:
    """Objects are strictly evicted in ascending score order."""
    objects = {
        "k1": CacheObject(
            key="k1",
            size_bytes=100,
            access_count=1,
            last_accessed=now,
            retrieval_cost_ms=1.0,
        ),
        "k2": CacheObject(
            key="k2",
            size_bytes=100,
            access_count=1,
            last_accessed=now,
            retrieval_cost_ms=1.0,
        ),
        "k3": CacheObject(
            key="k3",
            size_bytes=100,
            access_count=1,
            last_accessed=now,
            retrieval_cost_ms=1.0,
        ),
        "k4": CacheObject(
            key="k4",
            size_bytes=100,
            access_count=1,
            last_accessed=now,
            retrieval_cost_ms=1.0,
        ),
    }
    scores = {"k1": 0.85, "k2": 0.15, "k3": 0.65, "k4": 0.35}
    # usage = 400, target = 100, bytes_to_free = 300
    # order must be k2 (0.15), k4 (0.35), k3 (0.65)
    evictions = policy.select_evictions(scores, objects, 100)
    assert evictions == ["k2", "k4", "k3"]


def test_equal_scores_resolved_deterministically_by_ascending_key(
    policy: EvictionPolicy, now: datetime
) -> None:
    """Ties in score are broken deterministically by ascending object key."""
    objects = {
        "delta": CacheObject(
            key="delta",
            size_bytes=100,
            access_count=1,
            last_accessed=now,
            retrieval_cost_ms=1.0,
        ),
        "alpha": CacheObject(
            key="alpha",
            size_bytes=100,
            access_count=1,
            last_accessed=now,
            retrieval_cost_ms=1.0,
        ),
        "charlie": CacheObject(
            key="charlie",
            size_bytes=100,
            access_count=1,
            last_accessed=now,
            retrieval_cost_ms=1.0,
        ),
        "bravo": CacheObject(
            key="bravo",
            size_bytes=100,
            access_count=1,
            last_accessed=now,
            retrieval_cost_ms=1.0,
        ),
    }
    # All equal scores
    scores = {"delta": 0.30, "alpha": 0.30, "charlie": 0.30, "bravo": 0.30}
    # usage = 400, target = 200, bytes_to_free = 200 -> must select alpha then bravo
    evictions = policy.select_evictions(scores, objects, 200)
    assert evictions == ["alpha", "bravo"]


def test_returned_keys_are_unique(policy: EvictionPolicy, now: datetime) -> None:
    """Returned eviction list contains unique keys."""
    objects = {
        f"item_{i}": CacheObject(
            key=f"item_{i}",
            size_bytes=50,
            access_count=1,
            last_accessed=now,
            retrieval_cost_ms=1.0,
        )
        for i in range(10)
    }
    scores = {f"item_{i}": i * 0.1 for i in range(10)}
    # usage = 500, target = 200, bytes_to_free = 300 -> evicts 6 items
    evictions = policy.select_evictions(scores, objects, 200)
    assert len(evictions) == len(set(evictions))


def test_returned_keys_correspond_only_to_supplied_objects(
    policy: EvictionPolicy, now: datetime
) -> None:
    """All returned eviction keys must exist in the supplied objects mapping."""
    objects = {
        "x": CacheObject(
            key="x",
            size_bytes=300,
            access_count=1,
            last_accessed=now,
            retrieval_cost_ms=1.0,
        ),
        "y": CacheObject(
            key="y",
            size_bytes=300,
            access_count=1,
            last_accessed=now,
            retrieval_cost_ms=1.0,
        ),
    }
    scores = {"x": 0.20, "y": 0.80}
    evictions = policy.select_evictions(scores, objects, 200)
    for k in evictions:
        assert k in objects


def test_empty_objects_and_scores_returns_empty_list(
    policy: EvictionPolicy,
) -> None:
    """Empty objects and scores return []."""
    assert policy.select_evictions({}, {}, 500) == []


def test_missing_score_for_an_object_raises_value_error(
    policy: EvictionPolicy, now: datetime
) -> None:
    """If an object is missing a score in scores, raises ValueError."""
    objects = {
        "k1": CacheObject(
            key="k1",
            size_bytes=100,
            access_count=1,
            last_accessed=now,
            retrieval_cost_ms=1.0,
        ),
        "k2": CacheObject(
            key="k2",
            size_bytes=100,
            access_count=1,
            last_accessed=now,
            retrieval_cost_ms=1.0,
        ),
    }
    scores = {"k1": 0.50}  # k2 missing
    with pytest.raises(ValueError, match="Missing scores"):
        policy.select_evictions(scores, objects, 100)


def test_score_for_unknown_object_raises_value_error(
    policy: EvictionPolicy, now: datetime
) -> None:
    """If a score exists for a key not in objects, raises ValueError."""
    objects = {
        "k1": CacheObject(
            key="k1",
            size_bytes=100,
            access_count=1,
            last_accessed=now,
            retrieval_cost_ms=1.0,
        )
    }
    scores = {"k1": 0.50, "k2": 0.70}  # k2 not in objects
    with pytest.raises(ValueError, match="unknown objects"):
        policy.select_evictions(scores, objects, 50)


def test_score_below_zero_raises_value_error(
    policy: EvictionPolicy, now: datetime
) -> None:
    """Score < 0.0 raises ValueError."""
    objects = {
        "k1": CacheObject(
            key="k1",
            size_bytes=100,
            access_count=1,
            last_accessed=now,
            retrieval_cost_ms=1.0,
        )
    }
    scores = {"k1": -0.05}
    with pytest.raises(ValueError, match=r"\[0\.0, 1\.0\]"):
        policy.select_evictions(scores, objects, 50)


def test_score_above_one_raises_value_error(
    policy: EvictionPolicy, now: datetime
) -> None:
    """Score > 1.0 raises ValueError."""
    objects = {
        "k1": CacheObject(
            key="k1",
            size_bytes=100,
            access_count=1,
            last_accessed=now,
            retrieval_cost_ms=1.0,
        )
    }
    scores = {"k1": 1.05}
    with pytest.raises(ValueError, match=r"\[0\.0, 1\.0\]"):
        policy.select_evictions(scores, objects, 50)


def test_boolean_score_raises_value_error(
    policy: EvictionPolicy, now: datetime
) -> None:
    """Boolean score raises ValueError."""
    objects = {
        "k1": CacheObject(
            key="k1",
            size_bytes=100,
            access_count=1,
            last_accessed=now,
            retrieval_cost_ms=1.0,
        )
    }
    scores = {"k1": True}
    with pytest.raises(ValueError, match="numeric"):
        policy.select_evictions(scores, objects, 50)


def test_non_numeric_score_raises_value_error(
    policy: EvictionPolicy, now: datetime
) -> None:
    """String/non-numeric score raises ValueError."""
    objects = {
        "k1": CacheObject(
            key="k1",
            size_bytes=100,
            access_count=1,
            last_accessed=now,
            retrieval_cost_ms=1.0,
        )
    }
    scores = {"k1": "low"}
    with pytest.raises(ValueError, match="numeric"):
        policy.select_evictions(scores, objects, 50)


def test_boolean_target_capacity_raises_value_error(
    policy: EvictionPolicy, now: datetime
) -> None:
    """Boolean target_capacity_bytes raises ValueError."""
    objects = {
        "k1": CacheObject(
            key="k1",
            size_bytes=100,
            access_count=1,
            last_accessed=now,
            retrieval_cost_ms=1.0,
        )
    }
    scores = {"k1": 0.50}
    with pytest.raises(ValueError, match="numeric"):
        policy.select_evictions(scores, objects, True)  # type: ignore[arg-type]


@pytest.mark.parametrize("invalid_capacity", [0, -1, -500])
def test_non_positive_target_capacity_raises_value_error(
    policy: EvictionPolicy, now: datetime, invalid_capacity: int
) -> None:
    """target_capacity_bytes <= 0 raises ValueError."""
    objects = {
        "k1": CacheObject(
            key="k1",
            size_bytes=100,
            access_count=1,
            last_accessed=now,
            retrieval_cost_ms=1.0,
        )
    }
    scores = {"k1": 0.50}
    with pytest.raises(ValueError, match="greater than 0"):
        policy.select_evictions(scores, objects, invalid_capacity)


def test_input_scores_mapping_is_not_mutated(
    policy: EvictionPolicy, now: datetime
) -> None:
    """scores dictionary is not mutated."""
    objects = {
        "k1": CacheObject(
            key="k1",
            size_bytes=200,
            access_count=1,
            last_accessed=now,
            retrieval_cost_ms=1.0,
        )
    }
    original_scores = {"k1": 0.20}
    copied_scores = deepcopy(original_scores)

    policy.select_evictions(original_scores, objects, 100)
    assert original_scores == copied_scores


def test_input_objects_mapping_is_not_mutated(
    policy: EvictionPolicy, now: datetime
) -> None:
    """objects dictionary is not mutated."""
    obj1 = CacheObject(
        key="k1",
        size_bytes=200,
        access_count=1,
        last_accessed=now,
        retrieval_cost_ms=1.0,
    )
    original_objects = {"k1": obj1}
    copied_objects = dict(original_objects)

    policy.select_evictions({"k1": 0.20}, original_objects, 100)
    assert list(original_objects.keys()) == list(copied_objects.keys())


def test_cache_object_instances_are_not_mutated(
    policy: EvictionPolicy, now: datetime
) -> None:
    """CacheObject attributes are unchanged after eviction selection."""
    obj = CacheObject(
        key="k1",
        size_bytes=200,
        access_count=5,
        last_accessed=now,
        retrieval_cost_ms=15.0,
        features={"score": 0.2},
        metadata={"tag": "demo"},
    )
    objects = {"k1": obj}
    policy.select_evictions({"k1": 0.20}, objects, 100)

    assert obj.key == "k1"
    assert obj.size_bytes == 200
    assert obj.access_count == 5
    assert obj.last_accessed == now
    assert obj.retrieval_cost_ms == 15.0
    assert obj.features == {"score": 0.2}
    assert obj.metadata == {"tag": "demo"}


def test_determinism_same_input_produces_identical_output(
    policy: EvictionPolicy, now: datetime
) -> None:
    """Identical inputs produce identical eviction order."""
    objects = {
        f"k{i}": CacheObject(
            key=f"k{i}",
            size_bytes=100,
            access_count=1,
            last_accessed=now,
            retrieval_cost_ms=1.0,
        )
        for i in range(10)
    }
    scores = {f"k{i}": (i % 3) * 0.3 for i in range(10)}

    res1 = policy.select_evictions(scores, objects, 400)
    res2 = policy.select_evictions(scores, objects, 400)
    assert res1 == res2


def test_selected_objects_free_at_least_bytes_to_free(
    policy: EvictionPolicy, now: datetime
) -> None:
    """The sum of size_bytes of evicted objects must be >= bytes_to_free."""
    objects = {
        "A": CacheObject(
            key="A",
            size_bytes=120,
            access_count=1,
            last_accessed=now,
            retrieval_cost_ms=1.0,
        ),
        "B": CacheObject(
            key="B",
            size_bytes=230,
            access_count=1,
            last_accessed=now,
            retrieval_cost_ms=1.0,
        ),
        "C": CacheObject(
            key="C",
            size_bytes=340,
            access_count=1,
            last_accessed=now,
            retrieval_cost_ms=1.0,
        ),
        "D": CacheObject(
            key="D",
            size_bytes=450,
            access_count=1,
            last_accessed=now,
            retrieval_cost_ms=1.0,
        ),
    }
    scores = {"A": 0.9, "B": 0.3, "C": 0.1, "D": 0.4}
    total_usage = 120 + 230 + 340 + 450  # 1140
    target = 600
    bytes_to_free = total_usage - target  # 540

    evictions = policy.select_evictions(scores, objects, target)
    freed = sum(objects[k].size_bytes for k in evictions)
    assert freed >= bytes_to_free


def test_policy_does_not_evict_when_no_capacity_needs_freeing(
    policy: EvictionPolicy, now: datetime
) -> None:
    """Example 2: target=800, 4 items of 100 bytes each -> evictions = []."""
    objects = {
        "A": CacheObject(
            key="A",
            size_bytes=100,
            access_count=1,
            last_accessed=now,
            retrieval_cost_ms=1.0,
        ),
        "B": CacheObject(
            key="B",
            size_bytes=100,
            access_count=1,
            last_accessed=now,
            retrieval_cost_ms=1.0,
        ),
        "C": CacheObject(
            key="C",
            size_bytes=100,
            access_count=1,
            last_accessed=now,
            retrieval_cost_ms=1.0,
        ),
        "D": CacheObject(
            key="D",
            size_bytes=100,
            access_count=1,
            last_accessed=now,
            retrieval_cost_ms=1.0,
        ),
    }
    scores = {"A": 0.10, "B": 0.10, "C": 0.20, "D": 0.90}
    assert policy.select_evictions(scores, objects, 800) == []


def test_callable_syntax_matches_method(policy: EvictionPolicy, now: datetime) -> None:
    """EvictionPolicy instance can be called directly as a callable."""
    objects = {
        "A": CacheObject(
            key="A",
            size_bytes=200,
            access_count=1,
            last_accessed=now,
            retrieval_cost_ms=1.0,
        )
    }
    scores = {"A": 0.50}
    res1 = policy.select_evictions(scores, objects, 100)
    res2 = policy(scores, objects, 100)
    assert res1 == res2 == ["A"]
