# -*- coding: utf-8 -*-
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from api.app import create_app
from src.config import Config
from src.platform_accounts import PlatformAccountService
from src.storage import DatabaseManager


def _snapshot(code: str, *, market: str, lane: str, price: float, degraded: bool = False) -> dict:
    return {
        "stock_code": code,
        "stock_name": f"{code} name",
        "market": market,
        "quote": {
            "current_price": price,
            "change_percent": 1.23,
            "source": "unit-test",
            "freshness": "fresh",
        },
        "indicators": {"ma5": price - 1, "volume_price_signal": "neutral"},
        "route": {
            "input_code": code,
            "normalized_code": code,
            "market": market,
            "channel": market,
            "data_source_lane": lane,
            "ai_required": False,
        },
        "warnings": [{"code": "missing_history", "severity": "warning", "message": "missing"}] if degraded else [],
        "degradation": {
            "status": "degraded" if degraded else "ok",
            "severity": "warning" if degraded else "info",
            "message": "degraded" if degraded else "Market data ready",
        },
        "diagnostics": {"route_lane": lane, "cache": {"quote": "hit"}, "fallback": {"quote": "cache"}},
        "ai_used": False,
    }


class PlatformLocalWatchlistV17TestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.db_path = os.path.join(self.temp_dir.name, "platform-watchlist-v17.sqlite")
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

    def _register(self, email: str) -> int:
        response = self.client.post(
            "/api/v1/platform/register",
            json={"email": email, "password": "password123"},
        )
        self.assertEqual(response.status_code, 200)
        return int(response.json()["user"]["id"])

    def test_platform_watchlist_is_private_and_refreshes_multi_market_without_ai(self) -> None:
        user_a = self._register("watch-a@example.com")
        for code in ("600519", "AAPL", "HK00700", "BTC-USD"):
            response = self.client.post("/api/v1/platform/watchlist", json={"stock_code": code})
            self.assertEqual(response.status_code, 200)

        body = self.client.get("/api/v1/platform/watchlist").json()
        self.assertEqual(body["user_id"], user_a)
        self.assertEqual([item["stock_code"] for item in body["items"]], ["600519", "AAPL", "HK00700", "BTC-USD"])
        self.assertEqual({item["market"] for item in body["items"]}, {"cn", "us", "hk", "crypto"})
        self.assertFalse(body["ai_used"])

        snapshots = {
            "600519": _snapshot("600519", market="cn", lane="a_share_market_data", price=1680.0),
            "AAPL": _snapshot("AAPL", market="us", lane="us_market_data", price=210.0),
            "HK00700": _snapshot("HK00700", market="hk", lane="hk_market_data", price=380.0, degraded=True),
            "BTC-USD": _snapshot("BTC-USD", market="crypto", lane="crypto_market_data", price=65000.0),
        }
        with patch("src.platform_watchlist.BasicQueryService.get_snapshot", side_effect=lambda code: snapshots[code]):
            refresh = self.client.post("/api/v1/platform/watchlist/refresh")

        self.assertEqual(refresh.status_code, 200)
        summary = refresh.json()
        self.assertEqual(summary["requested"], 4)
        self.assertEqual(summary["refreshed"], 4)
        self.assertEqual(summary["degraded"], 1)
        self.assertFalse(summary["ai_used"])
        lanes = {item["stock_code"]: item["route_lane"] for item in summary["items"]}
        self.assertEqual(lanes["600519"], "a_share_market_data")
        self.assertEqual(lanes["AAPL"], "us_market_data")
        self.assertEqual(lanes["HK00700"], "hk_market_data")
        self.assertEqual(lanes["BTC-USD"], "crypto_market_data")
        self.assertEqual(PlatformAccountService().get_feature_quota_status(user_a, "ai_quick")["used"], 0)
        self.assertNotIn("sk-", str(summary))

        self._register("watch-b@example.com")
        isolated = self.client.get("/api/v1/platform/watchlist")
        self.assertEqual(isolated.status_code, 200)
        self.assertEqual(isolated.json()["items"], [])

    def test_platform_watchlist_requires_login_and_supports_remove(self) -> None:
        unauthenticated = TestClient(create_app(static_dir=self.static_dir))
        try:
            self.assertEqual(unauthenticated.get("/api/v1/platform/watchlist").status_code, 401)
        finally:
            unauthenticated.close()

        self._register("watch-remove@example.com")
        add = self.client.post("/api/v1/platform/watchlist", json={"stock_code": "HK00700"})
        self.assertEqual(add.status_code, 200)
        remove = self.client.delete("/api/v1/platform/watchlist/HK00700")
        self.assertEqual(remove.status_code, 200)
        self.assertEqual(remove.json()["items"], [])

    def test_watchlist_refresh_does_not_hide_unexpected_ai_usage(self) -> None:
        self._register("watch-ai-guard@example.com")
        add = self.client.post("/api/v1/platform/watchlist", json={"stock_code": "AAPL"})
        self.assertEqual(add.status_code, 200)
        snapshot = _snapshot("AAPL", market="us", lane="us_market_data", price=210.0)
        snapshot["ai_used"] = True

        with patch("src.platform_watchlist.BasicQueryService.get_snapshot", return_value=snapshot):
            refresh = self.client.post("/api/v1/platform/watchlist/refresh")

        self.assertEqual(refresh.status_code, 200)
        body = refresh.json()
        self.assertTrue(body["ai_used"])
        self.assertTrue(body["items"][0]["ai_used"])


if __name__ == "__main__":
    unittest.main()
