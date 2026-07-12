# -*- coding: utf-8 -*-
from __future__ import annotations

import os
import tempfile
import unittest
from concurrent.futures import Future
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from fastapi.testclient import TestClient

from api.app import create_app
from src.config import Config
from src.platform_accounts import PlatformAccountService
from src.services.api_boost_pack_service import ApiBoostPackService
from src.services.analysis_service import AnalysisService
from src.services.task_queue import AnalysisTaskQueue
from src.storage import (
    DatabaseManager,
    PlatformQuotaGrant,
    PlatformQuotaReservation,
    utc_naive_now,
)


class AnalysisModelSelectionV112TestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.db_path = os.path.join(self.temp_dir.name, "analysis-v112.sqlite")
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
                "PLATFORM_MEMBER_MODEL_PICKER_ENABLED": "true",
            },
            clear=False,
        )
        self.env_patch.start()
        self.client = TestClient(create_app(static_dir=self.static_dir))
        response = self.client.post(
            "/api/v1/platform/register",
            json={"email": "analysis-v112@example.com", "password": "password123"},
        )
        self.user_id = int(response.json()["user"]["id"])
        PlatformAccountService().set_user_plan(self.user_id, "pro")
        now = utc_naive_now()
        with DatabaseManager.get_instance().session_scope() as session:
            session.add(
                PlatformQuotaGrant(
                    user_id=self.user_id,
                    source_type="membership",
                    source_reference="membership-v112-test",
                    flash_total=3,
                    flash_used=0,
                    pro_total=3,
                    pro_used=0,
                    starts_at=now - timedelta(minutes=1),
                    expires_at=now + timedelta(days=10),
                    status="active",
                    created_at=now,
                )
            )

    def tearDown(self) -> None:
        self.client.close()
        self.env_patch.stop()
        DatabaseManager.reset_instance()
        Config.reset_instance()
        self.temp_dir.cleanup()

    @staticmethod
    def _result():
        return {
            "stock_code": "AAPL",
            "stock_name": "Apple Inc.",
            "report": {
                "meta": {"stock_code": "AAPL", "report_language": "zh"},
                "summary": {"analysis_summary": "信息分析"},
                "strategy": {},
                "details": {},
            },
        }

    def test_successful_platform_fast_analysis_consumes_flash_grant(self) -> None:
        service = SimpleNamespace(last_error=None, analyze_stock=lambda **kwargs: self._result())
        with patch("src.services.analysis_service.AnalysisService", return_value=service), patch(
            "api.v1.endpoints.analysis._load_sync_fundamental_sources", return_value=(None, None)
        ):
            response = self.client.post(
                "/api/v1/analysis/analyze",
                json={"stock_code": "AAPL", "async_mode": False, "analysis_depth": "fast"},
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(ApiBoostPackService().balance(self.user_id)["flash"], 2)

    def test_failed_platform_deep_analysis_releases_pro_grant(self) -> None:
        service = SimpleNamespace(last_error="upstream failed", analyze_stock=lambda **kwargs: None)
        with patch("src.services.analysis_service.AnalysisService", return_value=service):
            response = self.client.post(
                "/api/v1/analysis/analyze",
                json={"stock_code": "AAPL", "async_mode": False, "analysis_depth": "deep"},
            )
        self.assertEqual(response.status_code, 500)
        self.assertEqual(ApiBoostPackService().balance(self.user_id)["pro"], 3)

    def test_async_worker_consumes_only_its_own_member_reservation(self) -> None:
        class CapturingExecutor:
            def __init__(self) -> None:
                self.calls = []

            def submit(self, fn, *args, **kwargs):
                self.calls.append((fn, args, kwargs))
                return Future()

        quota = ApiBoostPackService()
        reference = "analysis:async-success-v112"
        quota.reserve(self.user_id, "flash", 1, reference)
        queue = AnalysisTaskQueue(max_workers=1)
        executor = CapturingExecutor()
        queue._executor = executor

        accepted, duplicates = queue.submit_tasks_batch(
            ["AAPL"],
            platform_user_id=self.user_id,
            api_key_mode="platform",
            member_quota_references={"AAPL": reference},
        )
        self.assertEqual(duplicates, [])
        self.assertNotIn("member_quota_reference", accepted[0].to_dict())

        service = SimpleNamespace(last_error=None, analyze_stock=lambda **kwargs: self._result())
        with patch("src.services.analysis_service.AnalysisService", return_value=service):
            executor.calls[0][0](*executor.calls[0][1])

        with DatabaseManager.get_instance().get_session() as session:
            reservation = session.query(PlatformQuotaReservation).filter_by(
                reference_id=reference
            ).one()
            self.assertEqual(reservation.status, "consumed")
        self.assertEqual(quota.balance(self.user_id)["flash"], 2)

    def test_async_worker_releases_member_reservation_after_failure(self) -> None:
        class CapturingExecutor:
            def __init__(self) -> None:
                self.calls = []

            def submit(self, fn, *args, **kwargs):
                self.calls.append((fn, args, kwargs))
                return Future()

        quota = ApiBoostPackService()
        reference = "analysis:async-failure-v112"
        quota.reserve(self.user_id, "pro", 1, reference)
        queue = AnalysisTaskQueue(max_workers=1)
        executor = CapturingExecutor()
        queue._executor = executor
        queue.submit_tasks_batch(
            ["AAPL"],
            analysis_depth="deep",
            platform_user_id=self.user_id,
            api_key_mode="platform",
            member_quota_references={"AAPL": reference},
        )

        service = SimpleNamespace(last_error="upstream failed", analyze_stock=lambda **kwargs: None)
        with patch("src.services.analysis_service.AnalysisService", return_value=service):
            executor.calls[0][0](*executor.calls[0][1])

        with DatabaseManager.get_instance().get_session() as session:
            reservation = session.query(PlatformQuotaReservation).filter_by(
                reference_id=reference
            ).one()
            self.assertEqual(reservation.status, "released")
        self.assertEqual(quota.balance(self.user_id)["pro"], 3)

    def test_user_local_analysis_uses_connector_without_platform_fallback(self) -> None:
        connector_result = {
            "text": "Price and volume data remain mixed. Buy now at 100 with a target price of 120. Data freshness should be checked.",
            "diagnostics": {"done_reason": "stop"},
            "connector_id": 12,
            "model_name": "qwen3:8b",
        }
        with patch(
            "src.services.user_local_connector_service.UserLocalConnectorService.run_analysis",
            return_value=connector_result,
        ) as run_analysis, patch("src.core.pipeline.StockAnalysisPipeline") as platform_pipeline:
            result = AnalysisService().analyze_stock(
                stock_code="AAPL",
                report_language="en",
                platform_user_id=self.user_id,
                api_key_mode="user_local",
                user_local_connector_id=12,
                user_local_model_name="qwen3:8b",
            )

        self.assertIsNotNone(result)
        platform_pipeline.assert_not_called()
        run_analysis.assert_called_once()
        summary = result["report"]["summary"]
        self.assertNotIn("Buy now", summary["analysis_summary"])
        self.assertNotIn("target price", summary["analysis_summary"])
        self.assertEqual(summary["operation_advice"], "Information only")
        self.assertEqual(result["model_source"], "user_local")


if __name__ == "__main__":
    unittest.main()
