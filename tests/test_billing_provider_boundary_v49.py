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


class BillingProviderBoundaryV49TestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.db_path = os.path.join(self.temp_dir.name, "billing-provider-v49.sqlite")
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
            json={"email": "billing-v49@example.com", "password": "password123"},
        )
        self.assertEqual(response.status_code, 200)
        return int(response.json()["user"]["id"])

    def test_provider_status_reports_disabled_sandbox_and_real_provider_without_secrets(self) -> None:
        from src.billing.payment_provider import get_payment_provider_status

        with patch.dict(os.environ, {"BILLING_ENABLED": "false", "BILLING_PROVIDER": "disabled"}, clear=False):
            disabled = get_payment_provider_status()
        with patch.dict(os.environ, {"BILLING_ENABLED": "true", "BILLING_PROVIDER": "sandbox"}, clear=False):
            sandbox = get_payment_provider_status()
        with patch.dict(
            os.environ,
            {
                "BILLING_ENABLED": "true",
                "BILLING_PROVIDER": "stripe",
                "BILLING_STRIPE_SECRET_KEY": "sk_test_v49_should_not_leak",
                "BILLING_STRIPE_WEBHOOK_SECRET": "whsec_v49_should_not_leak",
            },
            clear=False,
        ):
            stripe = get_payment_provider_status()

        self.assertFalse(disabled["billing_enabled"])
        self.assertEqual(disabled["mode"], "disabled")
        self.assertTrue(sandbox["configuration_ready"])
        self.assertEqual(sandbox["mode"], "local_sandbox")
        self.assertEqual(stripe["provider"], "stripe")
        self.assertEqual(stripe["mode"], "real_provider_missing_config")
        self.assertFalse(stripe["adapter_implemented"])
        self.assertIn("BILLING_STRIPE_PRICE_PRO", stripe["missing_config"])
        self.assertNotIn("sk_test_v49_should_not_leak", json.dumps(stripe))
        self.assertNotIn("whsec_v49_should_not_leak", json.dumps(stripe))

    def test_real_provider_checkout_fails_closed_when_config_is_missing(self) -> None:
        self._register()

        with patch.dict(
            os.environ,
            {
                "BILLING_ENABLED": "true",
                "BILLING_PROVIDER": "stripe",
                "BILLING_STRIPE_SECRET_KEY": "sk_test_v49_should_not_leak",
            },
            clear=False,
        ):
            response = self.client.post("/api/v1/billing/checkout", json={"plan": "pro"})

        payload = response.json()
        self.assertEqual(response.status_code, 503)
        self.assertEqual(payload["error"], "billing_provider_not_ready")
        self.assertEqual(payload["provider"], "stripe")
        self.assertIn("BILLING_STRIPE_WEBHOOK_SECRET", payload["missing_config"])
        self.assertIn("BILLING_STRIPE_PRICE_PRO", payload["missing_config"])
        self.assertNotIn("sk_test_v49_should_not_leak", json.dumps(payload))

    def test_real_provider_checkout_still_does_not_process_payment_when_config_exists(self) -> None:
        self._register()

        with patch.dict(
            os.environ,
            {
                "BILLING_ENABLED": "true",
                "BILLING_PROVIDER": "stripe",
                "BILLING_STRIPE_SECRET_KEY": "sk_test_v49_should_not_leak",
                "BILLING_STRIPE_WEBHOOK_SECRET": "whsec_v49_should_not_leak",
                "BILLING_STRIPE_PRICE_PRO": "price_v49_pro",
            },
            clear=False,
        ):
            response = self.client.post("/api/v1/billing/checkout", json={"plan": "pro"})

        payload = response.json()
        self.assertEqual(response.status_code, 501)
        self.assertEqual(payload["error"], "billing_provider_adapter_not_implemented")
        self.assertEqual(payload["provider"], "stripe")
        self.assertFalse(payload["adapter_implemented"])
        self.assertNotIn("sk_test_v49_should_not_leak", json.dumps(payload))
        self.assertNotIn("whsec_v49_should_not_leak", json.dumps(payload))

    def test_billing_account_includes_sanitized_provider_readiness(self) -> None:
        self._register()

        with patch.dict(
            os.environ,
            {
                "BILLING_ENABLED": "true",
                "BILLING_PROVIDER": "stripe",
                "BILLING_STRIPE_SECRET_KEY": "sk_test_v49_should_not_leak",
            },
            clear=False,
        ):
            response = self.client.get("/api/v1/billing/account")

        self.assertEqual(response.status_code, 200)
        readiness = response.json()["provider_readiness"]
        self.assertEqual(readiness["provider"], "stripe")
        self.assertFalse(readiness["configuration_ready"])
        self.assertIn("BILLING_STRIPE_WEBHOOK_SECRET", readiness["missing_config"])
        self.assertNotIn("sk_test_v49_should_not_leak", json.dumps(readiness))


if __name__ == "__main__":
    unittest.main()
