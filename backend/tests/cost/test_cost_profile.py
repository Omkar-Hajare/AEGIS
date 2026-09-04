"""Unit tests for CostProfile and platform-aware CostModel integration.

Tests cover:
- CostProfile validation, immutability, and edge cases
- Predefined example profiles (PostgreSQL, MySQL, External API, Default)
- CostModel dependency injection with custom CostProfile
- Economic divergence across different profiles (backend savings, RAM costs, net benefit)
- Backward compatibility with legacy CostModel defaults
- Platform-agnostic DecisionEngine integration
- Deterministic behavior
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import datetime, timezone

import pytest

from backend.adaptive.engine.decision_engine import DecisionEngine
from backend.cost import (
    DEFAULT_PROFILE,
    EXTERNAL_API_PROFILE,
    MYSQL_PROFILE,
    POSTGRESQL_PROFILE,
    PROFILES,
    CostModel,
    CostModelValidationError,
    CostProfile,
    get_profile,
)
from contracts.schemas import CacheObject, SystemState, WorkloadState


@pytest.fixture
def now() -> datetime:
    """Fixture providing a fixed timezone-aware timestamp."""
    return datetime(2026, 9, 5, 12, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
def sample_object(now: datetime) -> CacheObject:
    """Fixture providing a standard test CacheObject."""
    return CacheObject(
        key="sample_key",
        size_bytes=1_000_000,  # 1 MB
        access_count=50,
        last_accessed=now,
        retrieval_cost_ms=50.0,
    )


@pytest.fixture
def base_system(now: datetime) -> SystemState:
    """Fixture providing a standard test SystemState."""
    return SystemState(
        cache_capacity_bytes=10_000_000,
        cache_usage_bytes=5_000_000,
        object_count=10,
        window_seconds=60.0,
        timestamp=now,
    )


@pytest.fixture
def base_workload(now: datetime) -> WorkloadState:
    """Fixture providing a standard test WorkloadState."""
    return WorkloadState(
        request_rate=200.0,
        hit_rate=0.75,
        miss_rate=0.25,
        backend_latency_ms=45.0,
        window_seconds=60.0,
        timestamp=now,
    )


# ---------------------------------------------------------------------------
# 1. CostProfile Initialization and Validation Tests
# ---------------------------------------------------------------------------


def test_cost_profile_default_initialization() -> None:
    """CostProfile initializes with sensible defaults when only name is provided."""
    profile = CostProfile(name="custom_profile")
    assert profile.name == "custom_profile"
    assert profile.backend_cost_per_request == 0.0
    assert profile.backend_cost_per_ms == 1.0
    assert profile.cache_memory_cost_per_gb_hour == 0.10
    assert profile.metadata is None


def test_cost_profile_full_initialization() -> None:
    """CostProfile accepts and stores all valid numeric parameters and metadata."""
    meta = {"tier": "premium", "cloud": "simulated"}
    profile = CostProfile(
        name="full_profile",
        backend_cost_per_request=0.005,
        backend_cost_per_ms=2.5,
        cache_memory_cost_per_gb_hour=0.25,
        metadata=meta,
    )
    assert profile.name == "full_profile"
    assert profile.backend_cost_per_request == 0.005
    assert profile.backend_cost_per_ms == 2.5
    assert profile.cache_memory_cost_per_gb_hour == 0.25
    assert profile.metadata == meta


def test_cost_profile_coerces_integers_to_float() -> None:
    """Integer numeric values are converted to float."""
    profile = CostProfile(
        name="int_profile",
        backend_cost_per_request=1,
        backend_cost_per_ms=3,
        cache_memory_cost_per_gb_hour=2,
    )
    assert isinstance(profile.backend_cost_per_request, float)
    assert isinstance(profile.backend_cost_per_ms, float)
    assert isinstance(profile.cache_memory_cost_per_gb_hour, float)
    assert profile.backend_cost_per_request == 1.0
    assert profile.backend_cost_per_ms == 3.0
    assert profile.cache_memory_cost_per_gb_hour == 2.0


def test_cost_profile_immutability() -> None:
    """CostProfile is frozen and disallows field re-assignment."""
    profile = CostProfile(name="immutable_profile")
    with pytest.raises((FrozenInstanceError, AttributeError)):
        profile.name = "new_name"  # type: ignore[misc]
    with pytest.raises((FrozenInstanceError, AttributeError)):
        profile.backend_cost_per_ms = 5.0  # type: ignore[misc]


def test_cost_profile_metadata_is_snapshot() -> None:
    """Mutating external metadata dictionary does not affect the CostProfile snapshot."""
    external_meta = {"key": "original_value"}
    profile = CostProfile(name="meta_test", metadata=external_meta)
    external_meta["key"] = "mutated_value"
    assert profile.metadata is not None
    assert profile.metadata["key"] == "original_value"


@pytest.mark.parametrize(
    "invalid_name",
    ["", "   ", "\t\n", None, 123, True, False, []],
)
def test_cost_profile_invalid_name(invalid_name: object) -> None:
    """Empty, non-string, or boolean names raise CostModelValidationError."""
    with pytest.raises(CostModelValidationError):
        CostProfile(name=invalid_name)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "field",
    [
        "backend_cost_per_request",
        "backend_cost_per_ms",
        "cache_memory_cost_per_gb_hour",
    ],
)
@pytest.mark.parametrize(
    "invalid_val",
    [
        -0.01,
        -1.0,
        float("inf"),
        float("-inf"),
        float("nan"),
        "invalid",
        True,
        False,
        None,
    ],
)
def test_cost_profile_invalid_numeric_fields(field: str, invalid_val: object) -> None:
    """Negative, non-finite, non-numeric, or boolean costs raise CostModelValidationError."""
    kwargs = {field: invalid_val}
    with pytest.raises(CostModelValidationError):
        CostProfile(name="test", **kwargs)  # type: ignore[arg-type]


def test_cost_profile_invalid_metadata_type() -> None:
    """Non-mapping metadata raises CostModelValidationError."""
    with pytest.raises(CostModelValidationError):
        CostProfile(name="test", metadata="not_a_mapping")  # type: ignore[arg-type]
    with pytest.raises(CostModelValidationError):
        CostProfile(name="test", metadata=[1, 2, 3])  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# 2. Predefined Example Profiles and Registry Tests
# ---------------------------------------------------------------------------


def test_example_profiles_structure_and_constants() -> None:
    """Predefined profiles exist with valid attributes and distinct values."""
    assert len(PROFILES) >= 4
    assert "postgresql" in PROFILES
    assert "mysql" in PROFILES
    assert "external_api" in PROFILES
    assert "default" in PROFILES

    assert DEFAULT_PROFILE.name == "default"
    assert DEFAULT_PROFILE.backend_cost_per_request == 0.0
    assert DEFAULT_PROFILE.backend_cost_per_ms == 1.0
    assert DEFAULT_PROFILE.cache_memory_cost_per_gb_hour == 0.10

    assert POSTGRESQL_PROFILE.name == "postgresql"
    assert POSTGRESQL_PROFILE.backend_cost_per_request > 0.0
    assert POSTGRESQL_PROFILE.backend_cost_per_ms == 0.50

    assert MYSQL_PROFILE.name == "mysql"
    assert MYSQL_PROFILE.backend_cost_per_request > 0.0
    assert MYSQL_PROFILE.backend_cost_per_ms == 0.60

    assert EXTERNAL_API_PROFILE.name == "external_api"
    assert EXTERNAL_API_PROFILE.backend_cost_per_request == 0.020
    assert EXTERNAL_API_PROFILE.backend_cost_per_ms == 2.00
    assert EXTERNAL_API_PROFILE.cache_memory_cost_per_gb_hour == 0.15


def test_get_profile_lookup() -> None:
    """get_profile retrieves profiles case-insensitively from PROFILES registry."""
    assert get_profile("postgresql") is POSTGRESQL_PROFILE
    assert get_profile("PostgreSQL") is POSTGRESQL_PROFILE
    assert get_profile("MYSQL") is MYSQL_PROFILE
    assert get_profile("external_api") is EXTERNAL_API_PROFILE
    assert get_profile("default") is DEFAULT_PROFILE


def test_get_profile_unknown_or_invalid() -> None:
    """get_profile raises CostModelValidationError for unknown or invalid names."""
    with pytest.raises(CostModelValidationError, match="Unknown cost profile"):
        get_profile("nonexistent_profile")
    with pytest.raises(CostModelValidationError):
        get_profile("")
    with pytest.raises(CostModelValidationError):
        get_profile(123)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# 3. CostModel Dependency Injection & Economic Divergence Tests
# ---------------------------------------------------------------------------


def test_cost_model_default_profile_injection() -> None:
    """CostModel with no arguments defaults to DEFAULT_PROFILE."""
    model = CostModel()
    assert model.profile is DEFAULT_PROFILE
    assert model.profile.name == "default"


def test_cost_model_custom_profile_injection() -> None:
    """CostModel accepts injected CostProfile through constructor."""
    model = CostModel(profile=POSTGRESQL_PROFILE)
    assert model.profile is POSTGRESQL_PROFILE
    assert model.profile.name == "postgresql"


def test_cost_model_invalid_profile_type() -> None:
    """Passing an invalid object as profile raises CostModelValidationError."""
    with pytest.raises(CostModelValidationError):
        CostModel(profile="not_a_cost_profile")  # type: ignore[arg-type]


def test_different_profiles_produce_different_backend_savings(
    sample_object: CacheObject,
) -> None:
    """Identical CacheObject produces divergent backend cost savings under different profiles.

    Object: retrieval_cost_ms=50.0, cached_requests=100
    - DEFAULT: 100 * (0.0 + 50.0 * 1.0) = 5000.0
    - POSTGRESQL: 100 * (0.002 + 50.0 * 0.50) = 100 * 25.002 = 2500.2
    - MYSQL: 100 * (0.0015 + 50.0 * 0.60) = 100 * 30.0015 = 3000.15
    - EXTERNAL_API: 100 * (0.020 + 50.0 * 2.00) = 100 * 100.02 = 10002.0
    """
    model_default = CostModel(profile=DEFAULT_PROFILE)
    model_pg = CostModel(profile=POSTGRESQL_PROFILE)
    model_mysql = CostModel(profile=MYSQL_PROFILE)
    model_api = CostModel(profile=EXTERNAL_API_PROFILE)

    saved_default = model_default.estimate_backend_cost_saved(
        sample_object, cached_requests=100
    )
    saved_pg = model_pg.estimate_backend_cost_saved(sample_object, cached_requests=100)
    saved_mysql = model_mysql.estimate_backend_cost_saved(
        sample_object, cached_requests=100
    )
    saved_api = model_api.estimate_backend_cost_saved(
        sample_object, cached_requests=100
    )

    assert saved_default == pytest.approx(5000.0)
    assert saved_pg == pytest.approx(2500.2)
    assert saved_mysql == pytest.approx(3000.15)
    assert saved_api == pytest.approx(10002.0)

    # Ordering verification: external API is most expensive to regenerate, Postgres is cheapest
    assert saved_api > saved_default > saved_mysql > saved_pg


def test_different_profiles_produce_different_ram_costs() -> None:
    """Identical size and retention duration produce divergent RAM costs across profiles."""
    size_bytes = 100_000_000  # 0.1 GB
    hours = 10.0

    model_default = CostModel(profile=DEFAULT_PROFILE)  # 0.10 / GB-hr
    model_pg = CostModel(profile=POSTGRESQL_PROFILE)  # 0.12 / GB-hr
    model_api = CostModel(profile=EXTERNAL_API_PROFILE)  # 0.15 / GB-hr

    ram_default = model_default.estimate_cache_ram_cost(
        size_bytes=size_bytes, hours=hours
    )
    ram_pg = model_pg.estimate_cache_ram_cost(size_bytes=size_bytes, hours=hours)
    ram_api = model_api.estimate_cache_ram_cost(size_bytes=size_bytes, hours=hours)

    assert ram_default == pytest.approx(0.10)
    assert ram_pg == pytest.approx(0.12)
    assert ram_api == pytest.approx(0.15)
    assert ram_api > ram_pg > ram_default


def test_different_profiles_change_net_economic_benefit(now: datetime) -> None:
    """Net benefit calculation shifts depending on platform economics."""
    # Object A: Fast DB query with relatively large size (50 MB, 5 ms retrieval)
    obj_a = CacheObject(
        key="query_table_scan",
        size_bytes=50_000_000,
        access_count=20,
        last_accessed=now,
        retrieval_cost_ms=5.0,
    )
    # Object B: Small external API response with slow latency (10 KB, 300 ms retrieval)
    obj_b = CacheObject(
        key="api_credit_score",
        size_bytes=10_000,
        access_count=20,
        last_accessed=now,
        retrieval_cost_ms=300.0,
    )

    model_pg = CostModel(profile=POSTGRESQL_PROFILE)
    model_api = CostModel(profile=EXTERNAL_API_PROFILE)

    benefit_a_pg = model_pg.estimate_net_benefit(obj_a, cached_requests=10, hours=2.0)
    benefit_b_api = model_api.estimate_net_benefit(obj_b, cached_requests=10, hours=2.0)

    # Object B under external API produces vastly higher net economic benefit
    # due to high API per-request overhead and latency avoidance
    assert benefit_b_api > benefit_a_pg


def test_backward_compatibility_with_legacy_defaults(
    sample_object: CacheObject,
) -> None:
    """Default CostModel() preserves exact legacy formulas and results without arguments."""
    model = CostModel()

    # Legacy formula: retrieval_cost_ms * cached_requests * 1.0
    saved = model.estimate_backend_cost_saved(sample_object, cached_requests=10)
    expected_saved = 50.0 * 10 * 1.0
    assert saved == expected_saved

    # Legacy formula: (size / 1e9) * 0.10 * 1.0
    ram = model.estimate_cache_ram_cost(size_bytes=sample_object.size_bytes)
    expected_ram = (1_000_000 / 1_000_000_000) * 0.10 * 1.0
    assert ram == expected_ram

    # Explicit parameter overrides still work seamlessly
    custom_saved = model.estimate_backend_cost_saved(
        sample_object, cached_requests=10, backend_cost_per_ms=3.0
    )
    assert custom_saved == 50.0 * 10 * 3.0


# ---------------------------------------------------------------------------
# 4. DecisionEngine Platform-Agnostic Integration Tests
# ---------------------------------------------------------------------------


def test_decision_engine_default_cost_profile(
    base_workload: WorkloadState,
    base_system: SystemState,
    sample_object: CacheObject,
    now: datetime,
) -> None:
    """DecisionEngine defaults to 'default' cost_profile in decision metadata."""
    engine = DecisionEngine()
    assert engine.cost_model.profile.name == "default"

    objects = {sample_object.key: sample_object}
    decision = engine.decide(
        objects=objects,
        workload=base_workload,
        system=base_system,
        min_capacity_bytes=1_000_000,
        max_capacity_bytes=20_000_000,
        now=now,
    )
    assert decision.metadata.get("cost_profile") == "default"


def test_decision_engine_injected_cost_profile(
    base_workload: WorkloadState,
    base_system: SystemState,
    sample_object: CacheObject,
    now: datetime,
) -> None:
    """DecisionEngine accepts injected CostModel and exposes cost_profile in metadata."""
    custom_model = CostModel(profile=POSTGRESQL_PROFILE)
    engine = DecisionEngine(cost_model=custom_model)
    assert engine.cost_model is custom_model
    assert engine.cost_model.profile.name == "postgresql"

    objects = {sample_object.key: sample_object}
    decision = engine.decide(
        objects=objects,
        workload=base_workload,
        system=base_system,
        min_capacity_bytes=1_000_000,
        max_capacity_bytes=20_000_000,
        now=now,
    )
    assert decision.metadata.get("cost_profile") == "postgresql"


def test_decision_engine_external_api_profile_eviction_integration(
    base_workload: WorkloadState,
    base_system: SystemState,
    now: datetime,
) -> None:
    """DecisionEngine works with external API profile during eviction without knowing platform."""
    api_model = CostModel(profile=EXTERNAL_API_PROFILE)
    engine = DecisionEngine(cost_model=api_model)

    obj_cheap = CacheObject(
        key="cheap_local",
        size_bytes=4_000_000,
        access_count=1,
        last_accessed=now,
        retrieval_cost_ms=5.0,
    )
    obj_expensive = CacheObject(
        key="expensive_api",
        size_bytes=4_000_000,
        access_count=1,
        last_accessed=now,
        retrieval_cost_ms=500.0,
    )

    objects = {obj_cheap.key: obj_cheap, obj_expensive.key: obj_expensive}
    # Usage is 8 MB, min capacity is 5 MB -> forces 1 eviction
    decision = engine.decide(
        objects=objects,
        workload=base_workload,
        system=base_system,
        min_capacity_bytes=1_000_000,
        max_capacity_bytes=5_000_000,
        now=now,
    )
    assert decision.metadata.get("cost_profile") == "external_api"
    # Cheap local should be evicted first, protecting the expensive external API item
    assert "cheap_local" in decision.eviction_keys
    assert "expensive_api" not in decision.eviction_keys


# ---------------------------------------------------------------------------
# 5. Determinism Tests
# ---------------------------------------------------------------------------


def test_cost_model_determinism(sample_object: CacheObject) -> None:
    """Cost calculations are 100% deterministic across multiple invocations."""
    model = CostModel(profile=POSTGRESQL_PROFILE)

    saved_runs = [
        model.estimate_backend_cost_saved(sample_object, cached_requests=42)
        for _ in range(50)
    ]
    ram_runs = [
        model.estimate_cache_ram_cost(sample_object.size_bytes, hours=3.5)
        for _ in range(50)
    ]
    benefit_runs = [
        model.estimate_net_benefit(sample_object, cached_requests=42, hours=3.5)
        for _ in range(50)
    ]

    assert len(set(saved_runs)) == 1
    assert len(set(ram_runs)) == 1
    assert len(set(benefit_runs)) == 1
