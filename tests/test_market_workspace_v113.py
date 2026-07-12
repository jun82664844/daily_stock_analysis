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


def _snapshot(symbol: str, *, market: str = "us", change: float = 1.25) -> dict:
    return {
        "stock_code": symbol,
        "stock_name": {"AAPL": "Apple Inc.", "600519.SH": "贵州茅台", "0700.HK": "腾讯控股"}.get(symbol, symbol),
        "market": market,
        "quote": {
            "current_price": 100.0,
            "change_percent": change,
            "volume": 1000000,
            "amount": 2000000,
            "update_time": "2026-07-12T09:30:00Z",
            "source": f"{market}_unit_quote",
            "freshness": "fresh",
        },
        "profile": {"sector": "Technology", "industry": "Software", "currency": "USD", "market_cap": 1_000_000},
        "indicators": {"ma5": 98.0, "ma10": 97.0, "ma20": 95.0, "price_change_20d": 4.2},
        "trend": {"points": [{"date": "2026-07-11", "close": 99.0, "volume": 900000}]},
        "intelligence": {"items": []},
        "warnings": [],
        "degradation": {"status": "ok"},
        "ai_used": False,
    }


class MarketWorkspaceServiceV113TestCase(unittest.TestCase):
    def test_quote_card_skips_history_and_profile_fetches(self) -> None:
        from src.services.basic_query_service import BasicQueryService
        from src.services.market_data_cache import MarketDataCache

        class QuoteOnlyStockService:
            def get_realtime_quote(self, code: str) -> dict:
                return {
                    "code": code,
                    "stock_name": "腾讯控股",
                    "current_price": 500.0,
                    "change_percent": 1.2,
                    "source": "unit_quote",
                }

            def get_history_data(self, *args, **kwargs):
                raise AssertionError("overview quote card must not fetch history")

            def get_basic_company_profile(self, *args, **kwargs):
                raise AssertionError("overview quote card must not fetch profile")

        service = BasicQueryService(
            stock_service=QuoteOnlyStockService(),
            cache=MarketDataCache(default_ttl_seconds=60),
            fetch_timeout_seconds=0.2,
        )

        card = service.get_quote_card("0700.HK")

        self.assertEqual(card["stock_code"], "HK00700")
        self.assertEqual(card["stock_name"], "腾讯控股")
        self.assertEqual(card["quote"]["current_price"], 500.0)
        self.assertEqual(card["profile"], {})
        self.assertFalse(card["ai_used"])

    def test_overview_calls_only_selected_market_and_uses_cache(self) -> None:
        from src.services.market_workspace_service import MarketWorkspaceService

        calls: list[str] = []

        def loader(symbol: str) -> dict:
            calls.append(symbol)
            return _snapshot(symbol)

        service = MarketWorkspaceService(
            snapshot_loader=loader,
            market_symbols={"cn": ["600519.SH"], "hk": ["0700.HK"], "us": ["AAPL"]},
            cache_ttl_seconds=60,
        )

        first = service.get_overview("us")
        second = service.get_overview("us")

        self.assertEqual(calls, ["AAPL"])
        self.assertFalse(first["cache"]["hit"])
        self.assertTrue(second["cache"]["hit"])
        self.assertEqual(first["market"], "us")
        self.assertFalse(first["ai_used"])

    def test_news_failure_keeps_market_data_and_reports_degradation(self) -> None:
        from src.services.market_workspace_service import MarketWorkspaceService

        def failed_news(_: str) -> list[dict]:
            raise TimeoutError("provider timed out")

        service = MarketWorkspaceService(
            snapshot_loader=lambda symbol: _snapshot(symbol),
            news_loader=failed_news,
            market_symbols={"cn": ["600519.SH"], "hk": ["0700.HK"], "us": ["AAPL"]},
        )

        overview = service.get_overview("us")

        self.assertEqual(len(overview["movers"]), 1)
        self.assertIn("market_news_unavailable", overview["warnings"])
        self.assertEqual(overview["sources"][1]["status"], "unavailable")

    def test_market_symbols_are_loaded_with_bounded_parallelism(self) -> None:
        from src.services.market_workspace_service import MarketWorkspaceService

        def delayed_loader(symbol: str) -> dict:
            time.sleep(0.1)
            return _snapshot(symbol)

        service = MarketWorkspaceService(
            snapshot_loader=delayed_loader,
            market_symbols={"cn": [], "hk": [], "us": ["AAPL", "MSFT", "NVDA", "TSLA"]},
        )

        started = time.perf_counter()
        overview = service.get_overview("us")
        elapsed = time.perf_counter() - started

        self.assertEqual(len(overview["movers"]), 4)
        self.assertLess(elapsed, 0.25)

    def test_overview_returns_at_deadline_when_a_market_source_stalls(self) -> None:
        from src.services.market_workspace_service import MarketWorkspaceService

        def stalled_loader(symbol: str) -> dict:
            if symbol == "TSLA":
                time.sleep(0.8)
            return _snapshot(symbol)

        service = MarketWorkspaceService(
            snapshot_loader=stalled_loader,
            market_symbols={"cn": [], "hk": [], "us": ["AAPL", "TSLA"]},
            overview_timeout_seconds=0.1,
        )

        started = time.perf_counter()
        overview = service.get_overview("us")
        elapsed = time.perf_counter() - started

        self.assertLess(elapsed, 0.3)
        self.assertEqual([item["symbol"] for item in overview["movers"]], ["AAPL"])
        self.assertIn("market_symbol_timeout:TSLA", overview["warnings"])

    def test_symbol_workspace_keeps_quote_history_profile_and_no_ai_boundary(self) -> None:
        from src.services.market_workspace_service import MarketWorkspaceService

        body = MarketWorkspaceService(snapshot_loader=lambda symbol: _snapshot(symbol)).get_symbol("AAPL")

        self.assertEqual(body["symbol"], "AAPL")
        self.assertEqual(body["quote"]["current_price"], 100.0)
        self.assertEqual(body["history"][0]["close"], 99.0)
        self.assertEqual(body["profile"]["sector"], "Technology")
        self.assertFalse(body["ai_used"])
        self.assertTrue(body["informational_only"])
        self.assertNotIn("raw", body)


class MarketWorkspaceEndpointV113TestCase(unittest.TestCase):
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

    def test_market_workspace_is_disabled_by_default(self) -> None:
        with patch.dict(os.environ, {
            "DATABASE_PATH": str(Path(self.temp_dir.name) / "disabled.sqlite"),
            "PLATFORM_MARKET_WORKSPACE_V113_ENABLED": "false",
        }, clear=False):
            client = TestClient(create_app(static_dir=self.static_dir))
            response = client.get("/api/v1/market-workspace/overview?market=us")
            client.close()

        self.assertEqual(response.status_code, 404)

    def test_public_search_is_anonymous_but_daily_brief_requires_login(self) -> None:
        env = {
            "DATABASE_PATH": str(Path(self.temp_dir.name) / "public.sqlite"),
            "PLATFORM_MARKET_WORKSPACE_V113_ENABLED": "true",
            "PLATFORM_USER_AUTH_ENABLED": "true",
            "ADMIN_AUTH_ENABLED": "true",
        }
        with patch.dict(os.environ, env, clear=False):
            client = TestClient(create_app(static_dir=self.static_dir))
            search = client.get("/api/v1/market-workspace/search", params={"q": "AAPL"})
            brief = client.get("/api/v1/market-workspace/daily-brief")
            client.close()

        self.assertEqual(search.status_code, 200)
        self.assertEqual(search.json()["items"][0]["symbol"], "AAPL")
        self.assertEqual(brief.status_code, 401)


if __name__ == "__main__":
    unittest.main()
