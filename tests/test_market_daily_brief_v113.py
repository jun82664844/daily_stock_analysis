import unittest


class _WatchlistStub:
    def __init__(self) -> None:
        self.listed_user_ids: list[int] = []
        self.refreshed_user_ids: list[int] = []

    def list_items(self, user_id: int) -> dict:
        self.listed_user_ids.append(user_id)
        symbol = "AAPL" if user_id == 7 else "600519.SH"
        return {"items": [{"stock_code": symbol, "market": "us" if user_id == 7 else "cn"}]}

    def refresh(self, user_id: int, *, limit: int = 20) -> dict:
        self.refreshed_user_ids.append(user_id)
        symbol = "AAPL" if user_id == 7 else "600519.SH"
        return {
            "items": [{
                "stock_code": symbol,
                "stock_name": "Apple Inc." if user_id == 7 else "贵州茅台",
                "market": "us" if user_id == 7 else "cn",
                "current_price": 100.0,
                "change_percent": 1.2,
                "freshness": "fresh",
                "status": "ok",
                "warning_codes": [],
                "ai_used": False,
            }],
            "ai_used": False,
        }


class MarketDailyBriefServiceV113TestCase(unittest.TestCase):
    def test_daily_brief_contains_only_current_users_watchlist_and_never_uses_ai(self) -> None:
        from src.services.market_daily_brief_service import MarketDailyBriefService

        watchlist = _WatchlistStub()
        body = MarketDailyBriefService(watchlist_service=watchlist).build(7)

        self.assertEqual([item["symbol"] for item in body["items"]], ["AAPL"])
        self.assertEqual(watchlist.listed_user_ids, [7])
        self.assertEqual(watchlist.refreshed_user_ids, [7])
        self.assertFalse(body["ai_used"])
        self.assertTrue(body["informational_only"])

    def test_empty_watchlist_returns_empty_brief(self) -> None:
        from src.services.market_daily_brief_service import MarketDailyBriefService

        watchlist = _WatchlistStub()
        watchlist.list_items = lambda user_id: {"items": []}

        body = MarketDailyBriefService(watchlist_service=watchlist).build(7)

        self.assertEqual(body["items"], [])
        self.assertEqual(body["empty_action"], "add_watchlist")
        self.assertFalse(body["ai_used"])


if __name__ == "__main__":
    unittest.main()
