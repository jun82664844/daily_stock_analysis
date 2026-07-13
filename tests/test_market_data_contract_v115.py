# -*- coding: utf-8 -*-
import unittest
from unittest.mock import MagicMock

from api.v1.schemas.basic_query import BasicStockSnapshot
from src.services.basic_query_service import BasicQueryService
from src.services.market_data_cache import MarketDataCache
from src.services.market_data_contract import MarketDataContractService


class MarketDataContractV115TestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.service = MarketDataContractService()

    def test_fresh_candidate_wins_without_averaging_conflicting_values(self) -> None:
        decision = self.service.arbitrate_fact(
            domain="quote",
            field="current_price",
            candidates=[
                {
                    "value": 100.0,
                    "source": "preferred_but_stale",
                    "freshness": "stale",
                    "observed_at": "2026-07-12T09:20:00Z",
                },
                {
                    "value": 103.0,
                    "source": "secondary_live",
                    "freshness": "fresh",
                    "observed_at": "2026-07-12T09:19:00Z",
                },
            ],
            source_priority=("preferred_but_stale", "secondary_live"),
        )

        self.assertEqual(decision["value"], 103.0)
        self.assertEqual(decision["source"], "secondary_live")
        self.assertTrue(decision["conflict"])
        self.assertEqual(decision["resolution"], "freshness_then_priority_then_observed_at")

    def test_source_priority_breaks_equal_freshness_ties(self) -> None:
        decision = self.service.arbitrate_fact(
            domain="quote",
            field="current_price",
            candidates=[
                {"value": 101.0, "source": "secondary", "freshness": "fresh"},
                {"value": 100.0, "source": "primary", "freshness": "fresh"},
            ],
            source_priority=("primary", "secondary"),
        )

        self.assertEqual(decision["value"], 100.0)
        self.assertEqual(decision["source"], "primary")
        self.assertTrue(decision["conflict"])

    def test_event_deduplication_normalizes_tracking_parameters(self) -> None:
        items, metrics = self.service.deduplicate_records(
            [
                {
                    "title": "Company filing",
                    "url": "https://example.com/filing?id=7&utm_source=feed",
                    "published_at": "2026-07-12T09:00:00Z",
                },
                {
                    "title": "Company filing",
                    "url": "https://example.com/filing?utm_medium=email&id=7",
                    "published_at": "2026-07-12T09:00:00Z",
                },
                {
                    "title": "Different filing",
                    "url": "https://example.com/filing?id=8",
                    "published_at": "2026-07-12T09:10:00Z",
                },
            ]
        )

        self.assertEqual(len(items), 2)
        self.assertEqual(metrics, {"input_count": 3, "output_count": 2, "removed_count": 1})

    def test_event_deduplication_preserves_semantic_query_parameters(self) -> None:
        items, metrics = self.service.deduplicate_records(
            [
                {"title": "Exchange filing", "url": "https://example.com/filing?id=7&source=exchange_a"},
                {"title": "Exchange filing", "url": "https://example.com/filing?id=7&source=exchange_b"},
            ]
        )

        self.assertEqual(len(items), 2)
        self.assertEqual(metrics["removed_count"], 0)

    def test_value_records_with_same_label_but_different_values_are_not_collapsed(self) -> None:
        items, metrics = self.service.deduplicate_records(
            [
                {"label": "Market cap", "value": 100, "source": "provider_a"},
                {"label": "Market cap", "value": 110, "source": "provider_a"},
            ]
        )

        self.assertEqual([item["value"] for item in items], [100, 110])
        self.assertEqual(metrics["removed_count"], 0)

    def test_snapshot_contract_exposes_selected_sources_and_field_provenance(self) -> None:
        contract = self.service.build_snapshot_contract(
            symbol="AAPL",
            market="us",
            source_priority={
                "quote": ("us_realtime", "yfinance"),
                "history": ("us_history", "yfinance"),
                "profile": ("yfinance_profile",),
            },
            quote={
                "current_price": 200.0,
                "change_percent": 1.5,
                "source": "us_realtime",
                "freshness": "fresh",
                "update_time": "2026-07-12T09:30:00Z",
            },
            history={
                "source": "us_history",
                "freshness": "cached",
                "data": [{"date": "2026-07-11", "close": 197.0}],
            },
            profile={
                "company_name": "Apple Inc.",
                "market_cap": 4_500_000_000_000,
                "source": "yfinance_profile",
                "freshness": "cached",
            },
            diagnostics={"cache": {"quote": "miss", "history": "hit", "profile": "hit"}},
            deduplication={"input_count": 4, "output_count": 3, "removed_count": 1},
        )

        self.assertEqual(contract["contract_version"], "v1")
        self.assertEqual(contract["selected_sources"]["quote"]["source"], "us_realtime")
        self.assertEqual(contract["field_provenance"]["quote.current_price"], "us_realtime")
        self.assertEqual(contract["field_provenance"]["profile.market_cap"], "yfinance_profile")
        self.assertTrue(contract["policy"]["no_averaging"])
        self.assertEqual(contract["deduplication"]["removed_count"], 1)
        self.assertTrue(contract["informational_only"])

    def test_basic_query_publishes_canonical_contract_through_response_schema(self) -> None:
        stock_service = MagicMock()
        stock_service.get_realtime_quote.side_effect = lambda code: {
            "stock_code": code,
            "stock_name": "Apple Inc." if code == "AAPL" else code,
            "current_price": 200.0,
            "change_percent": 1.5,
            "update_time": "2026-07-12T09:30:00Z",
            "source": "us_realtime",
        }
        stock_service.get_history_data.return_value = {
            "stock_code": "AAPL",
            "source": "us_history",
            "data": [{"date": "2026-07-11", "close": 197.0, "volume": 1000}],
        }
        stock_service.get_basic_company_profile.return_value = {
            "company_name": "Apple Inc.",
            "market_cap": 4_500_000_000_000,
            "source": "yfinance_profile",
        }
        service = BasicQueryService(
            stock_service=stock_service,
            cache=MarketDataCache(default_ttl_seconds=60),
        )

        snapshot = service.get_snapshot("AAPL")
        serialized = BasicStockSnapshot.model_validate(snapshot).model_dump()

        contract = serialized["canonical_data"]
        self.assertEqual(contract["symbol"], "AAPL")
        self.assertEqual(contract["selected_sources"]["quote"]["source"], "us_realtime")
        self.assertEqual(contract["field_provenance"]["quote.current_price"], "us_realtime")
        self.assertFalse(contract["ai_used"])


if __name__ == "__main__":
    unittest.main()
