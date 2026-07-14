# -*- coding: utf-8 -*-
from __future__ import annotations

import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from api.app import create_app
from src.config import Config
from src.storage import DatabaseManager


def _security(symbol: str, turnover: float | None, change: float | None) -> dict:
    return {
        "symbol": symbol, "name": symbol, "market": "us", "currency": "USD",
        "current_price": 100, "change_percent": change, "turnover": turnover,
        "source_state": {"source": "unit_quote", "status": "fresh", "observed_at": "2026-07-13T01:30:00Z"},
    }


def _overview(market: str) -> dict:
    items = [_security(f"{market}-LOW", 10, -5), _security(f"{market}-HIGH", 30, 1), _security(f"{market}-NONE", None, 9)]
    for item in items:
        item["market"] = market
    return {
        "market": market, "session_state": "unknown", "indices": items[:1], "movers": items,
        "headlines": [{
            "title": f"{market.upper()} market bulletin",
            "summary": "Objective market information.",
            "publisher": "Unit News",
            "published_at": "2026-07-13T01:25:00Z",
            "url": "https://example.com/market-bulletin",
            "source_state": {
                "source": "unit_news",
                "status": "fresh",
                "observed_at": "2026-07-13T01:25:00Z",
            },
        }],
        "sources": [{"source": f"{market}_snapshot", "status": "fresh"}], "warnings": [],
    }


class _Workspace:
    def __init__(self, *, failed: str | None = None, delay: float = 0) -> None:
        self.failed = failed
        self.delay = delay
        self.calls: list[str] = []

    def get_overview(self, market: str) -> dict:
        self.calls.append(market)
        if self.delay:
            time.sleep(self.delay)
        if market == self.failed:
            raise RuntimeError("provider unavailable")
        return _overview(market)


class PublicMarketHomeServiceV116TestCase(unittest.TestCase):
    def test_workspace_attention_symbols_are_configurable_and_deduplicated(self) -> None:
        from src.services.market_workspace_service import MarketWorkspaceService

        with patch.dict(os.environ, {
            "PLATFORM_PUBLIC_MARKET_HOME_SYMBOLS_US": "AAPL,MSFT,AAPL",
        }, clear=False):
            service = MarketWorkspaceService(snapshot_loader=lambda symbol: {"stock_code": symbol})
        self.assertEqual(service.market_symbols["us"], ("AAPL", "MSFT"))

    def test_builds_fixed_three_market_order_without_ai(self) -> None:
        from src.services.public_market_home_service import PublicMarketHomeService

        service = PublicMarketHomeService(_Workspace(), timeout_seconds=1)
        body = service.build()

        self.assertEqual([item["market"] for item in body["markets"]], ["cn", "hk", "us"])
        self.assertFalse(body["ai_used"])
        self.assertTrue(body["informational_only"])
        self.assertEqual(body["markets"][0]["ranking_scope"], "configured_universe")
        self.assertEqual(body["markets"][0]["display_mode"], "latest_available")
        self.assertEqual([item["symbol"] for item in body["markets"][0]["attention"]], ["cn-HIGH", "cn-LOW", "cn-NONE"])
        self.assertEqual(body["markets"][0]["headlines"][0]["title"], "CN market bulletin")

    def test_one_market_failure_does_not_blank_other_markets(self) -> None:
        from src.services.public_market_home_service import PublicMarketHomeService

        body = PublicMarketHomeService(_Workspace(failed="hk"), timeout_seconds=1).build()
        self.assertTrue(body["markets"][0]["attention"])
        self.assertEqual(body["markets"][1]["warnings"], ["market_home_unavailable"])
        self.assertEqual(body["markets"][1]["headlines"], [])
        self.assertTrue(body["markets"][2]["attention"])

    def test_three_markets_load_concurrently_under_one_deadline(self) -> None:
        from src.services.public_market_home_service import PublicMarketHomeService

        started = time.perf_counter()
        body = PublicMarketHomeService(_Workspace(delay=0.1), timeout_seconds=0.3).build()
        elapsed = time.perf_counter() - started
        self.assertLess(elapsed, 0.24)
        self.assertTrue(all(item["attention"] for item in body["markets"]))


class PublicMarketHomeEndpointV116TestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.static_dir = Path(self.temp_dir.name) / "static"
        self.static_dir.mkdir()
        (self.static_dir / "index.html").write_text("<html>ok</html>", encoding="utf-8")
        DatabaseManager.reset_instance()
        Config.reset_instance()

    def tearDown(self) -> None:
        DatabaseManager.reset_instance()
        Config.reset_instance()
        self.temp_dir.cleanup()

    def test_home_is_public_when_both_feature_flags_are_enabled(self) -> None:
        env = {
            "DATABASE_PATH": str(Path(self.temp_dir.name) / "public-home.sqlite"),
            "PLATFORM_MARKET_WORKSPACE_V113_ENABLED": "true",
            "PLATFORM_PUBLIC_MARKET_HOME_V116_ENABLED": "true",
            "PLATFORM_USER_AUTH_ENABLED": "true",
            "ADMIN_AUTH_ENABLED": "true",
        }
        with patch.dict(os.environ, env, clear=False), patch(
            "api.v1.endpoints.market_workspace._public_home_service.build",
            return_value={"as_of": "2026-07-13T01:30:00Z", "markets": [], "ai_used": False, "informational_only": True},
        ):
            client = TestClient(create_app(static_dir=self.static_dir))
            response = client.get("/api/v1/market-workspace/home")
            client.close()
        self.assertEqual(response.status_code, 200)

    def test_home_is_404_when_v116_is_disabled(self) -> None:
        with patch.dict(os.environ, {
            "DATABASE_PATH": str(Path(self.temp_dir.name) / "disabled-home.sqlite"),
            "PLATFORM_MARKET_WORKSPACE_V113_ENABLED": "true",
            "PLATFORM_PUBLIC_MARKET_HOME_V116_ENABLED": "false",
        }, clear=False):
            client = TestClient(create_app(static_dir=self.static_dir))
            response = client.get("/api/v1/market-workspace/home")
            client.close()
        self.assertEqual(response.status_code, 404)


if __name__ == "__main__":
    unittest.main()
