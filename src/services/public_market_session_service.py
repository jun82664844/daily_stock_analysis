# -*- coding: utf-8 -*-
"""Truthful, no-AI market-session context for public market surfaces."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable, Dict, Optional, Union

from src.core.trading_calendar import build_market_phase_context


SessionTime = Optional[Union[str, datetime]]
SessionContextBuilder = Callable[..., Any]

_KNOWN_PHASES = {
    "premarket",
    "intraday",
    "lunch_break",
    "closing_auction",
    "postmarket",
    "non_trading",
    "unknown",
}
_OPEN_PHASES = {"intraday", "closing_auction"}


def unknown_market_session(*warning_codes: str) -> Dict[str, Any]:
    warnings = list(dict.fromkeys(code for code in warning_codes if code))
    return {
        "session_state": "unknown",
        "session_phase": "unknown",
        "market_local_time": None,
        "minutes_to_open": None,
        "minutes_to_close": None,
        "session_source": "unavailable",
        "session_warning_codes": warnings,
    }


class PublicMarketSessionService:
    """Map the shared exchange calendar context to a public DTO."""

    def __init__(self, *, context_builder: SessionContextBuilder = build_market_phase_context) -> None:
        self.context_builder = context_builder

    def resolve(self, market: str, as_of: SessionTime = None) -> Dict[str, Any]:
        try:
            context = self.context_builder(
                market=market,
                current_time=self._parse_time(as_of),
                trigger_source="public_market_home",
            )
            raw_phase = getattr(context.phase, "value", context.phase)
            phase = str(raw_phase) if raw_phase in _KNOWN_PHASES else "unknown"
            warnings = list(dict.fromkeys(str(code) for code in (context.warnings or []) if code))
            if phase == "unknown":
                return {
                    **unknown_market_session(*warnings),
                    "market_local_time": context.market_local_time.isoformat()
                    if getattr(context, "market_local_time", None)
                    else None,
                }
            return {
                "session_state": "open" if phase in _OPEN_PHASES else "closed",
                "session_phase": phase,
                "market_local_time": context.market_local_time.isoformat(),
                "minutes_to_open": self._non_negative(getattr(context, "minutes_to_open", None)),
                "minutes_to_close": self._non_negative(getattr(context, "minutes_to_close", None)),
                "session_source": "exchange_calendar",
                "session_warning_codes": warnings,
            }
        except Exception:
            return unknown_market_session("calendar_error")

    @staticmethod
    def _parse_time(value: SessionTime) -> Optional[datetime]:
        if value is None:
            return None
        if isinstance(value, datetime):
            return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)
        raw = str(value).strip()
        if not raw:
            return None
        parsed = datetime.fromisoformat(raw[:-1] + "+00:00" if raw.endswith("Z") else raw)
        return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=timezone.utc)

    @staticmethod
    def _non_negative(value: Any) -> Optional[int]:
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            return None
        return parsed if parsed >= 0 else None
