# -*- coding: utf-8 -*-
import os
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from fastapi.testclient import TestClient

from api.app import create_app
from src.config import Config
from src.platform_accounts import PlatformAccountService
from src.storage import AnalysisHistory, DatabaseManager
from scripts.verify_platform_local_history_ops_v29 import evaluate_history_ops_v29_summary


def _history_result(stock_code: str, stock_name: str) -> SimpleNamespace:
    return SimpleNamespace(
        code=stock_code,
        name=stock_name,
        sentiment_score=58,
        operation_advice="informational watch",
        trend_prediction="range",
        analysis_summary=f"{stock_code} local V29 history operations report",
        news_summary="",
        technical_analysis="local technical snapshot",
        fundamental_analysis="",
        risk_warning="not investment advice",
        data_sources="unit-test",
        raw_response={"authorization": "Bearer sk-v29-history-ops-secret"},
        success=True,
    )


class PlatformLocalHistoryOpsV29TestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.db_path = os.path.join(self.temp_dir.name, "history-ops-v29.sqlite")
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

    def _register(self, email: str) -> int:
        response = self.client.post(
            "/api/v1/platform/register",
            json={"email": email, "password": "password123"},
        )
        self.assertEqual(response.status_code, 200)
        return int(response.json()["user"]["id"])

    def _save_history(
        self,
        *,
        user_id: int,
        stock_code: str,
        stock_name: str,
        query_id: str,
        created_at: datetime,
        report_type: str = "detailed",
    ) -> int:
        db = DatabaseManager.get_instance()
        record_id = db.save_analysis_history(
            result=_history_result(stock_code, stock_name),
            query_id=query_id,
            report_type=report_type,
            news_content=None,
            platform_user_id=user_id,
        )
        self.assertGreater(record_id, 0)
        with db.session_scope() as session:
            row = session.get(AnalysisHistory, record_id)
            self.assertIsNotNone(row)
            row.created_at = created_at
        return int(record_id)

    def test_filters_history_by_owner_scoped_note_search_and_batch_flags_without_ai(self) -> None:
        owner_id = self._register("history-ops-v29-owner@example.com")
        other_user = PlatformAccountService().create_user("history-ops-v29-other@example.com", "password123")

        aapl_id = self._save_history(
            user_id=owner_id,
            stock_code="AAPL",
            stock_name="Apple",
            query_id="v29-aapl",
            created_at=datetime(2026, 7, 4, 9, 30, 0),
            report_type="simple",
        )
        hk_id = self._save_history(
            user_id=owner_id,
            stock_code="HK00700",
            stock_name="Tencent",
            query_id="v29-hk",
            created_at=datetime(2026, 7, 3, 9, 30, 0),
            report_type="full",
        )
        other_id = self._save_history(
            user_id=int(other_user.id),
            stock_code="MSFT",
            stock_name="Microsoft",
            query_id="v29-other-msft",
            created_at=datetime(2026, 7, 4, 10, 0, 0),
            report_type="detailed",
        )

        for record_id, note in (
            (aapl_id, "Earnings gap watch monitor; review after call."),
            (hk_id, "Dividend watch; archived lane."),
            (other_id, "Earnings gap monitor for another user."),
        ):
            response = self.client.patch(
                f"/api/v1/history/{record_id}/state",
                json={"note": note, "ai_used": False},
            )
            expected_status = 200 if record_id != other_id else 404
            self.assertEqual(response.status_code, expected_status)

        archive_response = self.client.patch(
            "/api/v1/history/state",
            json={"record_ids": [hk_id], "archived": True, "ai_used": False},
        )
        self.assertEqual(archive_response.status_code, 200)

        batch_response = self.client.patch(
            "/api/v1/history/state",
            json={"record_ids": [aapl_id, hk_id, other_id], "important": True, "read": True, "ai_used": False},
        )
        self.assertEqual(batch_response.status_code, 200)
        self.assertEqual(batch_response.json()["record_ids"], [aapl_id, hk_id])
        self.assertFalse(batch_response.json()["ai_used"])

        note_search_response = self.client.get(
            "/api/v1/history",
            params={"note_search": "earnings gap"},
        )
        self.assertEqual(note_search_response.status_code, 200)
        note_search_body = note_search_response.json()
        self.assertEqual([item["id"] for item in note_search_body["items"]], [aapl_id])
        self.assertTrue(note_search_body["items"][0]["important"])
        self.assertTrue(note_search_body["items"][0]["read"])
        self.assertIn("Earnings gap", note_search_body["items"][0]["note"])

        active_note_response = self.client.get(
            "/api/v1/history",
            params={"state": "active", "note_search": "watch"},
        )
        self.assertEqual(active_note_response.status_code, 200)
        self.assertEqual([item["id"] for item in active_note_response.json()["items"]], [aapl_id])

        archived_note_response = self.client.get(
            "/api/v1/history",
            params={"state": "archived", "note_search": "dividend"},
        )
        self.assertEqual(archived_note_response.status_code, 200)
        self.assertEqual([item["id"] for item in archived_note_response.json()["items"]], [hk_id])


class PlatformLocalHistoryOpsV29VerifierTestCase(unittest.TestCase):
    def test_evaluate_history_ops_v29_summary_accepts_complete_shape(self) -> None:
        summary = {
            "backend": {
                "note_search": True,
                "owner_scoped": True,
                "batch_flags": True,
                "no_ai": True,
                "backend_test": True,
            },
            "frontend": {
                "active_default": True,
                "note_search_input": True,
                "date_groups": True,
                "batch_important_read": True,
                "frontend_test": True,
            },
            "docs": {
                "local_only": True,
                "no_real_payment": True,
                "no_real_api_key": True,
                "no_delete_data": True,
                "not_investment_advice": True,
            },
        }

        self.assertEqual(evaluate_history_ops_v29_summary(summary), [])

    def test_evaluate_history_ops_v29_summary_rejects_missing_boundaries(self) -> None:
        summary = {
            "backend": {
                "note_search": False,
                "owner_scoped": False,
                "batch_flags": True,
                "no_ai": False,
                "backend_test": True,
            },
            "frontend": {
                "active_default": False,
                "note_search_input": False,
                "date_groups": True,
                "batch_important_read": False,
                "frontend_test": True,
            },
            "docs": {
                "local_only": True,
                "no_real_payment": True,
                "no_real_api_key": False,
                "no_delete_data": False,
                "not_investment_advice": True,
            },
        }

        problems = evaluate_history_ops_v29_summary(summary)
        self.assertIn("backend:note_search_missing", problems)
        self.assertIn("backend:owner_scope_missing", problems)
        self.assertIn("backend:no_ai_missing", problems)
        self.assertIn("frontend:active_default_missing", problems)
        self.assertIn("frontend:note_search_input_missing", problems)
        self.assertIn("frontend:batch_important_read_missing", problems)
        self.assertIn("docs:no_real_api_key_missing", problems)
        self.assertIn("docs:no_delete_data_missing", problems)


if __name__ == "__main__":
    unittest.main()
