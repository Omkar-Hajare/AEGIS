"""Focused API integration tests for the /adaptive route."""

from __future__ import annotations

import unittest
from datetime import datetime, timezone
from unittest.mock import MagicMock

from api.routes.adaptive import (
    get_adaptive_service,
    get_decision_engine,
    runtime_cache_manager,
    runtime_telemetry_collector,
)
from app.main import app
from fastapi.testclient import TestClient

from contracts.schemas import (
    CapacityAction,
    Decision,
    WorkloadType,
)


class TestAdaptiveRoutes(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)
        self.now = datetime(2026, 9, 5, 12, 0, 0, tzinfo=timezone.utc)
        self.now_iso = self.now.isoformat()

        self.valid_workload = {
            "request_rate": 150.0,
            "hit_rate": 0.85,
            "miss_rate": 0.15,
            "backend_latency_ms": 30.0,
            "workload_type": WorkloadType.STEADY.value,
            "timestamp": self.now_iso,
            "window_seconds": 60.0,
        }

        self.valid_system = {
            "cache_capacity_bytes": 5000,
            "cache_usage_bytes": 2000,
            "object_count": 2,
            "timestamp": self.now_iso,
            "window_seconds": 60.0,
        }

        self.valid_objects_dict = {
            "obj:1": {
                "key": "obj:1",
                "size_bytes": 1000,
                "access_count": 20,
                "last_accessed": self.now_iso,
                "retrieval_cost_ms": 25.0,
            },
            "obj:2": {
                "key": "obj:2",
                "size_bytes": 1000,
                "access_count": 5,
                "last_accessed": self.now_iso,
                "retrieval_cost_ms": 40.0,
            },
        }

    def tearDown(self) -> None:
        app.dependency_overrides.clear()
        for key in list(runtime_cache_manager.get_all_metadata().keys()):
            runtime_cache_manager.delete(key)
        runtime_telemetry_collector.reset()

    def test_post_decision_success_with_dict_objects(self) -> None:
        """Verify POST /adaptive/decision succeeds and returns a valid Decision contract."""
        payload = {
            "objects": self.valid_objects_dict,
            "workload": self.valid_workload,
            "system": self.valid_system,
            "min_capacity_bytes": 1000,
            "max_capacity_bytes": 10000,
            "now": self.now_iso,
        }
        response = self.client.post("/adaptive/decision", json=payload)
        self.assertEqual(response.status_code, 200)

        data = response.json()
        self.assertEqual(data["version"], "v1")
        self.assertIn("object_scores", data)
        self.assertIn("eviction_keys", data)
        self.assertIn("capacity_action", data)
        self.assertIn("recommended_capacity_bytes", data)
        self.assertIn("reason", data)
        self.assertIn("timestamp", data)
        self.assertIn("metadata", data)
        self.assertIn("obj:1", data["object_scores"])
        self.assertIn("obj:2", data["object_scores"])

    def test_post_decision_success_with_list_objects(self) -> None:
        """Verify POST /adaptive/decision accepts objects as a list."""
        objects_list = list(self.valid_objects_dict.values())
        payload = {
            "objects": objects_list,
            "workload": self.valid_workload,
            "system": self.valid_system,
            "min_capacity_bytes": 1000,
            "max_capacity_bytes": 10000,
        }
        response = self.client.post("/adaptive/decision", json=payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("obj:1", data["object_scores"])
        self.assertIn("obj:2", data["object_scores"])

    def test_post_decision_empty_objects(self) -> None:
        """Verify POST /adaptive/decision works with empty candidate objects."""
        payload = {
            "objects": {},
            "workload": self.valid_workload,
            "system": {
                "cache_capacity_bytes": 5000,
                "cache_usage_bytes": 0,
                "object_count": 0,
                "timestamp": self.now_iso,
                "window_seconds": 60.0,
            },
            "min_capacity_bytes": 1000,
            "max_capacity_bytes": 10000,
        }
        response = self.client.post("/adaptive/decision", json=payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["object_scores"], {})
        self.assertEqual(data["eviction_keys"], [])

    def test_post_decision_invalid_min_capacity_zero_or_negative(self) -> None:
        """Verify min_capacity_bytes <= 0 is rejected with HTTP 422."""
        for invalid_min in (0, -1, -500):
            payload = {
                "objects": self.valid_objects_dict,
                "workload": self.valid_workload,
                "system": self.valid_system,
                "min_capacity_bytes": invalid_min,
                "max_capacity_bytes": 10000,
            }
            response = self.client.post("/adaptive/decision", json=payload)
            self.assertEqual(response.status_code, 422)

    def test_post_decision_invalid_max_capacity_zero_or_negative(self) -> None:
        """Verify max_capacity_bytes <= 0 is rejected with HTTP 422."""
        for invalid_max in (0, -100):
            payload = {
                "objects": self.valid_objects_dict,
                "workload": self.valid_workload,
                "system": self.valid_system,
                "min_capacity_bytes": 500,
                "max_capacity_bytes": invalid_max,
            }
            response = self.client.post("/adaptive/decision", json=payload)
            self.assertEqual(response.status_code, 422)

    def test_post_decision_min_greater_than_max_capacity(self) -> None:
        """Verify min_capacity_bytes > max_capacity_bytes is rejected with HTTP 422."""
        payload = {
            "objects": self.valid_objects_dict,
            "workload": self.valid_workload,
            "system": self.valid_system,
            "min_capacity_bytes": 5000,
            "max_capacity_bytes": 2000,
        }
        response = self.client.post("/adaptive/decision", json=payload)
        self.assertEqual(response.status_code, 422)

    def test_post_decision_boolean_capacity_rejected(self) -> None:
        """Verify boolean values for capacity fields are rejected with HTTP 422."""
        payload = {
            "objects": self.valid_objects_dict,
            "workload": self.valid_workload,
            "system": self.valid_system,
            "min_capacity_bytes": True,
            "max_capacity_bytes": 10000,
        }
        response = self.client.post("/adaptive/decision", json=payload)
        self.assertEqual(response.status_code, 422)

    def test_post_decision_missing_required_fields(self) -> None:
        """Verify omitting required fields returns HTTP 422."""
        payload = {
            "objects": self.valid_objects_dict,
            "workload": self.valid_workload,
            "min_capacity_bytes": 1000,
            "max_capacity_bytes": 5000,
        }
        response = self.client.post("/adaptive/decision", json=payload)
        self.assertEqual(response.status_code, 422)

    def test_post_decision_dependency_injection_override(self) -> None:
        """Verify DecisionEngine can be mocked/injected via FastAPI dependency_overrides."""
        mock_engine = MagicMock()
        mock_decision = Decision(
            object_scores={"mock:1": 0.99},
            eviction_keys=["mock:1"],
            capacity_action=CapacityAction.MAINTAIN,
            recommended_capacity_bytes=5000,
            reason="Mock decision for test",
            decision_id="dec_mock_123",
            timestamp=self.now,
            metadata={"mocked": True},
        )
        mock_engine.decide.return_value = mock_decision

        app.dependency_overrides[get_decision_engine] = lambda: mock_engine

        payload = {
            "objects": self.valid_objects_dict,
            "workload": self.valid_workload,
            "system": self.valid_system,
            "min_capacity_bytes": 1000,
            "max_capacity_bytes": 10000,
        }
        response = self.client.post("/adaptive/decision", json=payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()

        self.assertEqual(data["decision_id"], "dec_mock_123")
        self.assertEqual(data["object_scores"], {"mock:1": 0.99})
        self.assertEqual(data["eviction_keys"], ["mock:1"])
        self.assertEqual(data["metadata"], {"mocked": True})
        mock_engine.decide.assert_called_once()

    # -----------------------------------------------------------------------
    # GET /adaptive/runtime-decision tests
    # -----------------------------------------------------------------------

    def test_get_runtime_decision_success_200_and_schema(self) -> None:
        """Verify GET /adaptive/runtime-decision returns 200 and a valid Decision contract."""
        response = self.client.get("/adaptive/runtime-decision")
        self.assertEqual(response.status_code, 200)

        data = response.json()
        self.assertEqual(data["version"], "v1")
        self.assertIn("decision_id", data)
        self.assertTrue(data["decision_id"].startswith("dec-"))
        self.assertIn("capacity_action", data)
        self.assertIn("recommended_capacity_bytes", data)
        self.assertIn("object_scores", data)
        self.assertIn("eviction_keys", data)
        self.assertIn("reason", data)
        self.assertIn("timestamp", data)
        self.assertIn("metadata", data)

        # Validate against frozen Pydantic Decision model
        validated = Decision.model_validate(data)
        self.assertEqual(validated.version, "v1")

    def test_get_runtime_decision_uses_adaptive_service(self) -> None:
        """Verify GET /adaptive/runtime-decision delegates to AdaptiveService."""
        mock_service = MagicMock()
        mock_decision = Decision(
            decision_id="dec_svc_mock_1",
            timestamp=self.now,
            capacity_action=CapacityAction.MAINTAIN,
            recommended_capacity_bytes=2_000_000,
            object_scores={"k:1": 0.88},
            eviction_keys=[],
            reason="AdaptiveService mock",
            metadata={"source": "mock_service"},
        )
        mock_service.decide.return_value = mock_decision
        app.dependency_overrides[get_adaptive_service] = lambda: mock_service

        response = self.client.get("/adaptive/runtime-decision")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["decision_id"], "dec_svc_mock_1")
        self.assertEqual(data["object_scores"], {"k:1": 0.88})
        self.assertEqual(data["metadata"], {"source": "mock_service"})
        mock_service.decide.assert_called_once()

    def test_get_runtime_decision_dependency_injection_override(self) -> None:
        """Verify dependency injection replaces AdaptiveService and forwards query parameters."""
        mock_service = MagicMock()
        mock_decision = Decision(
            decision_id="dec_injected_42",
            timestamp=self.now,
            capacity_action=CapacityAction.SCALE_UP,
            recommended_capacity_bytes=8_000_000,
            object_scores={},
            eviction_keys=[],
            reason="Injected service decision",
        )
        mock_service.decide.return_value = mock_decision
        app.dependency_overrides[get_adaptive_service] = lambda: mock_service

        response = self.client.get(
            "/adaptive/runtime-decision",
            params={
                "min_capacity_bytes": 500_000,
                "max_capacity_bytes": 5_000_000,
                "capacity_mode": "continuous",
                "refresh_after_seconds": 150.0,
                "decision_id": "custom-dec-override",
            },
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["decision_id"], "dec_injected_42")
        self.assertEqual(data["capacity_action"], CapacityAction.SCALE_UP.value)

        mock_service.decide.assert_called_once()
        kwargs = mock_service.decide.call_args.kwargs
        self.assertEqual(kwargs["min_capacity_bytes"], 500_000)
        self.assertEqual(kwargs["max_capacity_bytes"], 5_000_000)
        self.assertEqual(kwargs["capacity_mode"], "continuous")
        self.assertEqual(kwargs["refresh_after_seconds"], 150.0)
        self.assertEqual(kwargs["decision_id"], "custom-dec-override")

    def test_get_runtime_decision_empty_cache(self) -> None:
        """Verify runtime endpoint handles an empty cache cleanly."""
        runtime_cache_manager.clear_metadata()

        response = self.client.get("/adaptive/runtime-decision")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["object_scores"], {})
        self.assertEqual(data["eviction_keys"], [])
        self.assertGreater(data["recommended_capacity_bytes"], 0)

    def test_get_runtime_decision_with_cache_metadata(self) -> None:
        """Verify runtime endpoint reflects current cache metadata from shared CacheManager."""
        cache_key = "product:runtime_test_item"
        runtime_cache_manager.set(cache_key, {"title": "Test Item", "price": 49.99})
        runtime_cache_manager.create_metadata(
            key=cache_key,
            size_bytes=350,
            retrieval_cost_ms=45.0,
        )

        response = self.client.get("/adaptive/runtime-decision")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn(cache_key, data["object_scores"])

        # Clean up
        runtime_cache_manager.delete(cache_key)

    def test_get_runtime_decision_uses_current_telemetry_state(self) -> None:
        """Verify runtime endpoint reflects current telemetry recorded on shared collector."""
        runtime_telemetry_collector.record_request()
        runtime_telemetry_collector.record_request()
        runtime_telemetry_collector.record_cache_hit()
        runtime_telemetry_collector.record_cache_miss()
        runtime_telemetry_collector.record_backend_call(60.0)

        response = self.client.get("/adaptive/runtime-decision")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("metadata", data)
        self.assertIn("workload_type", data["metadata"])

    def test_get_runtime_decision_invalid_capacity_bounds(self) -> None:
        """Verify runtime endpoint returns 422 when min_capacity_bytes > max_capacity_bytes."""
        response = self.client.get(
            "/adaptive/runtime-decision",
            params={
                "min_capacity_bytes": 5_000_000,
                "max_capacity_bytes": 1_000_000,
            },
        )
        self.assertEqual(response.status_code, 422)

    def test_get_runtime_decision_invalid_min_capacity_nonpositive(self) -> None:
        """Verify runtime endpoint returns 422 when min_capacity_bytes <= 0."""
        response = self.client.get(
            "/adaptive/runtime-decision",
            params={"min_capacity_bytes": 0},
        )
        self.assertEqual(response.status_code, 422)

    def test_get_runtime_decision_invalid_refresh_after_seconds(self) -> None:
        """Verify runtime endpoint returns 422 when refresh_after_seconds <= 0."""
        response = self.client.get(
            "/adaptive/runtime-decision",
            params={"refresh_after_seconds": -5.0},
        )
        self.assertEqual(response.status_code, 422)


if __name__ == "__main__":
    unittest.main()
