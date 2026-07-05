# -*- coding: utf-8 -*-
import os
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from api.app import create_app
from src.config import Config
from src.platform_accounts import PlatformAccountService
from src.services.basic_query_service import BasicQueryService
from src.services.market_data_cache import MarketDataCache
from src.storage import DatabaseManager


def _history_rows(count: int = 24) -> list[dict]:
    return [
        {
            "date": f"2026-06-{day:02d}",
            "open": 90.0 + day,
            "high": 92.0 + day,
            "low": 89.0 + day,
            "close": 91.0 + day,
            "volume": 1000 + day * 10,
        }
        for day in range(1, count + 1)
    ]


def _quote(code: str, *, name: str | None = None, source: str = "unit-test") -> dict:
    return {
        "stock_code": code,
        "stock_name": name or code,
        "current_price": 120.0,
        "change_percent": 1.2,
        "volume": 123456,
        "amount": 456789.0,
        "source": source,
        "update_time": "2026-07-02T09:30:00",
    }


def _analysis_service_result(stock_code: str = "AAPL", *, diagnostics: dict | None = None):
    return SimpleNamespace(
        last_error=None,
        analyze_stock=lambda **kwargs: {
            "stock_code": stock_code,
            "stock_name": "Apple Inc.",
            "diagnostic_summary": diagnostics,
            "report": {
                "meta": {"stock_code": stock_code, "report_language": "zh"},
                "summary": {"analysis_summary": "ok"},
                "strategy": {},
                "details": {},
            },
        },
    )


class PlatformQueryQualityV4TestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.db_path = os.path.join(self.temp_dir.name, "query-quality-v4.sqlite")
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
        self.cache_patch = patch(
            "src.services.basic_query_service.default_persistent_market_data_cache",
            MarketDataCache(default_ttl_seconds=60),
        )
        self.cache_patch.start()
        self.client = TestClient(create_app(static_dir=self.static_dir))

    def tearDown(self) -> None:
        self.client.close()
        self.cache_patch.stop()
        self.env_patch.stop()
        DatabaseManager.reset_instance()
        Config.reset_instance()
        self.temp_dir.cleanup()

    def _register(self, email: str = "quality@example.com") -> int:
        response = self.client.post(
            "/api/v1/platform/register",
            json={"email": email, "password": "password123"},
        )
        self.assertEqual(response.status_code, 200)
        return int(response.json()["user"]["id"])

    def test_basic_query_routes_a_share_us_hk_and_crypto_without_ai(self) -> None:
        stock_service = MagicMock()
        stock_service.get_realtime_quote.side_effect = lambda code: _quote(code)
        stock_service.get_history_data.side_effect = lambda code, **_: {
            "stock_code": code,
            "stock_name": code,
            "data": _history_rows(),
        }
        service = BasicQueryService(
            stock_service=stock_service,
            cache=MarketDataCache(default_ttl_seconds=60),
        )

        cn = service.get_snapshot("600519")
        us = service.get_snapshot("AAPL")
        hk = service.get_snapshot("00700.HK")
        crypto = service.get_snapshot("BTC-USD")

        self.assertEqual(cn["market"], "cn")
        self.assertEqual(cn["route"]["channel"], "a_share")
        self.assertEqual(cn["route"]["data_source_lane"], "a_share_market_data")
        self.assertEqual(cn["intelligence"]["market_brief"]["market"], "cn")
        self.assertIn("A-share", cn["intelligence"]["market_brief"]["title"])
        self.assertIn("000300.SH", {item["symbol"] for item in cn["intelligence"]["comparison_targets"]})
        self.assertEqual(us["market"], "us")
        self.assertEqual(us["route"]["channel"], "us_equity")
        self.assertEqual(us["route"]["data_source_lane"], "us_market_data")
        self.assertEqual(us["intelligence"]["market_brief"]["market"], "us")
        self.assertIn("US equity", us["intelligence"]["market_brief"]["title"])
        self.assertEqual(hk["market"], "hk")
        self.assertEqual(hk["route"]["channel"], "hk_equity")
        self.assertEqual(hk["route"]["data_source_lane"], "hk_market_data")
        self.assertEqual(hk["intelligence"]["market_brief"]["market"], "hk")
        self.assertIn("Hong Kong", hk["intelligence"]["market_brief"]["title"])
        self.assertIn("^HSI", {item["symbol"] for item in hk["intelligence"]["comparison_targets"]})
        self.assertEqual(crypto["market"], "crypto")
        self.assertEqual(crypto["stock_code"], "BTC-USD")
        self.assertEqual(crypto["route"]["channel"], "crypto_spot")
        self.assertEqual(crypto["route"]["data_source_lane"], "crypto_market_data")
        self.assertEqual(crypto["intelligence"]["market_brief"]["market"], "crypto")
        self.assertIn("Crypto", crypto["intelligence"]["market_brief"]["title"])
        self.assertIn("not apply", crypto["intelligence"]["items"][2]["summary"])
        self.assertFalse(cn["ai_used"])
        self.assertFalse(us["ai_used"])
        self.assertFalse(crypto["route"]["ai_required"])
        self.assertEqual(crypto["degradation"]["status"], "ok")
        self.assertIn("volume_price_signal", crypto["indicators"])

    def test_stale_and_missing_quotes_return_degradation_warnings(self) -> None:
        stock_service = MagicMock()
        stock_service.get_history_data.return_value = {
            "stock_code": "AAPL",
            "stock_name": "Apple Inc.",
            "data": _history_rows(),
        }
        stale_cache = MarketDataCache(default_ttl_seconds=0)
        stale_cache.set("quote:AAPL", _quote("AAPL", source="cache"), source="cache")
        time.sleep(0.01)
        stale_service = BasicQueryService(stock_service=stock_service, cache=stale_cache)

        stale = stale_service.get_snapshot("AAPL")

        self.assertEqual(stale["quote"]["freshness"], "stale")
        self.assertEqual(stale["degradation"]["status"], "degraded")
        self.assertTrue(any(warning["code"] == "stale_quote" for warning in stale["warnings"]))
        self.assertFalse(stale["ai_used"])

        missing_quote_service = MagicMock()
        missing_quote_service.get_realtime_quote.return_value = None
        missing_quote_service.get_history_data.return_value = {
            "stock_code": "AAPL",
            "stock_name": "Apple Inc.",
            "data": _history_rows(),
        }
        missing = BasicQueryService(
            stock_service=missing_quote_service,
            cache=MarketDataCache(default_ttl_seconds=60),
        ).get_snapshot("AAPL")

        self.assertEqual(missing["quote"]["freshness"], "unavailable")
        self.assertTrue(any(warning["code"] == "missing_quote" for warning in missing["warnings"]))
        self.assertIsNotNone(missing["indicators"]["ma20"])
        self.assertEqual(missing["degradation"]["status"], "degraded")

    def test_snapshot_endpoint_accepts_crypto_and_returns_degraded_payload_for_missing_quote(self) -> None:
        self._register("crypto-v4@example.com")
        fake_stock_service = MagicMock()
        fake_stock_service.get_realtime_quote.return_value = None
        fake_stock_service.get_history_data.return_value = {
            "stock_code": "BTC-USD",
            "stock_name": "Bitcoin",
            "data": _history_rows(),
        }

        with patch("src.services.basic_query_service.StockService", return_value=fake_stock_service):
            response = self.client.get("/api/v1/stocks/BTC-USD/snapshot")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["market"], "crypto")
        self.assertEqual(body["stock_code"], "BTC-USD")
        self.assertEqual(body["quote"]["freshness"], "unavailable")
        self.assertEqual(body["route"]["channel"], "crypto_spot")
        self.assertTrue(any(warning["code"] == "missing_quote" for warning in body["warnings"]))
        self.assertFalse(body["ai_used"])

    def test_quick_snapshot_does_not_consume_ai_quota_and_deep_modes_use_distinct_buckets(self) -> None:
        user_id = self._register("quota-v4@example.com")
        PlatformAccountService().set_user_plan(user_id, "pro")

        snapshot = {
            "stock_code": "AAPL",
            "stock_name": "Apple Inc.",
            "market": "us",
            "quote": {"current_price": 120.0, "source": "unit", "freshness": "fresh"},
            "indicators": {"ma5": 119.0, "ma20": 110.0, "volume_price_signal": "neutral"},
            "route": {
                "market": "us",
                "channel": "us_equity",
                "normalized_code": "AAPL",
                "data_source_lane": "us_market_data",
                "ai_required": False,
            },
            "warnings": [],
            "degradation": {"status": "ok", "severity": "info", "message": "Market data ready"},
            "ai_used": False,
        }
        with patch("src.services.basic_query_service.BasicQueryService.get_snapshot", return_value=snapshot):
            no_ai = self.client.get("/api/v1/stocks/AAPL/snapshot")
        self.assertEqual(no_ai.status_code, 200)
        self.assertEqual(PlatformAccountService().get_feature_quota_status(user_id, "ai_quick")["used"], 0)
        self.assertEqual(PlatformAccountService().get_feature_quota_status(user_id, "ai_deep")["used"], 0)

        key_response = self.client.post(
            "/api/v1/platform/api-keys",
            json={"provider": "deepseek", "apiKey": "sk-v4-user-secret"},
        )
        self.assertEqual(key_response.status_code, 200)

        with patch("src.services.analysis_service.AnalysisService", return_value=_analysis_service_result()), \
             patch("api.v1.endpoints.analysis._load_sync_fundamental_sources", return_value=(None, None)):
            platform_deep = self.client.post(
                "/api/v1/analysis/analyze",
                json={"stock_code": "AAPL", "async_mode": False, "analysisDepth": "deep"},
            )
            byok_deep = self.client.post(
                "/api/v1/analysis/analyze",
                json={
                    "stock_code": "AAPL",
                    "async_mode": False,
                    "analysisDepth": "deep",
                    "apiKeyMode": "user",
                },
            )
            local_quick = self.client.post(
                "/api/v1/analysis/analyze",
                json={
                    "stock_code": "AAPL",
                    "async_mode": False,
                    "analysisDepth": "fast",
                    "apiKeyMode": "local",
                },
            )

        self.assertEqual(platform_deep.status_code, 200)
        self.assertEqual(byok_deep.status_code, 200)
        self.assertEqual(local_quick.status_code, 200)
        self.assertEqual(PlatformAccountService().get_feature_quota_status(user_id, "ai_deep")["used"], 3)
        self.assertEqual(PlatformAccountService().get_feature_quota_status(user_id, "ai_deep_user_key")["used"], 1)
        self.assertEqual(PlatformAccountService().get_feature_quota_status(user_id, "ai_local")["used"], 1)

    def test_ai_timeout_and_public_search_degradation_are_clear(self) -> None:
        user_id = self._register("degrade-v4@example.com")
        PlatformAccountService().set_user_plan(user_id, "pro")

        timeout_service = MagicMock()
        timeout_service.analyze_stock.side_effect = TimeoutError("provider timed out")
        timeout_service.last_error = "provider timed out"
        with patch("src.services.analysis_service.AnalysisService", return_value=timeout_service):
            timeout_response = self.client.post(
                "/api/v1/analysis/analyze",
                json={"stock_code": "AAPL", "async_mode": False, "analysisDepth": "deep"},
            )

        self.assertEqual(timeout_response.status_code, 504)
        self.assertEqual(timeout_response.json()["error"], "ai_timeout")
        self.assertIn("timed out", timeout_response.json()["message"].lower())

        diagnostics = {
            "warnings": [{"code": "public_search_failed", "message": "Public search unavailable"}],
            "degradation_status": "degraded",
        }
        with patch("src.services.analysis_service.AnalysisService", return_value=_analysis_service_result(diagnostics=diagnostics)), \
             patch("api.v1.endpoints.analysis._load_sync_fundamental_sources", return_value=(None, None)):
            degraded_response = self.client.post(
                "/api/v1/analysis/analyze",
                json={"stock_code": "AAPL", "async_mode": False, "analysisDepth": "fast"},
            )

        self.assertEqual(degraded_response.status_code, 200)
        self.assertEqual(
            degraded_response.json()["diagnostic_summary"]["warnings"][0]["code"],
            "public_search_failed",
        )


if __name__ == "__main__":
    unittest.main()
