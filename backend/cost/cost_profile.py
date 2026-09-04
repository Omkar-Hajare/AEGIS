"""Configurable economic cost profile for the Adaptive Cache System.

Represents economic parameters for backends and caching tiers (e.g. database
retrieval overhead, network API latency, RAM retention cost) without coupling
adaptive caching intelligence to specific infrastructure platforms.

Note:
    All cost metrics and profile parameters represent configurable, simulated
    economic models for algorithmic decision-making and benchmark demonstrations.
    They do NOT represent actual or contractual vendor/cloud pricing.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any


class CostModelValidationError(ValueError, TypeError):
    """Raised when an argument passed to the cost model or cost profile is invalid."""


@dataclass(frozen=True)
class CostProfile:
    """Configurable, immutable platform economic profile for adaptive caching.

    Attributes:
        name: Non-empty identifier for the platform profile (e.g. 'postgresql').
        backend_cost_per_request: Fixed overhead cost incurred per avoided backend
            regeneration request (e.g. connection/query dispatch overhead).
            Must be finite and >= 0.0.
        backend_cost_per_ms: Variable cost incurred per millisecond of backend
            retrieval time. Must be finite and >= 0.0.
        cache_memory_cost_per_gb_hour: Cost rate per decimal gigabyte-hour of cache
            RAM retention. Must be finite and >= 0.0.
        metadata: Optional read-only mapping containing descriptive profile metadata.
    """

    name: str
    backend_cost_per_request: float = 0.0
    backend_cost_per_ms: float = 1.0
    cache_memory_cost_per_gb_hour: float = 0.10
    metadata: Mapping[str, Any] | None = None

    def __post_init__(self) -> None:
        """Validate all fields upon initialization."""
        # 1. Validate name
        if isinstance(self.name, bool) or not isinstance(self.name, str):
            raise CostModelValidationError(
                f"name must be a non-empty string, got {type(self.name).__name__}"
            )
        if not self.name.strip():
            raise CostModelValidationError("name must not be empty or whitespace")

        # 2. Validate numeric cost parameters
        cost_fields = (
            ("backend_cost_per_request", self.backend_cost_per_request),
            ("backend_cost_per_ms", self.backend_cost_per_ms),
            ("cache_memory_cost_per_gb_hour", self.cache_memory_cost_per_gb_hour),
        )
        for field_name, val in cost_fields:
            if isinstance(val, bool) or not isinstance(val, (int, float)):
                raise CostModelValidationError(
                    f"{field_name} must be numeric, got {type(val).__name__}"
                )
            if not math.isfinite(val):
                raise CostModelValidationError(
                    f"{field_name} must be finite, got {val}"
                )
            if val < 0.0:
                raise CostModelValidationError(
                    f"{field_name} must be non-negative, got {val}"
                )
            object.__setattr__(self, field_name, float(val))

        # 3. Validate metadata
        if self.metadata is not None:
            if not isinstance(self.metadata, Mapping):
                raise CostModelValidationError(
                    f"metadata must be a mapping or None, got {type(self.metadata).__name__}"
                )
            object.__setattr__(self, "metadata", dict(self.metadata))
