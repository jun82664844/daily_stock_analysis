# -*- coding: utf-8 -*-
"""Local Kronos forecast sandbox with explicit no-model fallback."""

from __future__ import annotations

import copy
import importlib.util
import json
import os
import sys
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, Optional

from src.services.basic_query_service import BasicQueryService, MarketRoute
from src.services.stock_service import StockService


_KRONOS_EXECUTOR = ThreadPoolExecutor(max_workers=max(1, int(os.getenv("KRONOS_MAX_CONCURRENT", "1"))))
_KRONOS_SEMAPHORE = threading.BoundedSemaphore(max(1, int(os.getenv("KRONOS_MAX_CONCURRENT", "1"))))
_KRONOS_DATA_EXECUTOR = ThreadPoolExecutor(max_workers=max(2, int(os.getenv("KRONOS_DATA_MAX_CONCURRENT", "2"))))


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _env_bool(name: str, default: str = "false") -> bool:
    return os.getenv(name, default).strip().lower() in {"1", "true", "yes", "on"}


def _safe_float(value: Any) -> Optional[float]:
    if value is None or value == "":
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number == number else None


def _safe_int(value: Any, default: int, *, minimum: int, maximum: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = default
    return max(minimum, min(maximum, parsed))


def _data_dir() -> Path:
    db_path = os.getenv("DATABASE_PATH", "./data/stock_analysis.db")
    return Path(db_path).resolve().parent


def _default_dependency_probe() -> Dict[str, bool]:
    repo_path = os.getenv("KRONOS_REPO_PATH", "").strip()
    if repo_path and repo_path not in sys.path:
        sys.path.insert(0, repo_path)
    return {
        "pandas": importlib.util.find_spec("pandas") is not None,
        "torch": importlib.util.find_spec("torch") is not None,
        "einops": importlib.util.find_spec("einops") is not None,
        "safetensors": importlib.util.find_spec("safetensors") is not None,
        "huggingface_hub": importlib.util.find_spec("huggingface_hub") is not None,
        "model": importlib.util.find_spec("model") is not None,
    }


class KronosForecastService:
    """Build an explicit Kronos/local-rules forecast payload for the UI lab."""

    def __init__(
        self,
        *,
        stock_service: Optional[StockService] = None,
        dependency_probe: Optional[Callable[[], Dict[str, bool]]] = None,
        cache_ttl_seconds: Optional[float] = None,
        data_timeout_seconds: Optional[float] = None,
    ) -> None:
        self.stock_service = stock_service or StockService()
        self.basic_query_service = BasicQueryService(stock_service=self.stock_service)
        self.dependency_probe = dependency_probe or _default_dependency_probe
        self.cache_ttl_seconds = (
            float(os.getenv("KRONOS_CACHE_TTL_SEC", "120"))
            if cache_ttl_seconds is None
            else max(0.0, float(cache_ttl_seconds))
        )
        self.data_timeout_seconds = (
            float(os.getenv("KRONOS_DATA_TIMEOUT_SEC", "8"))
            if data_timeout_seconds is None
            else max(0.01, float(data_timeout_seconds))
        )
        self._cache: dict[tuple[str, int, int, bool], tuple[float, Dict[str, Any]]] = {}
        self._cache_lock = threading.Lock()

    def check_availability(self) -> Dict[str, Any]:
        dependency_status = self.dependency_probe()
        missing = sorted(name for name, available in dependency_status.items() if not available)
        enabled = _env_bool("KRONOS_ENABLED", "false")
        status = "model_ready" if enabled and not missing else ("model_unavailable" if enabled else "model_disabled")
        return {
            "enabled": enabled,
            "status": status,
            "dependency_status": dependency_status,
            "missing_dependencies": missing,
            "model_id": os.getenv("KRONOS_MODEL_ID", "NeoQuasar/Kronos-mini"),
            "tokenizer_id": os.getenv("KRONOS_TOKENIZER_ID", "NeoQuasar/Kronos-Tokenizer-2k"),
            "device": os.getenv("KRONOS_DEVICE", "auto"),
            "max_context": _safe_int(os.getenv("KRONOS_MAX_CONTEXT", "512"), 512, minimum=16, maximum=2048),
            "timeout_sec": max(1.0, float(os.getenv("KRONOS_TIMEOUT_SEC", "30"))),
        }

    def forecast(self, stock_code: str, *, lookback: int = 120, horizon: int = 5) -> Dict[str, Any]:
        started = time.perf_counter()
        route = self.basic_query_service._resolve_route(stock_code)
        lookback = _safe_int(lookback, 120, minimum=5, maximum=512)
        horizon = _safe_int(horizon, 5, minimum=1, maximum=30)
        availability = self.check_availability()
        cache_key = (route.normalized_code, lookback, horizon, bool(availability["enabled"]))

        cached = self._get_cached(cache_key)
        if cached is not None:
            cached["cache_hit"] = True
            cached["elapsed_ms"] = round((time.perf_counter() - started) * 1000, 3)
            current_close = _safe_float(cached.get("anchor_close"))
            cached["backtest_summary"] = self._backtest_summary(
                route.normalized_code,
                current_close=current_close,
                current_record_id="",
            )
            cached.pop("anchor_close", None)
            return cached

        quote, history, data_warnings = self._fetch_market_inputs(route, lookback=lookback)
        rows = self._history_rows(history.get("data") or [])
        recent_rows = rows[-lookback:] if rows else []
        signal = self._build_local_signal(route=route, quote=quote, rows=recent_rows)
        model_points: list[Dict[str, Any]] = []
        model_warning = ""
        status = str(availability["status"])
        source = self._fallback_source(status)
        kronos_model_used = False

        if availability["enabled"] and not availability["missing_dependencies"]:
            try:
                model_points = self._run_kronos_model(recent_rows, horizon=horizon, availability=availability)
                if model_points:
                    status = "model_ready"
                    source = "kronos_model_local"
                    kronos_model_used = True
                    signal = self._signal_from_model_points(signal, model_points)
            except Exception as exc:
                status = "model_error"
                source = "local_kline_rules_kronos_error"
                model_warning = f"Kronos model failed locally; local rules fallback used: {exc}"

        forecast_points = model_points or self._fallback_forecast_points(recent_rows, signal=signal, horizon=horizon)
        record_id = uuid.uuid4().hex
        current_close = signal.get("anchor_close")
        backtest_summary = self._backtest_summary(
            route.normalized_code,
            current_close=current_close,
            current_record_id=record_id,
        )
        warnings = self._warnings(
            availability=availability,
            status=status,
            model_warning=model_warning,
            rows=recent_rows,
            data_warnings=data_warnings,
        )
        result = {
            "stock_code": route.normalized_code,
            "stock_name": quote.get("stock_name") or history.get("stock_name"),
            "market": route.market,
            "mode": "kronos_sandbox",
            "status": status,
            "provider": "kronos",
            "source": source,
            "horizon": f"next_{horizon}_bars",
            "lookback": lookback,
            "direction": signal["direction"],
            "confidence": signal["confidence"],
            "support": signal["support"],
            "resistance": signal["resistance"],
            "adapter_status": self._adapter_status(availability=availability, status=status),
            "enabled": bool(availability["enabled"]),
            "kronos_model_used": kronos_model_used,
            "model_id": availability["model_id"],
            "tokenizer_id": availability["tokenizer_id"],
            "device": availability["device"],
            "dependency_status": availability["dependency_status"],
            "missing_dependencies": availability["missing_dependencies"],
            "scenarios": signal["scenarios"],
            "forecast_points": forecast_points,
            "backtest_summary": backtest_summary,
            "warnings": warnings,
            "elapsed_ms": round((time.perf_counter() - started) * 1000, 3),
            "cache_hit": False,
            "record_id": record_id,
            "ai_used": False,
            "public_search_used": False,
            "boundary": "Experimental model preview; information analysis only; not investment advice.",
            "anchor_close": current_close,
        }
        self._append_record(result)
        self._set_cached(cache_key, result)
        public_result = copy.deepcopy(result)
        public_result.pop("anchor_close", None)
        return public_result

    def _get_cached(self, cache_key: tuple[str, int, int, bool]) -> Optional[Dict[str, Any]]:
        with self._cache_lock:
            cached = self._cache.get(cache_key)
            if cached is None:
                return None
            ts, payload = cached
            if self.cache_ttl_seconds <= 0 or time.time() - ts > self.cache_ttl_seconds:
                self._cache.pop(cache_key, None)
                return None
            return copy.deepcopy(payload)

    def _set_cached(self, cache_key: tuple[str, int, int, bool], payload: Dict[str, Any]) -> None:
        with self._cache_lock:
            self._cache[cache_key] = (time.time(), copy.deepcopy(payload))

    def _fetch_market_inputs(self, route: MarketRoute, *, lookback: int) -> tuple[Dict[str, Any], Dict[str, Any], list[str]]:
        days = max(lookback + 10, 30)
        futures = {
            "quote": _KRONOS_DATA_EXECUTOR.submit(self.stock_service.get_realtime_quote, route.normalized_code),
            "history": _KRONOS_DATA_EXECUTOR.submit(
                self.stock_service.get_history_data,
                route.normalized_code,
                period="daily",
                days=days,
            ),
        }
        quote: Dict[str, Any] = {}
        history: Dict[str, Any] = {}
        warnings: list[str] = []
        for name, future in futures.items():
            try:
                result = future.result(timeout=self.data_timeout_seconds)
            except TimeoutError:
                future.cancel()
                warnings.append("Kronos market data fetch timed out; local rules fallback used.")
            except Exception as exc:
                warnings.append(f"Kronos market data fetch degraded; {name} source failed: {type(exc).__name__}.")
            else:
                if name == "quote":
                    quote = result or {}
                else:
                    history = result or {}
        return quote, history, list(dict.fromkeys(warnings))

    def _history_rows(self, rows: Iterable[Dict[str, Any]]) -> list[Dict[str, Any]]:
        normalized: list[Dict[str, Any]] = []
        for index, row in enumerate(rows):
            close = _safe_float(row.get("close"))
            if close is None:
                continue
            open_price = _safe_float(row.get("open")) or close
            high = _safe_float(row.get("high")) or max(open_price, close)
            low = _safe_float(row.get("low")) or min(open_price, close)
            normalized.append(
                {
                    "timestamp": str(row.get("date") or row.get("timestamp") or row.get("time") or f"row-{index}"),
                    "open": open_price,
                    "high": high,
                    "low": low,
                    "close": close,
                    "volume": _safe_float(row.get("volume")),
                    "amount": _safe_float(row.get("amount")),
                }
            )
        return normalized

    def _build_local_signal(self, *, route: MarketRoute, quote: Dict[str, Any], rows: list[Dict[str, Any]]) -> Dict[str, Any]:
        closes = [_safe_float(row.get("close")) for row in rows]
        closes = [value for value in closes if value is not None]
        current = _safe_float(quote.get("current_price")) or (closes[-1] if closes else None)
        ma5 = self._ma(closes, 5)
        ma10 = self._ma(closes, 10)
        ma20 = self._ma(closes, 20)
        lows = [_safe_float(row.get("low")) for row in rows[-20:]]
        highs = [_safe_float(row.get("high")) for row in rows[-20:]]
        support_values = [value for value in [*lows, ma20, ma10, ma5] if value is not None]
        resistance_values = [value for value in [*highs, current, ma5, ma10, ma20] if value is not None]
        support = min(support_values) if support_values else None
        resistance = max(resistance_values) if resistance_values else None
        score = 50
        if current is None:
            score -= 20
        if current is not None and ma20 is not None:
            score += 16 if current >= ma20 else -16
        if current is not None and ma5 is not None:
            score += 8 if current >= ma5 else -8
        change_5 = self._change_percent(closes, 5)
        change_20 = self._change_percent(closes, 20)
        if change_5 is not None:
            score += 8 if change_5 >= 0 else -8
        if change_20 is not None:
            score += 5 if change_20 >= 0 else -5
        score = max(5, min(95, int(round(score))))
        if current is None or len(closes) < 5:
            direction = "insufficient_data"
            label = "Insufficient K-line context"
        elif score >= 62:
            direction = "upside_bias"
            label = "Upside-biased preview"
        elif score <= 38:
            direction = "downside_risk"
            label = "Downside-risk preview"
        else:
            direction = "range_watch"
            label = "Range-watch preview"
        confidence = max(35, min(88, 40 + abs(score - 50)))
        scenarios = [
            {
                "label": label,
                "direction": direction,
                "probability": int(score if direction == "upside_bias" else max(20, 100 - abs(score - 50))),
                "trigger": f"Hold above local support {self._fmt(support)} and monitor MA20 {self._fmt(ma20)}.",
                "detail": "Local fallback uses OHLCV, moving averages, and volume context; this is not a trade instruction.",
            },
            {
                "label": "Breakout confirmation",
                "direction": "upside_bias",
                "probability": int(max(15, min(78, score + 8))),
                "trigger": f"Price closes above resistance {self._fmt(resistance)} with stronger volume.",
                "detail": f"Use this as a next-refresh checklist for {route.channel}; it is not investment advice.",
            },
            {
                "label": "Pullback risk",
                "direction": "downside_risk",
                "probability": int(max(10, min(75, 100 - score))),
                "trigger": f"Price loses support {self._fmt(support)} or source freshness degrades.",
                "detail": "Recheck market data and broader context before interpreting weakness.",
            },
        ]
        return {
            "direction": direction,
            "confidence": int(confidence),
            "support": support,
            "resistance": resistance,
            "score": score,
            "scenarios": scenarios,
            "anchor_close": current,
        }

    def _run_kronos_model(
        self,
        rows: list[Dict[str, Any]],
        *,
        horizon: int,
        availability: Dict[str, Any],
    ) -> list[Dict[str, Any]]:
        if len(rows) < 5:
            return []
        acquired = _KRONOS_SEMAPHORE.acquire(blocking=False)
        if not acquired:
            raise RuntimeError("kronos_concurrency_limit")
        try:
            future = _KRONOS_EXECUTOR.submit(self._predict_with_kronos, rows, horizon, availability)
            return future.result(timeout=float(availability["timeout_sec"]))
        except TimeoutError as exc:
            raise TimeoutError("kronos_timeout") from exc
        finally:
            _KRONOS_SEMAPHORE.release()

    def _predict_with_kronos(
        self,
        rows: list[Dict[str, Any]],
        horizon: int,
        availability: Dict[str, Any],
    ) -> list[Dict[str, Any]]:
        import pandas as pd
        import torch
        from model import Kronos, KronosPredictor, KronosTokenizer

        device = str(availability["device"])
        if device == "auto":
            device = "cuda" if torch.cuda.is_available() else "cpu"
        tokenizer = KronosTokenizer.from_pretrained(str(availability["tokenizer_id"]))
        model = Kronos.from_pretrained(str(availability["model_id"]))
        try:
            predictor = KronosPredictor(model, tokenizer, max_context=int(availability["max_context"]), device=device)
        except TypeError:
            predictor = KronosPredictor(model, tokenizer, max_context=int(availability["max_context"]))

        x_df = pd.DataFrame(rows)[["open", "high", "low", "close", "volume", "amount"]].fillna(0)
        x_timestamp = pd.to_datetime([row["timestamp"] for row in rows])
        last_ts = x_timestamp.iloc[-1] if hasattr(x_timestamp, "iloc") else x_timestamp[-1]
        y_timestamp = pd.Series([last_ts + pd.Timedelta(days=offset) for offset in range(1, horizon + 1)])
        pred_df = predictor.predict(
            df=x_df,
            x_timestamp=pd.Series(x_timestamp),
            y_timestamp=y_timestamp,
            pred_len=horizon,
            T=1.0,
            top_p=0.9,
            sample_count=1,
        )
        return self._points_from_dataframe(pred_df, y_timestamp)

    def _points_from_dataframe(self, df: Any, timestamps: Any) -> list[Dict[str, Any]]:
        points: list[Dict[str, Any]] = []
        for index, (_, row) in enumerate(df.iterrows()):
            timestamp = timestamps.iloc[index] if hasattr(timestamps, "iloc") else None
            points.append(
                {
                    "timestamp": str(timestamp) if timestamp is not None else str(index),
                    "open": _safe_float(row.get("open")),
                    "high": _safe_float(row.get("high")),
                    "low": _safe_float(row.get("low")),
                    "close": _safe_float(row.get("close")),
                    "volume": _safe_float(row.get("volume")),
                    "amount": _safe_float(row.get("amount")),
                }
            )
        return points

    def _fallback_forecast_points(
        self,
        rows: list[Dict[str, Any]],
        *,
        signal: Dict[str, Any],
        horizon: int,
    ) -> list[Dict[str, Any]]:
        last = rows[-1] if rows else {}
        last_close = _safe_float(signal.get("anchor_close")) or _safe_float(last.get("close")) or 0.0
        last_volume = _safe_float(last.get("volume"))
        last_amount = _safe_float(last.get("amount"))
        try:
            last_ts = datetime.fromisoformat(str(last.get("timestamp")))
        except Exception:
            last_ts = _utc_now()
        drift = (float(signal.get("score") or 50) - 50.0) / 1000.0
        points: list[Dict[str, Any]] = []
        previous_close = last_close
        for offset in range(1, horizon + 1):
            close = previous_close * (1 + drift)
            open_price = previous_close
            high = max(open_price, close) * 1.01
            low = min(open_price, close) * 0.99
            points.append(
                {
                    "timestamp": (last_ts + timedelta(days=offset)).date().isoformat(),
                    "open": round(open_price, 6),
                    "high": round(high, 6),
                    "low": round(low, 6),
                    "close": round(close, 6),
                    "volume": last_volume,
                    "amount": last_amount,
                }
            )
            previous_close = close
        return points

    def _signal_from_model_points(self, signal: Dict[str, Any], points: list[Dict[str, Any]]) -> Dict[str, Any]:
        anchor = _safe_float(signal.get("anchor_close"))
        final_close = _safe_float(points[-1].get("close")) if points else None
        if anchor and final_close:
            change = (final_close - anchor) / anchor * 100
            if change >= 1:
                direction = "upside_bias"
            elif change <= -1:
                direction = "downside_risk"
            else:
                direction = "range_watch"
            signal = copy.deepcopy(signal)
            signal["direction"] = direction
            signal["confidence"] = max(45, min(92, int(55 + min(abs(change) * 4, 37))))
            signal["scenarios"][0]["label"] = "Kronos model forecast"
            signal["scenarios"][0]["direction"] = direction
            signal["scenarios"][0]["probability"] = signal["confidence"]
            signal["scenarios"][0]["trigger"] = f"Kronos forecasted {change:.2f}% over the requested horizon."
            signal["scenarios"][0]["detail"] = "Real local Kronos model output; still experimental information analysis only."
        return signal

    def _warnings(
        self,
        *,
        availability: Dict[str, Any],
        status: str,
        model_warning: str,
        rows: list[Dict[str, Any]],
        data_warnings: Optional[list[str]] = None,
    ) -> list[str]:
        warnings: list[str] = []
        warnings.extend(data_warnings or [])
        if status == "model_disabled":
            warnings.append("KRONOS_ENABLED is false; local rules fallback only.")
        if status == "model_unavailable":
            missing = ", ".join(availability["missing_dependencies"])
            warnings.append(f"Kronos model unavailable; missing dependencies: {missing}.")
        if model_warning:
            warnings.append(model_warning)
        if len(rows) < 20:
            warnings.append("K-line context is short; confidence is capped.")
        warnings.append("Forecast lab output is experimental information analysis only; not investment advice.")
        return warnings

    def _adapter_status(self, *, availability: Dict[str, Any], status: str) -> str:
        if status == "model_ready":
            return "Kronos model sandbox ran locally with configured dependencies."
        if status == "model_error":
            return "Kronos model sandbox is configured but failed; local rules fallback was used."
        if status == "model_disabled":
            return "Kronos adapter ready; KRONOS_ENABLED is false, so only local rules ran."
        missing = ", ".join(availability["missing_dependencies"]) or "unknown"
        return f"Kronos adapter ready; model not invoked because dependencies are missing: {missing}."

    def _fallback_source(self, status: str) -> str:
        if status == "model_disabled":
            return "local_kline_rules_kronos_disabled"
        if status == "model_error":
            return "local_kline_rules_kronos_error"
        return "local_kline_rules_kronos_unavailable"

    def _record_path(self) -> Path:
        configured = os.getenv("KRONOS_RECORD_PATH", "").strip()
        return Path(configured) if configured else _data_dir() / "kronos_forecasts.jsonl"

    def _append_record(self, payload: Dict[str, Any]) -> None:
        path = self._record_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        record = {
            "record_id": payload.get("record_id"),
            "created_at": _utc_now().isoformat(),
            "stock_code": payload.get("stock_code"),
            "market": payload.get("market"),
            "status": payload.get("status"),
            "source": payload.get("source"),
            "direction": payload.get("direction"),
            "confidence": payload.get("confidence"),
            "anchor_close": payload.get("anchor_close"),
            "kronos_model_used": payload.get("kronos_model_used"),
            "ai_used": False,
            "public_search_used": False,
        }
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")

    def _backtest_summary(
        self,
        stock_code: str,
        *,
        current_close: Optional[float],
        current_record_id: str,
    ) -> Dict[str, Any]:
        path = self._record_path()
        if not path.exists():
            return {"records": 0, "evaluated": 0, "hits": 0, "hit_rate": None, "last_evaluated_at": None}
        records = []
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines()[-200:]:
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue
            if item.get("stock_code") == stock_code and item.get("record_id") != current_record_id:
                records.append(item)
        evaluated = 0
        hits = 0
        if current_close is not None:
            for item in records:
                anchor = _safe_float(item.get("anchor_close"))
                direction = str(item.get("direction") or "")
                if anchor is None or anchor <= 0:
                    continue
                evaluated += 1
                change = (current_close - anchor) / anchor * 100
                if direction == "upside_bias" and change >= 0:
                    hits += 1
                elif direction == "downside_risk" and change <= 0:
                    hits += 1
                elif direction == "range_watch" and abs(change) <= 2:
                    hits += 1
        return {
            "records": len(records),
            "evaluated": evaluated,
            "hits": hits,
            "hit_rate": round(hits / evaluated, 4) if evaluated else None,
            "last_evaluated_at": _utc_now().isoformat() if records else None,
        }

    def _ma(self, closes: list[float], window: int) -> Optional[float]:
        if len(closes) < window:
            return None
        return sum(closes[-window:]) / window

    def _change_percent(self, closes: list[float], window: int) -> Optional[float]:
        if len(closes) <= window:
            return None
        first = closes[-window - 1]
        last = closes[-1]
        if first == 0:
            return None
        return (last - first) / first * 100

    def _fmt(self, value: Any) -> str:
        number = _safe_float(value)
        return "-" if number is None else f"{number:.4f}".rstrip("0").rstrip(".")
