"""Metric computation and result serialization utilities for the benchmark engine.

Provides percentile calculation, formatted summary tables, and serialization
helpers for raw benchmark results.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from typing import Any

from benchmark.models import (
    BenchmarkMetrics,
    BenchmarkSuiteResult,
)


def calculate_percentile(data: Sequence[float], percentile: float) -> float:
    """Calculate the p-th percentile of a sequence using linear interpolation.

    Matches numpy's percentile calculation (method='linear').

    Args:
        data: Non-empty sequence of finite numeric values.
        percentile: Target percentile between 0.0 and 100.0 inclusive.

    Returns:
        Interpolated percentile value as a float.

    Raises:
        ValueError: If data is empty, contains non-finite values, or if
            percentile is outside [0.0, 100.0].
        TypeError: If data is not a sequence, contains non-numeric values,
            or if percentile is boolean / non-numeric.
    """
    if isinstance(percentile, bool) or not isinstance(percentile, (int, float)):
        raise TypeError(f"percentile must be numeric, got {type(percentile).__name__}")
    if not math.isfinite(percentile):
        raise ValueError(f"percentile must be finite, got {percentile}")
    if percentile < 0.0 or percentile > 100.0:
        raise ValueError(f"percentile must be between 0.0 and 100.0, got {percentile}")

    if isinstance(data, (str, bytes, dict)):
        raise TypeError(f"data must be a numeric sequence, got {type(data).__name__}")
    if not isinstance(data, Sequence):
        raise TypeError(f"data must be a numeric sequence, got {type(data).__name__}")
    if len(data) == 0:
        raise ValueError("data sequence must not be empty")

    sorted_vals: list[float] = []
    for i, v in enumerate(data):
        if isinstance(v, bool) or not isinstance(v, (int, float)):
            raise TypeError(
                f"Element at index {i} must be numeric, got {type(v).__name__}"
            )
        if not math.isfinite(v):
            raise ValueError(f"Element at index {i} must be finite, got {v}")
        sorted_vals.append(float(v))

    sorted_vals.sort()
    n = len(sorted_vals)
    if n == 1:
        return sorted_vals[0]

    rank = (percentile / 100.0) * (n - 1)
    idx = math.floor(rank)
    frac = rank - idx

    if idx + 1 < n:
        return sorted_vals[idx] + frac * (sorted_vals[idx + 1] - sorted_vals[idx])
    return sorted_vals[idx]


def compute_benchmark_metrics(
    total_requests: int,
    cache_hits: int,
    cache_misses: int,
    latencies: Sequence[float],
    backend_latency_total_ms: float,
    eviction_count: int,
    cache_capacity_bytes: int,
    peak_cache_usage_bytes: int,
) -> BenchmarkMetrics:
    """Compute and construct a validated BenchmarkMetrics model.

    Args:
        total_requests: Total requests processed.
        cache_hits: Total cache hits.
        cache_misses: Total cache misses.
        latencies: Sequence of simulated per-request latencies in ms.
        backend_latency_total_ms: Sum of backend retrieval latencies in ms.
        eviction_count: Total evictions performed.
        cache_capacity_bytes: Configured cache capacity in bytes.
        peak_cache_usage_bytes: Maximum cache bytes used.

    Returns:
        Frozen BenchmarkMetrics instance.
    """
    if total_requests > 0:
        hit_ratio = cache_hits / total_requests
        miss_ratio = cache_misses / total_requests
        avg_latency = sum(latencies) / len(latencies) if latencies else 0.0
        p99_latency = calculate_percentile(latencies, 99.0) if latencies else 0.0
    else:
        hit_ratio = 0.0
        miss_ratio = 0.0
        avg_latency = 0.0
        p99_latency = 0.0

    return BenchmarkMetrics(
        total_requests=total_requests,
        cache_hits=cache_hits,
        cache_misses=cache_misses,
        hit_ratio=hit_ratio,
        miss_ratio=miss_ratio,
        backend_requests=cache_misses,
        backend_requests_prevented=cache_hits,
        backend_latency_total_ms=backend_latency_total_ms,
        average_latency_ms=avg_latency,
        p99_latency_ms=p99_latency,
        eviction_count=eviction_count,
        cache_capacity_bytes=cache_capacity_bytes,
        peak_cache_usage_bytes=peak_cache_usage_bytes,
    )


def format_summary_table(suite_result: BenchmarkSuiteResult) -> str:
    """Format a human-readable summary table comparing policies in a suite result.

    Args:
        suite_result: BenchmarkSuiteResult containing evaluated policies.

    Returns:
        Formatted ASCII text table.
    """
    header = (
        f"Benchmark Suite: {suite_result.scenario_name} | "
        f"Profile: {suite_result.workload_profile} | "
        f"Capacity: {suite_result.cache_capacity_bytes:,} B | "
        f"Seed: {suite_result.seed}\n"
    )
    divider = "-" * 88
    cols = (
        f"{'Policy':<10} | {'Hit Ratio':<10} | {'Hits / Total':<16} | "
        f"{'Avg Lat (ms)':<12} | {'P99 Lat (ms)':<12} | {'Evictions':<10}"
    )

    rows = [header, divider, cols, divider]
    for policy_name, result in suite_result.results.items():
        m = result.metrics
        hit_str = f"{m.cache_hits:,} / {m.total_requests:,}"
        row = (
            f"{policy_name:<10} | {m.hit_ratio:>9.2%} | {hit_str:<16} | "
            f"{m.average_latency_ms:>12.2f} | {m.p99_latency_ms:>12.2f} | "
            f"{m.eviction_count:>10,}"
        )
        rows.append(row)
    rows.append(divider)
    return "\n".join(rows)


def serialize_suite_result(suite_result: BenchmarkSuiteResult) -> dict[str, Any]:
    """Serialize a BenchmarkSuiteResult to a standard dictionary.

    Args:
        suite_result: BenchmarkSuiteResult instance.

    Returns:
        JSON-compatible dictionary representation.
    """
    if not isinstance(suite_result, BenchmarkSuiteResult):
        raise TypeError(
            "suite_result must be a BenchmarkSuiteResult, "
            f"got {type(suite_result).__name__}"
        )
    return suite_result.model_dump(mode="json")


def deserialize_suite_result(data: dict[str, Any]) -> BenchmarkSuiteResult:
    """Deserialize a dictionary into a BenchmarkSuiteResult model.

    Args:
        data: Dictionary matching BenchmarkSuiteResult schema.

    Returns:
        Validated BenchmarkSuiteResult instance.
    """
    if not isinstance(data, dict):
        raise TypeError(f"data must be a dict, got {type(data).__name__}")
    return BenchmarkSuiteResult.model_validate(data)
