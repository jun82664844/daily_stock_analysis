import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from api.app import create_app
from src.config import Config
from src.storage import DatabaseManager


class PlatformSecurityBoundariesTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.db_path = os.path.join(self.temp_dir.name, "security.sqlite")
        self.static_dir = Path(self.temp_dir.name) / "static"
        self.static_dir.mkdir()
        (self.static_dir / "index.html").write_text("<html>ok</html>", encoding="utf-8")
        DatabaseManager.reset_instance()
        Config.reset_instance()

    def tearDown(self) -> None:
        DatabaseManager.reset_instance()
        Config.reset_instance()
        self.temp_dir.cleanup()

    def _client(self, extra_env: dict[str, str] | None = None):
        env = {
            "DATABASE_PATH": self.db_path,
            "ADMIN_AUTH_ENABLED": "true",
            "PLATFORM_USER_AUTH_ENABLED": "true",
        }
        env.update(extra_env or {})
        patcher = patch.dict(os.environ, env, clear=False)
        patcher.start()
        client = TestClient(create_app(static_dir=self.static_dir))
        self.addCleanup(client.close)
        self.addCleanup(patcher.stop)
        return client

    def test_platform_user_cannot_access_admin_system_config(self):
        client = self._client()
        client.post(
            "/api/v1/platform/register",
            json={"email": "user@example.com", "password": "password123"},
        )

        response = client.get("/api/v1/system/config")

        self.assertIn(response.status_code, {401, 403})

    def test_cookie_write_endpoint_rejects_missing_csrf_when_csrf_enabled(self):
        client = self._client({"PLATFORM_CSRF_ENABLED": "true"})
        client.post(
            "/api/v1/platform/register",
            json={"email": "csrf@example.com", "password": "password123"},
        )

        response = client.post(
            "/api/v1/platform/api-keys",
            json={"provider": "deepseek", "apiKey": "sk-secret"},
        )

        self.assertEqual(response.status_code, 403)

    def test_analysis_write_rejects_missing_csrf_when_csrf_enabled(self):
        client = self._client({"PLATFORM_CSRF_ENABLED": "true"})
        client.post(
            "/api/v1/platform/register",
            json={"email": "analysis-csrf@example.com", "password": "password123"},
        )

        with patch("src.services.analysis_service.AnalysisService") as analysis_service_cls:
            response = client.post(
                "/api/v1/analysis/analyze",
                json={"stock_code": "600519", "async_mode": False},
            )

        self.assertEqual(response.status_code, 403)
        analysis_service_cls.assert_not_called()

    def test_history_delete_rejects_missing_csrf_when_csrf_enabled(self):
        client = self._client({"PLATFORM_CSRF_ENABLED": "true"})
        client.post(
            "/api/v1/platform/register",
            json={"email": "history-csrf@example.com", "password": "password123"},
        )

        response = client.request(
            "DELETE",
            "/api/v1/history",
            json={"record_ids": [123]},
        )

        self.assertEqual(response.status_code, 403)

    def test_watchlist_automation_writes_reject_missing_csrf_when_enabled(self):
        client = self._client({"PLATFORM_CSRF_ENABLED": "true"})
        client.post(
            "/api/v1/platform/register",
            json={"email": "watchlist-csrf@example.com", "password": "password123"},
        )

        responses = [
            client.post("/api/v1/platform/watchlist/radar/run"),
            client.post(
                "/api/v1/platform/watchlist/alert-rules",
                json={"stockCode": "AAPL", "ruleType": "price_move", "threshold": 2.0},
            ),
            client.delete("/api/v1/platform/watchlist/alert-rules/1"),
        ]

        self.assertEqual([response.status_code for response in responses], [403, 403, 403])

    def test_cookie_write_endpoint_accepts_matching_csrf_header_when_csrf_enabled(self):
        client = self._client({"PLATFORM_CSRF_ENABLED": "true"})
        client.post(
            "/api/v1/platform/register",
            json={"email": "csrf-ok@example.com", "password": "password123"},
        )
        csrf_token = client.cookies.get("dsa_csrf_token")

        response = client.post(
            "/api/v1/platform/api-keys",
            json={"provider": "deepseek", "apiKey": "sk-user-owned-secret"},
            headers={"X-DSA-CSRF": csrf_token or ""},
        )

        self.assertEqual(response.status_code, 200)
        self.assertNotIn("sk-user-owned-secret", str(response.json()))

    def test_admin_login_issues_and_logout_clears_csrf_when_csrf_enabled(self):
        client = self._client({"PLATFORM_CSRF_ENABLED": "true"})

        login = client.post(
            "/api/v1/auth/login",
            json={"password": "AdminPass123", "passwordConfirm": "AdminPass123"},
        )

        self.assertEqual(login.status_code, 200)
        csrf_token = client.cookies.get("dsa_csrf_token")
        self.assertTrue(csrf_token)

        logout = client.post(
            "/api/v1/auth/logout",
            headers={"X-DSA-CSRF": csrf_token or ""},
        )

        self.assertEqual(logout.status_code, 204)
        self.assertIn("dsa_csrf_token=", logout.headers.get("set-cookie", ""))

    def test_admin_cookie_write_rejects_missing_csrf_when_csrf_enabled(self):
        client = self._client({"PLATFORM_CSRF_ENABLED": "true"})
        login = client.post(
            "/api/v1/auth/login",
            json={"password": "AdminPass123", "passwordConfirm": "AdminPass123"},
        )
        self.assertEqual(login.status_code, 200)

        response = client.post("/api/v1/auth/logout")

        self.assertEqual(response.status_code, 403)
