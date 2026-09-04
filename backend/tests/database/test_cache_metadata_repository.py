from datetime import datetime, timezone
import unittest

import sqlalchemy as sa
from sqlalchemy.orm import Session, sessionmaker

from cache.metadata import CacheObjectMetadata
from database.models import Base
from database.repositories.cache_metadata import CacheMetadataRepository


class TestCacheMetadataRepository(unittest.TestCase):
    def setUp(self):
        """Set up an in-memory SQLite database and repository session for unit tests."""
        self.engine = sa.create_engine("sqlite:///:memory:")
        Base.metadata.create_all(bind=self.engine)
        self.session_factory = sessionmaker(bind=self.engine)
        self.session: Session = self.session_factory()
        self.repo = CacheMetadataRepository(self.session)

    def tearDown(self):
        """Tear down the session and tables."""
        self.session.close()
        Base.metadata.drop_all(bind=self.engine)
        self.engine.dispose()

    def test_insert_and_read(self):
        """Verify inserting metadata and retrieving it by key."""
        meta = CacheObjectMetadata(
            key="product:101",
            size_bytes=256,
            retrieval_cost_ms=35.5,
            access_count=1,
            hit_count=0,
            miss_count=1,
        )
        self.repo.save(meta)
        self.session.commit()

        retrieved = self.repo.get_by_key("product:101")
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.key, "product:101")
        self.assertEqual(retrieved.size_bytes, 256)
        self.assertEqual(retrieved.retrieval_cost_ms, 35.5)
        self.assertEqual(retrieved.access_count, 1)
        self.assertEqual(retrieved.hit_count, 0)
        self.assertEqual(retrieved.miss_count, 1)
        self.assertEqual(retrieved.version, "v1")

    def test_update_existing_metadata(self):
        """Verify saving an updated metadata object mutates the existing row."""
        meta = CacheObjectMetadata(
            key="product:102",
            size_bytes=100,
            retrieval_cost_ms=20.0,
            access_count=1,
            hit_count=0,
            miss_count=1,
        )
        self.repo.save(meta)
        self.session.commit()

        # Update metadata object
        meta.record_hit()
        meta.record_backend_retrieval(45.0)
        self.repo.save(meta)
        self.session.commit()

        updated = self.repo.get_by_key("product:102")
        self.assertIsNotNone(updated)
        self.assertEqual(updated.access_count, 2)
        self.assertEqual(updated.hit_count, 1)
        self.assertEqual(updated.retrieval_cost_ms, 45.0)

    def test_delete_existing_key(self):
        """Verify deleting an existing key returns True and removes the record."""
        meta = CacheObjectMetadata(key="to_delete", size_bytes=64)
        self.repo.save(meta)
        self.session.commit()

        self.assertTrue(self.repo.delete("to_delete"))
        self.session.commit()

        self.assertIsNone(self.repo.get_by_key("to_delete"))

    def test_delete_missing_key(self):
        """Verify deleting an absent key returns False without error."""
        self.assertFalse(self.repo.delete("missing_key"))

    def test_get_missing_key_returns_none(self):
        """Verify get_by_key on a non-existent key returns None."""
        self.assertIsNone(self.repo.get_by_key("unknown_key"))

    def test_get_all_multiple_records(self):
        """Verify get_all returns all persisted metadata objects."""
        m1 = CacheObjectMetadata(key="item:1", size_bytes=10)
        m2 = CacheObjectMetadata(key="item:2", size_bytes=20)
        m3 = CacheObjectMetadata(key="item:3", size_bytes=30)
        self.repo.save(m1)
        self.repo.save(m2)
        self.repo.save(m3)
        self.session.commit()

        all_records = self.repo.get_all()
        self.assertEqual(len(all_records), 3)
        keys = [r.key for r in all_records]
        self.assertEqual(keys, ["item:1", "item:2", "item:3"])

    def test_json_fields_features_and_metadata(self):
        """Verify storing and retrieving complex JSON dictionary fields."""
        features_dict = {"popularity": 0.95, "category": "electronics", "tags": ["sale", "featured"]}
        custom_metadata = {"source": "catalog_v2", "owner": "team_alpha"}

        meta = CacheObjectMetadata(
            key="product:rich",
            size_bytes=512,
            features=features_dict,
            metadata=custom_metadata,
        )
        self.repo.save(meta)
        self.session.commit()

        retrieved = self.repo.get_by_key("product:rich")
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.features, features_dict)
        self.assertEqual(retrieved.metadata, custom_metadata)

    def test_utc_timestamps_preserved(self):
        """Verify UTC timestamps are stored and retrieved."""
        now = datetime(2026, 9, 4, 12, 0, 0, tzinfo=timezone.utc)
        meta = CacheObjectMetadata(
            key="product:timestamped",
            size_bytes=128,
            created_at=now,
            last_accessed=now,
        )
        self.repo.save(meta)
        self.session.commit()

        retrieved = self.repo.get_by_key("product:timestamped")
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.created_at.year, 2026)
        self.assertEqual(retrieved.last_accessed.year, 2026)


if __name__ == "__main__":
    unittest.main()
