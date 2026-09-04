"""Prometheus metric definitions for the Adaptive Cache System.

Defines all Prometheus counters, gauges, and histograms.
Provides a sync_from_telemetry() function that copies the current
state of the in-process TelemetryCollector + CacheManager into
Prometheus gauges so /metrics always reflects live values.
"""

from prometheus_client import Counter, Gauge, Histogram


# ──────────────────────────────────────────────
# REQUEST METRICS
# ──────────────────────────────────────────────
REQUEST_COUNT = Counter(
    "requests_total",
    "Total HTTP requests handled by the backend",
    ["method", "endpoint", "status"],
)

REQUEST_LATENCY = Histogram(
    "request_latency_seconds",
    "HTTP request latency in seconds",
    ["method", "endpoint"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0),
)

# ──────────────────────────────────────────────
# CACHE METRICS
# ──────────────────────────────────────────────
CACHE_HITS = Counter(
    "cache_hits_total",
    "Total cache hit count",
)

CACHE_MISSES = Counter(
    "cache_misses_total",
    "Total cache miss count",
)

CACHE_HIT_RATIO = Gauge(
    "cache_hit_ratio",
    "Current cache hit ratio (hits / total requests)",
)

CACHE_SIZE_BYTES = Gauge(
    "cache_size_bytes",
    "Current estimated cache usage in bytes",
)

CACHE_OBJECT_COUNT = Gauge(
    "cache_object_count",
    "Number of objects currently tracked in cache metadata",
)

CACHE_EVICTIONS = Counter(
    "cache_evictions_total",
    "Total cache evictions performed",
)

# ──────────────────────────────────────────────
# BACKEND / ORIGIN METRICS
# ──────────────────────────────────────────────
BACKEND_REQUESTS = Counter(
    "backend_requests_total",
    "Total requests forwarded to the origin backend",
)

BACKEND_LATENCY = Histogram(
    "backend_latency_seconds",
    "Backend / origin response latency in seconds",
    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)

# ──────────────────────────────────────────────
# SYSTEM METRICS
# ──────────────────────────────────────────────
REQUEST_RATE = Gauge(
    "request_rate_per_second",
    "Current request rate (requests per second in the observation window)",
)

BACKEND_AVG_LATENCY_MS = Gauge(
    "backend_avg_latency_ms",
    "Average backend latency in milliseconds for the current window",
)

# ──────────────────────────────────────────────
# ADAPTIVE SYSTEM METRICS
# ──────────────────────────────────────────────
ADAPTIVE_DECISIONS = Counter(
    "adaptive_decisions_total",
    "Total adaptive decisions evaluated",
)


def sync_from_telemetry(telemetry_collector, cache_manager=None):
    """Copy current in-process telemetry state into Prometheus gauges.

    Called on every /metrics scrape so Prometheus always sees fresh values.
    This bridges the existing TelemetryCollector counters to Prometheus
    without modifying the application's data routes.
    """
    observation = telemetry_collector.observe()

    # Hit ratio
    if observation.total_requests > 0:
        CACHE_HIT_RATIO.set(observation.cache_hits / observation.total_requests)
    else:
        CACHE_HIT_RATIO.set(0.0)

    # Request rate
    REQUEST_RATE.set(observation.request_rate)

    # Backend average latency
    BACKEND_AVG_LATENCY_MS.set(observation.backend_latency_ms)

    # Cache size and object count from CacheManager metadata
    if cache_manager is not None:
        all_metadata = cache_manager.get_all_metadata()
        total_bytes = sum(meta.size_bytes for meta in all_metadata.values())
        CACHE_SIZE_BYTES.set(total_bytes)
        CACHE_OBJECT_COUNT.set(len(all_metadata))
