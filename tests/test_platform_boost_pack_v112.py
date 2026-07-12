# -*- coding: utf-8 -*-
from __future__ import annotations

import os
import hashlib
import hmac
import json
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from api.app import create_app
from src.config import Config
from src.platform_accounts import membership_month_quota, normalize_membership_plan
from src.services.api_boost_pack_service import ApiBoostPackService, MemberApiQuotaExceeded
from src.storage import (
    DatabaseManager,
    PlatformBillingSubscription,
    PlatformQuotaGrant,
    utc_naive_now,
)


SANDBOX_SECRET = "v112-boost-pack-secret"


class PlatformBoostPackV112TestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.db_path = os.path.join(self.temp_dir.name, "boost-pack-v112.sqlite")
        DatabaseManager.reset_instance()
        self.db = DatabaseManager(db_url=f"sqlite:///{self.db_path}")
        self.service = ApiBoostPackService(self.db)

    def tearDown(self) -> None:
        DatabaseManager.reset_instance()
        self.temp_dir.cleanup()

    def _user(self, email: str = "boost-v112@example.com", plan: str = "pro"):
        from src.platform_accounts import PlatformAccountService

        return PlatformAccountService(self.db).create_user(email, "password123", plan=plan)

    def _grant(
        self,
        user_id: int,
        source_type: str,
        *,
        flash: int = 0,
        pro: int = 0,
        reference: str,
        expires_in_days: int = 10,
    ) -> PlatformQuotaGrant:
        now = utc_naive_now()
        with self.db.session_scope() as session:
            grant = PlatformQuotaGrant(
                user_id=user_id,
                source_type=source_type,
                source_reference=reference,
                flash_total=flash,
                flash_used=0,
                pro_total=pro,
                pro_used=0,
                starts_at=now - timedelta(minutes=1),
                expires_at=now + timedelta(days=expires_in_days),
                status="active",
                created_at=now,
            )
            session.add(grant)
            session.flush()
            grant_id = int(grant.id)
        with self.db.get_session() as session:
            row = session.get(PlatformQuotaGrant, grant_id)
            session.expunge(row)
            return row

    def test_v112_membership_quota_contract(self) -> None:
        self.assertEqual(normalize_membership_plan("premium"), "max")
        self.assertEqual(normalize_membership_plan("plus"), "plus")
        self.assertEqual(membership_month_quota("pro"), {"flash": 268, "pro": 28})
        self.assertEqual(membership_month_quota("max"), {"flash": 1688, "pro": 168})
        self.assertEqual(membership_month_quota("plus"), {"flash": 0, "pro": 0})

    def test_quota_grant_has_separate_flash_pro_and_expiry(self) -> None:
        user = self._user()
        grant = self._grant(
            user.id,
            "boost_pack",
            flash=168,
            pro=28,
            reference="evt_paid_1",
        )
        self.assertEqual(grant.flash_total, 168)
        self.assertEqual(grant.pro_total, 28)
        self.assertGreater(grant.expires_at, grant.starts_at)

    def test_membership_period_grant_is_idempotent_and_uses_plan_allowance(self) -> None:
        user = self._user(plan="pro")
        starts_at = utc_naive_now()
        expires_at = starts_at + timedelta(days=30)

        first = self.service.grant_membership_period(
            user_id=user.id,
            plan="pro",
            period_reference="sub-v112:2026-07",
            starts_at=starts_at,
            expires_at=expires_at,
        )
        duplicate = self.service.grant_membership_period(
            user_id=user.id,
            plan="pro",
            period_reference="sub-v112:2026-07",
            starts_at=starts_at,
            expires_at=expires_at,
        )

        self.assertEqual(first.id, duplicate.id)
        self.assertEqual(first.flash_total, 268)
        self.assertEqual(first.pro_total, 28)
        with self.db.get_session() as session:
            self.assertEqual(
                session.query(PlatformQuotaGrant).filter_by(
                    source_reference="membership:sub-v112:2026-07"
                ).count(),
                1,
            )

    def test_member_grant_is_spent_before_boost_grant(self) -> None:
        user = self._user()
        base = self._grant(user.id, "membership", flash=1, reference="member-1")
        boost = self._grant(user.id, "boost_pack", flash=168, pro=28, reference="boost-1")

        self.service.reserve(user.id, "flash", 2, "analysis:req-1")

        with self.db.get_session() as session:
            self.assertEqual(session.get(PlatformQuotaGrant, base.id).flash_used, 1)
            self.assertEqual(session.get(PlatformQuotaGrant, boost.id).flash_used, 1)

    def test_insufficient_combined_balance_does_not_partially_debit(self) -> None:
        user = self._user()
        grant = self._grant(user.id, "membership", flash=1, reference="member-2")

        with self.assertRaises(MemberApiQuotaExceeded):
            self.service.reserve(user.id, "flash", 2, "analysis:req-2")

        with self.db.get_session() as session:
            self.assertEqual(session.get(PlatformQuotaGrant, grant.id).flash_used, 0)

    def test_failed_analysis_releases_same_reservation_once(self) -> None:
        user = self._user()
        self._grant(user.id, "boost_pack", flash=168, pro=28, reference="boost-3")
        self.service.reserve(user.id, "pro", 3, "analysis:req-3")

        first = self.service.release("analysis:req-3")
        second = self.service.release("analysis:req-3")

        self.assertTrue(first["released"])
        self.assertFalse(second["released"])
        self.assertEqual(self.service.balance(user.id)["pro"], 28)

    def test_duplicate_reference_does_not_debit_twice(self) -> None:
        user = self._user()
        self._grant(user.id, "boost_pack", flash=5, reference="boost-4")

        first = self.service.reserve(user.id, "flash", 2, "analysis:req-4")
        duplicate = self.service.reserve(user.id, "flash", 2, "analysis:req-4")

        self.assertEqual(first["reference_id"], duplicate["reference_id"])
        self.assertEqual(self.service.balance(user.id)["flash"], 3)


if __name__ == "__main__":
    unittest.main()


class PlatformBoostPackBillingApiV112TestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.db_path = os.path.join(self.temp_dir.name, "boost-pack-api-v112.sqlite")
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
                "BILLING_ENABLED": "true",
                "BILLING_PROVIDER": "sandbox",
                "BILLING_SANDBOX_SECRET": SANDBOX_SECRET,
                "PLATFORM_BOOST_PACK_ENABLED": "true",
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

    def _register(self, email: str, *, plan: str) -> int:
        response = self.client.post(
            "/api/v1/platform/register",
            json={"email": email, "password": "password123"},
        )
        self.assertEqual(response.status_code, 200)
        user_id = int(response.json()["user"]["id"])
        from src.platform_accounts import PlatformAccountService

        PlatformAccountService().set_user_plan(user_id, plan)
        now = utc_naive_now()
        with DatabaseManager.get_instance().session_scope() as session:
            subscription = session.query(PlatformBillingSubscription).filter_by(user_id=user_id).first()
            if subscription is None:
                subscription = PlatformBillingSubscription(user_id=user_id, provider="sandbox")
                session.add(subscription)
            subscription.plan = plan
            subscription.status = "active"
            subscription.current_period_start = now - timedelta(days=1)
            subscription.current_period_end = now + timedelta(days=29)
            subscription.expires_at = now + timedelta(days=29)
        return user_id

    def _signed_webhook(self, payload: dict):
        body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        signature = hmac.new(SANDBOX_SECRET.encode("utf-8"), body, hashlib.sha256).hexdigest()
        return self.client.post(
            "/api/v1/billing/webhook",
            content=body,
            headers={"X-DSA-Billing-Signature": signature},
        )

    def test_completed_boost_pack_checkout_grants_quota_without_changing_plan(self) -> None:
        user_id = self._register("boost-paid@example.com", plan="pro")
        checkout = self.client.post(
            "/api/v1/billing/boost-pack/checkout",
            json={"product_code": "api_boost_168_28"},
        )
        self.assertEqual(checkout.status_code, 200)
        payload = checkout.json()

        completed = self._signed_webhook(
            {
                "event": "checkout.completed",
                "provider_event_id": "evt_v112_boost_paid",
                "provider_session_id": payload["provider_session_id"],
            }
        )
        duplicate = self._signed_webhook(
            {
                "event": "checkout.completed",
                "provider_event_id": "evt_v112_boost_paid",
                "provider_session_id": payload["provider_session_id"],
            }
        )

        self.assertEqual(completed.status_code, 200)
        self.assertEqual(duplicate.status_code, 200)
        self.assertTrue(duplicate.json()["idempotent"])
        from src.platform_accounts import PlatformAccountService

        self.assertEqual(PlatformAccountService().get_user(user_id).plan, "pro")
        self.assertEqual(ApiBoostPackService().balance(user_id), {"flash": 168, "pro": 28})
        with DatabaseManager.get_instance().get_session() as session:
            grants = session.query(PlatformQuotaGrant).filter_by(
                source_reference="evt_v112_boost_paid"
            ).all()
            self.assertEqual(len(grants), 1)

    def test_boost_pack_requires_active_pro_or_max(self) -> None:
        self._register("boost-plus@example.com", plan="plus")

        response = self.client.post(
            "/api/v1/billing/boost-pack/checkout",
            json={"product_code": "api_boost_168_28"},
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["error"], "boost_pack_not_available")

    def test_boost_pack_rejects_subscription_with_less_than_one_hour_remaining(self) -> None:
        user_id = self._register("boost-expiring@example.com", plan="max")
        with DatabaseManager.get_instance().session_scope() as session:
            subscription = session.query(PlatformBillingSubscription).filter_by(user_id=user_id).one()
            subscription.current_period_end = utc_naive_now() + timedelta(minutes=30)
            subscription.expires_at = utc_naive_now() + timedelta(minutes=30)

        response = self.client.post(
            "/api/v1/billing/boost-pack/checkout",
            json={"product_code": "api_boost_168_28"},
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["error"], "renew_membership_first")
