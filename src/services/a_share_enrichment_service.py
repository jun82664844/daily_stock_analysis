# -*- coding: utf-8 -*-
"""Local A-share enrichment adapter inspired by a-stock-data.

This POC keeps the quick query lane deterministic: no AI calls, no public
search, no hard dependency on third-party unofficial endpoints.
"""

from __future__ import annotations

import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional


HttpGet = Callable[..., dict[str, Any]]


class AShareEnrichmentService:
    """Build compact A-share information channels with safe degradation."""

    CHANNELS = ("announcements", "capital_flow", "sector", "research", "dragon_tiger")
    CHANNEL_SLUGS = {
        "announcements": "announcements",
        "capital_flow": "fund-flow",
        "sector": "concept-blocks",
        "research": "reports",
        "dragon_tiger": "dragon-tiger",
    }

    def __init__(
        self,
        *,
        http_get: Optional[HttpGet] = None,
        timeout_seconds: Optional[float] = None,
        http_enabled: Optional[bool] = None,
        source_mode: Optional[str] = None,
        cache_ttl_seconds: Optional[float] = None,
        min_interval_seconds: Optional[float] = None,
        skill_root: Optional[str] = None,
        skill_revision: Optional[str] = None,
        time_provider: Optional[Callable[[], float]] = None,
    ) -> None:
        self.timeout_seconds = max(0.1, float(timeout_seconds or os.getenv("A_STOCK_DATA_POC_TIMEOUT_SEC", "1.2")))
        self.source_mode = self._normalize_source_mode(source_mode or os.getenv("A_STOCK_DATA_SOURCE_MODE", "poc"))
        self.cache_ttl_seconds = max(
            0.0,
            float(
                cache_ttl_seconds
                if cache_ttl_seconds is not None
                else os.getenv("A_STOCK_DATA_CACHE_TTL_SEC", "600")
            ),
        )
        self.min_interval_seconds = max(
            0.0,
            float(
                min_interval_seconds
                if min_interval_seconds is not None
                else os.getenv("A_STOCK_DATA_MIN_INTERVAL_SEC", "1")
            ),
        )
        self.skill_root = skill_root or os.getenv(
            "A_STOCK_DATA_SKILL_ROOT",
            r"C:\Users\26879\Documents\Codex\external\a-stock-data",
        )
        self.skill_revision = skill_revision or os.getenv("A_STOCK_DATA_SKILL_REVISION") or self._detect_skill_revision()
        self._time_provider = time_provider or time.monotonic
        self._cache: dict[tuple[str, str], dict[str, Any]] = {}
        self._last_request_at: dict[tuple[str, str], float] = {}
        enabled = http_enabled
        if enabled is None:
            enabled = self._env_flag("A_STOCK_DATA_HTTP_ENABLED") or self._env_flag("A_STOCK_DATA_POC_HTTP_ENABLED")
        if self.source_mode == "off":
            self.http_get = None
        else:
            self.http_get = http_get if http_get is not None else (self._default_http_get if enabled else None)

    def get_enrichment(
        self,
        stock_code: str,
        *,
        stock_name: str | None = None,
        profile: Optional[dict[str, Any]] = None,
        quote: Optional[dict[str, Any]] = None,
        indicators: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        code = self._normalize_code(stock_code)
        fetched: dict[str, dict[str, Any] | None] = {}
        errors: dict[str, str] = {}
        diagnostics: dict[str, Any] = self._new_diagnostics(errors)

        for channel in self.CHANNELS:
            fetched[channel] = self._fetch_channel(channel, code=code, errors=errors, diagnostics=diagnostics)

        has_external_data = any(self._has_external_payload(fetched.get(channel)) for channel in self.CHANNELS)
        if not has_external_data:
            channels = self._quick_reference_channels(
                stock_name=stock_name or code,
                quote=quote,
                profile=profile,
                indicators=indicators,
            )
            any_available = any(item["status"] == "available" for item in channels)
            return {
                "title": "A-share quick reference",
                "summary": self._quick_reference_summary(stock_name or code),
                "status": "available" if any_available else "degraded",
                "source": "basic_quote_snapshot",
                "updated_at": self._now_iso(),
                "ai_used": False,
                "public_search_used": False,
                "source_mode": self.source_mode,
                "skill": self._skill_metadata(),
                "diagnostics": diagnostics,
                "channels": channels,
                "premium_unlock": "Premium can add live announcements, fund-flow history, research PDFs, sector linkage, and dragon-tiger seat details.",
                "boundary": "Information analysis only; not investment advice.",
            }

        channels = [
            self._announcements_channel(code, stock_name, fetched.get("announcements")),
            self._capital_flow_channel(code, stock_name, quote, fetched.get("capital_flow")),
            self._sector_channel(code, stock_name, profile, fetched.get("sector")),
            self._research_channel(code, stock_name, fetched.get("research")),
            self._dragon_tiger_channel(code, stock_name, fetched.get("dragon_tiger")),
        ]
        any_available = any(item["status"] == "available" for item in channels)
        status = "degraded" if errors or diagnostics["rate_limited_channels"] or not any_available else "available"
        summary = self._summary(stock_name or code, profile=profile, quote=quote, status=status)
        source = "a_stock_data_skill_adapter" if self.source_mode == "a_stock_data" else "a_stock_data_poc_adapter"
        return {
            "title": "A-share enrichment",
            "summary": summary,
            "status": status,
            "source": source,
            "updated_at": self._now_iso(),
            "ai_used": False,
            "public_search_used": False,
            "source_mode": self.source_mode,
            "skill": self._skill_metadata(),
            "diagnostics": diagnostics,
            "channels": channels,
            "premium_unlock": "Premium can expand announcement source text, research PDFs, fund-flow history, sector linkage, and dragon-tiger seat details.",
            "boundary": "Information analysis only; not investment advice.",
        }

    def _fetch_channel(
        self,
        channel: str,
        *,
        code: str,
        errors: dict[str, str],
        diagnostics: dict[str, Any],
    ) -> dict[str, Any] | None:
        if self.http_get is None:
            return None
        now = self._time_provider()
        cache_key = (channel, code)
        cached = self._cache.get(cache_key)
        if self._cache_is_fresh(cached, now):
            diagnostics["cache"]["hits"] += 1
            return cached["payload"]
        last_request_at = self._last_request_at.get(cache_key)
        if (
            self.min_interval_seconds > 0
            and last_request_at is not None
            and now - last_request_at < self.min_interval_seconds
        ):
            diagnostics["rate_limited_channels"].append(channel)
            if cached is not None:
                diagnostics["cache"]["stale_hits"] += 1
                return cached["payload"]
            errors[channel] = "rate_limited"
            return None
        diagnostics["cache"]["misses"] += 1
        self._last_request_at[cache_key] = now
        try:
            url = self._channel_url(channel)
            result = self.http_get(
                url,
                params={"code": code, "channel": channel, "source_mode": self.source_mode},
                headers={"User-Agent": "DSA local a-stock-data adapter"},
                timeout=self.timeout_seconds,
            )
            if not isinstance(result, dict):
                return None
            if self._has_external_payload(result):
                self._cache[cache_key] = {"payload": result, "fetched_at": now}
            return result
        except Exception as exc:
            errors[channel] = type(exc).__name__
            return None

    def _channel_url(self, channel: str) -> str:
        if self.source_mode == "a_stock_data":
            return f"a-stock-data://{channel}"
        slug = self.CHANNEL_SLUGS.get(channel, channel.replace("_", "-"))
        return f"a-stock-data-poc://{slug}"

    def _new_diagnostics(self, errors: dict[str, str]) -> dict[str, Any]:
        return {
            "source_mode": self.source_mode,
            "cache": {"hits": 0, "stale_hits": 0, "misses": 0},
            "rate_limited_channels": [],
            "errors": errors,
        }

    def _cache_is_fresh(self, cached: dict[str, Any] | None, now: float) -> bool:
        if cached is None:
            return False
        fetched_at = self._float_or_none(cached.get("fetched_at"))
        if fetched_at is None:
            return False
        return now - fetched_at <= self.cache_ttl_seconds

    def _skill_metadata(self) -> dict[str, Any]:
        root = Path(self.skill_root)
        return {
            "name": "simonlin1212/a-stock-data",
            "mode": "reference_adapter",
            "installed": (root / "SKILL.md").exists(),
            "revision": self.skill_revision,
        }

    def _detect_skill_revision(self) -> str:
        head_path = Path(self.skill_root or "") / ".git" / "HEAD"
        try:
            head = head_path.read_text(encoding="utf-8", errors="replace").strip()
            if head.startswith("ref:"):
                ref_path = Path(self.skill_root) / ".git" / head.split(" ", 1)[1]
                return ref_path.read_text(encoding="utf-8", errors="replace").strip()[:7]
            return head[:7]
        except Exception:
            return "unknown"

    def _normalize_source_mode(self, value: str) -> str:
        normalized = str(value or "poc").strip().lower().replace("-", "_")
        if normalized in {"a_stock_data", "skill", "real"}:
            return "a_stock_data"
        if normalized in {"off", "disabled", "none"}:
            return "off"
        return "poc"

    def _env_flag(self, name: str) -> bool:
        return os.getenv(name, "false").lower() in {"1", "true", "yes", "on"}

    def _has_external_payload(self, payload: dict[str, Any] | None) -> bool:
        if not isinstance(payload, dict) or not payload:
            return False
        items = payload.get("items")
        if isinstance(items, list):
            return bool(items)
        return any(value not in (None, "", [], {}) for value in payload.values())

    def _quick_reference_summary(self, label: str) -> str:
        return (
            f"{label} quick reference uses quote, moving-average, volume, valuation, and freshness data. "
            "External announcements, fund-flow, research, and dragon-tiger seats are not enabled in free quick mode."
        )

    def _quick_reference_channels(
        self,
        *,
        stock_name: str,
        quote: dict[str, Any] | None,
        profile: dict[str, Any] | None,
        indicators: dict[str, Any] | None,
    ) -> list[dict[str, Any]]:
        return [
            self._price_structure_channel(stock_name, quote, indicators),
            self._volume_activity_channel(quote, indicators),
            self._valuation_snapshot_channel(profile),
            self._trend_windows_channel(indicators),
            self._data_quality_channel(quote, profile),
        ]

    def _price_structure_channel(
        self,
        stock_name: str,
        quote: dict[str, Any] | None,
        indicators: dict[str, Any] | None,
    ) -> dict[str, Any]:
        price = self._float_or_none((quote or {}).get("current_price"))
        change = self._float_or_none((quote or {}).get("change_percent"))
        open_price = self._float_or_none((quote or {}).get("open"))
        high = self._float_or_none((quote or {}).get("high"))
        low = self._float_or_none((quote or {}).get("low"))
        ma20 = self._float_or_none((indicators or {}).get("ma20"))
        status = "available" if price is not None else "degraded"
        if price is not None and ma20 is not None:
            position = "above" if price >= ma20 else "below"
            position_text = f"price is {position} MA20 {self._format_number(ma20)}"
        else:
            position_text = "MA20 context is incomplete"
        return self._channel(
            "price_structure",
            "Price structure",
            (
                f"Latest {self._format_number_or_dash(price)}, change {self._format_percent(change)}, "
                f"open {self._format_number_or_dash(open_price)}, high {self._format_number_or_dash(high)}, "
                f"low {self._format_number_or_dash(low)}; {position_text}."
            ),
            status=status,
            source="basic_quote_snapshot",
            action=f"Use this as a first-pass structure check for {stock_name}; refresh stale quotes before comparing intraday moves.",
        )

    def _volume_activity_channel(
        self,
        quote: dict[str, Any] | None,
        indicators: dict[str, Any] | None,
    ) -> dict[str, Any]:
        volume = self._float_or_none((quote or {}).get("volume"))
        amount = self._float_or_none((quote or {}).get("amount"))
        volume_change = self._float_or_none((indicators or {}).get("volume_change_vs_ma5"))
        status = "available" if volume is not None or amount is not None or volume_change is not None else "degraded"
        change_text = (
            f"volume is {self._format_percent(volume_change)} versus MA5"
            if volume_change is not None
            else "volume versus MA5 is incomplete"
        )
        return self._channel(
            "volume_activity",
            "Volume activity",
            f"Volume {self._format_money(volume)}, amount {self._format_money(amount)}; {change_text}.",
            status=status,
            source="basic_indicator_snapshot",
            action="Use volume only as confirmation; price and source freshness come first.",
        )

    def _valuation_snapshot_channel(self, profile: dict[str, Any] | None) -> dict[str, Any]:
        market_cap = self._float_or_none((profile or {}).get("market_cap"))
        pe_ratio = self._float_or_none((profile or {}).get("pe_ratio"))
        pb_ratio = self._float_or_none((profile or {}).get("pb_ratio"))
        parts = [
            f"Market cap {self._format_money(market_cap)}" if market_cap is not None else None,
            f"PE {self._format_number(pe_ratio)}" if pe_ratio is not None else None,
            f"PB {self._format_number(pb_ratio)}" if pb_ratio is not None else None,
        ]
        available_parts = [part for part in parts if part]
        summary = "; ".join(available_parts) + "." if available_parts else "Valuation fields are not available in the free quick snapshot."
        return self._channel(
            "valuation_snapshot",
            "Valuation snapshot",
            summary,
            status="available" if available_parts else "degraded",
            source="basic_profile_snapshot",
            action="Use valuation as context, not as a timing signal.",
        )

    def _trend_windows_channel(self, indicators: dict[str, Any] | None) -> dict[str, Any]:
        ma5 = self._float_or_none((indicators or {}).get("ma5"))
        ma10 = self._float_or_none((indicators or {}).get("ma10"))
        ma20 = self._float_or_none((indicators or {}).get("ma20"))
        change_5d = self._float_or_none((indicators or {}).get("price_change_5d"))
        change_20d = self._float_or_none((indicators or {}).get("price_change_20d"))
        last_close = self._float_or_none((indicators or {}).get("last_close"))
        has_value = any(value is not None for value in (ma5, ma10, ma20, change_5d, change_20d, last_close))
        return self._channel(
            "trend_windows",
            "Trend windows",
            (
                f"5-day change {self._format_percent(change_5d)}; 20-day change {self._format_percent(change_20d)}; "
                f"MA5 {self._format_number_or_dash(ma5)}, MA10 {self._format_number_or_dash(ma10)}, "
                f"MA20 {self._format_number_or_dash(ma20)}; last close {self._format_number_or_dash(last_close)}."
            ),
            status="available" if has_value else "degraded",
            source="basic_indicator_snapshot",
            action="Compare short-window moves with MA20 before reading the trend as repaired.",
        )

    def _data_quality_channel(
        self,
        quote: dict[str, Any] | None,
        profile: dict[str, Any] | None,
    ) -> dict[str, Any]:
        quote_freshness = str((quote or {}).get("freshness") or "unknown")
        profile_freshness = str((profile or {}).get("freshness") or "unknown")
        quote_source = str((quote or {}).get("source") or "unknown")
        return self._channel(
            "data_quality",
            "Data quality",
            f"Quote freshness {quote_freshness}; profile freshness {profile_freshness}; quote source {quote_source}.",
            status="available" if quote_freshness != "unknown" or quote_source != "unknown" else "degraded",
            source="basic_data_quality_snapshot",
            action="Treat stale or cached data as provisional and refresh before acting on changes.",
        )

    def _announcements_channel(
        self,
        code: str,
        stock_name: str | None,
        payload: dict[str, Any] | None,
    ) -> dict[str, Any]:
        item = self._first_item(payload)
        if item:
            title = str(item.get("title") or "Latest announcement")
            date = str(item.get("date") or "").strip()
            summary = f"{date + ' ' if date else ''}{title}"
            return self._channel(
                "announcements",
                "Announcements channel",
                summary,
                status="available",
                source="a_stock_data_cninfo_or_f10",
                action="Deep mode can expand original announcement text and source links.",
            )
        return self._channel(
            "announcements",
            "Announcements channel",
            f"{stock_name or code} keeps a reserved CNINFO / TDX F10 announcements lane; quick mode shows the checklist entry only.",
            status="degraded",
            source="a_stock_data_poc_local_rules",
            action="Later versions can enable cached announcement fetching without calling external sources on every query.",
        )

    def _capital_flow_channel(
        self,
        code: str,
        stock_name: str | None,
        quote: dict[str, Any] | None,
        payload: dict[str, Any] | None,
    ) -> dict[str, Any]:
        main_net = self._float_or_none((payload or {}).get("main_net"))
        ratio = self._float_or_none((payload or {}).get("main_net_ratio"))
        if main_net is not None:
            ratio_text = f", ratio {self._format_percent(ratio)}" if ratio is not None else ""
            return self._channel(
                "capital_flow",
                "Fund-flow channel",
                f"Main fund net inflow is {self._format_money(main_net)}{ratio_text}.",
                status="available",
                source="a_stock_data_eastmoney_fund_flow",
                action="Check whether main fund inflow is continuous across several sessions, not only a single-day move.",
            )
        change_percent = self._float_or_none((quote or {}).get("change_percent"))
        price_hint = f" Current change is {self._format_percent(change_percent)}." if change_percent is not None else ""
        return self._channel(
            "capital_flow",
            "Fund-flow channel",
            f"{stock_name or code} keeps a reserved Eastmoney fund-flow lane.{price_hint}".strip(),
            status="degraded",
            source="a_stock_data_poc_local_rules",
            action="Later versions can add cached daily fund flow by main, large, medium, and small orders.",
        )

    def _sector_channel(
        self,
        code: str,
        stock_name: str | None,
        profile: dict[str, Any] | None,
        payload: dict[str, Any] | None,
    ) -> dict[str, Any]:
        concepts = payload.get("concepts") if isinstance(payload, dict) else None
        concepts_list = [str(item) for item in concepts or [] if item]
        industry = str((payload or {}).get("industry") or (profile or {}).get("industry") or "").strip()
        sector = str((profile or {}).get("sector") or "").strip()
        bits = [bit for bit in [sector, industry, " / ".join(concepts_list[:3])] if bit]
        if bits:
            return self._channel(
                "sector",
                "Sector channel",
                f"{stock_name or code} current context: {'; '.join(bits)}.",
                status="available",
                source="a_stock_data_eastmoney_concept_blocks",
                action="Compare move, valuation, and fund flow against the same sector.",
            )
        return self._channel(
            "sector",
            "Sector channel",
            f"{stock_name or code} has no usable sector tags yet; later versions can add Eastmoney concepts and industry mapping.",
            status="degraded",
            source="a_stock_data_poc_local_rules",
            action="Refresh profile data or enable sector sources before comparing peers.",
        )

    def _research_channel(
        self,
        code: str,
        stock_name: str | None,
        payload: dict[str, Any] | None,
    ) -> dict[str, Any]:
        item = self._first_item(payload)
        if item:
            title = str(item.get("title") or "Institutional research")
            rating = str(item.get("rating") or "").strip()
            rating_text = f"; rating {rating}" if rating else ""
            return self._channel(
                "research",
                "Research channel",
                f"Latest research: {title}{rating_text}.",
                status="available",
                source="a_stock_data_eastmoney_reportapi",
                action="Premium can expand research lists, PDFs, and institution forecast fields.",
            )
        return self._channel(
            "research",
            "Research channel",
            f"{stock_name or code} keeps a reserved Eastmoney / iFinD research lane; free quick mode does not fetch PDFs.",
            status="degraded",
            source="a_stock_data_poc_local_rules",
            action="Deep mode can fetch research sources by symbol and industry.",
        )

    def _dragon_tiger_channel(
        self,
        code: str,
        stock_name: str | None,
        payload: dict[str, Any] | None,
    ) -> dict[str, Any]:
        item = self._first_item(payload)
        net_buy = self._float_or_none((item or {}).get("net_buy"))
        if item:
            date = str(item.get("date") or "").strip()
            buy_text = f", net buy {self._format_money(net_buy)}" if net_buy is not None else ""
            return self._channel(
                "dragon_tiger",
                "Dragon-tiger channel",
                f"{date + ' ' if date else ''}Dragon-tiger list record exists{buy_text}.",
                status="available",
                source="a_stock_data_eastmoney_datacenter",
                action="Focus on institution seats and brokerage buy/sell direction.",
            )
        return self._channel(
            "dragon_tiger",
            "Dragon-tiger channel",
            f"{stock_name or code} keeps a reserved dragon-tiger seat lane; seat details are not fetched in quick mode.",
            status="degraded",
            source="a_stock_data_poc_local_rules",
            action="Fetch seat details only after unusual moves or limit-up events to reduce source pressure.",
        )

    def _channel(
        self,
        category: str,
        title: str,
        summary: str,
        *,
        status: str,
        source: str,
        action: str,
    ) -> dict[str, Any]:
        return {
            "category": category,
            "title": title,
            "summary": summary,
            "status": status,
            "source": source,
            "action": action,
            "updated_at": self._now_iso(),
        }

    def _default_http_get(self, url: str, *, params=None, headers=None, timeout=None) -> dict[str, Any]:
        try:
            import requests

            response = requests.get(url, params=params, headers=headers, timeout=timeout)
            response.raise_for_status()
            data = response.json()
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    def _summary(
        self,
        label: str,
        *,
        profile: dict[str, Any] | None,
        quote: dict[str, Any] | None,
        status: str,
    ) -> str:
        context = " / ".join(
            str(value)
            for value in ((profile or {}).get("sector"), (profile or {}).get("industry"))
            if value
        )
        price = self._float_or_none((quote or {}).get("current_price"))
        change = self._float_or_none((quote or {}).get("change_percent"))
        price_text = ""
        if price is not None:
            price_text = f" Last price {self._format_number(price)}"
            if change is not None:
                price_text += f", change {self._format_percent(change)}"
        status_text = "is available through the local POC lane" if status == "available" else "is degraded through local rules"
        context_text = f" Context: {context}." if context else ""
        return f"{label} A-share enrichment for announcements, fund flow, sectors, research, and dragon-tiger data {status_text}.{context_text}{price_text}".strip()

    def _first_item(self, payload: dict[str, Any] | None) -> dict[str, Any] | None:
        items = payload.get("items") if isinstance(payload, dict) else None
        if isinstance(items, list) and items and isinstance(items[0], dict):
            return items[0]
        return None

    def _normalize_code(self, stock_code: str) -> str:
        raw = str(stock_code or "").strip().upper()
        match = re.search(r"(\d{6})", raw)
        return match.group(1) if match else raw

    def _float_or_none(self, value: Any) -> float | None:
        if value in (None, ""):
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    def _format_money(self, value: float | None) -> str:
        if value is None:
            return "-"
        absolute = abs(value)
        if absolute >= 1_000_000_000_000:
            return f"{self._format_scaled(value, 1_000_000_000_000, 4)}T"
        if absolute >= 1_000_000_000:
            return f"{self._format_scaled(value, 1_000_000_000, 2)}B"
        if absolute >= 1_000_000:
            return f"{self._format_scaled(value, 1_000_000, 2)}M"
        if absolute >= 1_000:
            return f"{self._format_scaled(value, 1_000, 1)}K"
        return self._format_number(value)

    def _format_percent(self, value: float | None) -> str:
        return "-" if value is None else f"{self._format_number(value)}%"

    def _format_number_or_dash(self, value: float | None) -> str:
        return "-" if value is None else self._format_number(value)

    def _format_scaled(self, value: float, divisor: float, decimals: int) -> str:
        return f"{value / divisor:.{decimals}f}".rstrip("0").rstrip(".")

    def _format_number(self, value: float) -> str:
        text = f"{value:.4f}".rstrip("0").rstrip(".")
        return text or "0"

    def _now_iso(self) -> str:
        return datetime.now(timezone.utc).replace(microsecond=0).isoformat()
