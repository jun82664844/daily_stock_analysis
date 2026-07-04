import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from api.app import create_app
from src.config import Config
from src.storage import DatabaseManager


class BillingApiTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.db_path = os.path.join(self.temp_dir.name, "billing.sqlite")
        self.static_dir = Path(self.temp_dir.name) / "static"
        self.static_dir.mkdir()
        (self.static_dir / "index.html").write_text("<html>ok</html>", encoding="utf-8")
        DatabaseManager.reset_instance()
        Config.reset_instance()
        self.env_patch = patch.dict(
            os.environ,
            {
                "DATABASE_PATH": self.db_path,
                "PLATFORM_USER_AUTH_ENABLED": "true",
                "BILLING_ENABLED": "false",
            },
            clear=False,
        )
        self.env_patch.start()
        self.client = TestClient(create_app(static_dir=self.static_dir))

    def tearDown(self) -> None:
        self.client.close()
        self.env_patch.stop()
        DatabaseManager.reset_instance()
        Config.reset_instance()
        self.temp_dir.cleanup()

    def test_checkout_requires_authenticated_platform_user(self):
        response = self.client.post("/api/v1/billing/checkout", json={"plan": "premium"})

        self.assertEqual(response.status_code, 401)

    def test_checkout_is_disabled_in_local_v1_after_login(self):
        self.client.post(
            "/api/v1/platform/register",
            json={"email": "bill@example.com", "password": "password123"},
        )

        response = self.client.post("/api/v1/billing/checkout", json={"plan": "premium"})

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"], "billing_disabled")

    def test_webhook_rejects_missing_signature(self):
        response = self.client.post("/api/v1/billing/webhook", json={"event": "paid"})

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"], "invalid_signature")
