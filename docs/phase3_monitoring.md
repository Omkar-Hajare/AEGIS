# Phase 3 — Prometheus Monitoring Integration

## Overview

The backend now exposes a `/metrics` endpoint in Prometheus exposition format. Prometheus scrapes this endpoint every 5 seconds and stores time-series data. Grafana reads from Prometheus and renders pre-built dashboards.

## Architecture

```
FastAPI (/metrics) ──scrape──► Prometheus (:9090) ──query──► Grafana (:3000)
```

## Exposed Metrics

| Metric | Type | Description |
|--------|------|-------------|
| `requests_total` | Counter | Total HTTP requests (labels: method, endpoint, status) |
| `request_latency_seconds` | Histogram | HTTP request latency with percentile buckets |
| `cache_hits_total` | Counter | Total cache hits |
| `cache_misses_total` | Counter | Total cache misses |
| `cache_hit_ratio` | Gauge | Current hit ratio (synced from telemetry) |
| `cache_size_bytes` | Gauge | Current cache usage in bytes |
| `cache_object_count` | Gauge | Number of cached objects |
| `cache_evictions_total` | Counter | Total cache evictions |
| `backend_requests_total` | Counter | Requests forwarded to origin |
| `backend_latency_seconds` | Histogram | Origin response latency with buckets |
| `request_rate_per_second` | Gauge | Current request rate from observation window |
| `backend_avg_latency_ms` | Gauge | Average backend latency in ms |

## How It Works

1. **Middleware** (`app/main.py`): Automatically tracks every HTTP request — increments `requests_total` counter and observes `request_latency_seconds` histogram.

2. **Data Routes** (`api/routes/data.py`): On each cache hit/miss/backend call, increments the corresponding Prometheus counter alongside the existing `TelemetryCollector`.

3. **Sync on Scrape** (`metrics/prometheus.py`): When Prometheus hits `/metrics`, the `sync_from_telemetry()` function reads the current `TelemetryCollector` observation and updates gauge values (hit ratio, request rate, cache size, object count).

## Files Added/Modified

| File | Action | Purpose |
|------|--------|---------|
| `backend/metrics/__init__.py` | NEW | Metrics package init |
| `backend/metrics/prometheus.py` | NEW | All Prometheus metric definitions + sync function |
| `backend/app/main.py` | MODIFIED | Added middleware + `/metrics` endpoint |
| `backend/api/routes/data.py` | MODIFIED | Added Prometheus counter increments |
| `backend/requirements.txt` | MODIFIED | Added `prometheus_client>=0.20.0` |
| `monitoring/grafana/provisioning/dashboards/dashboards.yml` | NEW | Dashboard provisioning config |
| `monitoring/grafana/provisioning/dashboards/adaptive-cache.json` | NEW | Pre-built Grafana dashboard |

## Grafana Dashboard

Auto-provisioned dashboard named **"Adaptive Cache System"** with panels:

- Request Rate (req/s) — time series
- Request Latency percentiles (p50/p95/p99) — time series
- Cache Hit Ratio — gauge (red < 50%, yellow < 80%, green ≥ 80%)
- Cache Hits vs Misses — bar chart
- Cache Size (bytes) — stat
- Cache Object Count — stat
- Cache Evictions — time series
- Backend Latency percentiles — time series
- Backend Requests rate — time series

## Verification

```bash
# 1. Build and start
docker compose up --build -d

# 2. Check /metrics endpoint
curl http://localhost:8000/metrics

# 3. Check Prometheus targets
# Open http://localhost:9090/targets — "backend" job should be UP

# 4. Check Grafana dashboard
# Open http://localhost:3000 → login admin/admin → "Adaptive Cache System" dashboard

# 5. Generate traffic and watch metrics
curl http://localhost:8000/data/product/1
curl http://localhost:8000/data/recommendation/user1
```

## Prometheus Config

```yaml
# monitoring/prometheus.yml
scrape_configs:
  - job_name: "backend"
    metrics_path: "/metrics"
    static_configs:
      - targets: ["backend:8000"]
```

Already configured in Phase 2. No changes needed.
