from datetime import datetime, timezone
from typing import Any

import sqlalchemy as sa
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class ProductModel(Base):
    """SQLAlchemy model representing a product stored in PostgreSQL."""

    __tablename__ = "products"

    product_id: Mapped[str] = mapped_column(
        sa.String(255),
        primary_key=True,
        index=True,
    )
    name: Mapped[str] = mapped_column(
        sa.String(255),
        nullable=False,
    )
    description: Mapped[str | None] = mapped_column(
        sa.Text,
        nullable=True,
    )
    price: Mapped[float] = mapped_column(
        sa.Float,
        default=0.0,
        nullable=False,
    )
    category: Mapped[str | None] = mapped_column(
        sa.String(255),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )


class RecommendationModel(Base):
    """SQLAlchemy model representing recommendations stored in PostgreSQL."""

    __tablename__ = "recommendations"

    user_id: Mapped[str] = mapped_column(
        sa.String(255),
        primary_key=True,
        index=True,
    )
    recommendations: Mapped[list[Any]] = mapped_column(
        sa.JSON,
        default=list,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )


class CacheMetadataModel(Base):
    """SQLAlchemy model representing persistent cache object metadata."""

    __tablename__ = "cache_metadata"

    key: Mapped[str] = mapped_column(
        sa.String(255),
        primary_key=True,
        index=True,
    )
    version: Mapped[str] = mapped_column(
        sa.String(32),
        default="v1",
        nullable=False,
    )
    size_bytes: Mapped[int] = mapped_column(
        sa.BigInteger,
        default=0,
        nullable=False,
    )
    access_count: Mapped[int] = mapped_column(
        sa.Integer,
        default=1,
        nullable=False,
    )
    last_accessed: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    retrieval_cost_ms: Mapped[float] = mapped_column(
        sa.Float,
        default=0.0,
        nullable=False,
    )
    hit_count: Mapped[int] = mapped_column(
        sa.Integer,
        default=0,
        nullable=False,
    )
    miss_count: Mapped[int] = mapped_column(
        sa.Integer,
        default=1,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    features: Mapped[dict[str, Any] | None] = mapped_column(
        sa.JSON,
        nullable=True,
    )
    # The database column is named "metadata"; attribute name is
    # metadata_payload to avoid collision with SQLAlchemy metadata.
    metadata_payload: Mapped[dict[str, Any] | None] = mapped_column(
        "metadata",
        sa.JSON,
        nullable=True,
    )


class TelemetryObservationModel(Base):
    """SQLAlchemy model representing persistent telemetry observations."""

    __tablename__ = "telemetry_observations"

    id: Mapped[int] = mapped_column(
        sa.Integer,
        primary_key=True,
        autoincrement=True,
    )
    timestamp: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        index=True,
        nullable=False,
    )
    window_seconds: Mapped[float] = mapped_column(
        sa.Float,
        default=0.0,
        nullable=False,
    )
    request_rate: Mapped[float] = mapped_column(
        sa.Float,
        default=0.0,
        nullable=False,
    )
    hit_rate: Mapped[float] = mapped_column(
        sa.Float,
        default=0.0,
        nullable=False,
    )
    miss_rate: Mapped[float] = mapped_column(
        sa.Float,
        default=0.0,
        nullable=False,
    )
    backend_latency_ms: Mapped[float] = mapped_column(
        sa.Float,
        default=0.0,
        nullable=False,
    )
    total_requests: Mapped[int] = mapped_column(
        sa.Integer,
        default=0,
        nullable=False,
    )
    cache_hits: Mapped[int] = mapped_column(
        sa.Integer,
        default=0,
        nullable=False,
    )
    cache_misses: Mapped[int] = mapped_column(
        sa.Integer,
        default=0,
        nullable=False,
    )
    backend_calls: Mapped[int] = mapped_column(
        sa.Integer,
        default=0,
        nullable=False,
    )
    current_window_access_counts: Mapped[dict[str, int]] = mapped_column(
        sa.JSON,
        default=dict,
        nullable=False,
    )
    previous_window_access_counts: Mapped[dict[str, int]] = mapped_column(
        sa.JSON,
        default=dict,
        nullable=False,
    )