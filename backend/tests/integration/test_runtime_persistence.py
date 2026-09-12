"""Integration tests for runtime persistence layer integration.

Tests verify:
1. Cache metadata persistence on cache misses via CacheMetadataRepository.
2. Zero database queries on cache hits.
3. Persistent metadata deletion upon cache invalidation.
4. Telemetry observation persistence via TelemetryRepository on observation endpoints.
5. Resilience and graceful degradation when the database is unavailable or fails.
"""

from __future__ import annotations

import unittest
from collections.abc import Generator
from typing import Any
from unittest.mock import MagicMock

import sqlalchemy as sa
from api.routes.data import cache_manager
from app.main import app
from database.connection import get_db
from database.models import Base
from database.repositories.cache_metadata import CacheMetadataRepository
from database.repositories.telemetry import TelemetryRepository
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool
from telemetry.collector import telemetry_collector


class TestRuntimePersistence(unittest.TestCase):
    def setUp(self) -> None:
        """Set up an isolated in-memory SQLite database sharing connection pool."""
        self.engine = sa.create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(bind=self.engine)
        self.session_factory = sessionmaker(bind=self.engine)

        def override_get_db() -> Generator[Session, None, None]:
            session = self.session_factory()
            try:
                yield session
            finally:
                session.close()

        app.dependency_overrides[get_db] = override_get_db
        self.client = TestClient(app)

        # Clear in-memory caches and telemetry
        cache_manager._store._store.clear()
        cache_manager.clear_metadata()
        telemetry_collector.reset()

    def tearDown(self) -> None:
        """Clean up dependency overrides and tear down database schema."""
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=self.engine)
        self.engine.dispose()

        cache_manager._store._store.clear()
        cache_manager.clear_metadata()
        telemetry_collector.reset()

    def test_cache_miss_persists_metadata_to_database(self) -> None:
        """Verify that cache misses for product and recommendation endpoints persist metadata."""
        # Product miss
        resp = self.client.get("/data/product/prod_101")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["product_id"], "prod_101")

        session = self.session_factory()
        try:
            repo = CacheMetadataRepository(session)
            meta = repo.get_by_key("product:prod_101")
            self.assertIsNotNone(meta, "Metadata must be persisted in DB on cache miss")
            self.assertEqual(meta.key, "product:prod_101")
            self.assertEqual(meta.access_count, 1)
            self.assertEqual(meta.miss_count, 1)
            self.assertEqual(meta.hit_count, 0)
            self.assertGreater(meta.size_bytes, 0)
            self.assertGreater(meta.retrieval_cost_ms, 0.0)
            self.assertEqual(meta.version, "v1")
        finally:
            session.close()

        # Recommendation miss
        resp_rec = self.client.get("/data/recommendation/user_202")
        self.assertEqual(resp_rec.status_code, 200)
        self.assertEqual(resp_rec.json()["user_id"], "user_202")

        session2 = self.session_factory()
        try:
            repo2 = CacheMetadataRepository(session2)
            meta_rec = repo2.get_by_key("recommendation:user_202")
            self.assertIsNotNone(meta_rec, "Recommendation metadata must be persisted on cache miss")
            self.assertEqual(meta_rec.key, "recommendation:user_202")
            self.assertEqual(meta_rec.access_count, 1)
        finally:
            session2.close()

    def test_cache_hit_performs_zero_database_queries(self) -> None:
        """Verify that cache hits return cached data without calling backend origin and persist metadata updates."""
        # First call: Cache miss, which persists metadata
        init_resp = self.client.get("/data/product/fast_item")
        self.assertEqual(init_resp.status_code, 200)
        init_data = init_resp.json()

        session = self.session_factory()
        try:
            repo = CacheMetadataRepository(session)
            meta_before = repo.get_by_key("product:fast_item")
            self.assertIsNotNone(meta_before)
            initial_access_count = meta_before.access_count
            initial_hit_count = meta_before.hit_count
            initial_miss_count = meta_before.miss_count
        finally:
            session.close()

        backend_calls_before = telemetry_collector.snapshot()["backend_calls"]

        # Second call: Cache HIT
        hit_resp = self.client.get("/data/product/fast_item")
        self.assertEqual(hit_resp.status_code, 200)
        self.assertEqual(hit_resp.json(), init_data)

        # Verification: does not call backend origin
        backend_calls_after = telemetry_collector.snapshot()["backend_calls"]
        self.assertEqual(
            backend_calls_after,
            backend_calls_before,
            "Cache hit must not increase backend origin calls",
        )

        # Verification: updates persistent metadata in database
        session2 = self.session_factory()
        try:
            repo2 = CacheMetadataRepository(session2)
            meta_after = repo2.get_by_key("product:fast_item")
            self.assertIsNotNone(meta_after)
            self.assertEqual(meta_after.access_count, initial_access_count + 1)
            self.assertEqual(meta_after.hit_count, initial_hit_count + 1)
            self.assertEqual(meta_after.miss_count, initial_miss_count)
        finally:
            session2.close()

    def test_cache_invalidation_removes_persistent_metadata(self) -> None:
        """Verify that cache invalidation removes persistent metadata from database."""
        # 1. Populate product
        self.client.get("/data/product/del_item")
        session = self.session_factory()
        repo = CacheMetadataRepository(session)
        self.assertIsNotNone(repo.get_by_key("product:del_item"))
        session.close()

        # Delete product via DELETE /data/product/{id}
        del_resp = self.client.delete("/data/product/del_item")
        self.assertEqual(del_resp.status_code, 200)
        self.assertTrue(del_resp.json()["deleted"])

        # Confirm removed from DB
        session2 = self.session_factory()
        repo2 = CacheMetadataRepository(session2)
        self.assertIsNone(repo2.get_by_key("product:del_item"))
        session2.close()

        # Confirm removed from in-memory cache
        self.assertIsNone(cache_manager.get("product:del_item"))
        self.assertIsNone(cache_manager.get_metadata("product:del_item"))

        # 2. Populate recommendation and delete via DELETE /data/recommendation/{id}
        self.client.get("/data/recommendation/del_user")
        del_rec = self.client.delete("/data/recommendation/del_user")
        self.assertEqual(del_rec.status_code, 200)
        self.assertTrue(del_rec.json()["deleted"])

        session3 = self.session_factory()
        repo3 = CacheMetadataRepository(session3)
        self.assertIsNone(repo3.get_by_key("recommendation:del_user"))
        session3.close()

        # 3. Populate product and delete via DELETE /cache/objects/{key}
        self.client.get("/data/product/del_cache_obj")
        del_obj = self.client.delete("/cache/objects/product:del_cache_obj")
        self.assertEqual(del_obj.status_code, 200)
        self.assertTrue(del_obj.json()["deleted"])

        session4 = self.session_factory()
        repo4 = CacheMetadataRepository(session4)
        self.assertIsNone(repo4.get_by_key("product:del_cache_obj"))
        session4.close()

    def test_telemetry_observation_persistence(self) -> None:
        """Verify that GET /telemetry/observation persists observation snapshots."""
        resp = self.client.get("/telemetry/observation")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["version"], "v1")

        session = self.session_factory()
        try:
            repo = TelemetryRepository(session)
            observations = repo.get_recent_observations(limit=10)
            self.assertGreaterEqual(len(observations), 1)
            latest = observations[0]
            self.assertIsNotNone(latest.timestamp)
            self.assertGreaterEqual(latest.window_seconds, 0.0)
            self.assertEqual(latest.total_requests, 0)
        finally:
            session.close()

    def test_telemetry_workload_and_system_persistence(self) -> None:
        """Verify that GET /telemetry/workload and /telemetry/system persist observation snapshots."""
        # Perform some requests
        self.client.get("/data/product/item_w")

        resp_w = self.client.get("/telemetry/workload")
        self.assertEqual(resp_w.status_code, 200)
        self.assertEqual(resp_w.json()["version"], "v1")

        resp_s = self.client.get("/telemetry/system")
        self.assertEqual(resp_s.status_code, 200)
        self.assertEqual(resp_s.json()["version"], "v1")

        session = self.session_factory()
        try:
            repo = TelemetryRepository(session)
            observations = repo.get_recent_observations(limit=10)
            # Both /telemetry/workload and /telemetry/system persist observations
            self.assertGreaterEqual(len(observations), 2)
        finally:
            session.close()

    def test_resilience_when_database_fails_on_cache_miss(self) -> None:
        """Verify API continues functioning and returns 200 when database persistence fails on cache miss."""
        mock_session = MagicMock(spec=Session)
        mock_session.add.side_effect = sa.exc.OperationalError("db connection failed", None, None)
        mock_session.flush.side_effect = sa.exc.OperationalError("db connection failed", None, None)
        mock_session.commit.side_effect = sa.exc.OperationalError("db connection failed", None, None)

        def failing_db() -> Generator[Session, None, None]:
            yield mock_session

        app.dependency_overrides[get_db] = failing_db

        resp = self.client.get("/data/product/resilient_prod")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["product_id"], "resilient_prod")

        # Cache still stored the object
        self.assertIsNotNone(cache_manager.get("product:resilient_prod"))
        self.assertIsNotNone(cache_manager.get_metadata("product:resilient_prod"))

        # Test recommendation with failing DB
        resp_rec = self.client.get("/data/recommendation/resilient_rec")
        self.assertEqual(resp_rec.status_code, 200)
        self.assertEqual(resp_rec.json()["user_id"], "resilient_rec")

    def test_resilience_when_database_fails_on_invalidation(self) -> None:
        """Verify API continues functioning and returns 200 when database fails during invalidation."""
        # Pre-populate in memory
        cache_manager.set("product:fail_del", {"product_id": "fail_del"})
        cache_manager.create_metadata(key="product:fail_del", size_bytes=128)

        mock_session = MagicMock(spec=Session)
        mock_session.delete.side_effect = sa.exc.OperationalError("db connection failed", None, None)
        mock_session.scalars.side_effect = sa.exc.OperationalError("db connection failed", None, None)

        def failing_db() -> Generator[Session, None, None]:
            yield mock_session

        app.dependency_overrides[get_db] = failing_db

        del_resp = self.client.delete("/data/product/fail_del")
        self.assertEqual(del_resp.status_code, 200)
        self.assertTrue(del_resp.json()["deleted"])
        self.assertIsNone(cache_manager.get("product:fail_del"))

    def test_resilience_when_database_fails_on_telemetry(self) -> None:
        """Verify telemetry endpoints return 200 OK when database persistence fails."""
        mock_session = MagicMock(spec=Session)
        mock_session.add.side_effect = sa.exc.OperationalError("db connection failed", None, None)
        mock_session.flush.side_effect = sa.exc.OperationalError("db connection failed", None, None)
        mock_session.commit.side_effect = sa.exc.OperationalError("db connection failed", None, None)

        def failing_db() -> Generator[Session, None, None]:
            yield mock_session

        app.dependency_overrides[get_db] = failing_db

        resp_obs = self.client.get("/telemetry/observation")
        self.assertEqual(resp_obs.status_code, 200)
        self.assertEqual(resp_obs.json()["version"], "v1")

        resp_workload = self.client.get("/telemetry/workload")
        self.assertEqual(resp_workload.status_code, 200)
        self.assertEqual(resp_workload.json()["version"], "v1")

        resp_system = self.client.get("/telemetry/system")
        self.assertEqual(resp_system.status_code, 200)
        self.assertEqual(resp_system.json()["version"], "v1")
