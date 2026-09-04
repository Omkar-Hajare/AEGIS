"""Policy adapters bridging baseline and adaptive policies to the benchmark runner.

Wraps LRUPolicy, LFUPolicy, GDSPolicy, and DecisionEngine into a unified
BenchmarkPolicy interface for isolated replay within the CacheSimulator.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Any

from backend.adaptive.engine.decision_engine import DecisionEngine
from backend.adaptive.policies.gds import GDSPolicy
from backend.adaptive.policies.lfu import LFUPolicy
from backend.adaptive.policies.lru import LRUPolicy
from backend.workload.scenario import ScenarioEvent
from benchmark.rolling_telemetry import RollingTelemetry
from contracts.schemas.cache import CacheObject
from contracts.schemas.decision import Decision
from contracts.schemas.system import SystemState
from contracts.schemas.workload import WorkloadState


class BenchmarkPolicy(ABC):
    """Abstract base class for benchmark eviction policy adapters."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Policy identifier (e.g. 'LRU', 'LFU', 'GDS', 'ADAPTIVE')."""
        ...

    @abstractmethod
    def select_evictions(
        self,
        cache: Mapping[str, CacheObject],
        target_capacity_bytes: int,
        event: ScenarioEvent | None = None,
    ) -> list[str]:
        """Select cache object keys to evict to meet target capacity.

        Args:
            cache: Current mapping of cached keys to CacheObject instances.
            target_capacity_bytes: Maximum allowed bytes for remaining objects.
            event: The incoming request ScenarioEvent triggering eviction.

        Returns:
            List of object keys chosen for eviction.
        """
        ...

    def on_hit(
        self,
        key: str,
        event: ScenarioEvent,
        cache: Mapping[str, CacheObject],
    ) -> None:
        """Callback invoked when a request hits the cache."""

    def on_miss(
        self,
        key: str,
        event: ScenarioEvent,
        cache: Mapping[str, CacheObject],
    ) -> None:
        """Callback invoked when a request misses the cache."""

    def reset(self) -> None:
        """Reset internal telemetry and state between benchmark runs."""

    def get_metadata(self) -> dict[str, Any]:
        """Return policy-specific run metadata."""
        return {}

    def configure_capacity(
        self,
        capacity_bytes: int,
        min_capacity_bytes: int | None = None,
        max_capacity_bytes: int | None = None,
    ) -> None:
        """Configure capacity bounds for policies that support dynamic sizing."""


class LRUPolicyAdapter(BenchmarkPolicy):
    """Benchmark adapter for the Least Recently Used (LRU) policy."""

    def __init__(self, policy: LRUPolicy | None = None) -> None:
        """Initialize with an optional LRUPolicy instance."""
        self._policy = policy or LRUPolicy()

    @property
    def name(self) -> str:
        """Return policy name 'LRU'."""
        return "LRU"

    def select_evictions(
        self,
        cache: Mapping[str, CacheObject],
        target_capacity_bytes: int,
        event: ScenarioEvent | None = None,
    ) -> list[str]:
        """Select LRU eviction candidates until target capacity is reached."""
        if not cache:
            return []
        if target_capacity_bytes <= 0:
            return self._policy._rank_keys(cache)
        return self._policy.select_evictions(cache, target_capacity_bytes)


class LFUPolicyAdapter(BenchmarkPolicy):
    """Benchmark adapter for the Least Frequently Used (LFU) policy."""

    def __init__(self, policy: LFUPolicy | None = None) -> None:
        """Initialize with an optional LFUPolicy instance."""
        self._policy = policy or LFUPolicy()

    @property
    def name(self) -> str:
        """Return policy name 'LFU'."""
        return "LFU"

    def select_evictions(
        self,
        cache: Mapping[str, CacheObject],
        target_capacity_bytes: int,
        event: ScenarioEvent | None = None,
    ) -> list[str]:
        """Select LFU eviction candidates until target capacity is reached."""
        if not cache:
            return []
        if target_capacity_bytes <= 0:
            return self._policy._rank_keys(cache)
        return self._policy.select_evictions(cache, target_capacity_bytes)


class GDSPolicyAdapter(BenchmarkPolicy):
    """Benchmark adapter for the Greedy-Dual-Size (GDS) policy."""

    def __init__(self, policy: GDSPolicy | None = None) -> None:
        """Initialize with an optional GDSPolicy instance."""
        self._policy = policy or GDSPolicy()

    @property
    def name(self) -> str:
        """Return policy name 'GDS'."""
        return "GDS"

    def select_evictions(
        self,
        cache: Mapping[str, CacheObject],
        target_capacity_bytes: int,
        event: ScenarioEvent | None = None,
    ) -> list[str]:
        """Select GDS eviction candidates until target capacity is reached."""
        if not cache:
            return []
        if target_capacity_bytes <= 0:
            return self._policy._rank_keys(cache)
        return self._policy.select_evictions(cache, target_capacity_bytes)


class AdaptivePolicyAdapter(BenchmarkPolicy):
    """Benchmark adapter for the unified Adaptive Decision Engine.

    Feeds the simulated cache state, access history, and telemetry into
    DecisionEngine and applies retention-score eviction.

    WorkloadAnalyzer classification relies on two metric keys supplied via
    WorkloadState.metrics:
    - ``request_rate_baseline``: required by the SPIKE rule.
    - ``popularity_shift_score``: required by the POPULARITY_SHIFT rule.

    These are derived at eviction time from ScenarioEvent.metadata using
    ``_build_workload_metrics()``. Without this, every call classifies as
    STEADY because the WorkloadAnalyzer rules silently guard on key presence.
    """

    def __init__(
        self,
        decision_engine: DecisionEngine | None = None,
        window_seconds: float = 60.0,
        capacity_bytes: int | None = None,
        min_capacity_bytes: int | None = None,
        max_capacity_bytes: int | None = None,
    ) -> None:
        """Initialize AdaptivePolicyAdapter with optional DecisionEngine."""
        self._decision_engine = decision_engine or DecisionEngine()
        self.window_seconds = window_seconds
        self.cache_capacity_bytes = capacity_bytes
        self.min_capacity_bytes = min_capacity_bytes
        self.max_capacity_bytes = max_capacity_bytes

        self.rolling_telemetry = RollingTelemetry(window_seconds=window_seconds)

        self._current_window_accesses: dict[str, int] = {}
        self._previous_window_accesses: dict[str, int] = {}
        self._window_start_time: datetime | None = None

        self._requests: int = 0
        self._hits: int = 0
        self._misses: int = 0
        self._backend_calls: int = 0
        self._backend_latency_sum: float = 0.0
        self._evictions: int = 0
        self._refresh_count: int = 0
        self._last_decision: Decision | None = None

    @property
    def name(self) -> str:
        """Return policy name 'ADAPTIVE'."""
        return "ADAPTIVE"

    def configure_capacity(
        self,
        capacity_bytes: int,
        min_capacity_bytes: int | None = None,
        max_capacity_bytes: int | None = None,
    ) -> None:
        """Configure capacity bounds."""
        self.cache_capacity_bytes = capacity_bytes
        self.min_capacity_bytes = min_capacity_bytes
        self.max_capacity_bytes = max_capacity_bytes

    def _update_window(self, timestamp: datetime) -> None:
        """Roll measurement window when duration is exceeded."""
        if self._window_start_time is None:
            self._window_start_time = timestamp
            return
        elapsed = (timestamp - self._window_start_time).total_seconds()
        if elapsed >= self.window_seconds:
            self._previous_window_accesses = dict(self._current_window_accesses)
            self._current_window_accesses = {}
            self._window_start_time = timestamp

    def on_hit(
        self,
        key: str,
        event: ScenarioEvent,
        cache: Mapping[str, CacheObject],
    ) -> None:
        """Record hit telemetry and update access window."""
        self._update_window(event.timestamp)
        self.rolling_telemetry.record_hit(event.timestamp, key=key, latency_ms=0.0)
        self._requests += 1
        self._hits += 1
        self._current_window_accesses[key] = (
            self._current_window_accesses.get(key, 0) + 1
        )

    def on_miss(
        self,
        key: str,
        event: ScenarioEvent,
        cache: Mapping[str, CacheObject],
    ) -> None:
        """Record miss telemetry and update access window."""
        self._update_window(event.timestamp)
        self.rolling_telemetry.record_miss(
            event.timestamp, key=key, latency_ms=event.backend_latency_ms
        )
        self._requests += 1
        self._misses += 1
        self._backend_calls += 1
        self._backend_latency_sum += event.backend_latency_ms
        self._current_window_accesses[key] = (
            self._current_window_accesses.get(key, 0) + 1
        )

    @staticmethod
    def _build_workload_metrics(
        event: ScenarioEvent | None,
    ) -> dict[str, Any] | None:
        """Derive WorkloadState.metrics from ScenarioEvent metadata.

        Extracts the signal fields required by WorkloadAnalyzer classification:

        - ``request_rate_baseline`` — SPIKE rule prerequisite. Computed as
          ``event.request_rate / spike_multiplier`` when ``spike_multiplier > 1``.
          For baseline and recovery phases (multiplier == 1.0), the key is omitted
          so those phases do not trigger SPIKE classification.
        - ``popularity_shift_score`` — POPULARITY_SHIFT rule prerequisite. Set
          directly from ``shift_progress`` in event metadata. Values above 0.7
          (transition and final phases) trigger POPULARITY_SHIFT classification.

        Returns None when no relevant metadata is present (e.g. steady scenario).
        """
        if event is None or event.metadata is None:
            return None

        meta = event.metadata
        metrics: dict[str, Any] = {}

        # SPIKE signal: infer baseline rate from spike_multiplier on the event.
        # During the spike phase spike_multiplier > 1 so baseline < request_rate,
        # satisfying request_rate >= 1.5 * baseline for standard multipliers (3x).
        # During baseline/recovery phases spike_multiplier == 1.0 so no entry is
        # added and the SPIKE rule is not triggered.
        spike_mult = meta.get("spike_multiplier")
        if (
            isinstance(spike_mult, (int, float))
            and not isinstance(spike_mult, bool)
            and spike_mult > 1.0
            and event.request_rate > 0.0
        ):
            metrics["request_rate_baseline"] = event.request_rate / spike_mult

        # POPULARITY_SHIFT signal: shift_progress encodes the transition alpha.
        # Values >= 0.7 (late transition and final phases) exceed the threshold.
        shift_progress = meta.get("shift_progress")
        if isinstance(shift_progress, (int, float)) and not isinstance(
            shift_progress, bool
        ):
            metrics["popularity_shift_score"] = float(shift_progress)

        return metrics if metrics else None

    def select_evictions(
        self,
        cache: Mapping[str, CacheObject],
        target_capacity_bytes: int,
        event: ScenarioEvent | None = None,
    ) -> list[str]:
        """Evaluate DecisionEngine and select evictions using retention scores."""
        if not cache:
            return []

        eval_time = event.timestamp if event is not None else datetime.now(timezone.utc)
        snap = self.rolling_telemetry.get_recent_metrics(eval_time)

        # Primary telemetry uses rolling window metrics so current conditions drive decisions
        hit_rate = snap["recent_hit_rate"]
        miss_rate = snap["recent_miss_rate"]
        backend_lat = snap["recent_backend_latency_ms"]
        if event is not None and snap["recent_misses"] == 0:
            backend_lat = event.backend_latency_ms

        base_cap = self.cache_capacity_bytes or max(
            target_capacity_bytes,
            sum(o.size_bytes for o in cache.values()),
        )
        min_cap = self.min_capacity_bytes or base_cap
        max_cap = self.max_capacity_bytes or base_cap

        # Supply workload classifier metrics derived from scenario event metadata.
        # Augment with rolling telemetry observations for explainability and downstream use.
        workload_metrics = self._build_workload_metrics(event)
        if workload_metrics is None:
            workload_metrics = {}
        workload_metrics["recent_request_count"] = snap["recent_requests"]
        workload_metrics["recent_hit_rate"] = hit_rate
        workload_metrics["recent_miss_rate"] = miss_rate
        workload_metrics["recent_backend_latency_ms"] = backend_lat
        workload_metrics["lifetime_requests"] = self._requests
        workload_metrics["lifetime_hit_rate"] = (
            (self._hits / self._requests) if self._requests > 0 else 0.0
        )

        workload = WorkloadState(
            request_rate=event.request_rate if event is not None else 100.0,
            hit_rate=hit_rate,
            miss_rate=miss_rate,
            backend_latency_ms=backend_lat,
            workload_type=event.workload_type if event is not None else None,
            timestamp=eval_time,
            window_seconds=self.window_seconds,
            metrics=workload_metrics,
        )
        system = SystemState(
            cache_capacity_bytes=base_cap,
            cache_usage_bytes=sum(o.size_bytes for o in cache.values()),
            object_count=len(cache),
            backend_calls=self._backend_calls,
            cache_evictions=self._evictions,
            timestamp=eval_time,
            window_seconds=self.window_seconds,
        )

        decision = self._decision_engine.decide(
            objects=cache,
            workload=workload,
            system=system,
            min_capacity_bytes=min_cap,
            max_capacity_bytes=max_cap,
            now=eval_time,
            previous_access_counts=self._previous_window_accesses,
        )
        self._last_decision = decision

        if decision.metadata and "refresh_keys" in decision.metadata:
            self._refresh_count += len(decision.metadata["refresh_keys"])

        if target_capacity_bytes <= 0:
            scores = decision.object_scores
            return sorted(cache.keys(), key=lambda k: (scores.get(k, 0.0), k))

        evicted = self._decision_engine.eviction_policy.select_evictions(
            scores=decision.object_scores,
            objects=dict(cache),
            target_capacity_bytes=target_capacity_bytes,
            workload=workload,
            system=system,
        )
        self._evictions += len(evicted)
        return evicted

    def reset(self) -> None:
        """Reset internal telemetry and access history between runs."""
        self.rolling_telemetry.reset()
        self._current_window_accesses.clear()
        self._previous_window_accesses.clear()
        self._window_start_time = None
        self._requests = 0
        self._hits = 0
        self._misses = 0
        self._backend_calls = 0
        self._backend_latency_sum = 0.0
        self._evictions = 0
        self._refresh_count = 0
        self._last_decision = None

    def get_metadata(self) -> dict[str, Any]:
        """Return adaptive run metadata."""
        meta: dict[str, Any] = {
            "refresh_count": self._refresh_count,
        }
        if self._last_decision is not None:
            if self._last_decision.metadata:
                meta["last_workload_type"] = self._last_decision.metadata.get(
                    "workload_type"
                )
            meta["last_capacity_action"] = self._last_decision.capacity_action.value
            meta["last_decision_id"] = self._last_decision.decision_id
        return meta


POLICY_REGISTRY: dict[str, type[BenchmarkPolicy]] = {
    "LRU": LRUPolicyAdapter,
    "LFU": LFUPolicyAdapter,
    "GDS": GDSPolicyAdapter,
    "ADAPTIVE": AdaptivePolicyAdapter,
}


def get_policy_adapter(
    policy_or_name: str | BenchmarkPolicy,
    **kwargs: Any,
) -> BenchmarkPolicy:
    """Resolve a BenchmarkPolicy from an instance or string name.

    Args:
        policy_or_name: Either a BenchmarkPolicy instance or registered policy name.
        **kwargs: Optional constructor arguments for the policy class.
            Adaptive-only kwargs (``window_seconds``, ``capacity_bytes``,
            ``min_capacity_bytes``, ``max_capacity_bytes``) are forwarded only
            to :class:`AdaptivePolicyAdapter` and silently ignored for the
            baseline adapters (LRU, LFU, GDS) which do not accept them.

    Returns:
        BenchmarkPolicy instance.

    Raises:
        ValueError: If policy name is unrecognized.
        TypeError: If policy_or_name is neither str nor BenchmarkPolicy.
    """
    # Kwargs that are only accepted by AdaptivePolicyAdapter.
    _ADAPTIVE_ONLY_KWARGS = frozenset(
        {"window_seconds", "capacity_bytes", "min_capacity_bytes", "max_capacity_bytes"}
    )

    if isinstance(policy_or_name, BenchmarkPolicy):
        return policy_or_name
    if isinstance(policy_or_name, str):
        normalized = policy_or_name.upper().strip()
        policy_cls = POLICY_REGISTRY.get(normalized)
        if policy_cls is not None:
            if policy_cls is AdaptivePolicyAdapter:
                return policy_cls(**kwargs)
            # Strip adaptive-only kwargs before constructing baseline policies.
            filtered = {
                k: v for k, v in kwargs.items() if k not in _ADAPTIVE_ONLY_KWARGS
            }
            return policy_cls(**filtered)
        raise ValueError(
            f"Unknown policy {policy_or_name!r}. "
            f"Supported policies: {sorted(POLICY_REGISTRY.keys())}"
        )
    raise TypeError(
        f"Expected str or BenchmarkPolicy, got {type(policy_or_name).__name__}"
    )
