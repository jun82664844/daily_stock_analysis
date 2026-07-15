import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from fastapi.testclient import TestClient

from api.app import create_app
from src.config import Config
from src.platform_accounts import PlatformAccountService
from src.storage import DatabaseManager


def _analysis_service_result(stock_code: str = "AAPL"):
    return SimpleNamespace(
        last_error=None,
        analyze_stock=lambda **kwargs: {
            "stock_code": stock_code,
            "stock_name": "Apple Inc.",
            "report": {
                "meta": {"stock_code": stock_code, "report_language": "zh"},
                "summary": {"analysis_summary": "ok"},
                "strategy": {},
                "details": {},
            },
        },
    )


def _ready_local_runtime():
    status = {
        "enabled": True,
        "reachable": True,
        "ready": True,
        "quick_ready": True,
        "deep_ready": True,
        "reason": "ready",
    }
    return SimpleNamespace(
        get_status=lambda: status,
        readiness_reason=lambda analysis_depth, *, status=None: "ready",
    )


class PlatformAiFeatureQuotaTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.db_path = os.path.join(self.temp_dir.name, "ai-feature-quota.sqlite")
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
                "PLATFORM_CSRF_ENABLED": "false",
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

    def test_fast_analysis_consumes_quick_ai_bucket(self):
        reg = self.client.post(
            "/api/v1/platform/register",
            json={"email": "quick@example.com", "password": "password123"},
        )
        user_id = reg.json()["user"]["id"]

        with patch("src.services.analysis_service.AnalysisService", return_value=_analysis_service_result()), \
             patch("api.v1.endpoints.analysis._load_sync_fundamental_sources", return_value=(None, None)):
            response = self.client.post(
                "/api/v1/analysis/analyze",
                json={"stock_code": "AAPL", "async_mode": False, "analysis_depth": "fast"},
            )

        self.assertEqual(response.status_code, 200)
        quick_quota = PlatformAccountService().get_feature_quota_status(user_id, "ai_quick")
        deep_quota = PlatformAccountService().get_feature_quota_status(user_id, "ai_deep")
        self.assertEqual(quick_quota["used"], 1)
        self.assertEqual(deep_quota["used"], 0)

    def test_user_key_deep_analysis_consumes_user_key_bucket(self):
        reg = self.client.post(
            "/api/v1/platform/register",
            json={"email": "userkey@example.com", "password": "password123"},
        )
        user_id = reg.json()["user"]["id"]
        key_response = self.client.post(
            "/api/v1/platform/api-keys",
            json={"provider": "deepseek", "apiKey": "sk-user-cost"},
        )
        self.assertEqual(key_response.status_code, 200)

        with patch("src.services.analysis_service.AnalysisService", return_value=_analysis_service_result()), \
             patch("api.v1.endpoints.analysis._load_sync_fundamental_sources", return_value=(None, None)):
            response = self.client.post(
                "/api/v1/analysis/analyze",
                json={
                    "stock_code": "AAPL",
                    "async_mode": False,
                    "analysis_depth": "deep",
                    "apiKeyMode": "user",
                },
            )

        self.assertEqual(response.status_code, 200)
        platform_quota = PlatformAccountService().get_feature_quota_status(user_id, "ai_deep")
        user_key_quota = PlatformAccountService().get_feature_quota_status(user_id, "ai_deep_user_key")
        self.assertEqual(platform_quota["used"], 0)
        self.assertEqual(user_key_quota["used"], 1)

    def test_user_key_fast_analysis_consumes_quick_user_key_bucket(self):
        reg = self.client.post(
            "/api/v1/platform/register",
            json={"email": "quick-userkey@example.com", "password": "password123"},
        )
        user_id = reg.json()["user"]["id"]
        key_response = self.client.post(
            "/api/v1/platform/api-keys",
            json={"provider": "deepseek", "apiKey": "sk-user-quick-cost"},
        )
        self.assertEqual(key_response.status_code, 200)

        with patch("src.services.analysis_service.AnalysisService", return_value=_analysis_service_result()), \
             patch("api.v1.endpoints.analysis._load_sync_fundamental_sources", return_value=(None, None)):
            response = self.client.post(
                "/api/v1/analysis/analyze",
                json={
                    "stock_code": "AAPL",
                    "async_mode": False,
                    "analysis_depth": "fast",
                    "apiKeyMode": "user",
                },
            )

        self.assertEqual(response.status_code, 200)
        platform_quick = PlatformAccountService().get_feature_quota_status(user_id, "ai_quick")
        user_key_quick = PlatformAccountService().get_feature_quota_status(user_id, "ai_quick_user_key")
        self.assertEqual(platform_quick["used"], 0)
        self.assertEqual(user_key_quick["used"], 1)

    def test_local_model_deep_analysis_consumes_local_bucket(self):
        reg = self.client.post(
            "/api/v1/platform/register",
            json={"email": "local-deep@example.com", "password": "password123"},
        )
        user_id = reg.json()["user"]["id"]

        with patch("src.services.analysis_service.AnalysisService", return_value=_analysis_service_result()), \
             patch("src.services.ollama_runtime_service.get_ollama_runtime_service", return_value=_ready_local_runtime()), \
             patch("api.v1.endpoints.analysis._load_sync_fundamental_sources", return_value=(None, None)):
            response = self.client.post(
                "/api/v1/analysis/analyze",
                json={
                    "stock_code": "AAPL",
                    "async_mode": False,
                    "analysis_depth": "deep",
                    "apiKeyMode": "local",
                },
            )

        self.assertEqual(response.status_code, 200)
        platform_deep = PlatformAccountService().get_feature_quota_status(user_id, "ai_deep")
        local_model = PlatformAccountService().get_feature_quota_status(user_id, "ai_local")
        self.assertEqual(platform_deep["used"], 0)
        self.assertEqual(local_model["used"], 1)
