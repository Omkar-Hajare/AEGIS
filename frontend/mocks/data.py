cache_stats = {
    "hit_rate": 87.5,
    "requests_per_second": 1250,
    "cache_usage": 72.4,
    "total_objects": 1240,
    "backend_calls": 156,
}

cache_objects = [
    {
        "key": "user:1001",
        "size_bytes": 2048,
        "access_count": 245,
        "last_accessed": "2026-09-04 11:20:30",
        "retrieval_cost_ms": 12.5,
        "score": 0.92,
    },
    {
        "key": "product:501",
        "size_bytes": 4096,
        "access_count": 180,
        "last_accessed": "2026-09-04 11:20:20",
        "retrieval_cost_ms": 18.2,
        "score": 0.81,
    },
    {
        "key": "recommendation:88",
        "size_bytes": 8192,
        "access_count": 95,
        "last_accessed": "2026-09-04 11:19:55",
        "retrieval_cost_ms": 35.7,
        "score": 0.64,
    },
]

workload = {
    "workload_type": "READ_HEAVY",
    "request_rate": 1250,
    "hit_rate": 87.5,
    "miss_rate": 12.5,
    "backend_latency_ms": 24.6,
    "window_seconds": 60,
}

adaptive_decision = {
    "capacity_action": "SCALE_UP",
    "recommended_capacity_bytes": 536870912,
    "eviction_keys": ["recommendation:88"],
    "reason": "Read-heavy workload with increasing cache pressure",
}

benchmark_results = [
    {
        "policy": "LRU",
        "hit_rate": 78.4,
        "p95_latency_ms": 42.5,
        "backend_calls": 312,
        "cost": 18.4,
    },
    {
        "policy": "LFU",
        "hit_rate": 81.7,
        "p95_latency_ms": 38.2,
        "backend_calls": 276,
        "cost": 16.2,
    },
    {
        "policy": "GDS",
        "hit_rate": 84.1,
        "p95_latency_ms": 34.8,
        "backend_calls": 241,
        "cost": 14.8,
    },
    {
        "policy": "Adaptive",
        "hit_rate": 89.6,
        "p95_latency_ms": 27.3,
        "backend_calls": 184,
        "cost": 11.2,
    },
]

performance_history = {
    "time": [
        "11:10",
        "11:15",
        "11:20",
        "11:25",
        "11:30",
        "11:35",
        "11:40",
        "11:45",
    ],
    "hit_rate": [
        82.1,
        83.4,
        84.8,
        85.6,
        86.2,
        87.1,
        87.8,
        87.5,
    ],
    "request_rate": [
        980,
        1050,
        1110,
        1180,
        1210,
        1240,
        1270,
        1250,
    ],
    "cache_usage": [
        61,
        64,
        66,
        68,
        70,
        71,
        73,
        72.4,
    ],
}