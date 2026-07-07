# -*- coding: utf-8 -*-
import unittest


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


if __name__ == "__main__":
    unittest.main()
