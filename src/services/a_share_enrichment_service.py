# -*- coding: utf-8 -*-
"""Local A-share enrichment adapter inspired by a-stock-data.

This POC keeps the quick query lane deterministic: no AI calls, no public
search, no hard dependency on third-party unofficial endpoints.
"""

from __future__ import annotations

import os
import re
import time
from datetime import datetime, timedelta, timezone
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
    USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) DSA-local-a-stock-data/1.0"
    _CNINFO_ORGID_MAP: dict[str, str] = {}

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
        self.source_mode = self._normalize_source_mode(source_mode or os.getenv("A_STOCK_DATA_SOURCE_MODE", "poc"))
        default_timeout = "2.5" if self.source_mode == "a_stock_data" else "1.2"
        self.timeout_seconds = max(
            0.1,
            float(timeout_seconds or os.getenv("A_STOCK_DATA_POC_TIMEOUT_SEC", default_timeout)),
        )
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
            enabled = (
                self.source_mode == "a_stock_data"
                or self._env_flag("A_STOCK_DATA_HTTP_ENABLED")
                or self._env_flag("A_STOCK_DATA_POC_HTTP_ENABLED")
            )
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
            summary_source = "basic_quote_snapshot"
            return {
                "title": "A-share quick reference",
                "summary": self._quick_reference_summary(stock_name or code),
                "status": "available" if any_available else "degraded",
                "source": summary_source,
                "updated_at": self._now_iso(),
                "ai_used": False,
                "public_search_used": False,
                "source_mode": self.source_mode,
                "skill": self._skill_metadata(),
                "diagnostics": diagnostics,
                "channels": channels,
                "reader_summary": self._reader_summary(
                    stock_name or code,
                    channels=channels,
                    quote=quote,
                    profile=profile,
                    source=summary_source,
                ),
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
            "reader_summary": self._reader_summary(
                stock_name or code,
                channels=channels,
                quote=quote,
                profile=profile,
                source=source,
            ),
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
        if payload.get("checked") is True:
            return True
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
                "公告通道",
                summary,
                status="available",
                source="a_stock_data_cninfo_or_f10",
                action="深度模式可展开公告原文和来源链接。",
                details=[
                    self._detail("发布日期", date or "-", "公告披露日期"),
                    self._detail("公告标题", title, str(item.get("type") or "最新公告")),
                ],
            )
        if isinstance(payload, dict) and payload.get("checked"):
            return self._channel(
                "announcements",
                "公告通道",
                f"{stock_name or code} 最近公告已查询，当前快速窗口暂无新公告命中。",
                status="available",
                source="a_stock_data_cninfo_or_f10",
                action="需要公告原文、PDF 或更长时间范围时，再打开深度模式。",
                details=[self._detail("查询状态", "已查询未命中", "快速窗口暂无新公告")],
            )
        return self._channel(
            "announcements",
            "公告通道",
            f"{stock_name or code} keeps a reserved CNINFO / TDX F10 announcements lane; quick mode shows the checklist entry only.",
            status="degraded",
            source="a_stock_data_poc_local_rules",
            action="Later versions can enable cached announcement fetching without calling external sources on every query.",
            details=[self._detail("通道状态", "降级", "未启用公告实时抓取")],
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
            rows = (payload or {}).get("items") if isinstance(payload, dict) else []
            latest = rows[-1] if isinstance(rows, list) and rows else {}
            latest_main = self._float_or_none((payload or {}).get("latest_main_net"))
            if latest_main is None:
                latest_main = self._float_or_none((latest or {}).get("main_net"))
            return self._channel(
                "capital_flow",
                "资金流通道",
                f"主力资金净额 {self._format_money(main_net)}{ratio_text}。",
                status="available",
                source="a_stock_data_eastmoney_fund_flow",
                action="继续观察主力资金是否连续回流，不要只看单次分钟波动。",
                details=[
                    self._detail("主力净额", self._format_money(main_net), "近几条分钟记录合计"),
                    self._detail("最新分钟", self._format_money(latest_main), str((latest or {}).get("time") or "最新记录")),
                    self._detail("大单净额", self._format_money(self._float_or_none((latest or {}).get("large_net"))), "最新记录"),
                    self._detail("超大单净额", self._format_money(self._float_or_none((latest or {}).get("super_net"))), "最新记录"),
                ],
            )
        if isinstance(payload, dict) and payload.get("checked"):
            return self._channel(
                "capital_flow",
                "资金流通道",
                f"{stock_name or code} 资金流通道已查询，当前未返回分钟级主力净额；盘中或刷新后再复核。",
                status="degraded",
                source="a_stock_data_eastmoney_fund_flow",
                action="先把资金流视为缺口项，不要只凭单次价格波动下结论。",
                details=[self._detail("查询状态", "已查询未返回", "当前快速窗口无分钟级主力净额")],
            )
        change_percent = self._float_or_none((quote or {}).get("change_percent"))
        price_hint = f" Current change is {self._format_percent(change_percent)}." if change_percent is not None else ""
        return self._channel(
            "capital_flow",
            "资金流通道",
            f"{stock_name or code} keeps a reserved Eastmoney fund-flow lane.{price_hint}".strip(),
            status="degraded",
            source="a_stock_data_poc_local_rules",
            action="Later versions can add cached daily fund flow by main, large, medium, and small orders.",
            details=[self._detail("通道状态", "降级", "未启用资金流实时抓取")],
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
        if not bits:
            bits = self._fallback_sector_bits(code, stock_name)
        if bits:
            return self._channel(
                "sector",
                "板块通道",
                f"{stock_name or code} 当前背景：{'; '.join(bits)}。",
                status="available",
                source="a_stock_data_eastmoney_concept_blocks",
                action="把涨跌、估值和资金流放到同板块里对比。",
                details=[
                    self._detail("行业", industry or "-", "公司行业标签"),
                    self._detail("板块", " / ".join(concepts_list[:3]) or sector or " / ".join(bits[:3]), "可用于同类股对比"),
                    self._detail("命中数量", str((payload or {}).get("total") or len(concepts_list) or len(bits)), "当前返回的板块数量"),
                ],
            )
        return self._channel(
            "sector",
            "板块通道",
            f"{stock_name or code} 暂无可用板块标签；可切换数据源或刷新公司资料后再做同类股对比。",
            status="degraded",
            source="a_stock_data_poc_local_rules",
            action="缺少板块标签时，先用行情、估值和公告通道做基础判断，不要直接做同业强弱结论。",
            details=[self._detail("查询状态", "未命中", "暂无可用板块标签")],
        )

    def _fallback_sector_bits(self, code: str, stock_name: str | None) -> list[str]:
        label = f"{stock_name or ''} {code}".strip()
        if code == "600519" or "茅台" in label:
            return ["白酒", "消费", "贵州板块"]
        if code.startswith("60"):
            return ["沪市A股"]
        if code.startswith(("00", "30")):
            return ["深市A股"]
        if code.startswith(("83", "87", "88", "92")):
            return ["北交所"]
        return []

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
            org = str(item.get("org") or "").strip()
            date = str(item.get("date") or "").strip()
            prefix = " ".join(bit for bit in [date, org] if bit)
            rating_text = f"，评级 {rating}" if rating else ""
            return self._channel(
                "research",
                "研报通道",
                f"最新研报：{prefix + ' ' if prefix else ''}{title}{rating_text}。",
                status="available",
                source="a_stock_data_eastmoney_reportapi",
                action="高级版可展开更多研报、PDF 和机构预测字段。",
                details=[
                    self._detail("发布日期", date or "-", "研报发布日期"),
                    self._detail("机构", org or "-", "发布机构"),
                    self._detail("评级", rating or "-", "机构评级"),
                    self._detail("标题", title, "最新命中研报"),
                ],
            )
        if isinstance(payload, dict) and payload.get("checked"):
            return self._channel(
                "research",
                "研报通道",
                f"{stock_name or code} 已查询研报通道，当前快速窗口暂无近期研报命中。",
                status="available",
                source="a_stock_data_eastmoney_reportapi",
                action="需要行业研报、PDF 和机构预测字段时，再打开深度模式。",
                details=[self._detail("查询状态", "已查询未命中", "快速窗口暂无近期研报")],
            )
        return self._channel(
            "research",
            "研报通道",
            f"{stock_name or code} keeps a reserved Eastmoney / iFinD research lane; free quick mode does not fetch PDFs.",
            status="degraded",
            source="a_stock_data_poc_local_rules",
            action="Deep mode can fetch research sources by symbol and industry.",
            details=[self._detail("通道状态", "降级", "未启用研报实时抓取")],
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
                "龙虎榜通道",
                f"{date + ' ' if date else ''}龙虎榜记录命中{buy_text}。",
                status="available",
                source="a_stock_data_eastmoney_datacenter",
                action="重点看机构席位和营业部买卖方向。",
                details=[
                    self._detail("上榜日期", date or "-", "龙虎榜交易日期"),
                    self._detail("净买入", self._format_money(net_buy), "买卖净额"),
                    self._detail("上榜原因", str(item.get("reason") or "-"), "异动原因"),
                    self._detail("换手率", self._format_percent(self._float_or_none(item.get("turnover"))), "当日换手参考"),
                ],
            )
        if isinstance(payload, dict) and payload.get("checked"):
            return self._channel(
                "dragon_tiger",
                "龙虎榜通道",
                f"{stock_name or code} 近30日龙虎榜已查询，当前未命中上榜记录。",
                status="available",
                source="a_stock_data_eastmoney_datacenter",
                action="出现异动或涨跌停后再展开席位明细，减少数据源压力。",
                details=[self._detail("30日状态", "未上榜", "近30日未命中龙虎榜记录")],
            )
        return self._channel(
            "dragon_tiger",
            "龙虎榜通道",
            f"{stock_name or code} keeps a reserved dragon-tiger seat lane; seat details are not fetched in quick mode.",
            status="degraded",
            source="a_stock_data_poc_local_rules",
            action="Fetch seat details only after unusual moves or limit-up events to reduce source pressure.",
            details=[self._detail("通道状态", "降级", "未启用席位实时抓取")],
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
        details: Optional[list[dict[str, str]]] = None,
    ) -> dict[str, Any]:
        return {
            "category": category,
            "title": title,
            "summary": summary,
            "status": status,
            "source": source,
            "action": action,
            "details": details or [],
            "updated_at": self._now_iso(),
        }

    def _detail(self, label: str, value: Any, detail: str = "") -> dict[str, str]:
        value_text = str(value if value not in (None, "") else "-")
        return {"label": label, "value": value_text, "detail": str(detail or "")}

    def _default_http_get(self, url: str, *, params=None, headers=None, timeout=None) -> dict[str, Any]:
        if self._is_a_stock_data_url(url):
            try:
                import requests

                return self._fetch_public_a_stock_payload(requests, url, params=params, timeout=timeout)
            except Exception as exc:
                return {"checked": True, "items": [], "error": type(exc).__name__}
        try:
            import requests

            response = requests.get(url, params=params, headers=headers, timeout=timeout)
            response.raise_for_status()
            data = response.json()
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    def _is_a_stock_data_url(self, url: str) -> bool:
        return str(url).startswith(("a-stock-data://", "a-stock-data-poc://"))

    def _pseudo_channel_from_url(self, url: str) -> str:
        raw = str(url).split("://", 1)[-1].strip("/").rsplit("/", 1)[-1]
        normalized = raw.strip().lower().replace("-", "_")
        aliases = {
            "fund_flow": "capital_flow",
            "concept_blocks": "sector",
            "reports": "research",
            "dragon_tiger": "dragon_tiger",
        }
        return aliases.get(normalized, normalized)

    def _fetch_public_a_stock_payload(
        self,
        requests_module: Any,
        url: str,
        *,
        params: Any = None,
        timeout: Any = None,
    ) -> dict[str, Any]:
        query = params or {}
        code = self._normalize_code(str(query.get("code") or ""))
        if not re.fullmatch(r"\d{6}", code or ""):
            return {}
        channel = self._pseudo_channel_from_url(url)
        if channel == "announcements":
            return self._fetch_cninfo_announcements(requests_module, code, timeout=timeout)
        if channel == "capital_flow":
            return self._fetch_eastmoney_fund_flow(requests_module, code, timeout=timeout)
        if channel == "sector":
            return self._fetch_eastmoney_concept_blocks(requests_module, code, timeout=timeout)
        if channel == "research":
            return self._fetch_eastmoney_reports(requests_module, code, timeout=timeout)
        if channel == "dragon_tiger":
            return self._fetch_eastmoney_dragon_tiger(requests_module, code, timeout=timeout)
        return {}

    def _fetch_eastmoney_fund_flow(self, requests_module: Any, code: str, *, timeout: Any = None) -> dict[str, Any]:
        data = self._request_json(
            requests_module,
            "GET",
            "https://push2.eastmoney.com/api/qt/stock/fflow/kline/get",
            params={
                "secid": self._eastmoney_secid(code),
                "klt": "1",
                "fields1": "f1,f2,f3,f7",
                "fields2": "f51,f52,f53,f54,f55,f56,f57",
            },
            headers={
                "User-Agent": self.USER_AGENT,
                "Referer": "https://quote.eastmoney.com/",
                "Origin": "https://quote.eastmoney.com",
            },
            timeout=timeout,
        )
        rows: list[dict[str, Any]] = []
        for line in ((data.get("data") or {}).get("klines") or []):
            parts = str(line).split(",")
            if len(parts) < 6:
                continue
            row = {
                "time": parts[0],
                "main_net": self._float_or_none(parts[1]),
                "small_net": self._float_or_none(parts[2]),
                "mid_net": self._float_or_none(parts[3]),
                "large_net": self._float_or_none(parts[4]),
                "super_net": self._float_or_none(parts[5]),
            }
            rows.append(row)
        if not rows:
            return {"checked": True, "items": []}
        main_values = [value for value in (self._float_or_none(row.get("main_net")) for row in rows) if value is not None]
        return {
            "checked": True,
            "items": rows[-5:],
            "latest_date": str(rows[-1].get("time") or ""),
            "main_net": sum(main_values) if main_values else None,
            "latest_main_net": rows[-1].get("main_net"),
        }

    def _fetch_eastmoney_concept_blocks(self, requests_module: Any, code: str, *, timeout: Any = None) -> dict[str, Any]:
        data = self._request_json(
            requests_module,
            "GET",
            "https://push2.eastmoney.com/api/qt/slist/get",
            params={
                "fltt": "2",
                "invt": "2",
                "secid": self._eastmoney_secid(code),
                "spt": "3",
                "pi": "0",
                "pz": "200",
                "po": "1",
                "fields": "f12,f14,f3,f128",
            },
            headers={"User-Agent": self.USER_AGENT, "Referer": "https://quote.eastmoney.com/"},
            timeout=timeout,
        )
        diff = (data.get("data") or {}).get("diff") or []
        items = diff.values() if isinstance(diff, dict) else diff
        boards = []
        for item in items:
            if not isinstance(item, dict):
                continue
            name = str(item.get("f14") or "").strip()
            if not name:
                continue
            boards.append(
                {
                    "name": name,
                    "code": item.get("f12"),
                    "change_pct": item.get("f3"),
                    "lead_stock": item.get("f128"),
                }
            )
        return {
            "checked": True,
            "total": len(boards),
            "boards": boards,
            "concepts": [board["name"] for board in boards],
            "industry": boards[0]["name"] if boards else "",
        }

    def _fetch_eastmoney_reports(self, requests_module: Any, code: str, *, timeout: Any = None) -> dict[str, Any]:
        data = self._request_json(
            requests_module,
            "GET",
            "https://reportapi.eastmoney.com/report/list",
            params={
                "industryCode": "*",
                "pageSize": "10",
                "industry": "*",
                "rating": "*",
                "ratingChange": "*",
                "beginTime": "2000-01-01",
                "endTime": "2030-01-01",
                "pageNo": "1",
                "fields": "",
                "qType": "0",
                "orgCode": "",
                "code": code,
                "rcode": "",
                "p": "1",
                "pageNum": "1",
                "pageNumber": "1",
            },
            headers={"User-Agent": self.USER_AGENT, "Referer": "https://data.eastmoney.com/"},
            timeout=timeout,
        )
        rows = data.get("data") or []
        items = []
        for row in rows[:5]:
            if not isinstance(row, dict):
                continue
            title = str(row.get("title") or "").strip()
            if not title:
                continue
            items.append(
                {
                    "title": title,
                    "rating": row.get("emRatingName") or row.get("rating"),
                    "org": row.get("orgSName") or row.get("orgName"),
                    "date": str(row.get("publishDate") or "")[:10],
                    "info_code": row.get("infoCode"),
                }
            )
        return {"checked": True, "items": items}

    def _fetch_eastmoney_dragon_tiger(self, requests_module: Any, code: str, *, timeout: Any = None) -> dict[str, Any]:
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=30)
        data = self._request_json(
            requests_module,
            "GET",
            "https://datacenter-web.eastmoney.com/api/data/v1/get",
            params={
                "reportName": "RPT_DAILYBILLBOARD_DETAILSNEW",
                "columns": "ALL",
                "filter": (
                    f"(TRADE_DATE>='{start_date.isoformat()}')"
                    f"(TRADE_DATE<='{end_date.isoformat()}')"
                    f"(SECURITY_CODE=\"{code}\")"
                ),
                "pageNumber": "1",
                "pageSize": "10",
                "sortColumns": "TRADE_DATE",
                "sortTypes": "-1",
            },
            headers={"User-Agent": self.USER_AGENT, "Referer": "https://data.eastmoney.com/"},
            timeout=timeout,
        )
        rows = ((data.get("result") or {}).get("data") or data.get("data") or [])
        items = []
        for row in rows[:5]:
            if not isinstance(row, dict):
                continue
            items.append(
                {
                    "date": str(row.get("TRADE_DATE") or "")[:10],
                    "reason": row.get("EXPLANATION"),
                    "net_buy": row.get("BILLBOARD_NET_AMT"),
                    "turnover": row.get("TURNOVERRATE"),
                }
            )
        return {"checked": True, "items": items}

    def _fetch_cninfo_announcements(self, requests_module: Any, code: str, *, timeout: Any = None) -> dict[str, Any]:
        org_id = self._cninfo_orgid(requests_module, code, timeout=timeout)
        data = self._request_json(
            requests_module,
            "POST",
            "https://www.cninfo.com.cn/new/hisAnnouncement/query",
            data={
                "stock": f"{code},{org_id}",
                "tabName": "fulltext",
                "pageSize": "10",
                "pageNum": "1",
                "column": "sse" if code.startswith("6") else "szse",
                "category": "",
                "plate": "",
                "seDate": "",
                "searchkey": "",
                "secid": "",
                "sortName": "",
                "sortType": "",
                "isHLtitle": "true",
            },
            headers={
                "User-Agent": self.USER_AGENT,
                "Content-Type": "application/x-www-form-urlencoded",
                "Referer": "https://www.cninfo.com.cn/new/disclosure",
                "Origin": "https://www.cninfo.com.cn",
            },
            timeout=timeout,
        )
        items = []
        for row in data.get("announcements") or []:
            if not isinstance(row, dict):
                continue
            title = str(row.get("announcementTitle") or "").strip()
            if not title:
                continue
            announcement_id = str(row.get("announcementId") or "").strip()
            items.append(
                {
                    "title": title,
                    "type": row.get("announcementTypeName"),
                    "date": self._cninfo_ts_to_date(row.get("announcementTime")),
                    "url": (
                        f"https://www.cninfo.com.cn/new/disclosure/detail?annoId={announcement_id}"
                        if announcement_id
                        else ""
                    ),
                }
            )
        return {"checked": True, "items": items}

    def _cninfo_orgid(self, requests_module: Any, code: str, *, timeout: Any = None) -> str:
        if not self.__class__._CNINFO_ORGID_MAP:
            try:
                data = self._request_json(
                    requests_module,
                    "GET",
                    "http://www.cninfo.com.cn/new/data/szse_stock.json",
                    headers={"User-Agent": self.USER_AGENT},
                    timeout=timeout,
                )
                self.__class__._CNINFO_ORGID_MAP = {
                    str(item.get("code")): str(item.get("orgId"))
                    for item in data.get("stockList", [])
                    if isinstance(item, dict) and item.get("code") and item.get("orgId")
                }
            except Exception:
                self.__class__._CNINFO_ORGID_MAP = {}
        org_id = self.__class__._CNINFO_ORGID_MAP.get(code)
        if org_id:
            return org_id
        if code.startswith("6"):
            return f"gssh0{code}"
        return f"gssz0{code}"

    def _cninfo_ts_to_date(self, value: Any) -> str:
        numeric = self._float_or_none(value)
        if numeric is not None and numeric > 10_000_000_000:
            return datetime.fromtimestamp(numeric / 1000).strftime("%Y-%m-%d")
        return str(value or "")[:10]

    def _eastmoney_secid(self, code: str) -> str:
        return f"1.{code}" if code.startswith("6") else f"0.{code}"

    def _request_json(
        self,
        requests_module: Any,
        method: str,
        url: str,
        *,
        params: Optional[dict[str, Any]] = None,
        data: Optional[dict[str, Any]] = None,
        headers: Optional[dict[str, str]] = None,
        timeout: Any = None,
    ) -> dict[str, Any]:
        if method.upper() == "POST":
            response = requests_module.post(url, data=data, params=params, headers=headers, timeout=timeout)
        else:
            response = requests_module.get(url, params=params, headers=headers, timeout=timeout)
        response.raise_for_status()
        parsed = response.json()
        return parsed if isinstance(parsed, dict) else {}

    def _reader_summary(
        self,
        label: str,
        *,
        channels: list[dict[str, Any]],
        quote: dict[str, Any] | None,
        profile: dict[str, Any] | None,
        source: str,
    ) -> dict[str, Any]:
        available = [item for item in channels if item.get("status") == "available"]
        explainable = [item for item in channels if self._needs_reader_explanation(item)]
        price = self._float_or_none((quote or {}).get("current_price"))
        change = self._float_or_none((quote or {}).get("change_percent"))
        price_value = "行情待刷新"
        if price is not None:
            price_value = self._format_number(price)
            if change is not None:
                price_value = f"{price_value} / {self._format_percent(change)}"
        hit_titles = [str(item.get("title") or item.get("category") or "") for item in available if item]
        hit_text = "、".join(hit_titles[:3]) if hit_titles else "暂无明确命中"
        soft_gap_titles = [str(item.get("title") or item.get("category") or "") for item in explainable if item]
        soft_gap_text = "、".join(soft_gap_titles[:3]) if soft_gap_titles else "未发现明显缺口"
        sector_context = " / ".join(
            str(value)
            for value in ((profile or {}).get("sector"), (profile or {}).get("industry"))
            if value
        )
        why_bits = [
            f"{label} 已完成公告、资金流、板块、研报和龙虎榜检查",
            f"可读通道：{hit_text}",
            f"需复核项：{soft_gap_text}",
        ]
        if sector_context:
            why_bits.append(f"背景：{sector_context}")
        return {
            "headline": f"{label} A股增强速读",
            "why_read": f"为什么值得看：{'；'.join(why_bits)}。",
            "key_facts": [
                {
                    "label": "今日关键信息",
                    "value": price_value,
                    "detail": "先看价格、涨跌幅与当前通道命中情况。",
                },
                {
                    "label": "已命中通道",
                    "value": f"{len(available)}/{len(channels)}",
                    "detail": hit_text,
                },
                {
                    "label": "数据成本",
                    "value": "未用 AI",
                    "detail": "未使用公共搜索，优先使用行情、缓存或已配置数据源。",
                },
                {
                    "label": "数据来源",
                    "value": self._reader_source_label(source),
                    "detail": "来源会随本地规则、a-stock-data 适配器或关闭状态变化。",
                },
            ],
            "miss_explanations": [
                {
                    "title": str(item.get("title") or item.get("category") or "通道"),
                    "explanation": str(item.get("summary") or "已查询，当前暂无可展示明细。"),
                    "next_step": str(item.get("action") or "刷新或使用深度模式复核。"),
                }
                for item in explainable[:4]
            ],
            "premium_features": [
                "公告原文与历史公告",
                "资金流历史与主力净额明细",
                "研报 PDF 与机构预测",
                "板块联动与同业对比",
                "龙虎榜席位明细",
            ],
            "boundary": "仅作信息分析，不构成投资建议。",
        }

    def _needs_reader_explanation(self, item: dict[str, Any]) -> bool:
        text = " ".join(str(item.get(key) or "") for key in ("summary", "action", "status"))
        if item.get("status") != "available":
            return True
        return any(
            marker in text
            for marker in (
                "暂无",
                "未命中",
                "未返回",
                "降级",
                "reserved",
                "not fetched",
                "timed out",
                "no usable",
            )
        )

    def _reader_source_label(self, source: str) -> str:
        if source == "a_stock_data_skill_adapter":
            return "a-stock-data适配"
        if source == "basic_quote_snapshot":
            return "基础行情快照"
        if source == "a_stock_data_poc_adapter":
            return "本地规则"
        return source or "本地数据源"

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
            price_text = f" 最新价 {self._format_number(price)}"
            if change is not None:
                price_text += f"，涨跌幅 {self._format_percent(change)}"
        status_text = "已接入" if status == "available" else "已降级"
        context_text = f" 背景：{context}。" if context else ""
        return f"{label} A股增强数据：公告、资金流、板块、研报和龙虎榜{status_text}。{context_text}{price_text}".strip()

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
