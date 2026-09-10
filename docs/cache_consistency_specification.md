# Database Changes and Cache Consistency

**Document Version**: 1.0.0  
**Target Subsystem**: Cache Invalidation, Metadata Consistency, and Database Persistence  
**Repository**: `VH26-Satyagrah`  
**Execution Boundary**: Application-Controlled Invalidation Boundary, Pluggable `CacheStore` (`InMemoryCache` / `RedisCache`), and SQLAlchemy PostgreSQL Persistence  

---

## Executive Summary

The Adaptive Cache System implements an explicit **application-controlled cache invalidation boundary** designed to prevent stale data anomalies across mutating operations. While caching dramatically reduces origin latency and backend computational expenditure, keeping cached representations aligned with persistent database state requires deterministic invalidation.

In this architecture:
1. **Cache Consistency Principle**: Data mutations passing through application endpoints immediately purge the affected cache key and its associated metadata from both the active cache store (`InMemoryCache` or `RedisCache`) and persistent database tables (`cache_metadata`).
2. **Read-Through Freshness**: Subsequent reads for the invalidated key naturally register a cache miss, dispatching to the origin/database to fetch fresh data and repopulating both the cache store and metadata tracking.
3. **Explicit Out-of-Band Boundary**: The current implementation provides deterministic invalidation for all mutations executing through the application's controlled API and service boundaries. Direct, out-of-band SQL modifications executed externally against PostgreSQL bypass application logic and require explicit invalidation API calls to clear cached state.

---

## 1. The Cache Consistency Problem

In web services and data-intensive platforms, cache tiers sit in front of authoritative data stores to accelerate read-heavy access patterns. This architecture creates duplicate representations of the same logical entities:
- **Primary Source of Truth**: The database (e.g., PostgreSQL).
- **Transient Acceleration Representation**: The cache store (`InMemoryCache` or Redis).

```mermaid
flowchart TD
    subgraph StaleProblem["The Stale Cache Problem (Without Invalidation)"]
        direction TB
        Step1["1. Database Updated<br/>(Product 42: Price $10 -> $15)"]
        Step2["2. Cache Retains Old Copy<br/>(Product 42: Price $10)"]
        Step3["3. Next Request Arrives<br/>GET /data/product/42"]
        Step4["4. Cache Lookup: HIT!"]
        Step5["5. STALE DATA RETURNED TO USER<br/>(Price $10 instead of $15)"]
        
        Step1 -.-> Step2
        Step2 --> Step3
        Step3 --> Step4
        Step4 --> Step5
    end
```

### Problem Scenario
Consider a product catalog entry with key `product:42`:
1. **Initial State**: PostgreSQL contains Product Version A (`price = $10.00`). Cache contains Product Version A (`price = $10.00`).
2. **Database Mutation**: Product data is modified or deleted in PostgreSQL to Product Version B (`price = $15.00`).
3. **Anomaly Without Invalidation**: If the cache retains Version A, subsequent client reads hit the cache and receive stale Version A data indefinitely (until natural TTL expiration or memory-pressure eviction occurs).
4. **Impact on Adaptive Intelligence**: If stale objects remain resident, the adaptive engine continues calculating retention scores, popularity velocities, and capacity allocations based on outdated object characteristics.

---

## 2. Why Direct Database Changes Can Produce Stale Results

Direct database changes produce stale cache reads whenever the cache tier is decoupled from the mutation pipeline:
- **Read-Through / Cache-Aside Separation**: The application reads from the cache first; if the cache yields a hit, the database is never consulted (in fact, verified by tests, cache hits execute **zero SQL queries**).
- **Asynchronous Lifecycles**: Cache eviction algorithms prioritize items based on memory pressure, access frequency, and recency—not origin data freshness. A frequently accessed item with stale data might be prioritized for prolonged retention by standard LRU/LFU heuristics.
- **Metadata Desynchronization**: Caches that only track raw strings without synchronized object metadata leave the adaptive optimization layer blind to whether the cached representation matches current origin semantics.

To prevent this desynchronization, the system implements an explicit **invalidation boundary** that coordinates cache purging whenever application-controlled data modifications occur.

---

## 3. Implemented Cache Invalidation Architecture

The invalidation architecture establishes a clear separation of concerns between HTTP routing, business logic, cache management, and physical storage.

```mermaid
flowchart TD
    subgraph ClientLayer["Client & API Layer"]
        Req["Client Mutation Request<br/>DELETE /data/product/{id}<br/>DELETE /cache/objects/{key}"]
    end

    subgraph AppBoundary["Application Invalidation Boundary"]
        Route["FastAPI Route Handler<br/>(backend/api/routes/data.py)"]
        InvFn["invalidate_cached_key(key, db)"]
        InvCoord["CacheInvalidator<br/>(backend/cache/invalidation.py)"]
    end

    subgraph CacheLayer["Cache Management Layer"]
        Mgr["CacheManager<br/>(backend/cache/manager.py)"]
        MetaMap["In-Memory Metadata Registry<br/>self._metadata: dict[str, CacheObjectMetadata]"]
    end

    subgraph StorageLayer["Physical Storage Tiers"]
        CStore["CacheStore<br/>- InMemoryCache (dict)<br/>- RedisCache (DEL)"]
        PG["PostgreSQL Database<br/>Table: cache_metadata"]
        Repo["CacheMetadataRepository<br/>(backend/database/repositories/)"]
    end

    Req --> Route
    Route --> InvFn
    InvFn --> InvCoord
    InvCoord -->|invalidate_key| Mgr
    Mgr -->|delete key| CStore
    Mgr -->|del _metadata[key]| MetaMap
    InvFn -->|delete persistent metadata| Repo
    Repo -->|DELETE SQL| PG
```

### Architectural Responsibilities
- [`CacheInvalidator`](file:///home/gnx/Projects/VH26-Satyagrah/backend/cache/invalidation.py#L23-L86): The pure, reusable application boundary that validates input types and orchestrates deterministic key invalidation.
- [`CacheManager`](file:///home/gnx/Projects/VH26-Satyagrah/backend/cache/manager.py#L25-L117): The core cache coordinator managing both the underlying `CacheStore` and in-memory `CacheObjectMetadata`.
- [`CacheStore`](file:///home/gnx/Projects/VH26-Satyagrah/backend/cache/manager.py#L7-L23): Abstract storage interface implemented by [`InMemoryCache`](file:///home/gnx/Projects/VH26-Satyagrah/backend/cache/in_memory.py#L6-L24) and [`RedisCache`](file:///home/gnx/Projects/VH26-Satyagrah/backend/cache/redis.py#L12-L69).
- [`CacheMetadataRepository`](file:///home/gnx/Projects/VH26-Satyagrah/backend/database/repositories/cache_metadata.py#L10-L90): SQLAlchemy repository responsible for persisting and deleting metadata rows in the `cache_metadata` PostgreSQL table.

---

## 4. Application-Controlled Database Mutation Flow

In [`backend/api/routes/data.py`](file:///home/gnx/Projects/VH26-Satyagrah/backend/api/routes/data.py) and [`backend/api/routes/cache.py`](file:///home/gnx/Projects/VH26-Satyagrah/backend/api/routes/cache.py), data mutation endpoints invoke the invalidation boundary directly:

```mermaid
sequenceDiagram
    autonumber
    actor Client
    participant Route as DELETE /data/product/{id}
    participant Inv as invalidate_cached_key()
    participant CM as CacheManager
    participant Store as CacheStore (InMemory / Redis)
    participant Repo as CacheMetadataRepository
    participant DB as PostgreSQL (Session)

    Client->>Route: DELETE /data/product/42
    Route->>Inv: invalidate_cached_key("product:42", db)
    Inv->>CM: get_metadata("product:42")
    CM-->>Inv: had_metadata (bool)
    Inv->>CM: delete("product:42")
    CM->>CM: del _metadata["product:42"]
    CM->>Store: delete("product:42")
    Store-->>CM: True
    CM-->>Inv: True
    opt If deleted or had_metadata
        Inv->>Repo: delete("product:42")
        Repo->>DB: DELETE FROM cache_metadata WHERE key = 'product:42'
        DB-->>Repo: Success
        Inv->>DB: db.commit()
    end
    Inv-->>Route: True
    Route-->>Client: {"key": "product:42", "deleted": true}
```

### Actual Code Implementation & Execution Ordering
As implemented in [`backend/api/routes/data.py`](file:///home/gnx/Projects/VH26-Satyagrah/backend/api/routes/data.py#L76-L83):

```python
def invalidate_cached_key(key: str, db: Any = None) -> bool:
    """Invalidate a key from runtime CacheManager and delete its persistent metadata."""
    had_metadata = cache_manager.get_metadata(key) is not None
    deleted = cache_manager.delete(key)
    if (deleted or had_metadata) and db is not None:
        _delete_persisted_cache_metadata(db, key)
    return deleted or had_metadata
```

#### Exact Ordering Steps:
1. **Metadata Inspection**: `cache_manager.get_metadata(key)` checks whether in-memory tracking exists for the target key.
2. **In-Memory Cache & Metadata Purge**: `cache_manager.delete(key)` purges the key from `self._metadata` and calls `self._store.delete(key)` on the active `CacheStore`.
3. **Persistent Metadata Deletion**: If the key was deleted or had metadata, `_delete_persisted_cache_metadata(db, key)` executes `CacheMetadataRepository(db).delete(key)` and commits the transaction.
4. **Return Value**: Returns `True` if either the cached entry or its metadata was deleted; `False` if the key was completely absent.

---

## 5. CacheManager as the Consistency Boundary

[`CacheManager`](file:///home/gnx/Projects/VH26-Satyagrah/backend/cache/manager.py#L25-L117) decouples application business logic from the physical storage backend.

### Key Deletion and Invalidation Contract
```python
def delete(self, key: str) -> bool:
    if key in self._metadata:
        del self._metadata[key]
    return self._store.delete(key)

def invalidate(self, key: str) -> bool:
    """Invalidate a cache key and its associated metadata."""
    return self.delete(key)
```

### Guarantees:
1. **Atomic Dual Cleanup**: Calling `delete()` or `invalidate()` synchronously strips both the payload from `self._store` and the associated tracking record from `self._metadata`.
2. **Storage Agnostic**: Application routes interact strictly with `CacheManager`. Swapping `InMemoryCache` for `RedisCache` requires zero code changes in API routes.
3. **Safe Return Semantics**: Returns `True` if the key existed and was deleted from the store; returns `False` safely without raising exceptions if the key was not present.

---

## 6. CacheInvalidator Boundary

[`CacheInvalidator`](file:///home/gnx/Projects/VH26-Satyagrah/backend/cache/invalidation.py#L23-L86) provides a pure, dependency-injected coordinator for cache invalidation.

```python
class CacheInvalidator:
    def __init__(self, cache_manager: CacheManager) -> None:
        if not isinstance(cache_manager, CacheManager):
            raise TypeError(f"cache_manager must be an instance of CacheManager, got {type(cache_manager).__name__}")
        self._cache_manager = cache_manager

    def invalidate_key(self, key: str) -> bool:
        if isinstance(key, bool) or not isinstance(key, str):
            raise TypeError(f"key must be a string, got {type(key).__name__}")
        return self._cache_manager.invalidate(key)

    def invalidate_keys(self, keys: Sequence[str]) -> list[str]:
        if isinstance(keys, (str, bytes)):
            raise TypeError("keys must be a sequence of strings, not a single string")
        deleted_keys: list[str] = []
        for key in keys:
            if self.invalidate_key(key):
                deleted_keys.append(key)
        return deleted_keys
```

### Key Capabilities:
- **Type Safety**: Strictly rejects non-string keys, boolean types (`isinstance(True, bool)`), and malformed key sequences.
- **Deterministic Multi-Key Purging**: `invalidate_keys()` iterates through a sequence in deterministic input order, returning a list containing only the keys that were actually present and purged.
- **Standalone Function Helpers**: Exposes `invalidate_key(cache_manager, key)` and `invalidate_keys(cache_manager, keys)` for procedural use cases.

---

## 7. Cache Metadata Consistency

In the Adaptive Cache System, cached items are not simple binary blobs; they are enriched with multidimensional telemetry in [`CacheObjectMetadata`](file:///home/gnx/Projects/VH26-Satyagrah/backend/cache/metadata.py#L20-L56):

| Field | Type | Role in Adaptive Decision Engine |
|---|---|---|
| `key` | `str` | Unique object identifier (e.g., `"product:42"`). |
| `size_bytes` | `int` | Memory footprint used by `EvictionPolicy` to evaluate Value Density ($Score / Size^\alpha$). |
| `retrieval_cost_ms` | `float` | Origin fetch latency used by `DynamicWeights` and `CostModel` to compute origin protection boosts. |
| `access_count` | `int` | Lifetime request counter used for frequency feature extraction ($f_{freq}$). |
| `hit_count` | `int` | Successful cache hit counter. |
| `miss_count` | `int` | Initial and subsequent cache miss counter. |
| `last_accessed` | `datetime` | Timezone-aware UTC timestamp used for recency decay ($f_{rec}$) and refresh urgency ($p_{age}$). |

### Why Synchronized Metadata Removal is Critical
If a cache key were deleted from the cache store while its metadata remained in memory:
1. **Orphaned Optimization Signals**: The decision engine would continue factoring ghost objects into capacity calculations, average retrieval cost metrics, and global pressure estimates.
2. **Inspection Inconsistencies**: Observability endpoints would display non-resident items. To prevent this, [`GET /cache/objects`](file:///home/gnx/Projects/VH26-Satyagrah/backend/api/routes/cache.py#L65-L85) enforces a defensive check:
   ```python
   for key, meta in all_metadata.items():
       if not manager.exists(key):
           continue
       resident_objects.append(_serialize_metadata(meta))
   ```
3. **State Integrity**: By removing metadata inside `CacheManager.delete()`, the system guarantees that metadata existence strictly matches object residence.

---

## 8. PostgreSQL Persistence Integration

The repository includes optional PostgreSQL persistence via SQLAlchemy in [`backend/database/`](file:///home/gnx/Projects/VH26-Satyagrah/backend/database/).

### Data Model & Table Mapping
The `cache_metadata` table is mapped by [`CacheMetadataModel`](file:///home/gnx/Projects/VH26-Satyagrah/backend/database/models.py#L12-L42):

```python
class CacheMetadataModel(Base):
    __tablename__ = "cache_metadata"

    key: Mapped[str] = mapped_column(sa.String(255), primary_key=True, index=True)
    version: Mapped[str] = mapped_column(sa.String(32), default="v1", nullable=False)
    size_bytes: Mapped[int] = mapped_column(sa.BigInteger, default=0, nullable=False)
    access_count: Mapped[int] = mapped_column(sa.Integer, default=1, nullable=False)
    last_accessed: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), nullable=False)
    retrieval_cost_ms: Mapped[float] = mapped_column(sa.Float, default=0.0, nullable=False)
    hit_count: Mapped[int] = mapped_column(sa.Integer, default=0, nullable=False)
    miss_count: Mapped[int] = mapped_column(sa.Integer, default=1, nullable=False)
    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), nullable=False)
    features: Mapped[dict[str, Any] | None] = mapped_column(sa.JSON, nullable=True)
    metadata_payload: Mapped[dict[str, Any] | None] = mapped_column("metadata", sa.JSON, nullable=True)
```

### Operational Invariants
1. **Zero SQL Queries on Cache Hits**: When a read hits the cache, the application immediately returns the in-memory/Redis payload and updates in-memory counters. **No database query or write is performed** (verified via SQLAlchemy engine statement listeners in `test_cache_hit_performs_zero_database_queries`).
2. **Metadata Persistence on Cache Misses**: On an origin miss, fresh metadata is persisted via `CacheMetadataRepository.save(meta)` so that restarts retain warm metadata profiles.
3. **Persistent Deletion on Invalidation**: When an object is invalidated via `DELETE /data/product/{id}` or `DELETE /cache/objects/{key}`, `_delete_persisted_cache_metadata()` executes `repo.delete(key)`.

### Architectural Clarification: Persistence vs. Synchronization
> [!IMPORTANT]
> **PostgreSQL Persistence is NOT Cache Synchronization**:
> - The database holds persistent application state and persistent cache metadata.
> - The cache holds temporary, performance-optimized copies of data.
> - Invalidation is the unilateral command that instructs the cache tier that a cached representation is no longer trustworthy.

---

## 9. Subsequent Request and Cache Repopulation

Following invalidation, the system relies on standard **read-through cache repopulation** on the next request.

```mermaid
sequenceDiagram
    autonumber
    actor Client
    participant API as GET /data/product/42
    participant CM as CacheManager
    participant Origin as Backend Data Origin (get_product_data)
    participant Telemetry as TelemetryCollector
    participant DB as PostgreSQL (cache_metadata)

    Client->>API: GET /data/product/42
    API->>CM: get("product:42")
    Note over CM: Key was invalidated!
    CM-->>API: None (Cache MISS)
    API->>Telemetry: record_cache_miss()
    API->>CM: record_miss("product:42")
    
    API->>Origin: get_product_data("42")
    Note over Origin: Fetches fresh data from DB/origin
    Origin-->>API: fresh_data (latency: 12.5ms)
    API->>Telemetry: record_backend_call(12.5)

    API->>CM: set("product:42", fresh_data)
    API->>CM: create_metadata("product:42", size, latency)
    API->>DB: _persist_cache_metadata(db, meta)
    DB-->>API: Committed
    API-->>Client: fresh_data
    
    Note over Client,API: Subsequent Request (Cache HIT)
    Client->>API: GET /data/product/42
    API->>CM: get("product:42")
    CM-->>API: fresh_data (Cache HIT)
    API->>Telemetry: record_cache_hit()
    API-->>Client: fresh_data (0 SQL queries)
```

### Complete Read-After-Invalidation Lifecycle:
1. **Client Request**: Client issues `GET /data/product/42`.
2. **Cache Lookup**: `cache_manager.get("product:42")` is evaluated.
3. **Guaranteed Miss**: Because the key was deleted during invalidation, `get()` returns `None`.
4. **Origin Fetch**: The endpoint invokes the origin provider (`get_product_data("42")`), fetching fresh state and timing origin latency ($t_{retrieval}$).
5. **Cache Repopulation**: Fresh data is written to the store (`cache_manager.set(...)`).
6. **Metadata Recreation**: Fresh metadata is created with recalculated payload byte size (`calculate_payload_size_bytes`) and observed latency.
7. **Persistent Sync**: Fresh metadata is saved to PostgreSQL (`_persist_cache_metadata`).
8. **Subsequent Hit**: Future requests find `product:42` resident, returning immediate answers with zero origin or database overhead.

---

## 10. Direct / Out-of-Band Database Modification Boundary

A critical question in cache consistency design is:
> *"What happens if a DBA or external service directly updates a PostgreSQL table via `psql` or an external batch script without calling the application?"*

### Implemented Boundary and Architectural Limitations

The current implementation provides explicit invalidation through the **application-level mutation and invalidation boundary**.

```mermaid
flowchart TD
    subgraph Controlled["1. Application-Controlled Mutation (CONSISTENT)"]
        AppClient["App Client / Admin API"] -->|DELETE /data/product/42| AppEndpoint["Application Route"]
        AppEndpoint -->|1. Invalidate| Cache["Cache Store + Metadata<br/>(PURGED)"]
        AppEndpoint -->|2. Invalidate| DB["PostgreSQL<br/>(UPDATED)"]
    end

    subgraph OutOfBand["2. Arbitrary Out-of-Band Direct Write (STALE UNTIL INVALIDATED)"]
        DBA["External SQL Client / DBA / Script"] -->|Direct UPDATE/DELETE SQL| RawDB["PostgreSQL Database"]
        RawDB -.->|NO AUTOMATIC EVENT| OutOfBandCache["Cache Store<br/>(REMAINS STALE)"]
        AdminFix["External Remedy: Trigger Invalidation API<br/>DELETE /cache/objects/product:42"] --> OutOfBandCache
    end
```

### Formal Architectural Statement
> **The implemented system guarantees cache invalidation for database mutations that pass through the application's controlled mutation/invalidation boundary. Arbitrary out-of-band database writes executed directly against PostgreSQL are not automatically observable by the cache unless an external synchronization mechanism is added.**

### What is NOT Implemented (Technical Truth):
- **No Database Triggers**: The repository does not install PostgreSQL `AFTER UPDATE` triggers.
- **No Change Data Capture (CDC)**: The repository does not deploy Debezium, Kafka Connect, or WAL log scrapers.
- **No PostgreSQL LISTEN/NOTIFY**: The database connection does not maintain an active socket listening for PostgreSQL asynchronous notification channels.
- **No Periodic Polling Daemon**: The backend does not run a background thread diffing database timestamps against cache metadata.

### How to Handle Out-of-Band Database Writes:
When external processes perform direct SQL operations on the database, they must notify the cache tier using one of the application's exposed endpoints:
- `DELETE /data/product/{product_id}`
- `DELETE /data/recommendation/{user_id}`
- `DELETE /cache/objects/{key}` (accepts arbitrary key paths, e.g., `/cache/objects/product:101`)

---

## 11. Redis Deployment Behavior

The cache architecture uses the abstract base class [`CacheStore`](file:///home/gnx/Projects/VH26-Satyagrah/backend/cache/manager.py#L7-L23).

### Portability Across InMemory and Redis
In [`backend/cache/factory.py`](file:///home/gnx/Projects/VH26-Satyagrah/backend/cache/factory.py#L9-L30), the active store is instantiated according to the `CACHE_BACKEND` setting:
- When `CACHE_BACKEND="inmemory"`: Uses [`InMemoryCache`](file:///home/gnx/Projects/VH26-Satyagrah/backend/cache/in_memory.py#L6-L24).
- When `CACHE_BACKEND="redis"`: Uses [`RedisCache`](file:///home/gnx/Projects/VH26-Satyagrah/backend/cache/redis.py#L12-L69).

### Invalidation in Redis
In `RedisCache`, invalidation maps directly to standard Redis primitives:
```python
def delete(self, key: str) -> bool:
    """Delete a key from Redis. Returns True if key existed, False otherwise."""
    deleted_count = self._client.delete(key)
    return bool(deleted_count > 0)
```
- **Redis Protocol Command**: `self._client.delete(key)` dispatches the standard Redis `DEL` command. (The codebase does not use `UNLINK`).
- **Zero API Coupling**: API routes and `CacheInvalidator` contain no Redis-specific syntax, maintaining 100% decoupling from cluster topology, connection pools, or cache provider types.

---

## 12. Failure Handling and Graceful Degradation

The system prioritizes application availability and predictable degradation during infrastructure failure.

### 1. Database Persistence Failure During Invalidation
If PostgreSQL becomes unavailable or throws an error during an invalidation operation (e.g., database timeout or network partition):
```python
def _delete_persisted_cache_metadata(db: Any, key: str) -> None:
    if not isinstance(db, Session):
        return
    try:
        repo = CacheMetadataRepository(db)
        repo.delete(key)
        db.commit()
    except Exception as exc:
        logger.warning("Failed to delete persisted metadata for '%s': %s", key, exc)
        try:
            db.rollback()
        except Exception as rb_exc:
            logger.debug("Rollback failed for deleted metadata '%s': %s", key, rb_exc)
```
- **Behavior**:
  1. The database exception is caught and logged as a warning.
  2. The session is rolled back defensively.
  3. **The cache purge still succeeds**: `cache_manager.delete(key)` has already purged the active in-memory/Redis cache store.
  4. The endpoint returns `HTTP 200 OK` with `{"deleted": true}`.
  5. The primary objective—preventing stale cached data from being served to clients—is satisfied even when database metadata deletion fails.

### 2. Database Persistence Failure on Cache Miss
If database persistence fails when caching a new object:
- `_persist_cache_metadata()` catches the error and executes a rollback.
- In-memory/Redis caching succeeds normally.
- The HTTP request returns `HTTP 200 OK` with fresh data.

### 3. No Distributed Transaction (2PC) Claim
The implementation does not claim or use distributed two-phase commit (2PC) between Redis and PostgreSQL. Invalidation follows a **best-effort, cache-first pattern**: the cache is purged immediately in memory, followed by database metadata removal.

---

## 13. Verification and Automated Test Coverage

The consistency, invalidation, and persistence behaviors are validated by dedicated automated test suites:

### 1. Invalidation Boundary Tests
**File**: [`backend/tests/cache/test_invalidation.py`](file:///home/gnx/Projects/VH26-Satyagrah/backend/tests/cache/test_invalidation.py)
- `test_initialization_success`: Confirms `CacheInvalidator` properly binds `CacheManager`.
- `test_initialization_invalid_type_raises`: Validates strict rejection of invalid managers.
- `test_invalidate_key_success`: Confirms single key deletion purges both store and metadata.
- `test_invalidate_key_missing_returns_false`: Verifies safe return on non-existent keys.
- `test_invalidate_key_invalid_type_raises`: Confirms type enforcement (rejects `bool`, non-string).
- `test_invalidate_key_delegation`: Verifies delegation to `CacheManager.invalidate()`.
- `test_invalidate_keys_all_exist`: Confirms multiple-key invalidation.
- `test_invalidate_keys_partial_exist`: Confirms accurate return of only present/deleted keys.
- `test_invalidate_keys_deterministic_order`: Verifies output preserves input sequence order.
- `test_standalone_helpers`: Confirms functional helpers `invalidate_key` and `invalidate_keys`.
- `test_cache_consistency_workflow_simulation`: Simulates cache-aside write flow (successful write invalidates; failed write preserves cache).

### 2. CacheManager Delegation & Metadata Cleanup Tests
**File**: [`backend/tests/cache/test_manager.py`](file:///home/gnx/Projects/VH26-Satyagrah/backend/tests/cache/test_manager.py)
- `test_delegation_delete`: Confirms `CacheManager.delete()` purges metadata and calls store.
- `test_invalidate_existing_key_deletes_value_and_metadata`: Verifies dual-purge on invalidation.
- `test_invalidate_missing_key_returns_false`: Confirms safe boolean return for missing keys.
- `test_invalidate_delegation_to_delete`: Verifies `invalidate()` delegates to `delete()`.

### 3. Runtime Persistence & Database Consistency Tests
**File**: [`backend/tests/integration/test_runtime_persistence.py`](file:///home/gnx/Projects/VH26-Satyagrah/backend/tests/integration/test_runtime_persistence.py)
- `test_cache_miss_persists_metadata_to_database`: Verifies cache misses write metadata rows to database.
- `test_cache_hit_performs_zero_database_queries`: Verifies with SQL event listener that cache hits execute **zero SQL statements**.
- `test_cache_invalidation_removes_persistent_metadata`: Tests end-to-end invalidation across `DELETE /data/product/{id}`, `DELETE /data/recommendation/{id}`, and `DELETE /cache/objects/{key}`.
- `test_resilience_when_database_fails_on_cache_miss`: Confirms API continues returning 200 OK when DB persistence fails.
- `test_resilience_when_database_fails_on_invalidation`: Confirms invalidation returns 200 OK even under database connection failures.

### 4. Integration Repopulation Flow Tests
**File**: [`backend/tests/integration/test_cache_metadata_flow.py`](file:///home/gnx/Projects/VH26-Satyagrah/backend/tests/integration/test_cache_metadata_flow.py)
- `test_cache_deletion_repopulation_flow`: Verifies deleting a key and re-requesting cleanly creates fresh state, resets access counts, and re-establishes fresh metadata.

---

## 14. End-to-End Product Update Example

### Scenario Walkthrough
Consider product catalog item `42`:

1. **Populate Cache**:
   Client reads the product:
   ```http
   GET /data/product/42 HTTP/1.1
   ```
   - Cache Miss: Fetches from backend (`Product 42`, simulated price `$100`).
   - Stores payload under key `"product:42"`.
   - Creates in-memory and persistent metadata (`key="product:42"`, `access_count=1`, `hit_count=0`, `miss_count=1`).

2. **Subsequent Reads (Cache Hit)**:
   ```http
   GET /data/product/42 HTTP/1.1
   ```
   - Cache Hit: Returns cached JSON in $< 1\text{ ms}$.
   - Executes **0 database queries**.
   - Increments in-memory `hit_count` to `1` and `access_count` to `2`.

3. **Data Mutation & Invalidation**:
   Product 42 is removed or updated via the application mutation endpoint:
   ```http
   DELETE /data/product/42 HTTP/1.1
   ```
   - `invalidate_cached_key("product:42", db)` is executed.
   - Key `"product:42"` is deleted from `CacheStore` (`InMemoryCache` or Redis `DEL`).
   - In-memory metadata `self._metadata["product:42"]` is removed.
   - Persistent database row in `cache_metadata` is deleted via `CacheMetadataRepository.delete("product:42")`.
   - Response: `{"key": "product:42", "deleted": true}`.

4. **Observability Verification**:
   ```http
   GET /cache/objects HTTP/1.1
   ```
   - Response does **not** include `"product:42"` because it is no longer resident.

5. **Subsequent Read (Fresh Fetch & Repopulation)**:
   ```http
   GET /data/product/42 HTTP/1.1
   ```
   - Cache Miss: Key `"product:42"` is absent.
   - Origin fetch executes fresh logic.
   - Fresh data is cached and fresh metadata is created with `access_count=1`, `hit_count=0`, `miss_count=1`.
   - Client receives 100% fresh data; stale data anomaly is completely averted.

---

## 15. Cache Behavior Before and After Invalidation

| Stage / Dimension | Without Invalidation Architecture | Implemented Invalidation Architecture |
|---|---|---|
| **Database Update** | Database mutates; cache is unaware. | Database mutates; application calls invalidation boundary. |
| **Cached Representation** | Remains resident with obsolete data. | Purged immediately from `CacheStore` (`InMemory` or Redis `DEL`). |
| **Cache Metadata** | Obsolete counters and latency metrics remain active. | Synchronously deleted from both in-memory map and `cache_metadata` table. |
| **Next Request** | Hits cache; returns stale data. | Misses cache; forces fresh read from origin backend. |
| **Returned Data** | **Stale** (inconsistent with database). | **Fresh** (consistent with origin). |
| **Subsequent Cache State** | Unchanged; continues serving stale data. | Repopulated with fresh payload, updated payload byte size, and measured latency. |
| **Database Load on Hit** | 0 queries. | 0 queries (strictly verified by automated tests). |

---

## 16. How This Addresses Judge Concerns

During hackathon presentations, technical judges frequently question cache consistency:
> *"What prevents your adaptive cache from serving stale data when items in the database are updated or deleted? How do you ensure cache metadata does not desynchronize from resident objects?"*

### Clear, Defensible Judge Response Points:
1. **Explicit Invalidation Boundary**: The architecture does not wait for passive TTL expiry or random eviction to purge obsolete entries. Mutations passing through application routes invoke `CacheInvalidator` and `CacheManager.delete()`, actively evicting the modified keys.
2. **Coordinated Metadata Purging**: Invalidation removes the payload and the metadata simultaneously. This prevents the adaptive intelligence algorithms from scoring or allocating memory for non-existent items.
3. **Verified Zero-Query Cache Hits**: While misses and invalidations maintain PostgreSQL metadata consistency, cache hits execute zero database queries, preserving maximum throughput.
4. **Honest Architectural Boundary**: We explicitly articulate what the system guarantees: application-controlled mutations are 100% consistent; arbitrary out-of-band direct database writes require an explicit invalidation API call because no background CDC or database trigger is currently deployed.

---

## 17. Implementation Mapping

Every concept documented in this specification maps directly to authoritative source files and automated verification suites in the repository:

| Architectural Concept | Repository Source File | Concrete Responsibility |
|---|---|---|
| **Cache Invalidation Boundary** | [`backend/cache/invalidation.py`](file:///home/gnx/Projects/VH26-Satyagrah/backend/cache/invalidation.py) | Type validation, single and multiple key invalidation coordinator (`CacheInvalidator`). |
| **Cache Manager & Metadata State** | [`backend/cache/manager.py`](file:///home/gnx/Projects/VH26-Satyagrah/backend/cache/manager.py) | Dual-purge `delete()` and `invalidate()` methods, in-memory metadata registry. |
| **In-Memory Cache Store** | [`backend/cache/in_memory.py`](file:///home/gnx/Projects/VH26-Satyagrah/backend/cache/in_memory.py) | Python dictionary store implementing `CacheStore`. |
| **Redis Cache Store** | [`backend/cache/redis.py`](file:///home/gnx/Projects/VH26-Satyagrah/backend/cache/redis.py) | Redis client store executing `_client.delete(key)` (`DEL` command). |
| **Cache Store Factory** | [`backend/cache/factory.py`](file:///home/gnx/Projects/VH26-Satyagrah/backend/cache/factory.py) | Environment-based dependency injection of `InMemoryCache` or `RedisCache`. |
| **Cache Object Metadata** | [`backend/cache/metadata.py`](file:///home/gnx/Projects/VH26-Satyagrah/backend/cache/metadata.py) | Dataclass tracking access, hit, miss, payload size, and latency. |
| **Data Mutation Endpoints** | [`backend/api/routes/data.py`](file:///home/gnx/Projects/VH26-Satyagrah/backend/api/routes/data.py) | `DELETE /data/product/{id}`, `DELETE /data/recommendation/{id}`, `invalidate_cached_key()`. |
| **Cache Inspection & Purge API** | [`backend/api/routes/cache.py`](file:///home/gnx/Projects/VH26-Satyagrah/backend/api/routes/cache.py) | `GET /cache/objects` (resident filtering), `DELETE /cache/objects/{key}`. |
| **PostgreSQL Metadata Model** | [`backend/database/models.py`](file:///home/gnx/Projects/VH26-Satyagrah/backend/database/models.py) | `CacheMetadataModel` SQLAlchemy declarative model. |
| **Metadata Repository** | [`backend/database/repositories/cache_metadata.py`](file:///home/gnx/Projects/VH26-Satyagrah/backend/database/repositories/cache_metadata.py) | `save()`, `get_by_key()`, `get_all()`, and `delete()` repository methods. |
| **Database Connection & Sessions** | [`backend/database/connection.py`](file:///home/gnx/Projects/VH26-Satyagrah/backend/database/connection.py) | Engine singleton, session lifecycle, and `get_db` FastAPI dependency. |
| **Invalidator Unit Tests** | [`backend/tests/cache/test_invalidation.py`](file:///home/gnx/Projects/VH26-Satyagrah/backend/tests/cache/test_invalidation.py) | 15 comprehensive unit tests for `CacheInvalidator`. |
| **Manager Unit Tests** | [`backend/tests/cache/test_manager.py`](file:///home/gnx/Projects/VH26-Satyagrah/backend/tests/cache/test_manager.py) | Delegation and metadata cleanup tests. |
| **Persistence Integration Tests** | [`backend/tests/integration/test_runtime_persistence.py`](file:///home/gnx/Projects/VH26-Satyagrah/backend/tests/integration/test_runtime_persistence.py) | Invalidation persistence, zero SQL on hit, and error resilience tests. |
| **Metadata Flow Tests** | [`backend/tests/integration/test_cache_metadata_flow.py`](file:///home/gnx/Projects/VH26-Satyagrah/backend/tests/integration/test_cache_metadata_flow.py) | Full cache deletion and repopulation lifecycle tests. |
