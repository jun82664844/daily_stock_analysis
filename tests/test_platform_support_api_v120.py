# -*- coding: utf-8 -*-
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from api.app import create_app
from src.config import Config
from src.platform_accounts import PlatformAccountService
from src.platform_audit import PlatformAuditLogger
from src.platform_rate_limit import reset_platform_rate_limits
from src.storage import DatabaseManager


class PlatformSupportApiV120TestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.db_path = os.path.join(self.temp_dir.name, "platform-support.sqlite")
        self.static_dir = Path(self.temp_dir.name) / "static"
        self.static_dir.mkdir()
        (self.static_dir / "index.html").write_text("<html>ok</html>", encoding="utf-8")
        DatabaseManager.reset_instance()
        Config.reset_instance()
        reset_platform_rate_limits()
        self.env_patch = patch.dict(
            os.environ,
            {
                "DATABASE_PATH": self.db_path,
                "PLATFORM_USER_AUTH_ENABLED": "true",
                "PLATFORM_CSRF_ENABLED": "true",
                "PLATFORM_RATE_LIMIT_ENABLED": "false",
                "ADMIN_AUTH_ENABLED": "true",
            },
            clear=False,
        )
        self.env_patch.start()
        self.app = create_app(static_dir=self.static_dir)
        self.owner = TestClient(self.app)
        self.other = TestClient(self.app)
        self.admin = TestClient(self.app)
        self.owner_id = self._register(self.owner, "owner-support@example.com")
        self.other_id = self._register(self.other, "other-support@example.com")
        PlatformAccountService().create_user(
            "admin-support@example.com",
            "password123",
            role="admin",
            plan="enterprise",
        )
        admin_login = self.admin.post(
            "/api/v1/platform/login",
            json={"email": "admin-support@example.com", "password": "password123"},
        )
        self.assertEqual(admin_login.status_code, 200)

    def tearDown(self) -> None:
        self.owner.close()
        self.other.close()
        self.admin.close()
        self.env_patch.stop()
        reset_platform_rate_limits()
        DatabaseManager.reset_instance()
        Config.reset_instance()
        self.temp_dir.cleanup()

    def _register(self, client: TestClient, email: str) -> int:
        response = client.post(
            "/api/v1/platform/register",
            json={"email": email, "password": "password123"},
        )
        self.assertEqual(response.status_code, 200)
        return int(response.json()["user"]["id"])

    @staticmethod
    def _csrf_headers(client: TestClient) -> dict[str, str]:
        token = client.cookies.get("dsa_csrf_token")
        if not token:
            raise AssertionError("expected CSRF cookie")
        return {"X-DSA-CSRF": token}

    def _create_ticket(self, client: TestClient | None = None) -> dict:
        active_client = client or self.owner
        response = active_client.post(
            "/api/v1/support/tickets",
            headers=self._csrf_headers(active_client),
            json={
                "category": "market_data",
                "subject": "Quote freshness question",
                "message": "The quote timestamp appears older than expected.",
            },
        )
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()["ticket"]

    def test_login_and_csrf_are_required_for_support_writes(self) -> None:
        anonymous = TestClient(self.app)
        try:
            not_logged_in = anonymous.get("/api/v1/support/tickets")
            missing_csrf = self.owner.post(
                "/api/v1/support/tickets",
                json={"category": "bug", "subject": "Browser page issue", "message": "The page did not load."},
            )
        finally:
            anonymous.close()

        self.assertEqual(not_logged_in.status_code, 401)
        self.assertEqual(missing_csrf.status_code, 403)
        self.assertEqual(missing_csrf.json()["error"], "csrf_failed")

    def test_user_can_create_list_reply_and_close_own_ticket(self) -> None:
        ticket = self._create_ticket()
        ticket_id = int(ticket["id"])

        self.assertEqual(ticket["user_id"], self.owner_id)
        self.assertEqual(ticket["status"], "open")
        self.assertFalse(ticket["unread_by_user"])
        self.assertTrue(ticket["unread_by_admin"])
        self.assertEqual(ticket["messages"][0]["author_role"], "user")
        self.assertTrue(ticket["created_at"].endswith("+00:00"))
        self.assertTrue(ticket["messages"][0]["created_at"].endswith("+00:00"))

        listed = self.owner.get("/api/v1/support/tickets")
        self.assertEqual(listed.status_code, 200)
        self.assertEqual(listed.json()["total"], 1)
        self.assertEqual(listed.json()["tickets"][0]["message_count"], 1)

        reply = self.owner.post(
            f"/api/v1/support/tickets/{ticket_id}/messages",
            headers=self._csrf_headers(self.owner),
            json={"message": "This is still reproducible after refresh."},
        )
        self.assertEqual(reply.status_code, 200)
        self.assertEqual(len(reply.json()["ticket"]["messages"]), 2)
        self.assertTrue(reply.json()["ticket"]["unread_by_admin"])

        closed = self.owner.post(
            f"/api/v1/support/tickets/{ticket_id}/close",
            headers=self._csrf_headers(self.owner),
        )
        self.assertEqual(closed.status_code, 200)
        self.assertEqual(closed.json()["ticket"]["status"], "closed")
        self.assertIsNotNone(closed.json()["ticket"]["closed_at"])

        rejected = self.owner.post(
            f"/api/v1/support/tickets/{ticket_id}/messages",
            headers=self._csrf_headers(self.owner),
            json={"message": "A late follow-up must be rejected."},
        )
        self.assertEqual(rejected.status_code, 409)
        self.assertEqual(rejected.json()["error"], "ticket_closed")

    def test_ticket_ownership_and_admin_boundaries_are_enforced(self) -> None:
        ticket_id = int(self._create_ticket()["id"])

        other_detail = self.other.get(f"/api/v1/support/tickets/{ticket_id}")
        other_reply = self.other.post(
            f"/api/v1/support/tickets/{ticket_id}/messages",
            headers=self._csrf_headers(self.other),
            json={"message": "I must not be able to reply."},
        )
        regular_admin_queue = self.owner.get("/api/v1/support/admin/tickets")

        self.assertEqual(other_detail.status_code, 404)
        self.assertEqual(other_reply.status_code, 404)
        self.assertEqual(regular_admin_queue.status_code, 403)

    def test_admin_can_triage_reply_and_update_status_with_unread_tracking(self) -> None:
        ticket_id = int(self._create_ticket()["id"])

        queue = self.admin.get("/api/v1/support/admin/tickets?status=open")
        self.assertEqual(queue.status_code, 200)
        self.assertEqual(queue.json()["total"], 1)
        self.assertEqual(queue.json()["tickets"][0]["requester_email"], "owner-support@example.com")
        self.assertTrue(queue.json()["tickets"][0]["unread_by_admin"])

        detail = self.admin.get(f"/api/v1/support/admin/tickets/{ticket_id}")
        self.assertEqual(detail.status_code, 200)
        self.assertFalse(detail.json()["ticket"]["unread_by_admin"])

        reply = self.admin.post(
            f"/api/v1/support/admin/tickets/{ticket_id}/messages",
            headers=self._csrf_headers(self.admin),
            json={"message": "We are checking the public market data source."},
        )
        self.assertEqual(reply.status_code, 200)
        self.assertEqual(reply.json()["ticket"]["status"], "in_progress")
        self.assertTrue(reply.json()["ticket"]["unread_by_user"])
        self.assertEqual(reply.json()["ticket"]["messages"][-1]["author_role"], "admin")

        owner_detail = self.owner.get(f"/api/v1/support/tickets/{ticket_id}")
        self.assertEqual(owner_detail.status_code, 200)
        self.assertFalse(owner_detail.json()["ticket"]["unread_by_user"])

        closed = self.admin.patch(
            f"/api/v1/support/admin/tickets/{ticket_id}/status",
            headers=self._csrf_headers(self.admin),
            json={"status": "closed"},
        )
        self.assertEqual(closed.status_code, 200)
        self.assertEqual(closed.json()["ticket"]["status"], "closed")
        self.assertTrue(closed.json()["ticket"]["unread_by_user"])

        reopened = self.admin.patch(
            f"/api/v1/support/admin/tickets/{ticket_id}/status",
            headers=self._csrf_headers(self.admin),
            json={"status": "in_progress"},
        )
        self.assertEqual(reopened.status_code, 200)
        self.assertEqual(reopened.json()["ticket"]["status"], "in_progress")
        self.assertIsNone(reopened.json()["ticket"]["closed_at"])

    def test_validation_rate_limit_and_audit_redaction_boundaries(self) -> None:
        invalid = self.owner.post(
            "/api/v1/support/tickets",
            headers=self._csrf_headers(self.owner),
            json={"category": "trading_tip", "subject": "No", "message": "x"},
        )
        self.assertEqual(invalid.status_code, 422)

        whitespace_only = self.owner.post(
            "/api/v1/support/tickets",
            headers=self._csrf_headers(self.owner),
            json={"category": "bug", "subject": "    ", "message": "   "},
        )
        self.assertEqual(whitespace_only.status_code, 422)

        reset_platform_rate_limits()
        with patch.dict(
            os.environ,
            {
                "PLATFORM_RATE_LIMIT_ENABLED": "true",
                "PLATFORM_RATE_LIMIT_SUPPORT_TICKET_CREATE_MAX": "1",
            },
            clear=False,
        ):
            first = self.owner.post(
                "/api/v1/support/tickets",
                headers=self._csrf_headers(self.owner),
                json={"category": "bug", "subject": "First valid support ticket", "message": "First message."},
            )
            second = self.owner.post(
                "/api/v1/support/tickets",
                headers=self._csrf_headers(self.owner),
                json={"category": "bug", "subject": "Second valid support ticket", "message": "Second message."},
            )
        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 429)
        self.assertEqual(second.json()["error"], "rate_limited")

        audit_text = str(PlatformAuditLogger().list_events(user_id=self.owner_id, limit=50))
        self.assertIn("support_ticket_created", audit_text)
        self.assertNotIn("First message.", audit_text)
        self.assertNotIn("The quote timestamp appears older than expected.", audit_text)


if __name__ == "__main__":
    unittest.main()
