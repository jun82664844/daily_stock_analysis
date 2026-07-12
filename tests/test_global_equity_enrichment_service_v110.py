# -*- coding: utf-8 -*-
from __future__ import annotations

import unittest

from src.services.global_equity_enrichment_service import GlobalEquityEnrichmentService


class GlobalEquityEnrichmentServiceV110Tests(unittest.TestCase):
    def setUp(self) -> None:
        GlobalEquityEnrichmentService.clear_cache()

    def test_repairs_common_utf8_latin1_news_title_mojibake(self) -> None:
        service = GlobalEquityEnrichmentService(http_get_json=lambda *_args, **_kwargs: {})
        self.assertEqual(
            service._repair_mojibake("Apple\u00e2\u0080\u0099s product update"),
            "Apple\u2019s product update",
        )

    def test_us_payload_combines_symbol_news_and_official_sec_filings(self) -> None:
        calls: list[str] = []

        def fake_json(url: str, **_kwargs):
            calls.append(url)
            if "finance/search" in url:
                return {
                    "news": [
                        {
                            "title": "Apple publishes a product update",
                            "publisher": "Example News",
                            "providerPublishTime": 1783815000,
                            "link": "https://finance.yahoo.com/news/apple-update",
                            "relatedTickers": ["AAPL", "MSFT"],
                        },
                        {
                            "title": "Unrelated market story",
                            "publisher": "Example News",
                            "providerPublishTime": 1783814000,
                            "link": "https://finance.yahoo.com/news/unrelated",
                            "relatedTickers": ["TSLA"],
                        },
                        {
                            "title": "A broad wealth and politics roundup",
                            "publisher": "Example News",
                            "providerPublishTime": 1783813000,
                            "link": "https://finance.yahoo.com/news/broad-roundup",
                            "relatedTickers": ["AAPL", "TSLA", "MSFT", "GOOG"],
                        },
                    ]
                }
            if url.endswith("company_tickers.json"):
                return {"0": {"cik_str": 320193, "ticker": "AAPL", "title": "Apple Inc."}}
            if "CIK0000320193.json" in url:
                return {
                    "name": "Apple Inc.",
                    "filings": {
                        "recent": {
                            "form": ["10-Q", "8-K"],
                            "filingDate": ["2026-07-10", "2026-07-08"],
                            "reportDate": ["2026-06-30", "2026-07-08"],
                            "accessionNumber": ["0000320193-26-000010", "0000320193-26-000009"],
                            "primaryDocument": ["aapl-20260630.htm", "aapl-20260708.htm"],
                            "primaryDocDescription": ["Quarterly report", "Current report"],
                        }
                    },
                }
            raise AssertionError(f"unexpected URL {url}")

        payload = GlobalEquityEnrichmentService(http_get_json=fake_json).get_enrichment(
            "AAPL",
            market="us",
            stock_name="Apple Inc.",
            profile={"sector": "Technology", "industry": "Consumer Electronics"},
        )

        self.assertEqual(payload["market"], "us")
        self.assertEqual(payload["status"], "available")
        self.assertFalse(payload["ai_used"])
        self.assertFalse(payload["public_search_used"])
        channels = {item["category"]: item for item in payload["channels"]}
        self.assertEqual(channels["news"]["status"], "available")
        self.assertEqual(len(channels["news"]["items"]), 1)
        self.assertEqual(channels["news"]["items"][0]["title"], "Apple publishes a product update")
        self.assertEqual(channels["filings"]["status"], "available")
        self.assertEqual(channels["filings"]["items"][0]["document_type"], "10-Q")
        self.assertEqual(channels["filings"]["items"][0]["title"], "10-Q - Quarterly report")
        self.assertIn("www.sec.gov/Archives/edgar/data/320193", channels["filings"]["items"][0]["url"])
        self.assertIn("Information and data only", payload["boundary"])
        self.assertEqual(len(calls), 3)

    def test_hk_payload_filters_news_and_keeps_hkex_boundary_honest(self) -> None:
        def fake_json(url: str, **_kwargs):
            self.assertIn("finance/search", url)
            return {
                "news": [
                    {
                        "title": "Tencent releases an operating update",
                        "publisher": "Example News",
                        "providerPublishTime": 1783815000,
                        "link": "https://finance.yahoo.com/news/tencent-update",
                        "relatedTickers": ["0700.HK", "TCEHY"],
                    },
                    {
                        "title": "Unrelated headline",
                        "publisher": "Example News",
                        "providerPublishTime": 1783814000,
                        "link": "https://finance.yahoo.com/news/unrelated",
                        "relatedTickers": ["AAPL"],
                    },
                ]
            }

        payload = GlobalEquityEnrichmentService(http_get_json=fake_json).get_enrichment(
            "HK00700",
            market="hk",
            stock_name="Tencent Holdings Limited",
            profile={"sector": "Communication Services"},
        )

        channels = {item["category"]: item for item in payload["channels"]}
        self.assertEqual(channels["news"]["status"], "available")
        self.assertEqual(len(channels["news"]["items"]), 1)
        self.assertEqual(channels["filings"]["status"], "degraded")
        self.assertEqual(channels["filings"]["source"], "hkexnews_official_search")
        self.assertEqual(channels["filings"]["items"], [])
        self.assertIn("not configured", channels["filings"]["summary"])
        self.assertFalse(payload["ai_used"])

    def test_cache_avoids_repeating_public_requests(self) -> None:
        calls = 0

        def fake_json(url: str, **_kwargs):
            nonlocal calls
            calls += 1
            if "finance/search" in url:
                return {"news": []}
            if url.endswith("company_tickers.json"):
                return {"0": {"cik_str": 320193, "ticker": "AAPL", "title": "Apple Inc."}}
            return {"name": "Apple Inc.", "filings": {"recent": {}}}

        service = GlobalEquityEnrichmentService(http_get_json=fake_json, cache_ttl_seconds=600)
        first = service.get_enrichment("AAPL", market="us", stock_name="Apple Inc.")
        second = service.get_enrichment("AAPL", market="us", stock_name="Apple Inc.")

        self.assertEqual(calls, 3)
        self.assertFalse(first["diagnostics"]["cache_hit"])
        self.assertTrue(second["diagnostics"]["cache_hit"])

    def test_hk_symbol_search_retries_with_resolved_company_name(self) -> None:
        calls: list[str] = []

        def fake_json(url: str, **_kwargs):
            calls.append(url)
            if "q=0700.HK" in url:
                return {
                    "quotes": [{"symbol": "0700.HK", "longname": "Tencent Holdings Limited"}],
                    "news": [{"title": "Broad story", "relatedTickers": ["AAPL"]}],
                }
            self.assertIn("Tencent+Holdings+Limited", url)
            return {
                "news": [
                    {
                        "title": "Tencent publishes an operating update",
                        "publisher": "Example News",
                        "providerPublishTime": 1783815000,
                        "link": "https://finance.yahoo.com/news/tencent-update",
                        "relatedTickers": ["0700.HK"],
                    }
                ]
            }

        payload = GlobalEquityEnrichmentService(http_get_json=fake_json).get_enrichment(
            "HK00700",
            market="hk",
            stock_name="è\x85¾è®¯æ\x8e§è\x82¡",
        )

        news = next(channel for channel in payload["channels"] if channel["category"] == "news")
        self.assertEqual(news["status"], "available")
        self.assertEqual(news["items"][0]["title"], "Tencent publishes an operating update")
        self.assertEqual(len(calls), 2)

    def test_non_us_hk_market_is_not_routed_through_global_adapter(self) -> None:
        service = GlobalEquityEnrichmentService(http_get_json=lambda *_args, **_kwargs: {})
        self.assertIsNone(service.get_enrichment("600519.SH", market="cn"))
        self.assertIsNone(service.get_enrichment("BTC-USD", market="crypto"))


if __name__ == "__main__":
    unittest.main()
