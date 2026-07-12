# -*- coding: utf-8 -*-
"""Low-cost public information adapter for US and Hong Kong equities."""

from __future__ import annotations

import copy
import json
import os
import re
import threading
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Optional


JsonGetter = Callable[..., Dict[str, Any]]


class GlobalEquityEnrichmentService:
    """Fetch direct public feeds without AI, general web search, or API keys."""

    _cache_lock = threading.Lock()
    _cache: Dict[str, tuple[float, Dict[str, Any]]] = {}
    _sec_ticker_cache: tuple[float, Dict[str, Dict[str, Any]]] | None = None

    def __init__(
        self,
        *,
        http_get_json: Optional[JsonGetter] = None,
        timeout_seconds: Optional[float] = None,
        cache_ttl_seconds: Optional[int] = None,
        max_news_items: Optional[int] = None,
        max_filing_items: Optional[int] = None,
    ) -> None:
        self.http_get_json = http_get_json or self._request_json
        self.timeout_seconds = max(
            0.2,
            float(timeout_seconds or os.getenv("GLOBAL_EQUITY_HTTP_TIMEOUT_SEC", "5")),
        )
        self.cache_ttl_seconds = max(
            1,
            int(cache_ttl_seconds or os.getenv("GLOBAL_EQUITY_CACHE_TTL_SEC", "600")),
        )
        self.max_news_items = max(
            1,
            min(10, int(max_news_items or os.getenv("GLOBAL_EQUITY_MAX_NEWS_ITEMS", "5"))),
        )
        self.max_filing_items = max(
            1,
            min(10, int(max_filing_items or os.getenv("GLOBAL_EQUITY_MAX_FILING_ITEMS", "5"))),
        )

    @classmethod
    def clear_cache(cls) -> None:
        with cls._cache_lock:
            cls._cache.clear()
            cls._sec_ticker_cache = None

    def get_enrichment(
        self,
        stock_code: str,
        *,
        market: str,
        stock_name: Optional[str] = None,
        profile: Optional[Dict[str, Any]] = None,
        force_refresh: bool = False,
    ) -> Optional[Dict[str, Any]]:
        normalized_market = str(market or "").strip().lower()
        if normalized_market not in {"us", "hk"}:
            return None

        symbol = self._public_symbol(stock_code, normalized_market)
        cache_key = f"{normalized_market}:{symbol}"
        if not force_refresh:
            cached = self._get_cached(cache_key)
            if cached is not None:
                cached["diagnostics"]["cache_hit"] = True
                return cached

        started = time.perf_counter()
        errors: list[Dict[str, str]] = []
        news_channel = self._news_channel(
            symbol=symbol,
            market=normalized_market,
            stock_name=stock_name,
            errors=errors,
        )
        if normalized_market == "us":
            filings_channel = self._sec_filings_channel(symbol=symbol, errors=errors)
        else:
            filings_channel = self._hkex_filings_channel(symbol=symbol)
        profile_channel = self._profile_channel(profile or {}, market=normalized_market)
        channels = [news_channel, filings_channel, profile_channel]
        available = sum(1 for channel in channels if channel["status"] == "available")
        status = "available" if available >= 2 else ("degraded" if available else "unavailable")
        label = "US equity" if normalized_market == "us" else "Hong Kong equity"
        updated_at = datetime.now(timezone.utc).isoformat()
        payload = {
            "title": f"{label} public data expansion",
            "summary": (
                f"{symbol} direct public feeds include company news, official filing status, and company facts. "
                "Unavailable sources remain visibly degraded and are never replaced with generated events."
            ),
            "market": normalized_market,
            "status": status,
            "source": "global_equity_public_adapter",
            "updated_at": updated_at,
            "ai_used": False,
            "public_search_used": False,
            "channels": channels,
            "diagnostics": {
                "cache_hit": False,
                "elapsed_ms": round((time.perf_counter() - started) * 1000, 3),
                "available_channels": available,
                "total_channels": len(channels),
                "errors": errors,
            },
            "premium_unlock": (
                "Premium can use configured API feeds for broader coverage and higher refresh limits; "
                "the visible module structure remains the same."
            ),
            "boundary": (
                "Information and data only; not investment advice, a trading instruction, a target price, "
                "or a return promise."
            ),
        }
        self._set_cached(cache_key, payload)
        return copy.deepcopy(payload)

    def _news_channel(
        self,
        *,
        symbol: str,
        market: str,
        stock_name: Optional[str],
        errors: list[Dict[str, str]],
    ) -> Dict[str, Any]:
        candidate_name = str(stock_name or "").strip()
        query = candidate_name if market == "hk" and self._usable_query_text(candidate_name) else symbol
        try:
            payload = self._fetch_yahoo_search(query)
            items = self._normalize_news_items(
                payload.get("news"),
                symbol=symbol,
                company_name=candidate_name,
            )
            if market == "hk" and not items:
                resolved_name = self._resolved_company_name(payload, symbol=symbol)
                if resolved_name and resolved_name.casefold() != query.casefold():
                    payload = self._fetch_yahoo_search(resolved_name)
                    items = self._normalize_news_items(
                        payload.get("news"),
                        symbol=symbol,
                        company_name=resolved_name,
                    )
        except Exception as exc:
            errors.append({"channel": "news", "error": type(exc).__name__})
            items = []
        status = "available" if items else "degraded"
        return {
            "category": "news",
            "title": "Company news",
            "summary": (
                f"{len(items)} symbol-linked public headlines are available."
                if items
                else "No symbol-linked public headline is currently available; no placeholder headline was generated."
            ),
            "status": status,
            "source": "yahoo_finance_search_feed",
            "items": items,
            "action": "Open the source link and confirm publication time before interpreting the event.",
        }

    def _fetch_yahoo_search(self, query: str) -> Dict[str, Any]:
        url = (
            "https://query1.finance.yahoo.com/v1/finance/search?"
            + urllib.parse.urlencode({"q": query, "quotesCount": 1, "newsCount": 10})
        )
        return self.http_get_json(
            url,
            headers={"User-Agent": "Mozilla/5.0 DSA-local-research/1.0"},
            timeout=self.timeout_seconds,
        )

    def _sec_filings_channel(self, *, symbol: str, errors: list[Dict[str, str]]) -> Dict[str, Any]:
        try:
            ticker_map = self._sec_ticker_map()
            ticker_row = ticker_map.get(symbol.upper())
            if not ticker_row:
                raise LookupError("ticker_not_found")
            cik = int(ticker_row["cik_str"])
            payload = self.http_get_json(
                f"https://data.sec.gov/submissions/CIK{cik:010d}.json",
                headers=self._sec_headers(),
                timeout=self.timeout_seconds,
            )
            items = self._normalize_sec_filings(payload, cik=cik)
        except Exception as exc:
            errors.append({"channel": "filings", "error": type(exc).__name__})
            items = []
        return {
            "category": "filings",
            "title": "SEC filings",
            "summary": (
                f"{len(items)} recent official SEC filings are available."
                if items
                else "Recent SEC filing data is temporarily unavailable; the channel remains visibly degraded."
            ),
            "status": "available" if items else "degraded",
            "source": "sec_edgar_submissions",
            "items": items,
            "action": "Read the official filing and filing date before using it as company context.",
        }

    def _hkex_filings_channel(self, *, symbol: str) -> Dict[str, Any]:
        return {
            "category": "filings",
            "title": "HKEX announcements",
            "summary": (
                f"The official HKEX announcement search is available for verification, but a stock-specific "
                f"document feed for {symbol} is not configured in this local adapter."
            ),
            "status": "degraded",
            "source": "hkexnews_official_search",
            "items": [],
            "official_url": "https://www1.hkexnews.hk/search/titlesearch.xhtml?lang=EN",
            "action": "Use the official HKEX search until a stable stock-specific feed is approved.",
        }

    @staticmethod
    def _profile_channel(profile: Dict[str, Any], *, market: str) -> Dict[str, Any]:
        facts: list[Dict[str, Any]] = []
        labels = (
            ("sector", "Sector"),
            ("industry", "Industry"),
            ("exchange", "Exchange"),
            ("currency", "Currency"),
            ("market_cap", "Market cap"),
            ("pe_ratio", "PE ratio"),
            ("dividend_yield", "Dividend yield"),
            ("revenue", "Revenue"),
            ("net_profit", "Net profit"),
        )
        for key, label in labels:
            value = profile.get(key)
            if value not in (None, ""):
                facts.append({"label": label, "value": value})
        return {
            "category": "fundamentals",
            "title": "Company facts",
            "summary": (
                f"{len(facts)} normalized company facts are available for the {market.upper()} lane."
                if facts
                else "Company facts are unavailable in the current public profile response."
            ),
            "status": "available" if facts else "degraded",
            "source": profile.get("source") or "profile_unavailable",
            "items": facts,
            "action": "Treat valuation and financial fields as dated company context, not a trading signal.",
        }

    def _sec_ticker_map(self) -> Dict[str, Dict[str, Any]]:
        now = time.monotonic()
        with self._cache_lock:
            cached = type(self)._sec_ticker_cache
            if cached and now - cached[0] < 86400:
                return copy.deepcopy(cached[1])
        payload = self.http_get_json(
            "https://www.sec.gov/files/company_tickers.json",
            headers=self._sec_headers(),
            timeout=self.timeout_seconds,
        )
        ticker_map: Dict[str, Dict[str, Any]] = {}
        for row in payload.values() if isinstance(payload, dict) else []:
            if not isinstance(row, dict):
                continue
            ticker = str(row.get("ticker") or "").strip().upper()
            if ticker and row.get("cik_str") is not None:
                ticker_map[ticker] = dict(row)
        with self._cache_lock:
            type(self)._sec_ticker_cache = (now, copy.deepcopy(ticker_map))
        return ticker_map

    def _normalize_news_items(
        self,
        raw_items: Any,
        *,
        symbol: str,
        company_name: str = "",
    ) -> list[Dict[str, Any]]:
        target = symbol.upper()
        common_tokens = {"holdings", "holding", "limited", "company", "group", "corporation", "incorporated"}
        name_tokens = {
            token.casefold()
            for token in re.findall(r"[A-Za-z0-9]+", company_name)
            if len(token) >= 4 and token.casefold() not in common_tokens
        }
        symbol_token = target.split(".", 1)[0].casefold()
        items: list[Dict[str, Any]] = []
        for raw in raw_items if isinstance(raw_items, list) else []:
            if not isinstance(raw, dict):
                continue
            related = {str(value).strip().upper() for value in raw.get("relatedTickers") or []}
            if target not in related:
                continue
            title = self._repair_mojibake(str(raw.get("title") or "").strip())
            url = self._safe_http_url(raw.get("link"))
            if not title or not url:
                continue
            title_text = title.casefold()
            directly_named = symbol_token in title_text or any(token in title_text for token in name_tokens)
            if not directly_named:
                continue
            published_at = self._timestamp_to_iso(raw.get("providerPublishTime"))
            items.append(
                {
                    "title": title,
                    "summary": str(raw.get("publisher") or "Public news source"),
                    "publisher": str(raw.get("publisher") or "Public news source"),
                    "published_at": published_at,
                    "url": url,
                    "source": "yahoo_finance_search_feed",
                }
            )
            if len(items) >= self.max_news_items:
                break
        return items

    def _normalize_sec_filings(self, payload: Dict[str, Any], *, cik: int) -> list[Dict[str, Any]]:
        recent = ((payload.get("filings") or {}).get("recent") or {}) if isinstance(payload, dict) else {}
        forms = recent.get("form") or []
        dates = recent.get("filingDate") or []
        reports = recent.get("reportDate") or []
        accession_numbers = recent.get("accessionNumber") or []
        documents = recent.get("primaryDocument") or []
        descriptions = recent.get("primaryDocDescription") or []
        accepted_forms = {"10-K", "10-K/A", "10-Q", "10-Q/A", "8-K", "8-K/A", "20-F", "20-F/A", "40-F", "6-K", "DEF 14A"}
        items: list[Dict[str, Any]] = []
        for index, form in enumerate(forms):
            document_type = str(form or "").strip().upper()
            if document_type not in accepted_forms:
                continue
            accession = str(accession_numbers[index] if index < len(accession_numbers) else "").strip()
            document = str(documents[index] if index < len(documents) else "").strip()
            if not accession or not document:
                continue
            accession_path = accession.replace("-", "")
            url = f"https://www.sec.gov/Archives/edgar/data/{cik}/{accession_path}/{urllib.parse.quote(document)}"
            description = str(descriptions[index] if index < len(descriptions) else "").strip()
            filing_date = str(dates[index] if index < len(dates) else "").strip() or None
            report_date = str(reports[index] if index < len(reports) else "").strip() or None
            items.append(
                {
                    "title": f"{document_type}{' - ' + description if description else ''}",
                    "summary": f"Filed {filing_date or 'date unavailable'}; report date {report_date or 'not stated'}.",
                    "document_type": document_type,
                    "published_at": filing_date,
                    "url": url,
                    "source": "sec_edgar_submissions",
                }
            )
            if len(items) >= self.max_filing_items:
                break
        return items

    def _get_cached(self, key: str) -> Optional[Dict[str, Any]]:
        now = time.monotonic()
        with self._cache_lock:
            entry = self._cache.get(key)
            if not entry:
                return None
            if now - entry[0] >= self.cache_ttl_seconds:
                self._cache.pop(key, None)
                return None
            return copy.deepcopy(entry[1])

    def _set_cached(self, key: str, payload: Dict[str, Any]) -> None:
        with self._cache_lock:
            self._cache[key] = (time.monotonic(), copy.deepcopy(payload))

    def _request_json(self, url: str, *, headers: Dict[str, str], timeout: float) -> Dict[str, Any]:
        request = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("upstream_json_not_object")
        return payload

    @staticmethod
    def _sec_headers() -> Dict[str, str]:
        user_agent = os.getenv(
            "GLOBAL_EQUITY_SEC_USER_AGENT",
            "DSA-local-research/1.0 contact@example.invalid",
        ).strip()
        return {"User-Agent": user_agent, "Accept": "application/json"}

    @staticmethod
    def _usable_query_text(value: str) -> bool:
        if not value or "\ufffd" in value:
            return False
        return not any(ord(character) < 32 or 127 <= ord(character) <= 159 for character in value)

    @staticmethod
    def _resolved_company_name(payload: Dict[str, Any], *, symbol: str) -> Optional[str]:
        target = symbol.upper()
        for row in payload.get("quotes") or []:
            if not isinstance(row, dict) or str(row.get("symbol") or "").upper() != target:
                continue
            name = str(row.get("longname") or row.get("shortname") or "").strip()
            if name:
                return name
        return None

    @staticmethod
    def _public_symbol(stock_code: str, market: str) -> str:
        code = str(stock_code or "").strip().upper()
        if market == "hk":
            if code.startswith("HK") and code[2:].isdigit():
                return f"{int(code[2:]):04d}.HK"
            if code.endswith(".HK") and code[:-3].isdigit():
                return f"{int(code[:-3]):04d}.HK"
        return code

    @staticmethod
    def _safe_http_url(value: Any) -> Optional[str]:
        text = str(value or "").strip()
        parsed = urllib.parse.urlparse(text)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            return None
        return text

    @staticmethod
    def _timestamp_to_iso(value: Any) -> Optional[str]:
        try:
            return datetime.fromtimestamp(float(value), tz=timezone.utc).isoformat()
        except (TypeError, ValueError, OSError, OverflowError):
            return None

    @staticmethod
    def _repair_mojibake(value: str) -> str:
        if not value or not any(marker in value for marker in ("\u00c2", "\u00c3", "\u00e2", "\u00f0")):
            return value
        try:
            repaired = value.encode("latin-1").decode("utf-8")
            return repaired if repaired else value
        except (UnicodeEncodeError, UnicodeDecodeError):
            return value
