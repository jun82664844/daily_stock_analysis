# -*- coding: utf-8 -*-
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from api.app import create_app
from src.config import Config
from src.services.market_data_cache import MarketDataCache
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

        with patch("src.services.stock_service.StockService.get_realtime_quote", return_value=quote), \
             patch("src.services.stock_service.StockService.get_history_data", return_value=history), \
             patch("src.services.analysis_service.AnalysisService") as analysis_service:
            response = self.client.get("/api/v1/stocks/AAPL/snapshot")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["stock_code"], "AAPL")
        self.assertEqual(body["stock_name"], "Apple Inc.")
        self.assertEqual(body["market"], "us")
        self.assertEqual(body["quote"]["current_price"], 200.0)
        self.assertEqual(body["quote"]["change_percent"], 1.5)
        self.assertEqual(body["indicators"]["ma5"], 199.0)
        self.assertEqual(body["indicators"]["ma20"], 191.5)
        self.assertFalse(body["ai_used"])
        analysis_service.assert_not_called()

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
