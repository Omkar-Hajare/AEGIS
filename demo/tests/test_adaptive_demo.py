"""Test suite for the isolated CLI demonstration of Adaptive Cache Intelligence."""

from __future__ import annotations

import io
from typing import Any

import pytest

from backend.adaptive.engine import DecisionEngine
from backend.workload.generator import ScenarioGenerator
from backend.workload.scenario import (
    PRODUCT_CATALOG_PROFILE,
    RECOMMENDATIONS_PROFILE,
    ScenarioConfig,
)
from benchmark import BenchmarkRunner
from demo.adaptive_demo import (
    AdaptiveDemo,
    main,
    run_demo,
)


class TestAdaptiveDemo:
    """Test suite validating AdaptiveDemo execution, determinism, and fairness."""

    def test_demo_imports_successfully(self) -> None:
        """Verify that demo modules import cleanly without error."""
        import demo
        import demo.adaptive_demo

        assert hasattr(demo, "run_demo")
        assert hasattr(demo, "AdaptiveDemo")
        assert hasattr(demo.adaptive_demo, "main")

    def test_demo_entrypoint_executes_successfully(self) -> None:
        """Verify that the CLI entrypoint executes with zero exit code."""
        # Test CLI main with quiet flag
        exit_code = main(["--seed", "42", "--requests", "30", "--quiet"])
        assert exit_code == 0

    def test_demo_does_not_mutate_generated_scenario_events(self) -> None:
        """Verify that demo benchmark execution never mutates input event lists."""
        cfg = ScenarioConfig(
            name="steady_test",
            scenario_type="steady",
            seed=42,
            object_count=10,
            request_count=30,
            profile=PRODUCT_CATALOG_PROFILE,
        )
        events = ScenarioGenerator(cfg).generate()

        orig_len = len(events)
        orig_keys = [e.key for e in events]
        orig_timestamps = [e.timestamp for e in events]

        demo = AdaptiveDemo(seed=42, request_count=30, stream=io.StringIO())
        demo.section_5_policy_benchmark([(cfg, 10000)])

        assert len(events) == orig_len
        assert [e.key for e in events] == orig_keys
        assert [e.timestamp for e in events] == orig_timestamps

    def test_same_seed_produces_deterministic_results(self) -> None:
        """Verify that identical seeds produce bit-for-bit equivalent demo results."""
        out1 = io.StringIO()
        out2 = io.StringIO()

        res1 = run_demo(seed=99, request_count=30, stream=out1)
        res2 = run_demo(seed=99, request_count=30, stream=out2)

        # Verify walkthrough decision matches
        assert (
            res1["walkthrough_decision"].decision_id
            == res2["walkthrough_decision"].decision_id
        )
        assert (
            res1["walkthrough_decision"].capacity_action
            == res2["walkthrough_decision"].capacity_action
        )
        assert (
            res1["walkthrough_decision"].eviction_keys
            == res2["walkthrough_decision"].eviction_keys
        )

        # Verify benchmark suites match across all 6 scenarios
        suites1 = res1["benchmark_suites"]
        suites2 = res2["benchmark_suites"]
        assert len(suites1) == 6
        assert len(suites2) == 6

        for s1, s2 in zip(suites1, suites2, strict=True):
            for policy_name in ("LRU", "LFU", "GDS", "ADAPTIVE"):
                m1 = s1.results[policy_name].metrics
                m2 = s2.results[policy_name].metrics
                assert m1 == m2

    def test_all_six_scenario_profile_combinations_execute(self) -> None:
        """Verify all 6 scenarios across both workload profiles execute properly."""
        stream = io.StringIO()
        demo = AdaptiveDemo(seed=42, request_count=20, stream=stream)
        scenarios = demo.section_2_scenario_selection()

        assert len(scenarios) == 6

        # Check expected profile mappings
        profiles = [cfg.profile.name for cfg, _ in scenarios]
        types = [cfg.scenario_type for cfg, _ in scenarios]

        assert profiles.count("product_catalog") == 3
        assert profiles.count("recommendations") == 3
        assert types.count("steady") == 2
        assert types.count("spike") == 2
        assert types.count("popularity_shift") == 2

        suites = demo.section_5_policy_benchmark(scenarios)
        assert len(suites) == 6

    def test_real_decision_engine_is_invoked(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verify the real DecisionEngine.decide method is invoked by the demo."""
        decide_called = False
        original_decide = DecisionEngine.decide

        def spy_decide(self_de: DecisionEngine, *args: Any, **kwargs: Any) -> Any:
            nonlocal decide_called
            decide_called = True
            return original_decide(self_de, *args, **kwargs)

        monkeypatch.setattr(DecisionEngine, "decide", spy_decide)

        stream = io.StringIO()
        demo = AdaptiveDemo(seed=42, request_count=20, stream=stream)
        decision = demo.section_3_walkthrough()

        assert decide_called is True
        assert decision.decision_id.startswith("dec-")
        assert decision.version == "v1"

    def test_real_benchmark_runner_is_invoked(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verify the real Step 12 BenchmarkRunner.run method is invoked by the demo."""
        runner_called = False
        original_run = BenchmarkRunner.run

        def spy_run(self_br: BenchmarkRunner, *args: Any, **kwargs: Any) -> Any:
            nonlocal runner_called
            runner_called = True
            return original_run(self_br, *args, **kwargs)

        monkeypatch.setattr(BenchmarkRunner, "run", spy_run)

        stream = io.StringIO()
        demo = AdaptiveDemo(seed=42, request_count=20, stream=stream)
        cfg = ScenarioConfig(
            name="test_steady",
            scenario_type="steady",
            seed=42,
            object_count=10,
            request_count=20,
            profile=RECOMMENDATIONS_PROFILE,
        )
        demo.section_5_policy_benchmark([(cfg, 60000)])

        assert runner_called is True

    def test_all_four_policies_appear_in_benchmark_output(self) -> None:
        """Verify LRU, LFU, GDS, and ADAPTIVE all appear in the benchmark output."""
        stream = io.StringIO()
        demo = AdaptiveDemo(seed=42, request_count=20, stream=stream)
        cfg = ScenarioConfig(
            name="test_steady",
            scenario_type="steady",
            seed=42,
            object_count=10,
            request_count=20,
            profile=PRODUCT_CATALOG_PROFILE,
        )
        suites = demo.section_5_policy_benchmark([(cfg, 20480)])

        suite = suites[0]
        assert set(suite.results.keys()) == {"LRU", "LFU", "GDS", "ADAPTIVE"}

        text_output = stream.getvalue()
        assert "LRU" in text_output
        assert "LFU" in text_output
        assert "GDS" in text_output
        assert "ADAPTIVE" in text_output

    def test_no_infrastructure_services_required(self) -> None:
        """Verify demo executes completely offline without external network or servers."""
        stream = io.StringIO()
        result = run_demo(seed=123, request_count=20, stream=stream)

        assert "elapsed_seconds" in result
        assert result["elapsed_seconds"] < 5.0  # Runs in fraction of a second
        assert len(result["benchmark_suites"]) == 6
        assert len(result["reaction_results"]) == 3
