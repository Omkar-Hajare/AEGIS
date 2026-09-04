"""Base workload scenario interface."""

from __future__ import annotations

import random
from abc import ABC, abstractmethod

from backend.workload.scenario import ScenarioConfig, ScenarioEvent


class BaseScenario(ABC):
    """Abstract base class for deterministic synthetic workload scenarios."""

    @abstractmethod
    def generate(
        self, config: ScenarioConfig, rng: random.Random
    ) -> list[ScenarioEvent]:
        """Generate a deterministic sequence of ScenarioEvents based on config and RNG.

        Args:
            config: Validated ScenarioConfig defining generation parameters.
            rng: Injected random.Random instance seeded for determinism.

        Returns:
            List of generated ScenarioEvent instances.
        """
