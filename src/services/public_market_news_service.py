# -*- coding: utf-8 -*-
"""Cached public market headlines for the no-AI homepage."""

from __future__ import annotations

import copy
import json
import os
import time
from datetime import datetime, timezone
from threading import Lock
from typing import Any, Callable, Dict, List, Optional
from urllib.parse import urlparse

import requests


PublicFeedFetcher = Callable[[str], Dict[str, Any]]
_NEWSNOW_ENDPOINT = "https://newsnow.busiyi.world/api/s"
_MAX_RESPONSE_BYTES = 512 * 1024
_MARKET_SOURCES = {
    "cn": ("cls-hot", "财联社"),
    "hk": ("gelonghui", "格隆汇"),
    "us": ("jin10", "金十数据"),
}


class PublicMarketNewsService:
    """Load allowlisted public headlines without model or API-key use."""

    def __init__(
        self,
        *,
        fetcher: Optional[PublicFeedFetcher] = None,
        cache_ttl_seconds: Optional[int] = None,
        timeout_seconds: Optional[float] = None,
        max_items: int = 6,
    ) -> None:
        self.fetcher = fetcher or self._fetch_newsnow
        self.cache_ttl_seconds = max(
            1,
            int(cache_ttl_seconds or os.getenv("PLATFORM_PUBLIC_MARKET_NEWS_CACHE_TTL_SECONDS", "300")),
        )
        self.timeout_seconds = max(
            0.5,
            min(float(timeout_seconds or os.getenv("PLATFORM_PUBLIC_MARKET_NEWS_TIMEOUT_SECONDS", "1.5")), 5.0),
        )
        self.max_items = max(1, min(int(max_items), 10))
        self._cache: Dict[str, tuple[float, List[Dict[str, Any]]]] = {}
        self._lock = Lock()

    def load(self, market: str) -> List[Dict[str, Any]]:
        normalized = str(market or "").strip().lower()
        source = _MARKET_SOURCES.get(normalized)
        if source is None:
            return []
        cached = self._read_cache(normalized)
        if cached is not None:
            return cached

        source_id, publisher = source
        try:
            payload = self.fetcher(source_id)
            items = self._normalize_items(payload, source_id=source_id, publisher=publisher)
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

    def _fetch_newsnow(self, source_id: str) -> Dict[str, Any]:
        if source_id not in {value[0] for value in _MARKET_SOURCES.values()}:
            raise ValueError("unsupported public market news source")
        response = requests.get(
            _NEWSNOW_ENDPOINT,
            params={"id": source_id},
            headers={
                "Accept": "application/json",
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/126.0.0.0 Safari/537.36 "
                    "daily-stock-analysis-public-home/1.0"
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
                    raise ValueError("public market news response too large")
                chunks.append(chunk)
            payload = json.loads(b"".join(chunks).decode("utf-8-sig"))
            if not isinstance(payload, dict):
                raise ValueError("invalid public market news payload")
            return payload
        finally:
            response.close()

    def _normalize_items(self, payload: Dict[str, Any], *, source_id: str, publisher: str) -> List[Dict[str, Any]]:
        raw_items = payload.get("items")
        if not isinstance(raw_items, list):
            return []
        result: List[Dict[str, Any]] = []
        seen_titles: set[str] = set()
        for raw_item in raw_items:
            if not isinstance(raw_item, dict):
                continue
            title = self._clean_text(raw_item.get("title"), 300)
            if not title or title.casefold() in seen_titles:
                continue
            extra = raw_item.get("extra") if isinstance(raw_item.get("extra"), dict) else {}
            summary = self._clean_text(extra.get("info") or extra.get("hover"), 600) or None
            story_url = self._safe_http_url(raw_item.get("url") or raw_item.get("mobileUrl"))
            published_at = self._published_at(raw_item.get("pubDate") or extra.get("date"))
            result.append({
                "title": title,
                "summary": summary,
                "publisher": publisher,
                "published_at": published_at,
                "url": story_url,
                "source": f"public_newsnow_{source_id.replace('-', '_')}",
            })
            seen_titles.add(title.casefold())
            if len(result) >= self.max_items:
                break
        return result

    @staticmethod
    def _clean_text(value: Any, limit: int) -> str:
        return " ".join(str(value or "").split())[:limit]

    @staticmethod
    def _safe_http_url(value: Any) -> Optional[str]:
        raw = str(value or "").strip()
        parsed = urlparse(raw)
        if parsed.scheme.lower() not in {"http", "https"} or not parsed.netloc:
            return None
        return raw

    @staticmethod
    def _published_at(value: Any) -> Optional[str]:
        raw = str(value or "").strip()
        if not raw:
            return None
        if raw.isdigit():
            try:
                timestamp = float(raw)
                if timestamp > 10_000_000_000:
                    timestamp /= 1000
                return datetime.fromtimestamp(timestamp, tz=timezone.utc).isoformat()
            except (ValueError, OSError, OverflowError):
                return None
        return raw
