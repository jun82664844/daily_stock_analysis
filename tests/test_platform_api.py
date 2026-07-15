# -*- coding: utf-8 -*-
import os
import tempfile
import unittest
from datetime import datetime
from types import SimpleNamespace
from pathlib import Path
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from api.app import create_app
from src import auth as admin_auth
from src.config import Config
from src.platform_accounts import PlatformAccountService
from src.services.task_queue import TaskStatus as QueueTaskStatus
from src.storage import DatabaseManager


def _queue_task(task_id: str, stock_code: str, platform_user_id: int):
    return SimpleNamespace(
        task_id=task_id,
        trace_id=task_id,
        stock_code=stock_code,
        stock_name=None,
        status=QueueTaskStatus.PENDING,
        progress=0,
        message="queued",
        report_type="detailed",
        analysis_phase="auto",
        analysis_depth="fast",
        created_at=datetime(2026, 1, 1, 9, 0, 0),
        started_at=None,
        completed_at=None,
        result=None,
        error=None,
        original_query=None,
        selection_source=None,
        skills=None,
        platform_user_id=platform_user_id,
    )


def _analysis_result(stock_code: str, stock_name: str, summary: str):
    return SimpleNamespace(
        code=stock_code,
        name=stock_name,
        sentiment_score=60,
        operation_advice="hold",
        trend_prediction="sideways",
        analysis_summary=summary,
        news_summary="",
        technical_analysis="",
        fundamental_analysis="",
        risk_warning="",
        data_sources="unit-test",
        raw_response=None,
        success=True,
    )


def _ready_local_runtime():
    status = {
        "enabled": True,
        "reachable": True,
        "ready": True,
        "quick_ready": True,
        "deep_ready": True,
        "reason": "ready",
    }
    return SimpleNamespace(
        get_status=lambda: status,
        readiness_reason=lambda analysis_depth, *, status=None: "ready",
    )


def _save_history_for_user(user_id: int, query_id: str, stock_code: str, stock_name: str) -> int:
    record_id = DatabaseManager.get_instance().save_analysis_history(
        result=_analysis_result(stock_code, stock_name, f"{stock_code} summary"),
        query_id=query_id,
        report_type="detailed",
        news_content="",
        context_snapshot={"diagnostics": {"trace_id": query_id}},
        platform_user_id=user_id,
    )
    if not record_id:
        raise AssertionError("failed to save test analysis history")
    return record_id


class PlatformApiTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.db_path = os.path.join(self.temp_dir.name, "platform-api.sqlite")
        self.static_dir = Path(self.temp_dir.name) / "static"
        self.static_dir.mkdir()
        (self.static_dir / "index.html").write_text("<html>ok</html>", encoding="utf-8")
        DatabaseManager.reset_instance()
        Config.reset_instance()
        admin_auth._rate_limit.clear()
        self.env_patch = patch.dict(
            os.environ,
            {
                "DATABASE_PATH": self.db_path,
                "ADMIN_AUTH_ENABLED": "true",
                "PLATFORM_USER_AUTH_ENABLED": "true",
                "PLATFORM_CSRF_ENABLED": "false",
            },
            clear=False,
        )
        self.env_patch.start()
        self.client = TestClient(create_app(static_dir=self.static_dir))

    def tearDown(self) -> None:
        self.client.close()
        self.env_patch.stop()
        admin_auth._rate_limit.clear()
        DatabaseManager.reset_instance()
        Config.reset_instance()
        self.temp_dir.cleanup()

    def test_platform_register_sets_user_session_and_returns_quota(self) -> None:
        response = self.client.post(
            "/api/v1/platform/register",
            json={"email": "User@Example.com", "password": "password123"},
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["user"]["email"], "user@example.com")
        self.assertEqual(body["quota"]["plan"], "free")
        self.assertEqual(body["quota"]["remaining"], 5)
        self.assertIn("dsa_user_session", response.cookies)

        me = self.client.get("/api/v1/platform/me")
        self.assertEqual(me.status_code, 200)
        self.assertEqual(me.json()["user"]["email"], "user@example.com")

    def test_platform_login_rejects_bad_password_and_accepts_good_password(self) -> None:
        self.client.post(
            "/api/v1/platform/register",
            json={"email": "login@example.com", "password": "password123"},
        )
        self.client.post("/api/v1/platform/logout")

        bad = self.client.post(
            "/api/v1/platform/login",
            json={"email": "login@example.com", "password": "wrong-password"},
        )
        self.assertEqual(bad.status_code, 401)

        good = self.client.post(
            "/api/v1/platform/login",
            json={"email": "login@example.com", "password": "password123"},
        )
        self.assertEqual(good.status_code, 200)
        self.assertIn("dsa_user_session", good.cookies)

    def test_platform_login_rate_limits_repeated_bad_passwords(self) -> None:
        self.client.post(
            "/api/v1/platform/register",
            json={"email": "rate-limit@example.com", "password": "password123"},
        )
        self.client.post("/api/v1/platform/logout")

        for _ in range(admin_auth.RATE_LIMIT_MAX_FAILURES):
            bad = self.client.post(
                "/api/v1/platform/login",
                json={"email": "rate-limit@example.com", "password": "wrong-password"},
            )
            self.assertEqual(bad.status_code, 401)

        limited = self.client.post(
            "/api/v1/platform/login",
            json={"email": "rate-limit@example.com", "password": "wrong-password"},
        )
        self.assertEqual(limited.status_code, 429)
        self.assertEqual(limited.json()["error"], "rate_limited")

    def test_platform_login_success_clears_bad_password_rate_limit(self) -> None:
        self.client.post(
            "/api/v1/platform/register",
            json={"email": "clear-limit@example.com", "password": "password123"},
        )
        self.client.post("/api/v1/platform/logout")
        bad = self.client.post(
            "/api/v1/platform/login",
            json={"email": "clear-limit@example.com", "password": "wrong-password"},
        )
        self.assertEqual(bad.status_code, 401)

        good = self.client.post(
            "/api/v1/platform/login",
            json={"email": "clear-limit@example.com", "password": "password123"},
        )
        self.assertEqual(good.status_code, 200)
        self.client.post("/api/v1/platform/logout")

        for _ in range(admin_auth.RATE_LIMIT_MAX_FAILURES):
            bad_after_clear = self.client.post(
                "/api/v1/platform/login",
                json={"email": "clear-limit@example.com", "password": "wrong-password"},
            )
            self.assertEqual(bad_after_clear.status_code, 401)

    def test_platform_me_requires_user_session(self) -> None:
        response = self.client.get("/api/v1/platform/me")

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["error"], "unauthorized")

    def test_duplicate_registration_is_rejected(self) -> None:
        first = self.client.post(
            "/api/v1/platform/register",
            json={"email": "dupe@example.com", "password": "password123"},
        )
        second = self.client.post(
            "/api/v1/platform/register",
            json={"email": "dupe@example.com", "password": "password123"},
        )

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 409)

    def test_analysis_consumes_one_platform_quota(self) -> None:
        register = self.client.post(
            "/api/v1/platform/register",
            json={"email": "quota@example.com", "password": "password123"},
        )
        user_id = register.json()["user"]["id"]

        service_instance = SimpleNamespace(
            last_error=None,
            analyze_stock=lambda **kwargs: {
                "stock_code": "600519",
                "stock_name": "贵州茅台",
                "report": {
                    "meta": {"stock_code": "600519", "report_language": "zh"},
                    "summary": {"analysis_summary": "ok"},
                    "strategy": {},
                    "details": {},
                },
            },
        )

        with patch("src.services.analysis_service.AnalysisService", return_value=service_instance), \
             patch("api.v1.endpoints.analysis._load_sync_fundamental_sources", return_value=(None, None)):
            response = self.client.post(
                "/api/v1/analysis/analyze",
                json={"stock_code": "600519", "async_mode": False},
            )

        self.assertEqual(response.status_code, 200)
        quota = PlatformAccountService().get_quota_status(user_id)
        self.assertEqual(quota["used"], 1)
        self.assertEqual(quota["remaining"], 4)

    def test_analysis_rejects_platform_user_when_quota_exhausted(self) -> None:
        register = self.client.post(
            "/api/v1/platform/register",
            json={"email": "limited@example.com", "password": "password123"},
        )
        user_id = register.json()["user"]["id"]
        PlatformAccountService().reserve_analysis_quota(user_id, 5, reason="test-preload")

        with patch("src.services.analysis_service.AnalysisService") as analysis_service_cls:
            response = self.client.post(
                "/api/v1/analysis/analyze",
                json={"stock_code": "600519", "async_mode": False},
            )

        self.assertEqual(response.status_code, 429)
        self.assertEqual(response.json()["error"], "quota_exceeded")
        analysis_service_cls.assert_not_called()

    def test_analysis_can_use_user_owned_api_key_mode(self) -> None:
        register = self.client.post(
            "/api/v1/platform/register",
            json={"email": "own-key@example.com", "password": "password123"},
        )
        user_id = register.json()["user"]["id"]
        key_response = self.client.post(
            "/api/v1/platform/api-keys",
            json={"provider": "deepseek", "apiKey": "sk-user-owned-secret"},
        )
        self.assertEqual(key_response.status_code, 200)
        self.assertNotIn("sk-user-owned-secret", str(key_response.json()))

        service_instance = MagicMock()
        service_instance.last_error = None
        service_instance.analyze_stock.return_value = {
            "stock_code": "600519",
            "stock_name": "贵州茅台",
            "report": {
                "meta": {"stock_code": "600519", "report_language": "zh"},
                "summary": {"analysis_summary": "ok"},
                "strategy": {},
                "details": {},
            },
        }

        with patch("src.services.analysis_service.AnalysisService", return_value=service_instance), \
             patch("api.v1.endpoints.analysis._load_sync_fundamental_sources", return_value=(None, None)):
            response = self.client.post(
                "/api/v1/analysis/analyze",
                json={"stock_code": "600519", "async_mode": False, "apiKeyMode": "user"},
            )

        self.assertEqual(response.status_code, 200)
        kwargs = service_instance.analyze_stock.call_args.kwargs
        self.assertEqual(kwargs["api_key_mode"], "user")
        self.assertEqual(kwargs["platform_user_id"], user_id)

    def test_async_analysis_tags_platform_mode_tasks_with_current_user(self) -> None:
        register = self.client.post(
            "/api/v1/platform/register",
            json={"email": "async-owner@example.com", "password": "password123"},
        )
        user_id = register.json()["user"]["id"]
        accepted_task = _queue_task("task-owned", "600519", user_id)
        fake_queue = MagicMock()
        fake_queue.submit_tasks_batch.return_value = ([accepted_task], [])

        with patch("api.v1.endpoints.analysis.get_task_queue", return_value=fake_queue):
            response = self.client.post(
                "/api/v1/analysis/analyze",
                json={"stock_code": "600519", "async_mode": True},
            )

        self.assertEqual(response.status_code, 202)
        kwargs = fake_queue.submit_tasks_batch.call_args.kwargs
        self.assertEqual(kwargs["api_key_mode"], "platform")
        self.assertEqual(kwargs["platform_user_id"], user_id)

    def test_async_analysis_can_select_local_model_mode(self) -> None:
        register = self.client.post(
            "/api/v1/platform/register",
            json={"email": "async-local@example.com", "password": "password123"},
        )
        user_id = register.json()["user"]["id"]
        accepted_task = _queue_task("task-local", "600519", user_id)
        fake_queue = MagicMock()
        fake_queue.submit_tasks_batch.return_value = ([accepted_task], [])

        with patch("api.v1.endpoints.analysis.get_task_queue", return_value=fake_queue), \
             patch("src.services.ollama_runtime_service.get_ollama_runtime_service", return_value=_ready_local_runtime()):
            response = self.client.post(
                "/api/v1/analysis/analyze",
                json={"stock_code": "600519", "async_mode": True, "apiKeyMode": "local"},
            )

        self.assertEqual(response.status_code, 202)
        kwargs = fake_queue.submit_tasks_batch.call_args.kwargs
        self.assertEqual(kwargs["api_key_mode"], "local")
        self.assertEqual(kwargs["platform_user_id"], user_id)

    def test_platform_user_task_list_only_returns_owned_tasks(self) -> None:
        register = self.client.post(
            "/api/v1/platform/register",
            json={"email": "tasks-owner@example.com", "password": "password123"},
        )
        user_id = register.json()["user"]["id"]
        other = PlatformAccountService().create_user("tasks-other@example.com", "password123")
        own_task = _queue_task("task-own", "600519", user_id)
        other_task = _queue_task("task-other", "AAPL", int(other.id))
        fake_queue = MagicMock()
        fake_queue.list_all_tasks.return_value = [own_task, other_task]
        fake_queue.get_task_stats.return_value = {"total": 2, "pending": 2, "processing": 0}

        with patch("api.v1.endpoints.analysis.get_task_queue", return_value=fake_queue):
            response = self.client.get("/api/v1/analysis/tasks")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["total"], 1)
        self.assertEqual([task["task_id"] for task in body["tasks"]], ["task-own"])

    def test_platform_user_history_list_only_returns_owned_records(self) -> None:
        register = self.client.post(
            "/api/v1/platform/register",
            json={"email": "history-owner@example.com", "password": "password123"},
        )
        owner_id = register.json()["user"]["id"]
        other = PlatformAccountService().create_user("history-other@example.com", "password123")
        own_id = _save_history_for_user(owner_id, "q-history-own", "600519", "Kweichow Moutai")
        other_id = _save_history_for_user(int(other.id), "q-history-other", "AAPL", "Apple")

        response = self.client.get("/api/v1/history")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["total"], 1)
        self.assertEqual([item["id"] for item in body["items"]], [own_id])
        self.assertNotIn(other_id, [item["id"] for item in body["items"]])

    def test_platform_user_cannot_read_or_delete_another_users_history(self) -> None:
        register = self.client.post(
            "/api/v1/platform/register",
            json={"email": "history-detail-owner@example.com", "password": "password123"},
        )
        owner_id = register.json()["user"]["id"]
        other = PlatformAccountService().create_user("history-detail-other@example.com", "password123")
        own_id = _save_history_for_user(owner_id, "q-history-detail-own", "600519", "Kweichow Moutai")
        other_id = _save_history_for_user(int(other.id), "q-history-detail-other", "AAPL", "Apple")

        own_detail = self.client.get(f"/api/v1/history/{own_id}")
        other_detail = self.client.get(f"/api/v1/history/{other_id}")
        delete_other = self.client.request(
            "DELETE",
            "/api/v1/history",
            json={"record_ids": [other_id]},
        )

        self.assertEqual(own_detail.status_code, 200)
        self.assertEqual(other_detail.status_code, 404)
        self.assertEqual(delete_other.status_code, 200)
        self.assertEqual(delete_other.json()["deleted"], 0)
        self.assertIsNotNone(DatabaseManager.get_instance().get_analysis_history_by_id(other_id))

    def test_existing_admin_session_can_read_all_platform_history(self) -> None:
        register = self.client.post(
            "/api/v1/platform/register",
            json={"email": "history-admin-owner@example.com", "password": "password123"},
        )
        owner_id = register.json()["user"]["id"]
        other = PlatformAccountService().create_user("history-admin-other@example.com", "password123")
        own_id = _save_history_for_user(owner_id, "q-history-admin-own", "600519", "Kweichow Moutai")
        other_id = _save_history_for_user(int(other.id), "q-history-admin-other", "AAPL", "Apple")
        admin_login = self.client.post(
            "/api/v1/auth/login",
            json={"password": "AdminPass123", "passwordConfirm": "AdminPass123"},
        )
        self.assertEqual(admin_login.status_code, 200)

        response = self.client.get("/api/v1/history")

        self.assertEqual(response.status_code, 200)
        ids = {item["id"] for item in response.json()["items"]}
        self.assertTrue({own_id, other_id}.issubset(ids))

    def test_platform_user_cannot_read_another_users_task_status(self) -> None:
        self.client.post(
            "/api/v1/platform/register",
            json={"email": "status-owner@example.com", "password": "password123"},
        )
        other = PlatformAccountService().create_user("status-other@example.com", "password123")
        fake_queue = MagicMock()
        fake_queue.get_task.return_value = _queue_task("task-other", "AAPL", int(other.id))

        with patch("api.v1.endpoints.analysis.get_task_queue", return_value=fake_queue):
            response = self.client.get("/api/v1/analysis/status/task-other")

        self.assertEqual(response.status_code, 404)

    def test_platform_user_cannot_read_another_users_task_flow(self) -> None:
        self.client.post(
            "/api/v1/platform/register",
            json={"email": "flow-owner@example.com", "password": "password123"},
        )
        other = PlatformAccountService().create_user("flow-other@example.com", "password123")
        fake_queue = MagicMock()
        fake_queue.get_task.return_value = _queue_task("task-other", "AAPL", int(other.id))

        with patch("api.v1.endpoints.analysis.get_task_queue", return_value=fake_queue):
            response = self.client.get("/api/v1/analysis/tasks/task-other/flow")

        self.assertEqual(response.status_code, 404)

    def test_market_review_background_task_is_tagged_with_current_user(self) -> None:
        register = self.client.post(
            "/api/v1/platform/register",
            json={"email": "market-owner@example.com", "password": "password123"},
        )
        user_id = register.json()["user"]["id"]
        accepted_task = _queue_task("market-task", "market_review", user_id)
        fake_queue = MagicMock()
        fake_queue.submit_background_task.return_value = accepted_task

        with patch("api.v1.endpoints.analysis.get_task_queue", return_value=fake_queue), \
             patch("api.v1.endpoints.analysis._try_acquire_market_review_lock", return_value=object()):
            response = self.client.post(
                "/api/v1/analysis/market-review",
                json={"send_notification": False},
            )

        self.assertEqual(response.status_code, 202)
        kwargs = fake_queue.submit_background_task.call_args.kwargs
        self.assertEqual(kwargs["platform_user_id"], user_id)

    def test_platform_admin_can_upgrade_user_plan_but_free_user_cannot(self) -> None:
        user_register = self.client.post(
            "/api/v1/platform/register",
            json={"email": "normal@example.com", "password": "password123"},
        )
        user_id = user_register.json()["user"]["id"]

        forbidden = self.client.get("/api/v1/platform/admin/users")
        self.assertEqual(forbidden.status_code, 403)

        self.client.post("/api/v1/platform/logout")
        PlatformAccountService().create_user("admin@example.com", "password123", role="admin")
        admin_login = self.client.post(
            "/api/v1/platform/login",
            json={"email": "admin@example.com", "password": "password123"},
        )
        self.assertEqual(admin_login.status_code, 200)

        upgraded = self.client.patch(
            f"/api/v1/platform/admin/users/{user_id}/plan",
            json={"plan": "pro"},
        )

        self.assertEqual(upgraded.status_code, 200)
        self.assertEqual(upgraded.json()["user"]["plan"], "pro")
        quota = PlatformAccountService().get_quota_status(user_id)
        self.assertEqual(quota["weekly_limit"], 500)

    def test_platform_admin_can_toggle_alphasift_but_free_user_cannot(self) -> None:
        self.client.post(
            "/api/v1/platform/register",
            json={"email": "alphasift-user@example.com", "password": "password123"},
        )

        forbidden = self.client.post(
            "/api/v1/platform/admin/features/alphasift",
            json={"enabled": True},
        )
        self.assertEqual(forbidden.status_code, 403)

        self.client.post("/api/v1/platform/logout")
        PlatformAccountService().create_user("alphasift-admin@example.com", "password123", role="admin")
        login = self.client.post(
            "/api/v1/platform/login",
            json={"email": "alphasift-admin@example.com", "password": "password123"},
        )
        self.assertEqual(login.status_code, 200)

        config_service = MagicMock()
        config_service.get_config.return_value = {
            "config_version": "v1",
            "mask_token": "******",
        }
        config_service.update.return_value = {
            "config_version": "v2",
            "updated_keys": ["ALPHASIFT_ENABLED"],
            "reload_triggered": True,
        }
        with patch(
            "api.v1.endpoints.platform.SystemConfigService",
            return_value=config_service,
        ):
            enabled = self.client.post(
                "/api/v1/platform/admin/features/alphasift",
                json={"enabled": True},
            )

        self.assertEqual(enabled.status_code, 200)
        self.assertTrue(enabled.json()["enabled"])
        config_service.update.assert_called_once_with(
            config_version="v1",
            items=[{"key": "ALPHASIFT_ENABLED", "value": "true"}],
            mask_token="******",
            reload_now=True,
        )

    def test_platform_admin_can_view_usage_buckets_and_audit_events(self) -> None:
        register = self.client.post(
            "/api/v1/platform/register",
            json={"email": "usage-user@example.com", "password": "password123"},
        )
        user_id = register.json()["user"]["id"]
        PlatformAccountService().reserve_feature_quota(user_id, "ai_quick", reference_id="AAPL")
        PlatformAccountService().create_user("usage-admin@example.com", "password123", role="admin")
        admin_login = self.client.post(
            "/api/v1/platform/login",
            json={"email": "usage-admin@example.com", "password": "password123"},
        )
        self.assertEqual(admin_login.status_code, 200)

        response = self.client.get("/api/v1/platform/admin/usage")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(any(row["quota_bucket"] == "ai_quick" and row["used"] >= 1 for row in body["usage"]))
        self.assertTrue(any(event["action"] == "quota_reserved" for event in body["audit_events"]))

    def test_existing_admin_session_can_manage_platform_users(self) -> None:
        self.client.post(
            "/api/v1/platform/register",
            json={"email": "admin-managed@example.com", "password": "password123"},
        )
        admin_login = self.client.post(
            "/api/v1/auth/login",
            json={"password": "AdminPass123", "passwordConfirm": "AdminPass123"},
        )
        self.assertEqual(admin_login.status_code, 200)

        response = self.client.get("/api/v1/platform/admin/users")

        self.assertEqual(response.status_code, 200)
        self.assertTrue(any(user["email"] == "admin-managed@example.com" for user in response.json()["users"]))


if __name__ == "__main__":
    unittest.main()
