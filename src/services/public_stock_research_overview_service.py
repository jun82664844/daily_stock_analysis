"""Public no-AI financial trend data for the V142 stock research overview."""

from __future__ import annotations

import copy
import math
import re
import statistics
import threading
from datetime import datetime
from typing import Any, Callable, Dict, Iterable, Optional

from src.services.stock_code_utils import normalize_crypto_symbol


TickerFactory = Callable[[str], Any]


def to_public_research_symbol(stock_code: str) -> Optional[str]:
    """Map a supported DSA stock code to a Yahoo Finance public symbol."""

    code = (stock_code or "").strip().upper()
    if not code or normalize_crypto_symbol(code) is not None:
        return None

    match = re.fullmatch(r"(?:SH)?(\d{6})(?:\.(?:SH|SS))?", code)
    if match and (code.startswith("SH") or code.endswith((".SH", ".SS"))):
        return f"{match.group(1)}.SS"

    match = re.fullmatch(r"(?:SZ)?(\d{6})(?:\.SZ)?", code)
    if match and (code.startswith("SZ") or code.endswith(".SZ")):
        return f"{match.group(1)}.SZ"

    match = re.fullmatch(r"(?:BJ)?(\d{6})(?:\.BJ)?", code)
    if match and (code.startswith("BJ") or code.endswith(".BJ")):
        return f"{match.group(1)}.BJ"

    if re.fullmatch(r"\d{6}", code):
        if code.startswith(("5", "6", "9")):
            return f"{code}.SS"
        return f"{code}.SZ"

    match = re.fullmatch(r"HK(\d{1,5})", code)
    if match:
        return f"{int(match.group(1)):04d}.HK"

    match = re.fullmatch(r"(\d{1,5})\.HK", code)
    if match:
        return f"{int(match.group(1)):04d}.HK"

    if re.fullmatch(r"\d{5}", code):
        return f"{int(code):04d}.HK"

    if code.endswith(".US"):
        code = code[:-3]
    if re.fullmatch(r"[A-Z]{1,5}(?:\.[A-Z])?", code):
        return code
    return None


def _safe_float(value: Any) -> Optional[float]:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    return numeric if math.isfinite(numeric) else None


def _row_values(frame: Any, names: Iterable[str]) -> Dict[Any, Optional[float]]:
    if frame is None or getattr(frame, "empty", True):
        return {}
    index = getattr(frame, "index", [])
    for name in names:
        if name in index:
            series = frame.loc[name]
            return {column: _safe_float(value) for column, value in series.items()}
    return {}


def _as_naive_datetime(value: Any) -> Optional[datetime]:
    try:
        converted = value.to_pydatetime() if hasattr(value, "to_pydatetime") else value
        if not isinstance(converted, datetime):
            converted = datetime.fromisoformat(str(converted))
        return converted.replace(tzinfo=None)
    except (TypeError, ValueError):
        return None


def _growth(current: Optional[float], previous: Optional[float]) -> Optional[float]:
    if current is None or previous in (None, 0):
        return None
    return round(((current - previous) / abs(previous)) * 100.0, 4)


class PublicStockResearchOverviewService:
    """Load observed public financial trends lazily and cache them locally."""

    def __init__(
        self,
        ticker_factory: Optional[TickerFactory] = None,
        *,
        cache_ttl_seconds: int = 21600,
        clock: Callable[[], datetime] = datetime.utcnow,
    ) -> None:
        self._ticker_factory = ticker_factory or self._default_ticker_factory
        self._cache_ttl_seconds = max(60, int(cache_ttl_seconds))
        self._clock = clock
        self._cache: Dict[str, tuple[datetime, Dict[str, Any]]] = {}
        self._lock = threading.Lock()

    @staticmethod
    def _default_ticker_factory(symbol: str) -> Any:
        import yfinance as yf

        return yf.Ticker(symbol)

    def get_overview(self, stock_code: str) -> Dict[str, Any]:
        code = (stock_code or "").strip().upper()
        public_symbol = to_public_research_symbol(code)
        now = self._clock()
        if public_symbol is None:
            return self._unavailable_payload(
                code,
                public_symbol=None,
                now=now,
                status="not_applicable",
                warning="该标的不适用股票财务报表；请查看价格、流动性和公开事件数据。",
            )

        with self._lock:
            cached = self._cache.get(public_symbol)
            if cached and (now - cached[0]).total_seconds() < self._cache_ttl_seconds:
                payload = copy.deepcopy(cached[1])
                payload["cache_status"] = "hit"
                return payload

        try:
            ticker = self._ticker_factory(public_symbol)
            financials = getattr(ticker, "financials", None)
            cashflow = getattr(ticker, "cashflow", None)
            history = ticker.history(period="5y", interval="1mo", auto_adjust=False)
            payload = self._build_payload(
                code=code,
                public_symbol=public_symbol,
                now=now,
                financials=financials,
                cashflow=cashflow,
                history=history,
            )
        except Exception:
            payload = self._unavailable_payload(
                code,
                public_symbol=public_symbol,
                now=now,
                status="unavailable",
                warning="公开财务数据暂时不可用，请稍后刷新；当前页面不会据此生成估值结论。",
            )

        with self._lock:
            self._cache[public_symbol] = (now, copy.deepcopy(payload))
        return payload

    def _build_payload(
        self,
        *,
        code: str,
        public_symbol: str,
        now: datetime,
        financials: Any,
        cashflow: Any,
        history: Any,
    ) -> Dict[str, Any]:
        revenue = _row_values(financials, ("Total Revenue", "Operating Revenue"))
        net_income = _row_values(
            financials,
            ("Net Income", "Net Income Common Stockholders"),
        )
        diluted_eps = _row_values(financials, ("Diluted EPS", "Basic EPS"))
        operating_cash_flow = _row_values(
            cashflow,
            ("Operating Cash Flow", "Total Cash From Operating Activities"),
        )
        if not operating_cash_flow:
            operating_cash_flow = _row_values(
                financials,
                ("Operating Cash Flow", "Total Cash From Operating Activities"),
            )

        financial_series = (revenue, net_income, diluted_eps, operating_cash_flow)
        period_columns = {
            column
            for values in financial_series
            for column in values
            if _as_naive_datetime(column) is not None
            and any(series.get(column) is not None for series in financial_series)
        }
        ordered_periods = sorted(
            period_columns,
            key=lambda value: _as_naive_datetime(value) or datetime.min,
        )[-5:]

        closes = self._history_closes(history)
        rows: list[Dict[str, Any]] = []
        previous_revenue: Optional[float] = None
        previous_net_income: Optional[float] = None
        for period in ordered_periods:
            period_end = _as_naive_datetime(period)
            if period_end is None:
                continue
            revenue_value = revenue.get(period)
            net_income_value = net_income.get(period)
            eps_value = diluted_eps.get(period)
            year_end_price = self._price_at_or_before(closes, period_end)
            observed_pe = None
            if year_end_price is not None and eps_value is not None and eps_value > 0:
                observed_pe = round(year_end_price / eps_value, 4)
            rows.append(
                {
                    "fiscal_year": period_end.year,
                    "period_end": period_end.date().isoformat(),
                    "revenue": revenue_value,
                    "revenue_growth": _growth(revenue_value, previous_revenue),
                    "net_income": net_income_value,
                    "net_income_growth": _growth(net_income_value, previous_net_income),
                    "diluted_eps": eps_value,
                    "operating_cash_flow": operating_cash_flow.get(period),
                    "fiscal_year_end_price": year_end_price,
                    "observed_pe": observed_pe,
                }
            )
            previous_revenue = revenue_value
            previous_net_income = net_income_value

        observed_values = [
            value
            for value in (_safe_float(row.get("observed_pe")) for row in rows)
            if value is not None and value > 0
        ]
        valuation_position = self._valuation_position(observed_values)
        populated = sum(
            1
            for row in rows
            if any(row.get(key) is not None for key in ("revenue", "net_income", "diluted_eps"))
        )
        status = "available" if populated >= 3 else "partial" if populated else "unavailable"
        warnings: list[str] = []
        if len(rows) < 5:
            warnings.append(f"公开源仅返回 {len(rows)} 个财年，五年趋势并不完整。")
        if valuation_position is None:
            warnings.append("每股收益或年末价格样本不足，历史市盈率位置暂不可用。")

        return {
            "stock_code": code,
            "public_symbol": public_symbol,
            "status": status,
            "source": "yfinance_public_financials",
            "source_url": f"https://finance.yahoo.com/quote/{public_symbol}/financials/",
            "updated_at": now.isoformat(),
            "cache_status": "miss",
            "financial_years": rows,
            "valuation_position": valuation_position,
            "warnings": warnings,
            "ai_used": False,
            "public_search_used": False,
            "boundary_zh": (
                "仅提供资讯和数据，不构成投资建议或交易指令。历史市盈率样本按财年末价格除以当年摊薄每股收益计算，"
                "不等同于实时、预测或目标估值。"
            ),
            "boundary_en": (
                "Information and data only; not investment advice or a trading instruction. "
                "Observed P/E uses fiscal-year-end price divided by annual diluted EPS; "
                "it is not a realtime, forecast, or target valuation."
            ),
        }

    @staticmethod
    def _history_closes(history: Any) -> list[tuple[datetime, float]]:
        if history is None or getattr(history, "empty", True) or "Close" not in history:
            return []
        points: list[tuple[datetime, float]] = []
        for index, value in history["Close"].items():
            timestamp = _as_naive_datetime(index)
            numeric = _safe_float(value)
            if timestamp is not None and numeric is not None:
                points.append((timestamp, numeric))
        return sorted(points, key=lambda item: item[0])

    @staticmethod
    def _price_at_or_before(
        closes: list[tuple[datetime, float]],
        period_end: datetime,
    ) -> Optional[float]:
        candidates = [item for item in closes if item[0] <= period_end]
        if not candidates:
            return closes[0][1] if closes else None
        return round(candidates[-1][1], 4)

    @staticmethod
    def _valuation_position(values: list[float]) -> Optional[Dict[str, Any]]:
        if not values:
            return None
        current = values[-1]
        percentile = round((sum(value <= current for value in values) / len(values)) * 100.0, 2)
        position = "lower_range" if percentile <= 33 else "upper_range" if percentile >= 67 else "middle_range"
        return {
            "metric": "observed_pe",
            "method": "fiscal_year_end_price_divided_by_diluted_eps",
            "current_value": round(current, 4),
            "minimum": round(min(values), 4),
            "median": round(statistics.median(values), 4),
            "maximum": round(max(values), 4),
            "percentile": percentile,
            "observation_count": len(values),
            "position": position,
        }

    @staticmethod
    def _unavailable_payload(
        code: str,
        *,
        public_symbol: Optional[str],
        now: datetime,
        status: str,
        warning: str,
    ) -> Dict[str, Any]:
        return {
            "stock_code": code,
            "public_symbol": public_symbol,
            "status": status,
            "source": "yfinance_public_financials",
            "source_url": (
                f"https://finance.yahoo.com/quote/{public_symbol}/financials/"
                if public_symbol
                else None
            ),
            "updated_at": now.isoformat(),
            "cache_status": "miss",
            "financial_years": [],
            "valuation_position": None,
            "warnings": [warning],
            "ai_used": False,
            "public_search_used": False,
            "boundary_zh": "仅提供资讯和数据，不构成投资建议或交易指令。",
            "boundary_en": "Information and data only; not investment advice or a trading instruction.",
        }
