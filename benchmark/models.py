"""Data models and configuration schemas for the benchmark engine.

Defines benchmark configuration, raw metrics, and structured benchmark results
for deterministic policy comparisons.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class BenchmarkMetrics(BaseModel):
    """Raw telemetry and performance metrics recorded during benchmark execution."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    total_requests: int = Field(..., ge=0, description="Total request count processed")
    cache_hits: int = Field(..., ge=0, description="Total cache hits")
    cache_misses: int = Field(..., ge=0, description="Total cache misses")
    hit_ratio: float = Field(
        ..., ge=0.0, le=1.0, description="Ratio of requests served from cache"
    )
    miss_ratio: float = Field(
        ..., ge=0.0, le=1.0, description="Ratio of requests requiring backend fetch"
    )
    backend_requests: int = Field(
        ..., ge=0, description="Total requests forwarded to backend"
    )
    backend_requests_prevented: int = Field(
        ..., ge=0, description="Requests served from cache avoiding backend load"
    )
    backend_latency_total_ms: float = Field(
        ..., ge=0.0, description="Sum of backend retrieval latencies in ms"
    )
    average_latency_ms: float = Field(
        ..., ge=0.0, description="Mean simulated request latency in ms"
    )
    p50_latency_ms: float = Field(
        default=0.0, ge=0.0, description="50th percentile simulated request latency in ms"
    )
    p95_latency_ms: float = Field(
        default=0.0, ge=0.0, description="95th percentile simulated request latency in ms"
    )
    p99_latency_ms: float = Field(
        ..., ge=0.0, description="99th percentile simulated request latency in ms"
    )
    eviction_count: int = Field(
        ..., ge=0, description="Total number of objects evicted"
    )
    cache_capacity_bytes: int = Field(
        ..., gt=0, description="Configured cache capacity in bytes"
    )
    peak_cache_usage_bytes: int = Field(
        ..., ge=0, description="Maximum cache memory usage in bytes observed"
    )
    estimated_cost: float = Field(
        default=0.0, ge=0.0, description="Estimated total operational cost based on project CostModel (backward-compatible alias)"
    )
    modeled_origin_penalty_ms: float = Field(
        default=0.0, ge=0.0, description="Modeled origin retrieval latency penalty in ms"
    )
    throughput_rps: float = Field(
        default=0.0, ge=0.0, description="Simulated or configured throughput in requests per second (backward-compatible alias)"
    )
    configured_arrival_rate_rps: float = Field(
        default=0.0, ge=0.0, description="Configured synthetic workload arrival rate in requests per second"
    )
    simulated_latency_ms: float = Field(
        default=0.0, ge=0.0, description="Mean simulated request latency in ms"
    )
    measured_wall_clock_runtime_ms: float = Field(
        default=0.0, ge=0.0, description="Monotonically measured execution duration in ms"
    )
    measured_processing_throughput_rps: float = Field(
        default=0.0, ge=0.0, description="Completed requests divided by monotonic execution time in requests per second"
    )

    @model_validator(mode="before")
    @classmethod
    def _sync_metric_aliases(cls, data: Any) -> Any:
        if isinstance(data, dict):
            # Sync cost / origin penalty
            cost = data.get("estimated_cost")
            penalty = data.get("modeled_origin_penalty_ms")
            if cost is not None and penalty is None:
                data["modeled_origin_penalty_ms"] = cost
            elif penalty is not None and cost is None:
                data["estimated_cost"] = penalty

            # Sync throughput / arrival rate
            t_rps = data.get("throughput_rps")
            arr_rps = data.get("configured_arrival_rate_rps")
            if t_rps is not None and arr_rps is None:
                data["configured_arrival_rate_rps"] = t_rps
            elif arr_rps is not None and t_rps is None:
                data["throughput_rps"] = arr_rps

            # Sync simulated latency
            avg_lat = data.get("average_latency_ms")
            sim_lat = data.get("simulated_latency_ms")
            if avg_lat is not None and sim_lat is None:
                data["simulated_latency_ms"] = avg_lat
            elif sim_lat is not None and avg_lat is None:
                data["average_latency_ms"] = sim_lat
        return data

    @field_validator(
        "total_requests",
        "cache_hits",
        "cache_misses",
        "hit_ratio",
        "miss_ratio",
        "backend_requests",
        "backend_requests_prevented",
        "backend_latency_total_ms",
        "average_latency_ms",
        "p50_latency_ms",
        "p95_latency_ms",
        "p99_latency_ms",
        "eviction_count",
        "cache_capacity_bytes",
        "peak_cache_usage_bytes",
        "estimated_cost",
        "modeled_origin_penalty_ms",
        "throughput_rps",
        "configured_arrival_rate_rps",
        "simulated_latency_ms",
        "measured_wall_clock_runtime_ms",
        "measured_processing_throughput_rps",
        mode="before",
    )
    @classmethod
    def _reject_bool_for_numeric(cls, v: Any) -> Any:
        if isinstance(v, bool):
            raise TypeError("Boolean values are not allowed for numeric fields")
        return v



SUPPORTED_POLICIES: tuple[str, ...] = ("LRU", "LFU", "GDS", "ADAPTIVE")


class BenchmarkConfig(BaseModel):
    """Configuration parameters for a benchmark execution suite."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    cache_capacity_bytes: int = Field(
        ..., gt=0, description="Fixed cache capacity in bytes"
    )
    cache_hit_latency_ms: float = Field(
        default=1.0, ge=0.0, description="Simulated cache hit latency in ms"
    )
    policies: tuple[str, ...] = Field(
        default=SUPPORTED_POLICIES,
        description="Ordered sequence of policy identifiers to benchmark",
    )
    min_capacity_bytes: int | None = Field(
        default=None,
        description="Optional minimum logical capacity for adaptive scaling",
    )
    max_capacity_bytes: int | None = Field(
        default=None,
        description="Optional maximum logical capacity for adaptive scaling",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Optional caller-supplied metadata"
    )

    @field_validator(
        "cache_capacity_bytes",
        "cache_hit_latency_ms",
        "min_capacity_bytes",
        "max_capacity_bytes",
        mode="before",
    )
    @classmethod
    def _reject_bool_for_numeric(cls, v: Any) -> Any:
        if isinstance(v, bool):
            raise TypeError("Boolean values are not allowed for numeric fields")
        return v

    @field_validator("policies", mode="before")
    @classmethod
    def _validate_policies(cls, v: Any) -> tuple[str, ...]:
        if isinstance(v, (list, tuple)):
            if not v:
                raise ValueError("policies list must not be empty")
            normalized: list[str] = []
            seen: set[str] = set()
            for p in v:
                if not isinstance(p, str):
                    raise TypeError(
                        f"Policy name must be a string, got {type(p).__name__}"
                    )
                name = p.upper().strip()
                if not name:
                    raise ValueError("Policy name cannot be empty")
                if name in seen:
                    raise ValueError(f"Duplicate policy name {name!r} not allowed")
                seen.add(name)
                normalized.append(name)
            return tuple(normalized)
        raise TypeError(f"policies must be a sequence, got {type(v).__name__}")

    @field_validator("metadata", mode="before")
    @classmethod
    def _copy_metadata(cls, v: Any) -> dict[str, Any]:
        if v is None:
            return {}
        if not isinstance(v, (dict, Mapping)):
            raise TypeError(f"metadata must be a mapping, got {type(v).__name__}")
        return dict(v)

    @model_validator(mode="after")
    def _validate_bounds(self) -> BenchmarkConfig:
        if not math.isfinite(self.cache_hit_latency_ms):
            raise ValueError("cache_hit_latency_ms must be finite")

        if self.min_capacity_bytes is not None:
            if self.min_capacity_bytes <= 0:
                raise ValueError("min_capacity_bytes must be greater than 0")
            if self.min_capacity_bytes > self.cache_capacity_bytes:
                raise ValueError(
                    f"min_capacity_bytes ({self.min_capacity_bytes}) cannot exceed "
                    f"cache_capacity_bytes ({self.cache_capacity_bytes})"
                )

        if (
            self.max_capacity_bytes is not None
            and self.max_capacity_bytes < self.cache_capacity_bytes
        ):
            raise ValueError(
                f"max_capacity_bytes ({self.max_capacity_bytes}) must be >= "
                f"cache_capacity_bytes ({self.cache_capacity_bytes})"
            )

        return self


class BenchmarkResult(BaseModel):
    """Structured benchmark outcome for an individual policy run."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    policy_name: str = Field(..., min_length=1, description="Policy evaluated")
    scenario_name: str = Field(..., min_length=1, description="Workload scenario name")
    workload_profile: str = Field(..., min_length=1, description="Workload profile")
    seed: int = Field(..., description="Generation seed used for the workload")
    cache_capacity_bytes: int = Field(
        ..., gt=0, description="Configured cache capacity in bytes"
    )
    metrics: BenchmarkMetrics = Field(..., description="Observed performance metrics")
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Additional policy and run metadata"
    )


class BenchmarkSuiteResult(BaseModel):
    """Aggregated benchmark outcome comparing all evaluated policies."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    scenario_name: str = Field(..., min_length=1, description="Scenario pattern")
    workload_profile: str = Field(..., min_length=1, description="Workload profile")
    seed: int = Field(..., description="Generation seed")
    cache_capacity_bytes: int = Field(..., gt=0, description="Cache capacity in bytes")
    results: dict[str, BenchmarkResult] = Field(
        ..., description="Policy results indexed by policy name"
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Suite-level execution metadata"
    )
