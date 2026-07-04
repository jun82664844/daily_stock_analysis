import hashlib
import hmac
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


SANDBOX_SECRET = "local-sandbox-secret"


def _signature(body: bytes) -> str:
    return hmac.new(SANDBOX_SECRET.encode("utf-8"), body, hashlib.sha256).hexdigest()


class BillingSandboxFlowTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.db_path = os.path.join(self.temp_dir.name, "billing-sandbox.sqlite")
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

    def _register(self) -> int:
        response = self.client.post(
            "/api/v1/platform/register",
            json={"email": "sandbox@example.com", "password": "password123"},
        )
        self.assertEqual(response.status_code, 200)
        return int(response.json()["user"]["id"])

    def test_sandbox_checkout_requires_enabled_sandbox_provider(self) -> None:
        self._register()
        with patch.dict(os.environ, {"BILLING_ENABLED": "false", "BILLING_PROVIDER": "sandbox"}, clear=False):
            disabled = self.client.post("/api/v1/billing/checkout", json={"plan": "pro"})
        with patch.dict(os.environ, {"BILLING_ENABLED": "true", "BILLING_PROVIDER": "disabled"}, clear=False):
            wrong_provider = self.client.post("/api/v1/billing/checkout", json={"plan": "pro"})

        self.assertEqual(disabled.status_code, 400)
        self.assertEqual(disabled.json()["error"], "billing_disabled")
        self.assertEqual(wrong_provider.status_code, 501)
        self.assertEqual(wrong_provider.json()["error"], "billing_provider_not_configured")

    def test_sandbox_webhook_rejects_missing_or_bad_signature(self) -> None:
        payload = {"event": "checkout.completed", "provider_session_id": "sandbox_1_pro_invalid"}
        body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        with patch.dict(os.environ, {"BILLING_ENABLED": "true", "BILLING_PROVIDER": "sandbox"}, clear=False):
            missing = self.client.post("/api/v1/billing/webhook", content=body)
            bad = self.client.post(
                "/api/v1/billing/webhook",
                content=body,
                headers={"X-DSA-Billing-Signature": "bad-signature"},
            )

        self.assertEqual(missing.status_code, 400)
        self.assertEqual(missing.json()["error"], "invalid_signature")
        self.assertEqual(bad.status_code, 400)
        self.assertEqual(bad.json()["error"], "invalid_signature")

    def test_sandbox_checkout_and_signed_webhook_upgrade_free_user_to_pro(self) -> None:
        user_id = self._register()
        with patch.dict(os.environ, {"BILLING_ENABLED": "true", "BILLING_PROVIDER": "sandbox"}, clear=False):
            checkout = self.client.post("/api/v1/billing/checkout", json={"plan": "pro"})
        self.assertEqual(checkout.status_code, 200)
        session = checkout.json()
        self.assertEqual(session["provider"], "sandbox")
        self.assertEqual(session["plan"], "pro")
        self.assertIn("/sandbox/checkout/", session["checkout_url"])
        self.assertEqual(PlatformAccountService().get_user(user_id).plan, "free")

        payload = {"event": "checkout.completed", "provider_session_id": session["provider_session_id"]}
        body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        with patch.dict(os.environ, {"BILLING_ENABLED": "true", "BILLING_PROVIDER": "sandbox"}, clear=False):
            webhook = self.client.post(
                "/api/v1/billing/webhook",
                content=body,
                headers={"X-DSA-Billing-Signature": _signature(body)},
            )

        self.assertEqual(webhook.status_code, 200)
        self.assertEqual(webhook.json()["status"], "processed")
        self.assertEqual(webhook.json()["user"]["plan"], "pro")
        self.assertEqual(PlatformAccountService().get_user(user_id).plan, "pro")
        account = self.client.get("/api/v1/platform/account")
        self.assertEqual(account.status_code, 200)
        self.assertEqual(account.json()["user"]["plan"], "pro")
        buckets = {bucket["quota_bucket"]: bucket for bucket in account.json()["quota_buckets"]}
        self.assertEqual(buckets["ai_quick"]["weekly_limit"], 100)
        self.assertEqual(buckets["ai_deep"]["weekly_limit"], 30)


if __name__ == "__main__":
    unittest.main()
