# -*- coding: utf-8 -*-
import os
import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from api.app import create_app
from src.config import Config
from src.services.market_source_health import MarketSourceHealthRegistry
from src.services.market_source_ops import build_market_source_ops_snapshot
from src.storage import DatabaseManager


class PlatformLocalMarketSourceOpsV11TestCase(unittest.TestCase):
    def test_ops_snapshot_lists_market_lanes_priority_and_source_health(self) -> None:
        health = MarketSourceHealthRegistry(failure_threshold=2, cooling_seconds=60)
        health.record_timeout("hk_realtime", elapsed_ms=4100)
        health.record_timeout("hk_realtime", elapsed_ms=4200)

        snapshot = build_market_source_ops_snapshot(source_health=health)

        self.assertFalse(snapshot["ai_used"])
        self.assertEqual(snapshot["mode"], "local_only")
        self.assertEqual([lane["market"] for lane in snapshot["lanes"]], ["cn", "us", "hk", "crypto"])
        hk_lane = next(lane for lane in snapshot["lanes"] if lane["market"] == "hk")
        self.assertEqual(hk_lane["route_lane"], "hk_market_data")
        self.assertEqual(hk_lane["quote_sources"][0]["source"], "hk_realtime")
        self.assertEqual(hk_lane["quote_sources"][0]["priority_rank"], 1)
        self.assertEqual(hk_lane["quote_sources"][0]["status"], "cooling_down")
        self.assertGreater(hk_lane["quote_sources"][0]["cooldown_remaining_sec"], 0)
        self.assertEqual(hk_lane["history_sources"][0]["priority_rank"], 1)
        self.assertEqual(snapshot["cache"]["mode"], "local_json")

    def test_source_health_endpoint_is_read_only_and_never_invokes_live_market_fetches(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
            db_path = Path(temp_dir) / "v11-source-ops.sqlite"
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
                },
                clear=False,
            ):
                with patch(
                    "src.services.stock_service.StockService.get_realtime_quote",
                    side_effect=AssertionError("source health endpoint must not fetch live quotes"),
                ), patch(
                    "src.services.stock_service.StockService.get_history_data",
                    side_effect=AssertionError("source health endpoint must not fetch live history"),
                ):
                    client = TestClient(create_app(static_dir=static_dir))
                    register = client.post(
                        "/api/v1/platform/register",
                        json={"email": "v11-source-ops@example.com", "password": "password123"},
                    )
                    self.assertEqual(register.status_code, 200)
                    response = client.get("/api/v1/stocks/sources/health")
                    client.close()

            DatabaseManager.reset_instance()
            Config.reset_instance()

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertFalse(body["ai_used"])
        self.assertEqual(body["mode"], "local_only")
        self.assertEqual(len(body["lanes"]), 4)
        self.assertIn("us_realtime", {item["source"] for lane in body["lanes"] for item in lane["quote_sources"]})

    def test_v11_verifier_file_and_marker_are_visible(self) -> None:
        root = Path(__file__).resolve().parents[1]
        verifier = root / "scripts" / "verify_platform_local_market_source_ops_v11.py"

        self.assertTrue(verifier.exists(), "V11 verifier script is missing")
        self.assertIsNotNone(importlib.util.find_spec("scripts.verify_platform_local_market_source_ops_v11"))

        from scripts.verify_platform_local_market_source_ops_v11 import OK_MARKER

        self.assertEqual(OK_MARKER, "DSA_PLATFORM_LOCAL_MARKET_SOURCE_OPS_V11_OK")

    def test_v11_evaluator_requires_local_source_priority_diagnostics(self) -> None:
        from scripts.verify_platform_local_market_source_ops_v11 import evaluate_market_source_ops_payload

        missing = evaluate_market_source_ops_payload({"mode": "local_only", "ai_used": False, "lanes": []})
        valid = evaluate_market_source_ops_payload(
            {
                "mode": "local_only",
                "ai_used": False,
                "cache": {"mode": "local_json"},
                "lanes": [
                    {
                        "market": "cn",
                        "quote_sources": [{"source": "a_share_realtime", "priority_rank": 1, "status": "ok"}],
                        "history_sources": [{"source": "a_share_history", "priority_rank": 1, "status": "ok"}],
                    },
                    {
                        "market": "us",
                        "quote_sources": [{"source": "us_realtime", "priority_rank": 1, "status": "ok"}],
                        "history_sources": [{"source": "us_history", "priority_rank": 1, "status": "ok"}],
                    },
                    {
                        "market": "hk",
                        "quote_sources": [{"source": "hk_realtime", "priority_rank": 1, "status": "cooling_down"}],
                        "history_sources": [{"source": "hk_history", "priority_rank": 1, "status": "ok"}],
                    },
                    {
                        "market": "crypto",
                        "quote_sources": [{"source": "crypto_yahoo_chart", "priority_rank": 1, "status": "ok"}],
                        "history_sources": [{"source": "crypto_yahoo_chart", "priority_rank": 1, "status": "ok"}],
                    },
                ],
            }
        )

        self.assertIn("lanes_missing", missing)
        self.assertEqual(valid, [])


if __name__ == "__main__":
    unittest.main()
