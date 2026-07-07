# -*- coding: utf-8 -*-
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from api.app import create_app
from src import auth as admin_auth
from src.config import Config
from src.storage import DatabaseManager


class PlatformRegistrationVerificationTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.db_path = os.path.join(self.temp_dir.name, "platform-registration.sqlite")
        self.static_dir = Path(self.temp_dir.name) / "static"
        self.static_dir.mkdir()
        (self.static_dir / "index.html").write_text("<html>ok</html>", encoding="utf-8")
        DatabaseManager.reset_instance()
        Config.reset_instance()
        admin_auth._rate_limit.clear()
        self.env_patch = patch.dict(
            os.environ,
            {
                "DATABASE_PATH": self.db_path,
                "ADMIN_AUTH_ENABLED": "true",
                "PLATFORM_USER_AUTH_ENABLED": "true",
            },
            clear=False,
        )
        self.env_patch.start()
        self.client = TestClient(create_app(static_dir=self.static_dir))

    def tearDown(self) -> None:
        self.client.close()
        self.env_patch.stop()
        admin_auth._rate_limit.clear()
        DatabaseManager.reset_instance()
        Config.reset_instance()
        self.temp_dir.cleanup()

    def test_registration_code_can_be_requested_and_used_once_for_registration(self) -> None:
        code_response = self.client.post(
            "/api/v1/platform/register/verification-code",
            json={"email": "Verify@Example.com"},
        )

        self.assertEqual(code_response.status_code, 200)
        code_body = code_response.json()
        self.assertEqual(code_body["email"], "verify@example.com")
        self.assertTrue(code_body["sent"])
        self.assertRegex(code_body["dev_code"], r"^\d{6}$")
        self.assertGreaterEqual(code_body["expires_in_seconds"], 60)

        wrong_code = "000000" if code_body["dev_code"] != "000000" else "111111"
        rejected = self.client.post(
            "/api/v1/platform/register",
            json={
                "email": "Verify@Example.com",
                "password": "password123",
                "verification_code": wrong_code,
            },
        )
        self.assertEqual(rejected.status_code, 400)
        self.assertEqual(rejected.json()["error"], "invalid_verification_code")

        accepted = self.client.post(
            "/api/v1/platform/register",
            json={
                "email": "Verify@Example.com",
                "password": "password123",
                "verification_code": code_body["dev_code"],
            },
        )
        self.assertEqual(accepted.status_code, 200)
        self.assertEqual(accepted.json()["user"]["email"], "verify@example.com")
        self.assertIn("dsa_user_session", accepted.cookies)

    def test_strict_verification_mode_rejects_registration_without_code(self) -> None:
        with patch.dict(os.environ, {"PLATFORM_EMAIL_VERIFICATION_REQUIRED": "true"}, clear=False):
            response = self.client.post(
                "/api/v1/platform/register",
                json={"email": "strict@example.com", "password": "password123"},
            )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"], "verification_required")


if __name__ == "__main__":
    unittest.main()
