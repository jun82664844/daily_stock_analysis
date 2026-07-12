from __future__ import annotations

import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from api.app import create_app


class FinancialResearchWorkflowApiV106TestCase(unittest.TestCase):
    def test_anonymous_user_can_read_no_ai_research_workflows(self) -> None:
        client = TestClient(create_app())
        snapshot = {
            "stock_code": "600519",
            "stock_name": "贵州茅台",
            "market": "cn",
            "quote": {
                "current_price": 1500.0,
                "change_percent": 0.5,
                "source": "a_share_quote",
                "freshness": "cached",
                "update_time": "2026-07-11T10:00:00Z",
            },
            "profile": {
                "sector": "Consumer Staples",
                "industry": "Beverages",
                "market_cap": 1_880_000_000_000,
                "pe_ratio": 22.0,
                "revenue": 170_000_000_000,
                "net_profit": 85_000_000_000,
                "revenue_growth": 0.12,
                "earnings_growth": 0.15,
                "source": "profile_cache",
                "freshness": "cached",
            },
            "intelligence": None,
            "ai_used": False,
        }

        with (
            patch("api.middlewares.auth.is_auth_enabled", return_value=True),
            patch("api.middlewares.auth.is_platform_user_auth_enabled", return_value=True),
            patch("api.v1.endpoints.stocks.BasicQueryService") as service_cls,
        ):
            service_cls.return_value.get_snapshot.return_value = snapshot
            response = client.get("/api/v1/stocks/600519.SH/research-workflows")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["stock_code"], "600519")
        self.assertEqual(len(payload["workflows"]), 4)
        self.assertFalse(payload["ai_used"])
        self.assertFalse(payload["public_search_used"])
        self.assertFalse(payload["source"]["connectors_enabled"])
        price_fact = payload["workflows"][0]["facts"][0]
        self.assertEqual(price_fact["currency"], "CNY")
        self.assertEqual(price_fact["unit"], "currency")
        service_cls.return_value.get_snapshot.assert_called_once_with("600519", force_refresh=False)

        with (
            patch("api.middlewares.auth.is_auth_enabled", return_value=True),
            patch("api.middlewares.auth.is_platform_user_auth_enabled", return_value=True),
        ):
            similar = client.get("/api/v1/stocks/600519.SH/private/research-workflows")
            wrong_method = client.post("/api/v1/stocks/600519.SH/research-workflows")
        self.assertEqual(similar.status_code, 401)
        self.assertEqual(wrong_method.status_code, 401)

    def test_refresh_is_forwarded_without_enabling_ai(self) -> None:
        client = TestClient(create_app())
        snapshot = {
            "stock_code": "AAPL",
            "stock_name": "Apple Inc.",
            "market": "us",
            "quote": {"source": "cache", "freshness": "stale"},
            "profile": None,
            "intelligence": None,
            "ai_used": False,
        }

        with patch("api.v1.endpoints.stocks.BasicQueryService") as service_cls:
            service_cls.return_value.get_snapshot.return_value = snapshot
            response = client.get("/api/v1/stocks/AAPL/research-workflows?refresh=true")

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["ai_used"])
        service_cls.return_value.get_snapshot.assert_called_once_with("AAPL", force_refresh=True)


if __name__ == "__main__":
    unittest.main()
