"""Deterministic benchmark runner orchestrating policy evaluation suites.

Replays identical ScenarioEvent sequences across LRU, LFU, GDS, and ADAPTIVE
policies starting from isolated initial states and produces benchmark results.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from backend.workload.generator import ScenarioGenerator
from backend.workload.scenario import ScenarioConfig, ScenarioEvent
from benchmark.cache_simulator import CacheSimulator
from benchmark.models import (
    BenchmarkConfig,
    BenchmarkResult,
    BenchmarkSuiteResult,
)
from benchmark.policies import BenchmarkPolicy, get_policy_adapter


class BenchmarkRunner:
    """Policy-agnostic deterministic benchmark runner."""

    def __init__(self, config: BenchmarkConfig) -> None:
        """Initialize BenchmarkRunner with configuration.

        Args:
            config: BenchmarkConfig specifying cache parameters and policies.

        Raises:
            TypeError: If config is not a BenchmarkConfig instance.
        """
        if not isinstance(config, BenchmarkConfig):
            raise TypeError(
                f"config must be a BenchmarkConfig, got {type(config).__name__}"
            )
        self.config = config

    def run_policy(
        self,
        policy: str | BenchmarkPolicy,
        events: Sequence[ScenarioEvent],
        scenario_name: str = "custom",
        workload_profile: str = "custom",
        seed: int = 0,
    ) -> BenchmarkResult:
        """Run an individual policy against the event sequence in an isolated simulator.

        Args:
            policy: Policy identifier or BenchmarkPolicy instance.
            events: Sequence of ScenarioEvent objects to replay.
            scenario_name: Name of the workload scenario.
            workload_profile: Name of the workload profile.
            seed: Scenario generation seed.

        Returns:
            Structured BenchmarkResult model.

        Raises:
            TypeError: If events is not a sequence of ScenarioEvents.
            ValueError: If event timestamps are out of order.
        """
        self._validate_events(events)

        # Compute an adaptive window that fits the actual event time span so that
        # the measurement window rolls at least once mid-scenario and
        # _previous_window_accesses accumulates popularity history.
        # With the default 60 s window, 100 events at 100 req/s span ~1 s,
        # so the window never rolls and previous_access_counts stays empty.
        adaptive_window_seconds: float = 1.0
        if len(events) >= 2:
            span = (events[-1].timestamp - events[0].timestamp).total_seconds()
            if span > 0.0:
                # Set window to half the span: guarantees at least one roll.
                adaptive_window_seconds = max(0.1, span / 2.0)

        policy_adapter = get_policy_adapter(
            policy,
            window_seconds=adaptive_window_seconds,
        )
        simulator = CacheSimulator(
            capacity_bytes=self.config.cache_capacity_bytes,
            policy=policy_adapter,
            hit_latency_ms=self.config.cache_hit_latency_ms,
            min_capacity_bytes=self.config.min_capacity_bytes,
            max_capacity_bytes=self.config.max_capacity_bytes,
        )

        for event in events:
            simulator.process_event(event)

        return simulator.get_result(
            scenario_name=scenario_name,
            workload_profile=workload_profile,
            seed=seed,
        )

    def run(
        self,
        events: Sequence[ScenarioEvent],
        scenario_name: str = "custom",
        workload_profile: str = "custom",
        seed: int = 0,
    ) -> BenchmarkSuiteResult:
        """Run all configured policies against the exact same event sequence.

        Args:
            events: Sequence of ScenarioEvent objects to replay.
            scenario_name: Optional explicit scenario name.
            workload_profile: Optional explicit workload profile name.
            seed: Optional scenario generation seed.

        Returns:
            BenchmarkSuiteResult aggregating results for all evaluated policies.

        Raises:
            TypeError: If events is not a sequence of ScenarioEvents.
            ValueError: If event timestamps are out of order.
        """
        self._validate_events(events)

        resolved_scenario = scenario_name
        resolved_profile = workload_profile

        if events and scenario_name == "custom" and events[0].metadata:
            if "scenario" in events[0].metadata:
                resolved_scenario = str(events[0].metadata["scenario"])
            elif "phase" in events[0].metadata:
                resolved_scenario = str(events[0].metadata["phase"])

        if events and workload_profile == "custom":
            resolved_profile = events[0].workload_type.value

        results: dict[str, BenchmarkResult] = {}
        for policy_name in self.config.policies:
            res = self.run_policy(
                policy=policy_name,
                events=events,
                scenario_name=resolved_scenario,
                workload_profile=resolved_profile,
                seed=seed,
            )
            results[res.policy_name] = res

        suite_metadata: dict[str, Any] = {
            "cache_hit_latency_ms": self.config.cache_hit_latency_ms,
            "min_capacity_bytes": self.config.min_capacity_bytes,
            "max_capacity_bytes": self.config.max_capacity_bytes,
            **self.config.metadata,
        }

        return BenchmarkSuiteResult(
            scenario_name=resolved_scenario,
            workload_profile=resolved_profile,
            seed=seed,
            cache_capacity_bytes=self.config.cache_capacity_bytes,
            results=results,
            metadata=suite_metadata,
        )

    def run_scenario(
        self,
        scenario_or_config: ScenarioConfig | ScenarioGenerator,
    ) -> BenchmarkSuiteResult:
        """Generate events from a scenario config or generator and run the benchmark.

        Args:
            scenario_or_config: ScenarioConfig or ScenarioGenerator instance.

        Returns:
            BenchmarkSuiteResult containing evaluated policy results.

        Raises:
            TypeError: If argument is neither ScenarioConfig nor ScenarioGenerator.
        """
        if isinstance(scenario_or_config, ScenarioConfig):
            generator = ScenarioGenerator(scenario_or_config)
            events = generator.generate()
            return self.run(
                events=events,
                scenario_name=scenario_or_config.name,
                workload_profile=scenario_or_config.profile.name,
                seed=scenario_or_config.seed,
            )

        if isinstance(scenario_or_config, ScenarioGenerator):
            events = scenario_or_config.generate()
            cfg = scenario_or_config.config
            return self.run(
                events=events,
                scenario_name=cfg.name,
                workload_profile=cfg.profile.name,
                seed=cfg.seed,
            )

        raise TypeError(
            f"Expected ScenarioConfig or ScenarioGenerator, got "
            f"{type(scenario_or_config).__name__}"
        )

    @staticmethod
    def _validate_events(events: Sequence[ScenarioEvent]) -> None:
        """Validate input events sequence and timestamp ordering.

        Args:
            events: Sequence of ScenarioEvents to validate.

        Raises:
            TypeError: If events is not a sequence or contains invalid elements.
            ValueError: If event timestamps are out of ascending order.
        """
        if isinstance(events, (str, bytes, dict)):
            raise TypeError(f"events must be a sequence, got {type(events).__name__}")
        if not isinstance(events, Sequence):
            raise TypeError(f"events must be a sequence, got {type(events).__name__}")

        prev_time = None
        for i, ev in enumerate(events):
            if not isinstance(ev, ScenarioEvent):
                raise TypeError(
                    f"All events must be ScenarioEvent instances, "
                    f"got {type(ev).__name__} at index {i}"
                )
            if prev_time is not None and ev.timestamp < prev_time:
                raise ValueError(
                    f"Events must be ordered by timestamp ascending: "
                    f"event at index {i} ({ev.timestamp.isoformat()}) is earlier "
                    f"than event at index {i - 1} ({prev_time.isoformat()})"
                )
            prev_time = ev.timestamp
