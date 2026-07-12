import hashlib
import hmac
import json
import os
import tempfile
import unittest
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from api.app import create_app
from src.config import Config
from src.platform_accounts import PlatformAccountService
from src.storage import DatabaseManager, PlatformQuotaGrant, utc_naive_now


SANDBOX_SECRET = "local-subscription-lifecycle-secret"


def _signature(body: bytes) -> str:
    return hmac.new(SANDBOX_SECRET.encode("utf-8"), body, hashlib.sha256).hexdigest()


def _json_body(payload: dict) -> bytes:
    return json.dumps(payload, separators=(",", ":")).encode("utf-8")


class BillingSubscriptionLifecycleTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.db_path = os.path.join(self.temp_dir.name, "billing-lifecycle.sqlite")
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

    def _new_client(self) -> TestClient:
        return TestClient(create_app(static_dir=self.static_dir))

    def _register(self, client: TestClient, email: str) -> int:
        response = client.post(
            "/api/v1/platform/register",
            json={"email": email, "password": "password123"},
        )
        self.assertEqual(response.status_code, 200)
        return int(response.json()["user"]["id"])

    def _checkout(self, client: TestClient, plan: str = "pro") -> dict:
        response = client.post("/api/v1/billing/checkout", json={"plan": plan})
        self.assertEqual(response.status_code, 200)
        return response.json()

    def _signed_webhook(self, payload: dict):
        body = _json_body(payload)
        return self.client.post(
            "/api/v1/billing/webhook",
            content=body,
            headers={"X-DSA-Billing-Signature": _signature(body)},
        )

    def test_checkout_persists_local_session_and_user_billing_summary(self) -> None:
        user_id = self._register(self.client, "billing-summary@example.com")

        checkout = self._checkout(self.client, "pro")
        account = self.client.get("/api/v1/billing/account")

        self.assertEqual(account.status_code, 200)
        body = account.json()
        self.assertTrue(body["billing_enabled"])
        self.assertEqual(body["provider"], "sandbox")
        self.assertEqual(body["subscription"]["user_id"], user_id)
        self.assertEqual(body["subscription"]["plan"], "free")
        self.assertEqual(body["subscription"]["status"], "none")
        self.assertEqual(body["checkout_sessions"][0]["provider_session_id"], checkout["provider_session_id"])
        self.assertEqual(body["checkout_sessions"][0]["plan"], "pro")
        self.assertEqual(body["checkout_sessions"][0]["status"], "created")
        self.assertIn("local sandbox", body["copy"].lower())
        self.assertIn("not real payment", body["copy"].lower())
        self.assertIn("checkout.created", {event["event_type"] for event in body["recent_events"]})

    def test_completed_webhook_is_idempotent_and_updates_subscription_once(self) -> None:
        user_id = self._register(self.client, "billing-idempotent@example.com")
        checkout = self._checkout(self.client, "pro")
        payload = {
            "event": "checkout.completed",
            "provider_event_id": "evt_completed_once",
            "provider_session_id": checkout["provider_session_id"],
        }

        first = self._signed_webhook(payload)
        duplicate = self._signed_webhook(payload)
        account = self.client.get("/api/v1/billing/account").json()

        self.assertEqual(first.status_code, 200)
        self.assertEqual(first.json()["status"], "processed")
        self.assertFalse(first.json()["idempotent"])
        self.assertEqual(duplicate.status_code, 200)
        self.assertEqual(duplicate.json()["status"], "processed")
        self.assertTrue(duplicate.json()["idempotent"])
        self.assertEqual(PlatformAccountService().get_user(user_id).plan, "pro")
        self.assertEqual(account["subscription"]["plan"], "pro")
        self.assertEqual(account["subscription"]["status"], "active")
        self.assertEqual(account["checkout_sessions"][0]["status"], "completed")
        events = [event for event in account["recent_events"] if event["provider_event_id"] == "evt_completed_once"]
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["processing_status"], "processed")
        with DatabaseManager.get_instance().get_session() as session:
            membership_grants = session.query(PlatformQuotaGrant).filter_by(
                user_id=user_id,
                source_type="membership",
            ).all()
            self.assertEqual(len(membership_grants), 1)
            self.assertEqual(membership_grants[0].flash_total, 268)
            self.assertEqual(membership_grants[0].pro_total, 28)

    def test_subscription_update_parses_period_and_refreshes_member_grant_once(self) -> None:
        user_id = self._register(self.client, "billing-period-v112@example.com")
        starts_at = utc_naive_now()
        expires_at = starts_at + timedelta(days=31)
        payload = {
            "event": "subscription.updated",
            "provider_event_id": "evt_period_v112",
            "provider_subscription_id": "sub_period_v112",
            "user_id": user_id,
            "plan": "max",
            "subscription_status": "active",
            "current_period_start": starts_at.isoformat(),
            "current_period_end": expires_at.isoformat(),
            "expires_at": expires_at.isoformat(),
        }

        first = self._signed_webhook(payload)
        duplicate = self._signed_webhook(payload)

        self.assertEqual(first.status_code, 200)
        self.assertEqual(duplicate.status_code, 200)
        with DatabaseManager.get_instance().get_session() as session:
            grant = session.query(PlatformQuotaGrant).filter_by(
                user_id=user_id,
                source_type="membership",
            ).one()
            self.assertEqual(grant.flash_total, 1688)
            self.assertEqual(grant.pro_total, 168)
            self.assertEqual(grant.expires_at, expires_at)

    def test_cancel_expire_and_payment_failed_events_do_not_upgrade_plan(self) -> None:
        user_id = self._register(self.client, "billing-negative@example.com")
        event_cases = (
            ("checkout.cancelled", "cancelled"),
            ("checkout.expired", "expired"),
            ("payment.failed", "failed"),
        )

        for index, (event_type, expected_status) in enumerate(event_cases, start=1):
            checkout = self._checkout(self.client, "pro")
            response = self._signed_webhook(
                {
                    "event": event_type,
                    "provider_event_id": f"evt_negative_{index}",
                    "provider_session_id": checkout["provider_session_id"],
                }
            )
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["status"], "processed")
            self.assertEqual(response.json()["checkout_status"], expected_status)

        self.assertEqual(PlatformAccountService().get_user(user_id).plan, "free")
        account = self.client.get("/api/v1/billing/account").json()
        statuses = {session["status"] for session in account["checkout_sessions"]}
        self.assertIn("cancelled", statuses)
        self.assertIn("expired", statuses)
        self.assertIn("failed", statuses)
        self.assertEqual(account["subscription"]["plan"], "free")
        self.assertEqual(account["subscription"]["status"], "none")

    def test_subscription_updated_reconciles_plan_for_signed_sandbox_events(self) -> None:
        user_id = self._register(self.client, "billing-reconcile@example.com")

        upgrade = self._signed_webhook(
            {
                "event": "subscription.updated",
                "provider_event_id": "evt_subscription_enterprise",
                "user_id": user_id,
                "plan": "enterprise",
                "subscription_status": "active",
            }
        )
        downgrade = self._signed_webhook(
            {
                "event": "subscription.updated",
                "provider_event_id": "evt_subscription_free",
                "user_id": user_id,
                "plan": "free",
                "subscription_status": "active",
            }
        )

        self.assertEqual(upgrade.status_code, 200)
        self.assertEqual(upgrade.json()["plan"], "enterprise")
        self.assertEqual(downgrade.status_code, 200)
        self.assertEqual(downgrade.json()["plan"], "free")
        self.assertEqual(PlatformAccountService().get_user(user_id).plan, "free")
        account = self.client.get("/api/v1/billing/account").json()
        self.assertEqual(account["subscription"]["plan"], "free")
        self.assertEqual(account["subscription"]["status"], "active")

    def test_regular_user_cannot_view_admin_billing_events_or_other_user_billing(self) -> None:
        user_a_id = self._register(self.client, "billing-a@example.com")
        checkout = self._checkout(self.client, "pro")
        completed = self._signed_webhook(
            {
                "event": "checkout.completed",
                "provider_event_id": "evt_user_a_completed",
                "provider_session_id": checkout["provider_session_id"],
            }
        )
        self.assertEqual(completed.status_code, 200)

        user_b_client = self._new_client()
        try:
            self._register(user_b_client, "billing-b@example.com")
            user_b_account = user_b_client.get("/api/v1/billing/account")
            forbidden = user_b_client.get("/api/v1/billing/admin/events")
        finally:
            user_b_client.close()

        self.assertEqual(user_b_account.status_code, 200)
        self.assertEqual(user_b_account.json()["checkout_sessions"], [])
        self.assertNotIn("evt_user_a_completed", str(user_b_account.json()))
        self.assertEqual(forbidden.status_code, 403)

        admin_client = self._new_client()
        try:
            PlatformAccountService().create_user(
                "billing-admin@example.com",
                "password123",
                plan="enterprise",
                role="admin",
            )
            login = admin_client.post(
                "/api/v1/platform/login",
                json={"email": "billing-admin@example.com", "password": "password123"},
            )
            self.assertEqual(login.status_code, 200)
            admin_events = admin_client.get("/api/v1/billing/admin/events")
        finally:
            admin_client.close()

        self.assertEqual(admin_events.status_code, 200)
        self.assertIn("evt_user_a_completed", str(admin_events.json()))
        self.assertIn(user_a_id, {event["user_id"] for event in admin_events.json()["events"]})


if __name__ == "__main__":
    unittest.main()
