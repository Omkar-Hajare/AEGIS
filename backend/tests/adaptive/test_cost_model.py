"""Unit tests for CostModel in the Adaptive Cache System.

Tests retrieval cost normalization, backend savings estimation, RAM cost estimation,
net benefit calculation, value density, bounds validation, immutability,
and determinism.
"""

from datetime import datetime, timezone

import pytest

from backend.cost.model import (
    BYTES_PER_GB,
    DEFAULT_ALPHA,
    DEFAULT_BACKEND_COST_PER_MS,
    DEFAULT_CACHE_RAM_COST_PER_GB_HOUR,
    DEFAULT_HOURS,
    CostModel,
    CostModelValidationError,
)
from contracts.schemas.cache import CacheObject


@pytest.fixture
def model() -> CostModel:
    """Fixture providing a fresh CostModel instance."""
    return CostModel()


@pytest.fixture
def now() -> datetime:
    """Fixture providing a fixed timezone-aware timestamp."""
    return datetime(2026, 9, 4, 12, 0, 0, tzinfo=timezone.utc)


def make_obj(
    key: str,
    size_bytes: int = 1000,
    retrieval_cost_ms: float = 10.0,
    now: datetime | None = None,
    access_count: int = 1,
) -> CacheObject:
    """Helper to create a CacheObject with key matching."""
    ts = now or datetime(2026, 9, 4, 12, 0, 0, tzinfo=timezone.utc)
    return CacheObject(
        key=key,
        size_bytes=size_bytes,
        access_count=access_count,
        last_accessed=ts,
        retrieval_cost_ms=retrieval_cost_ms,
    )


# ---------------------------------------------------------------------------
# Method 1: normalize_retrieval_costs Tests
# ---------------------------------------------------------------------------


def test_empty_objects_normalization(model: CostModel) -> None:
    """Empty object dictionary returns an empty dict."""
    assert model.normalize_retrieval_costs({}) == {}


def test_single_object_normalization(model: CostModel) -> None:
    """Single object normalization produces exactly 0.5."""
    objects = {"A": make_obj("A", retrieval_cost_ms=150.0)}
    normalized = model.normalize_retrieval_costs(objects)
    assert normalized == {"A": 0.5}


def test_different_retrieval_costs_min_max_normalization(
    model: CostModel,
) -> None:
    """Different retrieval costs scale linearly between 0.0 and 1.0."""
    objects = {
        "cheap": make_obj("cheap", retrieval_cost_ms=20.0),
        "mid": make_obj("mid", retrieval_cost_ms=60.0),
        "expensive": make_obj("expensive", retrieval_cost_ms=100.0),
    }
    normalized = model.normalize_retrieval_costs(objects)
    assert normalized["cheap"] == pytest.approx(0.0)
    assert normalized["mid"] == pytest.approx(0.5)
    assert normalized["expensive"] == pytest.approx(1.0)


def test_equal_retrieval_costs_produce_half(model: CostModel) -> None:
    """When all retrieval costs are identical, every object receives 0.5."""
    objects = {
        "A": make_obj("A", retrieval_cost_ms=50.0),
        "B": make_obj("B", retrieval_cost_ms=50.0),
        "C": make_obj("C", retrieval_cost_ms=50.0),
    }
    normalized = model.normalize_retrieval_costs(objects)
    assert normalized == {"A": 0.5, "B": 0.5, "C": 0.5}


def test_zero_retrieval_cost_normalization(model: CostModel) -> None:
    """Zero retrieval cost is properly handled at min boundary."""
    objects = {
        "free": make_obj("free", retrieval_cost_ms=0.0),
        "costly": make_obj("costly", retrieval_cost_ms=100.0),
    }
    normalized = model.normalize_retrieval_costs(objects)
    assert normalized["free"] == pytest.approx(0.0)
    assert normalized["costly"] == pytest.approx(1.0)


def test_all_zero_retrieval_costs_produce_half(model: CostModel) -> None:
    """When all retrieval costs are 0.0, every object receives 0.5."""
    objects = {
        "free1": make_obj("free1", retrieval_cost_ms=0.0),
        "free2": make_obj("free2", retrieval_cost_ms=0.0),
    }
    normalized = model.normalize_retrieval_costs(objects)
    assert normalized == {"free1": 0.5, "free2": 0.5}


def test_normalize_retrieval_costs_invalid_mapping_raises_error(
    model: CostModel,
) -> None:
    """Non-mapping objects argument raises CostModelValidationError."""
    with pytest.raises(CostModelValidationError):
        model.normalize_retrieval_costs(["not", "a", "dict"])  # type: ignore[arg-type]


def test_normalize_retrieval_costs_invalid_key_type_raises_error(
    model: CostModel,
) -> None:
    """Non-string key raises CostModelValidationError."""
    with pytest.raises(CostModelValidationError):
        model.normalize_retrieval_costs({123: make_obj("123")})  # type: ignore[dict-item]


def test_normalize_retrieval_costs_invalid_value_type_raises_error(
    model: CostModel,
) -> None:
    """Non-CacheObject value raises CostModelValidationError."""
    with pytest.raises(CostModelValidationError):
        model.normalize_retrieval_costs({"A": "not_an_object"})  # type: ignore[dict-item]


def test_normalize_retrieval_costs_key_mismatch_raises_error(
    model: CostModel,
) -> None:
    """Dictionary key not matching CacheObject.key raises CostModelValidationError."""
    obj = make_obj("actual_key")
    with pytest.raises(CostModelValidationError):
        model.normalize_retrieval_costs({"mismatched_key": obj})


# ---------------------------------------------------------------------------
# Method 2: estimate_backend_cost_saved Tests
# ---------------------------------------------------------------------------


def test_backend_cost_saved_with_zero_requests(model: CostModel) -> None:
    """Zero cached requests yields exactly 0.0 saved cost."""
    obj = make_obj("A", retrieval_cost_ms=100.0)
    saved = model.estimate_backend_cost_saved(obj, cached_requests=0)
    assert saved == 0.0


def test_backend_cost_saved_with_multiple_requests(model: CostModel) -> None:
    """Formula: retrieval_cost_ms * cached_requests * backend_cost_per_ms."""
    obj = make_obj("A", retrieval_cost_ms=25.0)
    # 25.0 ms * 10 requests * 1.5 cost/ms = 375.0
    saved = model.estimate_backend_cost_saved(
        obj, cached_requests=10, backend_cost_per_ms=1.5
    )
    assert saved == pytest.approx(375.0)


def test_backend_cost_saved_with_default_rate(model: CostModel) -> None:
    """Default backend_cost_per_ms is 1.0."""
    obj = make_obj("A", retrieval_cost_ms=50.0)
    # 50.0 ms * 4 requests * 1.0 = 200.0
    saved = model.estimate_backend_cost_saved(obj, cached_requests=4)
    assert saved == pytest.approx(200.0)


@pytest.mark.parametrize("invalid_req", [-1, -100])
def test_backend_cost_saved_negative_requests_raises_error(
    model: CostModel, invalid_req: int
) -> None:
    """Negative cached_requests raises CostModelValidationError."""
    obj = make_obj("A")
    with pytest.raises(CostModelValidationError):
        model.estimate_backend_cost_saved(obj, cached_requests=invalid_req)


@pytest.mark.parametrize("bad_arg", [True, False, 5.5, "10", None])
def test_backend_cost_saved_non_integer_requests_raises_error(
    model: CostModel, bad_arg: object
) -> None:
    """Boolean or non-integer cached_requests raises CostModelValidationError."""
    obj = make_obj("A")
    with pytest.raises(CostModelValidationError):
        model.estimate_backend_cost_saved(obj, cached_requests=bad_arg)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "bad_rate", [-0.1, -5.0, True, False, "1.0", float("inf"), float("nan")]
)
def test_backend_cost_saved_invalid_rate_raises_error(
    model: CostModel, bad_rate: object
) -> None:
    """Negative, bool, non-numeric, or non-finite backend_cost_per_ms raises error."""
    obj = make_obj("A")
    with pytest.raises(CostModelValidationError):
        model.estimate_backend_cost_saved(
            obj,
            cached_requests=5,
            backend_cost_per_ms=bad_rate,  # type: ignore[arg-type]
        )


def test_backend_cost_saved_invalid_object_raises_error(
    model: CostModel,
) -> None:
    """Non-CacheObject argument raises CostModelValidationError."""
    with pytest.raises(CostModelValidationError):
        model.estimate_backend_cost_saved("not_an_obj", cached_requests=5)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Method 3: estimate_cache_ram_cost Tests
# ---------------------------------------------------------------------------


def test_ram_cost_calculation(model: CostModel) -> None:
    """Formula: (size_bytes / 1_000_000_000) * cache_ram_cost_per_gb_hour * hours."""
    # 2 GB = 2_000_000_000 bytes. Rate = 0.10. Hours = 5.0.
    # Cost = 2.0 * 0.10 * 5.0 = 1.0
    cost = model.estimate_cache_ram_cost(
        size_bytes=2_000_000_000,
        cache_ram_cost_per_gb_hour=0.10,
        hours=5.0,
    )
    assert cost == pytest.approx(1.0)


def test_decimal_gb_conversion(model: CostModel) -> None:
    """Verify decimal gigabyte conversion uses exactly 1_000_000_000 bytes per GB."""
    assert BYTES_PER_GB == 1_000_000_000
    # 500_000_000 bytes = 0.5 GB. Rate = 0.20. Hours = 1.0. Cost = 0.10.
    cost = model.estimate_cache_ram_cost(
        size_bytes=500_000_000,
        cache_ram_cost_per_gb_hour=0.20,
        hours=1.0,
    )
    assert cost == pytest.approx(0.10)


def test_zero_size_object_ram_cost(model: CostModel) -> None:
    """Zero-size object has 0.0 RAM cost."""
    cost = model.estimate_cache_ram_cost(
        size_bytes=0,
        cache_ram_cost_per_gb_hour=0.50,
        hours=10.0,
    )
    assert cost == 0.0


def test_zero_hours_ram_cost(model: CostModel) -> None:
    """Zero hours yields 0.0 RAM cost."""
    cost = model.estimate_cache_ram_cost(
        size_bytes=1_000_000,
        cache_ram_cost_per_gb_hour=0.50,
        hours=0.0,
    )
    assert cost == 0.0


@pytest.mark.parametrize("invalid_size", [-1, -500, True, False, 100.5, "1000", None])
def test_ram_cost_invalid_size_raises_error(
    model: CostModel, invalid_size: object
) -> None:
    """Negative, boolean, non-integer size_bytes raises CostModelValidationError."""
    with pytest.raises(CostModelValidationError):
        model.estimate_cache_ram_cost(
            size_bytes=invalid_size,  # type: ignore[arg-type]
            cache_ram_cost_per_gb_hour=0.10,
        )


@pytest.mark.parametrize(
    "bad_rate", [-0.1, -5.0, True, False, "0.10", float("inf"), float("nan")]
)
def test_ram_cost_invalid_rate_raises_error(model: CostModel, bad_rate: object) -> None:
    """Negative, boolean, non-numeric, or non-finite rate raises error."""
    with pytest.raises(CostModelValidationError):
        model.estimate_cache_ram_cost(
            size_bytes=1000,
            cache_ram_cost_per_gb_hour=bad_rate,  # type: ignore[arg-type]
        )


@pytest.mark.parametrize(
    "bad_hours", [-0.5, -10.0, True, False, "1.0", float("inf"), float("nan")]
)
def test_ram_cost_invalid_hours_raises_error(
    model: CostModel, bad_hours: object
) -> None:
    """Negative, boolean, non-numeric, or non-finite hours raises error."""
    with pytest.raises(CostModelValidationError):
        model.estimate_cache_ram_cost(
            size_bytes=1000,
            cache_ram_cost_per_gb_hour=0.10,
            hours=bad_hours,  # type: ignore[arg-type]
        )


# ---------------------------------------------------------------------------
# Method 4: estimate_net_benefit Tests
# ---------------------------------------------------------------------------


def test_net_benefit_positive(model: CostModel) -> None:
    """Positive net benefit when backend savings exceed cache RAM cost."""
    # Object: size = 100_000 bytes (0.0001 GB), retrieval = 50.0 ms
    # Saved: 50.0 * 100 requests * 1.0 = 5000.0
    # RAM cost: 0.0001 GB * 0.10/GB-hr * 1 hr = 0.00001
    # Net benefit = 5000.0 - 0.00001 > 0
    obj = make_obj("valuable", size_bytes=100_000, retrieval_cost_ms=50.0)
    benefit = model.estimate_net_benefit(obj, cached_requests=100)
    assert benefit > 0.0
    assert benefit == pytest.approx(5000.0 - 0.00001)


def test_net_benefit_negative(model: CostModel) -> None:
    """Negative net benefit when cache RAM cost exceeds backend savings."""
    # Huge object (10 GB = 10_000_000_000 bytes), cheap regeneration (1.0 ms)
    # Saved: 1.0 ms * 1 req * 1.0 = 1.0
    # RAM cost: 10 GB * 1.0/GB-hr * 1 hr = 10.0
    # Net benefit = 1.0 - 10.0 = -9.0
    obj = make_obj("huge_cheap", size_bytes=10_000_000_000, retrieval_cost_ms=1.0)
    benefit = model.estimate_net_benefit(
        obj,
        cached_requests=1,
        backend_cost_per_ms=1.0,
        cache_ram_cost_per_gb_hour=1.0,
        hours=1.0,
    )
    assert benefit < 0.0
    assert benefit == pytest.approx(-9.0)


def test_net_benefit_zero(model: CostModel) -> None:
    """Zero net benefit when savings exactly equal RAM cost."""
    # size = 1_000_000_000 bytes (1.0 GB). RAM cost = 1.0 * 0.10 * 1 = 0.10.
    # retrieval = 0.10 ms, requests = 1, cost_per_ms = 1.0 -> Saved = 0.10.
    # Net benefit = 0.10 - 0.10 = 0.0.
    obj = make_obj("neutral", size_bytes=1_000_000_000, retrieval_cost_ms=0.10)
    benefit = model.estimate_net_benefit(
        obj,
        cached_requests=1,
        backend_cost_per_ms=1.0,
        cache_ram_cost_per_gb_hour=0.10,
        hours=1.0,
    )
    assert benefit == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# Method 5: value_density Tests
# ---------------------------------------------------------------------------


def test_value_density_calculation(model: CostModel) -> None:
    """Formula: score / (size_bytes ^ alpha) with default alpha=1.0."""
    # score = 0.8, size = 1000, alpha = 1.0 -> 0.8 / 1000 = 0.0008
    vd = model.value_density(score=0.8, size_bytes=1000)
    assert vd == pytest.approx(0.0008)


def test_value_density_with_alpha_other_than_one(model: CostModel) -> None:
    """Verify value density scaling with non-unit alpha."""
    # score = 0.9, size = 100, alpha = 0.5 -> 0.9 / (100 ^ 0.5) = 0.9 / 10 = 0.09
    vd = model.value_density(score=0.9, size_bytes=100, alpha=0.5)
    assert vd == pytest.approx(0.09)


def test_value_density_zero_score(model: CostModel) -> None:
    """Score of 0.0 produces value density 0.0."""
    vd = model.value_density(score=0.0, size_bytes=500)
    assert vd == 0.0


def test_value_density_max_score(model: CostModel) -> None:
    """Score of 1.0 produces 1 / (size ^ alpha)."""
    vd = model.value_density(score=1.0, size_bytes=200, alpha=2.0)
    assert vd == pytest.approx(1.0 / 40000.0)


@pytest.mark.parametrize(
    "invalid_score",
    [-0.1, 1.01, -5.0, 2.0, True, False, "0.5", float("inf"), float("nan")],
)
def test_value_density_invalid_score_raises_error(
    model: CostModel, invalid_score: object
) -> None:
    """Score outside [0, 1], boolean, non-numeric, or non-finite raises error."""
    with pytest.raises(CostModelValidationError):
        model.value_density(score=invalid_score, size_bytes=100)  # type: ignore[arg-type]


@pytest.mark.parametrize("invalid_size", [0, -1, -500, True, False, 100.5, "100", None])
def test_value_density_invalid_size_raises_error(
    model: CostModel, invalid_size: object
) -> None:
    """size_bytes <= 0, boolean, non-integer raises CostModelValidationError."""
    with pytest.raises(CostModelValidationError):
        model.value_density(score=0.5, size_bytes=invalid_size)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "invalid_alpha", [0.0, -1.0, -0.5, True, False, "1.0", float("inf"), float("nan")]
)
def test_value_density_invalid_alpha_raises_error(
    model: CostModel, invalid_alpha: object
) -> None:
    """alpha <= 0, bool, non-numeric, or non-finite raises CostModelValidationError."""
    with pytest.raises(CostModelValidationError):
        model.value_density(score=0.5, size_bytes=100, alpha=invalid_alpha)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Immutability & Determinism Tests
# ---------------------------------------------------------------------------


def test_input_objects_mapping_is_not_mutated(model: CostModel, now: datetime) -> None:
    """Input objects mapping and CacheObject instances are not modified."""
    obj_a = make_obj("A", size_bytes=500, retrieval_cost_ms=25.0, now=now)
    obj_b = make_obj("B", size_bytes=1000, retrieval_cost_ms=75.0, now=now)
    objects = {"A": obj_a, "B": obj_b}

    dump_a = obj_a.model_dump()
    dump_b = obj_b.model_dump()
    keys_before = list(objects.keys())

    model.normalize_retrieval_costs(objects)
    model.estimate_net_benefit(obj_a, cached_requests=10)

    assert list(objects.keys()) == keys_before
    assert obj_a.model_dump() == dump_a
    assert obj_b.model_dump() == dump_b


def test_cost_model_determinism(model: CostModel) -> None:
    """Repeated invocations with identical inputs yield identical outputs."""
    objects = {
        "A": make_obj("A", retrieval_cost_ms=10.0),
        "B": make_obj("B", retrieval_cost_ms=50.0),
        "C": make_obj("C", retrieval_cost_ms=100.0),
    }
    res1 = model.normalize_retrieval_costs(objects)
    res2 = model.normalize_retrieval_costs(objects)
    assert res1 == res2

    b1 = model.estimate_net_benefit(objects["A"], cached_requests=25)
    b2 = model.estimate_net_benefit(objects["A"], cached_requests=25)
    assert b1 == b2

    vd1 = model.value_density(0.75, 500, 1.2)
    vd2 = model.value_density(0.75, 500, 1.2)
    assert vd1 == vd2


def test_class_level_constants() -> None:
    """Constants are defined on the class and module level."""
    assert CostModel.BYTES_PER_GB == BYTES_PER_GB == 1_000_000_000
    assert CostModel.DEFAULT_BACKEND_COST_PER_MS == DEFAULT_BACKEND_COST_PER_MS == 1.0
    assert (
        CostModel.DEFAULT_CACHE_RAM_COST_PER_GB_HOUR
        == DEFAULT_CACHE_RAM_COST_PER_GB_HOUR
        == 0.10
    )
    assert CostModel.DEFAULT_HOURS == DEFAULT_HOURS == 1.0
    assert CostModel.DEFAULT_ALPHA == DEFAULT_ALPHA == 1.0
