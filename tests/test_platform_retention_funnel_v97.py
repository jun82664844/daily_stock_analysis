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
from src.storage import DatabaseManager


EVENTS = (
    "free_query_completed",
    "registration_completed",
    "api_trial_submitted",
    "trial_report_opened",
    "premium_options_viewed",
)


class PlatformRetentionFunnelV97TestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.db_path = os.path.join(self.temp_dir.name, "retention-funnel.sqlite")
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
                "PLATFORM_RATE_LIMIT_ENABLED": "false",
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

    def _track(self, event: str, session_id: str, source: str = "home"):
        return self.client.post(
            "/api/v1/platform/retention/events",
            json={"event": event, "sessionId": session_id, "source": source},
        )

    def test_public_event_is_hashed_deduplicated_and_rejects_extra_metadata(self) -> None:
        raw_session = "6e3ca62c-7548-4f8d-8f98-ef7eaefcab55"

        first = self._track("free_query_completed", raw_session)
        duplicate = self._track("free_query_completed", raw_session)
        invalid = self.client.post(
            "/api/v1/platform/retention/events",
            json={
                "event": "free_query_completed",
                "sessionId": raw_session,
                "source": "home",
                "email": "must-not-be-accepted@example.com",
            },
        )

        self.assertEqual(first.status_code, 200)
        self.assertEqual(first.json(), {
            "event": "free_query_completed",
            "accepted": True,
            "duplicate": False,
            "ai_used": False,
        })
        self.assertEqual(duplicate.status_code, 200)
        self.assertTrue(duplicate.json()["duplicate"])
        self.assertEqual(invalid.status_code, 422)

        events = [event for event in PlatformAuditLogger().list_events(limit=20) if event["action"].startswith("retention_")]
        self.assertEqual(len(events), 1)
        self.assertNotIn(raw_session, str(events))
        self.assertEqual(len(events[0]["metadata"]["session_hash"]), 24)
        self.assertEqual(events[0]["metadata"]["source"], "home")
        self.assertIsNone(events[0]["user_id"])

    def test_invalid_event_and_source_are_rejected(self) -> None:
        invalid_event = self._track("payment_completed", "session-invalid-event")
        invalid_source = self._track("free_query_completed", "session-invalid-source", source="arbitrary-page")

        self.assertEqual(invalid_event.status_code, 422)
        self.assertEqual(invalid_source.status_code, 422)

    def test_authenticated_event_is_owned_by_current_user(self) -> None:
        register = self.client.post(
            "/api/v1/platform/register",
            json={"email": "funnel-user@example.com", "password": "password123"},
        )
        user_id = int(register.json()["user"]["id"])

        response = self._track("registration_completed", "session-authenticated", source="registration")

        self.assertEqual(response.status_code, 200)
        event = next(
            event for event in PlatformAuditLogger().list_events(limit=20)
            if event["action"] == "retention_registration_completed"
        )
        self.assertEqual(event["user_id"], user_id)

    def test_admin_summary_builds_monotonic_unique_session_funnel(self) -> None:
        sessions = {
            "session-all-1": EVENTS,
            "session-through-trial": EVENTS[:3],
            "session-query-only": EVENTS[:1],
        }
        sources = {
            "free_query_completed": "home",
            "registration_completed": "registration",
            "api_trial_submitted": "trial",
            "trial_report_opened": "report",
            "premium_options_viewed": "account",
        }
        for session_id, events in sessions.items():
            for event in events:
                response = self._track(event, session_id, source=sources[event])
                self.assertEqual(response.status_code, 200)

        PlatformAccountService().create_user("regular@example.com", "password123")
        regular_login = self.client.post(
            "/api/v1/platform/login",
            json={"email": "regular@example.com", "password": "password123"},
        )
        self.assertEqual(regular_login.status_code, 200)
        forbidden = self.client.get("/api/v1/platform/admin/retention-funnel")
        self.assertEqual(forbidden.status_code, 403)

        PlatformAccountService().create_user("funnel-admin@example.com", "password123", role="admin")
        admin_login = self.client.post(
            "/api/v1/platform/login",
            json={"email": "funnel-admin@example.com", "password": "password123"},
        )
        self.assertEqual(admin_login.status_code, 200)
        response = self.client.get("/api/v1/platform/admin/retention-funnel?window_days=30")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["mode"], "local_only")
        self.assertEqual(body["window_days"], 30)
        self.assertFalse(body["ai_used"])
        self.assertEqual(body["total_sessions"], 3)
        self.assertEqual([stage["event"] for stage in body["stages"]], list(EVENTS))
        self.assertEqual([stage["unique_sessions"] for stage in body["stages"]], [3, 2, 2, 1, 1])
        self.assertEqual([stage["reached_from_start"] for stage in body["stages"]], [3, 2, 2, 1, 1])
        self.assertEqual(body["stages"][1]["conversion_from_previous_pct"], 66.7)
        self.assertEqual(body["stages"][2]["conversion_from_previous_pct"], 100.0)
        self.assertEqual(body["stages"][4]["conversion_from_start_pct"], 33.3)
        self.assertNotIn("session-all-1", str(body))

        usage = self.client.get("/api/v1/platform/admin/usage")
        self.assertEqual(usage.status_code, 200)
        retention_audit = [
            event for event in usage.json()["audit_events"]
            if event["action"].startswith("retention_")
        ]
        self.assertGreater(len(retention_audit), 0)
        self.assertNotIn("session_hash", str(retention_audit))


if __name__ == "__main__":
    unittest.main()
