import asyncio
from typing import Any
import unittest

from api.routes.data import cache_manager
from app.main import app
from telemetry.collector import telemetry_collector


def call_endpoint(method: str, path: str) -> tuple[int, str]:
    """In-process ASGI caller returning (status_code, body_string)."""
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
    return status_code, response_body.decode("utf-8")


class TestMetricsCardinality(unittest.TestCase):
    def setUp(self):
        """Reset cache and telemetry before each test."""
        cache_manager._store._store.clear()
        cache_manager.clear_metadata()
        telemetry_collector.reset()

    def test_metrics_endpoint_returns_200(self):
        """Confirm /metrics returns HTTP 200 and standard Prometheus exposition."""
        status, body = call_endpoint("GET", "/metrics")
        self.assertEqual(status, 200)
        self.assertIn("# HELP requests_total", body)
        self.assertIn("# HELP cache_hits_total", body)
        self.assertIn("# HELP cache_misses_total", body)

    def test_route_template_normalization_prevents_high_cardinality(self):
        """Confirm dynamic product/user IDs are normalized to route templates in metrics."""
        # Make requests with different dynamic IDs
        status1, _ = call_endpoint("GET", "/data/product/prod-999")
        status2, _ = call_endpoint("GET", "/data/product/prod-888")
        status3, _ = call_endpoint("GET", "/data/recommendation/user-aaa")
        status4, _ = call_endpoint("GET", "/data/recommendation/user-bbb")

        self.assertEqual(status1, 200)
        self.assertEqual(status2, 200)
        self.assertEqual(status3, 200)
        self.assertEqual(status4, 200)

        # Scrape /metrics
        status_m, body = call_endpoint("GET", "/metrics")
        self.assertEqual(status_m, 200)

        # Confirm normalized route template labels are present
        self.assertIn('endpoint="/data/product/{product_id}"', body)
        self.assertIn('endpoint="/data/recommendation/{user_id}"', body)

        # Confirm NO concrete IDs leak into endpoint labels
        self.assertNotIn('endpoint="/data/product/prod-999"', body)
        self.assertNotIn('endpoint="/data/product/prod-888"', body)
        self.assertNotIn('endpoint="/data/recommendation/user-aaa"', body)
        self.assertNotIn('endpoint="/data/recommendation/user-bbb"', body)

    def test_metrics_endpoint_excluded_from_instrumentation(self):
        """Confirm scraping /metrics does not instrument itself."""
        # Scrape metrics multiple times
        call_endpoint("GET", "/metrics")
        call_endpoint("GET", "/metrics")
        _, body = call_endpoint("GET", "/metrics")

        # Confirm endpoint="/metrics" is never recorded
        self.assertNotIn('endpoint="/metrics"', body)


if __name__ == "__main__":
    unittest.main()
