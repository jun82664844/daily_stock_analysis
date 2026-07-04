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
from scripts.verify_platform_local_history_state_v28 import evaluate_history_state_v28_summary


def _history_result(stock_code: str, stock_name: str) -> SimpleNamespace:
    return SimpleNamespace(
        code=stock_code,
        name=stock_name,
        sentiment_score=62,
        operation_advice="informational watch",
        trend_prediction="range",
        analysis_summary=f"{stock_code} local V28 history state report",
        news_summary="",
        technical_analysis="local technical snapshot",
        fundamental_analysis="",
        risk_warning="not investment advice",
        data_sources="unit-test",
        raw_response={"authorization": "Bearer sk-v28-state-secret"},
        success=True,
    )


class PlatformLocalHistoryStateV28TestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.db_path = os.path.join(self.temp_dir.name, "history-state-v28.sqlite")
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

    def test_updates_owner_scoped_history_state_and_filters_without_ai(self) -> None:
        owner_id = self._register("history-state-v28-owner@example.com")
        other_user = PlatformAccountService().create_user("history-state-v28-other@example.com", "password123")

        aapl_id = self._save_history(
            user_id=owner_id,
            stock_code="AAPL",
            stock_name="Apple",
            query_id="v28-aapl",
            created_at=datetime(2026, 7, 1, 9, 30, 0),
            report_type="simple",
        )
        hk_id = self._save_history(
            user_id=owner_id,
            stock_code="HK00700",
            stock_name="Tencent",
            query_id="v28-hk",
            created_at=datetime(2026, 7, 2, 9, 30, 0),
            report_type="full",
        )
        other_record_id = self._save_history(
            user_id=int(other_user.id),
            stock_code="MSFT",
            stock_name="Microsoft",
            query_id="v28-other-msft",
            created_at=datetime(2026, 7, 3, 9, 30, 0),
            report_type="detailed",
        )

        update_response = self.client.patch(
            f"/api/v1/history/{aapl_id}/state",
            json={
                "favorite": True,
                "important": True,
                "read": True,
                "note": "Watch after earnings, local note only.",
                "ai_used": False,
            },
        )
        self.assertEqual(update_response.status_code, 200)
        update_body = update_response.json()
        self.assertEqual(update_body["record_id"], aapl_id)
        self.assertTrue(update_body["favorite"])
        self.assertTrue(update_body["important"])
        self.assertTrue(update_body["read"])
        self.assertFalse(update_body["archived"])
        self.assertFalse(update_body["ai_used"])
        self.assertEqual(update_body["note"], "Watch after earnings, local note only.")

        favorite_list = self.client.get("/api/v1/history", params={"state": "favorite"})
        self.assertEqual(favorite_list.status_code, 200)
        favorite_body = favorite_list.json()
        self.assertEqual([item["id"] for item in favorite_body["items"]], [aapl_id])
        favorite_item = favorite_body["items"][0]
        self.assertTrue(favorite_item["favorite"])
        self.assertTrue(favorite_item["important"])
        self.assertTrue(favorite_item["read"])
        self.assertFalse(favorite_item["archived"])
        self.assertEqual(favorite_item["note"], "Watch after earnings, local note only.")

        unread_list = self.client.get("/api/v1/history", params={"state": "unread"})
        self.assertEqual(unread_list.status_code, 200)
        self.assertNotIn(aapl_id, [item["id"] for item in unread_list.json()["items"]])
        self.assertIn(hk_id, [item["id"] for item in unread_list.json()["items"]])

        other_update = self.client.patch(
            f"/api/v1/history/{other_record_id}/state",
            json={"favorite": True, "ai_used": False},
        )
        self.assertEqual(other_update.status_code, 404)

        ai_attempt = self.client.patch(
            f"/api/v1/history/{aapl_id}/state",
            json={"favorite": False, "ai_used": True},
        )
        self.assertEqual(ai_attempt.status_code, 400)

        archive_response = self.client.patch(
            "/api/v1/history/state",
            json={"record_ids": [aapl_id, hk_id, other_record_id], "archived": True, "ai_used": False},
        )
        self.assertEqual(archive_response.status_code, 200)
        archive_body = archive_response.json()
        self.assertEqual(archive_body["updated"], 2)
        self.assertEqual(archive_body["record_ids"], [aapl_id, hk_id])
        self.assertFalse(archive_body["ai_used"])

        archived_list = self.client.get("/api/v1/history", params={"state": "archived"})
        self.assertEqual(archived_list.status_code, 200)
        self.assertEqual([item["id"] for item in archived_list.json()["items"]], [hk_id, aapl_id])

        active_list = self.client.get("/api/v1/history", params={"state": "active"})
        self.assertEqual(active_list.status_code, 200)
        active_ids = [item["id"] for item in active_list.json()["items"]]
        self.assertNotIn(aapl_id, active_ids)
        self.assertNotIn(hk_id, active_ids)
        self.assertNotIn(other_record_id, active_ids)


class PlatformLocalHistoryStateV28VerifierTestCase(unittest.TestCase):
    def test_evaluate_history_state_v28_summary_accepts_complete_shape(self) -> None:
        summary = {
            "backend": {
                "state_table": True,
                "state_filter": True,
                "state_endpoints": True,
                "owner_scoped": True,
                "no_ai": True,
                "backend_test": True,
            },
            "frontend": {
                "state_api": True,
                "state_filter": True,
                "batch_archive": True,
                "detail_controls": True,
                "stable_select_all": True,
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

        self.assertEqual(evaluate_history_state_v28_summary(summary), [])

    def test_evaluate_history_state_v28_summary_rejects_missing_boundaries(self) -> None:
        summary = {
            "backend": {
                "state_table": True,
                "state_filter": False,
                "state_endpoints": False,
                "owner_scoped": False,
                "no_ai": False,
                "backend_test": True,
            },
            "frontend": {
                "state_api": False,
                "state_filter": True,
                "batch_archive": False,
                "detail_controls": True,
                "stable_select_all": False,
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

        problems = evaluate_history_state_v28_summary(summary)
        self.assertIn("backend:state_filter_missing", problems)
        self.assertIn("backend:state_endpoints_missing", problems)
        self.assertIn("backend:owner_scope_missing", problems)
        self.assertIn("backend:no_ai_missing", problems)
        self.assertIn("frontend:state_api_missing", problems)
        self.assertIn("frontend:batch_archive_missing", problems)
        self.assertIn("frontend:stable_select_all_missing", problems)
        self.assertIn("docs:no_real_api_key_missing", problems)
        self.assertIn("docs:no_delete_data_missing", problems)


if __name__ == "__main__":
    unittest.main()
