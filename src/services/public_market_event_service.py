# -*- coding: utf-8 -*-
"""Deterministic, no-AI normalization for public market events."""

from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional, Sequence
from urllib.parse import urlparse


MARKETS = ("cn", "hk", "us")
SOURCE_STATUSES = {"fresh", "cached", "stale", "unavailable"}
SECURITY_KEYS = ("indices", "attention", "most_active", "gainers", "losers")
A_SHARE_SYMBOL_PATTERN = re.compile(r"(?<![A-Z0-9])(\d{6})\.(SH|SZ)(?![A-Z])", re.IGNORECASE)
HK_SYMBOL_PATTERN = re.compile(r"(?<![A-Z0-9])(\d{1,5})\.HK(?![A-Z])", re.IGNORECASE)

CATEGORY_RULES = (
    ("trading_status", ("停牌", "复牌", "退市", "涨停", "跌停", "halt", "suspended", "delist")),
    ("earnings", ("业绩", "财报", "净利润", "盈利", "亏损", "预增", "预亏", "results", "earnings", "profit", "revenue", "guidance")),
    ("macro", ("央行", "逆回购", "美联储", "利率", "工厂订单", "耐用品订单", "cpi", "gdp", "非农", "通胀", "inflation", "federal reserve", "central bank", "factory orders", "payroll")),
    ("dividend", ("分红", "派息", "股息", "回购", "dividend", "buyback", "repurchase")),
    ("announcement", ("公告", "披露", "filing", "sec filing", "announcement")),
    ("corporate", ("收购", "并购", "订单", "合作", "融资", "merger", "acquisition", "contract", "partnership", "financing")),
)

FINANCE_SIGNAL_KEYWORDS = (
    "a股", "港股", "美股", "股票", "股价", "指数", "大盘", "市场", "收盘", "开盘", "盘前", "盘后",
    "上市", "证券", "基金", "债券", "期货", "外汇", "银行", "芯片", "半导体", "成交", "涨", "跌",
    "stock", "stocks", "share", "shares", "market", "index", "nasdaq", "dow", "s&p", "wall street",
    "premarket", "after-hours", "close", "trading", "ipo", "etf", "bond", "yield", "futures", "forex",
)

PROMOTIONAL_NOISE_KEYWORDS = (
    "专属文章", "盯盘神器", "推广内容", "广告内容", "sponsored content", "advertisement",
)

CATEGORY_REASONS = {
    "earnings": "earnings_event",
    "announcement": "announcement_event",
    "dividend": "dividend_event",
    "trading_status": "trading_status_event",
    "macro": "macro_event",
    "corporate": "corporate_event",
}


class PublicMarketEventService:
    """Build structured events from data already loaded for the public home."""

    def __init__(self, *, max_events_per_market: int = 8, max_events_total: int = 24) -> None:
        self.max_events_per_market = max(1, min(int(max_events_per_market), 20))
        self.max_events_total = max(1, min(int(max_events_total), 60))

    def build(self, markets: Sequence[Dict[str, Any]], as_of: str) -> List[Dict[str, Any]]:
        normalized: List[tuple[int, Dict[str, Any]]] = []
        events_by_title: Dict[str, Dict[str, Any]] = {}
        source_refs_by_title: Dict[str, set[str]] = {}
        market_counts = {market: 0 for market in MARKETS}
        ordinal = 0

        by_market = {
            str(section.get("market") or "").lower(): section
            for section in markets
            if isinstance(section, dict)
        }
        for market in MARKETS:
            section = by_market.get(market)
            if not section:
                continue
            securities = self._securities(section)
            for headline in section.get("headlines") or []:
                if not isinstance(headline, dict):
                    continue
                title = str(headline.get("title") or "").strip()
                if not title:
                    continue
                if self._is_promotional_noise(title):
                    continue
                title_key = re.sub(r"\s+", " ", title).strip().casefold()
                source_state = self._source_state(headline.get("source_state"))
                source_ref, source_publisher = self._source_reference(headline, source_state)
                source_record = self._source_record(headline, source_state, as_of)
                existing = events_by_title.get(title_key)
                if existing is not None:
                    source_refs = source_refs_by_title[title_key]
                    if source_ref not in source_refs and len(source_refs) < 20:
                        source_refs.add(source_ref)
                        existing["source_count"] = len(source_refs)
                        publishers = existing["source_publishers"]
                        if source_publisher and source_publisher not in publishers and len(publishers) < 8:
                            publishers.append(source_publisher)
                        source_records = existing["source_records"]
                        if len(source_records) < 8:
                            source_records.append(source_record)
                    continue
                explicit_symbol, explicit_market = self._explicit_exchange_symbol(title)
                event_market = explicit_market or market
                if market_counts[event_market] >= self.max_events_per_market:
                    continue
                published_at = str(headline.get("published_at") or "").strip()
                event_time = published_at or as_of
                time_kind = "published" if published_at else "retrieved"
                linked_symbol, linked_name, linked_sector = self._linked_security(title, securities)
                symbol = explicit_symbol or linked_symbol
                name = linked_name if linked_symbol and (not explicit_symbol or linked_symbol.casefold() == explicit_symbol.casefold()) else None
                sector = linked_sector if linked_symbol and (not explicit_symbol or linked_symbol.casefold() == explicit_symbol.casefold()) else None
                category = self._category(title)
                has_market_signal = self._has_finance_signal(title)
                if category == "market" and not symbol and not has_market_signal:
                    continue
                relevance_score, relevance_reasons = self._relevance(
                    category=category,
                    symbol=symbol,
                    has_market_signal=has_market_signal,
                    source_state=source_state,
                    has_url=bool(source_record["url"]),
                )
                event = {
                    "event_id": self._event_id(event_market, title, event_time),
                    "market": event_market,
                    "category": category,
                    "title": title,
                    "summary": self._optional_text(headline.get("summary")),
                    "symbol": symbol,
                    "name": name,
                    "sector": sector,
                    "event_time": event_time,
                    "time_kind": time_kind,
                    "publisher": self._optional_text(headline.get("publisher")),
                    "url": source_record["url"],
                    "source_state": source_state,
                    "classification_source": "keyword_rules",
                    "relevance_score": relevance_score,
                    "importance": self._importance(relevance_score),
                    "relevance_reasons": relevance_reasons,
                    "source_count": 1,
                    "source_publishers": [source_publisher] if source_publisher else [],
                    "source_records": [source_record],
                }
                normalized.append((ordinal, event))
                ordinal += 1
                events_by_title[title_key] = event
                source_refs_by_title[title_key] = {source_ref}
                market_counts[event_market] += 1

        normalized.sort(key=self._sort_key, reverse=True)
        return [event for _, event in normalized[: self.max_events_total]]

    @staticmethod
    def _category(title: str) -> str:
        lowered = title.casefold()
        for category, keywords in CATEGORY_RULES:
            if any(keyword in lowered for keyword in keywords):
                return category
        return "market"

    @staticmethod
    def _has_finance_signal(title: str) -> bool:
        lowered = title.casefold()
        return any(keyword in lowered for keyword in FINANCE_SIGNAL_KEYWORDS)

    @staticmethod
    def _is_promotional_noise(title: str) -> bool:
        lowered = title.casefold()
        return any(keyword in lowered for keyword in PROMOTIONAL_NOISE_KEYWORDS)

    @staticmethod
    def _relevance(
        *,
        category: str,
        symbol: Optional[str],
        has_market_signal: bool,
        source_state: Dict[str, Any],
        has_url: bool,
    ) -> tuple[int, List[str]]:
        score = 0
        reasons: List[str] = []
        category_reason = CATEGORY_REASONS.get(category)
        if category_reason:
            score += 30
            reasons.append(category_reason)
        if symbol:
            score += 35
            reasons.append("linked_security")
        if has_market_signal:
            score += 15
            reasons.append("market_signal")
        source_status = str(source_state.get("status") or "unavailable")
        if source_status == "fresh":
            score += 10
            reasons.append("fresh_source")
        elif source_status == "cached":
            score += 5
            reasons.append("cached_source")
        if has_url:
            score += 5
            reasons.append("source_link")
        return min(score, 100), reasons

    @staticmethod
    def _importance(score: int) -> str:
        if score >= 60:
            return "high"
        if score >= 35:
            return "medium"
        return "low"

    @staticmethod
    def _securities(section: Dict[str, Any]) -> List[Dict[str, str]]:
        securities: List[Dict[str, str]] = []
        seen: set[str] = set()
        for key in SECURITY_KEYS:
            for item in section.get(key) or []:
                if not isinstance(item, dict):
                    continue
                symbol = str(item.get("symbol") or "").strip()
                name = str(item.get("name") or "").strip()
                if not symbol or symbol.casefold() in seen:
                    continue
                seen.add(symbol.casefold())
                securities.append({
                    "symbol": symbol,
                    "name": name,
                    "sector": str(item.get("sector") or "").strip(),
                })
        return securities

    @staticmethod
    def _linked_security(
        title: str,
        securities: Iterable[Dict[str, str]],
    ) -> tuple[Optional[str], Optional[str], Optional[str]]:
        for security in securities:
            symbol = security["symbol"]
            name = security["name"]
            if PublicMarketEventService._symbol_in_title(title, symbol) or PublicMarketEventService._name_in_title(title, name):
                return symbol, name or None, security.get("sector") or None
        return None, None, None

    @staticmethod
    def _symbol_in_title(title: str, symbol: str) -> bool:
        core = symbol.split(".", 1)[0].strip()
        if not core:
            return False
        escaped = re.escape(symbol)
        if len(core) <= 2 and core.isalpha():
            return bool(re.search(rf"(?<![A-Z0-9])\${re.escape(core)}(?![A-Z0-9])", title, re.IGNORECASE))
        return bool(re.search(rf"(?<![A-Z0-9]){escaped}(?![A-Z0-9])", title, re.IGNORECASE))

    @staticmethod
    def _name_in_title(title: str, name: str) -> bool:
        candidate = name.strip()
        if len(candidate) < 2:
            return False
        if any(ord(character) > 127 for character in candidate):
            return candidate.casefold() in title.casefold()
        return bool(re.search(rf"(?<![A-Z0-9]){re.escape(candidate)}(?![A-Z0-9])", title, re.IGNORECASE))

    @staticmethod
    def _explicit_exchange_symbol(title: str) -> tuple[Optional[str], Optional[str]]:
        a_share = A_SHARE_SYMBOL_PATTERN.search(title)
        if a_share:
            return f"{a_share.group(1)}.{a_share.group(2).upper()}", "cn"
        hk_share = HK_SYMBOL_PATTERN.search(title)
        if hk_share:
            return f"{hk_share.group(1)}.HK", "hk"
        return None, None

    @staticmethod
    def _event_id(market: str, title: str, event_time: str) -> str:
        raw = f"{market}\n{title}\n{event_time}".encode("utf-8")
        return hashlib.sha256(raw).hexdigest()[:20]

    @staticmethod
    def _source_state(value: Any) -> Dict[str, Any]:
        payload = dict(value) if isinstance(value, dict) else {}
        status = str(payload.get("status") or "unavailable").lower()
        result: Dict[str, Any] = {
            "source": str(payload.get("source") or "public_market_news"),
            "status": status if status in SOURCE_STATUSES else "unavailable",
        }
        for key in ("observed_at", "fetched_at", "delay_seconds", "warning_code"):
            if payload.get(key) is not None:
                result[key] = payload[key]
        return result

    @staticmethod
    def _optional_text(value: Any) -> Optional[str]:
        text = str(value or "").strip()
        return text or None

    @classmethod
    def _safe_http_url(cls, value: Any) -> Optional[str]:
        url = cls._optional_text(value)
        if not url:
            return None
        try:
            parsed = urlparse(url)
        except ValueError:
            return None
        if parsed.scheme.casefold() not in {"http", "https"} or not parsed.netloc:
            return None
        return url

    @classmethod
    def _source_record(
        cls,
        headline: Dict[str, Any],
        source_state: Dict[str, Any],
        as_of: str,
    ) -> Dict[str, Any]:
        published_at = str(headline.get("published_at") or "").strip()
        source = str(source_state.get("source") or "public_market_news").strip() or "public_market_news"
        publisher = cls._optional_text(headline.get("publisher")) or source
        return {
            "publisher": publisher,
            "source": source,
            "url": cls._safe_http_url(headline.get("url")),
            "event_time": published_at or as_of,
            "time_kind": "published" if published_at else "retrieved",
        }

    @classmethod
    def _source_reference(cls, headline: Dict[str, Any], source_state: Dict[str, Any]) -> tuple[str, Optional[str]]:
        url = cls._safe_http_url(headline.get("url"))
        publisher = cls._optional_text(headline.get("publisher"))
        source = str(source_state.get("source") or "public_market_news").strip()
        if url:
            key = f"url:{url.casefold()}"
        else:
            key = f"publisher:{(publisher or '').casefold()}|source:{source.casefold()}"
        return key, publisher or source or None

    @staticmethod
    def _sort_key(item: tuple[int, Dict[str, Any]]) -> tuple[int, int, float, int]:
        ordinal, event = item
        relevance_score = int(event.get("relevance_score") or 0)
        is_published = 1 if event["time_kind"] == "published" else 0
        raw_time = str(event.get("event_time") or "")
        try:
            parsed = datetime.fromisoformat(raw_time.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            timestamp = parsed.timestamp()
        except (TypeError, ValueError, OverflowError):
            timestamp = 0.0
        return relevance_score, is_published, timestamp, -ordinal
