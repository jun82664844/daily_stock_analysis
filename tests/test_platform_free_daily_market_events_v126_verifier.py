from __future__ import annotations

import unittest


class FreeDailyMarketEventsV126VerifierTestCase(unittest.TestCase):
    def test_backend_contract_requires_rules_and_rejects_network_or_ai_clients(self) -> None:
        from scripts.verify_platform_free_daily_market_events_v126 import event_service_contract

        valid = """
class PublicMarketEventService:
    classification_source = 'keyword_rules'
    categories = ('earnings', 'announcement', 'dividend', 'trading_status', 'macro', 'corporate', 'market')
    A_SHARE_SYMBOL_PATTERN = True
    HK_SYMBOL_PATTERN = True
    factory_orders = 'factory orders'
    def _symbol_in_title(self):
        pass
"""
        self.assertTrue(event_service_contract(valid).ok)
        self.assertFalse(event_service_contract(valid + "\nimport httpx").ok)
        self.assertFalse(event_service_contract(valid.replace("keyword_rules", "llm_rules")).ok)
        self.assertFalse(event_service_contract(valid.replace("_symbol_in_title", "_unsafe_symbol_match")).ok)

    def test_frontend_contract_requires_lazy_loading_and_private_watchlist_forwarding(self) -> None:
        from scripts.verify_platform_free_daily_market_events_v126 import frontend_contract

        public_home = """
const DailyMarketEventCenterV126 = lazy(() => import('./DailyMarketEventCenterV126'));
<DailyMarketEventCenterV126 events={data.events} watchlistSymbols={watchlistSymbols} />
"""
        home_page = """
<PublicMarketHomeV116 watchlistSymbols={platformWatchlistItems.map((item) => item.stockCode)} />
"""
        self.assertTrue(frontend_contract(public_home, home_page).ok)
        self.assertFalse(frontend_contract(public_home.replace("lazy(() => import", "import"), home_page).ok)
        self.assertFalse(frontend_contract(public_home, home_page.replace("platformWatchlistItems", "[]")).ok)

    def test_safety_regression_contract_requires_review_findings_coverage(self) -> None:
        from scripts.verify_platform_free_daily_market_events_v126 import safety_regression_contract

        event_tests = """
test_does_not_link_ambiguous_short_us_symbols_without_cashtag
test_macro_rules_win_over_buyback_and_order_terms
test_explicit_exchange_symbol_overrides_mixed_feed_market
test_deduplicates_prioritizes_published_time_and_preserves_retrieved_time
"""
        component = """
const FILTERS = ['all', 'market'];
sourceMarkets: { cn: 'China source' }
"""
        component_tests = """
offers a market-update filter and labels unlinked markets as source channels
"""

        self.assertTrue(safety_regression_contract(event_tests, component, component_tests).ok)
        self.assertFalse(safety_regression_contract(event_tests.replace("ambiguous_short_us_symbols", "short_symbols"), component, component_tests).ok)
        self.assertFalse(safety_regression_contract(event_tests, component.replace("'market'", "'macro'"), component_tests).ok)


if __name__ == "__main__":
    unittest.main()
