import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from fastapi.testclient import TestClient

from api.app import create_app
from src.config import Config
from src.platform_accounts import PlatformAccountService
from src.storage import DatabaseManager


class PlatformOllamaAnalysisV107TestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.static_dir = Path(self.temp_dir.name) / "static"
        self.static_dir.mkdir()
        (self.static_dir / "index.html").write_text("<html>ok</html>", encoding="utf-8")
        DatabaseManager.reset_instance()
        Config.reset_instance()
        self.env_patch = patch.dict(
            os.environ,
            {
                "DATABASE_PATH": str(Path(self.temp_dir.name) / "ollama-analysis.sqlite"),
                "PLATFORM_USER_AUTH_ENABLED": "true",
                "PLATFORM_CSRF_ENABLED": "false",
                "PLATFORM_MEMBER_MODEL_PICKER_ENABLED": "false",
                "LOCAL_LLM_ENABLED": "true",
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

    def test_local_mode_requires_login(self) -> None:
        response = self.client.post(
            "/api/v1/analysis/analyze",
            json={"stock_code": "AAPL", "apiKeyMode": "local", "async_mode": False},
        )

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["error"], "unauthorized")

    def test_unavailable_runtime_does_not_consume_free_local_quota(self) -> None:
        registered = self.client.post(
            "/api/v1/platform/register",
            json={"email": "ollama-free@example.com", "password": "password123"},
        )
        user_id = registered.json()["user"]["id"]
        status = {
            "enabled": True,
            "reachable": False,
            "ready": False,
            "quick_ready": False,
            "deep_ready": False,
            "reason": "local_model_unreachable",
        }

        with patch(
            "src.services.ollama_runtime_service.OllamaRuntimeService.get_status",
            return_value=status,
        ), patch("src.services.analysis_service.AnalysisService") as analysis_service:
            response = self.client.post(
                "/api/v1/analysis/analyze",
                json={"stock_code": "AAPL", "apiKeyMode": "local", "async_mode": False},
            )

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["error"], "local_model_unreachable")
        analysis_service.assert_not_called()
        quota = PlatformAccountService().get_feature_quota_status(user_id, "ai_local")
        self.assertEqual(quota["used"], 0)

    def test_local_model_quota_does_not_reduce_platform_api_trial(self) -> None:
        registered = self.client.post(
            "/api/v1/platform/register",
            json={"email": "ollama-buckets@example.com", "password": "password123"},
        )
        user_id = registered.json()["user"]["id"]
        service = PlatformAccountService()

        service.reserve_feature_quota(
            user_id,
            "ai_quick",
            api_key_mode="local",
            reference_id="ollama-local-only",
        )

        base_quota = service.get_quota_status(user_id)
        platform_quota = service.get_feature_quota_status(user_id, "ai_quick")
        local_quota = service.get_feature_quota_status(user_id, "ai_local")
        self.assertEqual(base_quota["used"], 0)
        self.assertEqual(base_quota["remaining"], 5)
        self.assertEqual(platform_quota["used"], 0)
        self.assertEqual(local_quota["used"], 1)

    def test_busy_local_model_returns_stable_error_and_releases_reserved_quota(self) -> None:
        registered = self.client.post(
            "/api/v1/platform/register",
            json={"email": "ollama-busy@example.com", "password": "password123"},
        )
        user_id = registered.json()["user"]["id"]
        ready_status = {
            "enabled": True,
            "reachable": True,
            "ready": True,
            "quick_ready": True,
            "deep_ready": True,
            "reason": "ready",
        }

        with patch(
            "src.services.ollama_runtime_service.OllamaRuntimeService.get_status",
            return_value=ready_status,
        ), patch("src.services.analysis_service.AnalysisService") as analysis_service:
            analysis_service.return_value.analyze_stock.return_value = None
            analysis_service.return_value.last_error = "local_model_busy"
            response = self.client.post(
                "/api/v1/analysis/analyze",
                json={"stock_code": "AAPL", "apiKeyMode": "local", "async_mode": False},
            )

        self.assertEqual(response.status_code, 503)
        payload = response.json().get("detail", response.json())
        self.assertEqual(payload["error"], "local_model_busy")
        quota = PlatformAccountService().get_feature_quota_status(user_id, "ai_local")
        self.assertEqual(quota["used"], 0)

    def test_local_report_boundary_removes_action_levels(self) -> None:
        from src.services.analysis_service import AnalysisService

        result = SimpleNamespace(
            code="AAPL",
            name="Apple Inc.",
            current_price=200,
            change_pct=1.0,
            sentiment_score=50,
            operation_advice="Buy now",
            action="buy",
            decision_type="buy",
            trend_prediction="up",
            analysis_summary="Data summary",
            news_summary="News facts",
            technical_analysis="Technical facts",
            fundamental_analysis="Fundamental facts",
            risk_warning="Data may be stale",
            report_language="en",
            get_sniper_points=lambda: {
                "ideal_buy": 190,
                "secondary_buy": 185,
                "stop_loss": 180,
                "take_profit": 220,
            },
            to_dict=lambda: {},
        )

        payload = AnalysisService()._build_analysis_response(
            result,
            "query-local",
            informational_only=True,
        )

        self.assertEqual(payload["report"]["summary"]["operation_advice"], "Information only")
        self.assertIsNone(payload["report"]["summary"]["action"])
        self.assertEqual(payload["report"]["summary"]["action_label"], "Information only")
        self.assertTrue(all(value is None for value in payload["report"]["strategy"].values()))

    def test_history_keeps_information_label_without_mapping_it_to_hold(self) -> None:
        from src.services.history_service import HistoryService

        service = object.__new__(HistoryService)
        fields = service._decision_action_fields_for_record(
            SimpleNamespace(operation_advice="仅供信息观察", report_type="brief"),
            {
                "operation_advice": "仅供信息观察",
                "action": None,
                "action_label": "仅供信息观察",
                "report_language": "zh",
            },
        )

        self.assertIsNone(fields["action"])
        self.assertEqual(fields["action_label"], "仅供信息观察")

    def test_legacy_ollama_history_is_sanitized_without_mutating_stored_payload(self) -> None:
        from src.services.history_service import HistoryService

        stored = {
            "model_used": "ollama/qwen3-vl:8b-instruct",
            "report_language": "zh",
            "sentiment_score": 59,
            "operation_advice": "持有",
            "action": "hold",
            "action_label": "持有",
            "trend_prediction": "强烈看多",
            "analysis_summary": "可择机买入，止损设于MA20下方，目标看325元。",
            "dashboard": {
                "core_conclusion": {"one_sentence": "继续持有"},
                "battle_plan": {
                    "sniper_points": {"ideal_buy": 190, "stop_loss": 180, "take_profit": 325},
                    "action_checklist": ["突破后买入"],
                },
            },
        }

        sanitized = HistoryService._sanitize_informational_local_model_raw_result(stored)

        self.assertEqual(stored["operation_advice"], "持有")
        self.assertEqual(sanitized["operation_advice"], "仅供信息观察")
        self.assertIsNone(sanitized["action"])
        self.assertEqual(sanitized["sentiment_score"], 50)
        self.assertNotIn("325", sanitized["analysis_summary"])
        self.assertTrue(sanitized["informational_only_mode"])
        self.assertTrue(
            all(
                value is None
                for value in sanitized["dashboard"]["battle_plan"]["sniper_points"].values()
            )
        )

    def test_pipeline_boundary_is_applied_before_history_persistence(self) -> None:
        from src.core.pipeline import StockAnalysisPipeline

        result = SimpleNamespace(
            report_language="zh",
            operation_advice="持有",
            action="hold",
            action_label="持有",
            decision_type="hold",
            buy_reason="价格突破压力位",
            sentiment_score=59,
            trend_prediction="强烈看多",
            analysis_summary="缩量回调后可择机买入，止损设于MA20下方，目标看325元。",
            short_term_outlook="短期可加仓",
            medium_term_outlook="中期继续持有",
            dashboard={
                "core_conclusion": {
                    "one_sentence": "继续持有",
                    "signal_type": "持有信号",
                    "position_advice": {"no_position": "买入", "has_position": "继续持有"},
                },
                "battle_plan": {
                    "sniper_points": {
                        "ideal_buy": 190,
                        "secondary_buy": 185,
                        "stop_loss": 180,
                        "take_profit": 220,
                    },
                    "action_checklist": ["突破后买入"],
                },
            },
        )

        StockAnalysisPipeline._apply_information_only_boundary(result)

        self.assertEqual(result.operation_advice, "仅供信息观察")
        self.assertEqual(result.action_label, "仅供信息观察")
        self.assertIsNone(result.action)
        self.assertEqual(result.decision_type, "information")
        self.assertEqual(result.sentiment_score, 50)
        self.assertEqual(result.trend_prediction, "信息观察")
        self.assertNotIn("买入", result.analysis_summary)
        self.assertNotIn("止损", result.analysis_summary)
        self.assertNotIn("325", result.analysis_summary)
        self.assertIn("不提供", result.analysis_summary)
        self.assertEqual(result.short_term_outlook, "")
        self.assertEqual(result.medium_term_outlook, "")
        self.assertEqual(
            result.dashboard["core_conclusion"]["one_sentence"],
            result.analysis_summary,
        )
        self.assertEqual(result.buy_reason, "")
        self.assertEqual(result.dashboard["battle_plan"]["action_checklist"], [])
        self.assertTrue(
            all(value is None for value in result.dashboard["battle_plan"]["sniper_points"].values())
        )


if __name__ == "__main__":
    unittest.main()
