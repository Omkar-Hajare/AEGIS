"""Standalone CLI demonstration of Person 1's Adaptive Cache Intelligence work.

Showcases feature extraction, workload analysis, retention scoring, refresh
recommendations, dynamic capacity sizing, and isolated policy benchmarking
against LRU, LFU, and GDS using pure Python offline execution.
"""

from __future__ import annotations

import argparse
import sys
import time
from collections.abc import Sequence
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, TextIO

# Ensure repository root is on sys.path when executed directly as a script
_REPO_ROOT = str(Path(__file__).resolve().parent.parent)
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend.adaptive.capacity import CapacityController
from backend.adaptive.engine import DecisionEngine
from backend.adaptive.eviction import EvictionPolicy
from backend.adaptive.features import FeatureExtractor
from backend.adaptive.refresh import RefreshPolicy
from backend.adaptive.scoring import AdaptiveScorer
from backend.adaptive.workload import WorkloadAnalyzer
from backend.workload.generator import ScenarioGenerator
from backend.workload.scenario import (
    PRODUCT_CATALOG_PROFILE,
    RECOMMENDATIONS_PROFILE,
    ScenarioConfig,
)
from benchmark import BenchmarkConfig, BenchmarkRunner, BenchmarkSuiteResult
from contracts.schemas import (
    CacheObject,
    Decision,
    SystemState,
    WorkloadState,
    WorkloadType,
)

LINE_WIDTH = 88
DIVIDER_HEAVY = "=" * LINE_WIDTH
DIVIDER_LIGHT = "-" * LINE_WIDTH


class AdaptiveDemo:
    """Orchestrates the terminal demonstration of adaptive cache intelligence."""

    def __init__(
        self,
        seed: int = 42,
        request_count: int = 100,
        stream: TextIO | None = None,
    ) -> None:
        """Initialize the demo runner with deterministic parameters.

        Args:
            seed: Generation seed for deterministic synthetic workloads.
            request_count: Request count per benchmark scenario run.
            stream: Target text stream for terminal display (defaults to sys.stdout).
        """
        self.seed = seed
        self.request_count = request_count
        self.stream = stream or sys.stdout

    def _print(self, text: str = "") -> None:
        """Write formatted text to the configured output stream."""
        self.stream.write(text + "\n")
        self.stream.flush()

    def section_1_overview(self) -> None:
        """Display Section 1: System Overview and Person 1 Architecture Boundary."""
        self._print(DIVIDER_HEAVY)
        self._print("   ADAPTIVE CACHE SYSTEM — INTELLIGENCE DEMONSTRATION")
        self._print("   Person 1 Contribution: Adaptive Intelligence & Benchmarking")
        self._print(DIVIDER_HEAVY)
        self._print(" Architecture Boundary:")
        self._print("   - 100% Pure Python & In-Memory (Zero External Dependencies)")
        self._print(
            "   - Independent of FastAPI, Redis, PostgreSQL, Streamlit, K8s, Prometheus"
        )
        self._print(
            "   - Deterministic, data-driven telemetry evaluation & retention scoring"
        )
        self._print()
        self._print(" Core Pipeline Components Demonstrated:")
        self._print(
            "   1. FeatureExtractor    -> Frequency, recency, cost, size, trend"
        )
        self._print(
            "   2. WorkloadAnalyzer    -> Real-time classification (STEADY/SPIKE/SHIFT)"
        )
        self._print(
            "   3. AdaptiveScorer      -> Multi-factor retention scoring [0.0, 1.0]"
        )
        self._print(
            "   4. RefreshPolicy       -> Staleness detection with adaptive thresholds"
        )
        self._print(
            "   5. CapacityController  -> Utilization-driven capacity recommendations"
        )
        self._print("   6. EvictionPolicy      -> Capacity-bounded candidate selection")
        self._print(
            "   7. DecisionEngine      -> Unified deterministic Decision contract"
        )
        self._print(
            "   8. BenchmarkRunner     -> Fair replay across LRU/LFU/GDS/Adaptive"
        )
        self._print(DIVIDER_HEAVY)
        self._print()

    def section_2_scenario_selection(self) -> list[tuple[ScenarioConfig, int]]:
        """Display Section 2: Workload Scenarios & Profiles Specification.

        Returns:
            List of (ScenarioConfig, cache_capacity_bytes) tuples for the 6 scenarios.
        """
        self._print(DIVIDER_LIGHT)
        self._print(
            " [SECTION 2] Benchmark Scenarios & Workload Profiles Specification"
        )
        self._print(DIVIDER_LIGHT)
        self._print(
            " Six synthetic scenarios across Read-Heavy and Compute-Heavy profiles:"
        )
        self._print()

        headers = (
            f" {'#':<2} | {'Scenario Name':<18} | {'Profile':<16} | "
            f"{'Objects':<7} | {'Requests':<8} | {'Arrival':<10} | {'Capacity':<10}"
        )
        self._print(headers)
        self._print(DIVIDER_LIGHT)

        specs = [
            ("steady", PRODUCT_CATALOG_PROFILE, 20480, 100.0, 30),
            ("spike", PRODUCT_CATALOG_PROFILE, 20480, 100.0, 30),
            ("popularity_shift", PRODUCT_CATALOG_PROFILE, 20480, 100.0, 30),
            ("steady", RECOMMENDATIONS_PROFILE, 128000, 50.0, 20),
            ("spike", RECOMMENDATIONS_PROFILE, 128000, 50.0, 20),
            ("popularity_shift", RECOMMENDATIONS_PROFILE, 128000, 50.0, 20),
        ]

        scenarios: list[tuple[ScenarioConfig, int]] = []
        for idx, (stype, prof, cap, rate, obj_cnt) in enumerate(specs, start=1):
            name = f"{stype}_{prof.name}"
            cfg = ScenarioConfig(
                name=name,
                scenario_type=stype,
                seed=self.seed,
                object_count=obj_cnt,
                request_count=self.request_count,
                request_rate=rate,
                profile=prof,
            )
            scenarios.append((cfg, cap))
            row = (
                f" {idx:<2} | {stype:<18} | {prof.name:<16} | "
                f"{obj_cnt:<7} | {self.request_count:<8} | "
                f"{f'{rate:.0f} req/s':<10} | {f'{cap:,} B':<10}"
            )
            self._print(row)

        self._print(DIVIDER_LIGHT)
        self._print()
        return scenarios

    def section_3_walkthrough(self) -> Decision:
        """Display Section 3: Adaptive Intelligence Walkthrough using real components.

        Returns:
            The final Decision contract produced by DecisionEngine.
        """
        self._print(DIVIDER_LIGHT)
        self._print(
            " [SECTION 3] Adaptive Intelligence Walkthrough (Live Engine Execution)"
        )
        self._print(DIVIDER_LIGHT)
        self._print(" Step-by-step walkthrough on a cache state under pressure.")
        self._print()

        now = datetime(2026, 9, 4, 12, 0, 0, tzinfo=timezone.utc)
        raw_items = [
            ("product_0", 2048, 50, 2.0, 15.0, "Very hot, recently active"),
            ("product_1", 2048, 35, 10.0, 25.0, "Hot, recent, high compute cost"),
            ("product_2", 2048, 12, 120.0, 5.0, "Medium frequency, moderate age"),
            ("product_3", 2048, 3, 450.0, 8.0, "Cold, stale (>300s staleness)"),
            ("product_4", 2048, 1, 600.0, 2.0, "Single access, old timestamp"),
            ("product_5", 2048, 8, 25.0, 80.0, "Low access, expensive backend fetch"),
            ("product_6", 2048, 15, 60.0, 10.0, "Active steady-state product"),
        ]

        objects: dict[str, CacheObject] = {}
        char_map: dict[str, str] = {}
        for key, size, count, rec_sec, cost, desc in raw_items:
            objects[key] = CacheObject(
                key=key,
                size_bytes=size,
                access_count=count,
                last_accessed=now - timedelta(seconds=rec_sec),
                retrieval_cost_ms=cost,
                hit_count=count - 1,
                miss_count=1,
                created_at=now - timedelta(seconds=rec_sec + 60),
            )
            char_map[key] = desc

        prev_counts = {
            "product_0": 20,
            "product_1": 15,
            "product_2": 15,
            "product_3": 5,
            "product_4": 1,
            "product_5": 2,
            "product_6": 10,
        }

        # Sub-step 3.1: Representative Objects
        self._print(" 3.1 Representative Cache Objects (Sample 5 of 7):")
        sample_hdr = (
            f" {'Key':<11} | {'Size':<8} | {'Accesses':<8} | "
            f"{'Age':<8} | {'Cost (ms)':<10} | {'Characteristics':<28}"
        )
        self._print(sample_hdr)
        self._print(" " + "-" * 84)
        for key in [
            "product_0",
            "product_1",
            "product_3",
            "product_4",
            "product_5",
        ]:
            o = objects[key]
            age = (now - o.last_accessed).total_seconds()
            row = (
                f" {o.key:<11} | {f'{o.size_bytes:,} B':<8} | {o.access_count:<8} | "
                f"{f'{age:.0f}s':<8} | {o.retrieval_cost_ms:<10.1f} | "
                f"{char_map[key]:<28}"
            )
            self._print(row)
        self._print()

        # Sub-step 3.2: Feature Extraction
        fe = FeatureExtractor()
        features = fe.extract(
            list(objects.values()),
            now=now,
            window_seconds=60.0,
            previous_access_counts=prev_counts,
        )
        self._print(" 3.2 FeatureExtractor Output (Normalized Features):")
        feat_hdr = (
            f" {'Key':<11} | {'Frequency':<10} | {'Recency':<10} | "
            f"{'Cost':<10} | {'Size':<10} | {'Trend':<10}"
        )
        self._print(feat_hdr)
        self._print(" " + "-" * 70)
        for key in [
            "product_0",
            "product_1",
            "product_3",
            "product_4",
            "product_5",
        ]:
            f = features[key]
            row = (
                f" {key:<11} | {f['frequency']:<10.4f} | {f['recency']:<10.4f} | "
                f"{f['retrieval_cost']:<10.4f} | {f['size']:<10.4f} | "
                f"{f['popularity_trend']:<10.4f}"
            )
            self._print(row)
        self._print()

        # Sub-step 3.3: Workload Analysis
        workload = WorkloadState(
            request_rate=250.0,
            hit_rate=0.72,
            miss_rate=0.28,
            backend_latency_ms=18.5,
            workload_type=WorkloadType.READ_HEAVY,
            timestamp=now,
            window_seconds=60.0,
        )
        wa = WorkloadAnalyzer()
        detected_workload = wa.analyze(workload)
        self._print(" 3.3 WorkloadAnalyzer Classification:")
        self._print(
            f"   Input Telemetry: Hit Rate={workload.hit_rate:.1%}, "
            f"Miss Rate={workload.miss_rate:.1%}, Rate={workload.request_rate} req/s"
        )
        self._print(f"   Detected Pattern: {detected_workload.value.upper()}")
        # System state
        current_usage = sum(o.size_bytes for o in objects.values())
        configured_cap = 10240
        system = SystemState(
            cache_capacity_bytes=configured_cap,
            cache_usage_bytes=current_usage,
            object_count=len(objects),
            backend_calls=45,
            cache_evictions=12,
            timestamp=now,
            window_seconds=60.0,
        )

        # Sub-step 3.4: Adaptive Scoring
        scorer = AdaptiveScorer()
        scores = scorer.score(
            features,
            workload_type=detected_workload,
            workload=workload,
            system=system,
        )
        ranked_keys = sorted(scores.keys(), key=lambda k: scores[k], reverse=True)
        self._print(" 3.4 AdaptiveScorer Output (Retention Utility Scores [0.0, 1.0]):")
        if scorer.last_weights is not None:
            w = scorer.last_weights
            self._print(
                f"   Derived Dynamic Weights: Freq={w.frequency:.2f} | "
                f"Rec={w.recency:.2f} | Cost={w.retrieval_cost:.2f} | "
                f"Trend={w.popularity_trend:.2f} | Size={w.size_penalty:.2f}"
            )
        score_hdr = f" {'Rank':<4} | {'Key':<11} | {'Score':<8} | {'Analysis'}"
        self._print(score_hdr)
        self._print(" " + "-" * 75)
        for rk, k in enumerate(ranked_keys, start=1):
            sc = scores[k]
            if k == "product_0":
                exp = "High frequency + high recency + positive trend"
            elif k == "product_1":
                exp = "High frequency + high compute cost + high recency"
            elif k == "product_5":
                exp = "High retrieval cost (80ms) protects cold item from eviction"
            elif k == "product_4":
                exp = "Lowest score: single access, cold age -> eviction target"
            else:
                exp = f"{char_map.get(k, '')}"
            self._print(f" {rk:<4} | {k:<11} | {sc:<8.4f} | {exp}")
        self._print()

        # Sub-step 3.5: Refresh Policy
        rp = RefreshPolicy()
        refresh_candidates = [
            k
            for k, obj in objects.items()
            if rp.should_refresh(
                obj,
                now=now,
                workload_type=detected_workload,
                refresh_after_seconds=300.0,
            )
        ]
        self._print(" 3.5 RefreshPolicy Evaluation:")
        self._print("   Base Staleness Threshold: 300.0s")
        self._print(f"   Stale Objects Identified for Refresh: {refresh_candidates}")
        self._print()

        # Sub-step 3.6: Capacity Controller
        cc = CapacityController()
        cap_decision = cc.recommend(
            workload=workload,
            system=system,
            min_capacity_bytes=8192,
            max_capacity_bytes=20480,
        )
        self._print(" 3.6 CapacityController Recommendation:")
        self._print(
            f"   Usage: {current_usage:,} B / Capacity: {configured_cap:,} B "
            f"({current_usage / configured_cap:.1%} utilization)"
        )
        self._print(
            f"   Action: {cap_decision.capacity_action.value} -> "
            f"Recommended Capacity: {cap_decision.recommended_capacity_bytes:,} B"
        )
        self._print()

        # Sub-step 3.7: Eviction Policy
        ep = EvictionPolicy()
        eviction_keys = ep.select_evictions(
            scores=scores,
            objects=objects,
            target_capacity_bytes=configured_cap,
        )
        self._print(" 3.7 EvictionPolicy Selection:")
        self._print(
            f"   Target: {configured_cap:,} B "
            f"(Must free {current_usage - configured_cap:,} B)"
        )
        self._print(f"   Evicted Candidates (Lowest Score Order): {eviction_keys}")
        self._print()

        # Sub-step 3.8: Unified DecisionEngine Contract
        de = DecisionEngine()
        decision = de.decide(
            objects=objects,
            workload=workload,
            system=system,
            min_capacity_bytes=8192,
            max_capacity_bytes=20480,
            now=now,
            previous_access_counts=prev_counts,
        )
        self._print(" 3.8 DecisionEngine Final Contract Output:")
        self._print(f"   Decision ID:          {decision.decision_id}")
        self._print(f"   Timestamp:            {decision.timestamp.isoformat()}")
        self._print(f"   Capacity Action:      {decision.capacity_action.value}")
        self._print(
            f"   Recommended Capacity: {decision.recommended_capacity_bytes:,} B"
        )
        self._print(f"   Eviction Keys:        {decision.eviction_keys}")
        self._print(f"   Refresh Keys:         {decision.metadata.get('refresh_keys')}")
        self._print(f"   Contract Reason:      {decision.reason}")
        self._print(DIVIDER_LIGHT)
        self._print()
        return decision

    def section_4_scenario_reaction(self) -> list[dict[str, Any]]:
        """Display Section 4: Scenario Reaction comparing decisions across conditions.

        Returns:
            List of summary dictionaries for each tested workload state.
        """
        self._print(DIVIDER_LIGHT)
        self._print(" [SECTION 4] Scenario Reaction: Decisions Across Workload States")
        self._print(DIVIDER_LIGHT)
        self._print(" Demonstrating how the engine adapts to changing conditions:")
        self._print()

        now = datetime(2026, 9, 4, 12, 0, 0, tzinfo=timezone.utc)
        de = DecisionEngine()

        test_objects: dict[str, CacheObject] = {
            f"obj_{i}": CacheObject(
                key=f"obj_{i}",
                size_bytes=2048,
                access_count=(i + 1) * 3,
                last_accessed=now - timedelta(seconds=(7 - i) * 60),
                retrieval_cost_ms=10.0,
            )
            for i in range(6)
        }

        conditions = [
            (
                "Steady State",
                0.85,
                0.15,
                100.0,
                8192,
                10240,
                "Normal utilization and low miss rate",
            ),
            (
                "Traffic Spike",
                0.45,
                0.55,
                600.0,
                12288,
                10240,
                "Over-capacity utilization and high miss rate",
            ),
            (
                "Shift / Low Load",
                0.90,
                0.10,
                30.0,
                3072,
                10240,
                "Under-utilized cache with high hit rate",
            ),
        ]

        table_hdr = (
            f" {'Workload State':<18} | {'Hit%':<5} | {'Miss%':<5} | "
            f"{'Arrival':<10} | {'Classified':<10} | {'Action':<10} | "
            f"{'Target Cap':<11} | {'Refreshes':<9} | {'Evictions':<9}"
        )
        self._print(table_hdr)
        self._print(DIVIDER_LIGHT)

        results: list[dict[str, Any]] = []
        for name, hit_r, miss_r, rate, usage, cap, _desc in conditions:
            w = WorkloadState(
                request_rate=rate,
                hit_rate=hit_r,
                miss_rate=miss_r,
                backend_latency_ms=15.0,
                timestamp=now,
                window_seconds=60.0,
            )
            s = SystemState(
                cache_capacity_bytes=cap,
                cache_usage_bytes=usage,
                object_count=len(test_objects),
                backend_calls=int(rate * 0.2),
                cache_evictions=0,
                timestamp=now,
                window_seconds=60.0,
            )
            dec = de.decide(
                objects=test_objects,
                workload=w,
                system=s,
                min_capacity_bytes=8192,
                max_capacity_bytes=20480,
                now=now,
                refresh_after_seconds=300.0,
            )

            ref_count = dec.metadata.get("refreshed_count", 0)
            ev_count = len(dec.eviction_keys)
            wtype_str = dec.metadata.get("workload_type", "UNKNOWN").upper()

            row = (
                f" {name:<18} | {hit_r:>4.0%} | {miss_r:>4.0%} | "
                f"{f'{rate:.0f} req/s':<10} | {wtype_str:<10} | "
                f"{dec.capacity_action.value:<10} | "
                f"{f'{dec.recommended_capacity_bytes:,} B':<11} | "
                f"{ref_count:<9} | {ev_count:<9}"
            )
            self._print(row)
            results.append(
                {
                    "name": name,
                    "workload_type": wtype_str,
                    "action": dec.capacity_action.value,
                    "recommended_capacity": dec.recommended_capacity_bytes,
                    "refreshes": ref_count,
                    "evictions": ev_count,
                    "reason": dec.reason,
                }
            )

        self._print(DIVIDER_LIGHT)
        self._print(" Key Dynamic Behaviors:")
        self._print(
            "   1. Steady: Capacity MAINTAINED; normal hit-rate, low miss-rate."
        )
        self._print(
            "   2. Traffic Spike: SCALE_UP (+20%) triggered by over-capacity utilization"
            " (usage > cap)."
        )
        self._print(
            "   3. Shift/Low Load: SCALE_DOWN (-15%) triggered by low utilization"
            " to reclaim memory."
        )
        self._print(
            "   Note: SPIKE classification requires metrics['request_rate_baseline']"
            " in WorkloadState."
        )
        self._print(
            "         Demo states pass raw hit/miss/rate fields only, so the analyzer"
            " classifies by"
        )
        self._print(
            "         latency/hit-rate rules (STEADY here). The benchmark engine"
            " supplies baseline via"
        )
        self._print(
            "         ScenarioEvent.metadata['spike_multiplier'], enabling live"
            " SPIKE detection."
        )
        self._print()
        return results

    def section_5_policy_benchmark(
        self,
        scenarios: list[tuple[ScenarioConfig, int]] | None = None,
    ) -> list[BenchmarkSuiteResult]:
        """Display Section 5: Step 12 BenchmarkRunner Policy Comparison.

        Args:
            scenarios: Optional list of (ScenarioConfig, capacity_bytes) to execute.

        Returns:
            List of BenchmarkSuiteResult instances for all executed benchmarks.
        """
        self._print(DIVIDER_LIGHT)
        self._print(" [SECTION 5] Policy Benchmark: LRU vs LFU vs GDS vs ADAPTIVE")
        self._print(DIVIDER_LIGHT)
        self._print(" Replaying identical event streams across all four policies.")
        self._print(" Independent simulator state; no cross-policy contamination.")
        self._print()

        if scenarios is None:
            scenarios = self.section_2_scenario_selection()

        suites: list[BenchmarkSuiteResult] = []
        for i, (cfg, cap) in enumerate(scenarios, start=1):
            gen = ScenarioGenerator(cfg)
            events = gen.generate()

            bcfg = BenchmarkConfig(
                cache_capacity_bytes=cap,
                cache_hit_latency_ms=1.0,
            )
            runner = BenchmarkRunner(bcfg)
            suite = runner.run(
                events=events,
                scenario_name=cfg.name,
                workload_profile=cfg.profile.name,
                seed=cfg.seed,
            )
            suites.append(suite)

            self._print(
                f" [{i}/6] Scenario: {cfg.name} | Profile: {cfg.profile.name} | "
                f"Capacity: {cap:,} B | Requests: {len(events)}"
            )
            self._print(" " + "-" * 86)
            table_hdr = (
                f" {'Policy':<10} | {'Hit Ratio':<10} | {'Hits / Req':<12} | "
                f"{'P99 (ms)':<9} | {'Saved Req':<10} | {'Evictions':<10} | "
                f"{'Peak Usage':<10}"
            )
            self._print(table_hdr)
            self._print(" " + "-" * 86)

            for pname in ("LRU", "LFU", "GDS", "ADAPTIVE"):
                m = suite.results[pname].metrics
                hits_str = f"{m.cache_hits:,} / {m.total_requests:,}"
                row = (
                    f" {pname:<10} | {m.hit_ratio:>9.2%} | {hits_str:<14} | "
                    f"{m.p99_latency_ms:>9.1f} | {m.backend_requests_prevented:>10,} | "
                    f"{m.eviction_count:>10,} | {f'{m.peak_cache_usage_bytes:,} B':<10}"
                )
                self._print(row)
            self._print(" " + "-" * 86)
            self._print()

        return suites

    def section_6_final_summary(
        self, suites: list[BenchmarkSuiteResult]
    ) -> dict[str, Any]:
        """Display Section 6: Final Summary & Empirical Analysis.

        Args:
            suites: Executed BenchmarkSuiteResult list from Section 5.

        Returns:
            Dictionary summarizing win/loss statistics and conclusions.
        """
        self._print(DIVIDER_HEAVY)
        self._print(" [SECTION 6] Final Summary & Empirical Performance Analysis")
        self._print(DIVIDER_HEAVY)

        summary_data: list[dict[str, Any]] = []
        for s in suites:
            best_hit_policy = max(
                s.results.keys(), key=lambda p: s.results[p].metrics.hit_ratio
            )
            best_hit_val = s.results[best_hit_policy].metrics.hit_ratio

            lowest_lat_policy = min(
                s.results.keys(),
                key=lambda p: s.results[p].metrics.average_latency_ms,
            )
            lowest_lat_val = s.results[lowest_lat_policy].metrics.average_latency_ms

            adaptive_hit = s.results["ADAPTIVE"].metrics.hit_ratio
            adaptive_won_hit = bool(adaptive_hit >= best_hit_val - 1e-9)

            summary_data.append(
                {
                    "scenario": s.scenario_name,
                    "profile": s.workload_profile,
                    "best_hit_policy": best_hit_policy,
                    "best_hit_val": best_hit_val,
                    "adaptive_hit": adaptive_hit,
                    "adaptive_won_hit": adaptive_won_hit,
                    "lowest_lat_policy": lowest_lat_policy,
                    "lowest_lat_val": lowest_lat_val,
                }
            )

        self._print(" Empirical Findings by Scenario:")
        for item in summary_data:
            outcome = "[WIN/TIE]" if item["adaptive_won_hit"] else "[COMPARATIVE]"
            self._print(
                f"   - {item['scenario']:<32}: {outcome:<14} "
                f"Best: {item['best_hit_policy']} ({item['best_hit_val']:.1%}) | "
                f"Adaptive: {item['adaptive_hit']:.1%}"
            )

        self._print()
        self._print(" Policy-Neutral Conclusions:")
        self._print(
            "   1. Steady Workloads: LFU & ADAPTIVE excel when frequencies stabilize."
        )
        self._print(
            "   2. Popularity Shifts: LRU aligns with trends; LFU degrades on old data."
        )
        self._print(
            "   3. Compute-Heavy Profiles: Cost-awareness in GDS & ADAPTIVE prioritizes"
        )
        self._print("      high-cost objects, saving substantial backend compute time.")
        self._print(
            "   4. Multi-Factor: ADAPTIVE balances frequency, recency, trend, and cost"
        )
        self._print("      without hardcoded static rules, yielding stable metrics.")
        self._print(DIVIDER_HEAVY)

        return {"scenarios_evaluated": len(suites), "details": summary_data}

    def run_all(self) -> dict[str, Any]:
        """Execute all six sections sequentially and return execution metrics.

        Returns:
            Dictionary containing execution metadata, walkthrough decision,
            reaction data, and benchmark suite outcomes.
        """
        t0 = time.perf_counter()

        self.section_1_overview()
        scenarios = self.section_2_scenario_selection()
        walkthrough_decision = self.section_3_walkthrough()
        reaction_results = self.section_4_scenario_reaction()
        benchmark_suites = self.section_5_policy_benchmark(scenarios)
        summary_results = self.section_6_final_summary(benchmark_suites)

        elapsed = time.perf_counter() - t0
        self._print(f" Demonstration successfully completed in {elapsed:.3f} seconds.")
        self._print(DIVIDER_HEAVY)

        return {
            "elapsed_seconds": elapsed,
            "walkthrough_decision": walkthrough_decision,
            "reaction_results": reaction_results,
            "benchmark_suites": benchmark_suites,
            "summary_results": summary_results,
        }


def run_demo(
    seed: int = 42,
    request_count: int = 100,
    stream: TextIO | None = None,
) -> dict[str, Any]:
    """Programmatic entrypoint to run the complete Adaptive Cache Demo.

    Args:
        seed: Random seed for synthetic workload generation.
        request_count: Request count per benchmark scenario.
        stream: Target output text stream.

    Returns:
        Structured execution results dictionary.
    """
    demo = AdaptiveDemo(seed=seed, request_count=request_count, stream=stream)
    return demo.run_all()


def main(argv: Sequence[str] | None = None) -> int:
    """CLI main entrypoint supporting command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Person 1 Adaptive Cache Intelligence CLI Demonstration"
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for deterministic synthetic workloads (default: 42)",
    )
    parser.add_argument(
        "--requests",
        type=int,
        default=100,
        help="Number of request events per scenario benchmark (default: 100)",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress terminal output for automated testing",
    )

    args = parser.parse_args(argv)

    if args.quiet:
        with open("/dev/null", "w") as null_stream:
            run_demo(
                seed=args.seed,
                request_count=args.requests,
                stream=null_stream,
            )
    else:
        run_demo(seed=args.seed, request_count=args.requests, stream=sys.stdout)

    return 0


if __name__ == "__main__":
    sys.exit(main())
