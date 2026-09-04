from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
from typing import Any


def calculate_payload_size_bytes(payload: Any) -> int:
    """Calculate serialized payload size in UTF-8 bytes for JSON-compatible structures.

    This represents the logical serialized payload size, not internal memory overhead.
    """
    if isinstance(payload, bytes):
        return len(payload)
    if isinstance(payload, str):
        return len(payload.encode("utf-8"))
    encoded = json.dumps(payload, sort_keys=True).encode("utf-8")
    return len(encoded)


@dataclass
class CacheObjectMetadata:
    """Tracks backend-side metadata for a single cached object."""

    key: str
    size_bytes: int = 0
    retrieval_cost_ms: float = 0.0
    version: str = "v1"
    access_count: int = 1
    hit_count: int = 0
    miss_count: int = 1
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_accessed: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    features: dict[str, Any] | None = None
    metadata: dict[str, Any] | None = None

    def record_access(self, now: datetime | None = None) -> None:
        """Record a general access to this object."""
        self.access_count += 1
        self.last_accessed = now or datetime.now(timezone.utc)

    def record_hit(self, now: datetime | None = None) -> None:
        """Record a cache HIT: increment access_count and hit_count."""
        self.access_count += 1
        self.hit_count += 1
        self.last_accessed = now or datetime.now(timezone.utc)

    def record_miss(self, now: datetime | None = None) -> None:
        """Record a cache MISS: increment access_count and miss_count."""
        self.access_count += 1
        self.miss_count += 1
        self.last_accessed = now or datetime.now(timezone.utc)

    def record_backend_retrieval(self, latency_ms: float) -> None:
        """Update the measured retrieval latency from the backend."""
        self.retrieval_cost_ms = latency_ms
