# -*- coding: utf-8 -*-
import os
import sqlite3
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from src.config import Config
from src.storage import DatabaseManager
from src.platform_accounts import PlatformAccountService, QuotaExceeded
from src.services.analysis_service import AnalysisService


class PlatformAccountServiceTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.db_path = os.path.join(self.temp_dir.name, "platform.sqlite")
        DatabaseManager.reset_instance()
        Config.reset_instance()
        self.db = DatabaseManager(db_url=f"sqlite:///{self.db_path}")
        self.service = PlatformAccountService(self.db)

    def tearDown(self) -> None:
        DatabaseManager.reset_instance()
        Config.reset_instance()
        self.temp_dir.cleanup()

    def test_free_user_weekly_quota_blocks_after_limit(self) -> None:
        user = self.service.create_user("free@example.com", "password123")

        before = self.service.get_quota_status(user.id)
        self.assertEqual(before["plan"], "free")
        self.assertEqual(before["weekly_limit"], 5)
        self.assertEqual(before["remaining"], 5)

        self.service.reserve_analysis_quota(user.id, 5, reason="unit-test")
        after = self.service.get_quota_status(user.id)
        self.assertEqual(after["used"], 5)
        self.assertEqual(after["remaining"], 0)

        with self.assertRaises(QuotaExceeded) as ctx:
            self.service.reserve_analysis_quota(user.id, 1, reason="unit-test")

        self.assertEqual(ctx.exception.remaining, 0)
        self.assertEqual(ctx.exception.requested, 1)

    def test_paid_user_has_higher_weekly_quota(self) -> None:
        user = self.service.create_user("paid@example.com", "password123", plan="premium")

        status = self.service.get_quota_status(user.id)

        self.assertEqual(status["plan"], "premium")
        self.assertEqual(status["weekly_limit"], 500)
        self.assertEqual(status["remaining"], 500)

    def test_pro_user_has_higher_weekly_quota(self) -> None:
        user = self.service.create_user("pro@example.com", "password123", plan="pro")

        status = self.service.get_quota_status(user.id)

        self.assertEqual(status["plan"], "pro")
        self.assertEqual(status["weekly_limit"], 500)
        self.assertEqual(status["remaining"], 500)

    def test_user_api_key_is_not_stored_or_returned_as_plaintext(self) -> None:
        user = self.service.create_user("keys@example.com", "password123")

        self.service.store_api_key(user.id, provider="deepseek", api_key="sk-user-secret")
        listed = self.service.list_api_keys(user.id)

        self.assertEqual(len(listed), 1)
        self.assertEqual(listed[0]["provider"], "deepseek")
        self.assertEqual(listed[0]["masked_key"], "sk-u...cret")
        self.assertNotIn("sk-user-secret", str(listed))

        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute("SELECT encrypted_secret FROM platform_user_api_keys").fetchall()
        self.assertEqual(len(rows), 1)
        self.assertNotIn("sk-user-secret", rows[0][0])

    def test_user_api_key_mode_overrides_config_without_mutating_base_config(self) -> None:
        user = self.service.create_user("override@example.com", "password123")
        self.service.store_api_key(user.id, provider="deepseek", api_key="sk-user-secret")
        base_config = SimpleNamespace(
            deepseek_api_keys=["platform-secret"],
            deepseek_api_key="platform-secret",
            openai_api_keys=["platform-openai"],
            report_language="zh",
        )

        scoped = self.service.apply_user_llm_config(base_config, user.id, mode="user")

        self.assertIsNot(scoped, base_config)
        self.assertEqual(scoped.deepseek_api_keys, ["sk-user-secret"])
        self.assertEqual(scoped.deepseek_api_key, "sk-user-secret")
        self.assertEqual(base_config.deepseek_api_keys, ["platform-secret"])
        self.assertEqual(base_config.deepseek_api_key, "platform-secret")

    def test_platform_mode_keeps_base_config(self) -> None:
        user = self.service.create_user("platform@example.com", "password123")
        self.service.store_api_key(user.id, provider="deepseek", api_key="sk-user-secret")
        base_config = SimpleNamespace(deepseek_api_keys=["platform-secret"])

        scoped = self.service.apply_user_llm_config(base_config, user.id, mode="platform")

        self.assertIs(scoped, base_config)
        self.assertEqual(scoped.deepseek_api_keys, ["platform-secret"])

    def test_analysis_service_uses_user_owned_api_key_without_mutating_platform_config(self) -> None:
        user = self.service.create_user("analysis-user-key@example.com", "password123")
        self.service.store_api_key(user.id, provider="deepseek", api_key="sk-user-secret")
        base_config = SimpleNamespace(
            deepseek_api_keys=["platform-secret"],
            deepseek_api_key="platform-secret",
            report_language="zh",
        )
        pipeline_instance = MagicMock()
        pipeline_instance.process_single_stock.return_value = SimpleNamespace(
            success=False,
            error_message="stop-after-config",
        )

        with patch("src.config.get_config", return_value=base_config), \
             patch("src.core.pipeline.StockAnalysisPipeline", return_value=pipeline_instance) as pipeline_cls:
            AnalysisService().analyze_stock(
                "600519",
                report_type="detailed",
                query_id="q-user-key",
                send_notification=False,
                platform_user_id=user.id,
                api_key_mode="user",
            )

        scoped_config = pipeline_cls.call_args.kwargs["config"]
        self.assertIsNot(scoped_config, base_config)
        self.assertEqual(scoped_config.deepseek_api_keys, ["sk-user-secret"])
        self.assertEqual(scoped_config.deepseek_api_key, "sk-user-secret")
        self.assertEqual(base_config.deepseek_api_keys, ["platform-secret"])
        self.assertEqual(pipeline_cls.call_args.kwargs["platform_user_id"], user.id)


if __name__ == "__main__":
    unittest.main()
