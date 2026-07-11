# -*- coding: utf-8 -*-
import time
import unittest
from unittest.mock import MagicMock, patch

from src.services.basic_query_service import BasicQueryService
from src.services.market_data_cache import MarketDataCache
from src.services.market_source_health import MarketSourceHealthRegistry


def _quote(price: float, *, source: str) -> dict:
    return {
        "stock_code": "AAPL",
        "stock_name": "Apple Inc.",
        "current_price": price,
        "change_percent": 1.25,
        "volume": 1_000_000,
        "source": source,
        "update_time": "2026-07-10T09:30:00",
    }


def _history(last_close: float, *, source: str) -> dict:
    rows = [
        {
            "date": f"2026-07-{day:02d}",
            "close": last_close - (24 - day),
            "volume": 10_000 + day,
        }
        for day in range(1, 25)
    ]
    return {
        "stock_code": "AAPL",
        "stock_name": "Apple Inc.",
        "source": source,
        "data": rows,
    }


def _profile(market_cap: float, *, source: str) -> dict:
    return {
        "stock_code": "AAPL",
        "company_name": "Apple Inc.",
        "sector": "Technology",
        "industry": "Consumer Electronics",
        "market_cap": market_cap,
        "source": source,
    }


class _LiveStockService:
    def __init__(self) -> None:
        self.quote_calls = 0
        self.history_calls = 0
        self.profile_calls = 0

    def get_realtime_quote(self, code: str) -> dict:
        self.quote_calls += 1
        return _quote(210.0, source="live_quote")

    def get_history_data(self, code: str, **_: object) -> dict:
        self.history_calls += 1
        return _history(209.0, source="live_history")

    def get_basic_company_profile(self, code: str) -> dict:
        self.profile_calls += 1
        return _profile(3_500_000_000_000.0, source="live_profile")


class PlatformMarketDataFreshnessV92TestCase(unittest.TestCase):
    def _service(self, *, stock_service: object, cache: MarketDataCache) -> BasicQueryService:
        return BasicQueryService(
            stock_service=stock_service,
            cache=cache,
            source_health=MarketSourceHealthRegistry(),
        )

    def test_fresh_cache_hit_does_not_call_live_quote_source(self) -> None:
        cache = MarketDataCache(default_ttl_seconds=60)
        cache.set("quote:AAPL", _quote(100.0, source="cached_quote"), source="cached_quote")
        stock_service = MagicMock()
        service = self._service(stock_service=stock_service, cache=cache)

        result = service._get_quote("AAPL", route=service._resolve_route("AAPL"))

        self.assertEqual(result[0]["current_price"], 100.0)
        self.assertEqual(result[1], "cached")
        self.assertEqual(result[2], "hit")
        self.assertEqual(result[6], "cache")
        stock_service.get_realtime_quote.assert_not_called()

    def test_reference_quote_skips_a_source_that_is_already_cooling_down(self) -> None:
        health = MarketSourceHealthRegistry(failure_threshold=1, cooling_seconds=60)
        health.record_timeout("a_share_realtime", elapsed_ms=600)
        service = BasicQueryService(
            stock_service=MagicMock(),
            cache=MarketDataCache(default_ttl_seconds=60),
            source_health=health,
        )

        with patch.object(service, "_fetch_reference_quote") as fetch_reference:
            payloads = service._reference_quote_payloads_for_targets([{"symbol": "000300.SH"}])

        fetch_reference.assert_not_called()
        self.assertEqual(payloads["000300.SH"]["status"], "unavailable")
        self.assertEqual(payloads["000300.SH"]["error"], "cooling_down")

    def test_stale_quote_history_and_profile_are_revalidated_by_live_sources(self) -> None:
        cache = MarketDataCache(default_ttl_seconds=0)
        cache.set("quote:AAPL", _quote(100.0, source="cached_quote"), source="cached_quote")
        cache.set("history:AAPL:daily:30", _history(99.0, source="cached_history"), source="cached_history")
        cache.set("profile:AAPL", _profile(1.0, source="cached_profile"), source="cached_profile")
        time.sleep(0.01)
        stock_service = _LiveStockService()
        service = self._service(stock_service=stock_service, cache=cache)

        with patch.object(service, "_comparison_targets_with_reference_quotes", return_value=[]):
            snapshot = service.get_snapshot("AAPL")

        self.assertEqual(snapshot["quote"]["current_price"], 210.0)
        self.assertEqual(snapshot["profile"]["market_cap"], 3_500_000_000_000.0)
        self.assertEqual(snapshot["diagnostics"]["cache"]["quote"], "revalidated")
        self.assertEqual(snapshot["diagnostics"]["cache"]["history"], "revalidated")
        self.assertEqual(snapshot["diagnostics"]["cache"]["profile"], "revalidated")
        self.assertEqual(snapshot["diagnostics"]["freshness"]["quote"], "fresh")
        self.assertEqual(snapshot["diagnostics"]["fallback"]["quote"], "live")
        self.assertEqual(snapshot["diagnostics"]["refresh"]["mode"], "stale_while_revalidate")
        self.assertTrue(snapshot["diagnostics"]["refresh"]["quote"])
        self.assertTrue(snapshot["diagnostics"]["refresh"]["history"])
        self.assertTrue(snapshot["diagnostics"]["refresh"]["profile"])
        self.assertFalse(snapshot["ai_used"])
        self.assertEqual(stock_service.quote_calls, 1)
        self.assertEqual(stock_service.history_calls, 1)
        self.assertEqual(stock_service.profile_calls, 1)

    def test_stale_quote_is_preserved_when_live_source_returns_no_data(self) -> None:
        cache = MarketDataCache(default_ttl_seconds=0)
        cache.set("quote:AAPL", _quote(101.0, source="cached_quote"), source="cached_quote")
        time.sleep(0.01)
        stock_service = MagicMock()
        stock_service.get_realtime_quote.return_value = None
        service = self._service(stock_service=stock_service, cache=cache)

        result = service._get_quote("AAPL", route=service._resolve_route("AAPL"))

        self.assertEqual(result[0]["current_price"], 101.0)
        self.assertEqual(result[1], "stale")
        self.assertEqual(result[2], "stale_fallback")
        self.assertEqual(result[6], "stale_cache")
        self.assertEqual(result[7], "unavailable")
        self.assertEqual(result[8]["consecutive_failures"], 0)
        stock_service.get_realtime_quote.assert_called_once_with("AAPL")

    def test_stale_history_is_preserved_when_live_source_times_out(self) -> None:
        cache = MarketDataCache(default_ttl_seconds=0)
        cache.set("history:AAPL:daily:30", _history(99.0, source="cached_history"), source="cached_history")
        time.sleep(0.01)
        service = self._service(stock_service=MagicMock(), cache=cache)

        with patch.object(service, "_call_with_timeout", return_value=(None, "timeout")):
            result = service._get_history("AAPL", route=service._resolve_route("AAPL"))

        self.assertEqual(result[0]["data"][-1]["close"], 99.0)
        self.assertEqual(result[1], "stale")
        self.assertEqual(result[2], "stale_fallback")
        self.assertTrue(result[5])
        self.assertEqual(result[6], "stale_cache")
        self.assertEqual(result[7], "timeout")

    def test_stale_revalidation_uses_a_shorter_timeout_budget_than_cold_fetches(self) -> None:
        cache = MarketDataCache(default_ttl_seconds=0)
        cache.set("quote:AAPL", _quote(103.0, source="cached_quote"), source="cached_quote")
        time.sleep(0.01)
        stock_service = MagicMock()

        def slow_quote(_code: str) -> dict:
            time.sleep(0.2)
            return _quote(220.0, source="slow_live_quote")

        stock_service.get_realtime_quote.side_effect = slow_quote
        service = BasicQueryService(
            stock_service=stock_service,
            cache=cache,
            source_health=MarketSourceHealthRegistry(),
            fetch_timeout_seconds=1.0,
            stale_revalidation_timeout_seconds=0.01,
        )

        started = time.perf_counter()
        result = service._get_quote("AAPL", route=service._resolve_route("AAPL"))
        elapsed = time.perf_counter() - started

        self.assertLess(elapsed, 0.1)
        self.assertEqual(result[0]["current_price"], 103.0)
        self.assertEqual(result[2], "stale_fallback")
        self.assertTrue(result[5])
        self.assertEqual(result[7], "timeout")

    def test_stale_history_fallback_also_bounds_a_missing_hk_quote_fetch(self) -> None:
        cache = MarketDataCache(default_ttl_seconds=0)
        cache.set(
            "history:HK00700:daily:30",
            _history(430.0, source="cached_hk_history"),
            source="cached_hk_history",
        )
        time.sleep(0.01)
        stock_service = MagicMock()

        def slow_quote(_code: str) -> dict:
            time.sleep(0.2)
            return _quote(440.0, source="slow_hk_quote")

        stock_service.get_realtime_quote.side_effect = slow_quote
        stock_service.get_history_data.return_value = _history(431.0, source="live_hk_history")
        service = BasicQueryService(
            stock_service=stock_service,
            cache=cache,
            source_health=MarketSourceHealthRegistry(),
            fetch_timeout_seconds=1.0,
            stale_revalidation_timeout_seconds=0.01,
        )

        started = time.perf_counter()
        with patch.object(service, "_comparison_targets_with_reference_quotes", return_value=[]):
            snapshot = service.get_snapshot("HK00700")
        elapsed = time.perf_counter() - started

        self.assertLess(elapsed, 0.1)
        self.assertEqual(snapshot["quote"]["current_price"], 431.0)
        self.assertEqual(snapshot["diagnostics"]["cache"]["quote"], "fallback")
        self.assertEqual(snapshot["diagnostics"]["errors"]["quote"], "timeout")
        self.assertEqual(snapshot["diagnostics"]["fallback"]["quote"], "history_last_close")

    def test_stale_profile_is_preserved_when_live_source_errors(self) -> None:
        cache = MarketDataCache(default_ttl_seconds=0)
        cache.set("profile:AAPL", _profile(2.0, source="cached_profile"), source="cached_profile")
        time.sleep(0.01)
        service = self._service(stock_service=_LiveStockService(), cache=cache)

        with patch.object(service, "_call_with_timeout", return_value=(None, "error")):
            result = service._get_profile(
                "AAPL",
                route=service._resolve_route("AAPL"),
                quote=None,
            )

        self.assertEqual(result[0]["market_cap"], 2.0)
        self.assertEqual(result[1], "stale")
        self.assertEqual(result[2], "stale_fallback")
        self.assertEqual(result[6], "stale_cache")
        self.assertEqual(result[7], "error")

    def test_cooling_source_skips_live_call_and_uses_stale_quote(self) -> None:
        cache = MarketDataCache(default_ttl_seconds=0)
        cache.set("quote:AAPL", _quote(102.0, source="cached_quote"), source="cached_quote")
        time.sleep(0.01)
        health = MarketSourceHealthRegistry(failure_threshold=1, cooling_seconds=60)
        health.record_timeout("us_realtime", elapsed_ms=1000)
        stock_service = MagicMock()
        service = BasicQueryService(stock_service=stock_service, cache=cache, source_health=health)

        result = service._get_quote("AAPL", route=service._resolve_route("AAPL"))

        self.assertEqual(result[0]["current_price"], 102.0)
        self.assertEqual(result[1], "stale")
        self.assertEqual(result[2], "stale_fallback")
        self.assertEqual(result[7], "cooling_down")
        self.assertEqual(result[8]["status"], "cooling_down")
        stock_service.get_realtime_quote.assert_not_called()


if __name__ == "__main__":
    unittest.main()
