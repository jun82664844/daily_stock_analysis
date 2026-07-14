# -*- coding: utf-8 -*-
import unittest

from tests import test_platform_support_api_v120 as v120


class PlatformSupportNotificationsApiV122TestCase(unittest.TestCase):
    setUp = v120.PlatformSupportApiV120TestCase.setUp
    tearDown = v120.PlatformSupportApiV120TestCase.tearDown
    _register = v120.PlatformSupportApiV120TestCase._register
    _csrf_headers = staticmethod(v120.PlatformSupportApiV120TestCase._csrf_headers)
    _create_ticket = v120.PlatformSupportApiV120TestCase._create_ticket

    def test_user_summary_is_owner_scoped_and_tracks_unread_replies(self) -> None:
        initial = self.owner.get("/api/v1/support/summary")
        self.assertEqual(initial.status_code, 200)
        self.assertEqual(initial.json(), {"unread_count": 0, "active_count": 0})

        ticket = self._create_ticket()
        ticket_id = int(ticket["id"])
        other_summary = self.other.get("/api/v1/support/summary")
        self.assertEqual(other_summary.json(), {"unread_count": 0, "active_count": 0})

        reply = self.admin.post(
            f"/api/v1/support/admin/tickets/{ticket_id}/messages",
            headers=self._csrf_headers(self.admin),
            json={"message": "We are checking the refresh path."},
        )
        self.assertEqual(reply.status_code, 200)

        unread = self.owner.get("/api/v1/support/summary")
        self.assertEqual(unread.json(), {"unread_count": 1, "active_count": 1})
        self.assertNotIn("subject", unread.text)
        self.assertNotIn("checking the refresh path", unread.text)

        detail = self.owner.get(f"/api/v1/support/tickets/{ticket_id}")
        self.assertEqual(detail.status_code, 200)
        cleared = self.owner.get("/api/v1/support/summary")
        self.assertEqual(cleared.json(), {"unread_count": 0, "active_count": 1})

    def test_admin_summary_requires_admin_and_tracks_pending_queue(self) -> None:
        first = self._create_ticket()
        second = self._create_ticket(self.other)

        forbidden = self.owner.get("/api/v1/support/admin/summary")
        self.assertEqual(forbidden.status_code, 403)

        summary = self.admin.get("/api/v1/support/admin/summary")
        self.assertEqual(summary.status_code, 200)
        self.assertEqual(summary.json()["unread_count"], 2)
        self.assertEqual(summary.json()["pending_count"], 2)
        self.assertIsNotNone(summary.json()["oldest_pending_at"])
        self.assertEqual(set(summary.json()), {"unread_count", "pending_count", "oldest_pending_at"})

        opened = self.admin.get(f"/api/v1/support/admin/tickets/{int(first['id'])}")
        self.assertEqual(opened.status_code, 200)
        closed = self.admin.patch(
            f"/api/v1/support/admin/tickets/{int(second['id'])}/status",
            headers=self._csrf_headers(self.admin),
            json={"status": "closed"},
        )
        self.assertEqual(closed.status_code, 200)

        updated = self.admin.get("/api/v1/support/admin/summary")
        self.assertEqual(updated.json()["unread_count"], 0)
        self.assertEqual(updated.json()["pending_count"], 1)


if __name__ == "__main__":
    unittest.main()
