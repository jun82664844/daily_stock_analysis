# -*- coding: utf-8 -*-
from __future__ import annotations

import importlib.util
import os
import tempfile
import unittest
import sys
import inspect
from datetime import timedelta
from pathlib import Path

from src.platform_accounts import PlatformAccountService
from src.services.user_local_connector_service import UserLocalConnectorService
from src.storage import DatabaseManager, PlatformLocalConnector, utc_naive_now
from api.middlewares.auth import _connector_device_path
from api.v1.endpoints.local_connector import next_local_connector_job


class UserLocalConnectorV112TestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.db_path = os.path.join(self.temp_dir.name, "connector-v112.sqlite")
        DatabaseManager.reset_instance()
        self.db = DatabaseManager(db_url=f"sqlite:///{self.db_path}")
        self.accounts = PlatformAccountService(self.db)
        self.user_a = self.accounts.create_user("connector-a@example.com", "password123", plan="plus")
        self.user_b = self.accounts.create_user("connector-b@example.com", "password123", plan="plus")
        self.service = UserLocalConnectorService(self.db)

    def tearDown(self) -> None:
        DatabaseManager.reset_instance()
        self.temp_dir.cleanup()

    def _connector(self, user_id: int):
        pairing = self.service.create_pairing(user_id=user_id)
        return self.service.claim_pairing(pairing["code"], device_name="Test PC")

    def test_pairing_code_is_single_use_and_device_token_is_not_stored_plaintext(self) -> None:
        pairing = self.service.create_pairing(user_id=self.user_a.id)
        self.assertTrue(pairing["expires_at"].endswith("Z"))
        claimed = self.service.claim_pairing(pairing["code"], device_name="My PC")
        with self.assertRaisesRegex(ValueError, "pairing_code_used"):
            self.service.claim_pairing(pairing["code"], device_name="Other PC")
        with self.db.get_session() as session:
            row = session.get(PlatformLocalConnector, claimed["connector_id"])
            self.assertNotEqual(row.device_token_hash, claimed["device_token"])
            self.assertNotIn(claimed["device_token"], row.device_token_hash)

    def test_device_connector_routes_delegate_auth_to_bearer_boundary(self) -> None:
        self.assertTrue(_connector_device_path("/api/v1/local-connector/claim"))
        self.assertTrue(_connector_device_path("/api/v1/local-connector/heartbeat"))
        self.assertTrue(_connector_device_path("/api/v1/local-connector/jobs/abc/complete"))
        self.assertFalse(_connector_device_path("/api/v1/platform/local-connectors"))
        self.assertFalse(inspect.iscoroutinefunction(next_local_connector_job))

    def test_connector_cannot_complete_another_users_job(self) -> None:
        connector_a = self._connector(self.user_a.id)
        connector_b = self._connector(self.user_b.id)
        job_b = self.service.create_job(
            user_id=self.user_b.id,
            connector_id=connector_b["connector_id"],
            model_name="qwen3:8b",
            request_payload={"prompt": "information only"},
        )
        with self.assertRaisesRegex(ValueError, "job_not_found"):
            self.service.complete_job(connector_a["device_token"], job_b["job_id"], {"text": "x"})

    def test_heartbeat_preserves_discovery_order_and_deduplicates_models(self) -> None:
        connector = self._connector(self.user_a.id)
        result = self.service.heartbeat(
            connector["device_token"],
            ["qwen3:8b", "large:40b", "qwen3:8b"],
        )
        self.assertEqual(result["models"], ["qwen3:8b", "large:40b"])

    def test_expired_job_is_not_delivered(self) -> None:
        connector = self._connector(self.user_a.id)
        self.service.create_job(
            user_id=self.user_a.id,
            connector_id=connector["connector_id"],
            model_name="qwen3:8b",
            request_payload={"prompt": "expired"},
            expires_at=utc_naive_now() - timedelta(seconds=1),
        )
        self.assertIsNone(self.service.next_job(connector["device_token"], wait_seconds=0))

    def test_ollama_client_rejects_non_loopback_and_does_not_pull(self) -> None:
        module_path = Path("apps/dsa-local-connector/ollama.py")
        spec = importlib.util.spec_from_file_location("dsa_connector_ollama", module_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.assertEqual(module.OllamaClient("http://127.0.0.1:11434").base_url, "http://127.0.0.1:11434")
        with self.assertRaises(ValueError):
            module.OllamaClient("http://192.168.1.20:11434")

    def test_completed_job_returns_owner_scoped_decrypted_text(self) -> None:
        connector = self._connector(self.user_a.id)
        job = self.service.create_job(
            user_id=self.user_a.id,
            connector_id=connector["connector_id"],
            model_name="qwen3:8b",
            request_payload={"prompt": "information only"},
        )
        self.service.next_job(connector["device_token"], wait_seconds=0)
        self.service.complete_job(
            connector["device_token"],
            job["job_id"],
            {"text": "Market data summary", "diagnostics": {"done_reason": "stop"}},
        )

        result = self.service.wait_for_result(
            user_id=self.user_a.id,
            job_id=job["job_id"],
            timeout_seconds=0,
        )
        self.assertEqual(result["text"], "Market data summary")
        with self.assertRaisesRegex(ValueError, "job_not_found"):
            self.service.wait_for_result(
                user_id=self.user_b.id,
                job_id=job["job_id"],
                timeout_seconds=0,
            )

    def test_completion_rejects_unbounded_connector_payload(self) -> None:
        connector = self._connector(self.user_a.id)
        job = self.service.create_job(
            user_id=self.user_a.id,
            connector_id=connector["connector_id"],
            model_name="qwen3:8b",
            request_payload={"prompt": "information only"},
        )
        with self.assertRaisesRegex(ValueError, "invalid_job_result"):
            self.service.complete_job(
                connector["device_token"],
                job["job_id"],
                {"text": "ok", "command": "read-file"},
            )

    def test_desktop_runtime_discovers_models_and_returns_restricted_result(self) -> None:
        connector_dir = Path("apps/dsa-local-connector").resolve()
        sys.path.insert(0, str(connector_dir))
        try:
            runtime_spec = importlib.util.spec_from_file_location(
                "dsa_connector_runtime",
                connector_dir / "runtime.py",
            )
            runtime_module = importlib.util.module_from_spec(runtime_spec)
            runtime_spec.loader.exec_module(runtime_module)
        finally:
            sys.path.remove(str(connector_dir))

        class FakeClient:
            def __init__(self):
                self.completed = []

            def heartbeat(self, models):
                self.models = models

            def next_job(self):
                return {
                    "job_id": "job-1",
                    "model": "qwen3:8b",
                    "request": {"prompt": "information only"},
                }

            def complete(self, job_id, result):
                self.completed.append((job_id, result))

        class FakeOllama:
            def discover_models(self):
                return ["qwen3:8b"]

            def generate(self, model, prompt):
                return {
                    "response": "Market information summary",
                    "done_reason": "stop",
                    "eval_count": 12,
                    "prompt_eval_count": 99,
                }

        client = FakeClient()
        runtime = runtime_module.ConnectorRuntime(client=client, ollama=FakeOllama())
        state = runtime.process_once()

        self.assertEqual(state, {"status": "connected", "model_count": 1, "processed_job": True})
        _, result = client.completed[0]
        self.assertEqual(result["text"], "Market information summary")
        self.assertEqual(result["diagnostics"], {"done_reason": "stop", "eval_count": 12})
        self.assertNotIn("prompt", result)


if __name__ == "__main__":
    unittest.main()
