# -*- coding: utf-8 -*-
"""Bounded, no-key public schedule aggregation for the three-market home."""

from __future__ import annotations

import copy
import hashlib
import os
import re
import time
from concurrent.futures import Future, ThreadPoolExecutor, wait
from datetime import date, datetime, timedelta, timezone
from threading import Lock
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, Sequence
from urllib.parse import urlparse


CNINFO_REPORT_URL = "https://www.cninfo.com.cn/new/information/getPrbookInfo"
CNINFO_REPORT_PAGE = "https://www.cninfo.com.cn/new/commonUrl?url=data/yypl"
FOMC_CALENDAR_URL = "https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm"
YAHOO_QUOTE_URL = "https://finance.yahoo.com/quote/{symbol}/"

CALENDAR_PAST_DAYS = 7
CALENDAR_FUTURE_DAYS = 30
DEFAULT_MAX_EVENTS = 36
DEFAULT_CACHE_TTL_SECONDS = 900
DEFAULT_STALE_TTL_SECONDS = 21600
DEFAULT_TIMEOUT_SECONDS = 4.0
DEFAULT_MAX_CACHE_ENTRIES = 64
MAX_SYMBOLS_PER_MARKET = 6
MAX_SOURCE_CACHE_EVENTS = 72

_CALENDAR_EXECUTOR = ThreadPoolExecutor(max_workers=8, thread_name_prefix="public-market-calendar")
_MONTHS = {
    "january": 1,
    "february": 2,
    "march": 3,
    "april": 4,
    "may": 5,
    "june": 6,
    "july": 7,
    "august": 8,
    "september": 9,
    "october": 10,
    "november": 11,
    "december": 12,
}
_SECURITY_KEYS = ("attention", "most_active", "gainers", "losers")


class PublicMarketCalendarService:
    """Load explicit schedule dates without AI, credentials, or persistence."""

    def __init__(
        self,
        *,
        cninfo_loader: Optional[Callable[[str], Sequence[Mapping[str, Any]]]] = None,
        yahoo_loader: Optional[Callable[[str], Mapping[str, Any]]] = None,
        historical_earnings_loader: Optional[
            Callable[[str], Sequence[Any]]
        ] = None,
        fomc_loader: Optional[Callable[[int], Sequence[Mapping[str, date]]]] = None,
        timeout_seconds: Optional[float] = None,
        cache_ttl_seconds: Optional[int] = None,
        stale_ttl_seconds: Optional[int] = None,
        max_cache_entries: Optional[int] = None,
        max_events: int = DEFAULT_MAX_EVENTS,
        clock: Callable[[], float] = time.monotonic,
        executor: Optional[ThreadPoolExecutor] = None,
    ) -> None:
        raw_timeout = timeout_seconds if timeout_seconds is not None else os.getenv(
            "PLATFORM_PUBLIC_MARKET_CALENDAR_TIMEOUT_SECONDS",
            str(DEFAULT_TIMEOUT_SECONDS),
        )
        self.timeout_seconds = max(0.01, min(float(raw_timeout), 8.0))
        self.cache_ttl_seconds = max(
            1,
            int(cache_ttl_seconds or os.getenv(
                "PLATFORM_PUBLIC_MARKET_CALENDAR_CACHE_TTL_SECONDS",
                str(DEFAULT_CACHE_TTL_SECONDS),
            )),
        )
        self.stale_ttl_seconds = max(
            self.cache_ttl_seconds,
            int(stale_ttl_seconds or os.getenv(
                "PLATFORM_PUBLIC_MARKET_CALENDAR_STALE_TTL_SECONDS",
                str(DEFAULT_STALE_TTL_SECONDS),
            )),
        )
        self.max_cache_entries = max(
            1,
            min(
                int(
                    max_cache_entries
                    if max_cache_entries is not None
                    else os.getenv(
                        "PLATFORM_PUBLIC_MARKET_CALENDAR_CACHE_MAX_ENTRIES",
                        str(DEFAULT_MAX_CACHE_ENTRIES),
                    )
                ),
                256,
            ),
        )
        self.max_events = max(1, min(int(max_events), DEFAULT_MAX_EVENTS))
        self.clock = clock
        self.executor = executor or _CALENDAR_EXECUTOR
        self.cninfo_loader = cninfo_loader or self._fetch_cninfo_period
        self.yahoo_loader = yahoo_loader or self._fetch_yahoo_calendar
        self.historical_earnings_loader = (
            historical_earnings_loader
            if historical_earnings_loader is not None
            else self._fetch_yahoo_earnings_history
            if yahoo_loader is None
            else None
        )
        self.fomc_loader = fomc_loader or self._fetch_fomc_meetings
        self._cache: Dict[str, tuple[float, List[Dict[str, Any]]]] = {}
        self._inflight: Dict[str, Future[List[Dict[str, Any]]]] = {}
        self._lock = Lock()

    def load(
        self,
        sections: Sequence[Dict[str, Any]],
        as_of: str,
        *,
        past_days: int = CALENDAR_PAST_DAYS,
        future_days: int = CALENDAR_FUTURE_DAYS,
        max_events: Optional[int] = None,
        newest_first: bool = False,
        include_historical: bool = False,
        fail_on_source_unavailable: bool = False,
    ) -> List[Dict[str, Any]]:
        as_of_datetime = self._parse_datetime(as_of)
        visible = self._visible_securities(sections)
        markets = {
            str(section.get("market") or "").strip().lower()
            for section in sections
            if isinstance(section, dict)
        }
        periods = self._cninfo_periods(
            as_of_datetime.date(),
            include_historical=include_historical,
        )
        yahoo_securities = [
            item
            for market in ("hk", "us")
            for item in visible.get(market, [])
        ]
        jobs: Dict[str, Callable[[], List[Dict[str, Any]]]] = {}
        if "cn" in markets:
            suffix = ":history" if include_historical else ""
            for period in periods:
                jobs[f"cninfo:{period}{suffix}"] = (
                    lambda period=period: self._build_cninfo_events(
                        period,
                        as_of,
                        include_historical=include_historical,
                    )
                )
        if yahoo_securities:
            suffix = ":history" if include_historical else ""
            for security in yahoo_securities:
                symbol = security["symbol"]
                market = security["market"]
                jobs[f"yahoo:{market}:{symbol}{suffix}"] = (
                    lambda security=security: self._build_yahoo_events(
                        [security],
                        as_of,
                        include_historical=include_historical,
                    )
                )
        if "us" in markets:
            start_date = as_of_datetime.date() - timedelta(
                days=past_days if include_historical else 0
            )
            end_date = as_of_datetime.date() + timedelta(days=future_days)
            for year in range(start_date.year, end_date.year + 1):
                jobs[f"fomc:{year}"] = (
                    lambda year=year: self._build_fomc_events(year, as_of)
                )

        now = self.clock()
        events: List[Dict[str, Any]] = []
        available_sources = 0
        unavailable_sources = 0
        pending_jobs: Dict[str, Callable[[], List[Dict[str, Any]]]] = {}
        for key, job in jobs.items():
            cached = self._read_cache(key, now, allow_stale=False)
            if cached is None:
                pending_jobs[key] = job
            else:
                available_sources += 1
                events.extend(self._with_status(cached, "cached", "calendar_source_cached"))

        futures: Dict[str, Future[List[Dict[str, Any]]]] = {}
        for key, job in pending_jobs.items():
            with self._lock:
                future = self._inflight.get(key)
                if future is None:
                    future = self.executor.submit(job)
                    self._inflight[key] = future
            futures[key] = future
        if futures:
            completed, pending = wait(list(futures.values()), timeout=self.timeout_seconds)
            for key, future in futures.items():
                if future in completed:
                    with self._lock:
                        if self._inflight.get(key) is future:
                            self._inflight.pop(key, None)
                    try:
                        loaded = list(future.result() or [])
                    except Exception:
                        loaded = None
                    if loaded is not None:
                        loaded = self._bounded_events(
                            loaded,
                            visible,
                            as_of_datetime,
                            past_days=60,
                            future_days=60,
                            max_events=MAX_SOURCE_CACHE_EVENTS,
                            newest_first=include_historical,
                        )
                        self._write_cache(key, now, loaded)
                        available_sources += 1
                        events.extend(self._with_status(loaded, "fresh", None))
                        continue
                stale = self._read_cache(key, now, allow_stale=True)
                if stale is not None:
                    available_sources += 1
                    events.extend(self._with_status(stale, "stale", "calendar_source_stale"))
                else:
                    unavailable_sources += 1

        if (
            fail_on_source_unavailable
            and jobs
            and unavailable_sources > 0
            and not events
        ):
            raise RuntimeError("calendar_sources_unavailable")

        return self._bounded_events(
            events,
            visible,
            as_of_datetime,
            past_days=past_days,
            future_days=future_days,
            max_events=max_events,
            newest_first=newest_first,
        )

    def _build_cninfo_events(
        self,
        period: str,
        as_of: str,
        *,
        include_historical: bool = False,
    ) -> List[Dict[str, Any]]:
        events: List[Dict[str, Any]] = []
        for row in self.cninfo_loader(period):
            if not isinstance(row, Mapping):
                continue
            disclosed = self._coerce_date(row.get("实际披露"))
            if disclosed is not None and not include_historical:
                continue
            appointments = [
                self._coerce_date(row.get(field))
                for field in ("首次预约", "初次变更", "二次变更", "三次变更")
            ]
            scheduled = (
                disclosed
                if disclosed is not None
                else next((value for value in reversed(appointments) if value is not None), None)
            )
            code = str(row.get("股票代码") or "").strip()
            symbol = self._cn_symbol(code)
            if scheduled is None or symbol is None:
                continue
            name = str(row.get("股票简称") or "").strip() or symbol
            events.append(self._event(
                market="cn",
                category="earnings",
                schedule_type="earnings_release",
                scheduled=scheduled,
                title=(
                    f"{name}（{symbol}）{period}已披露"
                    if disclosed is not None
                    else f"{name}（{symbol}）{period}预约披露"
                ),
                summary=(
                    f"巨潮资讯定期报告实际披露日期，报告期：{period}。"
                    if disclosed is not None
                    else f"巨潮资讯定期报告预约，报告期：{period}。"
                ),
                symbol=symbol,
                name=name,
                publisher="巨潮资讯",
                source="cninfo_report_schedule",
                url=CNINFO_REPORT_PAGE,
                as_of=as_of,
            ))
        return events

    def _build_yahoo_events(
        self,
        securities: Sequence[Dict[str, str]],
        as_of: str,
        *,
        include_historical: bool = False,
    ) -> List[Dict[str, Any]]:
        events: List[Dict[str, Any]] = []
        attempted = 0
        failed = 0
        for security in securities:
            symbol = security["symbol"]
            attempted += 1
            if include_historical and self.historical_earnings_loader is not None:
                try:
                    calendar = {
                        "Earnings History": list(
                            self.historical_earnings_loader(symbol) or []
                        )
                    }
                except Exception:
                    failed += 1
                    continue
            else:
                try:
                    calendar = dict(self.yahoo_loader(symbol) or {})
                except Exception:
                    failed += 1
                    continue
            earnings_dates = calendar.get("Earnings Date") or []
            if not isinstance(earnings_dates, (list, tuple, set)):
                earnings_dates = [earnings_dates]
            if include_historical:
                historical_dates = calendar.get("Earnings History") or []
                if not isinstance(historical_dates, (list, tuple, set)):
                    historical_dates = [historical_dates]
                earnings_dates = [*earnings_dates, *historical_dates]
            seen_earnings_dates: set[date] = set()
            for scheduled in earnings_dates:
                parsed = self._coerce_date(scheduled)
                if parsed is None or parsed in seen_earnings_dates:
                    continue
                seen_earnings_dates.add(parsed)
                events.append(self._event(
                    market=security["market"],
                    category="earnings",
                    schedule_type="earnings_release",
                    scheduled=parsed,
                    title=f"{security['name']} ({symbol}) earnings release",
                    summary="Public calendar date supplied by Yahoo Finance through yfinance.",
                    symbol=symbol,
                    name=security["name"],
                    publisher="Yahoo Finance",
                    source="yfinance_public_calendar",
                    url=YAHOO_QUOTE_URL.format(symbol=symbol),
                    as_of=as_of,
                ))
            ex_dividend = self._coerce_date(calendar.get("Ex-Dividend Date"))
            if ex_dividend is not None:
                events.append(self._event(
                    market=security["market"],
                    category="dividend",
                    schedule_type="ex_dividend",
                    scheduled=ex_dividend,
                    title=f"{security['name']} ({symbol}) ex-dividend date",
                    summary="Public ex-dividend date supplied by Yahoo Finance through yfinance.",
                    symbol=symbol,
                    name=security["name"],
                    publisher="Yahoo Finance",
                    source="yfinance_public_calendar",
                    url=YAHOO_QUOTE_URL.format(symbol=symbol),
                    as_of=as_of,
                ))
        if attempted > 0 and failed == attempted:
            raise RuntimeError("yahoo_calendar_unavailable")
        return events

    def _build_fomc_events(self, year: int, as_of: str) -> List[Dict[str, Any]]:
        events: List[Dict[str, Any]] = []
        for meeting in self.fomc_loader(year):
            start = self._coerce_date(meeting.get("start"))
            end = self._coerce_date(meeting.get("end")) or start
            if start is None or end is None:
                continue
            events.append(self._event(
                market="us",
                category="macro",
                schedule_type="macro_policy",
                scheduled=end,
                title=f"Federal Reserve FOMC meeting ({start.isoformat()} to {end.isoformat()})",
                summary="Scheduled meeting date published by the Board of Governors of the Federal Reserve System.",
                symbol=None,
                name=None,
                publisher="Federal Reserve",
                source="federal_reserve_fomc_calendar",
                url=FOMC_CALENDAR_URL,
                as_of=as_of,
            ))
        return events

    def _bounded_events(
        self,
        events: Iterable[Dict[str, Any]],
        visible: Dict[str, List[Dict[str, str]]],
        as_of: datetime,
        *,
        past_days: int = CALENDAR_PAST_DAYS,
        future_days: int = CALENDAR_FUTURE_DAYS,
        max_events: Optional[int] = None,
        newest_first: bool = False,
    ) -> List[Dict[str, Any]]:
        bounded_past_days = max(0, min(int(past_days), 60))
        bounded_future_days = max(0, min(int(future_days), 60))
        result_limit = max(
            1,
            min(int(max_events if max_events is not None else self.max_events), 72),
        )
        earliest = as_of.date().toordinal() - bounded_past_days
        latest = as_of.date().toordinal() + bounded_future_days
        visible_symbols = {
            item["symbol"].upper()
            for items in visible.values()
            for item in items
        }
        unique: Dict[str, Dict[str, Any]] = {}
        for event in events:
            scheduled = self._coerce_date(event.get("event_time"))
            if scheduled is None or not earliest <= scheduled.toordinal() <= latest:
                continue
            event_id = str(event.get("event_id") or "")
            if event_id and event_id not in unique:
                unique[event_id] = event
        if newest_first:
            ordered = sorted(
                unique.values(),
                key=lambda event: (
                    -(
                        self._coerce_date(event.get("event_time")).toordinal()
                        if self._coerce_date(event.get("event_time")) is not None
                        else 0
                    ),
                    0 if str(event.get("symbol") or "").upper() in visible_symbols else 1,
                    str(event.get("market") or ""),
                    str(event.get("symbol") or ""),
                ),
            )
        else:
            ordered = sorted(
                unique.values(),
                key=lambda event: (
                    0 if str(event.get("symbol") or "").upper() in visible_symbols else 1,
                    str(event.get("event_time") or ""),
                    str(event.get("market") or ""),
                    str(event.get("symbol") or ""),
                ),
            )
        return copy.deepcopy(ordered[:result_limit])

    def _read_cache(
        self,
        key: str,
        now: float,
        *,
        allow_stale: bool,
    ) -> Optional[List[Dict[str, Any]]]:
        with self._lock:
            entry = self._cache.get(key)
            if entry is not None and max(0.0, now - entry[0]) >= self.stale_ttl_seconds:
                self._cache.pop(key, None)
                entry = None
        if entry is None:
            return None
        age = max(0.0, now - entry[0])
        limit = self.stale_ttl_seconds if allow_stale else self.cache_ttl_seconds
        if age >= limit:
            return None
        return copy.deepcopy(entry[1])

    def _write_cache(self, key: str, now: float, events: List[Dict[str, Any]]) -> None:
        with self._lock:
            expired = [
                cached_key
                for cached_key, entry in self._cache.items()
                if max(0.0, now - entry[0]) >= self.stale_ttl_seconds
            ]
            for cached_key in expired:
                self._cache.pop(cached_key, None)
            self._cache.pop(key, None)
            while len(self._cache) >= self.max_cache_entries:
                oldest_key = min(
                    self._cache,
                    key=lambda cached_key: self._cache[cached_key][0],
                )
                self._cache.pop(oldest_key, None)
            self._cache[key] = (now, copy.deepcopy(events))

    @staticmethod
    def _with_status(
        events: Sequence[Dict[str, Any]],
        status: str,
        warning: Optional[str],
    ) -> List[Dict[str, Any]]:
        result = copy.deepcopy(list(events))
        for event in result:
            state = event.get("source_state")
            if isinstance(state, dict):
                state["status"] = status
                state["warning_code"] = warning
        return result

    @staticmethod
    def _visible_securities(
        sections: Sequence[Dict[str, Any]],
    ) -> Dict[str, List[Dict[str, str]]]:
        result = {"cn": [], "hk": [], "us": []}
        seen = {market: set() for market in result}
        for section in sections:
            if not isinstance(section, dict):
                continue
            market = str(section.get("market") or "").strip().lower()
            if market not in result:
                continue
            for key in _SECURITY_KEYS:
                for item in section.get(key) or []:
                    if not isinstance(item, dict):
                        continue
                    symbol = str(item.get("symbol") or "").strip().upper()
                    if not symbol or symbol in seen[market]:
                        continue
                    seen[market].add(symbol)
                    result[market].append({
                        "symbol": symbol,
                        "name": str(item.get("name") or "").strip() or symbol,
                        "market": market,
                    })
                    if len(result[market]) >= MAX_SYMBOLS_PER_MARKET:
                        break
                if len(result[market]) >= MAX_SYMBOLS_PER_MARKET:
                    break
        return result

    @staticmethod
    def _event(
        *,
        market: str,
        category: str,
        schedule_type: str,
        scheduled: date,
        title: str,
        summary: str,
        symbol: Optional[str],
        name: Optional[str],
        publisher: str,
        source: str,
        url: str,
        as_of: str,
    ) -> Dict[str, Any]:
        event_time = f"{scheduled.isoformat()}T00:00:00Z"
        raw = f"{source}\n{market}\n{symbol or ''}\n{schedule_type}\n{event_time}".encode("utf-8")
        safe_url = PublicMarketCalendarService._safe_http_url(url)
        source_record = {
            "publisher": publisher,
            "source": source,
            "url": safe_url,
            "event_time": event_time,
            "time_kind": "scheduled",
        }
        return {
            "event_id": hashlib.sha256(raw).hexdigest()[:20],
            "market": market,
            "category": category,
            "title": title,
            "summary": summary,
            "symbol": symbol,
            "name": name,
            "sector": None,
            "event_time": event_time,
            "time_kind": "scheduled",
            "publisher": publisher,
            "url": safe_url,
            "source_state": {
                "source": source,
                "status": "fresh",
                "observed_at": as_of,
                "fetched_at": as_of,
                "delay_seconds": 0,
                "warning_code": None,
            },
            "classification_source": "provider_schedule",
            "schedule_type": schedule_type,
            "relevance_score": 85 if symbol else 70,
            "importance": "high" if symbol else "medium",
            "relevance_reasons": [
                "scheduled_event",
                *(["linked_security"] if symbol else ["macro_event"]),
                "source_link",
            ],
            "source_count": 1,
            "source_publishers": [publisher],
            "source_records": [source_record],
        }

    @staticmethod
    def _parse_datetime(value: str) -> datetime:
        try:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except (TypeError, ValueError):
            return datetime.now(timezone.utc)
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)

    @staticmethod
    def _coerce_date(value: Any) -> Optional[date]:
        if value is None:
            return None
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, date):
            return value
        text = str(value).strip()
        if not text or text.casefold() in {"nat", "nan", "none"}:
            return None
        try:
            return date.fromisoformat(text[:10])
        except ValueError:
            return None

    @staticmethod
    def _cn_symbol(value: Any) -> Optional[str]:
        code = re.sub(r"\D", "", str(value or ""))
        if len(code) != 6:
            return None
        if code.startswith(("4", "8", "92")):
            return f"{code}.BJ"
        if code.startswith("6"):
            return f"{code}.SH"
        return f"{code}.SZ"

    @staticmethod
    def _cninfo_period(today: date) -> str:
        if today.month <= 4:
            return f"{today.year - 1}年报"
        if today.month <= 8:
            return f"{today.year}半年报"
        if today.month <= 10:
            return f"{today.year}三季"
        return f"{today.year}年报"

    @classmethod
    def _cninfo_periods(
        cls,
        today: date,
        *,
        include_historical: bool,
    ) -> List[str]:
        current = cls._cninfo_period(today)
        if not include_historical:
            return [current]
        if today.month <= 4:
            return [current]
        if today.month <= 8:
            return [current, f"{today.year - 1}年报"]
        if today.month <= 10:
            return [current, f"{today.year}半年报"]
        return [current, f"{today.year}三季"]

    @staticmethod
    def _safe_http_url(value: Any) -> Optional[str]:
        text = str(value or "").strip()
        try:
            parsed = urlparse(text)
        except ValueError:
            return None
        return text if parsed.scheme.casefold() in {"http", "https"} and parsed.netloc else None

    @staticmethod
    def _fetch_cninfo_period(period: str) -> Sequence[Mapping[str, Any]]:
        import requests

        year = period[:4]
        section_time = {
            f"{year}一季": f"{year}-03-31",
            f"{year}半年报": f"{year}-06-30",
            f"{year}三季": f"{year}-09-30",
            f"{year}年报": f"{year}-12-31",
        }[period]
        response = requests.post(
            CNINFO_REPORT_URL,
            params={
                "sectionTime": section_time,
                "firstTime": "",
                "lastTime": "",
                "market": "szsh",
                "stockCode": "",
                "orderClos": "",
                "isDesc": "",
                "pagesize": "10000",
                "pagenum": "1",
            },
            headers={
                "User-Agent": "Mozilla/5.0 DSA-local-market-calendar/1.0",
                "Referer": "https://www.cninfo.com.cn/",
            },
            timeout=8,
        )
        response.raise_for_status()
        result: List[Dict[str, Any]] = []
        for row in response.json().get("prbookinfos") or []:
            if not isinstance(row, dict):
                continue
            result.append({
                "股票代码": row.get("seccode"),
                "股票简称": row.get("secname"),
                "首次预约": row.get("f002d_0102"),
                "实际披露": row.get("f006d_0102"),
                "初次变更": row.get("f003d_0102"),
                "二次变更": row.get("f004d_0102"),
                "三次变更": row.get("f005d_0102"),
            })
        return result

    @staticmethod
    def _fetch_yahoo_calendar(symbol: str) -> Mapping[str, Any]:
        import yfinance as yf

        return dict(yf.Ticker(symbol).calendar or {})

    @staticmethod
    def _fetch_yahoo_earnings_history(symbol: str) -> Sequence[Any]:
        import yfinance as yf

        frame = yf.Ticker(symbol).get_earnings_dates(limit=12)
        if frame is None:
            return []
        return list(frame.index)

    @classmethod
    def _fetch_fomc_meetings(cls, year: int) -> Sequence[Mapping[str, date]]:
        import requests

        response = requests.get(
            FOMC_CALENDAR_URL,
            headers={"User-Agent": "DSA-local-market-calendar/1.0"},
            timeout=8,
        )
        response.raise_for_status()
        return cls.parse_fomc_html(response.text, year)

    @staticmethod
    def parse_fomc_html(html: str, year: int) -> List[Dict[str, date]]:
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(html, "html.parser")
        target_heading = f"{year} FOMC Meetings".casefold()
        heading = next(
            (
                node
                for node in soup.find_all("h4")
                if target_heading in node.get_text(" ", strip=True).casefold()
            ),
            None,
        )
        if heading is None:
            anchor = soup.find(id=str(year))
            heading = anchor.find_parent("h4") if anchor is not None else None
        if heading is None:
            return []
        meetings: List[Dict[str, date]] = []
        for element in heading.find_all_next():
            if element.name == "h4" and element is not heading:
                break
            classes = set(element.get("class") or [])
            if element.name != "div" or "fomc-meeting" not in classes:
                continue
            month_node = element.select_one(".fomc-meeting__month")
            date_node = element.select_one(".fomc-meeting__date")
            if month_node is None or date_node is None:
                continue
            month = _MONTHS.get(month_node.get_text(" ", strip=True).casefold())
            numbers = [int(value) for value in re.findall(r"\d{1,2}", date_node.get_text(" ", strip=True))]
            if month is None or not numbers:
                continue
            try:
                start = date(year, month, numbers[0])
                end = date(year, month, numbers[-1])
            except ValueError:
                continue
            meetings.append({"start": start, "end": end})
        return meetings
