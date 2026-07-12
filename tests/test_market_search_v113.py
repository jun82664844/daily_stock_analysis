import unittest


class MarketSearchServiceV113TestCase(unittest.TestCase):
    def test_search_normalizes_three_markets(self) -> None:
        from src.services.market_search_service import MarketSearchService

        service = MarketSearchService()

        self.assertEqual(service.search("贵州茅台", ["cn"], 8)[0]["symbol"], "600519.SH")
        self.assertEqual(service.search("腾讯", ["hk"], 8)[0]["symbol"], "0700.HK")
        self.assertEqual(service.search("Apple", ["us"], 8)[0]["symbol"], "AAPL")

    def test_search_rejects_html_and_caps_results(self) -> None:
        from src.services.market_search_service import MarketSearchService

        service = MarketSearchService()

        with self.assertRaises(ValueError):
            service.search("<script>", ["cn", "hk", "us"], 1000)

    def test_search_prioritizes_exact_symbol_without_market_performance_ranking(self) -> None:
        from src.services.market_search_service import MarketSearchService

        results = MarketSearchService().search("AAPL", ["cn", "hk", "us"], 8)

        self.assertEqual(results[0]["symbol"], "AAPL")
        self.assertEqual(results[0]["match_type"], "exact_symbol")
        self.assertNotIn("change_percent", results[0])


if __name__ == "__main__":
    unittest.main()
