"""Unit tests for the capacity-driven EvictionPolicy.

Verifies deterministic eviction selection, capacity arithmetic, sorting,
error handling, and input immutability.
"""

from copy import deepcopy
from datetime import datetime, timedelta, timezone

import pytest

from backend.adaptive.engine.decision_engine import DecisionEngine
from backend.adaptive.eviction import EvictionPolicy
from backend.adaptive.features.extractor import FeatureExtractor
from backend.adaptive.scoring.scorer import AdaptiveScorer
from backend.cost.model import CostModel
from contracts.schemas import CacheObject
from contracts.schemas.enums import WorkloadType
from contracts.schemas.system import SystemState
from contracts.schemas.workload import WorkloadState


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


# ---------------------------------------------------------------------------
# Step 2: Economic Value Density & Dynamic Retention Tests
# ---------------------------------------------------------------------------


def test_eviction_is_capacity_driven_not_threshold_driven(
    policy: EvictionPolicy, now: datetime
) -> None:
    """Eviction only triggers when usage exceeds capacity, freeing minimal bytes."""
    objects = {
        "obj1": CacheObject(
            key="obj1",
            size_bytes=200,
            access_count=1,
            last_accessed=now,
            retrieval_cost_ms=1.0,
        ),
        "obj2": CacheObject(
            key="obj2",
            size_bytes=200,
            access_count=1,
            last_accessed=now,
            retrieval_cost_ms=1.0,
        ),
    }
    # Even with very low utility score (0.01), if usage <= capacity, no evictions happen
    low_scores = {"obj1": 0.01, "obj2": 0.01}
    assert policy.select_evictions(low_scores, objects, 500) == []
    assert policy.last_value_densities is None

    # When capacity is reduced so bytes_to_free = 100, exactly one object is evicted
    evicted = policy.select_evictions(low_scores, objects, 300)
    assert len(evicted) == 1
    assert evicted == ["obj1"]


def test_lowest_current_value_density_objects_selected_first(
    policy: EvictionPolicy, now: datetime
) -> None:
    """Objects with lowest economic value density are selected first for eviction."""
    objects = {
        "item_high": CacheObject(
            key="item_high",
            size_bytes=100,
            access_count=1,
            last_accessed=now,
            retrieval_cost_ms=10.0,
        ),
        "item_mid": CacheObject(
            key="item_mid",
            size_bytes=100,
            access_count=1,
            last_accessed=now,
            retrieval_cost_ms=10.0,
        ),
        "item_low": CacheObject(
            key="item_low",
            size_bytes=100,
            access_count=1,
            last_accessed=now,
            retrieval_cost_ms=10.0,
        ),
    }
    scores = {"item_high": 0.90, "item_mid": 0.50, "item_low": 0.20}
    # Total usage = 300, target = 200 -> bytes_to_free = 100 (evicts 1)
    evicted = policy.select_evictions(scores, objects, 200)
    assert evicted == ["item_low"]
    assert policy.last_value_densities is not None
    assert (
        policy.last_value_densities["item_low"]
        < policy.last_value_densities["item_mid"]
        < policy.last_value_densities["item_high"]
    )


def test_large_low_value_objects_preferentially_removed_under_high_memory_pressure(
    policy: EvictionPolicy, now: datetime
) -> None:
    """High memory pressure increases size penalty alpha, penalizing large objects."""
    obj_small = CacheObject(
        key="small",
        size_bytes=20,
        access_count=1,
        last_accessed=now,
        retrieval_cost_ms=10.0,
    )
    obj_large = CacheObject(
        key="large",
        size_bytes=200,
        access_count=1,
        last_accessed=now,
        retrieval_cost_ms=10.0,
    )
    scores = {"small": 0.35, "large": 0.60}
    objects = {"small": obj_small, "large": obj_large}

    # Under low memory pressure: alpha is low (0.10), large object retains higher density
    sys_low = SystemState(
        cache_capacity_bytes=100000,
        cache_usage_bytes=100,
        object_count=2,
        window_seconds=60.0,
        timestamp=now,
    )
    evicted_low = policy.select_evictions(scores, objects, 210, system=sys_low)
    assert evicted_low == ["small"]
    assert policy.last_value_densities is not None
    assert policy.last_value_densities["small"] < policy.last_value_densities["large"]

    # Under high memory pressure: alpha is high (0.60), large object density collapses
    sys_high = SystemState(
        cache_capacity_bytes=220,
        cache_usage_bytes=220,
        object_count=2,
        window_seconds=60.0,
        timestamp=now,
    )
    evicted_high = policy.select_evictions(scores, objects, 210, system=sys_high)
    assert evicted_high == ["large"]
    assert policy.last_value_densities is not None
    assert policy.last_value_densities["large"] < policy.last_value_densities["small"]


def test_small_high_value_objects_protected_over_large_low_value_objects(
    policy: EvictionPolicy, now: datetime
) -> None:
    """Small high-utility objects have vastly higher value density than large low-utility objects."""
    small_high = CacheObject(
        key="small_high",
        size_bytes=50,
        access_count=10,
        last_accessed=now,
        retrieval_cost_ms=10.0,
    )
    large_low = CacheObject(
        key="large_low",
        size_bytes=500,
        access_count=1,
        last_accessed=now,
        retrieval_cost_ms=10.0,
    )
    scores = {"small_high": 0.85, "large_low": 0.15}
    objects = {"small_high": small_high, "large_low": large_low}

    # Usage = 550, target = 500 -> bytes_to_free = 50
    evictions = policy.select_evictions(scores, objects, 500)
    assert evictions == ["large_low"]
    assert policy.last_value_densities is not None
    assert (
        policy.last_value_densities["large_low"]
        < policy.last_value_densities["small_high"]
    )


def test_higher_retrieval_cost_protects_object_under_latency_pressure(
    policy: EvictionPolicy, now: datetime
) -> None:
    """High backend latency boosts retention value for costly-to-retrieve objects."""
    obj_cheap = CacheObject(
        key="cheap",
        size_bytes=100,
        access_count=1,
        last_accessed=now,
        retrieval_cost_ms=5.0,
    )
    obj_costly = CacheObject(
        key="costly",
        size_bytes=100,
        access_count=1,
        last_accessed=now,
        retrieval_cost_ms=200.0,
    )
    scores = {"cheap": 0.50, "costly": 0.48}
    objects = {"cheap": obj_cheap, "costly": obj_costly}

    # Under low backend latency (5ms), costly is evicted because raw score is lower
    wl_low = WorkloadState(
        request_rate=100,
        hit_rate=0.5,
        miss_rate=0.5,
        backend_latency_ms=5.0,
        window_seconds=60.0,
        timestamp=now,
    )
    evicted_low = policy.select_evictions(scores, objects, 100, workload=wl_low)
    assert evicted_low == ["costly"]
    assert policy.last_value_densities is not None
    assert policy.last_value_densities["costly"] < policy.last_value_densities["cheap"]

    # Under high backend latency (500ms), costly receives retention boost and is protected
    wl_high = WorkloadState(
        request_rate=100,
        hit_rate=0.5,
        miss_rate=0.5,
        backend_latency_ms=500.0,
        window_seconds=60.0,
        timestamp=now,
    )
    evicted_high = policy.select_evictions(scores, objects, 100, workload=wl_high)
    assert evicted_high == ["cheap"]
    assert policy.last_value_densities is not None
    assert policy.last_value_densities["cheap"] < policy.last_value_densities["costly"]


def test_frequency_recency_and_popularity_protect_via_dynamic_scoring(
    policy: EvictionPolicy, now: datetime
) -> None:
    """Objects with higher access activity receive higher scores and survive eviction."""
    extractor = FeatureExtractor()
    scorer = AdaptiveScorer()

    item_active = CacheObject(
        key="active",
        size_bytes=100,
        access_count=50,
        last_accessed=now - timedelta(seconds=2),
        retrieval_cost_ms=10.0,
    )
    item_dormant = CacheObject(
        key="dormant",
        size_bytes=100,
        access_count=1,
        last_accessed=now - timedelta(seconds=600),
        retrieval_cost_ms=10.0,
    )
    objects = {"active": item_active, "dormant": item_dormant}
    wl = WorkloadState(
        request_rate=100.0,
        hit_rate=0.5,
        miss_rate=0.5,
        backend_latency_ms=30.0,
        window_seconds=60.0,
        timestamp=now,
    )
    sys = SystemState(
        cache_capacity_bytes=1000,
        cache_usage_bytes=200,
        object_count=2,
        window_seconds=60.0,
        timestamp=now,
    )

    features = extractor.extract(list(objects.values()), now=now, window_seconds=60.0)
    scores = scorer.score(features, WorkloadType.STEADY, workload=wl, system=sys)
    assert scores["active"] > scores["dormant"]

    evictions = policy.select_evictions(scores, objects, 100, workload=wl, system=sys)
    assert evictions == ["dormant"]
    assert policy.last_value_densities is not None
    assert (
        policy.last_value_densities["dormant"] < policy.last_value_densities["active"]
    )


def test_changing_runtime_telemetry_changes_eviction_ranking(
    policy: EvictionPolicy, now: datetime
) -> None:
    """Changing workload latency and memory pressure flips candidate eviction order."""
    obj_a = CacheObject(
        key="item_a",
        size_bytes=50,
        access_count=1,
        last_accessed=now,
        retrieval_cost_ms=5.0,
    )
    obj_b = CacheObject(
        key="item_b",
        size_bytes=50,
        access_count=1,
        last_accessed=now,
        retrieval_cost_ms=250.0,
    )
    objects = {"item_a": obj_a, "item_b": obj_b}
    scores = {"item_a": 0.45, "item_b": 0.44}

    # Condition 1: Low latency (fast backend) -> item_b evicted first
    wl_fast = WorkloadState(
        request_rate=50.0,
        hit_rate=0.6,
        miss_rate=0.4,
        backend_latency_ms=2.0,
        window_seconds=60.0,
        timestamp=now,
    )
    ev_cond1 = policy.select_evictions(scores, objects, 50, workload=wl_fast)
    assert ev_cond1 == ["item_b"]

    # Condition 2: High latency (stressed backend) -> item_a evicted first
    wl_slow = WorkloadState(
        request_rate=50.0,
        hit_rate=0.6,
        miss_rate=0.4,
        backend_latency_ms=400.0,
        window_seconds=60.0,
        timestamp=now,
    )
    ev_cond2 = policy.select_evictions(scores, objects, 50, workload=wl_slow)
    assert ev_cond2 == ["item_a"]


def test_zero_size_object_handled_without_division_by_zero(
    policy: EvictionPolicy, now: datetime
) -> None:
    """Zero-sized objects are assigned effective size 1 and handled safely."""
    obj_zero = CacheObject(
        key="zero_size",
        size_bytes=0,
        access_count=1,
        last_accessed=now,
        retrieval_cost_ms=10.0,
    )
    obj_normal = CacheObject(
        key="normal",
        size_bytes=100,
        access_count=1,
        last_accessed=now,
        retrieval_cost_ms=10.0,
    )
    scores = {"zero_size": 0.05, "normal": 0.80}
    objects = {"zero_size": obj_zero, "normal": obj_normal}

    # Target = 50 requires freeing 50 bytes. zero_size alone frees 0 bytes, so both are selected.
    evictions = policy.select_evictions(scores, objects, 50)
    assert evictions[0] == "zero_size"
    assert policy.last_value_densities is not None
    assert policy.last_value_densities["zero_size"] == pytest.approx(0.05, rel=1e-3)


def test_cost_model_custom_integration_and_value_density_calculation(
    now: datetime,
) -> None:
    """EvictionPolicy integrates with CostModel and supports custom cost model override."""
    custom_cost_model = CostModel()
    custom_policy = EvictionPolicy(cost_model=custom_cost_model)
    assert custom_policy.cost_model is custom_cost_model

    objects = {
        "item_x": CacheObject(
            key="item_x",
            size_bytes=200,
            access_count=1,
            last_accessed=now,
            retrieval_cost_ms=10.0,
        ),
        "item_y": CacheObject(
            key="item_y",
            size_bytes=400,
            access_count=1,
            last_accessed=now,
            retrieval_cost_ms=10.0,
        ),
    }
    scores = {"item_x": 0.60, "item_y": 0.60}

    # Eviction with explicit cost model parameter
    evictions = custom_policy.select_evictions(
        scores=scores,
        objects=objects,
        target_capacity_bytes=300,
        cost_model=custom_cost_model,
    )
    assert custom_policy.last_value_densities is not None
    # Both have equal scores and retrieval costs, but item_y is larger, so item_y has lower value density
    assert (
        custom_policy.last_value_densities["item_y"]
        < custom_policy.last_value_densities["item_x"]
    )
    assert evictions == ["item_y"]


def test_decision_engine_eviction_metadata_presence_and_clearing(
    now: datetime,
) -> None:
    """DecisionEngine populates eviction_value_density during evictions and clears it when none occur."""
    engine = DecisionEngine()
    objs = {
        "a": CacheObject(
            key="a",
            size_bytes=600,
            access_count=1,
            last_accessed=now,
            retrieval_cost_ms=5.0,
        ),
        "b": CacheObject(
            key="b",
            size_bytes=600,
            access_count=1,
            last_accessed=now,
            retrieval_cost_ms=200.0,
        ),
    }
    wl = WorkloadState(
        request_rate=100.0,
        hit_rate=0.5,
        miss_rate=0.5,
        backend_latency_ms=30.0,
        window_seconds=60.0,
        timestamp=now,
    )
    sys = SystemState(
        cache_capacity_bytes=1000,
        cache_usage_bytes=1200,
        object_count=2,
        window_seconds=60.0,
        timestamp=now,
    )

    # Run 1: Capacity pressure causes eviction
    dec1 = engine.decide(
        objects=objs,
        workload=wl,
        system=sys,
        min_capacity_bytes=100,
        max_capacity_bytes=1000,
        now=now,
    )
    assert len(dec1.eviction_keys) > 0
    assert "eviction_value_density" in dec1.metadata
    assert "a" in dec1.metadata["eviction_value_density"]
    assert "b" in dec1.metadata["eviction_value_density"]

    # Run 2: No capacity pressure (recommended capacity 2000 >= usage 1200)
    sys_room = SystemState(
        cache_capacity_bytes=2000,
        cache_usage_bytes=1200,
        object_count=2,
        window_seconds=60.0,
        timestamp=now,
    )
    dec2 = engine.decide(
        objects=objs,
        workload=wl,
        system=sys_room,
        min_capacity_bytes=1000,
        max_capacity_bytes=2000,
        now=now,
    )
    assert dec2.eviction_keys == []
    assert "eviction_value_density" not in dec2.metadata


# ---------------------------------------------------------------------------
# Step 2.1: Double-Penalty Hardening & Multi-Factor Dominance Tests
# ---------------------------------------------------------------------------


def test_large_high_value_object_survives_against_small_low_value_object_under_high_memory_pressure(
    policy: EvictionPolicy, now: datetime
) -> None:
    """A 100x larger object with high utility survives against a small low-utility object."""
    obj_tiny_low = CacheObject(
        key="tiny_low",
        size_bytes=200,
        access_count=1,
        last_accessed=now - timedelta(seconds=100),
        retrieval_cost_ms=5.0,
    )
    obj_large_high = CacheObject(
        key="large_high",
        size_bytes=20000,
        access_count=30,
        last_accessed=now - timedelta(seconds=2),
        retrieval_cost_ms=100.0,
    )
    # Utility scores: large_high has ~10x higher retention utility than tiny_low
    scores = {"tiny_low": 0.08, "large_high": 0.85}
    objects = {"tiny_low": obj_tiny_low, "large_high": obj_large_high}

    # Severe memory pressure: 100% full cache
    sys_full = SystemState(
        cache_capacity_bytes=20200,
        cache_usage_bytes=20200,
        object_count=2,
        window_seconds=60.0,
        timestamp=now,
    )
    wl = WorkloadState(
        request_rate=100.0,
        hit_rate=0.5,
        miss_rate=0.5,
        backend_latency_ms=40.0,
        window_seconds=60.0,
        timestamp=now,
    )

    evictions = policy.select_evictions(
        scores, objects, 20000, system=sys_full, workload=wl
    )
    assert evictions == ["tiny_low"]
    assert policy.last_value_densities is not None
    assert (
        policy.last_value_densities["large_high"]
        > policy.last_value_densities["tiny_low"]
    )


def test_size_penalty_monotonically_increases_with_memory_pressure(
    policy: EvictionPolicy, now: datetime
) -> None:
    """Density ratio between small and large objects increases monotonically with memory pressure."""
    obj_s = CacheObject(
        key="s",
        size_bytes=100,
        access_count=5,
        last_accessed=now,
        retrieval_cost_ms=10.0,
    )
    obj_l = CacheObject(
        key="l",
        size_bytes=10000,
        access_count=5,
        last_accessed=now,
        retrieval_cost_ms=10.0,
    )
    scores = {"s": 0.50, "l": 0.50}
    objects = {"s": obj_s, "l": obj_l}
    wl = WorkloadState(
        request_rate=100.0,
        hit_rate=0.5,
        miss_rate=0.5,
        backend_latency_ms=30.0,
        window_seconds=60.0,
        timestamp=now,
    )

    ratios: list[float] = []
    for pressure in [0.10, 0.40, 0.70, 0.95]:
        sys_p = SystemState(
            cache_capacity_bytes=int(10100 / pressure),
            cache_usage_bytes=10100,
            object_count=2,
            window_seconds=60.0,
            timestamp=now,
        )
        policy.select_evictions(scores, objects, 10000, system=sys_p, workload=wl)
        assert policy.last_value_densities is not None
        ratio = policy.last_value_densities["s"] / policy.last_value_densities["l"]
        ratios.append(ratio)

    # Monotonicity check: size matters strictly more as cache fills
    assert ratios[0] < ratios[1] < ratios[2] < ratios[3]


def test_retrieval_cost_protection_bounded_and_non_punitive(
    policy: EvictionPolicy, now: datetime
) -> None:
    """Cheap objects receive bounded penalties (<=15%) even under extreme backend latency."""
    obj_cheap = CacheObject(
        key="c_cheap",
        size_bytes=100,
        access_count=1,
        last_accessed=now,
        retrieval_cost_ms=1.0,
    )
    obj_costly = CacheObject(
        key="c_costly",
        size_bytes=100,
        access_count=1,
        last_accessed=now,
        retrieval_cost_ms=1000.0,
    )
    scores = {"c_cheap": 0.50, "c_costly": 0.50}
    objects = {"c_cheap": obj_cheap, "c_costly": obj_costly}

    # Extreme latency pressure: 10,000 ms backend latency
    wl_extreme = WorkloadState(
        request_rate=100.0,
        hit_rate=0.5,
        miss_rate=0.5,
        backend_latency_ms=10000.0,
        window_seconds=60.0,
        timestamp=now,
    )
    policy.select_evictions(scores, objects, 100, workload=wl_extreme)
    assert policy.last_retention_values is not None

    # Cheap object retention value is not overly penalized (floor >= score * 0.84)
    assert policy.last_retention_values["c_cheap"] >= 0.50 * 0.84
    # Expensive object retention value is boosted (ceiling <= score * 1.16)
    assert policy.last_retention_values["c_costly"] <= 0.50 * 1.16


def test_no_single_factor_completely_dominates_across_normal_conditions(
    policy: EvictionPolicy, now: datetime
) -> None:
    """Verifies that frequency, recency, retrieval cost, and size all interact without single-factor domination."""
    extractor = FeatureExtractor()
    scorer = AdaptiveScorer()

    candidates = {
        "tiny_stale": CacheObject(
            key="tiny_stale",
            size_bytes=100,
            access_count=1,
            last_accessed=now - timedelta(seconds=500),
            retrieval_cost_ms=5.0,
        ),
        "small_warm": CacheObject(
            key="small_warm",
            size_bytes=1000,
            access_count=10,
            last_accessed=now - timedelta(seconds=20),
            retrieval_cost_ms=15.0,
        ),
        "large_hot": CacheObject(
            key="large_hot",
            size_bytes=20000,
            access_count=45,
            last_accessed=now - timedelta(seconds=2),
            retrieval_cost_ms=100.0,
        ),
        "large_cold": CacheObject(
            key="large_cold",
            size_bytes=20000,
            access_count=2,
            last_accessed=now - timedelta(seconds=400),
            retrieval_cost_ms=10.0,
        ),
    }
    total_bytes = sum(o.size_bytes for o in candidates.values())
    sys_60 = SystemState(
        cache_capacity_bytes=int(total_bytes / 0.60),
        cache_usage_bytes=total_bytes,
        object_count=4,
        window_seconds=60.0,
        timestamp=now,
    )
    wl = WorkloadState(
        request_rate=100.0,
        hit_rate=0.6,
        miss_rate=0.4,
        backend_latency_ms=40.0,
        window_seconds=60.0,
        timestamp=now,
    )

    features = extractor.extract(
        list(candidates.values()), now=now, window_seconds=60.0
    )
    scores = scorer.score(features, WorkloadType.STEADY, workload=wl, system=sys_60)

    # Evict 5000 bytes: large_cold is evicted first, large_hot is preserved
    evicted = policy.select_evictions(
        scores, candidates, total_bytes - 5000, system=sys_60, workload=wl
    )
    assert "large_cold" in evicted
    assert "large_hot" not in evicted
    assert policy.last_value_densities is not None
    # large_hot density exceeds both large_cold and tiny_stale
    assert (
        policy.last_value_densities["large_hot"]
        > policy.last_value_densities["large_cold"]
    )
    assert (
        policy.last_value_densities["large_hot"]
        > policy.last_value_densities["tiny_stale"]
    )
