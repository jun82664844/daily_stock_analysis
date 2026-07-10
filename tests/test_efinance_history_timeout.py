# -*- coding: utf-8 -*-
"""Regression tests for the bounded Efinance A-share history call."""

import sys
import types
import unittest
from unittest.mock import MagicMock, patch

import pandas as pd

from data_provider.efinance_fetcher import EfinanceFetcher


class EfinanceHistoryTimeoutTests(unittest.TestCase):
    def test_a_share_history_uses_the_dedicated_bounded_timeout(self) -> None:
        fake_efinance = types.SimpleNamespace(
            stock=types.SimpleNamespace(get_quote_history=MagicMock(name="get_quote_history"))
        )
        captured = {}

        def fake_call(func, *args, timeout=None, **kwargs):
            captured["timeout"] = timeout
            return pd.DataFrame(
                {
                    "日期": ["2026-07-01"],
                    "开盘": [100.0],
                    "最高": [101.0],
                    "最低": [99.0],
                    "收盘": [100.5],
                    "成交量": [1000],
                    "成交额": [100000],
                }
            )

        with patch(
            "data_provider.efinance_fetcher.get_config",
            return_value=types.SimpleNamespace(enable_eastmoney_patch=False),
        ), patch.dict(sys.modules, {"efinance": fake_efinance}), patch(
            "data_provider.efinance_fetcher._ef_call_with_timeout",
            side_effect=fake_call,
        ):
            fetcher = EfinanceFetcher(sleep_min=0, sleep_max=0)
            with patch.object(fetcher, "_set_random_user_agent"), patch.object(
                fetcher, "_enforce_rate_limit"
            ):
                result = fetcher._fetch_stock_data("600519", "2026-07-01", "2026-07-02")

        self.assertEqual(len(result), 1)
        self.assertLessEqual(captured["timeout"], 10)


if __name__ == "__main__":
    unittest.main()
