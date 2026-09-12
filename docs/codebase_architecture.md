# Codebase Architecture Reference

A complete map of the VH26-Satyagrah repository: what every directory contains, what each module does, the exact classes/functions that implement each piece of adaptive-caching logic, and how a request flows through the system end to end.

This document describes **where things live**, not how to run them — see `docs/docker-compose.md`, `docs/docker.md`, and `docs/phase4_grafana_dashboard.md` for operational instructions.

---

## 1. Quick Reference — "Where is X implemented?"

| Question | File | Class / Function |
|---|---|---|
| **Where is the cost model?** | `backend/cost/cost_profile.py` | `CostProfile` — immutable per-platform economic parameters (`backend_cost_per_request`, `backend_cost_per_ms`, `cache_memory_cost_per_gb_hour`) |
| | `backend/cost/model.py` | `CostModel.estimate_backend_cost_saved()`, `.estimate_cache_ram_cost()`, `.estimate_net_benefit()`, `.value_density()` — the actual cost math |
| | `backend/cost/profiles.py` | `get_profile(name)` + preset profiles: `DEFAULT_PROFILE`, `POSTGRESQL_PROFILE`, `MYSQL_PROFILE`, `EXTERNAL_API_PROFILE` |
| | `backend/adaptive/eviction/policy.py` | `EvictionPolicy.select_evictions()` — where `CostModel.value_density()` is actually **called** to rank eviction candidates |
| **Where is stale-cache / refresh management?** | `backend/adaptive/refresh/policy.py` | `RefreshPolicy.compute_urgency()` (the staleness math) and `RefreshPolicy.should_refresh()` (the threshold decision) |
| | `backend/adaptive/engine/decision_engine.py` | `DecisionEngine.decide()`, step "6. Staleness / refresh evaluation" — where refresh urgency is computed per object and collected into `Decision.metadata["refresh_keys"]` |
| **Where is eviction decided?** | `backend/adaptive/eviction/policy.py` | `EvictionPolicy.select_evictions()` — value-density-based selection |
| **Where are baseline LRU/LFU/GDS policies (for benchmarking only)?** | `backend/adaptive/policies/{lru,lfu,gds,base}.py` | `LRUPolicy`, `LFUPolicy`, `GDSPolicy` (each extends `BaseEvictionPolicy`) — used only by `benchmark/`, **not** by the live `/adaptive/*` API |
| **Where is capacity scaling decided?** | `backend/adaptive/capacity/controller.py` | `CapacityController.compute_pressure()` and `.recommend()` |
| **Where is workload classified (SPIKE/READ_HEAVY/...)?** | `backend/adaptive/workload/analyzer.py` | `WorkloadAnalyzer.analyze()` |
| **Where are per-object features computed?** | `backend/adaptive/features/extractor.py` | `FeatureExtractor.extract()` — frequency, recency, retrieval_cost, size, popularity_trend |
| **Where are retention scores computed?** | `backend/adaptive/scoring/scorer.py` | `AdaptiveScorer.score()` |
| | `backend/adaptive/scoring/dynamic_weights.py` | `DynamicWeightModel.compute_weights()` — turns telemetry into per-feature weights instead of static lookup tables |
| **Where does everything get orchestrated into one `Decision`?** | `backend/adaptive/engine/decision_engine.py` | `DecisionEngine.decide()` |
| | `backend/adaptive/service.py` | `AdaptiveService.decide()` — the live-runtime bridge (telemetry + cache state → contracts → `DecisionEngine`) called by the API |
| **Where is the cache actually stored?** | `backend/cache/manager.py` | `CacheManager` (metadata + delegate) |
| | `backend/cache/in_memory.py` / `backend/cache/redis.py` | `InMemoryCache`, `RedisCache` — pluggable `CacheStore` backends |
| | `backend/cache/factory.py` | `create_cache_manager()` — selects backend via `CACHE_BACKEND` env var |
| **Where does upstream "backend" data come from?** | `backend/workload/adapter.py` | `BackendAdapter` ABC |
| | `backend/workload/simulated.py`, `backend/workload/amazon_like.py` | Concrete adapters (synthetic data, no real external calls) |
| | `backend/workload/factory.py` | `get_backend_adapter()` — selects adapter via `DATA_BACKEND` env var |
| **Where are the frozen API contracts?** | `contracts/schemas/*.py` | `CacheObject`, `WorkloadState`, `SystemState`, `Decision`, `WorkloadType`, `CapacityAction` |
| **Where is telemetry collected?** | `backend/telemetry/collector.py` | `TelemetryCollector` (counters, sliding window) |
| | `backend/telemetry/state.py` | `build_workload_state()`, `build_system_state()` — converts raw telemetry into contract-shaped state |
| **Where are Prometheus metrics exposed?** | `backend/metrics/prometheus.py` | Metric definitions + `sync_from_telemetry()` |
| | `backend/app/main.py` | `GET /metrics` endpoint |
| **Where are the FastAPI HTTP routes?** | `backend/api/routes/*.py` | `data.py` (product/recommendation), `cache.py` (inspect/invalidate), `telemetry.py`, `adaptive.py` |
| **Where is Postgres persistence?** | `backend/database/repositories/*.py` | `CacheMetadataRepository`, `TelemetryRepository` |
| **Where does the Streamlit UI live?** | `frontend/views/*.py` | One file per dashboard tab |
| **Where is the offline CLI demo?** | `demo/adaptive_demo.py` | Runs the whole adaptive pipeline without FastAPI/DB |
| **Where is the LRU/LFU/GDS/Adaptive comparison benchmark?** | `benchmark/*.py` | `CacheSimulator`, `BenchmarkRunner`, policy adapters |
| **Where are Kubernetes manifests / Helm chart?** | `k8s/`, `helm/adaptive-cache/` | Deployments, Services, HPA, ServiceMonitors |
| **Where is the Grafana dashboard defined?** | `monitoring/grafana/provisioning/` (docker-compose), `k8s/monitoring/dashboard-configmap.yaml` (Kubernetes) | Same 21-panel dashboard JSON, two provisioning paths |

---

## 2. Full Directory Tree

```
VH26-Satyagrah/
├── backend/                        FastAPI application + adaptive intelligence
│   ├── adaptive/                   The "intelligence" subsystem (pure Python, no I/O)
│   │   ├── capacity/                Capacity sizing (scale up/down/maintain)
│   │   ├── engine/                  DecisionEngine — orchestrates everything below
│   │   ├── eviction/                Value-density eviction selection
│   │   ├── features/                Per-object feature extraction
│   │   ├── policies/                Baseline LRU/LFU/GDS (benchmark-only)
│   │   ├── refresh/                 Staleness / refresh urgency (see §5)
│   │   ├── scoring/                 Retention scoring + dynamic feature weights
│   │   ├── workload/                Workload type classification
│   │   ├── history.py               Bounded in-memory Decision history
│   │   └── service.py               AdaptiveService — live runtime bridge
│   ├── api/
│   │   ├── routes/                  FastAPI routers: data, cache, telemetry, adaptive
│   │   └── schemas/                 Pydantic response models (API-facing only)
│   ├── app/                         FastAPI app factory, settings, DI
│   ├── cache/                       CacheStore abstraction + CacheManager + metadata
│   ├── cost/                        Economic cost model (see §4)
│   ├── database/                    SQLAlchemy models, connection, repositories
│   ├── metrics/                     Prometheus metric definitions
│   ├── telemetry/                   Runtime request/hit/miss/latency collection
│   ├── workload/                    Upstream "backend" data adapters + synthetic
│   │                                 workload/scenario generation for benchmarks
│   ├── tests/                       pytest suite, mirrors the structure above
│   ├── Dockerfile, requirements.txt
│   └── (backend/workload ≠ backend/adaptive/workload — see §6.7 note)
├── benchmark/                       Offline LRU vs LFU vs GDS vs Adaptive comparison engine
├── contracts/schemas/               Frozen v1 Pydantic contracts shared by every layer
├── demo/                            Standalone CLI demo of the adaptive pipeline
├── docs/                            Specifications and this file
├── frontend/                        Streamlit "AEGIS — Adaptive Cache Control Center" UI
│   ├── components/                   Reusable UI widgets (cards, charts, badges, navbar)
│   ├── mocks/                        Offline fallback data when backend is unreachable
│   ├── services/                     HTTP client(s) to the FastAPI backend
│   ├── utils/                        Formatting helpers
│   └── views/                        One module per dashboard tab/page
├── helm/adaptive-cache/             Helm chart mirroring k8s/ for Helm-based deploys
├── k6/                              k6 load-test scenarios (steady, spike, popularity-shift)
├── k8s/                             Raw Kubernetes manifests (backend, frontend, postgres, redis, monitoring)
├── monitoring/                      Docker-compose Prometheus + Grafana provisioning
├── docker-compose.yml               Full local stack: backend, frontend, redis, postgres, prometheus, grafana
├── requirements.txt / .env.example  Root-level dev requirements & sample environment
└── pytest.ini                       testpaths=backend/tests, pythonpath=.
```

---

## 3. Runtime Request Flow

```
Streamlit (frontend/)
     │ HTTP (frontend/services/api_client.py, data_service.py)
     ▼
FastAPI (backend/api/routes/data.py: GET /data/product/{id}, /data/recommendation/{id})
     │
     ├─► cache_manager.get(key)              (backend/cache/manager.py)
     │        │ MISS
     │        ▼
     │   backend_adapter.get_product(id)     (backend/workload/simulated.py or amazon_like.py)
     │        │
     │        ▼
     │   cache_manager.set(key, data) + create_metadata(...)
     │
     ├─► telemetry_collector.record_*(...)   (backend/telemetry/collector.py)
     ├─► Prometheus counters (backend/metrics/prometheus.py, via /metrics scrape)
     └─► _persist_cache_metadata(db, meta)   (backend/database/repositories/cache_metadata.py)

Separately, on demand or on a timer:
FastAPI (backend/api/routes/adaptive.py: GET /adaptive/runtime-decision)
     ▼
AdaptiveService.decide()                     (backend/adaptive/service.py)
     │  1. telemetry_collector.observe()          → Observation
     │  2. build_workload_state / build_system_state (backend/telemetry/state.py)
     │  3. cache_manager.get_all_metadata() → CacheObject contracts
     ▼
DecisionEngine.decide()                       (backend/adaptive/engine/decision_engine.py)
     │  1. FeatureExtractor.extract()              → per-object features
     │  2. WorkloadAnalyzer.analyze()               → WorkloadType
     │  3. AdaptiveScorer.score()                   → retention scores (uses DynamicWeightModel)
     │  4. RefreshPolicy.compute_urgency()          → per-object staleness urgency
     │  5. CapacityController.recommend()           → SCALE_UP / SCALE_DOWN / MAINTAIN
     │  6. EvictionPolicy.select_evictions()        → keys to evict (uses CostModel)
     ▼
Decision (contracts/schemas/decision.py) ── recorded into DecisionHistory (backend/adaptive/history.py)
     ▼
Returned to frontend / Grafana via /adaptive/decisions, /adaptive/runtime-decision
```

---

## 4. `backend/cost/` — Cost Implementation (detailed)

This is the economic layer. It is **platform-aware but platform-agnostic** — it never assumes a specific vendor, only a configurable set of numeric rates.

| File | Contents |
|---|---|
| `backend/cost/cost_profile.py` | `CostProfile` — a frozen dataclass: `name`, `backend_cost_per_request`, `backend_cost_per_ms`, `cache_memory_cost_per_gb_hour`, `metadata`. Fully validated in `__post_init__` (rejects bools, negatives, non-finite values). `CostModelValidationError` is the shared exception type for this whole package. |
| `backend/cost/profiles.py` | Registry of named profiles: `DEFAULT_PROFILE` (generic), `POSTGRESQL_PROFILE`, `MYSQL_PROFILE`, `EXTERNAL_API_PROFILE`. `get_profile(name)` looks one up by name (case-insensitive). All profiles are explicitly documented as *simulated* economic models, not real vendor pricing. |
| `backend/cost/model.py` | `CostModel` — the actual math, all pure functions of a `CostProfile`: |

`CostModel` methods, in the order they matter for the decision pipeline:

1. **`normalize_retrieval_costs(objects)`** — min-max normalizes `retrieval_cost_ms` across the candidate set into `[0, 1]`.
2. **`estimate_backend_cost_saved(object, cached_requests, ...)`** — `saved = cached_requests * (cost_per_request + retrieval_cost_ms * cost_per_ms)`. This is "how much would it have cost to NOT cache this."
3. **`estimate_cache_ram_cost(size_bytes, ...)`** — `(size_bytes / 1e9) * cache_ram_cost_per_gb_hour * hours`. This is "how much does it cost to keep this in RAM."
4. **`estimate_net_benefit(...)`** — `saved - ram_cost`. Positive means retention is economically justified.
5. **`value_density(score, size_bytes, alpha)`** — `score / (size_bytes ** alpha)`. **This is the function actually called during eviction.**

**Where the cost model is consumed (the "angle"):** `backend/adaptive/eviction/policy.py`, inside `EvictionPolicy.select_evictions()`:
- Derives a memory-pressure-scaled size-penalty exponent `alpha` (`_clamp(0.08 + 0.30 * memory_pressure, 0.05, 0.40)`).
- Computes a `cost_boost` per object using `model.normalize_retrieval_costs(objects)`, so objects that are *expensive to regenerate* get an economic boost under high backend-latency pressure.
- Combines the retention `score` (from `AdaptiveScorer`) with `cost_boost` into `retention_value`, then calls `model.value_density(retention_value, effective_size, alpha=alpha)`.
- Sorts all candidates by ascending value density and evicts the lowest-density objects first until enough bytes are freed.

So: **retention score comes from `AdaptiveScorer`; the eviction *ranking* is economic, computed by `CostModel.value_density()` inside `EvictionPolicy`.** `DecisionEngine` wires a shared `CostModel` instance into both itself and its `EvictionPolicy` (see `DecisionEngine.__init__`).

Tests: `backend/tests/adaptive/test_cost_model.py`, `backend/tests/cost/test_cost_profile.py`.

---

## 5. `backend/adaptive/refresh/` — Stale-Cache Management (detailed)

This is the answer to "where is stale cache management implemented": **`backend/adaptive/refresh/policy.py`**, class `RefreshPolicy`.

Important distinction documented at the top of the file itself:
- **Refresh** = the cached *data* may be stale and should be re-fetched from the backend, without necessarily removing it from RAM.
- **Eviction** = RAM is constrained, so *low-value* objects are dropped (handled by `EvictionPolicy`, §4 above — a completely separate concern).

### `RefreshPolicy.compute_urgency(object, now, ...)` → `float` in `[0.0, 1.0]`

This is a continuous (not binary) staleness score, combining six signals:

1. **Temporal staleness** — `age = now - object.last_accessed`; `p_age = 1 - 2^(-age / tau_eff)`. This reaches exactly `0.5` when `age == tau_eff` (an exponential decay curve, not a hard cutoff).
2. **Contextual time constant `tau_eff`** — if live `WorkloadState` telemetry is available, `tau_eff` is *compressed* (objects go stale "faster" in policy terms) as request rate and write ratio increase: `scale = 1 - 0.40 * p_rate * (0.5 + 0.5 * write_ratio)`. Otherwise falls back to `refresh_threshold()`, which halves the base threshold for `SPIKE` / `POPULARITY_SHIFT` workloads.
3. **Access frequency factor** — hot objects get their urgency nudged *up* (keep hot data fresher).
4. **Popularity trend factor** — objects trending upward in access count get proactively refreshed sooner.
5. **Retrieval cost / backend latency factor** — objects that are expensive to regenerate get higher urgency (avoid a costly miss on stale-but-still-cached data), amplified when current backend latency is high.
6. **Memory pressure dampening** — under high cache memory utilization, refresh urgency for *cold* objects is suppressed (don't waste backend bandwidth refreshing things about to be evicted anyway).

All six combine into a bounded multiplier `m_val ∈ [0.20, 3.00]` applied to `p_age`, clamped to `[0, 1]`.

### `RefreshPolicy.should_refresh(...)` → `bool`
Thin wrapper: `compute_urgency(...) >= urgency_threshold` (default `0.50`).

### `RefreshPolicy.refresh_threshold(workload_type, base_threshold_seconds)`
Legacy/static helper: returns `base_threshold_seconds * 0.5` for `SPIKE`/`POPULARITY_SHIFT`, else the base value unchanged. Used as the `tau_eff` fallback when no live `WorkloadState` is passed.

### Where it's invoked in the live pipeline
`backend/adaptive/engine/decision_engine.py`, `DecisionEngine.decide()`, step **"6. Staleness / refresh evaluation"**: loops over every candidate object, calls `RefreshPolicy.compute_urgency(...)`, and collects any key with urgency `>= 0.50` into `refresh_keys`. These are exposed in the final `Decision.metadata["refresh_keys"]`, `["refreshed_count"]`, and `["refresh_urgencies"]` — the API/dashboard never calls a separate "refresh" endpoint; refresh is advisory metadata attached to every decision, describing which cached objects *should* be revalidated.

Tests: `backend/tests/adaptive/test_refresh_policy.py`.

---

## 6. `backend/` — Full Module-by-Module Breakdown

### 6.1 `backend/adaptive/` — Adaptive Intelligence (pure Python, no I/O, no FastAPI/DB dependency)

| Subpackage | File | Class/Function | Role |
|---|---|---|---|
| `capacity/` | `controller.py` | `CapacityController.compute_pressure()` | Composite pressure signal: `0.40·mem_util + 0.25·(mem_util·miss_rate) + 0.20·request_rate_norm + 0.15·latency_norm`, clamped `[0,1]`. |
| | | `CapacityController.recommend()` | Two modes: `"continuous"` (pressure-proportional scaling within tunable `[min%, max%]` bands, thresholds `0.65`/`0.45`) or `"rule_based"` (legacy static thresholds: `HIGH_UTILIZATION_THRESHOLD=0.85`, etc). Returns a `Decision`-shaped capacity recommendation clamped to `[min_capacity_bytes, max_capacity_bytes]`. |
| `engine/` | `decision_engine.py` | `DecisionEngine` | Orchestrator described in §3. Wires `FeatureExtractor`, `WorkloadAnalyzer`, `AdaptiveScorer`, `RefreshPolicy`, `CapacityController`, `EvictionPolicy`, `CostModel` together; validates all inputs strictly (`_validate_inputs`); produces a deterministic `decision_id` via SHA-256 hash when none is supplied. |
| `eviction/` | `policy.py` | `EvictionPolicy` | Value-density-based selector — see §4. |
| `features/` | `extractor.py` | `FeatureExtractor.extract()` | Computes 5 normalized `[0,1]` features per object: `frequency` (access_count/window, min-max normalized), `recency` (`1 - age/window`), `retrieval_cost` (min-max normalized `retrieval_cost_ms`), `size` (min-max normalized `size_bytes`), `popularity_trend` (`0.5 + 0.5·tanh(Δaccess/prev)`). |
| `policies/` | `base.py`, `lru.py`, `lfu.py`, `gds.py` | `BaseEvictionPolicy`, `LRUPolicy`, `LFUPolicy`, `GDSPolicy` | **Baseline comparison policies only** — deterministic, stateless rankers (oldest-`last_accessed`-first, lowest-`access_count`-first, lowest-cost-per-byte-first). Used exclusively by `benchmark/policies.py` to compare against the real adaptive engine. Not reachable from any live API route. |
| | `dynamic_weights.py` | (re-export) | Compatibility shim re-exporting `DynamicWeightModel` from `scoring/dynamic_weights.py`. |
| `refresh/` | `policy.py` | `RefreshPolicy` | Staleness engine — see §5 in full. |
| `scoring/` | `scorer.py` | `AdaptiveScorer.score()` | `score = w_freq·frequency + w_recency·recency + w_cost·retrieval_cost + w_trend·popularity_trend − w_size·size`, clamped `[0,1]`. Weights come from `DynamicWeightModel` unless explicitly overridden. |
| | `dynamic_weights.py` | `DynamicWeightModel.compute_weights()` | Derives feature weights continuously from runtime telemetry/system pressure instead of a static `WorkloadType → weights` lookup table. Base weights: frequency `0.30`, recency `0.25`, retrieval_cost `0.25`, popularity_trend `0.15`, size_penalty `0.05` (sums to `0.95` + `0.05`). |
| `workload/` | `analyzer.py` | `WorkloadAnalyzer.analyze()` | Deterministic rule-based classifier, priority order: `SPIKE` (rate ≥ 1.5× baseline) → `POPULARITY_SHIFT` (shift score ≥ 0.7) → `COMPUTE_HEAVY` (latency ≥ 200ms) → `READ_HEAVY` (hit_rate ≥ 0.80 and miss_rate ≤ 0.20) → `STEADY` (default). |
| (top-level) | `history.py` | `DecisionHistory`, `runtime_decision_history` | Thread-safe bounded `deque` (default `maxlen=50`) of past `Decision`s, newest-first. Singleton instance shared across the app. |
| (top-level) | `service.py` | `AdaptiveService` | **Live-runtime bridge.** Converts internal telemetry dataclasses (`telemetry/state.py`) and `CacheObjectMetadata` into frozen v1 contracts, then calls `DecisionEngine.decide()`. This is what `backend/api/routes/adaptive.py`'s `GET /adaptive/runtime-decision` actually calls — it is purely a translation/orchestration layer and never mutates cache state itself. |

> **Note on `backend/adaptive/workload/` vs `backend/workload/`:** these are two unrelated directories that happen to share a name.
> - `backend/adaptive/workload/` = workload *classification* (`WorkloadAnalyzer`), part of the intelligence core.
> - `backend/workload/` = upstream data *source* adapters and synthetic *scenario generation* for benchmarking (§6.7).

### 6.2 `backend/cache/` — Cache Abstraction

| File | Contents |
|---|---|
| `manager.py` | `CacheStore` (ABC: `get`/`set`/`delete`/`exists`) and `CacheManager` — wraps a `CacheStore` plus an in-process `dict[str, CacheObjectMetadata]` for access-count/hit/miss bookkeeping. Methods: `create_metadata()`, `record_access/hit/miss()`, `record_backend_retrieval()`, `invalidate()`, `get_all_metadata()`. |
| `in_memory.py` | `InMemoryCache(CacheStore)` — plain dict-backed store. Default backend. |
| `redis.py` | `RedisCache(CacheStore)` — JSON-serialized Redis store (used in docker-compose/Kubernetes deployments via `CACHE_BACKEND=redis`). |
| `factory.py` | `get_cache_store(settings)`, `create_cache_manager(settings)` — selects `InMemoryCache` vs `RedisCache` based on `Settings.cache_backend` (env var `CACHE_BACKEND`). |
| `metadata.py` | `CacheObjectMetadata` dataclass (key, size_bytes, retrieval_cost_ms, access/hit/miss counts, timestamps, features, metadata) + `calculate_payload_size_bytes()` (JSON-serialized byte size). |
| `invalidation.py` | `CacheInvalidator` — explicit boundary for invalidating cache entries after a successful DB write (does not invalidate on failed writes). |

### 6.3 `backend/api/` — HTTP Layer

| File | Routes / Contents |
|---|---|
| `routes/data.py` | `GET/DELETE /data/product/{id}`, `GET/DELETE /data/recommendation/{id}`. Owns the module-level `cache_manager` and `backend_adapter` singletons. Cache MISS → `backend_adapter.get_product/get_recommendation()` → `cache_manager.set()` + `create_metadata()` → optional Postgres persistence via `CacheMetadataRepository`. |
| `routes/cache.py` | `GET /cache/objects` (resident objects + metadata), `DELETE /cache/objects/{key}` (invalidate). |
| `routes/telemetry.py` | `GET /telemetry/observation`, `/telemetry/workload`, `/telemetry/system`, `POST /telemetry/window/reset`. |
| `routes/adaptive.py` | `POST /adaptive/decision` (stateless, pass your own objects/workload/system), `GET /adaptive/runtime-decision` (live, calls `AdaptiveService`), `GET /adaptive/decisions` (history). |
| `schemas/*.py` | Pydantic **response** models only (`DecisionHistoryResponse`, `CacheObjectsResponse`, `TelemetryObservationResponse`, etc.) — distinct from the frozen `contracts/schemas/` which are the shared engine-level contracts. |

### 6.4 `backend/app/`

| File | Contents |
|---|---|
| `main.py` | FastAPI app instance, router registration, `/`, `/health`, `/metrics` endpoints, Prometheus middleware. |
| `config.py` | `Settings` (pydantic-settings) — `cache_backend`, `data_backend`, `redis_*`, `database_*`, all overridable via env vars / `.env`. |
| `dependencies.py` | `get_settings()` FastAPI dependency. |

### 6.5 `backend/database/`

| File | Contents |
|---|---|
| `models.py` | SQLAlchemy `Base`, `CacheMetadataModel`, `TelemetryObservationModel`. |
| `connection.py` | `get_database_url()`, `get_engine()`, `get_session_factory()`, `get_db()` (FastAPI dependency), `create_tables()`. Builds a `postgresql+psycopg://` URL from `Settings` unless `DATABASE_URL` is set directly. |
| `repositories/cache_metadata.py` | `CacheMetadataRepository` — persists/reads `CacheObjectMetadata` rows. |
| `repositories/telemetry.py` | `TelemetryRepository` — persists `Observation` snapshots. |

### 6.6 `backend/telemetry/` and `backend/metrics/`

| File | Contents |
|---|---|
| `telemetry/observation.py` | `Observation` — frozen dataclass snapshot (request_rate, hit_rate, miss_rate, backend_latency_ms, window counts). |
| `telemetry/collector.py` | `TelemetryCollector` — the live singleton (`telemetry_collector`) that every route calls into (`record_request`, `record_cache_hit/miss`, `record_backend_call`, `record_key_access`). `observe()` computes rates without resetting; `reset_window()` rotates current→previous window (used for popularity-trend features). |
| `telemetry/state.py` | Internal `WorkloadState`/`SystemState` dataclasses (distinct from, but shape-compatible with, `contracts/schemas`) + `build_workload_state()`, `build_system_state()`. |
| `metrics/prometheus.py` | All `prometheus_client` Counter/Gauge/Histogram definitions (`requests_total`, `cache_hits_total`, `cache_hit_ratio`, `backend_latency_seconds`, `adaptive_decisions_total`, ...) + `sync_from_telemetry()`, called on every `/metrics` scrape to push `TelemetryCollector`/`CacheManager` state into Prometheus gauges. |

### 6.7 `backend/workload/` — Upstream Data Adapters + Synthetic Scenario Generation

This directory has **two unrelated jobs** bundled together for historical reasons:

**(a) Backend/platform adapters** (used by the live `/data/*` routes):
| File | Contents |
|---|---|
| `adapter.py` | `BackendAdapter(ABC)` — `get_product(id)`, `get_recommendation(id)`. |
| `simulated.py` | `SimulatedBackendAdapter` — default, ~30ms/~600ms synthetic latency. |
| `amazon_like.py` | `AmazonLikeAdapter` — alternate synthetic payload/latency profile, proves platform-swap without touching the adaptive layer. **Not a real integration** — no network calls, no vendor SDK. |
| `factory.py` | `get_backend_adapter(settings)` — selects adapter via `Settings.data_backend` (env var `DATA_BACKEND`, values `simulated`/`amazon_like`). |

**(b) Synthetic workload/scenario generation** (used only by `benchmark/` and `demo/`, never by the live API):
| File | Contents |
|---|---|
| `scenario.py` | `WorkloadProfile`, `ScenarioConfig`, `ScenarioEvent` pydantic models; `PRODUCT_CATALOG_PROFILE`, `RECOMMENDATIONS_PROFILE`. |
| `scenarios/base.py` | `BaseScenario(ABC).generate(config, rng) -> list[ScenarioEvent]`. |
| `scenarios/steady.py`, `spike.py`, `popularity_shift.py` | Deterministic RNG-seeded event-stream generators matching `WorkloadType.STEADY/SPIKE/POPULARITY_SHIFT`. |
| `generator.py` | `ScenarioGenerator` — dispatches to the right scenario class by name. |

### 6.8 `backend/tests/`
Mirrors the module tree above 1:1 (`tests/adaptive/`, `tests/api/`, `tests/cache/`, `tests/cost/`, `tests/database/`, `tests/telemetry/`, `tests/workload/`, `tests/integration/`). Run via `pytest` (see `pytest.ini`: `testpaths = backend/tests`, `pythonpath = .`).

---

## 7. `contracts/schemas/` — Frozen v1 Contracts

Shared Pydantic models that every layer (backend routes, `AdaptiveService`, `DecisionEngine`, frontend response shapes) agrees on. Explicitly documented in each file as "frozen v1 — do not change field names, meanings, or add required fields."

| File | Model |
|---|---|
| `cache.py` | `CacheObject` — key, size_bytes, access_count, last_accessed, retrieval_cost_ms, hit_count, miss_count, created_at, features, metadata. |
| `workload.py` | `WorkloadState` — request_rate, hit_rate, miss_rate, backend_latency_ms, workload_type, window_seconds, metrics. |
| `system.py` | `SystemState` — cache_capacity_bytes, cache_usage_bytes, object_count, backend_calls, cache_evictions, window_seconds. |
| `decision.py` | `Decision` — object_scores, eviction_keys, capacity_action, recommended_capacity_bytes, reason, metadata, decision_id, timestamp. |
| `enums.py` | `WorkloadType` (STEADY/READ_HEAVY/COMPUTE_HEAVY/SPIKE/POPULARITY_SHIFT), `CapacityAction` (MAINTAIN/SCALE_UP/SCALE_DOWN). |

These are intentionally generic — no product schema, no vendor field, no platform assumption — which is what allows `backend/workload/`'s adapters to be swapped without touching `backend/adaptive/`.

---

## 8. `frontend/` — Streamlit UI ("AEGIS — Adaptive Cache Control Center")

| Path | Contents |
|---|---|
| `app.py` | Page config, sidebar navigation, imports + `importlib.reload()`s every view module (hot-reload friendly), routes to the selected view. |
| `views/overview_view.py` | Landing dashboard — health check, top-line metrics, donut chart. |
| `views/request_simulator_view.py` | Fires live requests at `/data/product/{id}` and `/data/recommendation/{id}` to demonstrate MISS→HIT. |
| `views/cache_performance_view.py` | Hit/miss ratios, backend-call counts, latency improvement from real telemetry. |
| `views/cache_objects_view.py` | Table/scatter view of resident cache objects + metadata (via `/cache/objects`). |
| `views/adaptive_decisions_view.py` | Shows recent `Decision`s from `/adaptive/decisions` / `/adaptive/runtime-decision`. |
| `views/workload_view.py` | Workload state / classification display. |
| `views/system_view.py` | System capacity/usage state, observation-window reset control. |
| `views/cost_analysis_view.py` | Cost-efficiency visualization — explicitly labeled as simulated economics (no public pricing API). |
| `views/benchmarks_view.py` | LRU/LFU/GDS/Adaptive comparison chart (currently backed by static/mock benchmark numbers in `api_client.get_benchmark_results()`, not a live `benchmark/` run). |
| `components/` | `metric_card.py`, `decision_card.py`, `status_badge.py`, `navbar.py`, `charts.py` (Plotly wrappers), `styles.py` (light/dark theme). |
| `services/api_client.py` | `ApiClient` — central `requests`-based HTTP client to the FastAPI backend; `BACKEND_URL`/`BACKEND_API_URL` env var configurable; graceful fallback to `mocks/data.py` when unreachable. |
| `services/data_service.py` | `fetch_product()`, `fetch_recommendation()` — used by the request simulator, includes an offline synthetic fallback. |
| `services/telemetry_service.py` | Thin wrappers over `/telemetry/*` endpoints. |
| `mocks/data.py` | Static fallback datasets shown when the backend is offline (clearly never presented as live data). |
| `utils/formatting.py` | Number/byte/percentage formatting helpers. |

---

## 9. `benchmark/` — Offline Policy Comparison Engine

Distinct from the live adaptive system — this is a deterministic, in-memory simulation used to *prove* the adaptive engine beats classic policies on identical synthetic traffic.

| File | Contents |
|---|---|
| `cache_simulator.py` | `CacheSimulator` — replays a `ScenarioEvent` stream against one policy, tracking capacity/usage/latency. |
| `policies.py` | `BenchmarkPolicy(ABC)` + adapters wrapping `LRUPolicy`, `LFUPolicy`, `GDSPolicy` (from `backend/adaptive/policies/`) and `DecisionEngine` itself into one uniform interface. |
| `rolling_telemetry.py` | `RollingTelemetry` — sliding-window telemetry so the adaptive policy adapter sees realistic recent-only signal during replay (not lifetime averages). |
| `runner.py` | `BenchmarkRunner` — runs the same event sequence across all policies from isolated starting states. |
| `models.py` | `BenchmarkConfig`, `BenchmarkMetrics`, `BenchmarkResult`, `BenchmarkSuiteResult`. |
| `results.py` | `calculate_percentile()`, result formatting/serialization. |

---

## 10. `demo/` — Standalone CLI Demo

`demo/adaptive_demo.py` imports the adaptive components directly (`CapacityController`, `DecisionEngine`, `EvictionPolicy`, `FeatureExtractor`, `RefreshPolicy`, `AdaptiveScorer`, `WorkloadAnalyzer`, `ScenarioGenerator`) and runs the full pipeline **offline** — no FastAPI, no database, no Docker — for quick manual verification or presentation.

---

## 11. Infrastructure & Deployment

| Path | Contents |
|---|---|
| `docker-compose.yml` | Full local stack: `backend` (FastAPI), `frontend` (Streamlit), `redis`, `postgres`, `prometheus`, `grafana` (with `extra_hosts: host.docker.internal:host-gateway` so Grafana can also reach a Kubernetes Prometheus). |
| `k8s/backend/` | `deployment.yaml` (2 replica default), `hpa.yaml` (CPU-target autoscaling), `service.yaml`, `configmap.yaml`. |
| `k8s/frontend/`, `k8s/postgres/`, `k8s/redis/` | Corresponding manifests for the rest of the stack. |
| `k8s/monitoring/` | `dashboard-configmap.yaml` (the Grafana dashboard JSON, auto-discovered by the kube-prometheus-stack Grafana sidecar via the `grafana_dashboard: '1'` label), `service-monitor.yaml` (scrapes backend `/metrics`). |
| `helm/adaptive-cache/` | Helm-templated equivalent of `k8s/` (`templates/backend-deployment.yaml`, `hpa.yaml`, `servicemonitor.yaml`, etc.), parameterized via `values.yaml`. |
| `monitoring/prometheus.yml` | Docker-compose Prometheus scrape config (scrapes the `backend` container's `/metrics`). |
| `monitoring/grafana/provisioning/datasources/prometheus.yml` | Two datasources: `prometheus` (project's own Prometheus, `uid: prometheus`) and `kubernetes-prometheus` (`uid: kubernetes-prometheus`, reaches the Kind cluster's kube-prometheus-stack via `http://host.docker.internal:9091`). |
| `monitoring/grafana/provisioning/dashboards/adaptive-cache.json` | The single "Adaptive Cache System" dashboard — 21 panels across APPLICATION / CACHE / ADAPTIVE SYSTEM (all on the `prometheus` datasource) and KUBERNETES (4 panels on `kubernetes-prometheus`: pod count, CPU, memory, HPA current/desired). |
| `k6/scenarios/` | Load-test scripts (`steady.js`, `spike.js`, `popularity-shift.js`, `realistic.js`) driving the live backend for demo/HPA-verification purposes. |

See `docs/phase4_grafana_dashboard.md` for the exact dual-datasource wiring and startup sequence, and `docs/phase3_monitoring.md` for the Prometheus/metrics rollout history.

---

## 12. Configuration Reference

All settings are defined in `backend/app/config.py` (`Settings`, pydantic-settings, reads `.env`) and mirrored in `.env.example`:

| Variable | Default | Consumed by |
|---|---|---|
| `CACHE_BACKEND` | `inmemory` | `backend/cache/factory.py` → `inmemory` \| `redis` |
| `DATA_BACKEND` | `simulated` | `backend/workload/factory.py` → `simulated` \| `amazon_like` |
| `REDIS_HOST` / `REDIS_PORT` / `REDIS_DB` / `REDIS_PASSWORD` | `localhost` / `6379` / `0` / `""` | `backend/cache/redis.py` |
| `DATABASE_HOST` / `PORT` / `NAME` / `USER` / `PASSWORD` / `DATABASE_URL` | postgres defaults | `backend/database/connection.py` |
| `BACKEND_URL` / `BACKEND_API_URL` | `http://localhost:8000` | `frontend/services/api_client.py` |

---

## 13. Related Documents

- `docs/adaptive_decision_engine_specification.md` — original design spec for the adaptive engine.
- `docs/cache_consistency_specification.md` — cache/DB consistency guarantees.
- `docs/phase3_monitoring.md` — Prometheus/telemetry rollout notes.
- `docs/phase4_grafana_dashboard.md` — Grafana dashboard architecture, dual-datasource setup, and demo startup sequence.
- `docs/docker.md`, `docs/docker-compose.md` — containerization details.
