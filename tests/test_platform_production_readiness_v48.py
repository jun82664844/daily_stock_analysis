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
from src.storage import DatabaseManager


class PlatformProductionReadinessV48TestCase(unittest.TestCase):
    def tearDown(self) -> None:
        DatabaseManager.reset_instance()
        Config.reset_instance()

    def test_production_readiness_builder_blocks_launch_and_redacts_secrets(self) -> None:
        from src.services.production_readiness import build_production_readiness_status

        with patch.dict(
            os.environ,
            {
                "ADMIN_AUTH_ENABLED": "true",
                "PLATFORM_USER_AUTH_ENABLED": "true",
                "PLATFORM_CSRF_ENABLED": "true",
                "CORS_ALLOW_ALL": "false",
                "DEBUG": "false",
                "SEARXNG_PUBLIC_INSTANCES_ENABLED": "false",
                "BILLING_ENABLED": "false",
                "BILLING_PROVIDER": "disabled",
                "DSA_SECRET_SOURCE": "managed-secret-store-or-protected-env",
                "DSA_PRODUCTION_DOMAIN_APPROVED": "false",
                "DSA_PRODUCTION_HTTPS_APPROVED": "false",
                "DSA_PRODUCTION_WAF_APPROVED": "false",
                "DSA_MARKET_DATA_LICENSE_APPROVED": "false",
                "DSA_LEGAL_TERMS_APPROVED": "false",
                "DSA_PRIVACY_POLICY_APPROVED": "false",
                "DSA_MONITORING_APPROVED": "false",
                "DSA_BACKUP_RESTORE_DRILL_APPROVED": "false",
                "LITELLM_API_KEY": "sk-v48-secret-must-not-leak",
            },
            clear=False,
        ):
            payload = build_production_readiness_status()

        encoded = json.dumps(payload, ensure_ascii=False)
        categories = {item["category"] for item in payload["checks"]}
        blocking_ids = {item["id"] for item in payload["blocking_checks"]}

        self.assertEqual(payload["mode"], "production_preflight")
        self.assertFalse(payload["ai_used"])
        self.assertEqual(payload["launch_decision"], "blocked")
        self.assertFalse(payload["production_ready"])
        self.assertEqual("not_investment_advice", payload["analysis_boundary"])
        self.assertTrue(payload["blocking_checks"])
        self.assertTrue(payload["manual_actions"])
        self.assertEqual(
            {
                "auth",
                "security",
                "billing",
                "deployment",
                "data_sources",
                "legal",
                "privacy",
                "observability",
                "backup",
            },
            categories,
        )
        self.assertIn("real_payment_disabled", blocking_ids)
        self.assertIn("domain_not_approved", blocking_ids)
        self.assertIn("market_data_license_not_approved", blocking_ids)
        self.assertIn("legal_terms_not_approved", blocking_ids)
        self.assertNotIn("sk-v48-secret-must-not-leak", encoded)
        self.assertNotIn("LITELLM_API_KEY", encoded)

    def test_production_readiness_endpoint_requires_admin(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
            db_path = Path(temp_dir) / "v48-readiness.sqlite"
            static_dir = Path(temp_dir) / "static"
            static_dir.mkdir()
            (static_dir / "index.html").write_text("<html>ok</html>", encoding="utf-8")
            DatabaseManager.reset_instance()
            Config.reset_instance()
            with patch.dict(
                os.environ,
                {
                    "DATABASE_PATH": str(db_path),
                    "ADMIN_AUTH_ENABLED": "true",
                    "PLATFORM_USER_AUTH_ENABLED": "true",
                    "PLATFORM_CSRF_ENABLED": "false",
                    "LITELLM_API_KEY": "sk-v48-endpoint-secret-must-not-leak",
                },
                clear=False,
            ):
                client = TestClient(create_app(static_dir=static_dir))
                client.post(
                    "/api/v1/platform/register",
                    json={"email": "v48-user@example.com", "password": "password123"},
                )
                user_response = client.get("/api/v1/platform/admin/production-readiness")
                client.post("/api/v1/platform/logout")
                login = client.post(
                    "/api/v1/auth/login",
                    json={"password": "AdminPass123", "passwordConfirm": "AdminPass123"},
                )
                admin_response = client.get("/api/v1/platform/admin/production-readiness")
                client.close()

        self.assertEqual(user_response.status_code, 403)
        self.assertEqual(login.status_code, 200)
        self.assertEqual(admin_response.status_code, 200)
        payload = admin_response.json()
        encoded = json.dumps(payload, ensure_ascii=False)
        self.assertEqual(payload["mode"], "production_preflight")
        self.assertEqual(payload["launch_decision"], "blocked")
        self.assertFalse(payload["ai_used"])
        self.assertFalse(payload["production_ready"])
        self.assertNotIn("sk-v48-endpoint-secret-must-not-leak", encoded)

    def test_v48_verifier_file_and_marker_are_visible(self) -> None:
        root = Path(__file__).resolve().parents[1]
        verifier = root / "scripts" / "verify_platform_production_readiness_v48.py"

        self.assertTrue(verifier.exists(), "V48 verifier script is missing")
        self.assertIsNotNone(importlib.util.find_spec("scripts.verify_platform_production_readiness_v48"))

        from scripts.verify_platform_production_readiness_v48 import OK_MARKER

        self.assertEqual(OK_MARKER, "DSA_PLATFORM_PRODUCTION_READINESS_V48_OK")


if __name__ == "__main__":
    unittest.main()
