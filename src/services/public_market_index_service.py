# -*- coding: utf-8 -*-
"""Cached public benchmark indices for the no-AI homepage."""

from __future__ import annotations

import copy
import json
import os
import time
from datetime import datetime, timezone
from threading import Lock
from typing import Any, Callable, Dict, List, Optional
from urllib.parse import quote

import requests


PublicIndexFetcher = Callable[[str], Dict[str, Any]]
_MAX_RESPONSE_BYTES = 512 * 1024
_INDEX_DEFINITIONS = {
    "cn": ("000001.SS", "上证指数", "CNY"),
    "hk": ("^HSI", "恒生指数", "HKD"),
    "us": ("^GSPC", "标普500指数", "USD"),
}


class PublicMarketIndexService:
    """Load one allowlisted benchmark per market without model usage."""

    def __init__(
        self,
        *,
        fetcher: Optional[PublicIndexFetcher] = None,
        cache_ttl_seconds: Optional[int] = None,
        timeout_seconds: Optional[float] = None,
    ) -> None:
        self.fetcher = fetcher or self._fetch_yahoo_chart
        self.cache_ttl_seconds = max(
            1,
            int(cache_ttl_seconds or os.getenv("PLATFORM_PUBLIC_MARKET_INDEX_CACHE_TTL_SECONDS", "60")),
        )
        self.timeout_seconds = max(
            0.5,
            min(float(timeout_seconds or os.getenv("PLATFORM_PUBLIC_MARKET_INDEX_TIMEOUT_SECONDS", "1.5")), 5.0),
        )
        self._cache: Dict[str, tuple[float, List[Dict[str, Any]]]] = {}
        self._lock = Lock()

    def load(self, market: str) -> List[Dict[str, Any]]:
        normalized = str(market or "").strip().lower()
        definition = _INDEX_DEFINITIONS.get(normalized)
        if definition is None:
            return []
        cached = self._read_cache(normalized)
        if cached is not None:
            return cached
        symbol, name, currency = definition
        try:
            payload = self.fetcher(symbol)
            items = self._normalize(payload, symbol=symbol, name=name, market=normalized, currency=currency)
        except Exception:
            items = []
        with self._lock:
            self._cache[normalized] = (time.monotonic(), copy.deepcopy(items))
        return copy.deepcopy(items)

    def _read_cache(self, market: str) -> Optional[List[Dict[str, Any]]]:
        with self._lock:
            cached = self._cache.get(market)
        if cached is None or time.monotonic() - cached[0] >= self.cache_ttl_seconds:
            return None
        return copy.deepcopy(cached[1])

    def _fetch_yahoo_chart(self, symbol: str) -> Dict[str, Any]:
        if symbol not in {value[0] for value in _INDEX_DEFINITIONS.values()}:
            raise ValueError("unsupported public market index")
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{quote(symbol, safe='')}"
        response = requests.get(
            url,
            params={"interval": "1d", "range": "5d"},
            headers={
                "Accept": "application/json",
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
                ),
            },
            timeout=(min(1.0, self.timeout_seconds), self.timeout_seconds),
            allow_redirects=False,
            stream=True,
        )
        try:
            response.raise_for_status()
            chunks: list[bytes] = []
            total = 0
            for chunk in response.iter_content(chunk_size=8192):
                if not chunk:
                    continue
                total += len(chunk)
                if total > _MAX_RESPONSE_BYTES:
                    raise ValueError("public market index response too large")
                chunks.append(chunk)
            payload = json.loads(b"".join(chunks).decode("utf-8-sig"))
            if not isinstance(payload, dict):
                raise ValueError("invalid public market index payload")
            return payload
        finally:
            response.close()

    @staticmethod
    def _normalize(
        payload: Dict[str, Any],
        *,
        symbol: str,
        name: str,
        market: str,
        currency: str,
    ) -> List[Dict[str, Any]]:
        chart = payload.get("chart") if isinstance(payload.get("chart"), dict) else {}
        results = chart.get("result") if isinstance(chart.get("result"), list) else []
        result = results[0] if results and isinstance(results[0], dict) else {}
        meta = result.get("meta") if isinstance(result.get("meta"), dict) else {}
        try:
            price = float(meta["regularMarketPrice"])
        except (KeyError, TypeError, ValueError):
            return []
        previous = meta.get("chartPreviousClose") or meta.get("previousClose")
        try:
            previous_value = float(previous)
            change_percent = round((price - previous_value) / previous_value * 100, 4) if previous_value else None
        except (TypeError, ValueError):
            change_percent = None
        observed_at = None
        try:
            observed_at = datetime.fromtimestamp(float(meta.get("regularMarketTime")), tz=timezone.utc).isoformat()
        except (TypeError, ValueError, OSError, OverflowError):
            pass
        return [{
            "symbol": symbol,
            "name": name,
            "market": market,
            "currency": currency,
            "current_price": price,
            "change_percent": change_percent,
            "turnover": None,
            "source_state": {
                "source": "yahoo_public_index",
                "status": "fresh" if observed_at else "cached",
                "observed_at": observed_at,
                "fetched_at": datetime.now(timezone.utc).isoformat(),
                "delay_seconds": None,
                "warning_code": None,
            },
        }]
