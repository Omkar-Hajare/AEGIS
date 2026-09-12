import asyncio
import json
from typing import Any
import unittest

from api.routes.data import cache_manager
from app.main import app
from telemetry.collector import telemetry_collector


def call_endpoint(method: str, path: str) -> tuple[int, dict[str, Any]]:
    """In-process standard ASGI caller for testing FastAPI endpoints without external dependencies."""
    query_string = b""
    if "?" in path:
        path, qs = path.split("?", 1)
        query_string = qs.encode("ascii")

    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": method,
        "path": path,
        "raw_path": path.encode("ascii"),
        "query_string": query_string,
        "headers": [],
        "server": ("127.0.0.1", 8000),
    }
    response_body = bytearray()
    status_code = 500

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message):
        nonlocal status_code
        if message["type"] == "http.response.start":
            status_code = message["status"]
        elif message["type"] == "http.response.body":
            response_body.extend(message.get("body", b""))

    asyncio.run(app(scope, receive, send))
    body = json.loads(response_body.decode("utf-8")) if response_body else {}
    return status_code, body


class TestTelemetryAPI(unittest.TestCase):
    def setUp(self):
        """Reset telemetry and cache before each test."""
        cache_manager._store._store.clear()
        cache_manager.clear_metadata()
        telemetry_collector.reset()

    def test_empty_telemetry_observation(self):
        """A. GET /telemetry/observation returns HTTP 200, version v1, zeros, and empty dicts."""
        status, body = call_endpoint("GET", "/telemetry/observation")
        self.assertEqual(status, 200)
        self.assertEqual(body["version"], "v1")
        self.assertEqual(body["total_requests"], 0)
        self.assertEqual(body["cache_hits"], 0)
        self.assertEqual(body["cache_misses"], 0)
        self.assertEqual(body["backend_calls"], 0)
        self.assertEqual(body["request_rate"], 0.0)
        self.assertEqual(body["hit_rate"], 0.0)
        self.assertEqual(body["miss_rate"], 0.0)
        self.assertEqual(body["backend_latency_ms"], 0.0)
        self.assertEqual(body["current_window_access_counts"], {})
        self.assertEqual(body["previous_window_access_counts"], {})
        self.assertIn("timestamp", body)
        self.assertGreaterEqual(body["window_seconds"], 0.0)

    def test_get_workload_state_endpoint(self):
        """B. GET /telemetry/workload returns HTTP 200, version v1, and workload_type is None."""
        call_endpoint("GET", "/data/product/42")
        call_endpoint("GET", "/data/product/42")

        status, body = call_endpoint("GET", "/telemetry/workload")
        self.assertEqual(status, 200)
        self.assertEqual(body["version"], "v1")
        self.assertIn("request_rate", body)
        self.assertEqual(body["hit_rate"], 0.5)
        self.assertEqual(body["miss_rate"], 0.5)
        self.assertGreater(body["backend_latency_ms"], 0.0)
        self.assertGreaterEqual(body["window_seconds"], 0.0)
        self.assertIsNone(body["workload_type"], "workload_type must remain None")
        self.assertIn("timestamp", body)

    def test_get_system_state_endpoint(self):
        """C. GET /telemetry/system returns HTTP 200, version v1, and system metrics."""
        call_endpoint("GET", "/data/product/10")

        status, body = call_endpoint("GET", "/telemetry/system")
        self.assertEqual(status, 200)
        self.assertEqual(body["version"], "v1")
        self.assertIn("cache_capacity_bytes", body)
        self.assertGreater(body["cache_usage_bytes"], 0)
        self.assertEqual(body["object_count"], 1)
        self.assertEqual(body["backend_calls"], 1)
        self.assertEqual(body["cache_evictions"], 0)
        self.assertGreaterEqual(body["window_seconds"], 0.0)
        self.assertIn("timestamp", body)

    def test_observation_consistency(self):
        """D. Observation consistency: verify counters reflect performed requests."""
        call_endpoint("GET", "/data/product/5")
        call_endpoint("GET", "/data/product/5")
        call_endpoint("GET", "/data/recommendation/8")

        status, obs = call_endpoint("GET", "/telemetry/observation")
        self.assertEqual(status, 200)
        self.assertEqual(obs["total_requests"], 3)
        self.assertEqual(obs["cache_hits"], 1)
        self.assertEqual(obs["cache_misses"], 2)
        self.assertEqual(obs["backend_calls"], 2)
        self.assertAlmostEqual(obs["hit_rate"], 1.0 / 3.0)
        self.assertAlmostEqual(obs["miss_rate"], 2.0 / 3.0)

    def test_workload_consistency(self):
        """E. Workload consistency: workload endpoint values match observation."""
        call_endpoint("GET", "/data/product/99")
        call_endpoint("GET", "/data/product/99")

        _, obs = call_endpoint("GET", "/telemetry/observation")
        _, ws = call_endpoint("GET", "/telemetry/workload")

        self.assertEqual(ws["hit_rate"], obs["hit_rate"])
        self.assertEqual(ws["miss_rate"], obs["miss_rate"])
        self.assertEqual(ws["backend_latency_ms"], obs["backend_latency_ms"])
        self.assertIsNone(ws["workload_type"])

    def test_system_consistency(self):
        """F. System consistency: after caching an object, object_count >= 1 and cache_usage_bytes > 0."""
        call_endpoint("GET", "/data/product/1")
        call_endpoint("GET", "/data/product/2")

        status, ss = call_endpoint("GET", "/telemetry/system")
        self.assertEqual(status, 200)
        self.assertGreaterEqual(ss["object_count"], 2)
        self.assertGreater(ss["cache_usage_bytes"], 0)

    def test_window_reset_behavior(self):
        """G. Reset: POST /telemetry/window/reset rotates window and clears current counters."""
        call_endpoint("GET", "/data/product/101")
        call_endpoint("GET", "/data/product/101")
        call_endpoint("GET", "/data/recommendation/202")

        # Reset window via API
        reset_status, reset_body = call_endpoint("POST", "/telemetry/window/reset")
        self.assertEqual(reset_status, 200)
        self.assertEqual(reset_body["status"], "ok")
        self.assertEqual(reset_body["message"], "telemetry window reset")

        # Query observation after window reset
        status, obs = call_endpoint("GET", "/telemetry/observation")
        self.assertEqual(status, 200)
        self.assertEqual(obs["total_requests"], 0)
        self.assertEqual(obs["cache_hits"], 0)
        self.assertEqual(obs["cache_misses"], 0)
        self.assertEqual(obs["backend_calls"], 0)
        self.assertEqual(obs["current_window_access_counts"], {})
        self.assertEqual(
            obs["previous_window_access_counts"],
            {"product:101": 2, "recommendation:202": 1},
        )

    def test_cache_isolation_after_window_reset(self):
        """H. Cache isolation: after reset, existing cached object is still served from cache."""
        call_endpoint("GET", "/data/product/303")
        self.assertTrue(cache_manager.exists("product:303"))

        # Reset telemetry window
        call_endpoint("POST", "/telemetry/window/reset")

        # Request again; should be a cache HIT without increasing backend calls
        self.assertTrue(cache_manager.exists("product:303"))
        status, prod = call_endpoint("GET", "/data/product/303")
        self.assertEqual(status, 200)
        self.assertEqual(prod["product_id"], "303")

        # The new window should only have 1 request and 1 HIT (no backend calls)
        _, obs = call_endpoint("GET", "/telemetry/observation")
        self.assertEqual(obs["total_requests"], 1)
        self.assertEqual(obs["cache_hits"], 1)
        self.assertEqual(obs["backend_calls"], 0)

    def test_read_only_endpoints(self):
        """I. Read-only endpoints: GET on observation, workload, system do not mutate counters."""
        call_endpoint("GET", "/data/product/500")

        # First read
        _, obs1 = call_endpoint("GET", "/telemetry/observation")
        _, ws1 = call_endpoint("GET", "/telemetry/workload")
        _, ss1 = call_endpoint("GET", "/telemetry/system")

        # Second read
        _, obs2 = call_endpoint("GET", "/telemetry/observation")
        _, ws2 = call_endpoint("GET", "/telemetry/workload")
        _, ss2 = call_endpoint("GET", "/telemetry/system")

        self.assertEqual(obs1["total_requests"], obs2["total_requests"])
        self.assertEqual(obs1["cache_misses"], obs2["cache_misses"])
        self.assertEqual(ws1["hit_rate"], ws2["hit_rate"])
        self.assertEqual(ss1["object_count"], ss2["object_count"])
        self.assertEqual(ss1["cache_usage_bytes"], ss2["cache_usage_bytes"])

    def test_cache_hit_ratio_endpoint(self):
        """J. GET /telemetry/cache-hit-ratio returns canonical aggregated metrics."""
        # Baseline empty
        status, body = call_endpoint("GET", "/telemetry/cache-hit-ratio")
        self.assertEqual(status, 200)
        self.assertEqual(body["total_requests"], 0)
        self.assertEqual(body["cache_hits"], 0)
        self.assertEqual(body["cache_misses"], 0)
        self.assertEqual(body["cache_hit_ratio"], 0.0)
        self.assertIn("observation_window_start", body)
        self.assertIn("observation_window_end", body)

        # Generate 1 miss and 1 hit
        call_endpoint("GET", "/data/product/777")
        call_endpoint("GET", "/data/product/777")

        status, body = call_endpoint("GET", "/telemetry/cache-hit-ratio?window_seconds=300")
        self.assertEqual(status, 200)
        self.assertEqual(body["total_requests"], 2)
        self.assertEqual(body["cache_hits"], 1)
        self.assertEqual(body["cache_misses"], 1)
        self.assertEqual(body["cache_hit_ratio"], 50.0)
        self.assertIn("observation_window_start", body)
        self.assertIn("observation_window_end", body)


if __name__ == "__main__":
    unittest.main()

