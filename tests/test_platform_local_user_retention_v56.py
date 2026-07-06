# -*- coding: utf-8 -*-
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from api.app import create_app
from src.config import Config
from src.storage import DatabaseManager


def _snapshot(code: str = "AAPL", *, ai_used: bool = False) -> dict:
    return {
        "stock_code": code,
        "stock_name": "Apple Inc.",
        "market": "us",
        "quote": {
            "current_price": 200.25,
            "change": 1.5,
            "change_percent": 0.75,
            "source": "unit_quote",
            "freshness": "fresh",
        },
        "indicators": {
            "ma5": 198.0,
            "ma20": 190.5,
            "volume_price_signal": "price up on stable volume",
        },
        "route": {
            "input_code": code,
            "normalized_code": code,
            "market": "us",
            "channel": "us_equity",
            "data_source_lane": "us_market_data",
            "quote_sources": ["unit_quote"],
            "history_sources": ["unit_history"],
            "ai_required": False,
        },
        "diagnostics": {
            "elapsed_ms": 9,
            "route_lane": "us_market_data",
            "cache": {"quote": "hit", "history": "hit"},
            "fallback": {"quote": "cache", "history": "cache"},
        },
        "intelligence": {
            "retention_brief": {
                "headline": "Apple no-AI snapshot ready",
                "why_it_matters": ["Free quick snapshot used cached quote and indicators."],
                "support_resistance": ["Support near 198, resistance near 205."],
                "next_steps": ["Save this local report after login."],
                "upgrade_hint": "Login to save history and watchlist.",
                "boundary": "For informational analysis only; not investment advice.",
                "source": "no_ai_retention_rules",
            },
            "signal_score": {"score": 61, "label": "neutral"},
        },
        "warnings": [],
        "degradation": {"status": "ok", "severity": "info", "message": ""},
        "ai_used": ai_used,
    }


class PlatformLocalUserRetentionV56TestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.db_path = os.path.join(self.temp_dir.name, "platform-retention-v56.sqlite")
        self.static_dir = Path(self.temp_dir.name) / "static"
        self.static_dir.mkdir()
        (self.static_dir / "index.html").write_text("<html>ok</html>", encoding="utf-8")
        DatabaseManager.reset_instance()
        Config.reset_instance()
        self.env_patch = patch.dict(
            os.environ,
            {
                "DATABASE_PATH": self.db_path,
                "ADMIN_AUTH_ENABLED": "true",
                "PLATFORM_USER_AUTH_ENABLED": "true",
                "PLATFORM_CSRF_ENABLED": "false",
                "SEARXNG_PUBLIC_INSTANCES_ENABLED": "false",
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

    def _register(self, email: str) -> dict:
        response = self.client.post(
            "/api/v1/platform/register",
            json={"email": email, "password": "password123"},
        )
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def test_guest_snapshot_can_be_saved_to_private_platform_history_after_login(self) -> None:
        anonymous = TestClient(create_app(static_dir=self.static_dir))
        try:
            unauthenticated = anonymous.post(
                "/api/v1/platform/history/snapshot",
                json={"snapshot": _snapshot("AAPL")},
            )
            self.assertEqual(unauthenticated.status_code, 401)
        finally:
            anonymous.close()

        user_a = self._register("v56-alice@example.com")
        self.assertEqual(user_a["quota"]["plan"], "free")

        saved = self.client.post(
            "/api/v1/platform/history/snapshot",
            json={"snapshot": _snapshot("AAPL"), "note": "guest result saved after register"},
        )
        self.assertEqual(saved.status_code, 200, saved.text)
        saved_body = saved.json()
        self.assertEqual(saved_body["stock_code"], "AAPL")
        self.assertEqual(saved_body["report_type"], "basic_snapshot")
        self.assertTrue(saved_body["saved_to_history"])
        self.assertFalse(saved_body["ai_used"])
        self.assertNotIn("sk-", str(saved_body).lower())

        history = self.client.get("/api/v1/history", params={"stock_code": "AAPL"})
        self.assertEqual(history.status_code, 200, history.text)
        items = history.json()["items"]
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["stock_code"], "AAPL")
        self.assertEqual(items[0]["report_type"], "basic_snapshot")
        self.assertIn("Apple no-AI snapshot", items[0]["analysis_summary"])

        self._register("v56-bob@example.com")
        isolated = self.client.get("/api/v1/history", params={"stock_code": "AAPL"})
        self.assertEqual(isolated.status_code, 200)
        self.assertEqual(isolated.json()["items"], [])

    def test_snapshot_history_save_rejects_ai_used_payloads(self) -> None:
        self._register("v56-ai-guard@example.com")

        response = self.client.post(
            "/api/v1/platform/history/snapshot",
            json={"snapshot": _snapshot("AAPL", ai_used=True)},
        )

        self.assertEqual(response.status_code, 400)
        body = response.json()
        self.assertEqual(body["error"], "invalid_request")
        self.assertIn("no-AI", body["message"])
        history = self.client.get("/api/v1/history", params={"stock_code": "AAPL"})
        self.assertEqual(history.json()["items"], [])

    def test_v56_verifier_file_and_marker_are_visible(self) -> None:
        root = Path(__file__).resolve().parents[1]
        verifier = root / "scripts" / "verify_platform_local_user_retention_v56.py"

        self.assertTrue(verifier.exists(), "V56 verifier script is missing")

        from scripts.verify_platform_local_user_retention_v56 import OK_MARKER

        self.assertEqual(OK_MARKER, "DSA_PLATFORM_LOCAL_USER_RETENTION_V56_OK")


if __name__ == "__main__":
    unittest.main()
