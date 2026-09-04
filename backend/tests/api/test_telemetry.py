import asyncio
import json
from typing import Any
import unittest

from api.routes.data import cache_manager
from app.main import app
from telemetry.collector import telemetry_collector


def call_endpoint(method: str, path: str) -> tuple[int, dict[str, Any]]:
    """In-process standard ASGI caller for testing FastAPI endpoints without external dependencies."""
    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": method,
        "path": path,
        "raw_path": path.encode("ascii"),
        "query_string": b"",
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
        """A. Empty telemetry observation: GET /telemetry/observation returns zeros and v1."""
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

    def test_telemetry_after_requests(self):
        """B. Telemetry reflects product and recommendation requests."""
        # Make product request (MISS)
        status, prod1 = call_endpoint("GET", "/data/product/42")
        self.assertEqual(status, 200)

        # Make product request again (HIT)
        status, prod2 = call_endpoint("GET", "/data/product/42")
        self.assertEqual(status, 200)

        # Make recommendation request (MISS)
        status, rec1 = call_endpoint("GET", "/data/recommendation/10")
        self.assertEqual(status, 200)

        status, obs = call_endpoint("GET", "/telemetry/observation")
        self.assertEqual(status, 200)
        self.assertEqual(obs["version"], "v1")
        self.assertEqual(obs["total_requests"], 3)
        self.assertEqual(obs["cache_hits"], 1)
        self.assertEqual(obs["cache_misses"], 2)
        self.assertEqual(obs["backend_calls"], 2)
        self.assertAlmostEqual(obs["hit_rate"], 1.0 / 3.0)
        self.assertAlmostEqual(obs["miss_rate"], 2.0 / 3.0)
        self.assertGreater(obs["backend_latency_ms"], 0.0)

    def test_per_key_observations(self):
        """C. Verify current_window_access_counts contains expected keys."""
        call_endpoint("GET", "/data/product/42")
        call_endpoint("GET", "/data/product/42")
        call_endpoint("GET", "/data/recommendation/99")

        status, obs = call_endpoint("GET", "/telemetry/observation")
        self.assertEqual(status, 200)
        counts = obs["current_window_access_counts"]
        self.assertEqual(counts.get("product:42"), 2)
        self.assertEqual(counts.get("recommendation:99"), 1)

    def test_previous_window_api_behavior(self):
        """D. Previous-window API behavior through POST /telemetry/window/reset."""
        call_endpoint("GET", "/data/product/1")
        call_endpoint("GET", "/data/product/1")
        call_endpoint("GET", "/data/recommendation/2")

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
            {"product:1": 2, "recommendation:2": 1},
        )

    def test_read_only_observation(self):
        """E. Calling GET /telemetry/observation twice does not mutate or reset counters."""
        call_endpoint("GET", "/data/product/5")

        status1, obs1 = call_endpoint("GET", "/telemetry/observation")
        status2, obs2 = call_endpoint("GET", "/telemetry/observation")

        self.assertEqual(status1, 200)
        self.assertEqual(status2, 200)
        self.assertEqual(obs1["total_requests"], 1)
        self.assertEqual(obs2["total_requests"], 1)
        self.assertEqual(obs1["cache_misses"], 1)
        self.assertEqual(obs2["cache_misses"], 1)
        self.assertEqual(obs1["current_window_access_counts"], obs2["current_window_access_counts"])

    def test_cache_isolation_after_window_reset(self):
        """F. Existing cache entries remain accessible after telemetry window reset."""
        # Populate cache
        call_endpoint("GET", "/data/product/88")
        self.assertTrue(cache_manager.exists("product:88"))

        # Reset telemetry window
        call_endpoint("POST", "/telemetry/window/reset")

        # Cache content and metadata must still exist
        self.assertTrue(cache_manager.exists("product:88"))
        self.assertEqual(cache_manager.get("product:88")["product_id"], "88")
        meta = cache_manager.get_metadata("product:88")
        self.assertIsNotNone(meta)
        self.assertEqual(meta.key, "product:88")

    def test_existing_functionality(self):
        """G. Verify health, product, and recommendation endpoints still work."""
        h_status, h_body = call_endpoint("GET", "/health")
        self.assertEqual(h_status, 200)
        self.assertEqual(h_body["status"], "ok")

        p_status, p_body = call_endpoint("GET", "/data/product/123")
        self.assertEqual(p_status, 200)
        self.assertEqual(p_body["product_id"], "123")

        r_status, r_body = call_endpoint("GET", "/data/recommendation/456")
        self.assertEqual(r_status, 200)
        self.assertEqual(r_body["user_id"], "456")


if __name__ == "__main__":
    unittest.main()
