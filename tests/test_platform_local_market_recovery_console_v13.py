# -*- coding: utf-8 -*-
import importlib.util
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from api.app import create_app
from src.config import Config
from src.services.market_source_health import MarketSourceHealthRegistry
from src.storage import DatabaseManager


class PlatformLocalMarketRecoveryConsoleV13TestCase(unittest.TestCase):
    def test_recovery_resets_selected_sources_without_global_reset_or_ai(self) -> None:
        from src.services.market_source_ops import recover_market_sources

        health = MarketSourceHealthRegistry(failure_threshold=2, cooling_seconds=60)
        health.record_timeout("hk_realtime", elapsed_ms=4100)
        health.record_timeout("hk_realtime", elapsed_ms=4200)
        health.record_timeout("us_realtime", elapsed_ms=4100)
        health.record_timeout("us_realtime", elapsed_ms=4200)

        result = recover_market_sources(
            source_health=health,
            sources=["hk_realtime"],
            symbols=[],
            prewarm=False,
        )

        self.assertFalse(result["ai_used"])
        self.assertEqual(result["mode"], "local_only")
        self.assertEqual(result["reset_count"], 1)
        self.assertEqual(result["reset_sources"], ["hk_realtime"])
        self.assertEqual(health.snapshot("hk_realtime")["status"], "ok")
        self.assertEqual(health.snapshot("us_realtime")["status"], "cooling_down")

    def test_recovery_endpoint_requires_admin_and_does_not_use_ai(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
            db_path = Path(temp_dir) / "v13-recovery.sqlite"
            static_dir = Path(temp_dir) / "static"
            static_dir.mkdir()
            (static_dir / "index.html").write_text("<html>ok</html>", encoding="utf-8")
            DatabaseManager.reset_instance()
            Config.reset_instance()
            with patch.dict(
                os.environ,
                {
                    "DATABASE_PATH": str(db_path),
                    "ADMIN_AUTH_ENABLED": "true",
                    "PLATFORM_USER_AUTH_ENABLED": "true",
                    "PLATFORM_CSRF_ENABLED": "false",
                },
                clear=False,
            ):
                client = TestClient(create_app(static_dir=static_dir))
                client.post(
                    "/api/v1/platform/register",
                    json={"email": "v13-user@example.com", "password": "password123"},
                )
                user_response = client.post(
                    "/api/v1/stocks/sources/recovery",
                    json={"sources": ["hk_realtime"], "prewarm": False},
                )
                client.post("/api/v1/platform/logout")
                login = client.post(
                    "/api/v1/auth/login",
                    json={"password": "AdminPass123", "passwordConfirm": "AdminPass123"},
                )
                admin_response = client.post(
                    "/api/v1/stocks/sources/recovery",
                    json={"sources": ["hk_realtime"], "prewarm": False},
                )
                client.close()

            DatabaseManager.reset_instance()
            Config.reset_instance()

        self.assertEqual(user_response.status_code, 403)
        self.assertEqual(login.status_code, 200)
        self.assertEqual(admin_response.status_code, 200)
        body = admin_response.json()
        self.assertFalse(body["ai_used"])
        self.assertEqual(body["reset_sources"], ["hk_realtime"])
        self.assertEqual(body["prewarm"]["requested"], 0)

    def test_v13_verifier_file_and_marker_are_visible(self) -> None:
        root = Path(__file__).resolve().parents[1]
        verifier = root / "scripts" / "verify_platform_local_market_recovery_console_v13.py"

        self.assertTrue(verifier.exists(), "V13 verifier script is missing")
        self.assertIsNotNone(importlib.util.find_spec("scripts.verify_platform_local_market_recovery_console_v13"))

        from scripts.verify_platform_local_market_recovery_console_v13 import OK_MARKER

        self.assertEqual(OK_MARKER, "DSA_PLATFORM_LOCAL_MARKET_RECOVERY_CONSOLE_V13_OK")


if __name__ == "__main__":
    unittest.main()
