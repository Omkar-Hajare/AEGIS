# Monitoring

## Purpose

Monitoring is an essential part of the Adaptive Cache System. It provides real-time visibility into how the application, caching layer, and backend services behave under varying workloads.

Specifically, monitoring helps to:
- **Observe cache performance**: Track how effectively cached data is serving client requests.
- **Track cache hits and misses**: See live counts and rates of cache hits versus cache misses.
- **Monitor request latency**: Measure end-to-end response times and origin retrieval delays.
- **Observe backend traffic and system health**: Monitor HTTP request volumes, error rates, and origin load.
- **Help identify performance issues**: Detect cache thrashing, high origin latency, or capacity saturation early.

---

## Prometheus

Prometheus is the time-series metrics collection and storage engine in our system:

- **Metrics Collection & Storage**: Prometheus continuously gathers and stores numeric time-series data from our services.
- **Exposed Endpoint**: The FastAPI backend exposes application metrics in Prometheus exposition format at `http://localhost:8000/metrics`.
- **Periodic Scraping**: Prometheus periodically queries (scrapes) the `/metrics` endpoint every 5 seconds to capture fresh runtime measurements.
- **Key Metrics Tracked**: It records critical system indicators, including:
  - Cache hit ratio (`cache_hit_ratio`)
  - Total cache hits and misses (`cache_hits_total`, `cache_misses_total`)
  - HTTP request counts and error rates (`requests_total`)
  - Request and origin backend latencies (`request_latency_seconds`, `backend_latency_seconds`)
  - Cache memory usage and object counts (`cache_size_bytes`, `cache_object_count`)
  - Evaluated adaptive decisions (`adaptive_decisions_total`)

---

## Grafana

Grafana provides visual analytics and interactive observability for the system:

- **Data Source Integration**: Grafana automatically connects to Prometheus as its default data source.
- **Visual Dashboards**: It translates raw Prometheus time-series data into intuitive gauges, line graphs, and status panels.
- **Audience & Evaluation**: It provides developers, operators, and evaluators with a single screen to visually understand live system performance.
- **Operational Insights**: Users can observe:
  - Cache efficiency through a color-coded hit ratio gauge (red, yellow, green)
  - Latency percentiles (P50, P95, P99)
  - Origin backend retrieval load prevented by caching
  - Real-time container resource usage and scaling behavior

---

## Monitoring Flow

The end-to-end monitoring pipeline operates as follows:

```
Application Backend (FastAPI :8000)
       │
       ▼
Metrics Endpoint (/metrics)
       │  (scraped every 5s)
       ▼
Prometheus (:9090)
       │  (PromQL queries)
       ▼
Grafana Dashboard (:3000)
```

---

## Running Monitoring

Both monitoring services are fully containerized and integrated into the local Docker Compose environment:

1. **Starting Services**: Running `docker compose up -d` automatically builds and launches both the `prometheus` and `grafana` containers alongside the backend, frontend, Redis, and PostgreSQL.
2. **Accessing Prometheus**: The Prometheus web console is available at `http://localhost:9090` to inspect targets and execute raw PromQL queries.
3. **Accessing Grafana**: The pre-provisioned **"Adaptive Cache System"** dashboard is accessible at `http://localhost:3000` (default credentials: `admin` / `admin`).
