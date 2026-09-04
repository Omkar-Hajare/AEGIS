import os
import unittest

import sqlalchemy as sa

from app.config import Settings
from cache.metadata import CacheObjectMetadata
from database.connection import (
    create_tables,
    drop_tables,
    get_database_url,
    get_db_session,
    get_engine,
    reset_engine,
)
from database.models import Base
from database.repositories.cache_metadata import CacheMetadataRepository
from database.repositories.telemetry import TelemetryRepository
from telemetry.observation import Observation


class TestPostgresIntegration(unittest.TestCase):
    def setUp(self):
        """Set up an integration test database."""
        # Use a temporary SQLite database to test the full SQLAlchemy integration pipeline offline
        self.test_url = "sqlite:///:memory:"
        self.engine = get_engine(url=self.test_url)
        create_tables(self.engine)

    def tearDown(self):
        """Clean up tables and reset engine."""
        drop_tables(self.engine)
        reset_engine()

    def test_database_url_builder(self):
        """Verify get_database_url generates valid PostgreSQL connection strings."""
        settings = Settings(
            database_host="pg.internal",
            database_port=5433,
            database_name="test_db",
            database_user="usr",
            database_password="pwd",
        )
        url = get_database_url(settings)
        self.assertEqual(url, "postgresql+psycopg://usr:pwd@pg.internal:5433/test_db")

    def test_database_url_direct_override(self):
        """Verify database_url setting overrides individual component settings."""
        settings = Settings(database_url="sqlite:///custom.db")
        self.assertEqual(get_database_url(settings), "sqlite:///custom.db")

    def test_table_creation_and_schema_inspection(self):
        """Verify all declared tables are created in the database schema."""
        inspector = sa.inspect(self.engine)
        tables = inspector.get_table_names()
        self.assertIn("cache_metadata", tables)
        self.assertIn("telemetry_observations", tables)

        columns = {col["name"] for col in inspector.get_columns("cache_metadata")}
        self.assertIn("key", columns)
        self.assertIn("metadata", columns)
        self.assertIn("features", columns)
        self.assertIn("size_bytes", columns)

    def test_cache_metadata_persistence_integration(self):
        """Verify end-to-end insert, read, update, delete with session context manager."""
        with get_db_session(self.engine) as session:
            repo = CacheMetadataRepository(session)
            meta = CacheObjectMetadata(
                key="product:pg_test",
                size_bytes=1024,
                retrieval_cost_ms=50.0,
                access_count=1,
                hit_count=0,
                miss_count=1,
            )
            repo.save(meta)

        # Read back in a separate session
        with get_db_session(self.engine) as session:
            repo = CacheMetadataRepository(session)
            fetched = repo.get_by_key("product:pg_test")
            self.assertIsNotNone(fetched)
            self.assertEqual(fetched.size_bytes, 1024)

            # Update
            fetched.record_hit()
            repo.save(fetched)

        # Verify update persisted
        with get_db_session(self.engine) as session:
            repo = CacheMetadataRepository(session)
            updated = repo.get_by_key("product:pg_test")
            self.assertIsNotNone(updated)
            self.assertEqual(updated.hit_count, 1)
            self.assertEqual(updated.access_count, 2)

            # Delete
            self.assertTrue(repo.delete("product:pg_test"))

        # Verify deletion persisted
        with get_db_session(self.engine) as session:
            repo = CacheMetadataRepository(session)
            self.assertIsNone(repo.get_by_key("product:pg_test"))

    def test_telemetry_persistence_integration(self):
        """Verify end-to-end telemetry save and retrieval across session boundaries."""
        with get_db_session(self.engine) as session:
            repo = TelemetryRepository(session)
            obs = Observation(
                request_rate=20.0,
                hit_rate=0.9,
                miss_rate=0.1,
                backend_latency_ms=25.0,
                window_seconds=60.0,
                total_requests=200,
                cache_hits=180,
                cache_misses=20,
                backend_calls=20,
                current_window_access_counts={"item:x": 100},
            )
            repo.save_observation(obs)

        # Read back in a separate session
        with get_db_session(self.engine) as session:
            repo = TelemetryRepository(session)
            recent = repo.get_recent_observations(limit=5)
            self.assertEqual(len(recent), 1)
            self.assertEqual(recent[0].total_requests, 200)
            self.assertEqual(recent[0].current_window_access_counts, {"item:x": 100})

    def test_real_postgres_connection_if_available(self):
        """Test against real PostgreSQL if host/port is reachable, or skip gracefully."""
        pg_url = get_database_url()
        try:
            pg_engine = sa.create_engine(pg_url, connect_args={"connect_timeout": 1})
            with pg_engine.connect() as conn:
                result = conn.execute(sa.text("SELECT 1"))
                self.assertEqual(result.scalar(), 1)
        except Exception as e:
            self.skipTest(f"Real PostgreSQL server not accessible ({e}); skipping live network ping.")


if __name__ == "__main__":
    unittest.main()
