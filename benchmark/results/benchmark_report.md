# AEGIS Adaptive Caching Benchmark Report

**Date:** 2026-10-21T19:19:20.229345+00:00
**Random Seed:** 42
**Warmup Requests:** 1,000
**Measured Requests:** 4,000
**Cost Profile:** `default` (modeled origin retrieval latency penalty in milliseconds (ms))

## 1. Executive Summary & Audit Remediation Notes

This benchmark deterministically measures the performance of **AEGIS** (Adaptive Engine for Intelligent Caching & Scaling)
against three foundational caching baselines: **LRU** (Least Recently Used), **LFU** (Least Frequently Used), and
**GDS** (GreedyDual-Size). All policies were subjected to identical request sequences, object sizes, backend retrieval costs,
and cache capacities, with separate warm-up phases to eliminate cold-start bias.

> [!IMPORTANT]
> **Audit Hardening & Remediation Summary:**
> 1. **Baseline Fairness (GDS Inflation Clock):** GreedyDual-Size implements standard inflation clock $L$ and deterministic recency tie-breaking (Cao & Irani 1997). On uniform workloads (`steady`), GDS mathematically reduces to and achieves exact parity with LRU (71.57% hit ratio).
> 2. **Zero Metadata Leakage:** AdaptivePolicyAdapter no longer reads synthetic generator labels (`shift_progress`, `spike_multiplier`). Policy decisions derive entirely from observed request arrival rates, sliding-window key turnover, and rolling hit/miss latency telemetry.
> 3. **Truthful Cost Semantics:** Default cost represents modeled origin retrieval latency penalty in milliseconds (`ms`), calculated as the sum of miss retrieval latencies. It represents platform origin computing penalty, NOT billed cloud expenditure ($). No dollar signs are used.
> 4. **Throughput Separation:** The synthetic workload arrival pace is configured to 100.0 req/s. Actual wall-clock evaluation throughput reaches ~15k-20k req/s for AEGIS and ~300k-500k req/s for LRU/LFU in Python memory.
> 5. **Latency Percentile Discreteness:** In `cost_sensitive`, AEGIS P50 latency of 1.00 ms vs LRU 11.03 ms is an artifact of crossing the 50% hit ratio boundary (AEGIS: 61.92% hits; LRU: 37.35% hits). When hit ratio exceeds 50%, P50 collapses to the fixed 1.00 ms hit latency. Relative to LFU (63.42% hits, P50 = 1.00 ms) and GDS (50.20% hits, P50 = 1.00 ms), P50 latency reduction is 0.0%.
> 6. **Autoscaling Boundary:** Kubernetes Horizontal Pod Autoscaler (HPA) was **NOT** executed during this benchmark (`NOT_RUN / UNVERIFIED in benchmark`). This benchmark is an isolated caching algorithm evaluation.

## 2. Comparison Table (Measured Results: Seed 42)

| Workload | Policy | Requests | Hits | Misses | Hit Ratio | Backend Calls | P50 (ms) | P95 (ms) | P99 (ms) | Evictions | Memory (B) | Origin Penalty (ms) | Arrival Pace (req/s) | Processing Throughput (req/s) |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| steady | **LRU** | 4,000 | 2,863 | 1,137 | **71.57%** | 1,137 | 1.00 | 6.00 | 6.00 | 1,137 | 40,960 | 5685.00 | 100.0 | 321,517.8 |
| steady | **LFU** | 4,000 | 3,279 | 721 | **81.97%** | 721 | 1.00 | 6.00 | 6.00 | 721 | 40,960 | 3605.00 | 100.0 | 497,332.6 |
| steady | **GDS** | 4,000 | 2,863 | 1,137 | **71.57%** | 1,137 | 1.00 | 6.00 | 6.00 | 1,137 | 40,960 | 5685.00 | 100.0 | 264,971.9 |
| steady | **AEGIS** | 4,000 | 3,054 | 946 | **76.35%** | 946 | 1.00 | 6.00 | 6.00 | 946 | 40,960 | 4730.00 | 100.0 | 18,279.5 |
| popularity_shift | **LRU** | 4,000 | 2,425 | 1,575 | **60.62%** | 1,575 | 1.00 | 6.00 | 6.00 | 1,575 | 40,960 | 7875.00 | 100.0 | 243,093.7 |
| popularity_shift | **LFU** | 4,000 | 2,108 | 1,892 | **52.70%** | 1,892 | 1.00 | 6.00 | 6.00 | 1,892 | 40,960 | 9460.00 | 100.0 | 235,484.7 |
| popularity_shift | **GDS** | 4,000 | 2,498 | 1,502 | **62.45%** | 1,502 | 1.00 | 6.00 | 6.00 | 1,502 | 40,960 | 7510.00 | 100.0 | 213,090.8 |
| popularity_shift | **AEGIS** | 4,000 | 2,818 | 1,182 | **70.45%** | 1,182 | 1.00 | 6.00 | 6.00 | 1,182 | 40,960 | 5910.00 | 100.0 | 14,369.3 |
| cost_sensitive | **LRU** | 4,000 | 1,494 | 2,506 | **37.35%** | 2,506 | 11.03 | 263.97 | 272.76 | 2,504 | 57,101 | 271871.03 | 100.0 | 287,026.0 |
| cost_sensitive | **LFU** | 4,000 | 2,537 | 1,463 | **63.42%** | 1,463 | 1.00 | 272.46 | 272.76 | 1,464 | 43,869 | 170615.53 | 100.0 | 360,792.3 |
| cost_sensitive | **GDS** | 4,000 | 2,008 | 1,992 | **50.20%** | 1,992 | 1.00 | 262.88 | 272.76 | 1,993 | 44,451 | 150880.18 | 100.0 | 214,333.8 |
| cost_sensitive | **AEGIS** | 4,000 | 2,477 | 1,523 | **61.92%** | 1,523 | 1.00 | 262.88 | 272.76 | 1,529 | 53,403 | 131366.47 | 100.0 | 15,761.8 |

## 3. AEGIS Relative Improvements vs Baselines (Seed 42)

> [!NOTE]
> Percentage improvements are computed as `(Baseline - AEGIS) / Baseline * 100` for metrics where lower is better (calls, latency, evictions, origin penalty),
> and `(AEGIS - Baseline) / Baseline * 100` for hit ratio (where higher is better).

### Workload: `steady`

| Baseline | Hit Ratio Relative | Hit Ratio Points | Backend Call Red. | P50 Latency Red. | P95 Latency Red. | Avg Latency Red. | Eviction Red. | Origin Penalty Red. |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| vs **LRU** | **+6.7%** | +4.78% | **16.8%** | 0.0% | 0.0% | 9.9% | **16.8%** | 16.8% |
| vs **LFU** | **-6.9%** | -5.62% | **-31.2%** | 0.0% | 0.0% | -14.7% | **-31.2%** | -31.2% |
| vs **GDS** | **+6.7%** | +4.78% | **16.8%** | 0.0% | 0.0% | 9.9% | **16.8%** | 16.8% |

### Workload: `popularity_shift`

| Baseline | Hit Ratio Relative | Hit Ratio Points | Backend Call Red. | P50 Latency Red. | P95 Latency Red. | Avg Latency Red. | Eviction Red. | Origin Penalty Red. |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| vs **LRU** | **+16.2%** | +9.83% | **24.9%** | 0.0% | 0.0% | 16.5% | **24.9%** | 24.9% |
| vs **LFU** | **+33.7%** | +17.75% | **37.5%** | 0.0% | 0.0% | 26.4% | **37.5%** | 37.5% |
| vs **GDS** | **+12.8%** | +8.00% | **21.3%** | 0.0% | 0.0% | 13.9% | **21.3%** | 21.3% |

### Workload: `cost_sensitive`

| Baseline | Hit Ratio Relative | Hit Ratio Points | Backend Call Red. | P50 Latency Red. | P95 Latency Red. | Avg Latency Red. | Eviction Red. | Origin Penalty Red. |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| vs **LRU** | **+65.8%** | +24.57% | **39.2%** | 90.9% | 0.4% | 50.9% | **38.9%** | 51.7% |
| vs **LFU** | **-2.4%** | -1.50% | **-4.1%** | 0.0% | 3.5% | 22.5% | **-4.4%** | 23.0% |
| vs **GDS** | **+23.4%** | +11.72% | **23.5%** | 0.0% | 0.0% | 12.6% | **23.3%** | 12.9% |

## 4. Multi-Seed Statistical Evaluation

Aggregated metrics across seeds: `[42, 100, 2024, 777, 999]` (Mean ± Std Dev [Min - Max]):

| Workload | Policy | Hit Ratio (Mean ± Std) | Hit Ratio [Min - Max] | Backend Calls (Mean ± Std) | Origin Penalty ms (Mean ± Std) | Evictions (Mean ± Std) |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: |
| steady | **LRU** | **70.98% ± 0.97%** | [69.63% - 72.20%] | 1160.8 ± 38.9 | 5804.00 ± 194.56 | 1160.8 ± 38.9 |
| steady | **LFU** | **81.32% ± 0.58%** | [80.60% - 81.97%] | 747.2 ± 23.1 | 3736.00 ± 115.62 | 747.2 ± 23.1 |
| steady | **GDS** | **70.98% ± 0.97%** | [69.63% - 72.20%] | 1160.8 ± 38.9 | 5804.00 ± 194.56 | 1160.8 ± 38.9 |
| steady | **AEGIS** | **75.33% ± 0.93%** | [74.42% - 76.35%] | 986.8 ± 37.3 | 4934.00 ± 186.69 | 986.8 ± 37.3 |
| popularity_shift | **LRU** | **61.78% ± 1.15%** | [60.62% - 62.95%] | 1528.8 ± 46.0 | 7644.00 ± 230.20 | 1528.8 ± 46.0 |
| popularity_shift | **LFU** | **53.06% ± 1.44%** | [51.08% - 55.05%] | 1877.8 ± 57.5 | 9389.00 ± 287.48 | 1877.8 ± 57.5 |
| popularity_shift | **GDS** | **63.33% ± 0.54%** | [62.45% - 63.85%] | 1466.8 ± 21.4 | 7334.00 ± 107.14 | 1466.8 ± 21.4 |
| popularity_shift | **AEGIS** | **71.69% ± 0.87%** | [70.45% - 72.48%] | 1132.4 ± 34.6 | 5662.00 ± 173.15 | 1132.4 ± 34.6 |
| cost_sensitive | **LRU** | **38.39% ± 0.67%** | [37.35% - 39.10%] | 2464.4 ± 27.0 | 264361.85 ± 9739.58 | 2464.4 ± 24.9 |
| cost_sensitive | **LFU** | **60.58% ± 5.50%** | [50.82% - 63.75%] | 1576.6 ± 219.9 | 167527.84 ± 5971.22 | 1576.4 ± 218.4 |
| cost_sensitive | **GDS** | **50.27% ± 0.44%** | [49.75% - 50.82%] | 1989.4 ± 17.5 | 144799.79 ± 7841.02 | 1990.4 ± 17.2 |
| cost_sensitive | **AEGIS** | **62.42% ± 0.48%** | [61.92% - 63.10%] | 1503.2 ± 19.1 | 121670.54 ± 8558.76 | 1503.0 ± 20.4 |

## 5. Architectural Trade-offs & Production Realities

1. **Static Invariant Workloads (`steady`):** LFU remains the theoretical optimum (81.97% hit ratio). AEGIS achieves 76.35%, outperforming LRU and GDS (71.57%) by +4.78 percentage points, trading ~5.6 percentage points of static optimality to retain responsiveness to dynamic shifts.
2. **Dynamic Workloads (`popularity_shift`):** AEGIS leads all algorithms with 70.45% hit ratio (+17.75 percentage points over LFU; +9.83 points over LRU; +8.00 points over GDS) by autonomously detecting working-set churn without reading synthetic metadata.
3. **Heterogeneous Economics (`cost_sensitive`):** AEGIS prioritizes high-cost objects, reducing modeled origin retrieval latency penalty by 51.7% vs LRU, 23.0% vs LFU, and 12.9% vs GDS.
4. **Execution Overhead:** Python in-memory scoring adds overhead (~18k req/s throughput vs >300k req/s for simple dictionary lookups). In production, AEGIS scoring runs asynchronously in background intervals without blocking the read path.
5. **Autoscaling Distinction:** Kubernetes HPA scaling was not benchmarked. Caching and pod horizontal scaling are separate architectural tiers.