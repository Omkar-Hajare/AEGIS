from typing import Any

import sqlalchemy as sa
from sqlalchemy.orm import Session

from cache.metadata import CacheObjectMetadata
from database.models import CacheMetadataModel


class CacheMetadataRepository:
    """Repository for persisting and querying CacheObjectMetadata records."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def save(self, metadata: CacheObjectMetadata) -> CacheMetadataModel:
        """Save or update a CacheObjectMetadata entity in the database."""
        stmt = sa.select(CacheMetadataModel).where(CacheMetadataModel.key == metadata.key)
        model = self.session.scalars(stmt).first()

        if model is None:
            model = CacheMetadataModel(
                key=metadata.key,
                version=metadata.version,
                size_bytes=metadata.size_bytes,
                access_count=metadata.access_count,
                last_accessed=metadata.last_accessed,
                retrieval_cost_ms=metadata.retrieval_cost_ms,
                hit_count=metadata.hit_count,
                miss_count=metadata.miss_count,
                created_at=metadata.created_at,
                features=metadata.features,
                metadata_payload=metadata.metadata,
            )
            self.session.add(model)
        else:
            model.version = metadata.version
            model.size_bytes = metadata.size_bytes
            model.access_count = metadata.access_count
            model.last_accessed = metadata.last_accessed
            model.retrieval_cost_ms = metadata.retrieval_cost_ms
            model.hit_count = metadata.hit_count
            model.miss_count = metadata.miss_count
            model.features = metadata.features
            model.metadata_payload = metadata.metadata

        self.session.flush()
        return model

    def get_by_key(self, key: str) -> CacheObjectMetadata | None:
        """Retrieve metadata for a specific key, returning CacheObjectMetadata or None."""
        stmt = sa.select(CacheMetadataModel).where(CacheMetadataModel.key == key)
        model = self.session.scalars(stmt).first()
        if model is None:
            return None
        return self._to_domain(model)

    def get_all(self) -> list[CacheObjectMetadata]:
        """Retrieve all metadata records as domain CacheObjectMetadata objects."""
        stmt = sa.select(CacheMetadataModel).order_by(CacheMetadataModel.key)
        models = self.session.scalars(stmt).all()
        return [self._to_domain(m) for m in models]

    def delete(self, key: str) -> bool:
        """Delete metadata by key. Returns True if existed and deleted, False otherwise."""
        stmt = sa.select(CacheMetadataModel).where(CacheMetadataModel.key == key)
        model = self.session.scalars(stmt).first()
        if model is None:
            return False
        self.session.delete(model)
        self.session.flush()
        return True

    @staticmethod
    def _to_domain(model: CacheMetadataModel) -> CacheObjectMetadata:
        """Convert a database model to the domain CacheObjectMetadata dataclass."""
        return CacheObjectMetadata(
            key=model.key,
            size_bytes=model.size_bytes,
            retrieval_cost_ms=model.retrieval_cost_ms,
            version=model.version,
            access_count=model.access_count,
            hit_count=model.hit_count,
            miss_count=model.miss_count,
            created_at=model.created_at,
            last_accessed=model.last_accessed,
            features=model.features,
            metadata=model.metadata_payload,
        )
