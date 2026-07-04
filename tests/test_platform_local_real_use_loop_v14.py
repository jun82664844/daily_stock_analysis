# -*- coding: utf-8 -*-
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


class PlatformLocalRealUseLoopV14TestCase(unittest.TestCase):
    def tearDown(self) -> None:
        DatabaseManager.reset_instance()
        Config.reset_instance()

    def test_local_status_builder_is_local_only_no_ai_and_redacts_secrets(self) -> None:
        from src.services.local_functional_status import build_local_functional_status

        with patch.dict(
            os.environ,
            {
                "WEBUI_HOST": "127.0.0.1",
                "WEBUI_PORT": "8018",
                "API_PORT": "8018",
                "ADMIN_AUTH_ENABLED": "true",
                "PLATFORM_USER_AUTH_ENABLED": "true",
                "BILLING_ENABLED": "false",
                "BILLING_PROVIDER": "sandbox",
                "LOCAL_LLM_ENABLED": "false",
                "SEARXNG_PUBLIC_INSTANCES_ENABLED": "false",
                "LITELLM_MODEL": "deepseek/deepseek-v4-flash",
                "LITELLM_API_KEY": "sk-v14-local-secret-must-not-leak",
            },
            clear=False,
        ):
            payload = build_local_functional_status()

        encoded = json.dumps(payload, ensure_ascii=False)
        self.assertEqual(payload["mode"], "local_only")
        self.assertFalse(payload["ai_used"])
        self.assertEqual(payload["service"]["port"], 8018)
        self.assertTrue(payload["auth"]["platform_user_auth_enabled"])
        self.assertFalse(payload["billing"]["enabled"])
        self.assertEqual(payload["billing"]["mode"], "local_only")
        self.assertEqual(payload["ai"]["default_model"], "deepseek/deepseek-v4-flash")
        self.assertFalse(payload["ai"]["public_search_enabled"])
        self.assertTrue(payload["ai"]["byok_supported"])
        self.assertTrue(payload["safety"]["no_ai_status"])
        self.assertTrue(payload["safety"]["secrets_redacted"])
        self.assertIn("market", payload)
        self.assertIn("lanes", payload["market"])
        self.assertNotIn("sk-v14-local-secret-must-not-leak", encoded)

    def test_local_status_endpoint_requires_admin(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
            db_path = Path(temp_dir) / "v14-real-use.sqlite"
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
                    "LITELLM_API_KEY": "sk-v14-endpoint-secret-must-not-leak",
                },
                clear=False,
            ):
                client = TestClient(create_app(static_dir=static_dir))
                client.post(
                    "/api/v1/platform/register",
                    json={"email": "v14-user@example.com", "password": "password123"},
                )
                user_response = client.get("/api/v1/platform/admin/local-status")
                client.post("/api/v1/platform/logout")
                login = client.post(
                    "/api/v1/auth/login",
                    json={"password": "AdminPass123", "passwordConfirm": "AdminPass123"},
                )
                admin_response = client.get("/api/v1/platform/admin/local-status")
                client.close()

        self.assertEqual(user_response.status_code, 403)
        self.assertEqual(login.status_code, 200)
        self.assertEqual(admin_response.status_code, 200)
        payload = admin_response.json()
        encoded = json.dumps(payload, ensure_ascii=False)
        self.assertEqual(payload["mode"], "local_only")
        self.assertFalse(payload["ai_used"])
        self.assertFalse(payload["billing"]["enabled"])
        self.assertTrue(payload["safety"]["no_ai_status"])
        self.assertNotIn("sk-v14-endpoint-secret-must-not-leak", encoded)

    def test_v14_verifier_file_and_marker_are_visible(self) -> None:
        root = Path(__file__).resolve().parents[1]
        verifier = root / "scripts" / "verify_platform_local_real_use_loop_v14.py"

        self.assertTrue(verifier.exists(), "V14 verifier script is missing")
        self.assertIsNotNone(importlib.util.find_spec("scripts.verify_platform_local_real_use_loop_v14"))

        from scripts.verify_platform_local_real_use_loop_v14 import OK_MARKER

        self.assertEqual(OK_MARKER, "DSA_PLATFORM_LOCAL_REAL_USE_LOOP_V14_OK")


if __name__ == "__main__":
    unittest.main()
