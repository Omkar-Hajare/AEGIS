"""Unit tests for the AdaptiveScorer engine.

Verifies deterministic calculation of normalized retention scores based on
extracted features and active WorkloadType weights, along with error handling,
boundary clamping, and input immutability.
"""

from copy import deepcopy

import pytest

from backend.adaptive.scoring import AdaptiveScorer
from contracts.schemas import WorkloadType


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


def test_steady_workload_weights(
    scorer: AdaptiveScorer, base_features: dict[str, float]
) -> None:
    """STEADY workload uses: 0.30 freq, 0.25 rec, 0.25 cost, 0.15 pop, 0.05 size.

    0.30*0.8 + 0.25*0.6 + 0.25*0.4 + 0.15*0.5 - 0.05*0.2 = 0.555
    """
    scores = scorer.score({"k1": base_features}, WorkloadType.STEADY)
    assert scores["k1"] == pytest.approx(0.555)


def test_read_heavy_workload_weights(
    scorer: AdaptiveScorer, base_features: dict[str, float]
) -> None:
    """READ_HEAVY uses: 0.40 freq, 0.30 rec, 0.15 cost, 0.10 pop, 0.05 size.

    0.40*0.8 + 0.30*0.6 + 0.15*0.4 + 0.10*0.5 - 0.05*0.2 = 0.600
    """
    scores = scorer.score({"k1": base_features}, WorkloadType.READ_HEAVY)
    assert scores["k1"] == pytest.approx(0.600)


def test_compute_heavy_workload_weights(
    scorer: AdaptiveScorer, base_features: dict[str, float]
) -> None:
    """COMPUTE_HEAVY uses: 0.20 freq, 0.15 rec, 0.45 cost, 0.15 pop, 0.05 size.

    0.20*0.8 + 0.15*0.6 + 0.45*0.4 + 0.15*0.5 - 0.05*0.2 = 0.495
    """
    scores = scorer.score({"k1": base_features}, WorkloadType.COMPUTE_HEAVY)
    assert scores["k1"] == pytest.approx(0.495)


def test_spike_workload_weights(
    scorer: AdaptiveScorer, base_features: dict[str, float]
) -> None:
    """SPIKE uses: 0.35 freq, 0.35 rec, 0.15 cost, 0.10 pop, 0.05 size.

    0.35*0.8 + 0.35*0.6 + 0.15*0.4 + 0.10*0.5 - 0.05*0.2 = 0.590
    """
    scores = scorer.score({"k1": base_features}, WorkloadType.SPIKE)
    assert scores["k1"] == pytest.approx(0.590)


def test_popularity_shift_workload_weights(
    scorer: AdaptiveScorer, base_features: dict[str, float]
) -> None:
    """POPULARITY_SHIFT uses: 0.20 freq, 0.20 rec, 0.15 cost, 0.40 pop, 0.05 size.

    0.20*0.8 + 0.20*0.6 + 0.15*0.4 + 0.40*0.5 - 0.05*0.2 = 0.530
    """
    scores = scorer.score({"k1": base_features}, WorkloadType.POPULARITY_SHIFT)
    assert scores["k1"] == pytest.approx(0.530)


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
