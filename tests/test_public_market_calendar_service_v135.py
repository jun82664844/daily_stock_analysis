from __future__ import annotations

import json
import time
import unittest
from datetime import date

from src.services.public_market_calendar_service import PublicMarketCalendarService


def _security(symbol: str, name: str, market: str) -> dict:
    return {
        "symbol": symbol,
        "name": name,
        "market": market,
        "source_state": {"source": "unit_rankings", "status": "fresh"},
    }


def _sections() -> list[dict]:
    return [
        {"market": "cn", "attention": [_security("600519.SH", "贵州茅台", "cn")]},
        {"market": "hk", "attention": [_security("0700.HK", "腾讯控股", "hk")]},
        {"market": "us", "attention": [_security("AAPL", "Apple Inc.", "us")]},
    ]


class PublicMarketCalendarServiceV135TestCase(unittest.TestCase):
    def test_builds_scheduled_events_for_three_markets_without_forecast_values(self) -> None:
        def cninfo_loader(_period: str):
            return [{
                "股票代码": "600519",
                "股票简称": "贵州茅台",
                "首次预约": date(2026, 8, 18),
                "初次变更": date(2026, 8, 12),
                "二次变更": None,
                "三次变更": None,
                "实际披露": None,
            }]

        def yahoo_loader(symbol: str):
            return {
                "Earnings Date": [date(2026, 8, 12) if symbol == "0700.HK" else date(2026, 7, 31)],
                "Ex-Dividend Date": date(2026, 8, 5),
                "Earnings High": 999.0,
                "Revenue Average": 123456789,
            }

        def fomc_loader(_year: int):
            return [{"start": date(2026, 8, 20), "end": date(2026, 8, 21)}]

        service = PublicMarketCalendarService(
            cninfo_loader=cninfo_loader,
            yahoo_loader=yahoo_loader,
            fomc_loader=fomc_loader,
            clock=lambda: 100.0,
        )

        events = service.load(_sections(), "2026-07-30T00:00:00Z")

        self.assertEqual({event["market"] for event in events}, {"cn", "hk", "us"})
        self.assertTrue(all(event["time_kind"] == "scheduled" for event in events))
        self.assertTrue(all(event["classification_source"] == "provider_schedule" for event in events))
        self.assertTrue(all(event["source_state"]["status"] == "fresh" for event in events))
        self.assertIn("600519.SH", {event.get("symbol") for event in events})
        self.assertIn("0700.HK", {event.get("symbol") for event in events})
        self.assertIn("AAPL", {event.get("symbol") for event in events})
        serialized = json.dumps(events, ensure_ascii=False)
        self.assertNotIn("999", serialized)
        self.assertNotIn("123456789", serialized)

    def test_cninfo_uses_latest_appointment_and_skips_already_disclosed_rows(self) -> None:
        rows = [
            {
                "股票代码": "000001",
                "股票简称": "平安银行",
                "首次预约": "2026-08-15",
                "初次变更": "2026-08-18",
                "二次变更": "2026-08-20",
                "三次变更": None,
                "实际披露": None,
            },
            {
                "股票代码": "600519",
                "股票简称": "贵州茅台",
                "首次预约": "2026-08-16",
                "初次变更": None,
                "二次变更": None,
                "三次变更": None,
                "实际披露": "2026-08-10",
            },
        ]
        service = PublicMarketCalendarService(
            cninfo_loader=lambda _period: rows,
            yahoo_loader=lambda _symbol: {},
            fomc_loader=lambda _year: [],
        )

        events = service.load(
            [{"market": "cn", "attention": [_security("000001.SZ", "平安银行", "cn")]}],
            "2026-07-30T00:00:00Z",
        )

        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["symbol"], "000001.SZ")
        self.assertEqual(events[0]["event_time"], "2026-08-20T00:00:00Z")
        self.assertEqual(events[0]["schedule_type"], "earnings_release")

    def test_marks_memory_cache_and_stale_fallback_per_source(self) -> None:
        calls = {"count": 0}
        now = {"value": 100.0}
        should_fail = {"value": False}

        def yahoo_loader(_symbol: str):
            calls["count"] += 1
            if should_fail["value"]:
                raise RuntimeError("temporary yahoo failure")
            return {"Earnings Date": [date(2026, 8, 2)]}

        service = PublicMarketCalendarService(
            cninfo_loader=lambda _period: [],
            yahoo_loader=yahoo_loader,
            fomc_loader=lambda _year: [],
            cache_ttl_seconds=60,
            stale_ttl_seconds=600,
            clock=lambda: now["value"],
        )
        sections = [{"market": "us", "attention": [_security("AAPL", "Apple Inc.", "us")]}]

        fresh = service.load(sections, "2026-07-30T00:00:00Z")
        now["value"] = 120.0
        cached = service.load(sections, "2026-07-30T00:00:00Z")
        should_fail["value"] = True
        now["value"] = 180.0
        stale = service.load(sections, "2026-07-30T00:00:00Z")

        self.assertEqual(calls["count"], 2)
        self.assertEqual(fresh[0]["source_state"]["status"], "fresh")
        self.assertEqual(cached[0]["source_state"]["status"], "cached")
        self.assertEqual(stale[0]["source_state"]["status"], "stale")
        self.assertEqual(stale[0]["source_state"]["warning_code"], "calendar_source_stale")

    def test_timeout_in_one_source_does_not_block_other_market_events(self) -> None:
        def slow_cninfo(_period: str):
            time.sleep(0.15)
            return []

        service = PublicMarketCalendarService(
            cninfo_loader=slow_cninfo,
            yahoo_loader=lambda _symbol: {"Earnings Date": [date(2026, 8, 1)]},
            fomc_loader=lambda _year: [],
            timeout_seconds=0.03,
        )

        started = time.monotonic()
        events = service.load(_sections(), "2026-07-30T00:00:00Z")
        elapsed = time.monotonic() - started

        self.assertLess(elapsed, 0.12)
        self.assertTrue(any(event.get("symbol") == "AAPL" for event in events))
        self.assertFalse(any(event.get("symbol") == "600519.SH" for event in events))

    def test_bounds_window_count_urls_and_stable_ids(self) -> None:
        rows = []
        for index in range(80):
            rows.append({
                "股票代码": f"{600000 + index:06d}",
                "股票简称": f"测试{index}",
                "首次预约": date(2026, 8, 1 + index % 20),
                "初次变更": None,
                "二次变更": None,
                "三次变更": None,
                "实际披露": None,
            })
        rows.append({
            "股票代码": "000001",
            "股票简称": "过远日期",
            "首次预约": date(2026, 12, 1),
            "初次变更": None,
            "二次变更": None,
            "三次变更": None,
            "实际披露": None,
        })
        service = PublicMarketCalendarService(
            cninfo_loader=lambda _period: rows,
            yahoo_loader=lambda _symbol: {},
            fomc_loader=lambda _year: [],
            max_events=36,
        )

        first = service.load([{"market": "cn"}], "2026-07-30T00:00:00Z")
        second = service.load([{"market": "cn"}], "2026-07-30T00:00:00Z")

        self.assertEqual(len(first), 36)
        self.assertEqual([event["event_id"] for event in first], [event["event_id"] for event in second])
        self.assertTrue(all(event["url"].startswith(("http://", "https://")) for event in first))
        self.assertNotIn("000001.SZ", {event.get("symbol") for event in first})

    def test_parses_only_explicit_fomc_meeting_dates_for_requested_year(self) -> None:
        html = """
        <h4><a id="42828">2026 FOMC Meetings</a></h4>
        <div class="row fomc-meeting">
          <div class="fomc-meeting__month"><strong>July</strong></div>
          <div class="fomc-meeting__date">28-29</div>
        </div>
        <div class="row fomc-meeting">
          <div class="fomc-meeting__month"><strong>September</strong></div>
          <div class="fomc-meeting__date">15-16*</div>
        </div>
        <h4><a id="dynamic-next-year">2027 FOMC Meetings</a></h4>
        <div class="row fomc-meeting">
          <div class="fomc-meeting__month"><strong>January</strong></div>
          <div class="fomc-meeting__date">20-21</div>
        </div>
        """

        meetings = PublicMarketCalendarService.parse_fomc_html(html, 2026)

        self.assertEqual(meetings, [
            {"start": date(2026, 7, 28), "end": date(2026, 7, 29)},
            {"start": date(2026, 9, 15), "end": date(2026, 9, 16)},
        ])


if __name__ == "__main__":
    unittest.main()
