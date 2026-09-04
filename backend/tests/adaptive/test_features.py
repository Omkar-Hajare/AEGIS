"""Unit tests for the adaptive feature extraction engine.

Verifies pure, deterministic calculation and normalization of all
adaptive cache features across various edge cases and normal workloads.
"""

from datetime import datetime, timedelta, timezone

import pytest

from backend.adaptive.features import FeatureExtractor
from contracts.schemas import CacheObject


@pytest.fixture
def base_time() -> datetime:
    """Provides a consistent timezone-aware reference timestamp."""
    return datetime(2026, 9, 4, 12, 0, 0, tzinfo=timezone.utc)


def test_empty_input_returns_empty_dict(base_time: datetime) -> None:
    """Empty cache_objects list returns {}."""
    result = FeatureExtractor.extract(
        objects=[],
        now=base_time,
        window_seconds=60.0,
    )
    assert result == {}


def test_frequency_calculation_and_normalization(base_time: datetime) -> None:
    """Frequency is calculated as access_count / window and min-max normalized."""
    obj_low = CacheObject(
        key="k1",
        size_bytes=100,
        access_count=10,
        last_accessed=base_time,
        retrieval_cost_ms=5.0,
    )
    obj_mid = CacheObject(
        key="k2",
        size_bytes=100,
        access_count=20,
        last_accessed=base_time,
        retrieval_cost_ms=5.0,
    )
    obj_high = CacheObject(
        key="k3",
        size_bytes=100,
        access_count=30,
        last_accessed=base_time,
        retrieval_cost_ms=5.0,
    )

    features = FeatureExtractor.extract(
        objects=[obj_low, obj_mid, obj_high],
        now=base_time,
        window_seconds=60.0,
    )

    assert features["k1"]["frequency"] == pytest.approx(0.0)
    assert features["k2"]["frequency"] == pytest.approx(0.5)
    assert features["k3"]["frequency"] == pytest.approx(1.0)


def test_most_frequently_accessed_object_receives_highest_feature(
    base_time: datetime,
) -> None:
    """The most frequently accessed object receives the highest frequency feature."""
    obj1 = CacheObject(
        key="frequent",
        size_bytes=50,
        access_count=500,
        last_accessed=base_time,
        retrieval_cost_ms=10.0,
    )
    obj2 = CacheObject(
        key="rare",
        size_bytes=50,
        access_count=5,
        last_accessed=base_time,
        retrieval_cost_ms=10.0,
    )

    features = FeatureExtractor.extract(
        objects=[obj1, obj2],
        now=base_time,
        window_seconds=100.0,
    )
    assert features["frequent"]["frequency"] > features["rare"]["frequency"]
    assert features["frequent"]["frequency"] == pytest.approx(1.0)
    assert features["rare"]["frequency"] == pytest.approx(0.0)


def test_recency_higher_for_more_recently_accessed_object(
    base_time: datetime,
) -> None:
    """Recency gives a higher score to a more recently accessed object."""
    recent_obj = CacheObject(
        key="recent",
        size_bytes=100,
        access_count=1,
        last_accessed=base_time - timedelta(seconds=10),
        retrieval_cost_ms=5.0,
    )
    older_obj = CacheObject(
        key="older",
        size_bytes=100,
        access_count=1,
        last_accessed=base_time - timedelta(seconds=40),
        retrieval_cost_ms=5.0,
    )

    features = FeatureExtractor.extract(
        objects=[recent_obj, older_obj],
        now=base_time,
        window_seconds=60.0,
    )

    # 1 - 10/60 = 50/60 ~= 0.8333
    # 1 - 40/60 = 20/60 ~= 0.3333
    assert features["recent"]["recency"] > features["older"]["recency"]
    assert features["recent"]["recency"] == pytest.approx(50 / 60)
    assert features["older"]["recency"] == pytest.approx(20 / 60)


def test_recency_at_or_beyond_window_is_zero(base_time: datetime) -> None:
    """Object accessed at or beyond one full window ago receives recency 0.0."""
    exact_window_obj = CacheObject(
        key="exact",
        size_bytes=100,
        access_count=1,
        last_accessed=base_time - timedelta(seconds=60),
        retrieval_cost_ms=5.0,
    )
    past_window_obj = CacheObject(
        key="past",
        size_bytes=100,
        access_count=1,
        last_accessed=base_time - timedelta(seconds=120),
        retrieval_cost_ms=5.0,
    )

    features = FeatureExtractor.extract(
        objects=[exact_window_obj, past_window_obj],
        now=base_time,
        window_seconds=60.0,
    )

    assert features["exact"]["recency"] == 0.0
    assert features["past"]["recency"] == 0.0


def test_retrieval_cost_normalized_correctly(base_time: datetime) -> None:
    """Retrieval cost is min-max normalized across the supplied cache objects."""
    cheap = CacheObject(
        key="cheap",
        size_bytes=100,
        access_count=1,
        last_accessed=base_time,
        retrieval_cost_ms=10.0,
    )
    expensive = CacheObject(
        key="expensive",
        size_bytes=100,
        access_count=1,
        last_accessed=base_time,
        retrieval_cost_ms=110.0,
    )

    features = FeatureExtractor.extract(
        objects=[cheap, expensive],
        now=base_time,
        window_seconds=60.0,
    )

    assert features["cheap"]["retrieval_cost"] == pytest.approx(0.0)
    assert features["expensive"]["retrieval_cost"] == pytest.approx(1.0)


def test_larger_object_receives_greater_size_pressure(base_time: datetime) -> None:
    """Larger object receives greater size pressure than a smaller object."""
    small = CacheObject(
        key="small",
        size_bytes=1024,
        access_count=1,
        last_accessed=base_time,
        retrieval_cost_ms=5.0,
    )
    large = CacheObject(
        key="large",
        size_bytes=10240,
        access_count=1,
        last_accessed=base_time,
        retrieval_cost_ms=5.0,
    )

    features = FeatureExtractor.extract(
        objects=[small, large],
        now=base_time,
        window_seconds=60.0,
    )

    assert features["large"]["size"] > features["small"]["size"]
    assert features["large"]["size"] == pytest.approx(1.0)
    assert features["small"]["size"] == pytest.approx(0.0)


def test_equal_frequency_values_produce_half(base_time: datetime) -> None:
    """Equal frequency values produce 0.5."""
    obj1 = CacheObject(
        key="k1",
        size_bytes=100,
        access_count=15,
        last_accessed=base_time,
        retrieval_cost_ms=5.0,
    )
    obj2 = CacheObject(
        key="k2",
        size_bytes=200,
        access_count=15,
        last_accessed=base_time,
        retrieval_cost_ms=10.0,
    )

    features = FeatureExtractor.extract(
        objects=[obj1, obj2],
        now=base_time,
        window_seconds=60.0,
    )

    assert features["k1"]["frequency"] == 0.5
    assert features["k2"]["frequency"] == 0.5


def test_equal_retrieval_costs_produce_half(base_time: datetime) -> None:
    """Equal retrieval costs produce 0.5."""
    obj1 = CacheObject(
        key="k1",
        size_bytes=100,
        access_count=5,
        last_accessed=base_time,
        retrieval_cost_ms=25.0,
    )
    obj2 = CacheObject(
        key="k2",
        size_bytes=200,
        access_count=10,
        last_accessed=base_time,
        retrieval_cost_ms=25.0,
    )

    features = FeatureExtractor.extract(
        objects=[obj1, obj2],
        now=base_time,
        window_seconds=60.0,
    )

    assert features["k1"]["retrieval_cost"] == 0.5
    assert features["k2"]["retrieval_cost"] == 0.5


def test_equal_sizes_produce_half(base_time: datetime) -> None:
    """Equal sizes produce 0.5."""
    obj1 = CacheObject(
        key="k1",
        size_bytes=512,
        access_count=5,
        last_accessed=base_time,
        retrieval_cost_ms=10.0,
    )
    obj2 = CacheObject(
        key="k2",
        size_bytes=512,
        access_count=10,
        last_accessed=base_time,
        retrieval_cost_ms=20.0,
    )

    features = FeatureExtractor.extract(
        objects=[obj1, obj2],
        now=base_time,
        window_seconds=60.0,
    )

    assert features["k1"]["size"] == 0.5
    assert features["k2"]["size"] == 0.5


def test_popularity_trend_increase_produces_value_above_half(
    base_time: datetime,
) -> None:
    """Popularity increase produces a value strictly greater than 0.5."""
    obj = CacheObject(
        key="trending_up",
        size_bytes=100,
        access_count=50,
        last_accessed=base_time,
        retrieval_cost_ms=5.0,
    )

    features = FeatureExtractor.extract(
        objects=[obj],
        now=base_time,
        window_seconds=60.0,
        previous_access_counts={"trending_up": 10},
    )

    trend = features["trending_up"]["popularity_trend"]
    assert trend > 0.5
    assert trend <= 1.0


def test_popularity_trend_decrease_produces_value_below_half(
    base_time: datetime,
) -> None:
    """Popularity decrease produces a value strictly less than 0.5."""
    obj = CacheObject(
        key="trending_down",
        size_bytes=100,
        access_count=10,
        last_accessed=base_time,
        retrieval_cost_ms=5.0,
    )

    features = FeatureExtractor.extract(
        objects=[obj],
        now=base_time,
        window_seconds=60.0,
        previous_access_counts={"trending_down": 50},
    )

    trend = features["trending_down"]["popularity_trend"]
    assert trend < 0.5
    assert trend >= 0.0


def test_popularity_trend_no_change_produces_half(base_time: datetime) -> None:
    """No popularity change produces 0.5."""
    obj = CacheObject(
        key="steady",
        size_bytes=100,
        access_count=25,
        last_accessed=base_time,
        retrieval_cost_ms=5.0,
    )

    features = FeatureExtractor.extract(
        objects=[obj],
        now=base_time,
        window_seconds=60.0,
        previous_access_counts={"steady": 25},
    )

    assert features["steady"]["popularity_trend"] == pytest.approx(0.5)


def test_missing_previous_access_count_produces_half(base_time: datetime) -> None:
    """Missing previous access count produces popularity_trend = 0.5."""
    obj = CacheObject(
        key="new_key",
        size_bytes=100,
        access_count=10,
        last_accessed=base_time,
        retrieval_cost_ms=5.0,
    )

    # When previous_access_counts is None
    features_none = FeatureExtractor.extract(
        objects=[obj],
        now=base_time,
        window_seconds=60.0,
        previous_access_counts=None,
    )
    assert features_none["new_key"]["popularity_trend"] == 0.5

    # When previous_access_counts is dict but key is missing
    features_missing = FeatureExtractor.extract(
        objects=[obj],
        now=base_time,
        window_seconds=60.0,
        previous_access_counts={"other_key": 20},
    )
    assert features_missing["new_key"]["popularity_trend"] == 0.5


def test_previous_access_count_zero_does_not_divide_by_zero(
    base_time: datetime,
) -> None:
    """Previous access count of zero uses max(0, 1) and does not divide by zero."""
    obj = CacheObject(
        key="from_zero",
        size_bytes=100,
        access_count=5,
        last_accessed=base_time,
        retrieval_cost_ms=5.0,
    )

    features = FeatureExtractor.extract(
        objects=[obj],
        now=base_time,
        window_seconds=60.0,
        previous_access_counts={"from_zero": 0},
    )

    trend = features["from_zero"]["popularity_trend"]
    assert trend > 0.5
    assert trend <= 1.0


def test_all_generated_feature_values_remain_within_range(
    base_time: datetime,
) -> None:
    """All generated feature values strictly satisfy 0.0 <= value <= 1.0."""
    objects = [
        CacheObject(
            key=f"k{i}",
            size_bytes=i * 1000,
            access_count=i * 5,
            last_accessed=base_time - timedelta(seconds=i * 15),
            retrieval_cost_ms=float(i * 10),
        )
        for i in range(10)
    ]
    prev_counts = {f"k{i}": (10 - i) * 5 for i in range(10)}

    features = FeatureExtractor.extract(
        objects=objects,
        now=base_time,
        window_seconds=60.0,
        previous_access_counts=prev_counts,
    )

    assert len(features) == 10
    feature_names = [
        "frequency",
        "recency",
        "retrieval_cost",
        "size",
        "popularity_trend",
    ]

    for key, feat_dict in features.items():
        assert set(feat_dict.keys()) == set(feature_names)
        for name in feature_names:
            val = feat_dict[name]
            assert 0.0 <= val <= 1.0, f"Feature {name} for {key} had value {val}"


@pytest.mark.parametrize("invalid_window", [0.0, -1.0, -100.0])
def test_invalid_window_seconds_raises_value_error(
    base_time: datetime, invalid_window: float
) -> None:
    """window_seconds <= 0 raises ValueError."""
    obj = CacheObject(
        key="k1",
        size_bytes=100,
        access_count=1,
        last_accessed=base_time,
        retrieval_cost_ms=1.0,
    )

    with pytest.raises(ValueError, match="window_seconds"):
        FeatureExtractor.extract(
            objects=[obj],
            now=base_time,
            window_seconds=invalid_window,
        )


def test_input_objects_are_not_mutated(base_time: datetime) -> None:
    """Input CacheObject instances and list are not mutated by feature extraction."""
    original_last_accessed = base_time - timedelta(seconds=10)
    obj = CacheObject(
        key="immutable_check",
        size_bytes=1024,
        access_count=42,
        last_accessed=original_last_accessed,
        retrieval_cost_ms=18.5,
        features=None,
        metadata={"original": "meta"},
    )

    input_list = [obj]
    FeatureExtractor.extract(
        objects=input_list,
        now=base_time,
        window_seconds=60.0,
        previous_access_counts={"immutable_check": 30},
    )

    # Verify obj properties remain identical
    assert obj.key == "immutable_check"
    assert obj.size_bytes == 1024
    assert obj.access_count == 42
    assert obj.last_accessed == original_last_accessed
    assert obj.retrieval_cost_ms == 18.5
    assert obj.features is None
    assert obj.metadata == {"original": "meta"}
    assert len(input_list) == 1
    assert input_list[0] is obj
