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
from scripts.verify_platform_local_history_center_v25 import (
    evaluate_history_center_v25_summary,
    run_local_history_center_v25_checks,
)


def _history_result(stock_code: str, stock_name: str) -> SimpleNamespace:
    return SimpleNamespace(
        code=stock_code,
        name=stock_name,
        sentiment_score=55,
        operation_advice="hold",
        trend_prediction="sideways",
        analysis_summary=f"{stock_code} informational history",
        news_summary="",
        technical_analysis="",
        fundamental_analysis="",
        risk_warning="",
        data_sources="unit-test",
        raw_response=None,
        success=True,
    )


class PlatformLocalHistoryCenterV25TestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.db_path = os.path.join(self.temp_dir.name, "history-center-v25.sqlite")
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

    def test_history_center_filters_sorting_and_persistent_refresh_marker_are_user_scoped(self) -> None:
        owner_id = self._register("history-v25-owner@example.com")
        other_user = PlatformAccountService().create_user("history-v25-other@example.com", "password123")

        aapl_id = self._save_history(
            user_id=owner_id,
            stock_code="AAPL",
            stock_name="Apple",
            query_id="v25-aapl",
            created_at=datetime(2026, 7, 1, 9, 30, 0),
            report_type="simple",
        )
        hk_id = self._save_history(
            user_id=owner_id,
            stock_code="HK00700",
            stock_name="Tencent",
            query_id="v25-hk",
            created_at=datetime(2026, 7, 2, 9, 30, 0),
            report_type="full",
        )
        btc_id = self._save_history(
            user_id=owner_id,
            stock_code="BTC-USD",
            stock_name="Bitcoin",
            query_id="v25-btc",
            created_at=datetime(2026, 7, 3, 9, 30, 0),
            report_type="brief",
        )
        cn_id = self._save_history(
            user_id=owner_id,
            stock_code="600519",
            stock_name="Kweichow Moutai",
            query_id="v25-cn",
            created_at=datetime(2026, 7, 4, 9, 30, 0),
            report_type="detailed",
        )
        other_record_id = self._save_history(
            user_id=int(other_user.id),
            stock_code="MSFT",
            stock_name="Microsoft",
            query_id="v25-other-msft",
            created_at=datetime(2026, 7, 5, 9, 30, 0),
            report_type="detailed",
        )

        us_response = self.client.get("/api/v1/history?market=us&sort=oldest&limit=10")
        self.assertEqual(us_response.status_code, 200)
        us_body = us_response.json()
        self.assertEqual(us_body["total"], 1)
        self.assertEqual([item["id"] for item in us_body["items"]], [aapl_id])
        self.assertFalse(us_body["items"][0]["current_quote_refreshed"])
        self.assertNotIn(other_record_id, [item["id"] for item in us_body["items"]])

        hk_response = self.client.get("/api/v1/history?market=hk&limit=10")
        self.assertEqual(hk_response.status_code, 200)
        self.assertEqual([item["id"] for item in hk_response.json()["items"]], [hk_id])

        crypto_response = self.client.get("/api/v1/history?market=crypto&limit=10")
        self.assertEqual(crypto_response.status_code, 200)
        self.assertEqual([item["id"] for item in crypto_response.json()["items"]], [btc_id])

        cn_response = self.client.get("/api/v1/history?market=cn&limit=10")
        self.assertEqual(cn_response.status_code, 200)
        self.assertEqual([item["id"] for item in cn_response.json()["items"]], [cn_id])

        marker_response = self.client.post(
            f"/api/v1/history/{aapl_id}/refresh-marker",
            json={
                "stock_code": "AAPL",
                "route_lane": "us_market_data",
                "quote_source": "yahoo_chart",
                "freshness": "fresh",
                "ai_used": False,
            },
        )
        self.assertEqual(marker_response.status_code, 200)
        marker_body = marker_response.json()
        self.assertEqual(marker_body["record_id"], aapl_id)
        self.assertEqual(marker_body["stock_code"], "AAPL")
        self.assertTrue(marker_body["current_quote_refreshed"])
        self.assertFalse(marker_body["ai_used"])
        self.assertEqual(marker_body["route_lane"], "us_market_data")

        refreshed = self.client.get("/api/v1/history?refresh_status=refreshed&limit=10")
        self.assertEqual(refreshed.status_code, 200)
        refreshed_items = refreshed.json()["items"]
        self.assertEqual([item["id"] for item in refreshed_items], [aapl_id])
        self.assertTrue(refreshed_items[0]["current_quote_refreshed"])
        self.assertIsNotNone(refreshed_items[0]["current_quote_refreshed_at"])

        not_refreshed = self.client.get("/api/v1/history?refresh_status=not_refreshed&sort=oldest&limit=10")
        self.assertEqual(not_refreshed.status_code, 200)
        self.assertEqual(
            [item["id"] for item in not_refreshed.json()["items"]],
            [hk_id, btc_id, cn_id],
        )

        forbidden_other_marker = self.client.post(
            f"/api/v1/history/{other_record_id}/refresh-marker",
            json={"stock_code": "MSFT", "ai_used": False},
        )
        self.assertEqual(forbidden_other_marker.status_code, 404)

        rejects_ai_marker = self.client.post(
            f"/api/v1/history/{aapl_id}/refresh-marker",
            json={"stock_code": "AAPL", "ai_used": True},
        )
        self.assertEqual(rejects_ai_marker.status_code, 400)


class PlatformLocalHistoryCenterV25VerifierTestCase(unittest.TestCase):
    def test_evaluate_history_center_v25_summary_accepts_complete_shape(self) -> None:
        summary = {
            "backend": {
                "refresh_marker_table": True,
                "market_filter": True,
                "refresh_status_filter": True,
                "stable_sort": True,
                "marker_endpoint": True,
                "user_scoped_marker": True,
                "no_ai_marker_rejects_ai": True,
                "backend_test": True,
            },
            "frontend": {
                "history_api_filters": True,
                "marker_api": True,
                "store_history_filters": True,
                "home_filter_mapping": True,
                "home_marker_write": True,
                "persistent_badge": True,
                "frontend_test": True,
            },
        }

        self.assertEqual(evaluate_history_center_v25_summary(summary), [])

    def test_evaluate_history_center_v25_summary_rejects_missing_backend_and_frontend_wiring(self) -> None:
        summary = {
            "backend": {
                "refresh_marker_table": False,
                "market_filter": True,
                "refresh_status_filter": False,
                "stable_sort": True,
                "marker_endpoint": False,
                "user_scoped_marker": False,
                "no_ai_marker_rejects_ai": False,
                "backend_test": False,
            },
            "frontend": {
                "history_api_filters": False,
                "marker_api": False,
                "store_history_filters": False,
                "home_filter_mapping": False,
                "home_marker_write": False,
                "persistent_badge": False,
                "frontend_test": False,
            },
        }

        problems = evaluate_history_center_v25_summary(summary)

        self.assertIn("backend:refresh_marker_table_missing", problems)
        self.assertIn("backend:refresh_status_filter_missing", problems)
        self.assertIn("backend:marker_endpoint_missing", problems)
        self.assertIn("backend:user_scope_missing", problems)
        self.assertIn("backend:no_ai_guard_missing", problems)
        self.assertIn("frontend:history_api_filters_missing", problems)
        self.assertIn("frontend:marker_api_missing", problems)
        self.assertIn("frontend:store_filters_missing", problems)
        self.assertIn("frontend:filter_mapping_missing", problems)
        self.assertIn("frontend:marker_write_missing", problems)
        self.assertIn("frontend:persistent_badge_missing", problems)

    def test_required_files_check_reports_missing_v25_plan(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
            results = run_local_history_center_v25_checks(
                project_root=Path(temp_dir),
                run_subprocess=False,
            )

        by_id = {result.check_id: result for result in results}
        self.assertEqual(by_id["v25_required_files_present"].status, "failed")
        self.assertIn(
            "docs/superpowers/plans/2026-07-03-dsa-local-v25-history-center-persistence.md",
            by_id["v25_required_files_present"].metadata["missing_files"],
        )


if __name__ == "__main__":
    unittest.main()
