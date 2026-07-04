import hashlib
import hmac
import json
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


SANDBOX_SECRET = "local-e2e-sandbox-secret"


def _signature(body: bytes) -> str:
    return hmac.new(SANDBOX_SECRET.encode("utf-8"), body, hashlib.sha256).hexdigest()


def _analysis_payload(stock_code: str = "600519") -> dict:
    return {
        "stock_code": stock_code,
        "stock_name": "Kweichow Moutai",
        "report": {
            "meta": {"stock_code": stock_code, "stock_name": "Kweichow Moutai", "report_language": "en"},
            "summary": {"analysis_summary": "informational E2E safety summary"},
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
        analysis_summary="informational E2E safety summary",
        news_summary="",
        technical_analysis="",
        fundamental_analysis="",
        risk_warning="",
        data_sources="unit-test",
        raw_response=None,
        success=True,
    )


class PlatformUserE2ESafetyTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.db_path = os.path.join(self.temp_dir.name, "platform-user-e2e-safety.sqlite")
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
                "PLATFORM_RATE_LIMIT_ENABLED": "true",
                "PLATFORM_RATE_LIMIT_WINDOW_SECONDS": "60",
                "PLATFORM_RATE_LIMIT_REGISTER_MAX": "2",
                "PLATFORM_RATE_LIMIT_API_KEYS_MAX": "1",
                "PLATFORM_RATE_LIMIT_ANALYSIS_MAX": "1",
                "PLATFORM_RATE_LIMIT_BILLING_CHECKOUT_MAX": "1",
                "PLATFORM_RATE_LIMIT_BILLING_WEBHOOK_MAX": "1",
                "BILLING_ENABLED": "true",
                "BILLING_PROVIDER": "sandbox",
                "BILLING_SANDBOX_SECRET": SANDBOX_SECRET,
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

    def _register(self, email: str = "e2e+safety@example.test") -> int:
        response = self.client.post(
            "/api/v1/platform/register",
            json={"email": email, "password": "password123"},
        )
        self.assertEqual(response.status_code, 200)
        return int(response.json()["user"]["id"])

    def test_register_rate_limit_is_ip_and_endpoint_scoped(self) -> None:
        first = self.client.post(
            "/api/v1/platform/register",
            json={"email": "e2e+rate-a@example.test", "password": "password123"},
        )
        second = self.client.post(
            "/api/v1/platform/register",
            json={"email": "e2e+rate-b@example.test", "password": "password123"},
        )
        limited = self.client.post(
            "/api/v1/platform/register",
            json={"email": "e2e+rate-c@example.test", "password": "password123"},
        )

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(limited.status_code, 429)
        self.assertEqual(limited.json()["error"], "rate_limited")
        self.assertIn("message", limited.json())
        self.assertIn("retry_after_seconds", limited.json())

    def test_user_write_endpoints_return_clear_429_when_limited(self) -> None:
        self._register()

        first_key = self.client.post(
            "/api/v1/platform/api-keys",
            json={"provider": "deepseek", "apiKey": "sk-e2e-safety-secret", "model": "deepseek/deepseek-v4-flash"},
        )
        limited_key = self.client.post(
            "/api/v1/platform/api-keys",
            json={"provider": "deepseek", "apiKey": "sk-e2e-safety-secret-2", "model": "deepseek/deepseek-v4-flash"},
        )

        service_instance = MagicMock()
        service_instance.last_error = None
        service_instance.analyze_stock.return_value = _analysis_payload()
        with patch("src.services.analysis_service.AnalysisService", return_value=service_instance), \
             patch("api.v1.endpoints.analysis._load_sync_fundamental_sources", return_value=(None, None)):
            first_analysis = self.client.post(
                "/api/v1/analysis/analyze",
                json={"stock_code": "600519", "async_mode": False, "analysisDepth": "fast"},
            )
            limited_analysis = self.client.post(
                "/api/v1/analysis/analyze",
                json={"stock_code": "600519", "async_mode": False, "analysisDepth": "fast"},
            )

        first_checkout = self.client.post("/api/v1/billing/checkout", json={"plan": "pro"})
        limited_checkout = self.client.post("/api/v1/billing/checkout", json={"plan": "pro"})

        self.assertEqual(first_key.status_code, 200)
        self.assertEqual(limited_key.status_code, 429)
        self.assertEqual(limited_key.json()["error"], "rate_limited")
        self.assertEqual(first_analysis.status_code, 200)
        self.assertEqual(limited_analysis.status_code, 429)
        self.assertEqual(limited_analysis.json()["error"], "rate_limited")
        self.assertEqual(first_checkout.status_code, 200)
        self.assertEqual(limited_checkout.status_code, 429)
        self.assertEqual(limited_checkout.json()["error"], "rate_limited")

    def test_webhook_attempts_are_rate_limited_without_counting_as_success(self) -> None:
        payload = {"event": "checkout.completed", "provider_session_id": "sandbox_999_pro_rate"}
        body = json.dumps(payload, separators=(",", ":")).encode("utf-8")

        invalid_signature = self.client.post(
            "/api/v1/billing/webhook",
            content=body,
            headers={"X-DSA-Billing-Signature": "bad-signature"},
        )
        limited = self.client.post(
            "/api/v1/billing/webhook",
            content=body,
            headers={"X-DSA-Billing-Signature": _signature(body)},
        )

        self.assertEqual(invalid_signature.status_code, 400)
        self.assertEqual(invalid_signature.json()["error"], "invalid_signature")
        self.assertEqual(limited.status_code, 429)
        self.assertEqual(limited.json()["error"], "rate_limited")

    def test_e2e_cleanup_dry_run_counts_only_e2e_namespace(self) -> None:
        from scripts.cleanup_platform_e2e_data import collect_e2e_cleanup_plan

        service = PlatformAccountService()
        e2e_user = service.create_user("e2e+cleanup@example.test", "password123")
        normal_user = service.create_user("normal@example.test", "password123")
        service.store_api_key(int(e2e_user.id), provider="deepseek", api_key="sk-e2e-cleanup-secret", model="deepseek/test")
        service.store_api_key(int(normal_user.id), provider="deepseek", api_key="sk-normal-secret", model="deepseek/test")
        service.reserve_feature_quota(int(e2e_user.id), "ai_quick", reference_id="e2e-cleanup")
        service.reserve_feature_quota(int(normal_user.id), "ai_quick", reference_id="normal")
        DatabaseManager.get_instance().save_analysis_history(
            result=_history_result(),
            query_id="e2e-cleanup-history",
            report_type="detailed",
            news_content=None,
            platform_user_id=int(e2e_user.id),
        )
        DatabaseManager.get_instance().save_analysis_history(
            result=_history_result("AAPL"),
            query_id="normal-history",
            report_type="detailed",
            news_content=None,
            platform_user_id=int(normal_user.id),
        )

        plan = collect_e2e_cleanup_plan(database_path=self.db_path, email_prefix="e2e+")

        self.assertTrue(plan.dry_run)
        self.assertEqual(plan.matched_users, 1)
        self.assertEqual(plan.api_keys, 1)
        self.assertEqual(plan.usage_events, 1)
        self.assertEqual(plan.analysis_history, 1)
        self.assertEqual(plan.deleted_users, 0)
        self.assertEqual(service.get_user(int(e2e_user.id)).email, "e2e+cleanup@example.test")
        self.assertEqual(service.get_user(int(normal_user.id)).email, "normal@example.test")

    def test_e2e_cleanup_refuses_non_e2e_prefix(self) -> None:
        from scripts.cleanup_platform_e2e_data import collect_e2e_cleanup_plan

        with self.assertRaises(ValueError):
            collect_e2e_cleanup_plan(database_path=self.db_path, email_prefix="normal")


if __name__ == "__main__":
    unittest.main()
