from __future__ import annotations

import unittest

import pandas as pd


class _FakePredictor:
    def predict(self, *, df, x_timestamp, y_timestamp, pred_len, **_kwargs):
        rows = []
        anchor = float(df.iloc[-1]["close"])
        for offset in range(pred_len):
            close = anchor + offset + 1
            rows.append(
                {
                    "open": close - 0.2,
                    "high": close + 0.8,
                    "low": close - 0.9,
                    "close": close,
                    "volume": 1000 + offset,
                    "amount": 100000 + offset,
                }
            )
        return pd.DataFrame(rows)


def _rows(count: int = 24):
    return [
        {
            "timestamp": f"2026-06-{index + 1:02d}",
            "open": 100.0 + index,
            "high": 101.0 + index,
            "low": 99.0 + index,
            "close": 100.5 + index,
            "volume": 1000 + index,
            "amount": 100000 + index,
        }
        for index in range(count)
    ]


class KronosRuntimeV108TestCase(unittest.TestCase):
    def test_runtime_loads_predictor_once_and_reports_request_metrics(self) -> None:
        from src.services.kronos_runtime import KronosRuntime

        loader_calls = []

        def loader(config):
            loader_calls.append(config)
            return _FakePredictor(), "cuda"

        runtime = KronosRuntime(loader=loader)
        first = runtime.predict(
            _rows(),
            horizon=5,
            model_id="NeoQuasar/Kronos-mini",
            tokenizer_id="NeoQuasar/Kronos-Tokenizer-2k",
            device="auto",
            max_context=512,
            local_files_only=True,
        )
        second = runtime.predict(
            _rows(),
            horizon=5,
            model_id="NeoQuasar/Kronos-mini",
            tokenizer_id="NeoQuasar/Kronos-Tokenizer-2k",
            device="auto",
            max_context=512,
            local_files_only=True,
        )

        self.assertEqual(len(loader_calls), 1)
        self.assertFalse(first["metrics"]["model_cache_hit"])
        self.assertTrue(second["metrics"]["model_cache_hit"])
        self.assertEqual(first["metrics"]["resolved_device"], "cuda")
        self.assertEqual(first["metrics"]["input_bars"], 24)
        self.assertEqual(first["metrics"]["forecast_bars"], 5)
        self.assertGreaterEqual(first["metrics"]["model_load_ms"], 0)
        self.assertGreaterEqual(first["metrics"]["inference_ms"], 0)
        self.assertEqual(len(first["points"]), 5)

    def test_runtime_cache_key_includes_offline_loading_policy(self) -> None:
        from src.services.kronos_runtime import KronosRuntime

        loader_calls = []

        def loader(config):
            loader_calls.append(config)
            return _FakePredictor(), "cpu"

        runtime = KronosRuntime(loader=loader)
        common = {
            "horizon": 2,
            "model_id": "model",
            "tokenizer_id": "tokenizer",
            "device": "cpu",
            "max_context": 128,
        }
        runtime.predict(_rows(), local_files_only=True, **common)
        runtime.predict(_rows(), local_files_only=False, **common)

        self.assertEqual(len(loader_calls), 2)
        self.assertTrue(loader_calls[0]["local_files_only"])
        self.assertFalse(loader_calls[1]["local_files_only"])


if __name__ == "__main__":
    unittest.main()
