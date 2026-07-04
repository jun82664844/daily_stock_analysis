import time
import unittest
from unittest.mock import MagicMock

from src.services.basic_query_service import BasicQueryService
from src.services.market_data_cache import MarketDataCache


class MarketDataCacheTestCase(unittest.TestCase):
    def test_cache_returns_value_until_ttl_expires(self):
        cache = MarketDataCache(default_ttl_seconds=60)
        cache.set("quote:AAPL", {"price": 200}, source="yahoo_chart")

        hit = cache.get("quote:AAPL")

        self.assertIsNotNone(hit)
        self.assertEqual(hit.value["price"], 200)
        self.assertEqual(hit.source, "yahoo_chart")
        self.assertEqual(hit.freshness, "cached")

    def test_cache_marks_stale_after_ttl(self):
        cache = MarketDataCache(default_ttl_seconds=0)
        cache.set("quote:AAPL", {"price": 200}, source="yahoo_chart")
        time.sleep(0.01)

        hit = cache.get("quote:AAPL")

        self.assertIsNotNone(hit)
        self.assertEqual(hit.freshness, "stale")

    def test_basic_query_reuses_cached_quote(self):
        cache = MarketDataCache(default_ttl_seconds=60)
        stock_service = MagicMock()
        stock_service.get_realtime_quote.return_value = {
            "stock_code": "AAPL",
            "stock_name": "Apple Inc.",
            "current_price": 200,
            "source": "unit",
        }
        stock_service.get_history_data.return_value = {"data": []}
        service = BasicQueryService(stock_service=stock_service, cache=cache)

        first = service.get_snapshot("AAPL")
        second = service.get_snapshot("AAPL")

        self.assertEqual(first["quote"]["freshness"], "fresh")
        self.assertEqual(second["quote"]["freshness"], "cached")
        stock_service.get_realtime_quote.assert_called_once_with("AAPL")
