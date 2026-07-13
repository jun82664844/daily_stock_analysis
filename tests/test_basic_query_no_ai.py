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
            "source": "unit_history",
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
             patch("src.services.stock_service.StockService.get_public_history_data", return_value=history), \
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
        self.assertEqual(body["trend"]["window"], 20)
        self.assertEqual(body["trend"]["source"], "unit_history")
        self.assertEqual(len(body["trend"]["points"]), 20)
        self.assertEqual(body["trend"]["points"][0]["date"], "2026-06-02")
        self.assertEqual(body["trend"]["points"][-1]["close"], 201.0)
        self.assertEqual(body["trend"]["min_close"], 182.0)
        self.assertEqual(body["trend"]["max_close"], 201.0)
        self.assertEqual(body["trend"]["change_percent"], 10.4396)
        self.assertEqual(body["intelligence"]["mode"], "no_ai_low_cost")
        self.assertFalse(body["intelligence"]["ai_used"])
        intelligence_categories = {item["category"] for item in body["intelligence"]["items"]}
        self.assertEqual(intelligence_categories, {"news", "announcements", "financials"})
        watch_categories = {item["category"] for item in body["intelligence"]["watch_points"]}
        self.assertTrue({"trend", "volume", "risk"}.issubset(watch_categories))
        comparison_symbols = {item["symbol"] for item in body["intelligence"]["comparison_targets"]}
        self.assertIn("QQQ", comparison_symbols)
        self.assertIn("not investment advice", body["intelligence"]["boundary"])
        self.assertFalse(body["ai_used"])
        analysis_service.assert_not_called()

    def test_snapshot_accepts_a_share_source_mode_query_param(self) -> None:
        captured_modes: list[str | None] = []

        class FakeBasicQueryService:
            def __init__(self, *args, **kwargs):
                service = kwargs.get("a_share_enrichment_service")
                captured_modes.append(getattr(service, "source_mode", None))

            def get_snapshot(self, stock_code: str, *, force_refresh: bool = False):
                mode = captured_modes[-1]
                return {
                    "stock_code": stock_code,
                    "stock_name": "贵州茅台",
                    "market": "cn",
                    "quote": {
                        "current_price": 1188.8,
                        "source": "unit_quote",
                        "freshness": "fresh",
                    },
                    "indicators": {},
                    "intelligence": {
                        "mode": "no_ai_low_cost",
                        "ai_used": False,
                        "a_share_enrichment": {
                            "title": "A-share enrichment",
                            "summary": "source mode probe",
                            "status": "degraded",
                            "source": "a_stock_data_skill_adapter",
                            "source_mode": mode,
                            "skill": {"revision": "unit"},
                            "diagnostics": {"cache": {"hits": 0}, "rate_limited_channels": []},
                            "ai_used": False,
                            "public_search_used": False,
                            "channels": [
                                {
                                    "category": "capital_flow",
                                    "title": "Fund flow",
                                    "summary": "Unit summary",
                                    "status": "available",
                                    "source": "unit",
                                    "action": "Unit action",
                                    "details": [
                                        {
                                            "label": "Main net",
                                            "value": "12.0M",
                                            "detail": "Preserved through response schema.",
                                        }
                                    ],
                                }
                            ],
                            "reader_summary": {
                                "headline": "600519 A-share readout",
                                "why_read": "Why this matters",
                                "key_facts": [
                                    {
                                        "label": "Today",
                                        "value": "1188.8",
                                        "detail": "Unit response keeps reader summary through API schema.",
                                    }
                                ],
                                "miss_explanations": [
                                    {
                                        "title": "Fund flow",
                                        "explanation": "Missing in unit response.",
                                        "next_step": "Refresh later.",
                                    }
                                ],
                                "premium_features": ["Announcements"],
                                "boundary": "Information analysis only; not investment advice.",
                            },
                            "premium_unlock": "Premium can add more sources.",
                            "boundary": "Information analysis only; not investment advice.",
                        },
                        "items": [],
                        "boundary": "Information analysis only; not investment advice.",
                    },
                    "ai_used": False,
                }

        with patch("api.v1.endpoints.stocks.BasicQueryService", FakeBasicQueryService):
            response = self.client.get("/api/v1/stocks/600519/snapshot?a_share_source_mode=a_stock_data")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(captured_modes, ["a_stock_data"])
        self.assertEqual(body["intelligence"]["a_share_enrichment"]["source_mode"], "a_stock_data")
        reader_summary = body["intelligence"]["a_share_enrichment"]["reader_summary"]
        self.assertEqual(reader_summary["headline"], "600519 A-share readout")
        self.assertEqual(reader_summary["key_facts"][0]["label"], "Today")
        self.assertEqual(reader_summary["miss_explanations"][0]["next_step"], "Refresh later.")
        channel_details = body["intelligence"]["a_share_enrichment"]["channels"][0]["details"]
        self.assertEqual(channel_details[0]["label"], "Main net")
        self.assertEqual(channel_details[0]["detail"], "Preserved through response schema.")

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

    def test_no_ai_snapshot_includes_retention_brief(self) -> None:
        class RetentionStockService:
            def get_realtime_quote(self, stock_code: str):
                return {
                    "stock_code": stock_code,
                    "stock_name": "Apple Inc.",
                    "current_price": 200.0,
                    "change_percent": 1.5,
                    "volume": 1200000,
                    "source": "unit_quote",
                    "freshness": "fresh",
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
                    "market_cap": 4500000000000,
                    "pe_ratio": 31.2,
                    "source": "unit_profile",
                }

        with patch("src.services.analysis_service.AnalysisService") as analysis_service:
            snapshot = BasicQueryService(
                stock_service=RetentionStockService(),
                cache=MarketDataCache(default_ttl_seconds=60),
            ).get_snapshot("AAPL")

        retention = snapshot["intelligence"]["retention_brief"]
        self.assertFalse(snapshot["ai_used"])
        self.assertEqual(retention["source"], "no_ai_retention_rules")
        self.assertIn("AAPL", retention["headline"])
        self.assertIn("Technology", retention["why_it_matters"])
        self.assertIn("support", retention["support_resistance"])
        self.assertIn("resistance", retention["support_resistance"])
        self.assertGreaterEqual(len(retention["next_steps"]), 3)
        self.assertIn("login", retention["upgrade_hint"].lower())
        self.assertIn("not investment advice", retention["boundary"])
        analysis_service.assert_not_called()

    def test_no_ai_snapshot_enriches_free_comparison_targets_with_reference_quotes(self) -> None:
        class ReferenceQuoteStockService:
            quotes = {
                "AAPL": {
                    "stock_code": "AAPL",
                    "stock_name": "Apple Inc.",
                    "current_price": 200.0,
                    "change_percent": 1.5,
                    "volume": 1200000,
                    "source": "unit_quote",
                    "freshness": "fresh",
                    "update_time": "2026-07-08T09:30:00",
                },
                "QQQ": {
                    "stock_code": "QQQ",
                    "stock_name": "Invesco QQQ Trust",
                    "current_price": 512.34,
                    "change_percent": 0.87,
                    "volume": 2200000,
                    "source": "unit_reference_quote",
                    "freshness": "fresh",
                    "update_time": "2026-07-08T09:31:00",
                },
                "^IXIC": {
                    "stock_code": "^IXIC",
                    "stock_name": "Nasdaq Composite",
                    "current_price": 20234.56,
                    "change_percent": -0.22,
                    "volume": 0,
                    "source": "unit_reference_quote",
                    "freshness": "fresh",
                    "update_time": "2026-07-08T09:31:00",
                },
                "XLK": {
                    "stock_code": "XLK",
                    "stock_name": "Technology Select Sector SPDR Fund",
                    "current_price": 245.67,
                    "change_percent": 1.11,
                    "volume": 990000,
                    "source": "unit_reference_quote",
                    "freshness": "fresh",
                    "update_time": "2026-07-08T09:31:00",
                },
            }

            def get_realtime_quote(self, stock_code: str):
                return dict(self.quotes[stock_code])

            def get_history_data(self, stock_code: str, **_kwargs):
                return {
                    "stock_code": stock_code,
                    "stock_name": stock_code,
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
                    "market_cap": 4500000000000,
                    "pe_ratio": 31.2,
                    "source": "unit_profile",
                }

        snapshot = BasicQueryService(
            stock_service=ReferenceQuoteStockService(),
            cache=MarketDataCache(default_ttl_seconds=60),
        ).get_snapshot("AAPL")

        targets = {item["symbol"]: item for item in snapshot["intelligence"]["comparison_targets"]}
        qqq_quote = targets["QQQ"]["reference_quote"]
        self.assertEqual(qqq_quote["current_price"], 512.34)
        self.assertEqual(qqq_quote["price"], 512.34)
        self.assertEqual(qqq_quote["change_percent"], 0.87)
        self.assertEqual(qqq_quote["freshness"], "fresh")
        self.assertEqual(qqq_quote["source"], "unit_reference_quote")
        self.assertEqual(qqq_quote["status"], "available")

        peer_rows = {row["symbol"]: row for row in snapshot["intelligence"]["peer_comparison"]["rows"]}
        self.assertEqual(peer_rows["^IXIC"]["reference_quote"]["current_price"], 20234.56)
        self.assertEqual(peer_rows["XLK"]["reference_quote"]["change_percent"], 1.11)
        self.assertFalse(snapshot["ai_used"])

    def test_no_ai_snapshot_uses_yahoo_reference_quote_fallback_when_platform_source_is_empty(self) -> None:
        class EmptyReferenceQuoteStockService:
            def get_realtime_quote(self, stock_code: str):
                if stock_code == "AAPL":
                    return {
                        "stock_code": "AAPL",
                        "stock_name": "Apple Inc.",
                        "current_price": 200.0,
                        "change_percent": 1.5,
                        "volume": 1200000,
                        "source": "unit_quote",
                        "freshness": "fresh",
                    }
                return None

            def get_history_data(self, stock_code: str, **_kwargs):
                return {
                    "stock_code": stock_code,
                    "stock_name": stock_code,
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
                    "market_cap": 4500000000000,
                    "pe_ratio": 31.2,
                    "source": "unit_profile",
                }

        def yahoo_fallback(code: str):
            return {
                "stock_code": code,
                "stock_name": code,
                "current_price": 500.0 if code == "QQQ" else 20000.0,
                "change_percent": 0.5 if code == "QQQ" else -0.1,
                "source": "unit_yahoo_reference",
                "freshness": "fresh",
            }

        service = BasicQueryService(
            stock_service=EmptyReferenceQuoteStockService(),
            cache=MarketDataCache(default_ttl_seconds=60),
        )
        with patch.object(service, "_fetch_reference_quote_from_yahoo_chart", side_effect=yahoo_fallback):
            snapshot = service.get_snapshot("AAPL")

        targets = {item["symbol"]: item for item in snapshot["intelligence"]["comparison_targets"]}
        self.assertEqual(targets["QQQ"]["reference_quote"]["current_price"], 500.0)
        self.assertEqual(targets["QQQ"]["reference_quote"]["source"], "unit_yahoo_reference")
        self.assertEqual(targets["^IXIC"]["reference_quote"]["change_percent"], -0.1)
        self.assertEqual(targets["XLK"]["reference_quote"]["status"], "available")
        self.assertFalse(snapshot["ai_used"])

    def test_no_ai_snapshot_includes_news_center_and_kline_forecast_lab(self) -> None:
        class NewsKlineStockService:
            def get_realtime_quote(self, stock_code: str):
                return {
                    "stock_code": stock_code,
                    "stock_name": "Apple Inc.",
                    "current_price": 200.0,
                    "change_percent": 1.5,
                    "open": 198.0,
                    "high": 205.0,
                    "low": 197.0,
                    "prev_close": 197.0,
                    "volume": 1200000,
                    "source": "unit_quote",
                    "freshness": "fresh",
                }

            def get_history_data(self, stock_code: str, **_kwargs):
                return {
                    "stock_code": stock_code,
                    "stock_name": "Apple Inc.",
                    "source": "unit_history",
                    "data": [
                        {
                            "date": f"2026-06-{day:02d}",
                            "open": 178.0 + day,
                            "high": 181.0 + day,
                            "low": 176.0 + day,
                            "close": 180.0 + day,
                            "volume": 1000 + day * 10,
                        }
                        for day in range(1, 22)
                    ],
                }

            def get_basic_company_profile(self, stock_code: str):
                return {
                    "stock_code": stock_code,
                    "company_name": "Apple Inc.",
                    "sector": "Technology",
                    "industry": "Consumer Electronics",
                    "market_cap": 4500000000000,
                    "pe_ratio": 31.2,
                    "source": "unit_profile",
                }

        with patch("src.services.analysis_service.AnalysisService") as analysis_service:
            snapshot = BasicQueryService(
                stock_service=NewsKlineStockService(),
                cache=MarketDataCache(default_ttl_seconds=60),
            ).get_snapshot("AAPL")

        intelligence = snapshot["intelligence"]
        news_center = intelligence["news_center"]
        kline_forecast = intelligence["kline_forecast"]

        self.assertFalse(snapshot["ai_used"])
        self.assertFalse(news_center["ai_used"])
        self.assertFalse(news_center["public_search_used"])
        self.assertEqual(news_center["source"], "no_ai_news_center_rules")
        self.assertIn("AAPL", news_center["summary"])
        self.assertIn("Technology", news_center["summary"])
        news_categories = {item["category"] for item in news_center["items"]}
        self.assertTrue({"news", "announcements", "financials", "sector"}.issubset(news_categories))
        self.assertIn("Premium", news_center["premium_unlock"])

        self.assertFalse(kline_forecast["ai_used"])
        self.assertFalse(kline_forecast["kronos_model_used"])
        self.assertEqual(kline_forecast["source"], "local_kline_rules_kronos_ready")
        self.assertIn("Kronos", kline_forecast["adapter_status"])
        self.assertEqual(kline_forecast["horizon"], "next_5_bars")
        self.assertGreaterEqual(len(kline_forecast["scenarios"]), 3)
        self.assertIn(kline_forecast["direction"], {"upside_bias", "range_watch", "downside_risk", "insufficient_data"})
        self.assertIn("not investment advice", kline_forecast["boundary"])
        self.assertIn("Premium", kline_forecast["premium_unlock"])
        analysis_service.assert_not_called()

    def test_a_share_snapshot_includes_a_stock_data_enrichment_poc(self) -> None:
        class AShareStockService:
            def get_realtime_quote(self, stock_code: str):
                return {
                    "stock_code": stock_code,
                    "stock_name": "贵州茅台",
                    "current_price": 1600.0,
                    "change_percent": 1.2,
                    "open": 1580.0,
                    "high": 1610.0,
                    "low": 1576.0,
                    "prev_close": 1581.0,
                    "volume": 1200000,
                    "amount": 1920000000.0,
                    "source": "unit_quote",
                    "freshness": "fresh",
                }

            def get_history_data(self, stock_code: str, **_kwargs):
                return {
                    "stock_code": stock_code,
                    "stock_name": "贵州茅台",
                    "source": "unit_history",
                    "data": [
                        {
                            "date": f"2026-06-{day:02d}",
                            "open": 1500.0 + day,
                            "high": 1510.0 + day,
                            "low": 1490.0 + day,
                            "close": 1500.0 + day,
                            "volume": 1000000 + day * 1000,
                        }
                        for day in range(1, 22)
                    ],
                }

            def get_basic_company_profile(self, stock_code: str):
                return {
                    "stock_code": stock_code,
                    "company_name": "贵州茅台",
                    "sector": "食品饮料",
                    "industry": "白酒",
                    "market_cap": 2000000000000,
                    "pe_ratio": 24.8,
                    "source": "unit_profile",
                }

        class FakeAShareEnrichmentService:
            def get_enrichment(self, stock_code: str, *, stock_name=None, profile=None, quote=None, indicators=None):
                return {
                    "title": "A股增强数据",
                    "summary": f"{stock_name or stock_code} 的公告、资金流、板块、研报和龙虎榜本地增强通道。",
                    "status": "available",
                    "source": "a_stock_data_poc_fixture",
                    "ai_used": False,
                    "public_search_used": False,
                    "channels": [
                        {"category": "announcements", "title": "公告通道", "summary": "近公告可用于核对重大事项。", "status": "available", "source": "fixture", "action": "深度模式可展开公告来源。"},
                        {"category": "capital_flow", "title": "资金流通道", "summary": "主力资金净流入为正。", "status": "available", "source": "fixture", "action": "观察连续性。"},
                        {"category": "sector", "title": "板块通道", "summary": "食品饮料 / 白酒。", "status": "available", "source": "fixture", "action": "对比同板块。"},
                        {"category": "research", "title": "研报通道", "summary": "有机构研报覆盖。", "status": "available", "source": "fixture", "action": "免费版保留入口；高级版使用 API 查看详情。"},
                        {"category": "dragon_tiger", "title": "龙虎榜通道", "summary": "未见近期异常上榜。", "status": "degraded", "source": "fixture", "action": "刷新后复核。"},
                    ],
                    "premium_unlock": "免费版保留同样入口；高级版使用 API 展开原始来源、PDF、席位明细和资金流历史。",
                    "boundary": "Information analysis only; not investment advice.",
                }

        with patch("src.services.analysis_service.AnalysisService") as analysis_service:
            snapshot = BasicQueryService(
                stock_service=AShareStockService(),
                cache=MarketDataCache(default_ttl_seconds=60),
                a_share_enrichment_service=FakeAShareEnrichmentService(),
            ).get_snapshot("600519")

        enrichment = snapshot["intelligence"]["a_share_enrichment"]
        self.assertEqual(snapshot["market"], "cn")
        self.assertFalse(snapshot["ai_used"])
        self.assertFalse(enrichment["ai_used"])
        self.assertFalse(enrichment["public_search_used"])
        categories = {item["category"] for item in enrichment["channels"]}
        self.assertEqual(categories, {"announcements", "capital_flow", "sector", "research", "dragon_tiger"})
        self.assertEqual(enrichment["source"], "a_stock_data_poc_fixture")
        self.assertIn("not investment advice", enrichment["boundary"])
        analysis_service.assert_not_called()

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

    def test_hk_snapshot_uses_history_close_when_realtime_quote_is_missing(self) -> None:
        class HkHistoryOnlyStockService:
            def get_realtime_quote(self, stock_code: str):
                return None

            def get_history_data(self, stock_code: str, **_kwargs):
                return {
                    "stock_code": stock_code,
                    "stock_name": "Tencent Holdings",
                    "source": "unit_hk_history",
                    "data": [
                        {
                            "date": "2026-07-01",
                            "open": 420.0,
                            "high": 430.0,
                            "low": 418.0,
                            "close": 425.0,
                            "volume": 1000000,
                            "amount": 425000000.0,
                        },
                        {
                            "date": "2026-07-02",
                            "open": 426.0,
                            "high": 436.0,
                            "low": 422.0,
                            "close": 431.2,
                            "volume": 1200000,
                            "amount": 517440000.0,
                        },
                    ],
                }

            def get_basic_company_profile(self, stock_code: str):
                return None

        service = BasicQueryService(
            stock_service=HkHistoryOnlyStockService(),
            cache=MarketDataCache(default_ttl_seconds=60),
        )
        with patch.object(service, "_fetch_reference_quote_from_yahoo_chart", return_value=None):
            snapshot = service.get_snapshot("00700.HK")

        self.assertFalse(snapshot["ai_used"])
        self.assertEqual(snapshot["market"], "hk")
        self.assertEqual(snapshot["quote"]["current_price"], 431.2)
        self.assertEqual(snapshot["quote"]["prev_close"], 425.0)
        self.assertAlmostEqual(snapshot["quote"]["change"], 6.2)
        self.assertAlmostEqual(snapshot["quote"]["change_percent"], 1.4588)
        self.assertEqual(snapshot["quote"]["source"], "unit_hk_history_last_close")
        self.assertEqual(snapshot["quote"]["freshness"], "cached")
        self.assertEqual(snapshot["diagnostics"]["fallback"]["quote"], "history_last_close")
        warning_codes = {item["code"] for item in snapshot["warnings"]}
        self.assertIn("quote_from_history_close", warning_codes)
        self.assertNotIn("missing_quote", warning_codes)

    def test_hk_snapshot_uses_fast_public_quote_and_history_fallbacks(self) -> None:
        class HkPublicFallbackStockService:
            def get_realtime_quote(self, _stock_code: str):
                return None

            def get_public_history_data(self, stock_code: str, **_kwargs):
                return {
                    "stock_code": stock_code,
                    "stock_name": "Tencent Holdings Limited",
                    "source": "yahoo_chart_history",
                    "data": [
                        {"date": "2026-07-01", "close": 450.0, "volume": 1_000_000},
                        {"date": "2026-07-02", "close": 458.2, "volume": 1_200_000},
                    ],
                }

            def get_history_data(self, *_args, **_kwargs):
                raise AssertionError("HK quick query should use the bounded public history path first")

            def get_basic_company_profile(self, _stock_code: str):
                return None

        service = BasicQueryService(
            stock_service=HkPublicFallbackStockService(),
            cache=MarketDataCache(default_ttl_seconds=60),
        )
        public_quote = {
            "stock_code": "HK00700",
            "stock_name": "Tencent Holdings Limited",
            "current_price": 458.2,
            "change": 6.2,
            "change_percent": 1.3717,
            "volume": 22_852_542,
            "source": "yahoo_chart_reference",
            "freshness": "fresh",
        }

        with (
            patch.object(
                service,
                "_fetch_reference_quote_from_yahoo_chart",
                side_effect=lambda code: public_quote if code == "HK00700" else None,
            ),
            patch.object(service, "_comparison_targets_with_reference_quotes", return_value=[]),
        ):
            snapshot = service.get_snapshot("00700.HK")

        self.assertEqual(snapshot["market"], "hk")
        self.assertEqual(snapshot["quote"]["current_price"], 458.2)
        self.assertEqual(snapshot["quote"]["source"], "yahoo_chart_reference")
        self.assertEqual(snapshot["quote"]["freshness"], "fresh")
        self.assertEqual(snapshot["trend"]["points"][-1]["close"], 458.2)
        self.assertEqual(snapshot["diagnostics"]["sources"]["history"], "yahoo_chart_history")


if __name__ == "__main__":
    unittest.main()
