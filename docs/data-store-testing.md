# Adaptive Cache System — Data Store Inspection & Testing Guide

This guide provides technical instructions for inspecting, verifying, and testing the physical data stores (**Redis 7** and **PostgreSQL 16**) running inside their Kubernetes pods. It details step-by-step procedures to validate cache hits, cache misses, metadata updates, persistence synchronization, and Prometheus metrics.

---

## 1. Identify Redis and PostgreSQL Pods

To execute inspection commands inside Kubernetes, identify the active pod names via their selector labels:

```bash
# Identify the Redis pod
kubectl get pods -l app=redis -o wide

# Identify the PostgreSQL pod
kubectl get pods -l app=postgres -o wide

# Export pod names into environment variables for convenient CLI access
export REDIS_POD=$(kubectl get pods -l app=redis -o jsonpath="{.items[0].metadata.name}")
export POSTGRES_POD=$(kubectl get pods -l app=postgres -o jsonpath="{.items[0].metadata.name}")

echo "Redis Pod:      $REDIS_POD"
echo "PostgreSQL Pod: $POSTGRES_POD"
```

*Expected Pod Name Patterns:*
- Redis: `redis-xxxxxxxxxx-xxxxx` (e.g., `redis-574db8ffc-x9w2k`)
- PostgreSQL: `postgres-xxxxxxxxxx-xxxxx` (e.g., `postgres-6b74686b4f-8pqlm`)

---

## 2. Open Redis CLI

Open an interactive `redis-cli` shell inside the running Redis container:

```bash
kubectl exec -it $REDIS_POD -c redis -- redis-cli
```

Alternatively, run non-interactive one-liner commands directly:

```bash
kubectl exec $REDIS_POD -c redis -- redis-cli <COMMAND>
```

---

## 3. Test Redis Connectivity with PING

Verify that the Redis server process is responsive and ready to accept commands:

```bash
kubectl exec $REDIS_POD -c redis -- redis-cli ping
```

*Expected Output:*
```text
PONG
```

---

## 4. Inspect Keys with SCAN

> **BEST PRACTICE**: Never run `KEYS *` in a production or shared environment, as it blocks the single-threaded Redis event loop. Always use cursor-based `SCAN`.

List stored keys across the active Redis database:

```bash
# Scan up to 100 keys matching any pattern
kubectl exec $REDIS_POD -c redis -- redis-cli --scan --pattern "*"

# Scan specifically for product cache keys
kubectl exec $REDIS_POD -c redis -- redis-cli --scan --pattern "product:*"

# Scan specifically for recommendation cache keys
kubectl exec $REDIS_POD -c redis -- redis-cli --scan --pattern "recommendation:*"
```

*Expected Output (after application requests):*
```text
product:101
product:1
recommendation:user42
```

---

## 5. Check Cache Values

The application's `RedisCache` store (`backend/cache/redis.py`) serializes cached entity dictionaries to JSON strings.

Inspect the payload and data type of a cached key:

```bash
# 1. Verify key data type (must be 'string')
kubectl exec $REDIS_POD -c redis -- redis-cli type product:101

# 2. Retrieve raw serialized JSON payload
kubectl exec $REDIS_POD -c redis -- redis-cli get product:101
```

*Expected Output:*
```json
{"product_id":"101","name":"Mechanical Keyboard","price":89.99,"category":"Electronics","created_at":"...","updated_at":"..."}
```

---

## 6. Check TTL and Database Size

Check key time-to-live and count resident objects in the current database:

```bash
# Check remaining TTL for a specific key in seconds
kubectl exec $REDIS_POD -c redis -- redis-cli ttl product:101

# Count total keys in the active database
kubectl exec $REDIS_POD -c redis -- redis-cli dbsize
```

*TTL Return Values:*
- `-1`: The key exists with no expiration (managed by the adaptive eviction policy).
- `-2`: The key does not exist or has already expired.
- `> 0`: Number of seconds remaining before automatic expiration.

---

## 7. Clear Only the Selected Redis Database

> ⚠️ **CAUTION: DESTRUCTIVE OPERATIONS**
> - `FLUSHALL` wipes **all 16 logical databases** (db 0 to db 15) in the Redis instance. **Avoid `FLUSHALL`.**
> - Prefer `FLUSHDB`, which purges **only the currently selected database** (the application defaults to database index `0` via `REDIS_DB=0`).

```bash
# Clear ONLY database 0 (the active application cache database)
kubectl exec $REDIS_POD -c redis -- redis-cli -n 0 flushdb

# Verify database 0 is empty
kubectl exec $REDIS_POD -c redis -- redis-cli -n 0 dbsize
# Output: (integer) 0
```

---

## 8. Identify the PostgreSQL Pod

Confirm the PostgreSQL pod name and ensure the container is ready:

```bash
kubectl get pods -l app=postgres
kubectl exec $POSTGRES_POD -c postgres -- pg_isready -U postgres -d adaptive_cache
```

*Expected Output:*
```text
adaptive_cache:5432 - accepting connections
```

---

## 9. Connect to the Correct PostgreSQL Database

Open an interactive `psql` session connected to the `adaptive_cache` database as the `postgres` user:

```bash
kubectl exec -it $POSTGRES_POD -c postgres -- psql -U postgres -d adaptive_cache
```

To execute single SQL queries non-interactively, use the `-c` flag:

```bash
kubectl exec $POSTGRES_POD -c postgres -- psql -U postgres -d adaptive_cache -c "<SQL_QUERY>"
```

---

## 10. List Tables and Inspect Schemas

List all application tables managed by SQLAlchemy models (`backend/database/models.py`):

```bash
kubectl exec $POSTGRES_POD -c postgres -- psql -U postgres -d adaptive_cache -c "\dt"
```

*Expected Tables:*
```text
               List of relations
 Schema |          Name          | Type  |  Owner   
--------+------------------------+-------+----------
 public | cache_metadata         | table | postgres
 public | products               | table | postgres
 public | recommendations        | table | postgres
 public | telemetry_observations | table | postgres
(4 rows)
```

### Inspect the `cache_metadata` Schema

```bash
kubectl exec $POSTGRES_POD -c postgres -- psql -U postgres -d adaptive_cache -c "\d cache_metadata"
```

*Columns in `cache_metadata`:*
- `key` (`varchar(255)`, Primary Key) — Cache key (e.g., `product:101`).
- `version` (`varchar(32)`) — Contract schema version (`v1`).
- `size_bytes` (`bigint`) — Serialized payload size in bytes.
- `access_count` (`integer`) — Cumulative access requests.
- `last_accessed` (`timestamp with time zone`) — Timestamp of most recent lookup.
- `retrieval_cost_ms` (`float`) — Upstream origin fetch duration in milliseconds.
- `hit_count` (`integer`) — Number of times served directly from cache.
- `miss_count` (`integer`) — Number of times retrieved from origin.
- `created_at` (`timestamp with time zone`) — Initial insertion timestamp.
- `features` (`json`) — Normalized [0, 1] feature vector calculated for adaptive scoring.
- `metadata` (`json`) — Additional runtime tags and attributes.

---

## 11. Query Cache Metadata

Inspect current persistent cache metadata:

```bash
kubectl exec $POSTGRES_POD -c postgres -- psql -U postgres -d adaptive_cache -c "
SELECT 
    key, 
    access_count, 
    hit_count, 
    miss_count, 
    retrieval_cost_ms, 
    size_bytes, 
    last_accessed 
FROM cache_metadata;
"
```

---

## 12. Test a Cache Miss Followed by a Cache Hit

Ensure the backend is accessible locally via port-forward (`kubectl port-forward svc/backend 8000:8000`) or test directly within the cluster network.

### Step 1: Clear the Cache
Start from a clean slate by flushing database 0:

```bash
kubectl exec $REDIS_POD -c redis -- redis-cli -n 0 flushdb
```

### Step 2: First Request (Cache MISS)
Request an uncached product (`product_id: 101`):

```bash
curl -i -s http://localhost:8000/data/product/101
```

*Expected Behavior:*
- **Status Code**: `200 OK`.
- **Latency**: Higher response time (~30ms–60ms) due to simulated origin retrieval delay in `backend_adapter.get_product(101)`.
- **Cache Action**:
  1. `CacheManager.get("product:101")` returns `None` (MISS).
  2. Telemetry records miss counter (`cache_misses_total` incremented).
  3. Payload is retrieved from `BackendAdapter` and serialized.
  4. `CacheManager.set("product:101", data)` saves entry into Redis.
  5. `CacheMetadataRepository.save()` inserts initial row into PostgreSQL.

### Step 3: Second Request (Cache HIT)
Request the identical product immediately:

```bash
curl -i -s http://localhost:8000/data/product/101
```

*Expected Behavior:*
- **Status Code**: `200 OK`.
- **Latency**: Near-instantaneous response (<2ms).
- **Cache Action**:
  1. `CacheManager.get("product:101")` returns cached JSON directly from Redis (HIT).
  2. Telemetry records hit counter (`cache_hits_total` incremented).
  3. **Zero origin calls executed** (no database query against `products` table).
  4. `CacheMetadataRepository.record_hit("product:101")` increments access and hit counters in PostgreSQL.

---

## 13. Verify Redis Keys After Requests

Confirm that Redis stored the key and payload:

```bash
# Check key existence
kubectl exec $REDIS_POD -c redis -- redis-cli exists product:101
# Expected Output: (integer) 1

# Check payload
kubectl exec $REDIS_POD -c redis -- redis-cli get product:101
```

---

## 14. Verify PostgreSQL Metadata Counters & Timestamps

Verify that PostgreSQL accurately reflects the transition from Miss to Hit:

```bash
kubectl exec $POSTGRES_POD -c postgres -- psql -U postgres -d adaptive_cache -c "
SELECT 
    key, 
    access_count, 
    hit_count, 
    miss_count, 
    round(retrieval_cost_ms::numeric, 2) AS origin_ms, 
    size_bytes, 
    created_at, 
    last_accessed 
FROM cache_metadata 
WHERE key = 'product:101';
"
```

*Expected Row Verification:*

| Column | Value after Request 1 (Miss) | Value after Request 2 (Hit) | Verification Criteria |
| :--- | :--- | :--- | :--- |
| `access_count` | `1` | `2` | Increments by 1 on each request |
| `hit_count` | `0` | `1` | Increments only on cache hits |
| `miss_count` | `1` | `1` | Stays at 1 (no new origin fetches) |
| `origin_ms` | `~30.00` | `~30.00` | Reflects initial origin retrieval duration |
| `size_bytes` | `> 0` | `> 0` | Matches serialized payload size |
| `last_accessed` | Equal to `created_at` | Greater than `created_at` | Updated timestamp on cache hit |

---

## 15. Check Backend Prometheus Cache Metrics

Verify that in-memory telemetry and Prometheus counters reflect the hit and miss:

```bash
curl -s http://localhost:8000/metrics | grep -E "(cache_hits_total|cache_misses_total|cache_hit_ratio|cache_size_bytes)"
```

*Expected Output:*
```text
# HELP cache_hits_total Total cache hit count
# TYPE cache_hits_total counter
cache_hits_total 1.0

# HELP cache_misses_total Total cache miss count
# TYPE cache_misses_total counter
cache_misses_total 1.0

# HELP cache_hit_ratio Current cache hit ratio (hits / total requests)
# TYPE cache_hit_ratio gauge
cache_hit_ratio 0.5

# HELP cache_size_bytes Current estimated cache usage in bytes
# TYPE cache_size_bytes gauge
cache_size_bytes 214.0
```

---

## 16. Troubleshooting Commands

### Issue 1: Backend Reports `Failed to connect to Redis`
Verify network reachability and configuration from inside the backend pod:

```bash
export BACKEND_POD=$(kubectl get pods -l app=backend -o jsonpath="{.items[0].metadata.name}")

# Check environment variables in backend pod
kubectl exec $BACKEND_POD -c backend -- env | grep -E "(CACHE_BACKEND|REDIS)"

# Verify backend can resolve and ping Redis service
kubectl exec $BACKEND_POD -c backend -- python3 -c "
import urllib.request, socket
print('DNS Redis:', socket.gethostbyname('redis'))
"
```

### Issue 2: Backend Falls Back to InMemory Cache
If `CACHE_BACKEND` is set to `inmemory`, the application will not store keys in Redis.
- **Check Backend ConfigMap**: Ensure `k8s/backend/configmap.yaml` has `CACHE_BACKEND: "redis"`.
- **Check Logs**:
  ```bash
  kubectl logs deployment/backend -c backend --tail=50 | grep -i cache
  ```

### Issue 3: PostgreSQL Authentication or Database Connection Fails
Check that the database credentials in `k8s/postgres/secret.yaml` match the backend configuration:

```bash
# Verify secret values (decoded)
kubectl get secret postgres-secret -o jsonpath="{.data.POSTGRES_PASSWORD}" | base64 --decode
echo ""

# Test direct connection using credentials
kubectl exec -it $BACKEND_POD -c backend -- python3 -c "
import os
from sqlalchemy import create_engine, text
url = 'postgresql+psycopg://postgres:postgres@postgres:5432/adaptive_cache'
engine = create_engine(url)
with engine.connect() as conn:
    print('DB Connection Success:', conn.execute(text('SELECT 1')).scalar())
"
```

### Issue 4: PostgreSQL Active Queries and Locks Inspection
If database operations hang during load testing, check active query status and locks:

```bash
kubectl exec $POSTGRES_POD -c postgres -- psql -U postgres -d adaptive_cache -c "
SELECT 
    pid, 
    usename, 
    client_addr, 
    state, 
    query 
FROM pg_stat_activity 
WHERE state != 'idle';
"
```
