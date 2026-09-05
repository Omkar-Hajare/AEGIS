# k6 Load Testing — Adaptive Cache System

This directory contains the performance, stress, and adaptive behavior load-testing suite for the Adaptive Cache System, designed to run against both **Docker Compose** and **Kubernetes** (Minikube).

---

## 1. Directory Structure

```
k6/
├── README.md                 # Documentation, configuration, and benchmark results
├── config.js                 # Shared environment configuration and target defaults
└── scenarios/
    ├── steady.js             # Baseline sustained throughput testing
    ├── spike.js              # Traffic surge and Kubernetes HPA autoscaling demonstration
    └── popularity-shift.js   # Dynamic access pattern shift for cache adaptation/eviction
```

---

## 2. Configuration & Environment Variables

All scenarios read configuration through environment variables with sensible defaults:

| Variable | Default Value | Description |
| :--- | :--- | :--- |
| `BASE_URL` | `http://localhost:8000` | Target backend host (e.g. `http://localhost:8000` for Compose, `http://10.103.58.156:8000` for Kubernetes ClusterIP). |
| `TARGET_PATH` | `/data/product/1` | Target endpoint path. Targets real cached payload retrieval. |
| `SLEEP_SECONDS` | `1` (or `0.005–0.1` for load) | Pace control: duration in seconds each Virtual User sleeps between requests. |
| `POPULAR_PATHS_A` | `/data/product/1,/data/product/2,/data/product/3` | Product set A for cache partition testing. |
| `POPULAR_PATHS_B` | `/data/product/7,/data/product/8,/data/product/9` | Product set B for cache partition testing. |

---

## 3. Real Backend Endpoints Used

The load test suite strictly exercises real FastAPI backend endpoints:

- **`/health`**: Lightweight health check endpoint verifying process responsiveness and service metadata.
- **`/data/product/{product_id}`**: Primary workload endpoint. Integrates the complete application stack:
  - `CacheManager.get()` lookup (Redis or In-Memory)
  - Origin database call simulation on cache miss
  - Dynamic payload size calculation
  - Metadata tracking (`access_count`, `hit_count`, `miss_count`, `retrieval_cost_ms`)
  - Prometheus telemetry recording (`requests_total`, `request_latency_seconds`, `cache_hits_total`, `cache_misses_total`)
- **`/data/recommendation/{user_id}`**: High-latency origin computation endpoint.

---

## 4. Scenarios Overview

### `scenarios/steady.js`
- **Purpose**: Establishes steady-state baseline performance under predictable, sustained concurrency.
- **Phases**: Ramp-up (10 VUs / 30s) → Sustained plateau (10 VUs / 60s) → Ramp-down (0 VUs / 30s).
- **Thresholds**:
  - `http_req_failed < 1%`
  - `http_req_duration p(95) < 500ms`

### `scenarios/spike.js`
- **Purpose**: Generates rapid traffic surges to stress the backend and trigger Kubernetes Horizontal Pod Autoscaler (HPA) scale-up.
- **Phases**: Baseline (5 VUs / 30s) → Rapid surge (50–80 VUs / 10s) → Sustained burst (60s) → Ramp-down (5 VUs / 10s) → Idle (0 VUs / 30s).
- **Thresholds**:
  - `http_req_failed < 1%`
  - `http_req_duration p(95) < 1000ms`

### `scenarios/popularity-shift.js`
- **Purpose**: Simulates non-stationary traffic where popularity transitions between disjoint key sets (`PRODUCTS_A` vs. `PRODUCTS_B`).
- **Demonstration**: Forces the Adaptive Cache closed-loop engine to observe hit-ratio drops, evaluate utility scoring, trigger eviction of cold keys, and dynamically scale capacity.
- **Thresholds**:
  - `http_req_failed < 1%`
  - `http_req_duration p(95) < 500ms`

---

## 5. Running the Tests

### Against Docker Compose
Ensure the multi-service stack is running (`docker compose up -d`):

```bash
# 1. Steady test
k6 run -e BASE_URL=http://localhost:8000 k6/scenarios/steady.js

# 2. Spike test
k6 run -e BASE_URL=http://localhost:8000 k6/scenarios/spike.js

# 3. Popularity shift test
k6 run -e BASE_URL=http://localhost:8000 k6/scenarios/popularity-shift.js
```

### Against Kubernetes (Minikube)
Execute `k6` within the Minikube network to ensure traffic routes directly through the Kubernetes Service ClusterIP (`http://10.103.58.156:8000`) and is load-balanced across all backend pods by `kube-proxy`:

```bash
# Copy scenarios into minikube
docker cp k6/. minikube:/k6/

# 1. Steady test
docker exec minikube k6 run \
  -e BASE_URL=http://10.103.58.156:8000 \
  -e SLEEP_SECONDS=0.1 \
  /k6/scenarios/steady.js

# 2. Popularity shift test
docker exec minikube k6 run \
  -e BASE_URL=http://10.103.58.156:8000 \
  -e SLEEP_SECONDS=0.1 \
  /k6/scenarios/popularity-shift.js

# 3. Spike test (triggers HPA scale-up)
docker exec minikube k6 run \
  --vus 80 \
  --duration 30s \
  -e BASE_URL=http://10.103.58.156:8000 \
  -e TARGET_PATH=/data/product/1 \
  -e SLEEP_SECONDS=0.005 \
  /k6/scenarios/spike.js
```

---

## 6. Benchmark Results

### Docker Compose Environment

| Scenario | Concurrency | Total Requests | Request Rate | Error Rate | Latency (P90) | Latency (P95) | Threshold Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `steady.js` | 10 VUs | 830 | 82.01 req/s | **0.00%** | 54.88 ms | 76.31 ms | **PASSED** |
| `spike.js` | 25 VUs | 3,100 | 307.34 req/s | **0.00%** | 59.20 ms | 96.55 ms | **PASSED** |
| `popularity-shift.js` | 15 VUs | 1,224 | 121.16 req/s | **0.00%** | 62.85 ms | 69.42 ms | **PASSED** |

### Kubernetes Environment (Minikube)

| Scenario | Concurrency | Total Requests | Request Rate | Error Rate | Latency (P90) | Latency (P95) | Threshold Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `steady.js` | 10 VUs | 868 | 85.88 req/s | **0.00%** | 36.02 ms | 46.78 ms | **PASSED** |
| `popularity-shift.js` | 15 VUs | 1,235 | 122.24 req/s | **0.00%** | 53.71 ms | 71.35 ms | **PASSED** |
| `spike.js` (Bursted) | 80 VUs | 24,614 | **819.41 req/s** | **0.00%** | 147.59 ms | 194.21 ms | **PASSED** |

---

## 7. Kubernetes HPA Autoscaling Verification

During the spike test on Kubernetes, the complete closed-loop infrastructure scaling lifecycle was verified:

```
                  k6 Traffic Burst (80 VUs, ~820 req/s)
                               │
                               ▼
                   backend ClusterIP Service
                               │
              ┌────────────────┴────────────────┐
              ▼                                 ▼
   FastAPI Pod 1 (~155m CPU)         FastAPI Pod 2 (~152m CPU)
              └────────────────┬────────────────┘
                               │
                               ▼
            Aggregated CPU: 143%–153% (Target: 50%)
                               │
                               ▼
               Kubernetes HPA Controller triggers
                               │
                Scale-Up: 2 Replicas → 4 Replicas
                               │
                Scale-Up: 4 Replicas → 6 Replicas
                               │
                               ▼
                  Traffic stops (0 req/s)
                               │
                 Idle CPU drops: 5m–6m (5%)
                               │
               60s Stabilization Window completes
                               │
                               ▼
                Scale-Down: 6 Replicas → 3 Replicas
                Scale-Down: 3 Replicas → 2 Replicas
```

### Verified Scaling Events
```
Events:
  Type    Reason             Age   From                       Message
  ----    ------             ----  ----                       -------
  Normal  SuccessfulRescale  3m    horizontal-pod-autoscaler  New size: 4; reason: cpu resource utilization above target
  Normal  SuccessfulRescale  3m    horizontal-pod-autoscaler  New size: 6; reason: cpu resource utilization above target
  Normal  SuccessfulRescale  45s   horizontal-pod-autoscaler  New size: 3; reason: All metrics below target
  Normal  SuccessfulRescale  30s   horizontal-pod-autoscaler  New size: 2; reason: All metrics below target
```

### Observability Integration
- **Prometheus**: Collected `kube_horizontalpodautoscaler_status_current_replicas` and `container_cpu_usage_seconds_total`.
- **Grafana Dashboard** (`adaptive-cache-dashboard`): Panel 14 (Pod Count) and Panel 17 (HPA Replicas) reflected real-time scaling from 2 to 4 to 6 and back to 2.
