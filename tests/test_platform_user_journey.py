import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from api.app import create_app
from src.config import Config
from src.platform_accounts import PlatformAccountService
from src.storage import DatabaseManager


def _analysis_payload(stock_code: str = "600519") -> dict:
    return {
        "stock_code": stock_code,
        "stock_name": "Kweichow Moutai",
        "report": {
            "meta": {"stock_code": stock_code, "stock_name": "Kweichow Moutai", "report_language": "en"},
            "summary": {"analysis_summary": "informational test summary"},
            "strategy": {},
            "details": {},
        },
    }


def _history_result(stock_code: str = "600519") -> SimpleNamespace:
    return SimpleNamespace(
        code=stock_code,
        name="Kweichow Moutai",
        sentiment_score=50,
        operation_advice="hold",
        trend_prediction="sideways",
        analysis_summary="informational test summary",
        news_summary="",
        technical_analysis="",
        fundamental_analysis="",
        risk_warning="",
        data_sources="unit-test",
        raw_response=None,
        success=True,
    )


class PlatformUserJourneyTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.db_path = os.path.join(self.temp_dir.name, "platform-user-journey.sqlite")
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
                "ADMIN_AUTH_ENABLED": "true",
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

    def _register(self, email: str = "journey@example.com") -> int:
        response = self.client.post(
            "/api/v1/platform/register",
            json={"email": email, "password": "password123"},
        )
        self.assertEqual(response.status_code, 200)
        return int(response.json()["user"]["id"])

    def test_account_center_shows_user_quota_buckets_and_masked_api_key(self) -> None:
        user_id = self._register()
        key_response = self.client.post(
            "/api/v1/platform/api-keys",
            json={
                "provider": "deepseek",
                "apiKey": "sk-user-journey-secret",
                "model": "deepseek/deepseek-v4-flash",
            },
        )
        self.assertEqual(key_response.status_code, 200)
        PlatformAccountService().reserve_feature_quota(user_id, "ai_quick", reference_id="quick-test")
        PlatformAccountService().reserve_feature_quota(
            user_id,
            "ai_deep",
            api_key_mode="user",
            reference_id="deep-byok-test",
        )

        response = self.client.get("/api/v1/platform/account")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["user"]["email"], "journey@example.com")
        self.assertEqual(body["user"]["role"], "user")
        self.assertEqual(body["user"]["plan"], "free")
        self.assertEqual(body["recommended_query_mode"], "user")
        self.assertIn("quota_buckets", body)
        buckets = {bucket["quota_bucket"]: bucket for bucket in body["quota_buckets"]}
        self.assertEqual(buckets["ai_quick"]["used"], 1)
        self.assertEqual(buckets["ai_deep_user_key"]["used"], 1)
        self.assertEqual(body["api_keys"][0]["provider"], "deepseek")
        self.assertIn("masked_key", body["api_keys"][0])
        self.assertNotIn("sk-user-journey-secret", str(body))

    def test_user_journey_no_ai_quick_byok_history_and_quota_boundaries(self) -> None:
        user_id = self._register("flow@example.com")
        self.client.post(
            "/api/v1/platform/api-keys",
            json={"provider": "deepseek", "apiKey": "sk-flow-user-secret", "model": "deepseek/deepseek-v4-flash"},
        )
        basic_snapshot = {
            "stock_code": "600519",
            "stock_name": "Kweichow Moutai",
            "market": "cn",
            "quote": {
                "current_price": 100.0,
                "change_percent": 1.2,
                "source": "unit-test",
                "freshness": "fresh",
            },
            "indicators": {"ma5": 99.0, "ma20": 95.0},
        }
        service_instance = MagicMock()
        service_instance.last_error = None
        service_instance.analyze_stock.return_value = _analysis_payload()

        with patch("src.services.basic_query_service.BasicQueryService.get_snapshot", return_value=basic_snapshot):
            no_ai = self.client.get("/api/v1/stocks/600519/snapshot")
        self.assertEqual(no_ai.status_code, 200)
        quick_before = PlatformAccountService().get_feature_quota_status(user_id, "ai_quick")
        self.assertEqual(quick_before["used"], 0)

        with patch("src.services.analysis_service.AnalysisService", return_value=service_instance), \
             patch("api.v1.endpoints.analysis._load_sync_fundamental_sources", return_value=(None, None)):
            quick = self.client.post(
                "/api/v1/analysis/analyze",
                json={"stock_code": "600519", "async_mode": False, "analysisDepth": "fast"},
            )
            byok_deep = self.client.post(
                "/api/v1/analysis/analyze",
                json={
                    "stock_code": "600519",
                    "async_mode": False,
                    "analysisDepth": "deep",
                    "apiKeyMode": "user",
                },
            )

        self.assertEqual(quick.status_code, 200)
        self.assertEqual(byok_deep.status_code, 200)
        account = self.client.get("/api/v1/platform/account").json()
        buckets = {bucket["quota_bucket"]: bucket for bucket in account["quota_buckets"]}
        self.assertEqual(buckets["ai_quick"]["used"], 1)
        self.assertEqual(buckets["ai_deep_user_key"]["used"], 1)
        self.assertEqual(buckets["ai_deep"]["used"], 0)
        byok_call = service_instance.analyze_stock.call_args_list[-1].kwargs
        self.assertEqual(byok_call["api_key_mode"], "user")
        self.assertEqual(byok_call["platform_user_id"], user_id)
        DatabaseManager.get_instance().save_analysis_history(
            result=_history_result(),
            query_id="flow-history",
            report_type="detailed",
            news_content=None,
            platform_user_id=user_id,
        )

        history = self.client.get("/api/v1/history")
        self.assertEqual(history.status_code, 200)
        self.assertGreaterEqual(history.json()["total"], 1)

        for i in range(4):
            PlatformAccountService().reserve_feature_quota(user_id, "ai_quick", reference_id=f"fill-{i}")
        exhausted = self.client.post(
            "/api/v1/analysis/analyze",
            json={"stock_code": "600519", "async_mode": False, "analysisDepth": "fast"},
        )
        self.assertEqual(exhausted.status_code, 429)
        self.assertEqual(exhausted.json()["error"], "quota_exceeded")
        self.assertIn("Weekly analysis quota exhausted", exhausted.json()["message"])

    def test_regular_user_cannot_access_admin_data_or_other_user_history(self) -> None:
        owner_id = self._register("owner@example.com")
        other = PlatformAccountService().create_user("other@example.com", "password123")
        DatabaseManager.get_instance().save_analysis_history(
            result=_history_result("AAPL"),
            query_id="other-history",
            report_type="detailed",
            news_content=None,
            platform_user_id=int(other.id),
        )

        admin = self.client.get("/api/v1/platform/admin/users")
        history = self.client.get("/api/v1/history")
        account = self.client.get("/api/v1/platform/account")

        self.assertEqual(admin.status_code, 403)
        self.assertEqual(history.status_code, 200)
        self.assertEqual(history.json()["total"], 0)
        self.assertEqual(account.status_code, 200)
        self.assertEqual(account.json()["user"]["id"], owner_id)


if __name__ == "__main__":
    unittest.main()
