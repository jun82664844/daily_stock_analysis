# -*- coding: utf-8 -*-
from __future__ import annotations

import unittest

from src.services.public_market_event_service import PublicMarketEventService


def _source(status: str = "fresh") -> dict:
    return {
        "source": "unit_public_news",
        "status": status,
        "observed_at": "2026-07-14T02:00:00Z",
    }


def _headline(title: str, published_at: str | None = "2026-07-14T02:00:00Z") -> dict:
    return {
        "title": title,
        "summary": f"{title} 的公开信息摘要。",
        "publisher": "Unit News",
        "published_at": published_at,
        "url": "https://example.com/news",
        "source_state": _source(),
    }


def _security(symbol: str, name: str, market: str) -> dict:
    return {
        "symbol": symbol,
        "name": name,
        "market": market,
        "source_state": _source(),
    }


class PublicMarketEventServiceTestCase(unittest.TestCase):
    def test_classifies_public_headlines_without_ai(self) -> None:
        markets = [{
            "market": "cn",
            "headlines": [
                _headline("贵州茅台发布业绩预增公告"),
                _headline("公司宣布派息及股份回购"),
                _headline("交易所公布停牌与复牌安排"),
                _headline("美联储公布最新利率决定"),
                _headline("企业完成收购并签署合作协议"),
                _headline("今日市场成交保持活跃"),
            ],
        }]

        events = PublicMarketEventService().build(markets, "2026-07-14T03:00:00Z")

        self.assertEqual(
            [event["category"] for event in events],
            ["earnings", "dividend", "trading_status", "macro", "corporate", "market"],
        )
        self.assertTrue(all(event["classification_source"] == "keyword_rules" for event in events))

    def test_links_only_symbols_or_names_present_in_title(self) -> None:
        markets = [{
            "market": "us",
            "attention": [_security("AAPL", "Apple Inc.", "us")],
            "gainers": [_security("NVDA", "NVIDIA", "us")],
            "headlines": [
                _headline("AAPL earnings results published"),
                _headline("NVIDIA announces new partnership"),
                _headline("Technology shares move before the open"),
            ],
        }]

        events = PublicMarketEventService().build(markets, "2026-07-14T03:00:00Z")

        self.assertEqual(events[0]["symbol"], "AAPL")
        self.assertEqual(events[1]["symbol"], "NVDA")
        self.assertIsNone(events[2]["symbol"])

    def test_classifies_chinese_net_profit_headlines_as_earnings(self) -> None:
        markets = [{
            "market": "cn",
            "headlines": [_headline("Company expects \u51c0\u5229\u6da6 to decline year over year")],
        }]

        events = PublicMarketEventService().build(markets, "2026-07-14T03:00:00Z")

        self.assertEqual(events[0]["category"], "earnings")

    def test_explicit_exchange_symbol_overrides_mixed_feed_market(self) -> None:
        markets = [{
            "market": "hk",
            "headlines": [_headline("Issuer (600161.SH) expects \u51c0\u5229\u6da6 to decline")],
        }]

        events = PublicMarketEventService().build(markets, "2026-07-14T03:00:00Z")

        self.assertEqual(events[0]["market"], "cn")
        self.assertEqual(events[0]["symbol"], "600161.SH")

    def test_does_not_link_ambiguous_short_us_symbols_without_cashtag(self) -> None:
        markets = [{
            "market": "us",
            "attention": [
                _security("A", "Agilent Technologies", "us"),
                _security("AI", "C3.ai", "us"),
                _security("MU", "Micron Technology", "us"),
            ],
            "headlines": [
                _headline("A broad AI market update"),
                _headline("$MU earnings results published"),
            ],
        }]

        events = PublicMarketEventService().build(markets, "2026-07-14T03:00:00Z")

        self.assertIsNone(events[0]["symbol"])
        self.assertEqual(events[1]["symbol"], "MU")

    def test_macro_rules_win_over_buyback_and_order_terms(self) -> None:
        markets = [{
            "market": "cn",
            "headlines": [
                _headline("Central bank \u592e\u884c conducts \u9006\u56de\u8d2d operations"),
                _headline("US \u5de5\u5382\u8ba2\u5355 data released"),
            ],
        }]

        events = PublicMarketEventService().build(markets, "2026-07-14T03:00:00Z")

        self.assertEqual([event["category"] for event in events], ["macro", "macro"])

    def test_deduplicates_prioritizes_published_time_and_preserves_retrieved_time(self) -> None:
        duplicate = _headline("Market bulletin", "2026-07-14T01:00:00Z")
        markets = [
            {"market": "cn", "headlines": [duplicate, dict(duplicate)]},
            {"market": "hk", "headlines": [_headline("HK filing update", "2026-07-14T03:00:00Z")]},
            {"market": "us", "headlines": [_headline("US market note", None)]},
        ]

        events = PublicMarketEventService().build(markets, "2026-07-14T04:00:00Z")

        self.assertEqual(len(events), 3)
        self.assertEqual(events[0]["market"], "hk")
        unknown = next(event for event in events if event["market"] == "us")
        self.assertEqual(unknown["event_time"], "2026-07-14T04:00:00Z")
        self.assertEqual(unknown["time_kind"], "retrieved")
        self.assertEqual(len({event["event_id"] for event in events}), 3)

    def test_limits_each_market_and_total_output(self) -> None:
        markets = [
            {
                "market": market,
                "headlines": [
                    _headline(f"{market} market item {index}", f"2026-07-14T{index:02d}:00:00Z")
                    for index in range(10)
                ],
            }
            for market in ("cn", "hk", "us")
        ]

        events = PublicMarketEventService(max_events_per_market=3, max_events_total=7).build(
            markets,
            "2026-07-14T12:00:00Z",
        )

        self.assertEqual(len(events), 7)
        self.assertLessEqual(max(sum(event["market"] == market for event in events) for market in ("cn", "hk", "us")), 3)


if __name__ == "__main__":
    unittest.main()
