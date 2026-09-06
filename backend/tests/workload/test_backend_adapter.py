"""Unit tests for the BackendAdapter abstraction and factory.

Verifies:
- SimulatedBackendAdapter and AmazonLikeAdapter both implement BackendAdapter.
- The factory defaults to the simulated adapter and honors DATA_BACKEND.
- An unsupported DATA_BACKEND value fails clearly.
- AdaptiveService can still produce a Decision regardless of which adapter
  served the underlying data (the adaptive layer never touches BackendAdapter).
"""

from __future__ import annotations

import unittest
from datetime import datetime, timezone

from adaptive.service import AdaptiveService
from app.config import Settings
from cache.in_memory import InMemoryCache
from cache.manager import CacheManager
from cache.metadata import calculate_payload_size_bytes
from telemetry.collector import TelemetryCollector
from workload.adapter import BackendAdapter
from workload.amazon_like import AmazonLikeAdapter
from workload.factory import get_backend_adapter
from workload.simulated import SimulatedBackendAdapter

from contracts.schemas import Decision


class TestBackendAdapterImplementations(unittest.TestCase):
    def test_simulated_adapter_implements_interface(self):
        adapter = SimulatedBackendAdapter()
        self.assertIsInstance(adapter, BackendAdapter)
        product = adapter.get_product("101")
        self.assertEqual(product["product_id"], "101")
        recommendation = adapter.get_recommendation("user_test")
        self.assertIsInstance(recommendation["recommendations"], list)

    def test_amazon_like_adapter_implements_interface(self):
        adapter = AmazonLikeAdapter()
        self.assertIsInstance(adapter, BackendAdapter)
        product = adapter.get_product("101")
        self.assertEqual(product["product_id"], "101")
        recommendation = adapter.get_recommendation("user_test")
        self.assertIsInstance(recommendation["recommendations"], list)


class TestBackendAdapterFactory(unittest.TestCase):
    def test_default_factory_returns_simulated_adapter(self):
        adapter = get_backend_adapter()
        self.assertIsInstance(adapter, SimulatedBackendAdapter)

    def test_factory_simulated_explicit(self):
        custom_settings = Settings(data_backend="simulated")
        adapter = get_backend_adapter(custom_settings)
        self.assertIsInstance(adapter, SimulatedBackendAdapter)

    def test_factory_amazon_like_selection(self):
        custom_settings = Settings(data_backend="amazon_like")
        adapter = get_backend_adapter(custom_settings)
        self.assertIsInstance(adapter, AmazonLikeAdapter)

    def test_factory_unsupported_backend_raises(self):
        bad_settings = Settings(data_backend="flipkart_like")
        with self.assertRaises(ValueError) as ctx:
            get_backend_adapter(bad_settings)
        self.assertIn("Unsupported data backend", str(ctx.exception))


class TestAdaptiveServiceIndependentOfBackendAdapter(unittest.TestCase):
    """Proves the adaptive layer produces a Decision regardless of which
    BackendAdapter served the cached payload -- AdaptiveService/DecisionEngine
    never import or depend on BackendAdapter."""

    def _run_decision_for_adapter(self, adapter: BackendAdapter) -> Decision:
        now = datetime(2026, 9, 5, 12, 0, 0, tzinfo=timezone.utc)
        cache_manager = CacheManager(InMemoryCache())
        collector = TelemetryCollector(time_provider=lambda: now)

        payload = adapter.get_product("101")
        cache_key = "product:101"
        cache_manager.set(cache_key, payload)
        cache_manager.create_metadata(
            key=cache_key,
            size_bytes=calculate_payload_size_bytes(payload),
            retrieval_cost_ms=30.0,
        )
        collector.record_request()
        collector.record_cache_miss()
        collector.record_backend_call(30.0)

        service = AdaptiveService(
            cache_manager=cache_manager,
            telemetry_collector=collector,
        )
        return service.decide(
            now=now,
            min_capacity_bytes=1_000,
            max_capacity_bytes=10_000_000,
        )

    def test_decision_produced_with_simulated_adapter(self):
        decision = self._run_decision_for_adapter(SimulatedBackendAdapter())
        self.assertIsInstance(decision, Decision)

    def test_decision_produced_with_amazon_like_adapter(self):
        decision = self._run_decision_for_adapter(AmazonLikeAdapter())
        self.assertIsInstance(decision, Decision)


if __name__ == "__main__":
    unittest.main()
