"""Deterministic benchmark engine for the Adaptive Cache System.

Replays synthetic workload scenarios against baseline policies (LRU, LFU, GDS)
and the Adaptive Decision Engine under identical conditions.
"""

from benchmark.cache_simulator import CacheSimulator
from benchmark.models import (
    SUPPORTED_POLICIES,
    BenchmarkConfig,
    BenchmarkMetrics,
    BenchmarkResult,
    BenchmarkSuiteResult,
)
from benchmark.policies import (
    POLICY_REGISTRY,
    AdaptivePolicyAdapter,
    BenchmarkPolicy,
    GDSPolicyAdapter,
    LFUPolicyAdapter,
    LRUPolicyAdapter,
    get_policy_adapter,
)
from benchmark.results import (
    calculate_percentile,
    compute_benchmark_metrics,
    deserialize_suite_result,
    format_summary_table,
    serialize_suite_result,
)
from benchmark.runner import BenchmarkRunner

__all__ = [
    "POLICY_REGISTRY",
    "SUPPORTED_POLICIES",
    "AdaptivePolicyAdapter",
    "BenchmarkConfig",
    "BenchmarkMetrics",
    "BenchmarkPolicy",
    "BenchmarkResult",
    "BenchmarkRunner",
    "BenchmarkSuiteResult",
    "CacheSimulator",
    "GDSPolicyAdapter",
    "LFUPolicyAdapter",
    "LRUPolicyAdapter",
    "calculate_percentile",
    "compute_benchmark_metrics",
    "deserialize_suite_result",
    "format_summary_table",
    "get_policy_adapter",
    "serialize_suite_result",
]
