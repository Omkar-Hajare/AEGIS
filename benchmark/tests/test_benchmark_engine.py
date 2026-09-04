"""Comprehensive test suite for the benchmark engine.

Tests determinism, policy isolation, identical replay fairness, metric accuracy,
capacity constraints, scenario variations, and error handling.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from backend.workload.generator import ScenarioGenerator
from backend.workload.scenario import (
    PRODUCT_CATALOG_PROFILE,
    RECOMMENDATIONS_PROFILE,
    ScenarioConfig,
    ScenarioEvent,
)
from benchmark import (
    SUPPORTED_POLICIES,
    AdaptivePolicyAdapter,
    BenchmarkConfig,
    BenchmarkMetrics,
    BenchmarkResult,
    BenchmarkRunner,
    BenchmarkSuiteResult,
    CacheSimulator,
    GDSPolicyAdapter,
    LFUPolicyAdapter,
    LRUPolicyAdapter,
    calculate_percentile,
    compute_benchmark_metrics,
    deserialize_suite_result,
    format_summary_table,
    get_policy_adapter,
    serialize_suite_result,
)
from contracts.schemas.enums import WorkloadType


@pytest.fixture
def sample_events() -> list[ScenarioEvent]:
    """Provide a deterministic small sequence of ScenarioEvents for unit testing."""
    start = datetime(2026, 9, 4, 12, 0, 0, tzinfo=timezone.utc)
    keys = ["obj_1", "obj_2", "obj_1", "obj_2", "obj_3", "obj_1", "obj_1"]
    events: list[ScenarioEvent] = []
    for i, key in enumerate(keys):
        events.append(
            ScenarioEvent(
                timestamp=start + timedelta(seconds=i),
                key=key,
                workload_type=WorkloadType.READ_HEAVY,
                backend_latency_ms=10.0,
                object_size_bytes=1000,
                retrieval_cost_ms=10.0,
                request_rate=1.0,
                metadata={"test": True},
            )
        )
    return events


@pytest.fixture
def steady_events() -> list[ScenarioEvent]:
    """Generate 100 steady requests using ScenarioGenerator."""
    cfg = ScenarioConfig(
        name="steady",
        scenario_type="steady",
        seed=42,
        object_count=20,
        request_count=100,
        request_rate=100.0,
        profile=PRODUCT_CATALOG_PROFILE,
    )
    return ScenarioGenerator(cfg).generate()


class TestBenchmarkModels:
    """Tests for BenchmarkConfig, BenchmarkMetrics, and result models."""

    def test_valid_config(self) -> None:
        cfg = BenchmarkConfig(cache_capacity_bytes=10000)
        assert cfg.cache_capacity_bytes == 10000
        assert cfg.cache_hit_latency_ms == 1.0
        assert cfg.policies == SUPPORTED_POLICIES

    def test_config_rejects_bool_for_numeric(self) -> None:
        with pytest.raises(TypeError, match="Boolean values are not allowed"):
            BenchmarkConfig(cache_capacity_bytes=True)  # type: ignore[arg-type]

        with pytest.raises(TypeError, match="Boolean values are not allowed"):
            BenchmarkConfig(
                cache_capacity_bytes=1000,
                cache_hit_latency_ms=False,  # type: ignore[arg-type]
            )

    def test_config_rejects_invalid_capacity(self) -> None:
        with pytest.raises(ValueError):
            BenchmarkConfig(cache_capacity_bytes=0)
        with pytest.raises(ValueError):
            BenchmarkConfig(cache_capacity_bytes=-500)

    def test_config_rejects_empty_or_duplicate_policies(self) -> None:
        with pytest.raises(ValueError, match="policies list must not be empty"):
            BenchmarkConfig(cache_capacity_bytes=1000, policies=())

        with pytest.raises(ValueError, match="Duplicate policy name"):
            BenchmarkConfig(cache_capacity_bytes=1000, policies=("LRU", "lru"))

    def test_config_capacity_bounds(self) -> None:
        with pytest.raises(ValueError, match="min_capacity_bytes .* cannot exceed"):
            BenchmarkConfig(
                cache_capacity_bytes=1000,
                min_capacity_bytes=2000,
            )
        with pytest.raises(ValueError, match="max_capacity_bytes .* must be >="):
            BenchmarkConfig(
                cache_capacity_bytes=1000,
                max_capacity_bytes=500,
            )

    def test_metrics_rejection_of_bool(self) -> None:
        with pytest.raises(TypeError, match="Boolean values are not allowed"):
            BenchmarkMetrics(
                total_requests=True,  # type: ignore[arg-type]
                cache_hits=0,
                cache_misses=0,
                hit_ratio=0.0,
                miss_ratio=0.0,
                backend_requests=0,
                backend_requests_prevented=0,
                backend_latency_total_ms=0.0,
                average_latency_ms=0.0,
                p99_latency_ms=0.0,
                eviction_count=0,
                cache_capacity_bytes=1000,
                peak_cache_usage_bytes=0,
            )


class TestPercentileAndMetrics:
    """Tests for calculate_percentile and compute_benchmark_metrics."""

    def test_calculate_percentile_single_value(self) -> None:
        assert calculate_percentile([42.0], 50.0) == 42.0
        assert calculate_percentile([42.0], 99.0) == 42.0

    def test_calculate_percentile_interpolation(self) -> None:
        data = list(range(101))  # 0 to 100
        # 50th percentile should be 50.0
        assert calculate_percentile(data, 50.0) == 50.0
        # 99th percentile of 0..100: rank = 0.99 * 100 = 99.0 -> 99.0
        assert calculate_percentile(data, 99.0) == 99.0

    def test_calculate_percentile_validation(self) -> None:
        with pytest.raises(ValueError, match="must not be empty"):
            calculate_percentile([], 99.0)

        with pytest.raises(TypeError, match="percentile must be numeric"):
            calculate_percentile([1.0, 2.0], True)  # type: ignore[arg-type]

        with pytest.raises(ValueError, match="between 0.0 and 100.0"):
            calculate_percentile([1.0, 2.0], 105.0)

        with pytest.raises(TypeError, match="must be a numeric sequence"):
            calculate_percentile("not-a-sequence", 50.0)  # type: ignore[arg-type]

    def test_compute_benchmark_metrics_zero_requests(self) -> None:
        metrics = compute_benchmark_metrics(
            total_requests=0,
            cache_hits=0,
            cache_misses=0,
            latencies=[],
            backend_latency_total_ms=0.0,
            eviction_count=0,
            cache_capacity_bytes=5000,
            peak_cache_usage_bytes=0,
        )
        assert metrics.total_requests == 0
        assert metrics.hit_ratio == 0.0
        assert metrics.miss_ratio == 0.0
        assert metrics.average_latency_ms == 0.0
        assert metrics.p99_latency_ms == 0.0

    def test_compute_benchmark_metrics_standard(self) -> None:
        latencies = [1.0, 1.0, 11.0, 11.0]
        metrics = compute_benchmark_metrics(
            total_requests=4,
            cache_hits=2,
            cache_misses=2,
            latencies=latencies,
            backend_latency_total_ms=20.0,
            eviction_count=1,
            cache_capacity_bytes=5000,
            peak_cache_usage_bytes=2000,
        )
        assert metrics.total_requests == 4
        assert metrics.cache_hits == 2
        assert metrics.cache_misses == 2
        assert metrics.hit_ratio == 0.5
        assert metrics.miss_ratio == 0.5
        assert metrics.backend_requests == 2
        assert metrics.backend_requests_prevented == 2
        assert metrics.average_latency_ms == 6.0
        assert metrics.eviction_count == 1
        assert metrics.peak_cache_usage_bytes == 2000


class TestPolicyAdapters:
    """Tests for individual policy adapter behavior."""

    def test_get_policy_adapter_resolution(self) -> None:
        assert isinstance(get_policy_adapter("LRU"), LRUPolicyAdapter)
        assert isinstance(get_policy_adapter("lfu"), LFUPolicyAdapter)
        assert isinstance(get_policy_adapter("Gds"), GDSPolicyAdapter)
        assert isinstance(get_policy_adapter("adaptive"), AdaptivePolicyAdapter)

        custom = LRUPolicyAdapter()
        assert get_policy_adapter(custom) is custom

        with pytest.raises(ValueError, match="Unknown policy"):
            get_policy_adapter("UNKNOWN")

        with pytest.raises(TypeError, match="Expected str or BenchmarkPolicy"):
            get_policy_adapter(123)  # type: ignore[arg-type]

    def test_adapters_empty_cache_eviction(self) -> None:
        for name in ("LRU", "LFU", "GDS", "ADAPTIVE"):
            adapter = get_policy_adapter(name)
            assert adapter.select_evictions({}, target_capacity_bytes=1000) == []

    def test_adapters_reset(self) -> None:
        for name in ("LRU", "LFU", "GDS", "ADAPTIVE"):
            adapter = get_policy_adapter(name)
            adapter.reset()
            assert adapter.name == name.upper()


class TestCacheSimulator:
    """Tests for CacheSimulator hit/miss/eviction mechanics."""

    def test_simulator_hits_and_misses(
        self, sample_events: list[ScenarioEvent]
    ) -> None:
        # Capacity of 2500 bytes allows up to 2 items of 1000 bytes
        sim = CacheSimulator(capacity_bytes=2500, policy="LRU", hit_latency_ms=1.0)
        for ev in sample_events:
            sim.process_event(ev)

        metrics = sim.get_metrics()
        assert metrics.total_requests == 7
        assert metrics.cache_hits > 0
        assert metrics.cache_misses > 0
        assert metrics.cache_hits + metrics.cache_misses == 7
        assert metrics.backend_requests == metrics.cache_misses
        assert metrics.backend_requests_prevented == metrics.cache_hits
        assert metrics.eviction_count > 0
        assert metrics.peak_cache_usage_bytes <= 2500

    def test_oversized_object_handling(self) -> None:
        start = datetime(2026, 9, 4, 12, 0, 0, tzinfo=timezone.utc)
        oversized_event = ScenarioEvent(
            timestamp=start,
            key="huge_obj",
            workload_type=WorkloadType.READ_HEAVY,
            backend_latency_ms=50.0,
            object_size_bytes=10000,
            retrieval_cost_ms=50.0,
            request_rate=1.0,
        )
        sim = CacheSimulator(capacity_bytes=5000, policy="LRU", hit_latency_ms=1.0)
        latency = sim.process_event(oversized_event)

        assert latency == 51.0  # 1.0 + 50.0
        assert sim.cache_misses == 1
        assert sim.oversized_requests == 1
        assert len(sim.cache) == 0
        assert sim.eviction_count == 0

    def test_capacity_strictly_respected(
        self, steady_events: list[ScenarioEvent]
    ) -> None:
        capacity = 5000  # fits ~2 objects of 2048 bytes
        sim = CacheSimulator(capacity_bytes=capacity, policy="LRU")
        for ev in steady_events:
            sim.process_event(ev)
            assert sim.current_usage_bytes <= capacity

        assert sim.peak_cache_usage_bytes <= capacity

    def test_simulator_reset(self, sample_events: list[ScenarioEvent]) -> None:
        sim = CacheSimulator(capacity_bytes=3000, policy="LFU")
        for ev in sample_events:
            sim.process_event(ev)

        assert sim.total_requests == len(sample_events)
        sim.reset()
        assert sim.total_requests == 0
        assert sim.cache_hits == 0
        assert len(sim.cache) == 0


class TestBenchmarkRunner:
    """Tests for BenchmarkRunner execution and validations."""

    def test_run_policy_all_four_policies(
        self, steady_events: list[ScenarioEvent]
    ) -> None:
        config = BenchmarkConfig(cache_capacity_bytes=10000)
        runner = BenchmarkRunner(config)

        for policy in ("LRU", "LFU", "GDS", "ADAPTIVE"):
            res = runner.run_policy(policy, steady_events)
            assert isinstance(res, BenchmarkResult)
            assert res.policy_name == policy
            assert res.metrics.total_requests == len(steady_events)
            assert res.metrics.hit_ratio >= 0.0
            assert res.metrics.miss_ratio <= 1.0
            assert res.metrics.peak_cache_usage_bytes <= config.cache_capacity_bytes

    def test_run_full_suite(self, steady_events: list[ScenarioEvent]) -> None:
        config = BenchmarkConfig(cache_capacity_bytes=10000)
        runner = BenchmarkRunner(config)
        suite = runner.run(steady_events)

        assert isinstance(suite, BenchmarkSuiteResult)
        assert set(suite.results.keys()) == set(SUPPORTED_POLICIES)
        for p in SUPPORTED_POLICIES:
            assert suite.results[p].metrics.total_requests == len(steady_events)

    def test_empty_workload_handling(self) -> None:
        config = BenchmarkConfig(cache_capacity_bytes=10000)
        runner = BenchmarkRunner(config)
        suite = runner.run([])

        assert isinstance(suite, BenchmarkSuiteResult)
        for res in suite.results.values():
            assert res.metrics.total_requests == 0
            assert res.metrics.hit_ratio == 0.0
            assert res.metrics.average_latency_ms == 0.0

    def test_single_request_handling(self) -> None:
        start = datetime(2026, 9, 4, 12, 0, 0, tzinfo=timezone.utc)
        single = [
            ScenarioEvent(
                timestamp=start,
                key="item1",
                workload_type=WorkloadType.READ_HEAVY,
                backend_latency_ms=10.0,
                object_size_bytes=1000,
                retrieval_cost_ms=10.0,
                request_rate=1.0,
            )
        ]
        config = BenchmarkConfig(cache_capacity_bytes=5000)
        runner = BenchmarkRunner(config)
        suite = runner.run(single)

        for res in suite.results.values():
            assert res.metrics.total_requests == 1
            assert res.metrics.cache_misses == 1
            assert res.metrics.cache_hits == 0
            assert res.metrics.average_latency_ms == 11.0  # 1.0 + 10.0

    def test_rejects_unordered_timestamps(self) -> None:
        start = datetime(2026, 9, 4, 12, 0, 0, tzinfo=timezone.utc)
        events = [
            ScenarioEvent(
                timestamp=start + timedelta(seconds=10),
                key="item1",
                workload_type=WorkloadType.READ_HEAVY,
                backend_latency_ms=5.0,
                object_size_bytes=500,
                retrieval_cost_ms=5.0,
                request_rate=1.0,
            ),
            ScenarioEvent(
                timestamp=start,  # Earlier than index 0!
                key="item2",
                workload_type=WorkloadType.READ_HEAVY,
                backend_latency_ms=5.0,
                object_size_bytes=500,
                retrieval_cost_ms=5.0,
                request_rate=1.0,
            ),
        ]
        runner = BenchmarkRunner(BenchmarkConfig(cache_capacity_bytes=5000))
        with pytest.raises(ValueError, match="ordered by timestamp ascending"):
            runner.run(events)

    def test_run_scenario_helper(self) -> None:
        cfg = ScenarioConfig(
            name="test_steady",
            scenario_type="steady",
            seed=99,
            object_count=10,
            request_count=30,
        )
        runner = BenchmarkRunner(BenchmarkConfig(cache_capacity_bytes=5000))
        suite = runner.run_scenario(cfg)
        assert suite.scenario_name == "test_steady"
        assert suite.seed == 99


class TestBenchmarkFairnessAndIsolation:
    """Rigorous fairness and policy state isolation tests."""

    def test_policies_receive_identical_event_count_and_keys(
        self, steady_events: list[ScenarioEvent]
    ) -> None:
        """Verify every policy receives same event count and sees same keys."""
        config = BenchmarkConfig(cache_capacity_bytes=10000)
        runner = BenchmarkRunner(config)
        suite = runner.run(steady_events)

        expected_count = len(steady_events)
        for policy_name, res in suite.results.items():
            assert res.metrics.total_requests == expected_count, (
                f"{policy_name} processed {res.metrics.total_requests} events; "
                f"expected {expected_count}"
            )

    def test_shared_event_list_is_never_mutated(
        self, steady_events: list[ScenarioEvent]
    ) -> None:
        """Verify policy execution cannot mutate the shared event list."""
        original_len = len(steady_events)
        original_keys = [e.key for e in steady_events]
        original_timestamps = [e.timestamp for e in steady_events]

        config = BenchmarkConfig(cache_capacity_bytes=10000)
        runner = BenchmarkRunner(config)
        runner.run(steady_events)

        assert len(steady_events) == original_len
        assert [e.key for e in steady_events] == original_keys
        assert [e.timestamp for e in steady_events] == original_timestamps

    def test_changing_policy_order_does_not_change_results(
        self, steady_events: list[ScenarioEvent]
    ) -> None:
        """Verify changing policy order does not change another policy's result."""
        cfg_forward = BenchmarkConfig(
            cache_capacity_bytes=10000,
            policies=("LRU", "LFU", "GDS", "ADAPTIVE"),
        )
        cfg_reverse = BenchmarkConfig(
            cache_capacity_bytes=10000,
            policies=("ADAPTIVE", "GDS", "LFU", "LRU"),
        )

        suite_forward = BenchmarkRunner(cfg_forward).run(steady_events)
        suite_reverse = BenchmarkRunner(cfg_reverse).run(steady_events)

        for p in SUPPORTED_POLICIES:
            mf = suite_forward.results[p].metrics
            mr = suite_reverse.results[p].metrics
            assert mf.cache_hits == mr.cache_hits
            assert mf.cache_misses == mr.cache_misses
            assert mf.hit_ratio == mr.hit_ratio
            assert mf.eviction_count == mr.eviction_count
            assert mf.average_latency_ms == mr.average_latency_ms
            assert mf.p99_latency_ms == mr.p99_latency_ms
            assert mf.peak_cache_usage_bytes == mr.peak_cache_usage_bytes

    def test_repeated_runs_produce_identical_results(
        self, steady_events: list[ScenarioEvent]
    ) -> None:
        """Verify running the same benchmark twice produces equivalent results."""
        config = BenchmarkConfig(cache_capacity_bytes=10000)
        runner = BenchmarkRunner(config)

        run1 = runner.run(steady_events)
        run2 = runner.run(steady_events)

        for p in SUPPORTED_POLICIES:
            assert run1.results[p].metrics == run2.results[p].metrics


class TestScenariosAndProfiles:
    """Tests evaluating all Step 11 scenarios and profiles."""

    @pytest.mark.parametrize("scenario_type", ["steady", "spike", "popularity_shift"])
    def test_benchmark_all_scenarios(self, scenario_type: str) -> None:
        cfg = ScenarioConfig(
            name=f"test_{scenario_type}",
            scenario_type=scenario_type,
            seed=42,
            object_count=15,
            request_count=50,
            request_rate=50.0,
            profile=PRODUCT_CATALOG_PROFILE,
        )
        events = ScenarioGenerator(cfg).generate()
        runner = BenchmarkRunner(BenchmarkConfig(cache_capacity_bytes=8000))
        suite = runner.run(events)

        assert len(suite.results) == 4
        for res in suite.results.values():
            assert res.metrics.total_requests == 50

    def test_benchmark_recommendations_profile(self) -> None:
        cfg = ScenarioConfig(
            name="test_recs",
            scenario_type="steady",
            seed=42,
            object_count=10,
            request_count=40,
            request_rate=20.0,
            profile=RECOMMENDATIONS_PROFILE,
        )
        events = ScenarioGenerator(cfg).generate()
        # Recommendations profile default object size is 25600 bytes
        runner = BenchmarkRunner(BenchmarkConfig(cache_capacity_bytes=60000))
        suite = runner.run(events)

        for res in suite.results.values():
            assert res.metrics.total_requests == 40
            assert res.metrics.peak_cache_usage_bytes <= 60000


class TestSerializationAndFormatting:
    """Tests for summary table formatting and JSON serialization round-trips."""

    def test_format_summary_table(self, steady_events: list[ScenarioEvent]) -> None:
        runner = BenchmarkRunner(BenchmarkConfig(cache_capacity_bytes=10000))
        suite = runner.run(steady_events)
        table = format_summary_table(suite)

        assert "Benchmark Suite:" in table
        assert "LRU" in table
        assert "LFU" in table
        assert "GDS" in table
        assert "ADAPTIVE" in table
        assert "Hit Ratio" in table

    def test_serialization_round_trip(self, steady_events: list[ScenarioEvent]) -> None:
        runner = BenchmarkRunner(BenchmarkConfig(cache_capacity_bytes=10000))
        suite = runner.run(steady_events)

        serialized = serialize_suite_result(suite)
        assert isinstance(serialized, dict)
        assert "results" in serialized
        assert "LRU" in serialized["results"]

        deserialized = deserialize_suite_result(serialized)
        assert deserialized == suite
