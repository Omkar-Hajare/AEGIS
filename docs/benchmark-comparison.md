# AEGIS Empirical Benchmark: Adaptive Caching vs. LRU, LFU, and GDS

This document presents the independent audit and empirical evaluation of the **AEGIS Adaptive Decision Engine** against three foundational cache eviction algorithms: **LRU** (Least Recently Used), **LFU** (Least Frequently Used), and **GDS** (GreedyDual-Size, Cao & Irani 1997).

The benchmark measures performance impacts across cache hit ratios, backend origin pressure, percentile latencies (P50/P95/P99), cache evictions, memory saturation, and modeled origin retrieval latency penalties under controlled, deterministic conditions.

---

## 1. Experimental Methodology & Control Standards

To ensure scientific rigor, comparability, and reproducibility, the benchmark enforces the following controls:

- **Deterministic Execution**: All stochastic operations (Zipfian key selection, popularity drift, object assignment) use fixed random seeds. The primary reference run uses `seed=42`, and a multi-seed evaluation suite verifies variance across seeds `[42, 100, 2024, 777, 999]`.
- **Warm-Up Phase Separation**: Every algorithm executes 1,000 warm-up requests to populate initial cache lines. All internal telemetry and hit/miss counters are explicitly reset (`reset_metrics()`) before beginning the 4,000-request measurement window. Cold-start initialization noise is completely excluded from measured metrics.
- **Identical Evaluation Environment**: For every workload scenario, LRU, LFU, GDS, and AEGIS process the exact same sequence of requests, payload sizes, backend retrieval penalties, and memory capacity limits.
- **Fair Baseline Implementation (GDS)**: GreedyDual-Size implements the standard inflation clock $L$ and deterministic recency tie-breaking (Cao & Irani 1997). On uniform payload workloads, GDS mathematically reduces to and achieves exact parity with LRU.
- **Zero Generator Metadata Leakage**: AEGIS decisions derive strictly from runtime-observable signals (observed request arrival rates, sliding-window key turnover, and rolling hit/miss latency). The policy does not inspect synthetic scenario generator fields (`shift_progress`, `spike_multiplier`).
- **Autoscaling Boundary**: Kubernetes Horizontal Pod Autoscaler (HPA) was **NOT** executed during this benchmark (`NOT_RUN / UNVERIFIED in benchmark`). This benchmark is an isolated caching algorithm evaluation.

### Evaluated Workload Scenarios

1. **`steady` (Static Zipfian Access)**:
   - **Characteristics**: Classical 80/20 power-law distribution ($\alpha = 0.8$) over 100 objects with uniform 1 KB sizes and fixed 5.0 ms backend retrieval penalty.
   - **Evaluation Goal**: Measure baseline retention efficiency under invariant access distributions.
2. **`popularity_shift` (Dynamic Working Set)**:
   - **Characteristics**: Initial warm-up requests focus on one hot key-set. At the start of the measurement phase, active popularity migrates to a non-overlapping key subset.
   - **Evaluation Goal**: Measure algorithm responsiveness to temporal trend shifts and resistance to stale-frequency cache pollution.
3. **`cost_sensitive` (Heterogeneous Payloads & Latencies)**:
   - **Characteristics**: Objects partitioned into 4 distinct architectural archetypes with asymmetric sizes (1 KB to 16 KB) and backend regeneration costs (10 ms to 250 ms):
     - *Lightweight Metadata*: 1 KB, 10 ms fetch cost (high frequency)
     - *Medium Content*: 4 KB, 30 ms fetch cost (moderate frequency)
     - *Heavy Computation*: 8 KB, 120 ms fetch cost (moderate frequency, expensive origin compute)
     - *Massive Query Result*: 16 KB, 250 ms fetch cost (lower frequency, severe origin penalty)
   - **Evaluation Goal**: Measure multi-objective utility balancing (origin retrieval penalty reduction vs. byte memory consumption).

---

## 2. Complete Benchmark Results Table (Seed 42)

*Results collected across 4,000 measured requests per test run (1,000 warm-up requests excluded). Cache capacity: 40 KB for uniform workloads, 60 KB for cost-sensitive workload.*

| Workload | Policy | Requests | Hits | Misses | Hit Ratio | Backend Calls | P50 (ms) | P95 (ms) | P99 (ms) | Evictions | Memory (B) | Origin Penalty (ms) | Arrival Pace (req/s) | Processing Throughput (req/s) |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **`steady`** | LRU | 4,000 | 2,863 | 1,137 | **71.57%** | 1,137 | 1.00 | 6.00 | 6.00 | 1,137 | 40,960 | 5,685.00 | 100.0 | 331,678.3 |
| **`steady`** | LFU | 4,000 | 3,279 | 721 | **81.97%** | 721 | 1.00 | 6.00 | 6.00 | 721 | 40,960 | 3,605.00 | 100.0 | 521,019.7 |
| **`steady`** | GDS | 4,000 | 2,863 | 1,137 | **71.57%** | 1,137 | 1.00 | 6.00 | 6.00 | 1,137 | 40,960 | 5,685.00 | 100.0 | 281,960.0 |
| **`steady`** | **AEGIS** | **4,000** | **3,054** | **946** | **76.35%** | **946** | **1.00** | **6.00** | **6.00** | **946** | **40,960** | **4,730.00** | **100.0** | **19,617.3** |
| **`popularity_shift`** | LRU | 4,000 | 2,425 | 1,575 | **60.62%** | 1,575 | 1.00 | 6.00 | 6.00 | 1,575 | 40,960 | 7,875.00 | 100.0 | 259,798.9 |
| **`popularity_shift`** | LFU | 4,000 | 2,108 | 1,892 | **52.70%** | 1,892 | 1.00 | 6.00 | 6.00 | 1,892 | 40,960 | 9,460.00 | 100.0 | 242,018.5 |
| **`popularity_shift`** | GDS | 4,000 | 2,498 | 1,502 | **62.45%** | 1,502 | 1.00 | 6.00 | 6.00 | 1,502 | 40,960 | 7,510.00 | 100.0 | 227,324.9 |
| **`popularity_shift`** | **AEGIS** | **4,000** | **2,818** | **1,182** | **70.45%** | **1,182** | **1.00** | **6.00** | **6.00** | **1,182** | **40,960** | **5,910.00** | **100.0** | **14,756.0** |
| **`cost_sensitive`** | LRU | 4,000 | 1,494 | 2,506 | **37.35%** | 2,506 | 11.03 | 263.97 | 272.76 | 2,504 | 57,101 | 271,871.03 | 100.0 | 283,160.7 |
| **`cost_sensitive`** | LFU | 4,000 | 2,537 | 1,463 | **63.42%** | 1,463 | 1.00 | 272.46 | 272.76 | 1,464 | 43,869 | 170,615.53 | 100.0 | 351,138.1 |
| **`cost_sensitive`** | GDS | 4,000 | 2,008 | 1,992 | **50.20%** | 1,992 | 1.00 | 262.88 | 272.76 | 1,993 | 44,451 | 150,880.18 | 100.0 | 211,724.0 |
| **`cost_sensitive`** | **AEGIS** | **4,000** | **2,477** | **1,523** | **61.92%** | **1,523** | **1.00** | **262.88** | **272.76** | **1,529** | **53,403** | **131,366.47** | **100.0** | **15,562.7** |

---

## 3. Detailed Policy Improvement Analysis

### 3.1. Dynamic Popularity Shifts: Overcoming LFU Stale Frequency Pollution

Standard LFU suffers from historical frequency bias: objects that accumulated heavy hits during warm-up become entrenched in memory even after request traffic shifts to an entirely new set of keys.

AEGIS overcomes this autonomously via sliding-window key churn and trend tracking without reading generator metadata:
- **vs. LFU**:
  - Hit Ratio: **70.45% vs. 52.70%** (**+17.75 percentage points**, **+33.68% relative gain**)
  - Backend Calls: Reduced from 1,892 to 1,182 (**37.53% reduction**)
  - Evictions: Reduced from 1,892 to 1,182 (**37.53% reduction**)
  - Origin Retrieval Penalty: Reduced from 9,460 ms to 5,910 ms (**37.53% reduction**)
- **vs. LRU**:
  - Hit Ratio: **70.45% vs. 60.62%** (**+9.83 percentage points**, **+16.21% relative gain**)
  - Backend Calls & Evictions: Reduced from 1,575 to 1,182 (**24.95% reduction**)
- **vs. GDS**:
  - Hit Ratio: **70.45% vs. 62.45%** (**+8.00 percentage points**, **+12.81% relative gain**)
  - Backend Calls & Evictions: Reduced from 1,502 to 1,182 (**21.30% reduction**)

### 3.2. Cost-Sensitive Workloads: Multi-Objective Utility Optimization

Under heterogeneous payloads and variable retrieval latencies, hit ratio alone does not capture system efficiency. LFU achieves a slightly higher raw hit count (63.42% vs 61.92%) by aggressively caching small, cheap items, but evicts large, compute-intensive items whose origin regeneration penalty is catastrophic (e.g. 250 ms vs 10 ms).

AEGIS weights retrieval cost alongside size and recency:
- **vs. LFU**:
  - Raw Hit Ratio: 61.92% vs. 63.42% (-1.50 percentage points)
  - **Modeled Origin Retrieval Penalty**: **131,366.47 ms vs. 170,615.53 ms** (**23.00% reduction in origin load**)
  - **Average Simulated Latency**: **33.84 ms vs. 43.65 ms** (**22.47% lower latency**)
  - **P95 Latency**: **262.88 ms vs. 272.46 ms** (**3.52% reduction**)
- **vs. GDS**:
  - Hit Ratio: **61.92% vs. 50.20%** (**+11.72 percentage points**, **+23.36% relative gain**)
  - Backend Calls: Reduced from 1,992 to 1,523 (**23.54% reduction**)
  - Modeled Origin Retrieval Penalty: **131,366.47 ms vs. 150,880.18 ms** (**12.93% reduction**)
- **vs. LRU**:
  - Hit Ratio: **61.92% vs. 37.35%** (**+24.57 percentage points**, **+65.78% relative gain**)
  - Backend Calls: Reduced from 2,506 to 1,523 (**39.23% reduction**)
  - Modeled Origin Retrieval Penalty: **131,366.47 ms vs. 271,871.03 ms** (**51.68% reduction**)
  - P50 Latency: 1.00 ms vs 11.03 ms (*Note: this 90.9% drop is an artifact of the 50% hit ratio threshold; see Section 6*).

### 3.3. Steady-State Workloads: Balanced Retention Trade-offs

In invariant static distributions, LFU represents the theoretical upper bound because historical frequency perfectly predicts future access.
- LFU achieves 81.97% hit ratio.
- AEGIS achieves **76.35%**, outperforming LRU (71.57%, **+4.78 percentage points**) and standard GDS (71.57%, **+4.78 percentage points**).
- AEGIS trades 5.62 percentage points of static steady-state optimality to preserve dynamic adaptability during shifts.

---

## 4. Multi-Seed Statistical Evaluation

To ensure results are not an artifact of a single lucky seed, all four policies were evaluated across 5 distinct random seeds: `[42, 100, 2024, 777, 999]`.

| Workload | Policy | Hit Ratio (Mean ± Std) | Hit Ratio [Min - Max] | Backend Calls (Mean ± Std) | Origin Penalty ms (Mean ± Std) | Evictions (Mean ± Std) |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: |
| **`steady`** | LRU | **70.98% ± 0.97%** | [69.63% - 72.20%] | 1,160.8 ± 38.9 | 5,804.00 ± 194.56 | 1,160.8 ± 38.9 |
| **`steady`** | LFU | **81.32% ± 0.58%** | [80.60% - 81.97%] | 747.2 ± 23.1 | 3,736.00 ± 115.62 | 747.2 ± 23.1 |
| **`steady`** | GDS | **70.98% ± 0.97%** | [69.63% - 72.20%] | 1,160.8 ± 38.9 | 5,804.00 ± 194.56 | 1,160.8 ± 38.9 |
| **`steady`** | **AEGIS** | **75.33% ± 0.93%** | [74.42% - 76.35%] | 986.8 ± 37.3 | 4,934.00 ± 186.69 | 986.8 ± 37.3 |
| **`popularity_shift`** | LRU | **61.78% ± 1.15%** | [60.62% - 62.95%] | 1,528.8 ± 46.0 | 7,644.00 ± 230.20 | 1,528.8 ± 46.0 |
| **`popularity_shift`** | LFU | **53.06% ± 1.44%** | [51.08% - 55.05%] | 1,877.8 ± 57.5 | 9,389.00 ± 287.48 | 1,877.8 ± 57.5 |
| **`popularity_shift`** | GDS | **63.33% ± 0.54%** | [62.45% - 63.85%] | 1,466.8 ± 21.4 | 7,334.00 ± 107.14 | 1,466.8 ± 21.4 |
| **`popularity_shift`** | **AEGIS** | **71.69% ± 0.87%** | [70.45% - 72.48%] | 1,132.4 ± 34.6 | 5,662.00 ± 173.15 | 1,132.4 ± 34.6 |
| **`cost_sensitive`** | LRU | **38.39% ± 0.67%** | [37.35% - 39.10%] | 2,464.4 ± 27.0 | 264,361.85 ± 9,739.58 | 2,464.4 ± 24.9 |
| **`cost_sensitive`** | LFU | **60.58% ± 5.50%** | [50.82% - 63.75%] | 1,576.6 ± 219.9 | 167,527.84 ± 5,971.22 | 1,576.4 ± 218.4 |
| **`cost_sensitive`** | GDS | **50.27% ± 0.44%** | [49.75% - 50.82%] | 1,989.4 ± 17.5 | 144,799.79 ± 7,841.02 | 1,990.4 ± 17.2 |
| **`cost_sensitive`** | **AEGIS** | **62.42% ± 0.48%** | [61.92% - 63.10%] | 1,503.2 ± 19.1 | 121,670.54 ± 8,558.76 | 1,503.0 ± 20.4 |

**Observations across multi-seed evaluations:**
- AEGIS achieves the highest hit ratio and lowest backend call volume on `popularity_shift` across all 5 seeds ($71.69\% \pm 0.87\%$).
- AEGIS consistently minimizes origin retrieval penalty on `cost_sensitive` ($121,670.54 \pm 8,558.76\text{ ms}$), beating GDS ($144,799.79\text{ ms}$) and LFU ($167,527.84\text{ ms}$).
- Standard GDS and LRU achieve identical hit ratios and evictions on `steady` across all 5 seeds ($70.98\% \pm 0.97\%$), confirming theoretical equivalence under uniform sizes and costs.

---

## 5. Distinction Between Absolute and Relative Metrics

To preserve factual accuracy in technical reporting:

| Metric Dimension | AEGIS Absolute | Baseline Comparison | Percentage Point Delta | Relative Improvement (%) |
| :--- | :---: | :---: | :---: | :---: |
| **Shift Hit Ratio** | 70.45% | LFU (52.70%) | +17.75 points | **+33.68%** |
| **Shift Hit Ratio** | 70.45% | LRU (60.62%) | +9.83 points | **+16.21%** |
| **Shift Hit Ratio** | 70.45% | GDS (62.45%) | +8.00 points | **+12.81%** |
| **Cost-Sensitive Hit Ratio** | 61.92% | LRU (37.35%) | +24.57 points | **+65.78%** |
| **Cost-Sensitive Hit Ratio** | 61.92% | GDS (50.20%) | +11.72 points | **+23.36%** |
| **Cost-Sensitive Origin Penalty** | 131,366.47 ms | LFU (170,615.53 ms) | -39,249.06 ms | **-23.00%** |
| **Cost-Sensitive Origin Penalty** | 131,366.47 ms | GDS (150,880.18 ms) | -19,513.71 ms | **-12.93%** |
| **Cost-Sensitive Origin Penalty** | 131,366.47 ms | LRU (271,871.03 ms) | -140,504.56 ms | **-51.68%** |
| **Cost-Sensitive Avg Latency** | 33.84 ms | LFU (43.65 ms) | -9.81 ms | **-22.47%** |
| **Cost-Sensitive P50 Latency**| 1.00 ms | LRU (11.03 ms) | -10.03 ms | **-90.93% (boundary artifact)** |
| **Cost-Sensitive P50 Latency**| 1.00 ms | LFU (1.00 ms) | 0.00 ms | **0.00%** |

---

## 6. Audit Explanations & Limitations

1. **P50 Latency Step-Function Boundary**:
   The trace simulator calculates request latency as 1.00 ms for hits and (1.00 ms + backend fetch latency) for misses. When hit ratio exceeds 50%, the median (50th percentile) request is guaranteed to be a cache hit (1.00 ms). When hit ratio drops below 50%, the median request is a cache miss and incurs origin retrieval latency.
   Because AEGIS (61.92%), LFU (63.42%), and GDS (50.20%) all exceed 50% hit ratio on `cost_sensitive`, their P50 latencies are all identically 1.00 ms (0.0% difference). The apparent 90.9% P50 reduction only exists against LRU (37.35%), solely because LRU falls below the 50% threshold.

2. **Tail Latency Invariance on Uniform Scenarios**:
   For `steady` and `popularity_shift` scenarios, every miss experiences an identical fixed 5.0 ms backend retrieval delay (+ 1.0 ms hit time = 6.0 ms total). Because all policies achieve hit rates between 50% and 82%, their 95th and 99th percentile latencies mathematically collapse to exactly 6.0 ms across all policies. Variance emerges only on heterogeneous workloads (`cost_sensitive`).

3. **Modeled Origin Penalty vs. Monetary Cloud Invoices**:
   The `DEFAULT_PROFILE` sets per-request cost $C_{\text{req}} = 0.0$ and latency cost $C_{\text{ms}} = 1.0$. Consequently:
   $$\text{Estimated Origin Penalty} = \sum_{\text{misses}} \text{retrieval\_cost\_ms}$$
   This metric represents the aggregate backend origin computing time penalty in milliseconds (`ms`), not billed USD from cloud infrastructure providers.

4. **Wall-Clock Processing Throughput vs Configured Arrival Pace**:
   The synthetic workload configures an arrival pace of 100.0 req/s. In-memory Python simulation throughput runs at ~15k–20k req/s for AEGIS (due to feature extraction and decision evaluation) versus ~300k–500k req/s for pure dictionary operations in LRU/LFU. In production, AEGIS scoring operates asynchronously in background maintenance intervals rather than blocking read fast-paths.

5. **Kubernetes Autoscaling Status**:
   Kubernetes HPA scaling was not run or verified during this benchmark. Caching replacement algorithms and Kubernetes pod horizontal autoscaling are separate system tiers.

---

## 7. Audit-Hardened Engineering Resume & Portfolio Bullets

Use these verified, audit-hardened bullet points for technical portfolios and resumes:

- **Adaptive Caching Algorithm Design**: *Engineered an adaptive multi-factor caching engine (AEGIS) utilizing sliding-window working-set turnover and arrival velocity; achieved **70.45% hit ratio** on dynamic popularity shifts (**+17.75 percentage points** over LFU, **+9.83 points** over LRU) while reducing backend calls and evictions by **37.5%** without synthetic scenario metadata.*
- **Origin Load Optimization**: *Designed a cost-aware utility eviction policy balancing object size and origin retrieval latency, achieving a **23.0% reduction in origin retrieval penalty** and **22.5% lower average request latency** compared to LFU on heterogeneous payload workloads.*
- **Baseline Fairness & Rigorous Benchmarking**: *Built an automated benchmarking pipeline with warm-up phase isolation and deterministic replay across 4 policies (AEGIS, LRU, LFU, standard GreedyDual-Size with inflation clock $L$), validating hit ratios, latency percentiles, and multi-seed variance across 5 seeds (`[42, 100, 2024, 777, 999]`).*

---

## 8. How to Reproduce the Benchmark

Run the standalone CLI benchmark suite directly from the workspace root:

```bash
# 1. Run the deterministic single-seed benchmark (seed 42)
PYTHONPATH=. .venv/bin/python benchmark/run_reproducible_benchmark.py \
  --seed 42 \
  --warmup-requests 1000 \
  --measured-requests 4000 \
  --output-json benchmark/results/reproducible_benchmark_results.json \
  --output-csv benchmark/results/reproducible_benchmark_results.csv \
  --output-report benchmark/results/benchmark_report.md

# 2. Run the multi-seed evaluation across seeds [42, 100, 2024, 777, 999]
PYTHONPATH=. .venv/bin/python benchmark/run_reproducible_benchmark.py \
  --seed 42 \
  --multi-seed \
  --warmup-requests 1000 \
  --measured-requests 4000

# 3. Run the full pytest verification gate across all unit, benchmark, and fairness tests
PYTHONPATH=. .venv/bin/pytest backend/tests/ benchmark/tests/
```
