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


class TestDataAndHealthAPI(unittest.TestCase):
    def setUp(self):
        """Reset cache and telemetry before each test for clean isolation."""
        cache_manager._store._store.clear()
        cache_manager.clear_metadata()
        telemetry_collector.reset()

    def test_health_check_endpoint(self):
        """Verify GET /health returns HTTP 200 and expected service status metadata."""
        status, body = call_endpoint("GET", "/health")
        self.assertEqual(status, 200)
        self.assertEqual(body.get("status"), "ok")
        self.assertIn("service", body)
        self.assertIn("version", body)

    def test_get_product_api_flow(self):
        """Verify GET /data/product/{id} lifecycle: MISS then HIT."""
        # Request 1: MISS
        status1, body1 = call_endpoint("GET", "/data/product/101")
        self.assertEqual(status1, 200)
        self.assertEqual(body1["product_id"], "101")
        self.assertEqual(body1["name"], "Product 101")
        self.assertEqual(body1["category"], "demo")

        # Verify cached
        self.assertTrue(cache_manager.exists("product:101"))

        # Request 2: HIT
        status2, body2 = call_endpoint("GET", "/data/product/101")
        self.assertEqual(status2, 200)
        self.assertEqual(body2, body1)

    def test_product_multiple_ids_isolation(self):
        """Verify different product IDs do not interfere with each other."""
        status1, body1 = call_endpoint("GET", "/data/product/alpha")
        status2, body2 = call_endpoint("GET", "/data/product/beta")

        self.assertEqual(status1, 200)
        self.assertEqual(status2, 200)
        self.assertEqual(body1["product_id"], "alpha")
        self.assertEqual(body2["product_id"], "beta")
        self.assertNotEqual(body1["product_id"], body2["product_id"])
        self.assertTrue(cache_manager.exists("product:alpha"))
        self.assertTrue(cache_manager.exists("product:beta"))

    def test_get_recommendation_api_flow(self):
        """Verify GET /data/recommendation/{id} lifecycle: MISS then HIT."""
        # Request 1: MISS
        status1, body1 = call_endpoint("GET", "/data/recommendation/user_test")
        self.assertEqual(status1, 200)
        self.assertEqual(body1["user_id"], "user_test")
        self.assertIsInstance(body1["recommendations"], list)
        self.assertGreater(len(body1["recommendations"]), 0)

        # Request 2: HIT
        status2, body2 = call_endpoint("GET", "/data/recommendation/user_test")
        self.assertEqual(status2, 200)
        self.assertEqual(body2, body1)

    def test_product_and_recommendation_namespace_isolation(self):
        """Verify that same ID used in product and recommendation routes do not collide."""
        status_prod, body_prod = call_endpoint("GET", "/data/product/999")
        status_rec, body_rec = call_endpoint("GET", "/data/recommendation/999")

        self.assertEqual(status_prod, 200)
        self.assertEqual(status_rec, 200)
        self.assertEqual(body_prod["product_id"], "999")
        self.assertEqual(body_rec["user_id"], "999")

        # Independent cache keys
        self.assertTrue(cache_manager.exists("product:999"))
        self.assertTrue(cache_manager.exists("recommendation:999"))
        meta_prod = cache_manager.get_metadata("product:999")
        meta_rec = cache_manager.get_metadata("recommendation:999")
        self.assertIsNotNone(meta_prod)
        self.assertIsNotNone(meta_rec)
        self.assertEqual(meta_prod.key, "product:999")
        self.assertEqual(meta_rec.key, "recommendation:999")


if __name__ == "__main__":
    unittest.main()
