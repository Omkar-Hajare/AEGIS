"""Unit tests for the AdaptiveScorer engine.

Verifies deterministic calculation of normalized retention scores based on
extracted features and active WorkloadType weights, along with error handling,
boundary clamping, and input immutability.
"""

import math
from copy import deepcopy
from datetime import datetime, timezone

import pytest

from backend.adaptive.scoring import (
    AdaptiveScorer,
    DynamicWeightModel,
)
from contracts.schemas import SystemState, WorkloadState, WorkloadType


@pytest.fixture
def scorer() -> AdaptiveScorer:
    """Provides a fresh AdaptiveScorer instance."""
    return AdaptiveScorer()


@pytest.fixture
def base_features() -> dict[str, float]:
    """Provides standard baseline feature values."""
    return {
        "frequency": 0.8,
        "recency": 0.6,
        "retrieval_cost": 0.4,
        "size": 0.2,
        "popularity_trend": 0.5,
    }


def make_test_workload(
    backend_latency_ms: float = 30.0,
    request_rate: float = 100.0,
    hit_rate: float = 0.5,
    miss_rate: float = 0.5,
    metrics: dict[str, float] | None = None,
) -> WorkloadState:
    """Helper to build a WorkloadState snapshot for testing."""
    return WorkloadState(
        request_rate=request_rate,
        hit_rate=hit_rate,
        miss_rate=miss_rate,
        backend_latency_ms=backend_latency_ms,
        workload_type=WorkloadType.STEADY,
        timestamp=datetime(2026, 9, 4, 12, 0, 0, tzinfo=timezone.utc),
        window_seconds=60.0,
        metrics=metrics,
    )


def make_test_system(
    cache_usage_bytes: int = 500,
    cache_capacity_bytes: int = 1000,
) -> SystemState:
    """Helper to build a SystemState snapshot for testing."""
    return SystemState(
        cache_capacity_bytes=cache_capacity_bytes,
        cache_usage_bytes=cache_usage_bytes,
        object_count=5,
        timestamp=datetime(2026, 9, 4, 12, 0, 0, tzinfo=timezone.utc),
        window_seconds=60.0,
    )


def test_dynamic_weights_change_when_backend_latency_pressure_changes(
    scorer: AdaptiveScorer, base_features: dict[str, float]
) -> None:
    """Increasing backend latency dynamically elevates the retrieval-cost weight."""
    wl_fast = make_test_workload(backend_latency_ms=5.0)
    wl_slow = make_test_workload(backend_latency_ms=500.0)

    scorer.score({"k1": base_features}, workload=wl_fast)
    assert scorer.last_weights is not None
    cost_weight_fast = scorer.last_weights.retrieval_cost

    scorer.score({"k1": base_features}, workload=wl_slow)
    assert scorer.last_weights is not None
    cost_weight_slow = scorer.last_weights.retrieval_cost

    assert cost_weight_slow > cost_weight_fast
    assert cost_weight_slow > 0.30


def test_dynamic_weights_change_when_memory_utilization_changes(
    scorer: AdaptiveScorer, base_features: dict[str, float]
) -> None:
    """Increasing cache memory utilization dynamically elevates the size-penalty weight."""
    sys_empty = make_test_system(cache_usage_bytes=100, cache_capacity_bytes=1000)
    sys_full = make_test_system(cache_usage_bytes=990, cache_capacity_bytes=1000)

    scorer.score({"k1": base_features}, system=sys_empty)
    assert scorer.last_weights is not None
    size_weight_empty = scorer.last_weights.size_penalty

    scorer.score({"k1": base_features}, system=sys_full)
    assert scorer.last_weights is not None
    size_weight_full = scorer.last_weights.size_penalty

    assert size_weight_full > size_weight_empty
    assert size_weight_full > 0.05


def test_dynamic_weights_change_when_popularity_trend_changes(
    scorer: AdaptiveScorer, base_features: dict[str, float]
) -> None:
    """Popularity shift signals dynamically elevate the popularity-trend weight."""
    wl_steady = make_test_workload(metrics={"popularity_shift_score": 0.0})
    wl_shift = make_test_workload(metrics={"popularity_shift_score": 1.0})

    scorer.score({"k1": base_features}, workload=wl_steady)
    assert scorer.last_weights is not None
    trend_weight_steady = scorer.last_weights.popularity_trend

    scorer.score({"k1": base_features}, workload=wl_shift)
    assert scorer.last_weights is not None
    trend_weight_shift = scorer.last_weights.popularity_trend

    assert trend_weight_shift > trend_weight_steady


def test_dynamic_weights_change_when_request_rate_pressure_changes(
    scorer: AdaptiveScorer, base_features: dict[str, float]
) -> None:
    """A surge in request rate dynamically elevates frequency and recency weights."""
    wl_normal = make_test_workload(
        request_rate=100.0,
        metrics={"request_rate_baseline": 100.0},
    )
    wl_surge = make_test_workload(
        request_rate=500.0,
        metrics={"request_rate_baseline": 100.0},
    )

    scorer.score({"k1": base_features}, workload=wl_normal)
    assert scorer.last_weights is not None
    rec_normal = scorer.last_weights.recency

    scorer.score({"k1": base_features}, workload=wl_surge)
    assert scorer.last_weights is not None
    rec_surge = scorer.last_weights.recency

    assert rec_surge > rec_normal


def test_same_workload_type_with_different_telemetry_produces_different_weights(
    scorer: AdaptiveScorer, base_features: dict[str, float]
) -> None:
    """Two observations with the exact same WorkloadType produce different weights."""
    wl_compute_low = make_test_workload(backend_latency_ms=210.0)
    wl_compute_high = make_test_workload(backend_latency_ms=2000.0)

    scores_low = scorer.score(
        {"k1": base_features},
        workload_type=WorkloadType.COMPUTE_HEAVY,
        workload=wl_compute_low,
    )
    weights_low = scorer.last_weights
    assert weights_low is not None

    scores_high = scorer.score(
        {"k1": base_features},
        workload_type=WorkloadType.COMPUTE_HEAVY,
        workload=wl_compute_high,
    )
    weights_high = scorer.last_weights
    assert weights_high is not None

    # Weights and final scores differ despite sharing WorkloadType.COMPUTE_HEAVY
    assert weights_high.retrieval_cost > weights_low.retrieval_cost
    assert scores_high["k1"] != scores_low["k1"]


def test_no_static_workload_type_weight_dictionary_remains() -> None:
    """Verify that AdaptiveScorer no longer contains SCORING_WEIGHTS table."""
    scorer_inst = AdaptiveScorer()
    assert not hasattr(scorer_inst, "SCORING_WEIGHTS")
    assert isinstance(scorer_inst.weight_model, DynamicWeightModel)


def test_weights_are_normalized_and_valid(
    scorer: AdaptiveScorer, base_features: dict[str, float]
) -> None:
    """Positive weights strictly sum to 0.95 and all weights are finite and non-negative."""
    scorer.score({"k1": base_features})
    w = scorer.last_weights
    assert w is not None

    assert w.frequency >= 0.0
    assert w.recency >= 0.0
    assert w.retrieval_cost >= 0.0
    assert w.popularity_trend >= 0.0
    assert w.size_penalty >= 0.0

    pos_sum = w.frequency + w.recency + w.retrieval_cost + w.popularity_trend
    assert pos_sum == pytest.approx(0.95)


def test_missing_optional_telemetry_uses_neutral_fallback(
    scorer: AdaptiveScorer, base_features: dict[str, float]
) -> None:
    """Calling score without workload or system telemetry safely uses neutral defaults."""
    scores = scorer.score({"k1": base_features})
    assert "k1" in scores
    assert 0.0 <= scores["k1"] <= 1.0
    assert scorer.last_weights is not None
    assert scorer.last_weights.frequency > 0.0


def test_invalid_telemetry_does_not_produce_nan_or_infinity(
    scorer: AdaptiveScorer, base_features: dict[str, float]
) -> None:
    """Non-finite or extreme telemetry values are safely clamped without producing NaN."""
    extreme_workload = WorkloadState(
        request_rate=1e9,
        hit_rate=1.0,
        miss_rate=0.0,
        backend_latency_ms=1e9,
        timestamp=datetime(2026, 9, 4, 12, 0, 0, tzinfo=timezone.utc),
        window_seconds=60.0,
    )
    extreme_system = SystemState(
        cache_capacity_bytes=1000,
        cache_usage_bytes=10000,  # over capacity
        object_count=100,
        timestamp=datetime(2026, 9, 4, 12, 0, 0, tzinfo=timezone.utc),
        window_seconds=60.0,
    )

    scores = scorer.score(
        {"k1": base_features},
        workload=extreme_workload,
        system=extreme_system,
    )
    score_val = scores["k1"]
    assert math.isfinite(score_val)
    assert 0.0 <= score_val <= 1.0


def test_higher_frequency_produces_higher_score(scorer: AdaptiveScorer) -> None:
    """A high-frequency object receives a higher score when other features are equal."""
    high_freq = {
        "frequency": 0.9,
        "recency": 0.5,
        "retrieval_cost": 0.5,
        "size": 0.5,
        "popularity_trend": 0.5,
    }
    low_freq = {
        "frequency": 0.2,
        "recency": 0.5,
        "retrieval_cost": 0.5,
        "size": 0.5,
        "popularity_trend": 0.5,
    }

    scores = scorer.score({"high": high_freq, "low": low_freq}, WorkloadType.STEADY)
    assert scores["high"] > scores["low"]


def test_higher_recency_produces_higher_score(scorer: AdaptiveScorer) -> None:
    """A more recent object receives a higher score when other features are equal."""
    recent = {
        "frequency": 0.5,
        "recency": 0.95,
        "retrieval_cost": 0.5,
        "size": 0.5,
        "popularity_trend": 0.5,
    }
    older = {
        "frequency": 0.5,
        "recency": 0.10,
        "retrieval_cost": 0.5,
        "size": 0.5,
        "popularity_trend": 0.5,
    }

    scores = scorer.score({"rec": recent, "old": older}, WorkloadType.STEADY)
    assert scores["rec"] > scores["old"]


def test_higher_retrieval_cost_produces_higher_score(
    scorer: AdaptiveScorer,
) -> None:
    """A higher retrieval-cost object receives a higher score."""
    costly = {
        "frequency": 0.5,
        "recency": 0.5,
        "retrieval_cost": 0.9,
        "size": 0.5,
        "popularity_trend": 0.5,
    }
    cheap = {
        "frequency": 0.5,
        "recency": 0.5,
        "retrieval_cost": 0.1,
        "size": 0.5,
        "popularity_trend": 0.5,
    }

    scores = scorer.score(
        {"costly": costly, "cheap": cheap}, WorkloadType.COMPUTE_HEAVY
    )
    assert scores["costly"] > scores["cheap"]


def test_larger_size_produces_lower_score(scorer: AdaptiveScorer) -> None:
    """A larger object receives a lower score due to eviction pressure."""
    large = {
        "frequency": 0.5,
        "recency": 0.5,
        "retrieval_cost": 0.5,
        "size": 0.9,
        "popularity_trend": 0.5,
    }
    small = {
        "frequency": 0.5,
        "recency": 0.5,
        "retrieval_cost": 0.5,
        "size": 0.1,
        "popularity_trend": 0.5,
    }

    scores = scorer.score({"lg": large, "sm": small}, WorkloadType.STEADY)
    assert scores["lg"] < scores["sm"]


def test_rising_popularity_trend_produces_higher_score(
    scorer: AdaptiveScorer,
) -> None:
    """A rising popularity-trend object receives a higher score."""
    trending = {
        "frequency": 0.5,
        "recency": 0.5,
        "retrieval_cost": 0.5,
        "size": 0.5,
        "popularity_trend": 0.95,
    }
    fading = {
        "frequency": 0.5,
        "recency": 0.5,
        "retrieval_cost": 0.5,
        "size": 0.5,
        "popularity_trend": 0.10,
    }

    scores = scorer.score(
        {"up": trending, "down": fading}, WorkloadType.POPULARITY_SHIFT
    )
    assert scores["up"] > scores["down"]


def test_final_scores_remain_within_range(scorer: AdaptiveScorer) -> None:
    """Final scores must be strictly clamped to [0.0, 1.0]."""
    # Max possible features: positive sum 0.95, size 0.0 -> 0.95
    maximum_possible = {
        "frequency": 1.0,
        "recency": 1.0,
        "retrieval_cost": 1.0,
        "size": 0.0,
        "popularity_trend": 1.0,
    }
    # Min possible features: positive sum 0.0, size 1.0 -> -0.05 -> clamped to 0.0
    minimum_possible = {
        "frequency": 0.0,
        "recency": 0.0,
        "retrieval_cost": 0.0,
        "size": 1.0,
        "popularity_trend": 0.0,
    }

    for wt in WorkloadType:
        scores = scorer.score({"max": maximum_possible, "min": minimum_possible}, wt)
        assert 0.0 <= scores["max"] <= 1.0
        assert 0.0 <= scores["min"] <= 1.0
        assert scores["max"] == pytest.approx(0.95)
        assert scores["min"] == pytest.approx(0.0)


def test_empty_input_returns_empty_dict(scorer: AdaptiveScorer) -> None:
    """An empty feature mapping returns an empty dictionary."""
    assert scorer.score({}, WorkloadType.STEADY) == {}


def test_multiple_objects_produce_one_score_per_object(
    scorer: AdaptiveScorer,
) -> None:
    """Multiple objects produce exactly one score per object key."""
    features = {
        f"item:{i}": {
            "frequency": i / 10.0,
            "recency": (10 - i) / 10.0,
            "retrieval_cost": 0.5,
            "size": 0.3,
            "popularity_trend": 0.5,
        }
        for i in range(10)
    }

    scores = scorer.score(features, WorkloadType.STEADY)
    assert len(scores) == 10
    assert set(scores.keys()) == set(features.keys())
    for val in scores.values():
        assert 0.0 <= val <= 1.0


def test_missing_feature_raises_value_error(scorer: AdaptiveScorer) -> None:
    """Missing required feature raises ValueError identifying key and feature."""
    incomplete = {
        "item:1": {
            "frequency": 0.8,
            "recency": 0.6,
            # "retrieval_cost" missing
            "size": 0.2,
            "popularity_trend": 0.5,
        }
    }
    with pytest.raises(ValueError, match="retrieval_cost"):
        scorer.score(incomplete, WorkloadType.STEADY)


def test_string_feature_value_raises_value_error(
    scorer: AdaptiveScorer,
) -> None:
    """String feature value raises ValueError."""
    bad_features = {
        "item:1": {
            "frequency": "high",  # invalid str
            "recency": 0.6,
            "retrieval_cost": 0.4,
            "size": 0.2,
            "popularity_trend": 0.5,
        }
    }
    with pytest.raises(ValueError, match="numeric"):
        scorer.score(bad_features, WorkloadType.STEADY)


def test_boolean_feature_value_raises_value_error(
    scorer: AdaptiveScorer,
) -> None:
    """Boolean feature value raises ValueError."""
    bad_features = {
        "item:1": {
            "frequency": True,  # invalid bool
            "recency": 0.6,
            "retrieval_cost": 0.4,
            "size": 0.2,
            "popularity_trend": 0.5,
        }
    }
    with pytest.raises(ValueError, match="numeric"):
        scorer.score(bad_features, WorkloadType.STEADY)


def test_feature_value_below_zero_raises_value_error(
    scorer: AdaptiveScorer,
) -> None:
    """Feature value below 0 raises ValueError."""
    bad_features = {
        "item:1": {
            "frequency": -0.1,  # below 0
            "recency": 0.6,
            "retrieval_cost": 0.4,
            "size": 0.2,
            "popularity_trend": 0.5,
        }
    }
    with pytest.raises(ValueError, match=r"\[0\.0, 1\.0\]"):
        scorer.score(bad_features, WorkloadType.STEADY)


def test_feature_value_above_one_raises_value_error(
    scorer: AdaptiveScorer,
) -> None:
    """Feature value above 1 raises ValueError."""
    bad_features = {
        "item:1": {
            "frequency": 1.05,  # above 1
            "recency": 0.6,
            "retrieval_cost": 0.4,
            "size": 0.2,
            "popularity_trend": 0.5,
        }
    }
    with pytest.raises(ValueError, match=r"\[0\.0, 1\.0\]"):
        scorer.score(bad_features, WorkloadType.STEADY)


def test_input_feature_mapping_is_not_mutated(
    scorer: AdaptiveScorer, base_features: dict[str, float]
) -> None:
    """Input feature dictionary is never mutated."""
    original_input = {"k1": base_features}
    copied_input = deepcopy(original_input)

    scorer.score(original_input, WorkloadType.STEADY)
    assert original_input == copied_input


def test_determinism_same_input_produces_identical_output(
    scorer: AdaptiveScorer, base_features: dict[str, float]
) -> None:
    """Same input always produces identical output score."""
    res1 = scorer.score({"k1": base_features}, WorkloadType.STEADY)
    res2 = scorer.score({"k1": base_features}, WorkloadType.STEADY)
    assert res1 == res2


def test_all_workload_type_enum_values_are_supported(
    scorer: AdaptiveScorer, base_features: dict[str, float]
) -> None:
    """All WorkloadType enum values are supported without error."""
    for wt in WorkloadType:
        scores = scorer.score({"k1": base_features}, wt)
        assert "k1" in scores
        assert isinstance(scores["k1"], float)


def test_invalid_workload_type_raises_value_error(
    scorer: AdaptiveScorer, base_features: dict[str, float]
) -> None:
    """Invalid workload type raises ValueError."""
    with pytest.raises(ValueError, match="workload_type"):
        scorer.score({"k1": base_features}, "NON_EXISTENT_WORKLOAD")  # type: ignore[arg-type]


def test_callable_syntax_matches_score_method(
    scorer: AdaptiveScorer, base_features: dict[str, float]
) -> None:
    """AdaptiveScorer instance can be called directly as a callable."""
    score1 = scorer.score({"k1": base_features}, WorkloadType.STEADY)
    score2 = scorer({"k1": base_features}, WorkloadType.STEADY)
    assert score1 == score2


def test_same_hit_rate_different_frequency_distribution_produces_different_pressure(
    scorer: AdaptiveScorer,
) -> None:
    """Same hit rate with different access-frequency distributions yields different frequency pressures and weights."""
    wl = make_test_workload(hit_rate=0.5, miss_rate=0.5)

    # Set A: uniformly low frequency objects
    features_low = {
        f"item_{i}": {
            "frequency": 0.1,
            "recency": 0.5,
            "retrieval_cost": 0.5,
            "size": 0.5,
            "popularity_trend": 0.5,
        }
        for i in range(4)
    }

    # Set B: objects with high frequency concentration
    features_high = {
        "item_0": {
            "frequency": 0.9,
            "recency": 0.5,
            "retrieval_cost": 0.5,
            "size": 0.5,
            "popularity_trend": 0.5,
        },
        "item_1": {
            "frequency": 0.8,
            "recency": 0.5,
            "retrieval_cost": 0.5,
            "size": 0.5,
            "popularity_trend": 0.5,
        },
        "item_2": {
            "frequency": 0.2,
            "recency": 0.5,
            "retrieval_cost": 0.5,
            "size": 0.5,
            "popularity_trend": 0.5,
        },
        "item_3": {
            "frequency": 0.1,
            "recency": 0.5,
            "retrieval_cost": 0.5,
            "size": 0.5,
            "popularity_trend": 0.5,
        },
    }

    scorer.score(features_low, workload=wl)
    assert scorer.last_pressures is not None
    assert scorer.last_weights is not None
    p_freq_low = scorer.last_pressures["frequency_pressure"]
    w_freq_low = scorer.last_weights.frequency

    scorer.score(features_high, workload=wl)
    assert scorer.last_pressures is not None
    assert scorer.last_weights is not None
    p_freq_high = scorer.last_pressures["frequency_pressure"]
    w_freq_high = scorer.last_weights.frequency

    # Despite identical workload.hit_rate (0.5), frequency pressure and weights differ
    assert p_freq_high > p_freq_low
    assert w_freq_high > w_freq_low


def test_higher_repeated_access_concentration_increases_frequency_pressure() -> None:
    """Higher concentration of repeated accesses monotonically elevates frequency pressure."""
    model = DynamicWeightModel()

    # Uniform distribution (no concentration)
    features_uniform = {
        f"k{i}": {
            "frequency": 0.5,
            "recency": 0.5,
            "retrieval_cost": 0.5,
            "size": 0.5,
            "popularity_trend": 0.5,
        }
        for i in range(4)
    }

    # Moderate concentration (mean 0.5)
    features_moderate = {
        "k0": {
            "frequency": 0.8,
            "recency": 0.5,
            "retrieval_cost": 0.5,
            "size": 0.5,
            "popularity_trend": 0.5,
        },
        "k1": {
            "frequency": 0.6,
            "recency": 0.5,
            "retrieval_cost": 0.5,
            "size": 0.5,
            "popularity_trend": 0.5,
        },
        "k2": {
            "frequency": 0.4,
            "recency": 0.5,
            "retrieval_cost": 0.5,
            "size": 0.5,
            "popularity_trend": 0.5,
        },
        "k3": {
            "frequency": 0.2,
            "recency": 0.5,
            "retrieval_cost": 0.5,
            "size": 0.5,
            "popularity_trend": 0.5,
        },
    }

    # Heavy repeat concentration (Zipfian-like hot spots, mean 0.5)
    features_skewed = {
        "k0": {
            "frequency": 1.0,
            "recency": 0.5,
            "retrieval_cost": 0.5,
            "size": 0.5,
            "popularity_trend": 0.5,
        },
        "k1": {
            "frequency": 0.8,
            "recency": 0.5,
            "retrieval_cost": 0.5,
            "size": 0.5,
            "popularity_trend": 0.5,
        },
        "k2": {
            "frequency": 0.1,
            "recency": 0.5,
            "retrieval_cost": 0.5,
            "size": 0.5,
            "popularity_trend": 0.5,
        },
        "k3": {
            "frequency": 0.1,
            "recency": 0.5,
            "retrieval_cost": 0.5,
            "size": 0.5,
            "popularity_trend": 0.5,
        },
    }

    p_uniform = model.compute_pressures(features=features_uniform)["frequency_pressure"]
    p_moderate = model.compute_pressures(features=features_moderate)[
        "frequency_pressure"
    ]
    p_skewed = model.compute_pressures(features=features_skewed)["frequency_pressure"]

    assert p_skewed > p_moderate > p_uniform


def test_frequency_pressure_remains_finite_and_bounded() -> None:
    """Frequency pressure remains strictly in [0.0, 1.0] across boundary inputs."""
    model = DynamicWeightModel()

    all_zero = {
        f"k{i}": {
            "frequency": 0.0,
            "recency": 0.0,
            "retrieval_cost": 0.0,
            "size": 0.0,
            "popularity_trend": 0.0,
        }
        for i in range(10)
    }
    all_one = {
        f"k{i}": {
            "frequency": 1.0,
            "recency": 1.0,
            "retrieval_cost": 1.0,
            "size": 1.0,
            "popularity_trend": 1.0,
        }
        for i in range(10)
    }

    p_zero = model.compute_pressures(features=all_zero)["frequency_pressure"]
    p_one = model.compute_pressures(features=all_one)["frequency_pressure"]

    assert 0.0 <= p_zero <= 1.0
    assert 0.0 <= p_one <= 1.0
    assert math.isfinite(p_zero)
    assert math.isfinite(p_one)


def test_cold_start_frequency_data_does_not_crash() -> None:
    """DynamicWeightModel does not crash on empty features or cold-start conditions."""
    model = DynamicWeightModel()

    p_empty = model.compute_pressures(features={})["frequency_pressure"]
    p_none = model.compute_pressures(features=None)["frequency_pressure"]

    assert 0.0 <= p_empty <= 1.0
    assert 0.0 <= p_none <= 1.0
    assert p_empty == 0.5
    assert p_none == 0.5


def test_same_hit_rate_different_last_accessed_recency_distribution_produces_different_pressure(
    scorer: AdaptiveScorer,
) -> None:
    """Same hit rate with different recency distributions yields different recency pressures and weights."""
    wl = make_test_workload(hit_rate=0.5, miss_rate=0.5)

    # Set A: stale cache objects (low recency)
    features_stale = {
        f"item_{i}": {
            "frequency": 0.5,
            "recency": 0.1,
            "retrieval_cost": 0.5,
            "size": 0.5,
            "popularity_trend": 0.5,
        }
        for i in range(4)
    }

    # Set B: fresh cache objects (high recency)
    features_fresh = {
        f"item_{i}": {
            "frequency": 0.5,
            "recency": 0.9,
            "retrieval_cost": 0.5,
            "size": 0.5,
            "popularity_trend": 0.5,
        }
        for i in range(4)
    }

    scorer.score(features_stale, workload=wl)
    assert scorer.last_pressures is not None
    assert scorer.last_weights is not None
    p_rec_stale = scorer.last_pressures["recency_pressure"]
    w_rec_stale = scorer.last_weights.recency

    scorer.score(features_fresh, workload=wl)
    assert scorer.last_pressures is not None
    assert scorer.last_weights is not None
    p_rec_fresh = scorer.last_pressures["recency_pressure"]
    w_rec_fresh = scorer.last_weights.recency

    # Despite identical workload.miss_rate (0.5), recency pressure and weights differ
    assert p_rec_fresh > p_rec_stale
    assert w_rec_fresh > w_rec_stale


def test_newly_active_working_set_increases_recency_pressure() -> None:
    """Arrival of a newly active working set elevates recency pressure."""
    model = DynamicWeightModel()

    features = {
        "k0": {
            "frequency": 0.5,
            "recency": 0.8,
            "retrieval_cost": 0.5,
            "size": 0.5,
            "popularity_trend": 0.5,
        },
        "k1": {
            "frequency": 0.5,
            "recency": 0.8,
            "retrieval_cost": 0.5,
            "size": 0.5,
            "popularity_trend": 0.5,
        },
        "k2": {
            "frequency": 0.5,
            "recency": 0.7,
            "retrieval_cost": 0.5,
            "size": 0.5,
            "popularity_trend": 0.5,
        },
        "k3": {
            "frequency": 0.5,
            "recency": 0.7,
            "retrieval_cost": 0.5,
            "size": 0.5,
            "popularity_trend": 0.5,
        },
    }

    # Case 1: Stable working set (keys were already active in previous window)
    prev_stable = {"k0": 10, "k1": 10, "k2": 10, "k3": 10}
    p_stable = model.compute_pressures(
        features=features,
        previous_access_counts=prev_stable,
    )["recency_pressure"]

    # Case 2: Newly active working set (k0..k3 are new keys not seen in previous window)
    prev_disjoint = {"old_a": 10, "old_b": 10}
    p_new_set = model.compute_pressures(
        features=features,
        previous_access_counts=prev_disjoint,
    )["recency_pressure"]

    assert p_new_set > p_stable


def test_recency_pressure_remains_finite_and_bounded() -> None:
    """Recency pressure remains strictly in [0.0, 1.0] across extreme inputs."""
    model = DynamicWeightModel()

    all_zero = {
        f"k{i}": {
            "frequency": 0.0,
            "recency": 0.0,
            "retrieval_cost": 0.0,
            "size": 0.0,
            "popularity_trend": 0.0,
        }
        for i in range(5)
    }
    all_one = {
        f"k{i}": {
            "frequency": 1.0,
            "recency": 1.0,
            "retrieval_cost": 1.0,
            "size": 1.0,
            "popularity_trend": 1.0,
        }
        for i in range(5)
    }

    p_zero = model.compute_pressures(features=all_zero)["recency_pressure"]
    p_one = model.compute_pressures(features=all_one)["recency_pressure"]

    assert 0.0 <= p_zero <= 1.0
    assert 0.0 <= p_one <= 1.0
    assert math.isfinite(p_zero)
    assert math.isfinite(p_one)


def test_missing_recency_data_uses_deterministic_fallback() -> None:
    """DynamicWeightModel provides safe deterministic fallback for missing recency data."""
    model = DynamicWeightModel()

    # Features missing recency key
    partial_features = {
        "k0": {
            "frequency": 0.5,
            "retrieval_cost": 0.5,
            "size": 0.5,
            "popularity_trend": 0.5,
        },
    }
    pressures = model.compute_pressures(features=partial_features)
    assert 0.0 <= pressures["recency_pressure"] <= 1.0
    assert math.isfinite(pressures["recency_pressure"])
