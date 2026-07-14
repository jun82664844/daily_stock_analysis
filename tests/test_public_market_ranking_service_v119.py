# -*- coding: utf-8 -*-
from __future__ import annotations

import unittest


class _Clock:
    def __init__(self) -> None:
        self.value = 0.0

    def __call__(self) -> float:
        return self.value


class _PublicResponses:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, int]] = []
        self.failed = False

    def __call__(self, url: str, params: dict, _timeout: float) -> object:
        if self.failed:
            raise RuntimeError("public source unavailable")
        sort = str(params.get("sort") or params.get("scrIds") or "sector")
        asc = int(params.get("asc", 0))
        self.calls.append((url, sort, asc))

        if "newSinaHy" in url:
            return 'var S_Finance_bankuai_sinaindustry = {"new_furniture":"new_furniture,家具行业,10,20,1,3.7,100,200,sh600001,8.2,10,1,领涨公司"}'
        if "getHQNodeData" in url:
            if sort == "amount":
                return [
                    {"symbol": "sh600000", "code": "600000", "name": "浦发银行", "trade": "12.50", "changepercent": "1.2", "volume": "1000", "amount": "900000000", "mktcap": "2000000", "ticktime": "10:01:30"},
                    {"symbol": "bj920305", "code": "920305", "name": "北交样本", "trade": "8.00", "changepercent": "8.8", "volume": "100", "amount": "100000000", "ticktime": "10:01:30"},
                ]
            if asc == 0:
                return [{"symbol": "sz300001", "code": "300001", "name": "特锐德", "trade": "20.00", "changepercent": "9.5", "volume": "2000", "amount": "300000000", "ticktime": "10:01:31"}]
            return [{"symbol": "sh600010", "code": "600010", "name": "包钢股份", "trade": "2.10", "changepercent": "-7.2", "volume": "3000", "amount": "500000000", "ticktime": "10:01:31"}]
        if "getHKStockData" in url:
            row = {"symbol": "00700", "name": "腾讯控股", "lasttrade": "450.4", "changepercent": "-1.2", "volume": "1000", "amount": "800000000", "ticktime": "2026/07/14 10:01:32"}
            return [row]
        if "finance/screener" in url:
            key = str(params["scrIds"])
            change = {"most_actives": 0.8, "day_gainers": 6.2, "day_losers": -5.1}[key]
            return {"finance": {"result": [{"quotes": [{
                "symbol": "AAPL", "shortName": "Apple Inc.", "regularMarketPrice": 210.4,
                "regularMarketChangePercent": change, "regularMarketVolume": 123456,
                "marketCap": 3200000000000, "regularMarketTime": 1783972802,
                "currency": "USD",
            }]}]}}
        raise AssertionError(f"unexpected URL: {url}")


class PublicMarketRankingServiceV119TestCase(unittest.TestCase):
    def test_maps_three_market_rankings_and_cn_sector_without_fixed_symbols(self) -> None:
        from src.services.public_market_ranking_service import PublicMarketRankingService

        responses = _PublicResponses()
        service = PublicMarketRankingService(
            fetch_public=responses,
            clock=lambda: "2026-07-14T02:02:00+00:00",
            monotonic=_Clock(),
            request_timeout_seconds=1,
        )

        cn = service.load("cn")
        hk = service.load("hk")
        us = service.load("us")

        self.assertEqual([item["symbol"] for item in cn["most_active"]], ["600000.SH"])
        self.assertEqual([item["symbol"] for item in cn["gainers"]], ["300001.SZ"])
        self.assertEqual([item["symbol"] for item in cn["losers"]], ["600010.SH"])
        self.assertEqual(cn["sector_highlights"][0]["name"], "家具行业")
        self.assertEqual(cn["sector_highlights"][0]["leading_symbol"], "600001.SH")
        self.assertEqual(hk["most_active"][0]["symbol"], "0700.HK")
        self.assertEqual(us["gainers"][0]["symbol"], "AAPL")
        self.assertNotIn("600519.SH", {item["symbol"] for item in cn["most_active"]})
        self.assertFalse(cn["ai_used"])
        self.assertTrue(cn["informational_only"])

    def test_fresh_cache_avoids_network_and_reports_cache_hit(self) -> None:
        from src.services.public_market_ranking_service import PublicMarketRankingService

        responses = _PublicResponses()
        clock = _Clock()
        service = PublicMarketRankingService(
            fetch_public=responses,
            monotonic=clock,
            cache_ttl_seconds=120,
            request_timeout_seconds=1,
        )
        first = service.load("us")
        call_count = len(responses.calls)
        clock.value = 30
        second = service.load("us")

        self.assertFalse(first["cache"]["hit"])
        self.assertTrue(second["cache"]["hit"])
        self.assertEqual(second["cache"]["age_seconds"], 30)
        self.assertEqual(len(responses.calls), call_count)

    def test_source_failure_uses_marked_stale_last_good_without_fixed_fallback(self) -> None:
        from src.services.public_market_ranking_service import PublicMarketRankingService

        responses = _PublicResponses()
        clock = _Clock()
        service = PublicMarketRankingService(
            fetch_public=responses,
            monotonic=clock,
            cache_ttl_seconds=10,
            stale_ttl_seconds=300,
            request_timeout_seconds=1,
        )
        service.load("hk")
        responses.failed = True
        clock.value = 20
        stale = service.load("hk")

        self.assertEqual(stale["most_active"][0]["symbol"], "0700.HK")
        self.assertEqual(stale["most_active"][0]["source_state"]["status"], "stale")
        self.assertIn("market_ranking_stale_cache", stale["warnings"])
        self.assertTrue(stale["cache"]["hit"])

    def test_total_failure_returns_empty_rankings_and_explicit_warning(self) -> None:
        from src.services.public_market_ranking_service import PublicMarketRankingService

        responses = _PublicResponses()
        responses.failed = True
        body = PublicMarketRankingService(fetch_public=responses, request_timeout_seconds=1).load("cn")

        self.assertEqual(body["most_active"], [])
        self.assertEqual(body["gainers"], [])
        self.assertEqual(body["losers"], [])
        self.assertIn("market_rankings_unavailable", body["warnings"])
        self.assertFalse(body["ai_used"])


if __name__ == "__main__":
    unittest.main()
