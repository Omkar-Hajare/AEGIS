"""Unit tests for GET /cache/objects route."""

import asyncio
import json
import unittest
from typing import Any

from api.routes.data import cache_manager
from app.main import app
from cache.metadata import CacheObjectMetadata
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


class TestCacheObjectsAPI(unittest.TestCase):
    def setUp(self):
        """Reset cache and telemetry before each test for clean isolation."""
        cache_manager._store._store.clear()
        cache_manager.clear_metadata()
        telemetry_collector.reset()

    def test_get_cache_objects_empty(self):
        """Verify GET /cache/objects returns empty list when cache has no resident objects."""
        status, body = call_endpoint("GET", "/cache/objects")
        self.assertEqual(status, 200)
        self.assertEqual(body.get("object_count"), 0)
        self.assertEqual(body.get("objects"), [])

    def test_get_cache_objects_resident_metadata(self):
        """Verify GET /cache/objects includes resident objects populated via data routes."""
        # Request product to populate cache and create metadata
        status_p, _body_p = call_endpoint("GET", "/data/product/test_item")
        self.assertEqual(status_p, 200)

        # Inspect cache objects endpoint
        status, body = call_endpoint("GET", "/cache/objects")
        self.assertEqual(status, 200)
        self.assertEqual(body.get("object_count"), 1)
        objects = body.get("objects", [])
        self.assertEqual(len(objects), 1)

        item = objects[0]
        self.assertEqual(item["key"], "product:test_item")
        self.assertGreater(item["size_bytes"], 0)
        self.assertEqual(item["access_count"], 1)
        self.assertEqual(item["hit_count"], 0)
        self.assertEqual(item["miss_count"], 1)
        self.assertIn("created_at", item)
        self.assertIn("last_accessed", item)
        self.assertIn("version", item)

    def test_get_cache_objects_hit_increments_counts(self):
        """Verify cache hits properly update access_count and hit_count in GET /cache/objects."""
        call_endpoint("GET", "/data/product/hit_item")
        call_endpoint("GET", "/data/product/hit_item")  # Second call = HIT

        status, body = call_endpoint("GET", "/cache/objects")
        self.assertEqual(status, 200)
        item = body["objects"][0]
        self.assertEqual(item["key"], "product:hit_item")
        self.assertEqual(item["access_count"], 2)
        self.assertEqual(item["hit_count"], 1)
        self.assertEqual(item["miss_count"], 1)

    def test_orphan_metadata_excluded_when_not_resident(self):
        """Verify that metadata for keys not resident in the underlying store is excluded."""
        # Manually inject metadata without storing in store
        orphan_meta = CacheObjectMetadata(
            key="orphan:ghost_key",
            size_bytes=1024,
            retrieval_cost_ms=15.0,
        )
        cache_manager.set_metadata("orphan:ghost_key", orphan_meta)

        # Also store a real resident key
        cache_manager.set("resident:real_key", {"data": "real"})
        real_meta = CacheObjectMetadata(
            key="resident:real_key",
            size_bytes=512,
            retrieval_cost_ms=10.0,
        )
        cache_manager.set_metadata("resident:real_key", real_meta)

        # GET /cache/objects should ONLY return the resident key
        status, body = call_endpoint("GET", "/cache/objects")
        self.assertEqual(status, 200)
        self.assertEqual(body.get("object_count"), 1)
        keys = [obj["key"] for obj in body.get("objects", [])]
        self.assertIn("resident:real_key", keys)
        self.assertNotIn("orphan:ghost_key", keys)


if __name__ == "__main__":
    unittest.main()
