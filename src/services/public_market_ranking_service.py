# -*- coding: utf-8 -*-
"""Public, no-AI market-wide rankings for the V119 home page."""

from __future__ import annotations

import copy
import json
import os
import time
from concurrent.futures import ThreadPoolExecutor, wait
from datetime import datetime, timezone
from threading import Lock
from typing import Any, Callable, Dict, List, Optional

import requests


FetchPublic = Callable[[str, Dict[str, Any], float], object]

_SINA_CN_URL = "https://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/Market_Center.getHQNodeData"
_SINA_HK_URL = "https://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/Market_Center.getHKStockData"
_SINA_SECTOR_URL = "https://vip.stock.finance.sina.com.cn/q/view/newSinaHy.php"
_YAHOO_SCREENER_URL = "https://query1.finance.yahoo.com/v1/finance/screener/predefined/saved"
_RANKING_EXECUTOR = ThreadPoolExecutor(max_workers=12, thread_name_prefix="public-market-ranking")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _default_fetch_public(url: str, params: Dict[str, Any], timeout: float) -> object:
    response = requests.get(
        url,
        params=params,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": "https://finance.sina.com.cn/" if "sina.com.cn" in url else "https://finance.yahoo.com/",
        },
        timeout=timeout,
    )
    response.raise_for_status()
    return response.text if "newSinaHy" in url else response.json()


class PublicMarketRankingService:
    """Load market-wide public rankings with bounded latency and last-good fallback."""

    def __init__(
        self,
        *,
        fetch_public: Optional[FetchPublic] = None,
        cache_ttl_seconds: Optional[int] = None,
        stale_ttl_seconds: Optional[int] = None,
        request_timeout_seconds: Optional[float] = None,
        load_timeout_seconds: Optional[float] = None,
        max_items: Optional[int] = None,
        clock: Callable[[], str] = _utc_now,
        monotonic: Callable[[], float] = time.monotonic,
        executor: Optional[ThreadPoolExecutor] = None,
    ) -> None:
        self.fetch_public = fetch_public or _default_fetch_public
        self.cache_ttl_seconds = max(1, int(cache_ttl_seconds or os.getenv("PLATFORM_PUBLIC_MARKET_RANKING_CACHE_TTL_SECONDS", "120")))
        self.stale_ttl_seconds = max(self.cache_ttl_seconds, int(stale_ttl_seconds or os.getenv("PLATFORM_PUBLIC_MARKET_RANKING_STALE_TTL_SECONDS", "1800")))
        self.request_timeout_seconds = max(0.2, min(float(request_timeout_seconds or os.getenv("PLATFORM_PUBLIC_MARKET_RANKING_REQUEST_TIMEOUT_SECONDS", "3.2")), 8.0))
        self.load_timeout_seconds = max(self.request_timeout_seconds, min(float(load_timeout_seconds or os.getenv("PLATFORM_PUBLIC_MARKET_RANKING_LOAD_TIMEOUT_SECONDS", "4.2")), 9.0))
        self.max_items = max(1, min(int(max_items or os.getenv("PLATFORM_PUBLIC_MARKET_RANKING_MAX_ITEMS", "8")), 20))
        self.clock = clock
        self.monotonic = monotonic
        self.executor = executor or _RANKING_EXECUTOR
        self._cache: Dict[str, tuple[float, Dict[str, Any]]] = {}
        self._last_good: Dict[str, tuple[float, Dict[str, Any]]] = {}
        self._lock = Lock()

    def load(self, market: str) -> Dict[str, Any]:
        normalized = str(market or "").strip().lower()
        if normalized not in {"cn", "hk", "us"}:
            raise ValueError("unsupported_market")

        cached = self._read_fresh_cache(normalized)
        if cached is not None:
            return cached

        payload, successful_groups = self._load_fresh(normalized)
        if successful_groups:
            with self._lock:
                entry = (self.monotonic(), copy.deepcopy(payload))
                self._cache[normalized] = entry
                self._last_good[normalized] = entry
            return payload

        stale = self._read_stale_cache(normalized)
        if stale is not None:
            return stale
        return payload

    def _load_fresh(self, market: str) -> tuple[Dict[str, Any], int]:
        fetched_at = self.clock()
        jobs: Dict[str, Any] = {}
        if market in {"cn", "hk"}:
            jobs = {
                "most_active": self.executor.submit(self._load_sina_ranking, market, "amount", 0, fetched_at),
                "gainers": self.executor.submit(self._load_sina_ranking, market, "changepercent", 0, fetched_at),
                "losers": self.executor.submit(self._load_sina_ranking, market, "changepercent", 1, fetched_at),
            }
        else:
            jobs = {
                "most_active": self.executor.submit(self._load_yahoo_ranking, "most_actives", fetched_at),
                "gainers": self.executor.submit(self._load_yahoo_ranking, "day_gainers", fetched_at),
                "losers": self.executor.submit(self._load_yahoo_ranking, "day_losers", fetched_at),
            }
        if market == "cn":
            jobs["sector_highlights"] = self.executor.submit(self._load_cn_sectors, fetched_at)

        completed, pending = wait(jobs.values(), timeout=self.load_timeout_seconds)
        for future in pending:
            future.cancel()

        groups: Dict[str, List[Dict[str, Any]]] = {
            "most_active": [], "gainers": [], "losers": [], "sector_highlights": [],
        }
        warnings: List[str] = []
        sources: List[Dict[str, Any]] = []
        successful_groups = 0
        for key, future in jobs.items():
            warning = f"{market}_{key}_unavailable"
            if future not in completed:
                warnings.append(f"{market}_{key}_timeout")
                sources.append(self._source_state(self._source_name(market, key), "unavailable", fetched_at, warning))
                continue
            try:
                rows = future.result()
                groups[key] = rows[: self.max_items]
                successful_groups += 1
                sources.append(self._source_state(self._source_name(market, key), "fresh", fetched_at, None))
            except Exception:
                warnings.append(warning)
                sources.append(self._source_state(self._source_name(market, key), "unavailable", fetched_at, warning))

        ranking_successes = sum(1 for key in ("most_active", "gainers", "losers") if groups[key])
        if ranking_successes == 0:
            warnings.append("market_rankings_unavailable")
            successful_groups = 0
        if market != "cn":
            warnings.append(f"{market}_sector_highlights_unavailable")

        payload = {
            "market": market,
            "as_of": fetched_at,
            **groups,
            "sources": sources,
            "warnings": list(dict.fromkeys(warnings)),
            "cache": {"hit": False, "age_seconds": 0, "ttl_seconds": self.cache_ttl_seconds},
            "ai_used": False,
            "informational_only": True,
        }
        return payload, successful_groups

    def _load_sina_ranking(self, market: str, sort: str, asc: int, fetched_at: str) -> List[Dict[str, Any]]:
        url = _SINA_CN_URL if market == "cn" else _SINA_HK_URL
        params: Dict[str, Any] = {
            "page": 1,
            "num": max(24, self.max_items * 3),
            "sort": sort,
            "asc": asc,
            "node": "hs_a" if market == "cn" else "qbgg_hk",
            "_s_r_a": "page",
        }
        if market == "cn":
            params["symbol"] = ""
        raw = self.fetch_public(url, params, self.request_timeout_seconds)
        if not isinstance(raw, list):
            raise ValueError("invalid_sina_ranking")
        rows: List[Dict[str, Any]] = []
        for record in raw:
            item = self._sina_item(record, market, fetched_at)
            if item is None:
                continue
            if sort == "changepercent" and not self._passes_liquidity(item, market):
                continue
            rows.append(item)
            if len(rows) >= self.max_items:
                break
        return rows

    def _load_yahoo_ranking(self, screen_id: str, fetched_at: str) -> List[Dict[str, Any]]:
        raw = self.fetch_public(
            _YAHOO_SCREENER_URL,
            {"formatted": "false", "scrIds": screen_id, "count": max(20, self.max_items * 2), "start": 0},
            self.request_timeout_seconds,
        )
        if not isinstance(raw, dict):
            raise ValueError("invalid_yahoo_ranking")
        results = ((raw.get("finance") or {}).get("result") or [])
        quotes = results[0].get("quotes") if results and isinstance(results[0], dict) else []
        rows = []
        for record in quotes or []:
            item = self._yahoo_item(record, fetched_at)
            if item is not None:
                rows.append(item)
            if len(rows) >= self.max_items:
                break
        return rows

    def _load_cn_sectors(self, fetched_at: str) -> List[Dict[str, Any]]:
        raw = self.fetch_public(_SINA_SECTOR_URL, {}, self.request_timeout_seconds)
        if not isinstance(raw, str):
            raise ValueError("invalid_sina_sector")
        start = raw.find("{")
        if start < 0:
            raise ValueError("invalid_sina_sector")
        data = json.loads(raw[start:])
        rows = []
        for value in data.values():
            parts = str(value).split(",")
            if len(parts) < 13:
                continue
            change = self._number(parts[5])
            if not parts[1].strip() or change is None:
                continue
            leader_symbol = self._cn_symbol(parts[8])
            rows.append({
                "name": parts[1].strip(),
                "market": "cn",
                "change_percent": change,
                "leading_symbol": leader_symbol,
                "leading_name": parts[12].strip() or None,
                "leading_change_percent": self._number(parts[9]),
                "source_state": self._source_state("sina_public_cn_sector", "fresh", fetched_at, None),
            })
        rows.sort(key=lambda item: float(item.get("change_percent") or 0), reverse=True)
        return rows[: self.max_items]

    def _sina_item(self, record: Any, market: str, fetched_at: str) -> Optional[Dict[str, Any]]:
        if not isinstance(record, dict):
            return None
        if market == "cn":
            symbol = self._cn_symbol(record.get("symbol") or record.get("code"))
            name = str(record.get("name") or "").strip()
            if symbol is None or not name or "退" in name or name.startswith(("N", "C")):
                return None
            price = self._number(record.get("trade"))
            market_cap = self._number(record.get("mktcap"))
            if market_cap is not None:
                market_cap *= 10000
            source = "sina_public_cn_ranking"
            currency = "CNY"
        else:
            symbol = self._hk_symbol(record.get("symbol"))
            name = str(record.get("name") or record.get("engname") or "").strip()
            if symbol is None or not name:
                return None
            price = self._number(record.get("lasttrade"))
            market_cap = self._number(record.get("market_value"))
            source = "sina_public_hk_ranking"
            currency = "HKD"
        if price is None or price <= 0:
            return None
        observed_at = str(record.get("ticktime") or "").strip() or None
        return {
            "symbol": symbol,
            "name": name,
            "market": market,
            "currency": currency,
            "current_price": price,
            "change_percent": self._number(record.get("changepercent")),
            "volume": self._number(record.get("volume")),
            "turnover": self._number(record.get("amount")),
            "market_cap": market_cap,
            "sector": None,
            "trading_session": "regular",
            "source_state": {
                **self._source_state(source, "fresh", fetched_at, None),
                "observed_at": observed_at,
            },
        }

    def _yahoo_item(self, record: Any, fetched_at: str) -> Optional[Dict[str, Any]]:
        if not isinstance(record, dict):
            return None
        symbol = str(record.get("symbol") or "").strip().upper()
        name = str(record.get("shortName") or record.get("longName") or symbol).strip()
        if not symbol or not name or len(symbol) > 16:
            return None
        session = self._yahoo_session(record.get("marketState"))
        prefix = "regularMarket"
        if session == "pre" and self._number(record.get("preMarketPrice")) is not None:
            prefix = "preMarket"
        elif session == "post" and self._number(record.get("postMarketPrice")) is not None:
            prefix = "postMarket"
        price = self._number(record.get(f"{prefix}Price"))
        if price is None or price <= 0:
            return None
        change = self._number(record.get(f"{prefix}ChangePercent"))
        volume = self._number(record.get("regularMarketVolume"))
        observed_epoch = self._number(record.get(f"{prefix}Time") or record.get("regularMarketTime"))
        observed_at = datetime.fromtimestamp(observed_epoch, timezone.utc).isoformat() if observed_epoch else None
        return {
            "symbol": symbol,
            "name": name,
            "market": "us",
            "currency": str(record.get("currency") or "USD"),
            "current_price": price,
            "change_percent": change,
            "volume": volume,
            "turnover": price * volume if volume is not None else None,
            "market_cap": self._number(record.get("marketCap")),
            "sector": str(record.get("sector") or "").strip() or None,
            "trading_session": session,
            "source_state": {
                **self._source_state("yahoo_public_us_screener", "fresh", fetched_at, None),
                "observed_at": observed_at,
            },
        }

    def _read_fresh_cache(self, market: str) -> Optional[Dict[str, Any]]:
        now = self.monotonic()
        with self._lock:
            entry = self._cache.get(market)
        if entry is None or now - entry[0] >= self.cache_ttl_seconds:
            return None
        return self._cached_copy(entry[1], int(max(0, now - entry[0])), "cached", "market_ranking_cache_hit")

    def _read_stale_cache(self, market: str) -> Optional[Dict[str, Any]]:
        now = self.monotonic()
        with self._lock:
            entry = self._last_good.get(market)
        if entry is None or now - entry[0] > self.stale_ttl_seconds:
            return None
        payload = self._cached_copy(entry[1], int(max(0, now - entry[0])), "stale", "market_ranking_stale_cache")
        payload["warnings"] = list(dict.fromkeys([*payload.get("warnings", []), "market_ranking_stale_cache"]))
        return payload

    def _cached_copy(self, payload: Dict[str, Any], age: int, status: str, warning: str) -> Dict[str, Any]:
        result = copy.deepcopy(payload)
        result["cache"] = {"hit": True, "age_seconds": age, "ttl_seconds": self.cache_ttl_seconds}
        for key in ("most_active", "gainers", "losers", "sector_highlights"):
            for item in result.get(key, []):
                state = item.get("source_state") if isinstance(item, dict) else None
                if isinstance(state, dict):
                    state["status"] = status
                    state["warning_code"] = warning
        for state in result.get("sources", []):
            if isinstance(state, dict) and state.get("status") != "unavailable":
                state["status"] = status
                state["warning_code"] = warning
        return result

    @staticmethod
    def _source_state(source: str, status: str, fetched_at: str, warning: Optional[str]) -> Dict[str, Any]:
        return {
            "source": source,
            "status": status,
            "observed_at": fetched_at if status == "fresh" else None,
            "fetched_at": fetched_at,
            "delay_seconds": 0 if status == "fresh" else None,
            "warning_code": warning,
        }

    @staticmethod
    def _source_name(market: str, key: str) -> str:
        if key == "sector_highlights":
            return "sina_public_cn_sector"
        return "yahoo_public_us_screener" if market == "us" else f"sina_public_{market}_ranking"

    @staticmethod
    def _passes_liquidity(item: Dict[str, Any], market: str) -> bool:
        turnover = PublicMarketRankingService._number(item.get("turnover")) or 0
        return turnover >= (50_000_000 if market == "cn" else 5_000_000)

    @staticmethod
    def _cn_symbol(value: Any) -> Optional[str]:
        text = str(value or "").strip().lower()
        if text.startswith("sh") and text[2:].isdigit() and len(text[2:]) == 6:
            return f"{text[2:]}.SH"
        if text.startswith("sz") and text[2:].isdigit() and len(text[2:]) == 6:
            return f"{text[2:]}.SZ"
        if text.isdigit() and len(text) == 6:
            if text.startswith(("6", "68")):
                return f"{text}.SH"
            if text.startswith(("0", "3")):
                return f"{text}.SZ"
        return None

    @staticmethod
    def _hk_symbol(value: Any) -> Optional[str]:
        text = str(value or "").strip()
        if not text.isdigit() or len(text) > 5:
            return None
        return f"{int(text):04d}.HK"

    @staticmethod
    def _yahoo_session(value: Any) -> str:
        state = str(value or "").strip().upper()
        if state.startswith("PRE"):
            return "pre"
        if state.startswith("POST"):
            return "post"
        if state == "REGULAR":
            return "regular"
        if state in {"CLOSED", "CLOSE"}:
            return "closed"
        return "unknown"

    @staticmethod
    def _number(value: Any) -> Optional[float]:
        try:
            if value in {None, "", "-", "--"}:
                return None
            return float(value)
        except (TypeError, ValueError):
            return None
