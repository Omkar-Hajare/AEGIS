# Phase 4 — Grafana Jury Dashboard

## Overview

A dedicated, clean Grafana dashboard titled **"Adaptive Cache System"** designed specifically for the hackathon jury demonstration. The dashboard is auto-provisioned upon Grafana startup, queries the Prometheus datasource, and organizes all critical system metrics into four logical rows:

1. **APPLICATION**
2. **CACHE**
3. **ADAPTIVE SYSTEM**
4. **KUBERNETES**

---

## Dashboard Architecture

```
FastAPI Backend (:8000/metrics)
             │ (5s scrape)
             ▼
      Prometheus (:9090)
             │ (PromQL queries)
             ▼
       Grafana (:3000)
 ┌──────────────────────────────────────────────┐
 │ APPLICATION   (Rate, Latency, Errors, Origin)│
 ├──────────────────────────────────────────────┤
 │ CACHE         (Hit Ratio, Hits, Misses, Size)│
 ├──────────────────────────────────────────────┤
 │ ADAPTIVE      (Decisions, Workload, Control) │
 ├──────────────────────────────────────────────┤
 │ KUBERNETES    (Pods, CPU, Memory, HPA)       │
 └──────────────────────────────────────────────┘
```

---

## Row & Panel Organization

### 1. APPLICATION
- **Request Rate**: `sum(rate(requests_total[1m])) by (method, endpoint, status)` — HTTP throughput across normalized endpoints (`/data/product/{product_id}`, `/data/recommendation/{user_id}`, `/health`).
- **Request Latency (P95 / P99)**: `histogram_quantile(0.95/0.99, sum(rate(request_latency_seconds_bucket[1m])) by (le))` — Percentile distribution of application response times.
- **Error Rate (HTTP 4xx / 5xx)**: `(sum(rate(requests_total{status=~"[45].."}[1m])) / sum(rate(requests_total[1m])) * 100) or vector(0)` — Ratio of non-2xx responses.
- **Backend Latency (Origin P50 / P95)**: `histogram_quantile(0.50/0.95, sum(rate(backend_latency_seconds_bucket[1m])) by (le))` — Latency to origin during cache misses.

### 2. CACHE
- **Cache Hit Ratio**: `cache_hit_ratio` — Live visual gauge with color thresholds:
  - 🔴 `< 50%` (Red)
  - 🟡 `50% - 80%` (Yellow)
  - 🟢 `≥ 80%` (Green)
- **Cache Hits**: `rate(cache_hits_total[1m])` — Hit operations per second.
- **Cache Misses**: `rate(cache_misses_total[1m])` — Miss operations forwarded to origin.
- **Cache Size**: `cache_size_bytes` — Live memory volume occupied by cached items.
- **Cache Evictions**: `rate(cache_evictions_total[1m])` — Eviction rate (safely 0 until capacity pressure or eviction policy triggers).

### 3. ADAPTIVE SYSTEM
- **Adaptive Decisions**: `adaptive_decisions_total` — Cumulative decisions evaluated by the adaptive intelligence engine.
- **Current Workload Request Rate**: `request_rate_per_second` — Real-time request arrival intensity feeding `WorkloadAnalyzer`.
- **Capacity Recommendation & Origin Pressure**: `backend_avg_latency_ms` — Mean origin retrieval delay informing dynamic capacity sizing.
- **Policy / Decision Information**: Visual markdown diagram illustrating the closed-loop control architecture:
  ```
  Workload Traffic ➔ Telemetry Observation ➔ Workload Classification ➔ Decision Engine ➔ Eviction & Capacity Scaling
  ```

### 4. KUBERNETES
- **FastAPI Pod Count**: `count(kube_pod_status_phase{phase="Running", pod=~".*(backend|fastapi).*"}) or count(kube_pod_info{pod=~".*(backend|fastapi).*"})` — Live backend pod count. Shows "No Data (Phase 5 K8s Pending)" in Compose mode.
- **FastAPI Pods CPU Usage**: `sum(rate(container_cpu_usage_seconds_total{pod=~".*(backend|fastapi).*", container!="POD", container!=""}[1m]))` — CPU consumption of backend pods.
- **FastAPI Pods Memory Usage**: `sum(container_memory_working_set_bytes{pod=~".*(backend|fastapi).*", container!="POD", container!=""})` — Working set memory consumption.
- **HPA Replicas (Desired / Current)**: `kube_hpa_status_current_replicas` and `kube_hpa_status_desired_replicas` — Gracefully indicates "Pending Phase 5 HPA" until Kubernetes autoscaling is deployed.

---

## Provisioning Configuration

- **Datasource Provisioning**: `monitoring/grafana/provisioning/datasources/prometheus.yml` provides Prometheus at `http://prometheus:9090` (UID: `PBFA97CFB590B2093`).
- **Dashboard Provisioning**: `monitoring/grafana/provisioning/dashboards/dashboards.yml` monitors `/etc/grafana/provisioning/dashboards` with automatic 10-second updates.
- **Dashboard Definition**: `monitoring/grafana/provisioning/dashboards/adaptive-cache.json` defines all 4 rows and 17 panels.

---

## Verification & Validation

```bash
# 1. Verify Grafana container health
docker compose ps grafana

# 2. Check Grafana provisioning logs
docker logs adaptive-grafana --tail 30 | grep -i dashboard

# 3. Verify provisioned dashboard API
curl -s -u admin:admin http://localhost:3000/api/dashboards/uid/adaptive-cache-dashboard

# 4. Access UI
# Open http://localhost:3000 (admin / admin) -> Dashboards -> "Adaptive Cache System"
```
