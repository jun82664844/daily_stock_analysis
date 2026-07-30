from __future__ import annotations

import hashlib
import json
import os
import unittest
from datetime import date
from typing import Any, Dict, List
from unittest.mock import patch

from src.services.public_market_calendar_service import PublicMarketCalendarService
from src.services.public_market_event_reaction_service import (
    PublicMarketEventReactionService,
)


def _security(symbol: str, name: str, market: str) -> dict:
    return {"symbol": symbol, "name": name, "market": market}


def _history_event(
    event_id: str,
    *,
    market: str,
    symbol: str,
    event_time: str,
) -> Dict[str, Any]:
    return {
        "event_id": event_id,
        "market": market,
        "category": "dividend",
        "title": f"{symbol} historical event",
        "summary": None,
        "symbol": symbol,
        "name": symbol,
        "sector": None,
        "event_time": event_time,
        "time_kind": "observed",
        "publisher": "public provider",
        "url": "https://example.com/event",
        "source_state": {
            "source": "provider_event_history",
            "status": "fresh",
            "observed_at": event_time,
            "fetched_at": "2026-07-30T00:00:00+00:00",
            "delay_seconds": None,
            "warning_code": None,
        },
        "classification_source": "provider_event_history",
        "schedule_type": "ex_dividend",
        "relevance_score": 85,
        "importance": "high",
        "relevance_reasons": ["provider_event_history"],
        "source_count": 1,
        "source_publishers": ["public provider"],
        "source_records": [],
    }


def _rows() -> List[Dict[str, Any]]:
    return [
        {
            "date": f"2026-07-{day:02d}",
            "close": 100.0 + index,
            "volume": 100.0 + index,
        }
        for index, day in enumerate(range(1, 31))
    ]


class PublicEventHistoryCoverageV138TestCase(unittest.TestCase):
    def test_existing_scheduled_event_ids_remain_stable(self) -> None:
        event = PublicMarketCalendarService._event(
            market="us",
            category="earnings",
            schedule_type="earnings_release",
            scheduled=date(2026, 7, 20),
            title="Apple earnings",
            summary="Scheduled event",
            symbol="AAPL",
            name="Apple",
            publisher="Yahoo Finance",
            source="yfinance_public_calendar",
            url="https://finance.yahoo.com/quote/AAPL/",
            as_of="2026-07-30T00:00:00Z",
        )
        old_raw = (
            "yfinance_public_calendar\nus\nAAPL\n"
            "earnings_release\n2026-07-20T00:00:00Z"
        ).encode("utf-8")

        self.assertEqual(
            event["event_id"],
            hashlib.sha256(old_raw).hexdigest()[:20],
        )

    def test_endpoint_requests_v138_history_per_market(self) -> None:
        from api.v1.endpoints.market_workspace import (
            _load_event_reaction_events,
        )

        calls: List[Dict[str, Any]] = []

        def load(sections, _as_of, **kwargs):
            calls.append({"market": sections[0]["market"], **kwargs})
            return []

        with (
            patch.dict(
                os.environ,
                {
                    "PLATFORM_PUBLIC_EVENT_HISTORY_V138_ENABLED": "true",
                    "PLATFORM_PUBLIC_EVENT_HISTORY_V138_PAST_DAYS": "180",
                },
            ),
            patch(
                (
                    "api.v1.endpoints.market_workspace."
                    "_public_market_calendar_service.load"
                ),
                side_effect=load,
            ),
        ):
            payload = _load_event_reaction_events()

        self.assertEqual(
            {call["market"] for call in calls},
            {"cn", "hk", "us"},
        )
        self.assertTrue(all(call["past_days"] == 180 for call in calls))
        self.assertTrue(
            all(call["include_observed_history"] for call in calls)
        )
        self.assertEqual(len(payload["market_sources"]), 3)

    def test_cninfo_actual_disclosure_is_observed_and_visible_symbols_are_kept(self) -> None:
        rows = [
            {
                "股票代码": "300750",
                "股票简称": "宁德时代",
                "首次预约": "2026-07-25",
                "初次变更": None,
                "二次变更": None,
                "三次变更": None,
                "实际披露": "2026-07-25",
            },
            {
                "股票代码": "600000",
                "股票简称": "非指定股票",
                "首次预约": "2026-07-29",
                "初次变更": None,
                "二次变更": None,
                "三次变更": None,
                "实际披露": "2026-07-29",
            },
        ]
        service = PublicMarketCalendarService(
            cninfo_loader=lambda _period: rows,
            yahoo_loader=lambda _symbol: {},
            fomc_loader=lambda _year: [],
        )

        events = service.load(
            [{
                "market": "cn",
                "attention": [_security("300750.SZ", "宁德时代", "cn")],
            }],
            "2026-07-30T00:00:00Z",
            past_days=180,
            future_days=0,
            include_historical=True,
            include_observed_history=True,
        )

        self.assertEqual({event["symbol"] for event in events}, {"300750.SZ"})
        self.assertEqual(events[0]["time_kind"], "observed")
        self.assertEqual(
            events[0]["classification_source"],
            "provider_event_history",
        )

    def test_hk_public_chart_actions_are_independent_from_earnings_history(self) -> None:
        service = PublicMarketCalendarService(
            yahoo_loader=lambda _symbol: {},
            historical_earnings_loader=lambda _symbol: [],
            corporate_action_loader=lambda _symbol: [
                {
                    "kind": "dividend",
                    "date": date(2026, 6, 10),
                    "amount": 1.02,
                }
            ],
            cninfo_loader=lambda _period: [],
            fomc_loader=lambda _year: [],
        )

        events = service.load(
            [{
                "market": "hk",
                "attention": [_security("9988.HK", "阿里巴巴-W", "hk")],
            }],
            "2026-07-30T00:00:00Z",
            past_days=180,
            future_days=0,
            include_historical=True,
            include_observed_history=True,
            fail_on_source_unavailable=True,
        )

        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["symbol"], "9988.HK")
        self.assertEqual(events[0]["schedule_type"], "ex_dividend")
        self.assertEqual(events[0]["time_kind"], "observed")
        self.assertEqual(
            events[0]["classification_source"],
            "provider_event_history",
        )

    def test_public_chart_action_parser_is_bounded_and_uses_no_key(self) -> None:
        payload = {
            "chart": {
                "result": [{
                    "events": {
                        "dividends": {
                            "one": {
                                "date": 1781049600,
                                "amount": 1.02,
                            }
                        },
                        "splits": {
                            "two": {
                                "date": 1778025600,
                                "splitRatio": "2:1",
                            }
                        },
                    }
                }]
            }
        }

        class Response:
            def raise_for_status(self) -> None:
                return None

            def iter_content(self, chunk_size: int):
                del chunk_size
                yield json.dumps(payload).encode("utf-8")

            def close(self) -> None:
                return None

        with patch(
            "requests.get",
            return_value=Response(),
        ) as get:
            actions = PublicMarketCalendarService._fetch_yahoo_corporate_actions(
                "9988.HK"
            )

        self.assertEqual({action["kind"] for action in actions}, {"dividend", "split"})
        self.assertEqual(get.call_args.kwargs["params"]["range"], "1y")
        self.assertNotIn("api_key", get.call_args.kwargs["params"])

    def test_reaction_service_accepts_history_events_and_reserves_each_market(self) -> None:
        events = [
            _history_event(
                f"us-{index}",
                market="us",
                symbol=symbol,
                event_time=f"2026-07-{29 - index:02d}T00:00:00+00:00",
            )
            for index, symbol in enumerate(("AAPL", "MSFT", "NVDA", "AMZN"))
        ]
        events.extend([
            _history_event(
                "cn-one",
                market="cn",
                symbol="300750.SZ",
                event_time="2026-07-25T00:00:00+00:00",
            ),
            _history_event(
                "hk-one",
                market="hk",
                symbol="9988.HK",
                event_time="2026-06-10T00:00:00+00:00",
            ),
        ])

        payload = PublicMarketEventReactionService(
            event_loader=lambda: {"events": events},
            history_loader=lambda symbol: {
                "symbol": symbol,
                "source": "yahoo_chart_public",
                "data": _rows(),
            },
            clock=lambda: "2026-07-30T00:00:00+00:00",
            max_events=6,
            allow_event_history=True,
        ).build()

        self.assertEqual(
            {item["market"] for item in payload["items"]},
            {"cn", "hk", "us"},
        )
        by_id = {item["event_id"]: item for item in payload["items"]}
        self.assertEqual(by_id["cn-one"]["event_time_kind"], "observed")
        self.assertEqual(
            by_id["hk-one"]["classification_source"],
            "provider_event_history",
        )

    def test_history_prices_request_one_year_for_older_event_windows(self) -> None:
        response_payload = {
            "chart": {
                "result": [{
                    "timestamp": [1782864000, 1782950400],
                    "indicators": {
                        "quote": [{
                            "close": [100.0, 101.0],
                            "volume": [1000, 1100],
                        }]
                    },
                }]
            }
        }

        class Response:
            def raise_for_status(self) -> None:
                return None

            def iter_content(self, chunk_size: int):
                del chunk_size
                import json

                yield json.dumps(response_payload).encode("utf-8")

            def close(self) -> None:
                return None

        with patch(
            "src.services.public_market_event_reaction_service.requests.get",
            return_value=Response(),
        ) as get:
            service = PublicMarketEventReactionService(
                event_loader=lambda: {"events": []},
            )
            service._fetch_yahoo_history("9988.HK")

        self.assertEqual(get.call_args.kwargs["params"]["range"], "1y")


if __name__ == "__main__":
    unittest.main()
