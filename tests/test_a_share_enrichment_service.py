# -*- coding: utf-8 -*-
import sys
import unittest
from unittest.mock import patch


class AShareEnrichmentServiceTestCase(unittest.TestCase):
    def test_builds_useful_quick_reference_when_external_lanes_are_disabled(self) -> None:
        from src.services.a_share_enrichment_service import AShareEnrichmentService

        payload = AShareEnrichmentService().get_enrichment(
            "600519.SH",
            stock_name="贵州茅台",
            profile={
                "company_name": "贵州茅台",
                "market_cap": 1476696000000.0,
                "pe_ratio": 17.85,
                "pb_ratio": 6.34,
                "source": "a_share_realtime",
                "freshness": "stale",
            },
            quote={
                "current_price": 1181.28,
                "change_percent": -1.1,
                "open": 1186.0,
                "high": 1190.0,
                "low": 1181.28,
                "volume": 174700.0,
                "amount": 207003534.0,
                "source": "a_share_realtime",
                "freshness": "stale",
            },
            indicators={
                "ma5": 1195.782,
                "ma10": 1191.91,
                "ma20": 1212.965,
                "last_close": 1202.45,
                "price_change_5d": 2.894,
                "price_change_20d": -3.0267,
                "volume_change_vs_ma5": -75.1617,
            },
        )

        self.assertEqual(payload["status"], "available")
        self.assertEqual(payload["title"], "A-share quick reference")
        self.assertEqual(payload["source"], "basic_quote_snapshot")
        self.assertFalse(payload["ai_used"])
        self.assertFalse(payload["public_search_used"])
        categories = [item["category"] for item in payload["channels"]]
        self.assertEqual(
            categories,
            ["price_structure", "volume_activity", "valuation_snapshot", "trend_windows", "data_quality"],
        )
        self.assertTrue(all(item["status"] == "available" for item in payload["channels"]))
        joined = "\n".join(item["summary"] for item in payload["channels"])
        self.assertIn("Latest 1181.28", joined)
        self.assertIn("MA20 1212.965", joined)
        self.assertIn("Volume 174.7K", joined)
        self.assertIn("amount 207M", joined)
        self.assertIn("Market cap 1.4767T", joined)
        self.assertIn("PE 17.85", joined)
        self.assertIn("5-day change 2.894%", joined)
        self.assertNotIn("reserved CNINFO", joined)
        self.assertNotIn("reserved Eastmoney", joined)
        self.assertIn("not investment advice", payload["boundary"])

    def test_builds_five_channel_payload_from_fixture_http_data(self) -> None:
        from src.services.a_share_enrichment_service import AShareEnrichmentService

        calls: list[tuple[str, dict]] = []

        def fake_http_get(url: str, *, params=None, headers=None, timeout=None):
            calls.append((url, params or {}))
            if "fund-flow" in url:
                return {"main_net": 125000000, "main_net_ratio": 3.2, "latest_date": "2026-07-06"}
            if "concept-blocks" in url:
                return {"concepts": ["白酒", "贵州国企改革"], "industry": "食品饮料"}
            if "reports" in url:
                return {"items": [{"title": "贵州茅台跟踪报告", "rating": "买入", "date": "2026-07-05"}]}
            if "announcements" in url:
                return {"items": [{"title": "2026年半年度经营数据公告", "date": "2026-07-04"}]}
            if "dragon-tiger" in url:
                return {"items": [{"date": "2026-07-03", "net_buy": 33000000}]}
            return {}

        payload = AShareEnrichmentService(http_get=fake_http_get).get_enrichment(
            "600519.SH",
            stock_name="贵州茅台",
            profile={"sector": "食品饮料", "industry": "白酒"},
            quote={"current_price": 1600.0, "change_percent": 1.2},
        )

        self.assertEqual(payload["status"], "available")
        self.assertFalse(payload["ai_used"])
        self.assertFalse(payload["public_search_used"])
        self.assertIn("贵州茅台", payload["summary"])
        self.assertEqual(
            {item["category"] for item in payload["channels"]},
            {"announcements", "capital_flow", "sector", "research", "dragon_tiger"},
        )
        self.assertTrue(any("fund-flow" in url for url, _params in calls))
        self.assertIn("not investment advice", payload["boundary"])

    def test_degrades_without_breaking_quick_query_when_upstream_fails(self) -> None:
        from src.services.a_share_enrichment_service import AShareEnrichmentService

        def broken_http_get(_url: str, *, params=None, headers=None, timeout=None):
            raise TimeoutError("upstream timeout")

        payload = AShareEnrichmentService(http_get=broken_http_get).get_enrichment(
            "600519",
            stock_name="贵州茅台",
            profile={"sector": "食品饮料", "industry": "白酒"},
            quote={"current_price": 1600.0},
        )

        self.assertEqual(payload["status"], "available")
        self.assertEqual(payload["title"], "A-share quick reference")
        self.assertEqual(payload["source"], "basic_quote_snapshot")
        self.assertFalse(payload["ai_used"])
        self.assertFalse(payload["public_search_used"])
        self.assertEqual(len(payload["channels"]), 5)
        self.assertTrue(all(item["status"] in {"degraded", "available"} for item in payload["channels"]))
        self.assertIn("price_structure", {item["category"] for item in payload["channels"]})
        self.assertIn("not investment advice", payload["boundary"])

    def test_a_stock_data_source_mode_uses_skill_metadata_and_cache(self) -> None:
        from src.services.a_share_enrichment_service import AShareEnrichmentService

        calls: list[tuple[str, dict]] = []

        def fake_http_get(url: str, *, params=None, headers=None, timeout=None):
            calls.append((url, params or {}))
            if url.endswith("/capital_flow"):
                return {"main_net": 88000000, "main_net_ratio": 2.4}
            if url.endswith("/sector"):
                return {"industry": "baijiu", "concepts": ["consumer", "high dividend"]}
            if url.endswith("/research"):
                return {"items": [{"title": "sample research", "rating": "buy"}]}
            if url.endswith("/announcements"):
                return {"items": [{"title": "sample announcement", "date": "2026-07-07"}]}
            if url.endswith("/dragon_tiger"):
                return {"items": [{"date": "2026-07-06", "net_buy": 12000000}]}
            return {}

        service = AShareEnrichmentService(
            http_get=fake_http_get,
            source_mode="a_stock_data",
            cache_ttl_seconds=300,
            min_interval_seconds=0,
            skill_root=r"C:\Users\26879\Documents\Codex\external\a-stock-data",
            skill_revision="bcda405",
        )

        first = service.get_enrichment("600519.SH", stock_name="Kweichow Moutai")
        second = service.get_enrichment("600519.SH", stock_name="Kweichow Moutai")

        self.assertEqual(first["source"], "a_stock_data_skill_adapter")
        self.assertEqual(first["source_mode"], "a_stock_data")
        self.assertEqual(first["skill"]["revision"], "bcda405")
        self.assertEqual(first["diagnostics"]["cache"]["hits"], 0)
        self.assertEqual(second["diagnostics"]["cache"]["hits"], 5)
        self.assertEqual(len(calls), 5)
        self.assertTrue(all(url.startswith("a-stock-data://") for url, _params in calls))
        self.assertEqual({params["code"] for _url, params in calls}, {"600519"})

    def test_a_stock_data_source_mode_uses_longer_default_timeout_than_local_poc(self) -> None:
        from src.services.a_share_enrichment_service import AShareEnrichmentService

        with patch.dict("os.environ", {}, clear=True):
            poc = AShareEnrichmentService(source_mode="poc", http_enabled=False)
            real = AShareEnrichmentService(source_mode="a_stock_data", http_enabled=False)

        self.assertEqual(poc.timeout_seconds, 1.2)
        self.assertEqual(real.timeout_seconds, 2.5)

    def test_a_stock_data_source_mode_reuses_stale_cache_during_rate_limit(self) -> None:
        from src.services.a_share_enrichment_service import AShareEnrichmentService

        now = [1000.0]
        calls: list[str] = []

        def fake_http_get(url: str, *, params=None, headers=None, timeout=None):
            calls.append(url)
            return {"items": [{"title": "cached item"}]}

        service = AShareEnrichmentService(
            http_get=fake_http_get,
            source_mode="a_stock_data",
            cache_ttl_seconds=0,
            min_interval_seconds=30,
            time_provider=lambda: now[0],
        )

        first = service.get_enrichment("600519")
        now[0] = 1001.0
        second = service.get_enrichment("600519")

        self.assertEqual(first["status"], "available")
        self.assertEqual(second["status"], "degraded")
        self.assertEqual(second["diagnostics"]["rate_limited_channels"], list(AShareEnrichmentService.CHANNELS))
        self.assertEqual(second["diagnostics"]["cache"]["stale_hits"], 5)
        self.assertEqual(len(calls), 5)

    def test_a_stock_data_source_mode_degrades_failed_channel_only(self) -> None:
        from src.services.a_share_enrichment_service import AShareEnrichmentService

        def fake_http_get(url: str, *, params=None, headers=None, timeout=None):
            if url.endswith("/research"):
                raise TimeoutError("research timeout")
            return {"items": [{"title": f"{url} item"}]}

        payload = AShareEnrichmentService(
            http_get=fake_http_get,
            source_mode="a_stock_data",
            min_interval_seconds=0,
        ).get_enrichment("600519", stock_name="Kweichow Moutai")

        by_category = {item["category"]: item for item in payload["channels"]}
        expected_titles = {
            "announcements": "公告通道",
            "capital_flow": "资金流通道",
            "sector": "板块通道",
            "research": "研报通道",
            "dragon_tiger": "龙虎榜通道",
        }
        for category, title in expected_titles.items():
            self.assertEqual(by_category[category]["title"], title)
        self.assertEqual(payload["status"], "degraded")
        self.assertEqual(by_category["research"]["status"], "degraded")
        self.assertEqual(by_category["announcements"]["status"], "available")
        self.assertEqual(payload["diagnostics"]["errors"], {"research": "TimeoutError"})
        self.assertFalse(payload["ai_used"])
        self.assertFalse(payload["public_search_used"])

    def test_default_a_stock_data_adapter_builds_useful_channels_from_public_payloads(self) -> None:
        from src.services.a_share_enrichment_service import AShareEnrichmentService

        calls: list[tuple[str, str, dict]] = []

        class FakeResponse:
            def __init__(self, payload: dict) -> None:
                self._payload = payload
                self.status_code = 200
                self.content = b"{}"

            def raise_for_status(self) -> None:
                return None

            def json(self) -> dict:
                return self._payload

        class FakeRequests:
            @staticmethod
            def get(url: str, params=None, headers=None, timeout=None):
                calls.append(("GET", url, params or {}))
                if "szse_stock.json" in url:
                    return FakeResponse({"stockList": [{"code": "600519", "orgId": "gssx0600519"}]})
                if "stock/fflow/kline/get" in url:
                    return FakeResponse(
                        {
                            "data": {
                                "klines": [
                                    "2026-07-07 14:58,-1200000,200000,300000,-400000,-500000",
                                    "2026-07-07 14:59,-800000,100000,200000,-300000,-400000",
                                ]
                            }
                        }
                    )
                if "slist/get" in url:
                    return FakeResponse(
                        {
                            "data": {
                                "diff": [
                                    {"f14": "白酒", "f12": "BK0477", "f3": -1.2, "f128": "贵州茅台"},
                                    {"f14": "贵州板块", "f12": "BK0159", "f3": -0.6, "f128": "中航重机"},
                                ]
                            }
                        }
                    )
                if "report/list" in url:
                    return FakeResponse(
                        {
                            "data": [
                                {
                                    "title": "贵州茅台跟踪报告：渠道库存保持健康",
                                    "emRatingName": "买入",
                                    "orgSName": "中信证券",
                                    "publishDate": "2026-07-07 08:00:00",
                                }
                            ]
                        }
                    )
                if "datacenter-web.eastmoney.com" in url:
                    return FakeResponse(
                        {
                            "result": {
                                "data": [
                                    {
                                        "TRADE_DATE": "2026-07-06 00:00:00",
                                        "EXPLANATION": "日价格振幅达到15%",
                                        "BILLBOARD_NET_AMT": 33000000,
                                        "TURNOVERRATE": 8.5,
                                    }
                                ]
                            }
                        }
                    )
                raise AssertionError(f"unexpected GET {url}")

            @staticmethod
            def post(url: str, data=None, params=None, headers=None, timeout=None):
                calls.append(("POST", url, data or params or {}))
                if "hisAnnouncement/query" in url:
                    return FakeResponse(
                        {
                            "announcements": [
                                {
                                    "announcementTitle": "2025年年度权益分派实施公告",
                                    "announcementTypeName": "分红",
                                    "announcementTime": 1783382400000,
                                    "announcementId": "123456",
                                }
                            ]
                        }
                    )
                raise AssertionError(f"unexpected POST {url}")

        with patch.dict(sys.modules, {"requests": FakeRequests}):
            payload = AShareEnrichmentService(
                source_mode="a_stock_data",
                http_enabled=True,
                min_interval_seconds=0,
            ).get_enrichment(
                "600519.SH",
                stock_name="贵州茅台",
                profile={"sector": "消费", "industry": "白酒"},
                quote={"current_price": 1188.8, "change_percent": -1.5},
            )

        self.assertEqual(payload["source"], "a_stock_data_skill_adapter")
        self.assertEqual(payload["status"], "available")
        by_category = {item["category"]: item for item in payload["channels"]}
        self.assertIn("2025年年度权益分派实施公告", by_category["announcements"]["summary"])
        self.assertIn("主力资金", by_category["capital_flow"]["summary"])
        self.assertIn("-2M", by_category["capital_flow"]["summary"])
        self.assertIn("白酒", by_category["sector"]["summary"])
        self.assertIn("当前背景", by_category["sector"]["summary"])
        self.assertNotIn("current context", by_category["sector"]["summary"])
        self.assertIn("贵州茅台跟踪报告", by_category["research"]["summary"])
        self.assertIn("2026-07-06", by_category["dragon_tiger"]["summary"])
        self.assertTrue(any("push2.eastmoney.com/api/qt/stock/fflow/kline/get" in url for _method, url, _params in calls))
        self.assertTrue(any("www.cninfo.com.cn/new/hisAnnouncement/query" in url for _method, url, _params in calls))
        self.assertFalse(payload["ai_used"])
        self.assertFalse(payload["public_search_used"])

    def test_checked_empty_fund_flow_reports_clear_degradation_not_reserved_lane(self) -> None:
        from src.services.a_share_enrichment_service import AShareEnrichmentService

        def fake_http_get(url: str, *, params=None, headers=None, timeout=None):
            if url.endswith("/capital_flow"):
                return {"checked": True, "items": []}
            if url.endswith("/sector"):
                return {"checked": True, "concepts": ["白酒"], "industry": "食品饮料"}
            if url.endswith("/announcements"):
                return {"checked": True, "items": []}
            if url.endswith("/research"):
                return {"checked": True, "items": []}
            if url.endswith("/dragon_tiger"):
                return {"checked": True, "items": []}
            return {}

        payload = AShareEnrichmentService(
            http_get=fake_http_get,
            source_mode="a_stock_data",
            min_interval_seconds=0,
        ).get_enrichment("600519", stock_name="贵州茅台", quote={"change_percent": -1.5})

        fund_flow = {item["category"]: item for item in payload["channels"]}["capital_flow"]
        self.assertEqual(fund_flow["status"], "degraded")
        self.assertIn("资金流通道已查询", fund_flow["summary"])
        self.assertNotIn("reserved Eastmoney", fund_flow["summary"])

    def test_default_adapter_timeout_keeps_checked_channel_copy(self) -> None:
        from src.services.a_share_enrichment_service import AShareEnrichmentService

        class FakeRequests:
            @staticmethod
            def get(url: str, params=None, headers=None, timeout=None):
                if "report/list" in url:
                    raise TimeoutError("research timeout")
                raise TimeoutError("skip other channels")

            @staticmethod
            def post(url: str, data=None, params=None, headers=None, timeout=None):
                raise TimeoutError("skip other channels")

        with patch.dict(sys.modules, {"requests": FakeRequests}):
            payload = AShareEnrichmentService(
                source_mode="a_stock_data",
                http_enabled=True,
                min_interval_seconds=0,
            ).get_enrichment("600519", stock_name="贵州茅台")

        by_category = {item["category"]: item for item in payload["channels"]}
        self.assertIn("research", by_category)
        research = by_category["research"]
        self.assertIn("已查询研报通道", research["summary"])
        self.assertNotIn("reserved Eastmoney", research["summary"])

    def test_cninfo_fallback_uses_sse_gssh_orgid_for_shanghai_codes(self) -> None:
        from src.services.a_share_enrichment_service import AShareEnrichmentService

        posted: list[dict] = []

        class FakeResponse:
            def __init__(self, payload: dict) -> None:
                self._payload = payload

            def raise_for_status(self) -> None:
                return None

            def json(self) -> dict:
                return self._payload

        class FakeRequests:
            @staticmethod
            def get(url: str, params=None, headers=None, timeout=None):
                return FakeResponse({"stockList": []})

            @staticmethod
            def post(url: str, data=None, params=None, headers=None, timeout=None):
                posted.append(data or {})
                return FakeResponse(
                    {
                        "announcements": [
                            {
                                "announcementTitle": "贵州茅台2025年年度权益分派实施公告",
                                "announcementTime": 1782057600000,
                                "announcementId": "123456",
                            }
                        ]
                    }
                )

        payload = AShareEnrichmentService()._fetch_cninfo_announcements(FakeRequests, "600519", timeout=1)

        self.assertEqual(posted[0]["stock"], "600519,gssh0600519")
        self.assertEqual(payload["items"][0]["title"], "贵州茅台2025年年度权益分派实施公告")

    def test_sector_channel_uses_moutai_local_fallback_when_public_source_empty(self) -> None:
        from src.services.a_share_enrichment_service import AShareEnrichmentService

        def fake_http_get(url: str, *, params=None, headers=None, timeout=None):
            if url.endswith("/sector"):
                return {"checked": True, "concepts": [], "industry": ""}
            return {"checked": True, "items": []}

        payload = AShareEnrichmentService(
            http_get=fake_http_get,
            source_mode="a_stock_data",
            min_interval_seconds=0,
        ).get_enrichment("600519", stock_name="贵州茅台")

        sector = {item["category"]: item for item in payload["channels"]}["sector"]
        self.assertEqual(sector["status"], "available")
        self.assertIn("白酒", sector["summary"])
        self.assertIn("消费", sector["summary"])
        self.assertNotIn("no usable sector tags", sector["summary"])


if __name__ == "__main__":
    unittest.main()
