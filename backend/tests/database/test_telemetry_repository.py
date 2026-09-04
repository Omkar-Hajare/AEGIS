from datetime import datetime, timedelta, timezone
import unittest

import sqlalchemy as sa
from sqlalchemy.orm import Session, sessionmaker

from database.models import Base
from database.repositories.telemetry import TelemetryRepository
from telemetry.observation import Observation


class TestTelemetryRepository(unittest.TestCase):
    def setUp(self):
        """Set up an in-memory SQLite database and repository session for unit tests."""
        self.engine = sa.create_engine("sqlite:///:memory:")
        Base.metadata.create_all(bind=self.engine)
        self.session_factory = sessionmaker(bind=self.engine)
        self.session: Session = self.session_factory()
        self.repo = TelemetryRepository(self.session)

    def tearDown(self):
        """Tear down the session and tables."""
        self.session.close()
        Base.metadata.drop_all(bind=self.engine)
        self.engine.dispose()

    def test_save_and_retrieve_observation(self):
        """Verify persisting an Observation and retrieving it."""
        now = datetime(2026, 9, 4, 15, 30, 0, tzinfo=timezone.utc)
        obs = Observation(
            request_rate=12.5,
            hit_rate=0.75,
            miss_rate=0.25,
            backend_latency_ms=42.0,
            window_seconds=10.0,
            total_requests=100,
            cache_hits=75,
            cache_misses=25,
            backend_calls=25,
            current_window_access_counts={"item:1": 50, "item:2": 50},
            previous_window_access_counts={"item:1": 20},
            timestamp=now,
        )

        model = self.repo.save_observation(obs)
        self.session.commit()
        self.assertIsNotNone(model.id)

        recent = self.repo.get_recent_observations(limit=10)
        self.assertEqual(len(recent), 1)
        r0 = recent[0]
        self.assertEqual(r0.request_rate, 12.5)
        self.assertEqual(r0.hit_rate, 0.75)
        self.assertEqual(r0.miss_rate, 0.25)
        self.assertEqual(r0.backend_latency_ms, 42.0)
        self.assertEqual(r0.window_seconds, 10.0)
        self.assertEqual(r0.total_requests, 100)
        self.assertEqual(r0.cache_hits, 75)
        self.assertEqual(r0.cache_misses, 25)
        self.assertEqual(r0.backend_calls, 25)
        self.assertEqual(r0.current_window_access_counts, {"item:1": 50, "item:2": 50})
        self.assertEqual(r0.previous_window_access_counts, {"item:1": 20})

    def test_empty_repository_returns_empty_list(self):
        """Verify get_recent_observations returns empty list on empty database."""
        self.assertEqual(self.repo.get_recent_observations(), [])

    def test_multiple_observations_and_limit(self):
        """Verify retrieving with limit returns the specified count."""
        base_time = datetime(2026, 9, 4, 12, 0, 0, tzinfo=timezone.utc)
        for i in range(5):
            obs = Observation(
                request_rate=float(i),
                hit_rate=0.5,
                miss_rate=0.5,
                backend_latency_ms=10.0,
                window_seconds=1.0,
                total_requests=i * 10,
                cache_hits=i * 5,
                cache_misses=i * 5,
                backend_calls=i * 5,
                timestamp=base_time + timedelta(minutes=i),
            )
            self.repo.save_observation(obs)
        self.session.commit()

        recent_3 = self.repo.get_recent_observations(limit=3)
        self.assertEqual(len(recent_3), 3)

        all_5 = self.repo.get_recent_observations(limit=10)
        self.assertEqual(len(all_5), 5)

    def test_timestamp_ordering(self):
        """Verify observations are returned in descending timestamp order (most recent first)."""
        t1 = datetime(2026, 9, 4, 10, 0, 0, tzinfo=timezone.utc)
        t2 = datetime(2026, 9, 4, 11, 0, 0, tzinfo=timezone.utc)
        t3 = datetime(2026, 9, 4, 12, 0, 0, tzinfo=timezone.utc)

        for rate, t in [(1.0, t1), (3.0, t3), (2.0, t2)]:
            obs = Observation(
                request_rate=rate,
                hit_rate=0.0,
                miss_rate=0.0,
                backend_latency_ms=0.0,
                window_seconds=1.0,
                total_requests=0,
                cache_hits=0,
                cache_misses=0,
                backend_calls=0,
                timestamp=t,
            )
            self.repo.save_observation(obs)
        self.session.commit()

        results = self.repo.get_recent_observations(limit=10)
        self.assertEqual(len(results), 3)
        # Most recent first
        self.assertEqual(results[0].request_rate, 3.0)
        self.assertEqual(results[1].request_rate, 2.0)
        self.assertEqual(results[2].request_rate, 1.0)


if __name__ == "__main__":
    unittest.main()
