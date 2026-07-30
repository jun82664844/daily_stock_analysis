from __future__ import annotations

import unittest
from datetime import datetime

import pandas as pd

from api.v1.schemas.basic_query import PublicStockResearchOverviewResponse
from src.services.public_stock_research_overview_service import (
    PublicStockResearchOverviewService,
    to_public_research_symbol,
)


def _financial_frame() -> pd.DataFrame:
    columns = [
        pd.Timestamp("2025-12-31"),
        pd.Timestamp("2024-12-31"),
        pd.Timestamp("2023-12-31"),
        pd.Timestamp("2022-12-31"),
        pd.Timestamp("2021-12-31"),
    ]
    return pd.DataFrame(
        {
            columns[0]: [1500.0, 210.0, 10.0, 260.0],
            columns[1]: [1320.0, 180.0, 9.0, 225.0],
            columns[2]: [1200.0, 160.0, 8.0, 205.0],
            columns[3]: [1080.0, 140.0, 7.0, 190.0],
            columns[4]: [1000.0, 120.0, 6.0, 170.0],
        },
        index=["Total Revenue", "Net Income", "Diluted EPS", "Operating Cash Flow"],
    )


def _history_frame() -> pd.DataFrame:
    return pd.DataFrame(
        {"Close": [90.0, 98.0, 104.0, 112.0, 125.0, 128.0]},
        index=pd.to_datetime(
            [
                "2021-12-31",
                "2022-12-30",
                "2023-12-29",
                "2024-12-31",
                "2025-12-31",
                "2026-01-31",
            ]
        ),
    )


class _FakeTicker:
    def __init__(self, symbol: str):
        self.symbol = symbol
        self.financials = _financial_frame()

    def history(self, *, period: str, interval: str, auto_adjust: bool = False):
        self.history_args = {
            "period": period,
            "interval": interval,
            "auto_adjust": auto_adjust,
        }
        return _history_frame()


class PublicStockResearchOverviewV142Tests(unittest.TestCase):
    def test_maps_supported_market_symbols_without_accepting_crypto(self):
        self.assertEqual(to_public_research_symbol("AAPL"), "AAPL")
        self.assertEqual(to_public_research_symbol("0700.HK"), "0700.HK")
        self.assertEqual(to_public_research_symbol("HK00700"), "0700.HK")
        self.assertEqual(to_public_research_symbol("600519.SH"), "600519.SS")
        self.assertEqual(to_public_research_symbol("SH600519"), "600519.SS")
        self.assertEqual(to_public_research_symbol("000001.SZ"), "000001.SZ")
        self.assertIsNone(to_public_research_symbol("BTC-USD"))

    def test_builds_five_year_financial_trends_and_observed_pe_position(self):
        created_symbols: list[str] = []

        def factory(symbol: str):
            created_symbols.append(symbol)
            return _FakeTicker(symbol)

        service = PublicStockResearchOverviewService(
            ticker_factory=factory,
            clock=lambda: datetime(2026, 7, 30, 12, 0, 0),
        )

        payload = service.get_overview("AAPL")

        self.assertEqual(payload["status"], "available")
        self.assertEqual(payload["source"], "yfinance_public_financials")
        self.assertEqual(payload["stock_code"], "AAPL")
        self.assertEqual(payload["public_symbol"], "AAPL")
        self.assertFalse(payload["ai_used"])
        self.assertFalse(payload["public_search_used"])
        self.assertEqual(created_symbols, ["AAPL"])
        self.assertEqual(len(payload["financial_years"]), 5)
        self.assertEqual(
            [point["fiscal_year"] for point in payload["financial_years"]],
            [2021, 2022, 2023, 2024, 2025],
        )
        self.assertEqual(payload["financial_years"][-1]["revenue"], 1500.0)
        self.assertEqual(payload["financial_years"][-1]["net_income"], 210.0)
        self.assertEqual(payload["financial_years"][-1]["diluted_eps"], 10.0)
        self.assertAlmostEqual(payload["financial_years"][-1]["revenue_growth"], 13.6364)
        self.assertEqual(
            payload["valuation_position"]["method"],
            "fiscal_year_end_price_divided_by_diluted_eps",
        )
        self.assertEqual(payload["valuation_position"]["observation_count"], 5)
        self.assertGreaterEqual(payload["valuation_position"]["percentile"], 0)
        self.assertLessEqual(payload["valuation_position"]["percentile"], 100)
        self.assertIn("不构成投资建议", payload["boundary_zh"])

        validated = PublicStockResearchOverviewResponse.model_validate(payload)
        self.assertEqual(validated.status, "available")
        self.assertEqual(len(validated.financial_years), 5)

    def test_uses_ttl_cache_for_repeat_reads(self):
        calls = 0

        def factory(symbol: str):
            nonlocal calls
            calls += 1
            return _FakeTicker(symbol)

        service = PublicStockResearchOverviewService(
            ticker_factory=factory,
            clock=lambda: datetime(2026, 7, 30, 12, 0, 0),
        )

        first = service.get_overview("AAPL")
        second = service.get_overview("AAPL")

        self.assertEqual(calls, 1)
        self.assertEqual(first["cache_status"], "miss")
        self.assertEqual(second["cache_status"], "hit")
        self.assertEqual(first["financial_years"], second["financial_years"])

    def test_omits_periods_without_observed_financial_values(self):
        class SparseTicker(_FakeTicker):
            def __init__(self, symbol: str):
                super().__init__(symbol)
                empty_period = pd.Timestamp("2021-12-31")
                self.financials[empty_period] = [float("nan")] * len(self.financials.index)

        service = PublicStockResearchOverviewService(
            ticker_factory=SparseTicker,
            clock=lambda: datetime(2026, 7, 30, 12, 0, 0),
        )

        payload = service.get_overview("AAPL")

        years = payload["financial_years"]
        self.assertEqual(len(years), 4)
        self.assertNotIn(2021, [point["fiscal_year"] for point in years])
        self.assertTrue(
            all(
                any(
                    point[key] is not None
                    for key in ("revenue", "net_income", "diluted_eps", "operating_cash_flow")
                )
                for point in years
            )
        )

    def test_returns_explicit_unavailable_payload_without_leaking_provider_error(self):
        def factory(symbol: str):
            raise RuntimeError("token=sk-secret-value upstream exploded")

        service = PublicStockResearchOverviewService(
            ticker_factory=factory,
            clock=lambda: datetime(2026, 7, 30, 12, 0, 0),
        )

        payload = service.get_overview("AAPL")

        self.assertEqual(payload["status"], "unavailable")
        self.assertEqual(payload["financial_years"], [])
        self.assertIsNone(payload["valuation_position"])
        self.assertTrue(payload["warnings"])
        rendered = str(payload)
        self.assertNotIn("sk-secret-value", rendered)
        self.assertNotIn("upstream exploded", rendered)
        self.assertFalse(payload["ai_used"])

    def test_crypto_returns_not_applicable_without_calling_a_ticker(self):
        service = PublicStockResearchOverviewService(
            ticker_factory=lambda symbol: self.fail("ticker must not be called"),
            clock=lambda: datetime(2026, 7, 30, 12, 0, 0),
        )

        payload = service.get_overview("BTC-USD")

        self.assertEqual(payload["status"], "not_applicable")
        self.assertEqual(payload["financial_years"], [])
        self.assertIn("股票财务报表", payload["warnings"][0])


if __name__ == "__main__":
    unittest.main()
