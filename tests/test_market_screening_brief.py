from __future__ import annotations

import math
import unittest

from src.services.market_screening_brief import build_market_screening_brief


class MarketScreeningBriefTestCase(unittest.TestCase):
    def test_builds_deterministic_no_ai_data_brief(self) -> None:
        brief = build_market_screening_brief(
            {
                "code": "600519",
                "screen_score": 88.0,
                "change_pct": 1.8,
                "factor_scores": {"quality": 92.0, "value": 61.0},
                "risk_flags": ["valuation_data_high"],
                "dsa_context": {
                    "quote": {
                        "price": 1688.0,
                        "source": "eastmoney",
                        "freshness": "fresh",
                        "updated_at": "2026-07-11T09:30:00+08:00",
                    },
                    "warnings": [],
                },
            }
        )

        self.assertFalse(brief["ai_used"])
        self.assertEqual(brief["data_freshness"], "fresh")
        self.assertEqual(brief["source_status"], "available")
        self.assertGreaterEqual(brief["data_completeness"], 75)
        self.assertIn("factor:quality", brief["matched_condition_codes"])
        self.assertIn("screen_score", brief["matched_condition_codes"])
        self.assertIn("valuation_data_high", brief["information_flags"])
        self.assertEqual(brief["observed_metrics"][0]["source"], "alphasift")
        self.assertNotIn("recommendation", brief)
        self.assertNotIn("action", brief)
        self.assertNotIn("target_price", brief)
        self.assertNotIn("expected_return", brief)

    def test_stale_data_is_explicit_even_when_fields_are_complete(self) -> None:
        brief = build_market_screening_brief(
            {
                "code": "AAPL",
                "score": 80,
                "factor_scores": {"quality": 82},
                "dsa_context": {
                    "quote": {
                        "price": 315.0,
                        "source": "cache",
                        "freshness": "stale",
                        "updated_at": "2026-07-09T16:00:00Z",
                    },
                    "warnings": ["quote stale"],
                },
            }
        )

        self.assertEqual(brief["data_freshness"], "stale")
        self.assertEqual(brief["source_status"], "partial")
        self.assertIn("data_stale", brief["information_flags"])
        self.assertIn("refresh_data", brief["observation_codes"])

    def test_missing_quote_and_factors_are_unavailable(self) -> None:
        brief = build_market_screening_brief(
            {"code": "AAPL", "dsa_context": {"warnings": ["quote unavailable"]}}
        )

        self.assertEqual(brief["data_freshness"], "unavailable")
        self.assertEqual(brief["source_status"], "unavailable")
        self.assertLess(brief["data_completeness"], 40)
        self.assertEqual(brief["observation_codes"], ["refresh_data"])
        self.assertEqual(brief["condition_exit_codes"], ["data_unavailable"])

    def test_llm_fields_only_mark_provenance(self) -> None:
        brief = build_market_screening_brief(
            {
                "code": "AAPL",
                "llm_score": 99,
                "llm_thesis": "Narrative only",
                "factor_scores": {},
                "dsa_context": {},
            }
        )

        self.assertTrue(brief["ai_used"])
        self.assertEqual(brief["source_status"], "unavailable")
        self.assertLess(brief["data_completeness"], 40)
        self.assertNotIn("llm_score", brief["matched_condition_codes"])

    def test_non_finite_metrics_and_duplicate_flags_are_removed(self) -> None:
        brief = build_market_screening_brief(
            {
                "code": "600519",
                "score": math.nan,
                "change_pct": math.inf,
                "factor_scores": {"quality": 80, "bad": math.nan},
                "risk_flags": ["data_partial", "data_partial", ""],
                "dsa_context": {"quote": {"price": 100, "freshness": "cached"}},
            }
        )

        codes = [item["code"] for item in brief["observed_metrics"]]
        self.assertNotIn("score", codes)
        self.assertNotIn("change_pct", codes)
        self.assertNotIn("factor:bad", codes)
        self.assertEqual(brief["information_flags"].count("data_partial"), 1)


if __name__ == "__main__":
    unittest.main()
