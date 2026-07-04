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
from scripts.verify_platform_local_history_export_v27 import evaluate_history_export_v27_summary


def _history_result(stock_code: str, stock_name: str) -> SimpleNamespace:
    return SimpleNamespace(
        code=stock_code,
        name=stock_name,
        sentiment_score=55,
        operation_advice="informational hold",
        trend_prediction="sideways",
        analysis_summary=f"{stock_code} informational history",
        news_summary="",
        technical_analysis="stable range",
        fundamental_analysis="",
        risk_warning="not investment advice",
        data_sources="unit-test",
        raw_response={"authorization": "Bearer sk-v27-export-secret"},
        success=True,
    )


class PlatformLocalHistoryExportV27TestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.db_path = os.path.join(self.temp_dir.name, "history-export-v27.sqlite")
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

    def test_exports_selected_history_as_owner_scoped_no_ai_bundle(self) -> None:
        owner_id = self._register("history-export-v27-owner@example.com")
        other_user = PlatformAccountService().create_user("history-export-v27-other@example.com", "password123")

        aapl_id = self._save_history(
            user_id=owner_id,
            stock_code="AAPL",
            stock_name="Apple",
            query_id="v27-aapl",
            created_at=datetime(2026, 7, 1, 9, 30, 0),
            report_type="simple",
        )
        hk_id = self._save_history(
            user_id=owner_id,
            stock_code="HK00700",
            stock_name="Tencent",
            query_id="v27-hk",
            created_at=datetime(2026, 7, 2, 9, 30, 0),
            report_type="full",
        )
        other_record_id = self._save_history(
            user_id=int(other_user.id),
            stock_code="MSFT",
            stock_name="Microsoft",
            query_id="v27-other-msft",
            created_at=datetime(2026, 7, 3, 9, 30, 0),
            report_type="detailed",
        )

        markdown_response = self.client.post(
            "/api/v1/history/export",
            json={"record_ids": [aapl_id, hk_id, aapl_id], "format": "markdown"},
        )
        self.assertEqual(markdown_response.status_code, 200)
        markdown_body = markdown_response.json()
        self.assertEqual(markdown_body["format"], "markdown")
        self.assertEqual(markdown_body["record_count"], 2)
        self.assertEqual(markdown_body["record_ids"], [aapl_id, hk_id])
        self.assertFalse(markdown_body["ai_used"])
        self.assertTrue(markdown_body["filename"].endswith(".md"))
        self.assertIn("AAPL", markdown_body["content"])
        self.assertIn("HK00700", markdown_body["content"])
        self.assertIn("not investment advice", markdown_body["content"])
        self.assertNotIn("sk-v27-export-secret", markdown_body["content"])

        json_response = self.client.post(
            "/api/v1/history/export",
            json={"record_ids": [aapl_id], "format": "json"},
        )
        self.assertEqual(json_response.status_code, 200)
        json_body = json_response.json()
        self.assertEqual(json_body["format"], "json")
        self.assertTrue(json_body["filename"].endswith(".json"))
        self.assertFalse(json_body["ai_used"])
        self.assertIn('"stock_code": "AAPL"', json_body["content"])
        self.assertNotIn("sk-v27-export-secret", json_body["content"])

        forbidden_other_export = self.client.post(
            "/api/v1/history/export",
            json={"record_ids": [other_record_id], "format": "markdown"},
        )
        self.assertEqual(forbidden_other_export.status_code, 404)

        empty_export = self.client.post(
            "/api/v1/history/export",
            json={"record_ids": [], "format": "markdown"},
        )
        self.assertEqual(empty_export.status_code, 400)


class PlatformLocalHistoryExportV27VerifierTestCase(unittest.TestCase):
    def test_evaluate_history_export_v27_summary_accepts_complete_shape(self) -> None:
        summary = {
            "backend": {
                "export_endpoint": True,
                "export_schemas": True,
                "owner_scoped": True,
                "no_ai": True,
                "secret_redaction": True,
                "backend_test": True,
            },
            "frontend": {
                "export_api": True,
                "download_helper": True,
                "selectable_history_center": True,
                "export_button": True,
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

        self.assertEqual(evaluate_history_export_v27_summary(summary), [])

    def test_evaluate_history_export_v27_summary_rejects_missing_safety_edges(self) -> None:
        summary = {
            "backend": {
                "export_endpoint": True,
                "export_schemas": True,
                "owner_scoped": False,
                "no_ai": False,
                "secret_redaction": False,
                "backend_test": True,
            },
            "frontend": {
                "export_api": True,
                "download_helper": True,
                "selectable_history_center": False,
                "export_button": True,
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

        problems = evaluate_history_export_v27_summary(summary)
        self.assertIn("backend:owner_scope_missing", problems)
        self.assertIn("backend:no_ai_missing", problems)
        self.assertIn("backend:secret_redaction_missing", problems)
        self.assertIn("frontend:selectable_history_center_missing", problems)
        self.assertIn("docs:no_real_api_key_missing", problems)
        self.assertIn("docs:no_delete_data_missing", problems)


if __name__ == "__main__":
    unittest.main()
