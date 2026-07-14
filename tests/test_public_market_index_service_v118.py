# -*- coding: utf-8 -*-
from __future__ import annotations

import unittest


class PublicMarketIndexServiceV118TestCase(unittest.TestCase):
    def test_builds_factual_market_index_from_allowlisted_chart(self) -> None:
        from src.services.public_market_index_service import PublicMarketIndexService

        calls: list[str] = []

        def fetch(symbol: str) -> dict:
            calls.append(symbol)
            return {
                "chart": {"result": [{"meta": {
                    "symbol": symbol,
                    "regularMarketPrice": 3913.79,
                    "chartPreviousClose": 3900.0,
                    "regularMarketTime": 1783952400,
                }}]}
            }

        service = PublicMarketIndexService(fetcher=fetch, cache_ttl_seconds=300)
        items = service.load("cn")

        self.assertEqual(calls, ["000001.SS"])
        self.assertEqual(items[0]["symbol"], "000001.SS")
        self.assertEqual(items[0]["name"], "上证指数")
        self.assertEqual(items[0]["market"], "cn")
        self.assertEqual(items[0]["currency"], "CNY")
        self.assertEqual(items[0]["current_price"], 3913.79)
        self.assertAlmostEqual(items[0]["change_percent"], 0.3536, places=4)
        self.assertEqual(items[0]["source_state"]["source"], "yahoo_public_index")

    def test_markets_use_separate_indices_and_cache_results(self) -> None:
        from src.services.public_market_index_service import PublicMarketIndexService

        calls: list[str] = []

        def fetch(symbol: str) -> dict:
            calls.append(symbol)
            return {"chart": {"result": [{"meta": {"regularMarketPrice": 100, "chartPreviousClose": 99}}]}}

        service = PublicMarketIndexService(fetcher=fetch, cache_ttl_seconds=300)
        self.assertEqual(service.load("hk")[0]["name"], "恒生指数")
        self.assertEqual(service.load("us")[0]["name"], "标普500指数")
        service.load("hk")

        self.assertEqual(calls, ["^HSI", "^GSPC"])

    def test_failure_or_unsupported_market_degrades_to_empty_list(self) -> None:
        from src.services.public_market_index_service import PublicMarketIndexService

        service = PublicMarketIndexService(fetcher=lambda _symbol: (_ for _ in ()).throw(RuntimeError("offline")))
        self.assertEqual(service.load("cn"), [])
        self.assertEqual(service.load("crypto"), [])


if __name__ == "__main__":
    unittest.main()
