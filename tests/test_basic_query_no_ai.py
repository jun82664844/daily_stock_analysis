# -*- coding: utf-8 -*-
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from fastapi.testclient import TestClient

from api.app import create_app
from src.config import Config
from src.services.basic_query_service import BasicQueryService
from src.services.market_data_cache import MarketDataCache
from src.services.stock_service import StockService
from src.storage import DatabaseManager


class BasicQueryNoAiTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.db_path = Path(self.temp_dir.name) / "basic-query.sqlite"
        self.static_dir = Path(self.temp_dir.name) / "static"
        self.static_dir.mkdir()
        (self.static_dir / "index.html").write_text("<html>ok</html>", encoding="utf-8")
        DatabaseManager.reset_instance()
        Config.reset_instance()
        self.env_patch = patch.dict(
            os.environ,
            {
                "DATABASE_PATH": str(self.db_path),
                "ADMIN_AUTH_ENABLED": "true",
                "PLATFORM_USER_AUTH_ENABLED": "true",
            },
            clear=False,
        )
        self.env_patch.start()
        self.cache_patch = patch(
            "src.services.basic_query_service.default_persistent_market_data_cache",
            MarketDataCache(default_ttl_seconds=60),
        )
        self.cache_patch.start()
        self.client = TestClient(create_app(static_dir=self.static_dir))
        register = self.client.post(
            "/api/v1/platform/register",
            json={"email": "basic@example.com", "password": "password123"},
        )
        self.assertEqual(register.status_code, 200)

    def tearDown(self) -> None:
        self.client.close()
        self.cache_patch.stop()
        self.env_patch.stop()
        DatabaseManager.reset_instance()
        Config.reset_instance()
        self.temp_dir.cleanup()

    def test_snapshot_returns_market_data_without_analysis_service(self) -> None:
        quote = {
            "stock_code": "AAPL",
            "stock_name": "Apple Inc.",
            "current_price": 200.0,
            "change_percent": 1.5,
            "volume": 1000,
            "amount": 200000.0,
            "update_time": "2026-07-01T09:30:00",
        }
        history = {
            "stock_code": "AAPL",
            "stock_name": "Apple Inc.",
            "period": "daily",
            "data": [
                {"date": f"2026-06-{day:02d}", "close": 180.0 + day, "volume": 1000 + day}
                for day in range(1, 22)
            ],
        }
        profile = {
            "stock_code": "AAPL",
            "company_name": "Apple Inc.",
            "sector": "Technology",
            "industry": "Consumer Electronics",
            "market_cap": 4500000000000,
            "pe_ratio": 31.2,
            "source": "unit_profile",
        }

        with patch("src.services.stock_service.StockService.get_realtime_quote", return_value=quote), \
             patch("src.services.stock_service.StockService.get_history_data", return_value=history), \
             patch("src.services.stock_service.StockService.get_basic_company_profile", return_value=profile), \
             patch("src.services.analysis_service.AnalysisService") as analysis_service:
            response = self.client.get("/api/v1/stocks/AAPL/snapshot")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["stock_code"], "AAPL")
        self.assertEqual(body["stock_name"], "Apple Inc.")
        self.assertEqual(body["market"], "us")
        self.assertEqual(body["quote"]["current_price"], 200.0)
        self.assertEqual(body["quote"]["change_percent"], 1.5)
        self.assertEqual(body["profile"]["sector"], "Technology")
        self.assertEqual(body["profile"]["industry"], "Consumer Electronics")
        self.assertEqual(body["profile"]["market_cap"], 4500000000000)
        self.assertEqual(body["profile"]["pe_ratio"], 31.2)
        self.assertEqual(body["indicators"]["ma5"], 199.0)
        self.assertEqual(body["indicators"]["ma20"], 191.5)
        self.assertFalse(body["ai_used"])
        analysis_service.assert_not_called()

    def test_service_snapshot_includes_no_ai_company_profile_when_available(self) -> None:
        class RichStockService:
            def get_realtime_quote(self, stock_code: str):
                return {
                    "stock_code": stock_code,
                    "stock_name": "Apple Inc.",
                    "current_price": 200.0,
                    "change_percent": 1.5,
                    "market_cap": 4500000000000,
                    "pe_ratio": 31.2,
                    "source": "unit_quote",
                }

            def get_history_data(self, stock_code: str, **_kwargs):
                return {
                    "stock_code": stock_code,
                    "stock_name": "Apple Inc.",
                    "source": "unit_history",
                    "data": [
                        {"date": f"2026-06-{day:02d}", "close": 180.0 + day, "volume": 1000 + day}
                        for day in range(1, 22)
                    ],
                }

            def get_basic_company_profile(self, stock_code: str):
                return {
                    "stock_code": stock_code,
                    "company_name": "Apple Inc.",
                    "sector": "Technology",
                    "industry": "Consumer Electronics",
                    "exchange": "NASDAQ",
                    "currency": "USD",
                    "country": "United States",
                    "market_cap": 4500000000000,
                    "pe_ratio": 31.2,
                    "dividend_yield": 0.5,
                    "source": "unit_profile",
                }

        snapshot = BasicQueryService(
            stock_service=RichStockService(),
            cache=MarketDataCache(default_ttl_seconds=60),
        ).get_snapshot("AAPL")

        self.assertFalse(snapshot["ai_used"])
        self.assertIn("profile", snapshot)
        self.assertEqual(snapshot["profile"]["company_name"], "Apple Inc.")
        self.assertEqual(snapshot["profile"]["sector"], "Technology")
        self.assertEqual(snapshot["profile"]["industry"], "Consumer Electronics")
        self.assertEqual(snapshot["profile"]["market_cap"], 4500000000000)
        self.assertEqual(snapshot["profile"]["pe_ratio"], 31.2)
        self.assertEqual(snapshot["profile"]["source"], "unit_profile")
        self.assertEqual(snapshot["diagnostics"]["cache"]["profile"], "miss")
        self.assertEqual(snapshot["diagnostics"]["sources"]["profile"], "unit_profile")

    def test_yfinance_profile_keeps_dividend_yield_percent_units(self) -> None:
        class FakeTicker:
            def get_info(self):
                return {
                    "longName": "Apple Inc.",
                    "sector": "Technology",
                    "industry": "Consumer Electronics",
                    "marketCap": 4500000000000,
                    "dividendYield": 0.35,
                }

        fake_yfinance = SimpleNamespace(Ticker=lambda _symbol: FakeTicker())
        with patch.dict("sys.modules", {"yfinance": fake_yfinance}):
            profile = StockService().get_basic_company_profile("AAPL")

        self.assertIsNotNone(profile)
        self.assertEqual(profile["dividend_yield"], 0.35)

    def test_snapshot_is_public_without_platform_login(self) -> None:
        quote = {
            "stock_code": "AAPL",
            "stock_name": "Apple Inc.",
            "current_price": 200.0,
            "change_percent": 1.5,
            "volume": 1000,
            "amount": 200000.0,
            "update_time": "2026-07-01T09:30:00",
        }
        history = {
            "stock_code": "AAPL",
            "stock_name": "Apple Inc.",
            "period": "daily",
            "data": [
                {"date": f"2026-06-{day:02d}", "close": 180.0 + day, "volume": 1000 + day}
                for day in range(1, 22)
            ],
        }

        anonymous_client = TestClient(create_app(static_dir=self.static_dir))
        try:
            with patch("src.services.stock_service.StockService.get_realtime_quote", return_value=quote), \
                 patch("src.services.stock_service.StockService.get_history_data", return_value=history), \
                 patch("src.services.stock_service.StockService.get_basic_company_profile", return_value=None), \
                 patch("src.services.analysis_service.AnalysisService") as analysis_service:
                response = anonymous_client.get("/api/v1/stocks/AAPL/snapshot")
        finally:
            anonymous_client.close()

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["stock_code"], "AAPL")
        self.assertFalse(body["ai_used"])
        analysis_service.assert_not_called()


if __name__ == "__main__":
    unittest.main()
