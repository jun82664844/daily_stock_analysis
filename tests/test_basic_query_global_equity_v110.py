# -*- coding: utf-8 -*-
from __future__ import annotations

import unittest

from src.services.basic_query_service import BasicQueryService
from src.services.market_data_cache import MarketDataCache
from src.services.stock_service import StockService


class _StockService:
    def get_realtime_quote(self, stock_code: str):
        return {
            "stock_code": stock_code,
            "stock_name": "Apple Inc." if stock_code == "AAPL" else "Tencent Holdings Limited",
            "current_price": 200.0,
            "change_percent": 1.5,
            "source": "unit_quote",
        }

    def get_history_data(self, stock_code: str, **_kwargs):
        return {
            "stock_code": stock_code,
            "source": "unit_history",
            "data": [
                {"date": f"2026-06-{day:02d}", "close": 180.0 + day, "volume": 1000 + day}
                for day in range(1, 22)
            ],
        }

    def get_basic_company_profile(self, stock_code: str):
        return {
            "stock_code": stock_code,
            "company_name": "Apple Inc." if stock_code == "AAPL" else "Tencent Holdings Limited",
            "sector": "Technology",
            "industry": "Software",
            "source": "unit_profile",
        }


class _GlobalService:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def get_enrichment(self, stock_code: str, **kwargs):
        self.calls.append({"stock_code": stock_code, **kwargs})
        if kwargs["market"] not in {"us", "hk"}:
            return None
        return {
            "title": "Global public data expansion",
            "summary": "Direct public source data is available.",
            "market": kwargs["market"],
            "status": "available",
            "source": "unit_global_adapter",
            "updated_at": "2026-07-12T00:00:00+00:00",
            "ai_used": False,
            "public_search_used": False,
            "channels": [
                {
                    "category": "news",
                    "title": "Company news",
                    "summary": "One real headline is available.",
                    "status": "available",
                    "source": "unit_news",
                    "items": [
                        {
                            "title": "Apple publishes a product update",
                            "summary": "Example News",
                            "publisher": "Example News",
                            "published_at": "2026-07-11T00:00:00+00:00",
                            "url": "https://finance.yahoo.com/news/apple-update",
                            "source": "unit_news",
                        }
                    ],
                    "action": "Open source.",
                }
            ],
            "diagnostics": {"cache_hit": False, "elapsed_ms": 1},
            "premium_unlock": "Configured APIs can add coverage.",
            "boundary": "Information and data only; not investment advice.",
        }


class BasicQueryGlobalEquityV110Tests(unittest.TestCase):
    def test_hk_profile_symbol_removes_internal_normalization_zero(self) -> None:
        self.assertEqual(StockService()._to_yfinance_profile_symbol("HK00700"), "0700.HK")

    def test_us_snapshot_preserves_global_enrichment_and_real_news_summary(self) -> None:
        global_service = _GlobalService()
        snapshot = BasicQueryService(
            stock_service=_StockService(),
            cache=MarketDataCache(default_ttl_seconds=60),
            global_equity_enrichment_service=global_service,
        ).get_snapshot("AAPL")

        enrichment = snapshot["intelligence"]["global_equity_enrichment"]
        self.assertEqual(enrichment["market"], "us")
        self.assertFalse(enrichment["ai_used"])
        self.assertEqual(enrichment["channels"][0]["items"][0]["title"], "Apple publishes a product update")
        news_items = snapshot["intelligence"]["news_center"]["items"]
        self.assertEqual(news_items[0]["title"], "Apple publishes a product update")
        self.assertEqual(news_items[0]["url"], "https://finance.yahoo.com/news/apple-update")
        self.assertEqual(global_service.calls[0]["stock_name"], "Apple Inc.")

    def test_a_share_does_not_call_global_equity_adapter(self) -> None:
        global_service = _GlobalService()
        snapshot = BasicQueryService(
            stock_service=_StockService(),
            cache=MarketDataCache(default_ttl_seconds=60),
            global_equity_enrichment_service=global_service,
        ).get_snapshot("600519.SH")

        self.assertIsNone(snapshot["intelligence"]["global_equity_enrichment"])
        self.assertEqual(global_service.calls, [])


if __name__ == "__main__":
    unittest.main()
