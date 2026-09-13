# Adaptive Cache System — Project Overview

The Adaptive Cache System is a closed-loop, telemetry-driven caching and scaling tier designed for high-concurrency, data-intensive web applications. It replaces static, one-dimensional caching heuristics with a continuous mathematical heuristic engine that balances access frequency, recency, retrieval cost, popularity trends, and object size to optimize cache retention, proactive refresh, and capacity allocation.

---

## 1. Problem Statement

Static caching algorithms (LRU, LFU, FIFO, static TTLs) make uniform assumptions about data access patterns and operate on single, isolated dimensions:

1. **Recency-Only / Frequency-Only Blindness**: Traditional LRU discards frequently accessed assets during bursty sequential scans (scan-resistance failure). LFU retains stale legacy items that accrued high historical frequency but are no longer relevant.
2. **Computational and Economic Asymmetry**: Static policies treat all misses equally. In real systems, recalculating an expensive personalized recommendation (e.g., 600ms CPU-heavy origin computation) costs significantly more than retrieving a lightweight static catalog record (e.g., 20ms simple database read). Evicting the high-cost object creates disproportionate origin strain.
3. **Memory Footprint Disregard**: Traditional caches treat a 500-byte record the same as a 100-kilobyte payload during eviction, leading to rapid RAM exhaustion without proportional utility gain.
4. **Binary Expiration vs. Thrashing**: Hard time-to-live (TTL) cutoffs cause synchronized cache expirations ("cache stampedes") and serve stale data until the cutoff expires, regardless of whether origin mutations have occurred.
5. **Decoupled Infrastructure Scaling**: Cache eviction heuristics operate blind to container resource pressure, while container autoscalers (such as Kubernetes HPA) operate blind to application-level cache hit rates and memory value density.

---

## 2. Project Objective

The objective of this project is to build an intelligent, observable, and production-ready caching platform that:

- Dynamically optimizes cache residency using multi-dimensional runtime telemetry.
- Balances retrieval latency, compute expenditure, and RAM consumption through an integrated economic cost model.
- Maintains strict cache-database consistency across mutating operations via explicit invalidation boundaries.
- Couples application-level cache optimization with infrastructure-level Horizontal Pod Autoscaling (HPA) on Kubernetes.
- Delivers complete operational observability via Prometheus time-series metrics and pre-provisioned Grafana dashboards.

---

## 3. Proposed Solution

The system introduces an embedded **Adaptive Decision Engine** that executes within the backend service process. Rather than relying on external machine learning services or static rule tables, the engine evaluates continuous mathematical heuristics over a sliding observation window:

- **Multi-Factor Feature Extraction**: Calculates 5 normalized features for every resident object: access frequency, access recency, upstream retrieval cost, popularity velocity, and serialized size.
- **Dynamic Weight Modeling**: Telemetry signals (request rate, hit/miss ratios, origin latency, RAM utilization) dynamically adjust feature weights without manual intervention.
- **Economic Value Density Ranking**: Eviction candidates are ranked by their economic value density $\left(\frac{\text{retention\_value}}{\text{size}^\alpha}\right)$, ensuring memory is allocated to items that maximize origin cost savings.
- **Staleness Urgency Revalidation**: Evaluates continuous staleness via exponential decay functions to proactively refresh hot, volatile items before users observe cache misses.
- **Continuous Capacity Sizing**: Recommends cache memory adjustments based on composite pressure calculations across memory saturation, miss ratios, and arrival rates.
- **Orthogonal Infrastructure Scaling**: Decouples application cache decisions from Kubernetes HPA, allowing the infrastructure to scale pod replicas based on CPU load while the cache optimizes memory utilization.

---

## 4. How the Adaptive Cache System Works

The core intelligence is driven by a deterministic mathematical heuristic model implemented directly in Python (`backend/adaptive/`). It requires zero external ML training pipelines, model servers, or non-deterministic inference dependencies.

```
┌────────────────────────────────────────────────────────────────────────┐
│                   INCOMING APPLICATION TRAFFIC                         │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│ 1. TELEMETRY COLLECTION (backend/telemetry/collector.py)               │
│    Tracks hits, misses, latencies, requests, and per-key access counts │
│    over a configurable sliding observation window                      │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│ 2. SHARED CONTRACT TRANSLATION (backend/adaptive/service.py)           │
│    Transforms telemetry state and CacheManager metadata into frozen   │
│    Pydantic v1 schemas (CacheObject, WorkloadState, SystemState)      │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│ 3. ADAPTIVE DECISION PIPELINE (backend/adaptive/engine/decision_engine)│
│                                                                        │
│    a. Feature Extraction (backend/adaptive/features/extractor.py)      │
│       Computes 5 normalized [0, 1] features per resident object:       │
│       • Frequency: min-max normalized window access count              │
│       • Recency: exponential decay 1 - (age / window)                  │
│       • Retrieval Cost: normalized upstream regeneration cost (ms)     │
│       • Size Penalty: normalized memory footprint (bytes)              │
│       • Popularity Trend: access velocity 0.5 + 0.5·tanh(Δacc / prev)   │
│                                                                        │
│    b. Dynamic Weight Derivation (backend/adaptive/scoring/)            │
│       Dynamically shifts weights (w_freq, w_recency, w_cost, w_trend,  │
│       w_size) based on live arrival rate and system pressure           │
│                                                                        │
│    c. Retention Scoring (backend/adaptive/scoring/scorer.py)           │
│       score = w_f·freq + w_r·recency + w_c·cost + w_t·trend - w_s·size │
│                                                                        │
│    d. Economic Eviction (backend/adaptive/eviction/policy.py)          │
│       Ranks objects by Value Density = retention_value / (size ^ α)    │
│       Selects lowest-density items for eviction under memory pressure   │
│                                                                        │
│    e. Proactive Refresh Urgency (backend/adaptive/refresh/policy.py)   │
│       Computes urgency ∈ [0, 1] based on age, access rate, and cost;   │
│       Keys with urgency ≥ 0.50 flagged for background refresh          │
│                                                                        │
│    f. Capacity Sizing (backend/adaptive/capacity/controller.py)        │
│       Composite pressure signals: MAINTAIN, SCALE_UP, or SCALE_DOWN    │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│ 4. DETERMINISTIC DECISION (contracts/schemas/decision.py)              │
│    Outputs SHA-256 verified Decision payload recorded in history       │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 5. Main Architecture

The platform follows a modular microservice architecture orchestrated over Docker Compose locally and Kubernetes/Helm in cluster environments.

```
                              ┌───────────────────────────┐
                              │     User / Web Browser    │
                              └─────────────┬─────────────┘
                                            │
                                            ▼
                              ┌───────────────────────────┐
                              │ Streamlit UI Dashboard    │
                              │ (adaptive-frontend:8501)  │
                              └─────────────┬─────────────┘
                                            │ HTTP
                                            ▼
┌───────────────────────────────────────────────────────────────────────────────────────┐
│ FastAPI Application (adaptive-backend:8000)                                           │
│                                                                                       │
│  ┌───────────────────────┐  ┌───────────────────────┐  ┌───────────────────────────┐  │
│  │ HTTP Route Handlers   │  │ Cache Invalidation    │  │ Prometheus Middleware     │  │
│  │ (/data, /cache, etc.) │  │ Boundary              │  │ (/metrics endpoint)       │  │
│  └───────────┬───────────┘  └───────────┬───────────┘  └─────────────┬─────────────┘  │
│              │                          │                            │                │
│              ▼                          ▼                            │                │
│  ┌──────────────────────────────────────────────────┐                │                │
│  │ CacheManager (backend/cache/manager.py)          │                │                │
│  │ • In-memory metadata tracking                    │                │                │
│  │ • Pluggable store adapter                        │                │                │
│  └───────────┬──────────────────────────────────────┘                │                │
│              │                                                       │                │
│              ├──────────────────────┐                                │                │
│              ▼                      ▼                                │                │
│   ┌─────────────────────┐┌────────────────────────┐                  │                │
│   │ InMemoryCache (RAM) ││ RedisCache (redis:6379)│                  │                │
│   └─────────────────────┘└────────────────────────┘                  │                │
│              │                                                       │                │
│              ▼                                                       │                │
│  ┌──────────────────────────────────────────────────┐                │                │
│  │ Adaptive Intelligence Subsystem                  │                │                │
│  │ (DecisionEngine, Scorer, CostModel, Capacity)    │                │                │
│  └──────────────────────────────────────────────────┘                │                │
└───────────────────────┬──────────────────────────────────────────────┼────────────────┘
                        │                                              │
         ┌──────────────┴──────────────┐                               │ Scrape (5s)
         │                             │                               ▼
         ▼                             ▼                  ┌───────────────────────────┐
┌─────────────────┐           ┌──────────────────┐        │ Prometheus Server         │
│ PostgreSQL 16   │           │ Upstream Backend │        │ (adaptive-prometheus:9090)│
│ (postgres:5432) │           │ Origin Adapters  │        └─────────────┬─────────────┘
│ Metadata Store  │           │ (Simulated /     │                      │ PromQL
│ & Persistence   │           │  Amazon-like)    │                      ▼
└─────────────────┘           └──────────────────┘        ┌───────────────────────────┐
                                                          │ Grafana Dashboard         │
                                                          │ (adaptive-grafana:3000)   │
                                                          └───────────────────────────┘
```

---

## 6. Technology Stack

| Domain | Technology | Version | Purpose |
| :--- | :--- | :--- | :--- |
| **API Backend** | FastAPI / Uvicorn | `0.115+` / `0.30+` | High-performance asynchronous REST API framework |
| **Data Contracts** | Pydantic / Pydantic-Settings | `v2.8+` | Frozen contract enforcement, schema validation, and config |
| **Caching Layer** | Redis / In-Memory Python Dict | Redis `7-alpine` | Fast low-latency key-value storage with TTL support |
| **Persistence** | PostgreSQL / SQLAlchemy | PostgreSQL `16-alpine` / SQLAlchemy `2.0+` | Persistent storage for cache metadata and telemetry snapshots |
| **Database Driver** | Psycopg 3 | `psycopg[binary]>=3.1` | Asynchronous/synchronous PostgreSQL database client |
| **Frontend UI** | Streamlit | `1.38+` | Control center dashboard for live inspection and demo |
| **Data Visualization** | Plotly | `5.24+` | Interactive charts for telemetry, benchmarks, and costs |
| **Metrics Collection** | Prometheus Client | `0.20+` | Exposes internal gauges, histograms, and counters |
| **Metrics Storage** | Prometheus Server | `v2.54.1` | Time-series scraper and metrics database |
| **Dashboards** | Grafana | `11.1.0` | Pre-provisioned 4-row operational dashboard |
| **Containers** | Docker / Docker Compose | Compose file v3.8 | Local multi-service orchestration |
| **Cluster Runtime** | Kubernetes / Minikube | `v1.28+` | Container orchestration, HPA, and ServiceMonitors |
| **Package Manager** | Helm | `v3+` | Templated Kubernetes deployment (`helm/adaptive-cache`) |
| **Testing & Load** | Pytest / k6 | Pytest `8.3+` / k6 `0.50+` | Automated testing and performance/load validation |

---

## 7. Important Backend Components

### `backend/app/main.py`
FastAPI application entry point. Configures CORS, mounts routers, attaches the Prometheus HTTP middleware (`requests_total`, `request_latency_seconds`), exposes `/health`, and serves `/metrics` with telemetry gauge synchronization.

### `backend/cache/manager.py` & `backend/cache/invalidation.py`
- `CacheManager`: Manages the active `CacheStore` backend (`InMemoryCache` or `RedisCache`) and maintains an in-memory dictionary of `CacheObjectMetadata` recording hits, misses, access timestamps, and retrieval costs.
- `CacheInvalidator`: Implements the explicit cache invalidation boundary. Ensures mutating actions synchronously evict resident keys and purge metadata rows from PostgreSQL.

### `backend/telemetry/collector.py`
`TelemetryCollector` records sliding-window metrics: request rates, hit ratios, miss counts, backend response delays, and per-key access frequencies. Computes rate observations without resetting raw counters and rotates historical windows.

### `backend/adaptive/service.py`
`AdaptiveService` acts as the bridge between live runtime state and the decision engine. It converts mutable runtime metadata into frozen immutable contract models (`CacheObject`, `WorkloadState`, `SystemState`) and delegates evaluation to `DecisionEngine`.

### `backend/adaptive/engine/decision_engine.py`
`DecisionEngine` is the top-level pipeline orchestrator. It executes feature extraction, dynamic weight calculation, retention scoring, staleness urgency evaluation, capacity recommendation, and eviction selection. Generates a deterministic SHA-256 decision ID.

### `backend/cost/model.py`
`CostModel` evaluates economic trade-offs based on a `CostProfile`. Calculates backend compute cost saved by caching versus RAM retention cost, deriving the continuous **Value Density** metric that ranks eviction candidates.

### `backend/database/repositories/`
- `CacheMetadataRepository`: Persists cache object metadata to PostgreSQL (`cache_metadata` table).
- `TelemetryRepository`: Persists historical telemetry observation windows (`telemetry_observations` table).

---

## 8. Cache Request Flow

```
Client Request (e.g., GET /data/product/{id})
   │
   ▼
FastAPI Middleware
   ├─► Start request timer (request_latency_seconds)
   └─► Increment requests_total
   │
   ▼
CacheManager.get(key) ────────────────────────┐
   │                                          │
   ├─► [HIT in CacheStore]                    ├─► [MISS in CacheStore]
   │   │                                      │   │
   │   ├─► Increment cache_hits_total         │   ├─► Increment cache_misses_total
   │   ├─► Record hit in TelemetryCollector   │   ├─► Record miss in TelemetryCollector
   │   ├─► Update CacheObjectMetadata access  │   │
   │   └─► Return cached data immediately     │   ▼
   │       (Zero SQL / Origin calls)          BackendAdapter.get_product(id)
   │                                          │   (Simulates 30ms-600ms origin delay)
   │                                          │
   │                                          ├─► Record backend latency
   │                                          ├─► Calculate payload size in bytes
   │                                          ├─► CacheManager.set(key, data)
   │                                          ├─► CacheManager.create_metadata(...)
   │                                          ├─► Persist metadata to PostgreSQL
   │                                          └─► Return fresh data to client
```

### Invalidation Request Flow (`DELETE /data/product/{id}`)
1. Client sends a mutating request.
2. `CacheInvalidator.invalidate_key(key)` is invoked within the database transaction boundary.
3. Key is purged from the active `CacheStore` (Redis `DEL` or dict removal).
4. Key metadata is purged from the in-memory registry and PostgreSQL `cache_metadata` table.
5. Subsequent client reads experience a guaranteed cache miss, fetching fresh origin data.

---

## 9. Adaptive Decision Flow

The adaptive decision process can be triggered on-demand via `GET /adaptive/runtime-decision` or scheduled periodically:

```
TelemetryCollector.observe() + CacheManager.get_all_metadata()
   │
   ▼
AdaptiveService.decide()
   │ Converts runtime dictionaries into frozen schemas:
   │ (CacheObject contracts, WorkloadState, SystemState)
   │
   ▼
DecisionEngine.decide()
   │
   ├─► 1. FeatureExtractor.extract()
   │      Computes [0, 1] normalized frequency, recency, retrieval_cost,
   │      size, and popularity_trend for each resident object.
   │
   ├─► 2. WorkloadAnalyzer.analyze()
   │      Classifies pattern: STEADY, SPIKE, READ_HEAVY, COMPUTE_HEAVY,
   │      or POPULARITY_SHIFT.
   │
   ├─► 3. DynamicWeightModel.compute_weights()
   │      Derives feature weights based on arrival rate, miss rate, and latency.
   │
   ├─► 4. AdaptiveScorer.score()
   │      Generates composite retention score per object.
   │
   ├─► 5. RefreshPolicy.compute_urgency()
   │      Calculates staleness urgency; objects ≥ 0.50 flagged in refresh_keys.
   │
   ├─► 6. CapacityController.recommend()
   │      Calculates composite system pressure and recommends MAINTAIN,
   │      SCALE_UP, or SCALE_DOWN with suggested target bytes.
   │
   └─► 7. EvictionPolicy.select_evictions()
          Ranks candidates by CostModel.value_density(); selects lowest-density
          keys for eviction when memory pressure requires space recovery.
   │
   ▼
Decision Schema Generated
   ├─► Assigned deterministic SHA-256 decision_id
   ├─► Appended to DecisionHistory (bounded deque, newest-first)
   └─► Returned to caller (FastAPI response / Grafana visualization)
```

---

## 10. Kubernetes Scaling Flow (vs. Adaptive Cache Decisions)

The platform enforces a strict separation of concerns between application-level cache optimization and infrastructure-level horizontal scaling:

```
┌────────────────────────────────────────────────────────────────────────────────┐
│                           CONCURRENT CLIENT TRAFFIC                            │
└───────────────────────┬────────────────────────────────┬───────────────────────┘
                        │                                │
                        ▼                                ▼
┌──────────────────────────────────────────┐   ┌─────────────────────────────────┐
│     APPLICATION-LEVEL CACHE CONTROL      │   │    INFRASTRUCTURE HPA SCALING   │
│     (backend/adaptive/ DecisionEngine)   │   │    (Kubernetes HPA Controller)  │
├──────────────────────────────────────────┤   ├─────────────────────────────────┤
│ Scope: In-process cache optimization     │   │ Scope: Pod replica count        │
│ Decision: Eviction, Refresh, Sizing      │   │ Decision: Number of backend pods│
│ Action: Purges low-value items via value │   │ Action: Deploys or terminates   │
│ density; sizes cache memory capacity.    │   │ container replicas (2 to 6 pods)│
│ Metric: Hit ratio, byte value density,   │   │ Metric: Average CPU utilization │
│ origin latency, staleness urgency.       │   │ target (50% target threshold).  │
└──────────────────────────────────────────┘   └─────────────────────────────────┘
```

### Kubernetes HPA Lifecycle (`k8s/backend/hpa.yaml`)
1. **Traffic Surge**: k6 load generator bursts traffic (e.g., 80 Virtual Users, 820 req/s) against the `backend` ClusterIP Service (`port: 8000`).
2. **CPU Pressure**: Pod CPU consumption exceeds the configured 50% target (climbing to 140%–153%).
3. **Rapid Scale-Up**: HPA controller detects sustained CPU pressure and rapidly scales the `backend` Deployment from 2 replicas to 4, then to 6 replicas (`maxReplicas: 6`, `scaleUp.stabilizationWindowSeconds: 0`).
4. **Traffic Distribution**: `kube-proxy` balances requests across all active pod endpoints.
5. **Stabilized Scale-Down**: When load subsides, pod CPU utilization drops below 10%. Following a 60-second stabilization window (`scaleDown.stabilizationWindowSeconds: 60`), HPA safely scales down to 3, and then back to the baseline 2 replicas (`minReplicas: 2`).

---

## 11. Workload Scenarios

The system adapts to five distinct workload scenarios, simulated in tests and benchmarks:

1. **`STEADY`**: Balanced read/write traffic at predictable arrival rates. Heuristic weights remain distributed evenly between access frequency and recency.
2. **`SPIKE`**: Traffic suddenly surges to $\ge 1.5\times$ baseline. Dynamic weights amplify recency and popularity velocity; the capacity controller signals memory scale-up; Kubernetes HPA triggers pod replica scaling.
3. **`READ_HEAVY`**: High hit ratios ($\ge 80\%$) and low write activity. Feature weights favor access frequency and low-latency cache retrieval, minimizing CPU overhead.
4. **`COMPUTE_HEAVY`**: High origin latency ($\ge 200\text{ms}$) caused by complex calculations (e.g., recommendation pipelines). The economic cost model significantly boosts retention scores for expensive items to prevent costly origin recalculation.
5. **`POPULARITY_SHIFT`**: Traffic abruptly transitions to a disjoint set of keys. The sliding observation window identifies the drop in hit ratio and velocity; historical items lose retention priority, and new keys rapidly acquire high cache residency.

---

## 12. Observability and Monitoring

The platform provides a complete observability pipeline using native Prometheus exposition and pre-provisioned Grafana dashboards.

### Prometheus Metrics Catalog (`backend/metrics/prometheus.py`)

| Metric Name | Type | Description | Labels / Dimensions |
| :--- | :--- | :--- | :--- |
| `requests_total` | Counter | Total HTTP requests handled by FastAPI | `method`, `endpoint`, `status` |
| `request_latency_seconds` | Histogram | HTTP request latency with percentile buckets | `method`, `endpoint` |
| `cache_hits_total` | Counter | Cumulative cache hits | None |
| `cache_misses_total` | Counter | Cumulative cache misses | None |
| `cache_hit_ratio` | Gauge | Current cache hit ratio $[0, 1]$ (synced on scrape) | None |
| `cache_size_bytes` | Gauge | Estimated resident cache memory usage | None |
| `cache_object_count` | Gauge | Total objects tracked in cache metadata | None |
| `cache_evictions_total` | Counter | Total objects evicted by eviction policies | None |
| `backend_requests_total` | Counter | Total calls forwarded to upstream origin | None |
| `backend_latency_seconds` | Histogram | Upstream origin retrieval latency | None |
| `backend_avg_latency_ms` | Gauge | Average origin latency in current window | None |
| `request_rate_per_second` | Gauge | Live request arrival rate in current window | None |
| `adaptive_decisions_total`| Counter | Total adaptive decisions evaluated | None |

### Grafana Dashboard ("Adaptive Cache System")
Auto-provisioned via `monitoring/grafana/provisioning/dashboards/adaptive-cache.json`. Organized into 4 structured rows:

1. **APPLICATION**:
   - Request Rate (req/s by endpoint and status)
   - Request Latency (P95 and P99 percentiles)
   - Error Rate (percentage of 4xx/5xx responses)
   - Origin Backend Latency (P50 and P95 origin response times)
2. **CACHE**:
   - Cache Hit Ratio (Gauge with color thresholds: Red $<50\%$, Yellow $50\%-80\%$, Green $\ge 80\%$)
   - Cache Hits vs. Misses (per-second rates)
   - Cache Memory Footprint (bytes) & Object Count
   - Cache Evictions Rate
3. **ADAPTIVE SYSTEM**:
   - Total Adaptive Decisions Evaluated
   - Workload Arrival Rate
   - Average Origin Latency
   - Control Loop Information & Decision Breakdown
4. **KUBERNETES**:
   - Active Backend Pod Count (Running pods)
   - Container CPU Usage across backend pods
   - Container Memory Working Set
   - HPA Desired vs. Current Replicas

---

## 13. Project Directory Overview

```
VH26-Satyagrah/
├── backend/                       # FastAPI application & adaptive intelligence
│   ├── adaptive/                  # Intelligence core (pure Python, zero I/O)
│   │   ├── capacity/              # Continuous capacity controller
│   │   ├── engine/                # DecisionEngine pipeline orchestrator
│   │   ├── eviction/              # Value-density eviction policy
│   │   ├── features/              # Multi-factor feature extractor
│   │   ├── policies/              # Baseline policies (LRU/LFU/GDS) for benchmarks
│   │   ├── refresh/               # Staleness urgency & proactive refresh policy
│   │   ├── scoring/               # Dynamic weight model & retention scorer
│   │   ├── workload/              # Rule-based workload pattern analyzer
│   │   ├── history.py             # Thread-safe in-memory decision history
│   │   └── service.py             # Runtime state-to-contract translation bridge
│   ├── api/                       # API routes (data, cache, telemetry, adaptive)
│   ├── app/                       # FastAPI app factory, config, and dependencies
│   ├── cache/                     # CacheManager, InMemoryCache, RedisCache, invalidator
│   ├── cost/                      # Economic cost profiles and value-density model
│   ├── database/                  # SQLAlchemy models, connections, and repositories
│   ├── metrics/                   # Prometheus metric definitions and scrape sync
│   ├── telemetry/                 # Sliding-window telemetry collector and state models
│   ├── workload/                  # Upstream backend adapters (Simulated, Amazon-like)
│   └── tests/                     # Unit and integration tests (mirrors backend structure)
├── frontend/                      # Streamlit dashboard ("AEGIS")
│   ├── components/                # Reusable UI cards, charts, badges, and layout
│   ├── views/                     # Views for simulator, objects, decisions, costs
│   ├── services/                  # HTTP clients to backend API
│   └── app.py                     # Streamlit application entry point
├── contracts/                     # Frozen v1 Pydantic schemas shared across all layers
│   └── schemas/                   # CacheObject, WorkloadState, SystemState, Decision
├── benchmark/                     # Offline trace simulator comparing Adaptive vs LRU/LFU/GDS
├── demo/                          # Standalone CLI demo of the adaptive pipeline
├── k8s/                           # Raw Kubernetes manifests (backend, frontend, redis, db)
├── helm/adaptive-cache/           # Parameterized Helm chart for Kubernetes deployment
├── monitoring/                    # Prometheus scrape config and Grafana provisioning
├── k6/                            # k6 performance and load-test scenarios
├── docker-compose.yml             # Full 6-service local development stack
├── requirements.txt               # Top-level development dependencies
└── pytest.ini                     # Pytest configuration
```

---

## 14. Main API and Dashboard Entry Points

### Service Ports and Web Interfaces

| Service | Container / Pod Name | Port | Access URL | Credentials |
| :--- | :--- | :--- | :--- | :--- |
| **FastAPI Backend** | `adaptive-backend` | `8000` | `http://localhost:8000` (Docs: `/docs`) | None |
| **Streamlit Dashboard** | `adaptive-frontend` | `8501` | `http://localhost:8501` | None |
| **Prometheus UI** | `adaptive-prometheus` | `9090` | `http://localhost:9090` | None |
| **Grafana UI** | `adaptive-grafana` | `3000` | `http://localhost:3000` | `admin` / `admin` |
| **Redis Store** | `adaptive-redis` | `6379` | `localhost:6379` | None |
| **PostgreSQL DB** | `adaptive-postgres` | `5432` | `localhost:5432` (`adaptive_cache`) | `postgres` / `postgres` |

### Primary REST API Endpoints

| Method | Endpoint | Purpose |
| :--- | :--- | :--- |
| `GET` | `/health` | Health probe returning service name, status, and version |
| `GET` | `/metrics` | Prometheus metrics exposition format with live telemetry sync |
| `GET` | `/data/product/{product_id}` | Read cached product catalog item (generates cache miss/hit) |
| `DELETE`| `/data/product/{product_id}` | Mutate product and trigger cache/metadata invalidation |
| `GET` | `/data/recommendation/{user_id}` | Read cached high-latency compute recommendation |
| `DELETE`| `/data/recommendation/{user_id}` | Invalidate recommendation entry |
| `GET` | `/cache/objects` | Inspect all resident cache objects, access counts, and sizes |
| `DELETE`| `/cache/objects/{key}` | Manually invalidate a specific cache key and its metadata |
| `GET` | `/telemetry/observation` | View current sliding-window request rates, hit ratios, and latencies |
| `POST`| `/telemetry/window/reset` | Rotate the telemetry sliding window |
| `GET` | `/adaptive/runtime-decision` | Trigger live evaluation of the adaptive decision engine |
| `GET` | `/adaptive/decisions` | Retrieve in-memory history of recent adaptive decisions |
| `POST`| `/adaptive/decision` | Stateless evaluation of a decision given an arbitrary payload |
