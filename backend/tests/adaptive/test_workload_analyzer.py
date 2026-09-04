"""Unit tests for the rule-based WorkloadAnalyzer.

Verifies deterministic classification into SPIKE, POPULARITY_SHIFT,
COMPUTE_HEAVY, READ_HEAVY, and STEADY according to strict priority rules
and robust handling of metrics edge cases.
"""

from datetime import datetime, timezone

import pytest

from backend.adaptive.workload import WorkloadAnalyzer
from contracts.schemas import WorkloadState, WorkloadType


@pytest.fixture
def analyzer() -> WorkloadAnalyzer:
    """Provides a fresh WorkloadAnalyzer instance."""
    return WorkloadAnalyzer()


@pytest.fixture
def now() -> datetime:
    """Provides a consistent timezone-aware reference timestamp."""
    return datetime(2026, 9, 4, 12, 0, 0, tzinfo=timezone.utc)


def test_steady_workload_returns_steady(
    analyzer: WorkloadAnalyzer, now: datetime
) -> None:
    """Normal balanced workload without elevated signals returns STEADY."""
    workload = WorkloadState(
        request_rate=100.0,
        hit_rate=0.60,
        miss_rate=0.40,
        backend_latency_ms=50.0,
        timestamp=now,
        window_seconds=60.0,
        metrics=None,
    )
    assert analyzer.analyze(workload) == WorkloadType.STEADY


def test_high_hit_rate_and_low_miss_rate_returns_read_heavy(
    analyzer: WorkloadAnalyzer, now: datetime
) -> None:
    """Hit rate >= 0.80 and miss rate <= 0.20 returns READ_HEAVY."""
    workload = WorkloadState(
        request_rate=120.0,
        hit_rate=0.85,
        miss_rate=0.15,
        backend_latency_ms=45.0,
        timestamp=now,
        window_seconds=60.0,
    )
    assert analyzer.analyze(workload) == WorkloadType.READ_HEAVY


def test_backend_latency_above_threshold_returns_compute_heavy(
    analyzer: WorkloadAnalyzer, now: datetime
) -> None:
    """Backend latency >= 200.0 ms returns COMPUTE_HEAVY."""
    workload = WorkloadState(
        request_rate=80.0,
        hit_rate=0.50,
        miss_rate=0.50,
        backend_latency_ms=250.0,
        timestamp=now,
        window_seconds=60.0,
    )
    assert analyzer.analyze(workload) == WorkloadType.COMPUTE_HEAVY


def test_request_rate_spike_returns_spike(
    analyzer: WorkloadAnalyzer, now: datetime
) -> None:
    """Request rate >= 1.5 * baseline returns SPIKE."""
    workload = WorkloadState(
        request_rate=300.0,
        hit_rate=0.50,
        miss_rate=0.50,
        backend_latency_ms=50.0,
        timestamp=now,
        window_seconds=60.0,
        metrics={"request_rate_baseline": 150.0},
    )
    assert analyzer.analyze(workload) == WorkloadType.SPIKE


def test_popularity_shift_score_returns_popularity_shift(
    analyzer: WorkloadAnalyzer, now: datetime
) -> None:
    """Popularity shift score >= 0.70 returns POPULARITY_SHIFT."""
    workload = WorkloadState(
        request_rate=100.0,
        hit_rate=0.50,
        miss_rate=0.50,
        backend_latency_ms=50.0,
        timestamp=now,
        window_seconds=60.0,
        metrics={"popularity_shift_score": 0.82},
    )
    assert analyzer.analyze(workload) == WorkloadType.POPULARITY_SHIFT


def test_spike_takes_priority_over_other_classifications(
    analyzer: WorkloadAnalyzer, now: datetime
) -> None:
    """SPIKE (priority 1) overrides POPULARITY_SHIFT, COMPUTE_HEAVY, and READ_HEAVY."""
    workload = WorkloadState(
        request_rate=300.0,
        hit_rate=0.90,  # qualifies for READ_HEAVY
        miss_rate=0.10,
        backend_latency_ms=350.0,  # qualifies for COMPUTE_HEAVY
        timestamp=now,
        window_seconds=60.0,
        metrics={
            "request_rate_baseline": 100.0,  # 300 >= 1.5 * 100 -> SPIKE
            "popularity_shift_score": 0.95,  # qualifies for POPULARITY_SHIFT
        },
    )
    assert analyzer.analyze(workload) == WorkloadType.SPIKE


def test_popularity_shift_takes_priority_over_compute_heavy(
    analyzer: WorkloadAnalyzer, now: datetime
) -> None:
    """POPULARITY_SHIFT (priority 2) overrides COMPUTE_HEAVY (priority 3)."""
    workload = WorkloadState(
        request_rate=100.0,
        hit_rate=0.50,
        miss_rate=0.50,
        backend_latency_ms=300.0,  # qualifies for COMPUTE_HEAVY
        timestamp=now,
        window_seconds=60.0,
        metrics={"popularity_shift_score": 0.75},
    )
    assert analyzer.analyze(workload) == WorkloadType.POPULARITY_SHIFT


def test_compute_heavy_takes_priority_over_read_heavy(
    analyzer: WorkloadAnalyzer, now: datetime
) -> None:
    """COMPUTE_HEAVY (priority 3) overrides READ_HEAVY (priority 4)."""
    workload = WorkloadState(
        request_rate=100.0,
        hit_rate=0.85,  # qualifies for READ_HEAVY
        miss_rate=0.15,
        backend_latency_ms=220.0,  # qualifies for COMPUTE_HEAVY
        timestamp=now,
        window_seconds=60.0,
    )
    assert analyzer.analyze(workload) == WorkloadType.COMPUTE_HEAVY


def test_missing_metrics_does_not_fail(
    analyzer: WorkloadAnalyzer, now: datetime
) -> None:
    """WorkloadState with metrics=None evaluates safely."""
    workload = WorkloadState(
        request_rate=100.0,
        hit_rate=0.50,
        miss_rate=0.50,
        backend_latency_ms=50.0,
        timestamp=now,
        window_seconds=60.0,
        metrics=None,
    )
    assert analyzer.analyze(workload) == WorkloadType.STEADY


def test_invalid_string_request_rate_baseline_is_ignored(
    analyzer: WorkloadAnalyzer, now: datetime
) -> None:
    """Non-numeric string request_rate_baseline is ignored without error."""
    workload = WorkloadState(
        request_rate=500.0,
        hit_rate=0.50,
        miss_rate=0.50,
        backend_latency_ms=50.0,
        timestamp=now,
        window_seconds=60.0,
        metrics={"request_rate_baseline": "not_a_number"},
    )
    assert analyzer.analyze(workload) == WorkloadType.STEADY


def test_zero_or_negative_request_rate_baseline_is_ignored(
    analyzer: WorkloadAnalyzer, now: datetime
) -> None:
    """request_rate_baseline <= 0 is non-positive and ignored."""
    for invalid_base in [0, 0.0, -10, -50.5]:
        workload = WorkloadState(
            request_rate=200.0,
            hit_rate=0.50,
            miss_rate=0.50,
            backend_latency_ms=50.0,
            timestamp=now,
            window_seconds=60.0,
            metrics={"request_rate_baseline": invalid_base},
        )
        assert analyzer.analyze(workload) == WorkloadType.STEADY


def test_boolean_numeric_metric_values_are_ignored(
    analyzer: WorkloadAnalyzer, now: datetime
) -> None:
    """Booleans passed for metric thresholds are strictly ignored."""
    # request_rate_baseline = True
    workload_bool_base = WorkloadState(
        request_rate=10.0,
        hit_rate=0.50,
        miss_rate=0.50,
        backend_latency_ms=50.0,
        timestamp=now,
        window_seconds=60.0,
        metrics={"request_rate_baseline": True},
    )
    assert analyzer.analyze(workload_bool_base) == WorkloadType.STEADY

    # popularity_shift_score = True
    workload_bool_shift = WorkloadState(
        request_rate=10.0,
        hit_rate=0.50,
        miss_rate=0.50,
        backend_latency_ms=50.0,
        timestamp=now,
        window_seconds=60.0,
        metrics={"popularity_shift_score": True},
    )
    assert analyzer.analyze(workload_bool_shift) == WorkloadType.STEADY

    # popularity_shift_score = False
    workload_bool_shift_false = WorkloadState(
        request_rate=10.0,
        hit_rate=0.50,
        miss_rate=0.50,
        backend_latency_ms=50.0,
        timestamp=now,
        window_seconds=60.0,
        metrics={"popularity_shift_score": False},
    )
    assert analyzer.analyze(workload_bool_shift_false) == WorkloadType.STEADY


def test_boundary_spike_multiplier(analyzer: WorkloadAnalyzer, now: datetime) -> None:
    """Boundary check for exactly 1.5 * baseline vs. slightly below."""
    baseline = 100.0

    # Exactly 1.5 * baseline -> SPIKE
    workload_exact = WorkloadState(
        request_rate=150.0,
        hit_rate=0.50,
        miss_rate=0.50,
        backend_latency_ms=50.0,
        timestamp=now,
        window_seconds=60.0,
        metrics={"request_rate_baseline": baseline},
    )
    assert analyzer.analyze(workload_exact) == WorkloadType.SPIKE

    # Just below 1.5 * baseline -> STEADY
    workload_below = WorkloadState(
        request_rate=149.99,
        hit_rate=0.50,
        miss_rate=0.50,
        backend_latency_ms=50.0,
        timestamp=now,
        window_seconds=60.0,
        metrics={"request_rate_baseline": baseline},
    )
    assert analyzer.analyze(workload_below) == WorkloadType.STEADY


def test_boundary_popularity_shift_score(
    analyzer: WorkloadAnalyzer, now: datetime
) -> None:
    """Boundary check for exactly 0.70 score vs. slightly below."""
    # Exactly 0.70 -> POPULARITY_SHIFT
    workload_exact = WorkloadState(
        request_rate=50.0,
        hit_rate=0.50,
        miss_rate=0.50,
        backend_latency_ms=50.0,
        timestamp=now,
        window_seconds=60.0,
        metrics={"popularity_shift_score": 0.70},
    )
    assert analyzer.analyze(workload_exact) == WorkloadType.POPULARITY_SHIFT

    # Slightly below 0.70 -> STEADY
    workload_below = WorkloadState(
        request_rate=50.0,
        hit_rate=0.50,
        miss_rate=0.50,
        backend_latency_ms=50.0,
        timestamp=now,
        window_seconds=60.0,
        metrics={"popularity_shift_score": 0.6999},
    )
    assert analyzer.analyze(workload_below) == WorkloadType.STEADY


def test_boundary_compute_heavy_latency(
    analyzer: WorkloadAnalyzer, now: datetime
) -> None:
    """Boundary check for exactly 200.0 ms backend latency vs. slightly below."""
    # Exactly 200.0 ms -> COMPUTE_HEAVY
    workload_exact = WorkloadState(
        request_rate=50.0,
        hit_rate=0.50,
        miss_rate=0.50,
        backend_latency_ms=200.0,
        timestamp=now,
        window_seconds=60.0,
    )
    assert analyzer.analyze(workload_exact) == WorkloadType.COMPUTE_HEAVY

    # Just below 200.0 ms -> STEADY
    workload_below = WorkloadState(
        request_rate=50.0,
        hit_rate=0.50,
        miss_rate=0.50,
        backend_latency_ms=199.9,
        timestamp=now,
        window_seconds=60.0,
    )
    assert analyzer.analyze(workload_below) == WorkloadType.STEADY


def test_boundary_read_heavy_rates(analyzer: WorkloadAnalyzer, now: datetime) -> None:
    """Boundary check for hit_rate == 0.80 and miss_rate == 0.20."""
    # Exactly 0.80 hit and 0.20 miss -> READ_HEAVY
    workload_exact = WorkloadState(
        request_rate=50.0,
        hit_rate=0.80,
        miss_rate=0.20,
        backend_latency_ms=50.0,
        timestamp=now,
        window_seconds=60.0,
    )
    assert analyzer.analyze(workload_exact) == WorkloadType.READ_HEAVY

    # Hit rate slightly below 0.80 -> STEADY
    workload_low_hit = WorkloadState(
        request_rate=50.0,
        hit_rate=0.799,
        miss_rate=0.20,
        backend_latency_ms=50.0,
        timestamp=now,
        window_seconds=60.0,
    )
    assert analyzer.analyze(workload_low_hit) == WorkloadType.STEADY

    # Miss rate slightly above 0.20 -> STEADY
    workload_high_miss = WorkloadState(
        request_rate=50.0,
        hit_rate=0.80,
        miss_rate=0.201,
        backend_latency_ms=50.0,
        timestamp=now,
        window_seconds=60.0,
    )
    assert analyzer.analyze(workload_high_miss) == WorkloadType.STEADY


def test_workload_state_is_not_mutated(
    analyzer: WorkloadAnalyzer, now: datetime
) -> None:
    """Input WorkloadState instance is never modified by analyze()."""
    workload = WorkloadState(
        request_rate=200.0,
        hit_rate=0.85,
        miss_rate=0.15,
        backend_latency_ms=250.0,
        workload_type=None,
        timestamp=now,
        window_seconds=60.0,
        metrics={"request_rate_baseline": 100.0},
    )
    result = analyzer.analyze(workload)
    assert result == WorkloadType.SPIKE
    assert workload.workload_type is None
    assert workload.metrics == {"request_rate_baseline": 100.0}
    assert workload.request_rate == 200.0


def test_analyzer_is_callable(analyzer: WorkloadAnalyzer, now: datetime) -> None:
    """WorkloadAnalyzer can be invoked directly as a callable."""
    workload = WorkloadState(
        request_rate=100.0,
        hit_rate=0.50,
        miss_rate=0.50,
        backend_latency_ms=50.0,
        timestamp=now,
        window_seconds=60.0,
    )
    assert analyzer(workload) == WorkloadType.STEADY
