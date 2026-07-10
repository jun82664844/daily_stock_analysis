# -*- coding: utf-8 -*-
"""
===================================
股票数据服务层
===================================

职责：
1. 封装股票数据获取逻辑
2. 提供实时行情和历史数据接口
"""

import logging
import json
import os
import re
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any, List

from src.repositories.stock_repo import StockRepository
from src.services.stock_code_utils import normalize_crypto_symbol

logger = logging.getLogger(__name__)


def _positive_env_float(name: str, default: float) -> float:
    try:
        return max(0.1, float(os.environ.get(name, str(default))))
    except (TypeError, ValueError):
        return default


_HISTORY_FETCH_TIMEOUT_SECONDS = _positive_env_float("HISTORY_FETCH_TIMEOUT_SEC", 12.0)


class StockService:
    """
    股票数据服务
    
    封装股票数据获取的业务逻辑
    """
    
    def __init__(self):
        """初始化股票数据服务"""
        self.repo = StockRepository()
    
    def get_realtime_quote(self, stock_code: str) -> Optional[Dict[str, Any]]:
        """
        获取股票实时行情
        
        Args:
            stock_code: 股票代码
            
        Returns:
            实时行情数据字典
        """
        try:
            crypto_symbol = normalize_crypto_symbol(stock_code)
            if crypto_symbol is not None:
                return self._get_crypto_realtime_quote(crypto_symbol)

            # 调用数据获取器获取实时行情
            from data_provider.base import DataFetcherManager
            
            manager = DataFetcherManager()
            quote = manager.get_realtime_quote(stock_code)
            
            if quote is None:
                logger.warning(f"获取 {stock_code} 实时行情失败")
                return None
            
            # UnifiedRealtimeQuote 是 dataclass，使用 getattr 安全访问字段
            # 字段映射: UnifiedRealtimeQuote -> API 响应
            # - code -> stock_code
            # - name -> stock_name
            # - price -> current_price
            # - change_amount -> change
            # - change_pct -> change_percent
            # - open_price -> open
            # - high -> high
            # - low -> low
            # - pre_close -> prev_close
            # - volume -> volume
            # - amount -> amount
            return {
                "stock_code": getattr(quote, "code", stock_code),
                "stock_name": getattr(quote, "name", None),
                "current_price": getattr(quote, "price", 0.0) or 0.0,
                "change": getattr(quote, "change_amount", None),
                "change_percent": getattr(quote, "change_pct", None),
                "open": getattr(quote, "open_price", None),
                "high": getattr(quote, "high", None),
                "low": getattr(quote, "low", None),
                "prev_close": getattr(quote, "pre_close", None),
                "volume": getattr(quote, "volume", None),
                "amount": getattr(quote, "amount", None),
                "pe_ratio": getattr(quote, "pe_ratio", None),
                "pb_ratio": getattr(quote, "pb_ratio", None),
                "total_mv": getattr(quote, "total_mv", None),
                "market_cap": getattr(quote, "total_mv", None),
                "turnover_rate": getattr(quote, "turnover_rate", None),
                "update_time": datetime.now().isoformat(),
            }
            
        except ImportError:
            logger.warning("DataFetcherManager 未找到，使用占位数据")
            return self._get_placeholder_quote(stock_code)
        except Exception as e:
            logger.error(f"获取实时行情失败: {e}", exc_info=True)
            return None
    
    def get_history_data(
        self,
        stock_code: str,
        period: str = "daily",
        days: int = 30
    ) -> Dict[str, Any]:
        """
        获取股票历史行情
        
        Args:
            stock_code: 股票代码
            period: K 线周期 (daily/weekly/monthly)
            days: 获取天数
            
        Returns:
            历史行情数据字典
            
        Raises:
            ValueError: 当 period 不是 daily 时抛出（weekly/monthly 暂未实现）
        """
        # 验证 period 参数，只支持 daily
        if period != "daily":
            raise ValueError(
                f"暂不支持 '{period}' 周期，目前仅支持 'daily'。"
                "weekly/monthly 聚合功能将在后续版本实现。"
            )
        
        crypto_symbol = normalize_crypto_symbol(stock_code)
        if crypto_symbol is not None:
            return self._get_crypto_history_data(crypto_symbol, period=period, days=days)

        try:
            # 调用数据获取器获取历史数据
            from data_provider.base import DataFetcherManager
            
            manager = DataFetcherManager()
            df, source = manager.get_daily_data(
                stock_code,
                days=days,
                timeout_seconds=_HISTORY_FETCH_TIMEOUT_SECONDS,
            )
            
            if df is None or df.empty:
                logger.warning(f"获取 {stock_code} 历史数据失败")
                public_history = self._get_public_yahoo_history_data(stock_code, period=period, days=days)
                if public_history is not None:
                    return public_history
                return {
                    "stock_code": stock_code,
                    "period": period,
                    "source": source or "history_empty",
                    "data": [],
                }
            
            # 获取股票名称
            stock_name = manager.get_stock_name(stock_code)
            
            # 转换为响应格式
            data = []
            for _, row in df.iterrows():
                date_val = row.get("date")
                if hasattr(date_val, "strftime"):
                    date_str = date_val.strftime("%Y-%m-%d")
                else:
                    date_str = str(date_val)
                
                data.append({
                    "date": date_str,
                    "open": float(row.get("open", 0)),
                    "high": float(row.get("high", 0)),
                    "low": float(row.get("low", 0)),
                    "close": float(row.get("close", 0)),
                    "volume": float(row.get("volume", 0)) if row.get("volume") else None,
                    "amount": float(row.get("amount", 0)) if row.get("amount") else None,
                    "change_percent": float(row.get("pct_chg", 0)) if row.get("pct_chg") else None,
                })
            
            return {
                "stock_code": stock_code,
                "stock_name": stock_name,
                "period": period,
                "source": source,
                "data": data,
            }
            
        except ImportError:
            logger.warning("DataFetcherManager 未找到，返回空数据")
            public_history = self._get_public_yahoo_history_data(stock_code, period=period, days=days)
            if public_history is not None:
                return public_history
            return {
                "stock_code": stock_code,
                "period": period,
                "source": "history_unavailable",
                "data": [],
            }
        except Exception as e:
            logger.error(f"获取历史数据失败: {e}", exc_info=True)
            public_history = self._get_public_yahoo_history_data(stock_code, period=period, days=days)
            if public_history is not None:
                return public_history
            return {
                "stock_code": stock_code,
                "period": period,
                "source": "history_timeout" if "timeout" in str(e).lower() else "history_unavailable",
                "data": [],
            }

    def get_basic_company_profile(self, stock_code: str) -> Optional[Dict[str, Any]]:
        """Fetch lightweight public company facts for the no-AI quick lane."""
        symbol = self._to_yfinance_profile_symbol(stock_code)
        if not symbol:
            return None

        try:
            import yfinance as yf
        except Exception as exc:
            logger.debug("yfinance unavailable for basic company profile: %s", exc)
            return None

        try:
            ticker = yf.Ticker(symbol)
            info = ticker.get_info() if hasattr(ticker, "get_info") else getattr(ticker, "info", {})
            if not isinstance(info, dict) or not info:
                return None
        except Exception as exc:
            logger.debug("basic company profile fetch failed for %s: %s", stock_code, exc)
            return None

        profile = {
            "stock_code": stock_code,
            "company_name": info.get("longName") or info.get("shortName") or info.get("displayName"),
            "sector": info.get("sector") or info.get("sectorDisp"),
            "industry": info.get("industry") or info.get("industryDisp"),
            "exchange": info.get("exchange") or info.get("fullExchangeName"),
            "currency": info.get("currency") or info.get("financialCurrency"),
            "country": info.get("country"),
            "website": info.get("website"),
            "market_cap": self._safe_float(info.get("marketCap")),
            "pe_ratio": self._safe_float(info.get("trailingPE")) or self._safe_float(info.get("forwardPE")),
            "pb_ratio": self._safe_float(info.get("priceToBook")),
            "dividend_yield": self._dividend_yield_from_info(info),
            "revenue": self._safe_float(info.get("totalRevenue")),
            "net_profit": self._net_profit_from_info(info),
            "revenue_growth": self._ratio_to_percent(info.get("revenueGrowth")),
            "earnings_growth": self._ratio_to_percent(info.get("earningsGrowth")),
            "source": "yfinance_profile",
        }
        meaningful = (
            "sector",
            "industry",
            "exchange",
            "currency",
            "country",
            "website",
            "market_cap",
            "pe_ratio",
            "pb_ratio",
            "dividend_yield",
            "revenue",
            "net_profit",
            "revenue_growth",
            "earnings_growth",
        )
        if not any(profile.get(key) not in (None, "") for key in meaningful):
            return None
        return profile

    def _to_yfinance_profile_symbol(self, stock_code: str) -> Optional[str]:
        code = (stock_code or "").strip().upper()
        if not code or normalize_crypto_symbol(code) is not None:
            return None
        if code.endswith((".SH", ".SZ", ".BJ")):
            return None
        if code.startswith("HK") and code[2:].isdigit():
            return f"{code[2:].zfill(4)}.HK"
        if code.endswith(".HK"):
            digits = code[:-3]
            return f"{digits.zfill(4)}.HK" if digits.isdigit() else code
        if code.isdigit():
            return f"{code.zfill(4)}.HK" if len(code) <= 5 else None
        return code

    def _safe_float(self, value: Any) -> Optional[float]:
        if value is None or value == "":
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    def _ratio_to_percent(self, value: Any) -> Optional[float]:
        numeric = self._safe_float(value)
        if numeric is None:
            return None
        if abs(numeric) <= 1:
            numeric *= 100.0
        return round(numeric, 4)

    def _dividend_yield_from_info(self, info: Dict[str, Any]) -> Optional[float]:
        current_yield = self._safe_float(info.get("dividendYield"))
        if current_yield is not None:
            return round(current_yield, 4)
        return self._ratio_to_percent(info.get("trailingAnnualDividendYield"))

    def _net_profit_from_info(self, info: Dict[str, Any]) -> Optional[float]:
        revenue = self._safe_float(info.get("totalRevenue"))
        margin = self._safe_float(info.get("profitMargins"))
        if revenue is None or margin is None:
            return None
        return revenue * margin

    def _crypto_yahoo_timeout(self) -> float:
        try:
            return max(0.5, float(os.getenv("CRYPTO_YAHOO_TIMEOUT_SECONDS", "3")))
        except ValueError:
            return 3.0

    def _load_public_yahoo_chart(
        self,
        symbol: str,
        *,
        range_value: str,
        interval: str,
    ) -> Optional[Dict[str, Any]]:
        query = urllib.parse.urlencode({"range": range_value, "interval": interval})
        encoded_symbol = urllib.parse.quote(symbol, safe="")
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{encoded_symbol}?{query}"
        try:
            request = urllib.request.Request(url, headers={"User-Agent": "DSA-local-quick-query/1.0"})
            with urllib.request.urlopen(request, timeout=self._crypto_yahoo_timeout()) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except Exception as exc:
            logger.info("[yahoo_chart] request unavailable for %s: %s", symbol, exc)
            return None

        try:
            result = payload["chart"]["result"][0]
        except (KeyError, IndexError, TypeError):
            return None
        return result if isinstance(result, dict) else None

    @staticmethod
    def _public_yahoo_history_range(days: int) -> str:
        requested = max(5, int(days or 30))
        if requested <= 30:
            return "1mo"
        if requested <= 90:
            return "3mo"
        if requested <= 180:
            return "6mo"
        return "1y"

    def _get_public_yahoo_history_data(
        self,
        stock_code: str,
        *,
        period: str,
        days: int,
    ) -> Optional[Dict[str, Any]]:
        if not self._supports_public_history_fallback(stock_code):
            return None
        symbol = self._to_yfinance_profile_symbol(stock_code)
        if not symbol:
            return None
        result = self._load_public_yahoo_chart(
            symbol,
            range_value=self._public_yahoo_history_range(days),
            interval="1d",
        )
        if not result:
            return None

        try:
            meta = result.get("meta") if isinstance(result.get("meta"), dict) else {}
            timestamps = result.get("timestamp") if isinstance(result.get("timestamp"), list) else []
            quote_container = (result.get("indicators") or {}).get("quote")
            if isinstance(quote_container, list):
                quote_block = quote_container[0] if quote_container and isinstance(quote_container[0], dict) else {}
            elif isinstance(quote_container, dict):
                quote_block = quote_container
            else:
                quote_block = {}
            rows = []
            start_index = max(0, len(timestamps) - max(1, int(days or 30)))
            for index in range(start_index, len(timestamps)):
                def _value(name: str):
                    values = quote_block.get(name) or []
                    if not isinstance(values, list):
                        return None
                    return values[index] if index < len(values) else None

                close = _value("close")
                if close is None:
                    continue
                try:
                    date_value = datetime.fromtimestamp(int(timestamps[index]), tz=timezone.utc).strftime("%Y-%m-%d")
                except (OSError, OverflowError, TypeError, ValueError):
                    continue
                rows.append({
                    "date": date_value,
                    "open": _value("open"),
                    "high": _value("high"),
                    "low": _value("low"),
                    "close": close,
                    "volume": _value("volume"),
                    "amount": None,
                    "change_percent": None,
                })
        except (AttributeError, IndexError, KeyError, TypeError, ValueError) as exc:
            logger.info("[public_history] malformed Yahoo chart payload for %s: %s", symbol, exc)
            return None
        if not rows:
            return None
        return {
            "stock_code": stock_code,
            "stock_name": meta.get("shortName") or meta.get("longName") or symbol,
            "period": period,
            "source": "yahoo_chart_history",
            "data": rows,
        }

    @staticmethod
    def _supports_public_history_fallback(stock_code: str) -> bool:
        code = (stock_code or "").strip().upper()
        if not code or normalize_crypto_symbol(code) is not None:
            return False
        if code.endswith((".SH", ".SZ", ".BJ", ".SS", ".T", ".KS", ".KQ", ".TW", ".TO", ".L", ".AX")) \
                or code.startswith(("SH", "SZ", "BJ")):
            return False
        if code.startswith("HK") and code[2:].isdigit():
            return True
        if code.endswith(".HK") and code[:-3].isdigit():
            return True
        normalized_us = code[:-3] if code.endswith(".US") else code
        return bool(re.fullmatch(r"[A-Z]{1,5}(?:\.[A-Z])?", normalized_us))

    def _load_crypto_yahoo_chart(
        self,
        symbol: str,
        *,
        range_value: str,
        interval: str,
    ) -> Optional[Dict[str, Any]]:
        return self._load_public_yahoo_chart(symbol, range_value=range_value, interval=interval)

    def _get_crypto_realtime_quote(self, symbol: str) -> Optional[Dict[str, Any]]:
        result = self._load_crypto_yahoo_chart(symbol, range_value="2d", interval="1d")
        if not result:
            return None
        meta = result.get("meta") or {}
        quote_block = ((result.get("indicators") or {}).get("quote") or [{}])[0] or {}
        close_values = [value for value in (quote_block.get("close") or []) if value is not None]
        volume_values = [value for value in (quote_block.get("volume") or []) if value is not None]
        current_price = meta.get("regularMarketPrice")
        if current_price is None and close_values:
            current_price = close_values[-1]
        prev_close = meta.get("chartPreviousClose")
        if prev_close is None and len(close_values) > 1:
            prev_close = close_values[-2]
        change = None
        change_percent = None
        try:
            if current_price is not None and prev_close:
                change = float(current_price) - float(prev_close)
                change_percent = (change / float(prev_close)) * 100
        except (TypeError, ValueError, ZeroDivisionError):
            change = None
            change_percent = None
        return {
            "stock_code": symbol,
            "stock_name": meta.get("shortName") or meta.get("longName") or symbol,
            "current_price": float(current_price) if current_price is not None else None,
            "change": round(change, 6) if change is not None else None,
            "change_percent": round(change_percent, 4) if change_percent is not None else None,
            "open": (quote_block.get("open") or [None])[-1],
            "high": (quote_block.get("high") or [None])[-1],
            "low": (quote_block.get("low") or [None])[-1],
            "prev_close": prev_close,
            "volume": volume_values[-1] if volume_values else None,
            "amount": None,
            "source": "crypto_yahoo_chart",
            "update_time": datetime.now().isoformat(),
        }

    def _get_crypto_history_data(self, symbol: str, *, period: str, days: int) -> Dict[str, Any]:
        requested_days = max(5, int(days or 30))
        result = self._load_crypto_yahoo_chart(symbol, range_value=f"{requested_days}d", interval="1d")
        if not result:
            return {
                "stock_code": symbol,
                "stock_name": symbol,
                "period": period,
                "source": "crypto_yahoo_chart",
                "data": [],
            }
        meta = result.get("meta") or {}
        timestamps = result.get("timestamp") or []
        quote_block = ((result.get("indicators") or {}).get("quote") or [{}])[0] or {}
        rows = []
        start_index = max(0, len(timestamps) - int(days or 30))
        for index in range(start_index, len(timestamps)):
            def _value(name: str):
                values = quote_block.get(name) or []
                return values[index] if index < len(values) else None

            close = _value("close")
            if close is None:
                continue
            rows.append(
                {
                    "date": datetime.fromtimestamp(int(timestamps[index]), tz=timezone.utc).strftime("%Y-%m-%d"),
                    "open": _value("open"),
                    "high": _value("high"),
                    "low": _value("low"),
                    "close": close,
                    "volume": _value("volume"),
                    "amount": None,
                    "change_percent": None,
                }
            )
        return {
            "stock_code": symbol,
            "stock_name": meta.get("shortName") or meta.get("longName") or symbol,
            "period": period,
            "source": "crypto_yahoo_chart",
            "data": rows,
        }
    
    def _get_placeholder_quote(self, stock_code: str) -> Dict[str, Any]:
        """
        获取占位行情数据（用于测试）
        
        Args:
            stock_code: 股票代码
            
        Returns:
            占位行情数据
        """
        return {
            "stock_code": stock_code,
            "stock_name": f"股票{stock_code}",
            "current_price": 0.0,
            "change": None,
            "change_percent": None,
            "open": None,
            "high": None,
            "low": None,
            "prev_close": None,
            "volume": None,
            "amount": None,
            "update_time": datetime.now().isoformat(),
        }
