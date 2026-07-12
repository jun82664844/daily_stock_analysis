# -*- coding: utf-8 -*-
"""Process-local Kronos model lifecycle and measurable inference runtime."""

from __future__ import annotations

import threading
import time
from typing import Any, Callable, Dict, Iterable, Optional


Loader = Callable[[Dict[str, Any]], tuple[Any, str]]


def _safe_float(value: Any) -> Optional[float]:
    if value is None or value == "":
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number == number else None


class KronosRuntime:
    """Load one predictor per runtime key and return secret-free telemetry."""

    def __init__(self, *, loader: Optional[Loader] = None) -> None:
        self._loader = loader or self._default_loader
        self._predictors: dict[tuple[str, str, str, int, bool], tuple[Any, str]] = {}
        self._load_lock = threading.Lock()

    def predict(
        self,
        rows: Iterable[Dict[str, Any]],
        *,
        horizon: int,
        model_id: str,
        tokenizer_id: str,
        device: str,
        max_context: int,
        local_files_only: bool,
    ) -> Dict[str, Any]:
        import pandas as pd

        normalized_rows = list(rows)
        if not normalized_rows:
            raise ValueError("kronos_input_rows_empty")

        config = {
            "model_id": model_id,
            "tokenizer_id": tokenizer_id,
            "device": device,
            "max_context": int(max_context),
            "local_files_only": bool(local_files_only),
        }
        cache_key = (model_id, tokenizer_id, device, int(max_context), bool(local_files_only))
        load_started = time.perf_counter()
        with self._load_lock:
            cached = self._predictors.get(cache_key)
            model_cache_hit = cached is not None
            if cached is None:
                cached = self._loader(config)
                self._predictors[cache_key] = cached
        model_load_ms = 0.0 if model_cache_hit else (time.perf_counter() - load_started) * 1000
        predictor, resolved_device = cached

        x_df = pd.DataFrame(normalized_rows)[["open", "high", "low", "close", "volume", "amount"]].fillna(0)
        x_timestamp = pd.Series(pd.to_datetime([row["timestamp"] for row in normalized_rows]))
        last_timestamp = x_timestamp.iloc[-1]
        y_timestamp = pd.Series(
            [last_timestamp + pd.Timedelta(days=offset) for offset in range(1, int(horizon) + 1)]
        )

        torch_module = self._torch_for_device(resolved_device)
        if torch_module is not None:
            torch_module.cuda.reset_peak_memory_stats()
        inference_started = time.perf_counter()
        prediction = predictor.predict(
            df=x_df,
            x_timestamp=x_timestamp,
            y_timestamp=y_timestamp,
            pred_len=int(horizon),
            T=1.0,
            top_p=0.9,
            sample_count=1,
            verbose=False,
        )
        if torch_module is not None:
            torch_module.cuda.synchronize()
        inference_ms = (time.perf_counter() - inference_started) * 1000

        points = self._points_from_dataframe(prediction, y_timestamp)
        peak_vram_mb = 0.0
        if torch_module is not None:
            peak_vram_mb = torch_module.cuda.max_memory_allocated() / 1024 / 1024
        return {
            "points": points,
            "metrics": {
                "resolved_device": str(resolved_device),
                "model_cache_hit": model_cache_hit,
                "model_load_ms": round(model_load_ms, 3),
                "inference_ms": round(inference_ms, 3),
                "peak_vram_mb": round(peak_vram_mb, 3),
                "input_bars": len(normalized_rows),
                "forecast_bars": len(points),
            },
        }

    def clear(self) -> None:
        with self._load_lock:
            self._predictors.clear()

    @staticmethod
    def _torch_for_device(device: str):
        if not str(device).lower().startswith("cuda"):
            return None
        try:
            import torch
        except ImportError:
            return None
        return torch if torch.cuda.is_available() else None

    @staticmethod
    def _default_loader(config: Dict[str, Any]) -> tuple[Any, str]:
        import torch
        from model import Kronos, KronosPredictor, KronosTokenizer

        requested_device = str(config["device"])
        if requested_device == "auto":
            resolved_device = "cuda" if torch.cuda.is_available() else "cpu"
        else:
            resolved_device = requested_device
        load_options = {"local_files_only": bool(config["local_files_only"])}
        tokenizer = KronosTokenizer.from_pretrained(str(config["tokenizer_id"]), **load_options)
        model = Kronos.from_pretrained(str(config["model_id"]), **load_options)
        predictor = KronosPredictor(
            model,
            tokenizer,
            max_context=int(config["max_context"]),
            device=resolved_device,
        )
        return predictor, resolved_device

    @staticmethod
    def _points_from_dataframe(df: Any, timestamps: Any) -> list[Dict[str, Any]]:
        points: list[Dict[str, Any]] = []
        for index, (_, row) in enumerate(df.iterrows()):
            timestamp = timestamps.iloc[index] if index < len(timestamps) else index
            points.append(
                {
                    "timestamp": str(timestamp),
                    "open": _safe_float(row.get("open")),
                    "high": _safe_float(row.get("high")),
                    "low": _safe_float(row.get("low")),
                    "close": _safe_float(row.get("close")),
                    "volume": _safe_float(row.get("volume")),
                    "amount": _safe_float(row.get("amount")),
                }
            )
        return points


KRONOS_RUNTIME = KronosRuntime()
