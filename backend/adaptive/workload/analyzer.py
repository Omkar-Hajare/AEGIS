"""Deterministic rule-based workload classification engine.

Analyzes observed WorkloadState telemetry and classifies it into
one of the frozen v1 WorkloadType patterns:
1. SPIKE
2. POPULARITY_SHIFT
3. COMPUTE_HEAVY
4. READ_HEAVY
5. STEADY
"""

from __future__ import annotations

from contracts.schemas import WorkloadState, WorkloadType

SPIKE_MULTIPLIER: float = 1.5
POPULARITY_SHIFT_THRESHOLD: float = 0.7
COMPUTE_LATENCY_THRESHOLD_MS: float = 200.0
READ_HEAVY_HIT_RATE: float = 0.80
READ_HEAVY_MISS_RATE: float = 0.20


class WorkloadAnalyzer:
    """Deterministic, explainable rule-based workload classifier.

    Evaluates observed system metrics against prioritized classification
    rules without external infrastructure, ML models, or internal state.
    """

    SPIKE_MULTIPLIER: float = SPIKE_MULTIPLIER
    POPULARITY_SHIFT_THRESHOLD: float = POPULARITY_SHIFT_THRESHOLD
    COMPUTE_LATENCY_THRESHOLD_MS: float = COMPUTE_LATENCY_THRESHOLD_MS
    READ_HEAVY_HIT_RATE: float = READ_HEAVY_HIT_RATE
    READ_HEAVY_MISS_RATE: float = READ_HEAVY_MISS_RATE

    def _is_spike(self, workload: WorkloadState) -> bool:
        """Determines if a request rate spike is detected relative to baseline.

        A spike is identified when:
        1. `metrics` contains a valid numeric `request_rate_baseline` > 0.
        2. `workload.request_rate >= SPIKE_MULTIPLIER * request_rate_baseline`.

        Booleans, non-numeric values, missing values, or non-positive baselines
        are strictly ignored.
        """
        metrics = workload.metrics or {}
        baseline = metrics.get("request_rate_baseline")

        if isinstance(baseline, bool) or not isinstance(baseline, (int, float)):
            return False

        if baseline <= 0:
            return False

        return workload.request_rate >= self.SPIKE_MULTIPLIER * baseline

    def _is_popularity_shift(self, workload: WorkloadState) -> bool:
        """Determines if a popularity shift pattern is present in the workload.

        A popularity shift is detected when:
        1. `metrics` contains a valid numeric `popularity_shift_score`.
        2. `popularity_shift_score >= POPULARITY_SHIFT_THRESHOLD`.

        Booleans, non-numeric values, or missing values are strictly ignored.
        """
        metrics = workload.metrics or {}
        score = metrics.get("popularity_shift_score")

        if isinstance(score, bool) or not isinstance(score, (int, float)):
            return False

        return score >= self.POPULARITY_SHIFT_THRESHOLD

    def analyze(self, workload: WorkloadState) -> WorkloadType:
        """Classifies a WorkloadState observation into a WorkloadType.

        Rules are evaluated in strict priority order:
        1. SPIKE: request_rate >= 1.5 * baseline (with baseline > 0)
        2. POPULARITY_SHIFT: popularity_shift_score >= 0.7
        3. COMPUTE_HEAVY: backend_latency_ms >= 200.0
        4. READ_HEAVY: hit_rate >= 0.80 and miss_rate <= 0.20
        5. STEADY: default baseline state when no condition above is met

        Args:
            workload: The observed WorkloadState snapshot.

        Returns:
            The determined WorkloadType enum value.
        """
        # Priority 1: Sudden traffic spike
        if self._is_spike(workload):
            return WorkloadType.SPIKE

        # Priority 2: Shift in object popularity distribution
        if self._is_popularity_shift(workload):
            return WorkloadType.POPULARITY_SHIFT

        # Priority 3: Long backend compute / retrieval latency
        if workload.backend_latency_ms >= self.COMPUTE_LATENCY_THRESHOLD_MS:
            return WorkloadType.COMPUTE_HEAVY

        # Priority 4: High cache hit throughput
        if (
            workload.hit_rate >= self.READ_HEAVY_HIT_RATE
            and workload.miss_rate <= self.READ_HEAVY_MISS_RATE
        ):
            return WorkloadType.READ_HEAVY

        # Priority 5: Normal steady-state operation
        return WorkloadType.STEADY

    def __call__(self, workload: WorkloadState) -> WorkloadType:
        """Callable interface forwarding to analyze()."""
        return self.analyze(workload)
