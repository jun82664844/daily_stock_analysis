import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from api.app import create_app
from src.config import Config
from src.platform_accounts import PlatformAccountService
from src.storage import DatabaseManager


REPO_ROOT = Path(__file__).resolve().parents[1]


class PlatformOpsHealthV52TestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.db_path = os.path.join(self.temp_dir.name, "ops-health-v52.sqlite")
        self.static_dir = Path(self.temp_dir.name) / "static"
        self.static_dir.mkdir()
        (self.static_dir / "index.html").write_text("<html>ok</html>", encoding="utf-8")
        DatabaseManager.reset_instance()
        Config.reset_instance()
        self.env_patch = patch.dict(
            os.environ,
            {
                "DATABASE_PATH": self.db_path,
                "ADMIN_AUTH_ENABLED": "true",
                "PLATFORM_USER_AUTH_ENABLED": "true",
                "PLATFORM_CSRF_ENABLED": "true",
                "BILLING_ENABLED": "true",
                "BILLING_PROVIDER": "stripe",
                "BILLING_STRIPE_SECRET_KEY": "sk_test_v52_should_not_leak",
                "DEBUG": "false",
                "CORS_ALLOW_ALL": "false",
                "SEARXNG_PUBLIC_INSTANCES_ENABLED": "false",
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

    def test_ops_health_builder_is_read_only_secret_free_and_path_safe(self) -> None:
        from src.services.platform_ops_health import build_platform_ops_health_status

        payload = build_platform_ops_health_status()
        serialized = json.dumps(payload, ensure_ascii=False)

        self.assertEqual(payload["mode"], "local_ops_health")
        self.assertFalse(payload["ai_used"])
        self.assertIn(payload["overall_status"], {"ok", "degraded", "failed"})
        self.assertIn("database", {check["category"] for check in payload["checks"]})
        self.assertIn("backup", {check["category"] for check in payload["checks"]})
        self.assertIn("billing", {check["category"] for check in payload["checks"]})
        self.assertIn("security", {check["category"] for check in payload["checks"]})
        self.assertNotIn("sk_test_v52_should_not_leak", serialized)
        self.assertNotIn(self.temp_dir.name, serialized)

    def test_ops_health_endpoint_requires_admin(self) -> None:
        PlatformAccountService().create_user("ops-user@example.com", "password123", role="user")
        PlatformAccountService().create_user("ops-admin@example.com", "password123", role="admin", plan="enterprise")

        user_login = self.client.post(
            "/api/v1/platform/login",
            json={"email": "ops-user@example.com", "password": "password123"},
        )
        self.assertEqual(user_login.status_code, 200)
        user_response = self.client.get("/api/v1/platform/admin/ops-health")
        self.assertEqual(user_response.status_code, 403)

        admin_client = TestClient(create_app(static_dir=self.static_dir))
        try:
            admin_login = admin_client.post(
                "/api/v1/platform/login",
                json={"email": "ops-admin@example.com", "password": "password123"},
            )
            self.assertEqual(admin_login.status_code, 200)
            admin_response = admin_client.get("/api/v1/platform/admin/ops-health")
        finally:
            admin_client.close()

        self.assertEqual(admin_response.status_code, 200)
        payload = admin_response.json()
        self.assertEqual(payload["mode"], "local_ops_health")
        self.assertFalse(payload["ai_used"])
        self.assertNotIn("sk_test_v52_should_not_leak", json.dumps(payload))

    def test_v52_verifier_file_and_marker_are_visible(self) -> None:
        verifier = REPO_ROOT / "scripts" / "verify_platform_ops_health_v52.py"

        self.assertTrue(verifier.exists(), "V52 verifier script is missing")
        self.assertIsNotNone(importlib.util.find_spec("scripts.verify_platform_ops_health_v52"))

        from scripts.verify_platform_ops_health_v52 import OK_MARKER

        self.assertEqual(OK_MARKER, "DSA_PLATFORM_OPS_HEALTH_V52_OK")


if __name__ == "__main__":
    unittest.main()
