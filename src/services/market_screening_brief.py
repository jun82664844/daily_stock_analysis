from __future__ import annotations

import math
from typing import Any, Dict, Iterable, List, Optional


_AI_FIELDS = (
    "llm_score",
    "llm_thesis",
    "llm_catalysts",
    "llm_watch_items",
    "llm_invalidators",
    "llm_risks",
)
_FRESHNESS_VALUES = {"fresh", "cached", "stale", "unavailable"}


def _number(value: Any) -> Optional[float]:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


def _text(value: Any) -> str:
    return str(value or "").strip()


def _text_list(value: Any) -> List[str]:
    if not isinstance(value, list):
        return []
    return list(dict.fromkeys(_text(item) for item in value if _text(item)))


def _first_text(values: Iterable[Any]) -> str:
    for value in values:
        normalized = _text(value)
        if normalized:
            return normalized
    return ""


def _freshness(context: Dict[str, Any], quote: Dict[str, Any], warnings: List[str]) -> str:
    joined_warnings = " ".join(warnings).lower()
    if any(token in joined_warnings for token in ("stale", "expired", "过期")):
        return "stale"
    if not quote and any(
        token in joined_warnings
        for token in ("unavailable", "missing", "failed", "timeout", "缺失", "失败", "超时")
    ):
        return "unavailable"

    explicit = _first_text(
        (
            quote.get("freshness"),
            quote.get("data_freshness"),
            quote.get("status"),
            context.get("freshness"),
            context.get("data_freshness"),
            context.get("quote_status"),
        )
    ).lower()
    aliases = {
        "ok": "fresh",
        "current": "fresh",
        "realtime": "fresh",
        "real_time": "fresh",
        "cache": "cached",
        "disk_cache": "cached",
        "expired": "stale",
        "missing": "unavailable",
        "failed": "unavailable",
        "error": "unavailable",
    }
    normalized = aliases.get(explicit, explicit)
    if normalized in _FRESHNESS_VALUES:
        return normalized
    return "cached" if quote else "unavailable"


def _metric(code: str, value: float, *, source: str, as_of: str = "") -> Dict[str, Any]:
    return {"code": code, "value": value, "source": source, "as_of": as_of or None}


def build_market_screening_brief(candidate: Dict[str, Any]) -> Dict[str, Any]:
    context = candidate.get("dsa_context") if isinstance(candidate.get("dsa_context"), dict) else {}
    quote = context.get("quote") if isinstance(context.get("quote"), dict) else {}
    factors = candidate.get("factor_scores") if isinstance(candidate.get("factor_scores"), dict) else {}
    raw = candidate.get("raw") if isinstance(candidate.get("raw"), dict) else {}
    numeric_factors = sorted(
        (
            (str(key), number)
            for key, value in factors.items()
            if (number := _number(value)) is not None
        ),
        key=lambda item: item[1],
        reverse=True,
    )
    warnings = _text_list(context.get("warnings"))
    freshness = _freshness(context, quote, warnings)
    quote_price = next(
        (
            number
            for key in ("price", "current_price", "close", "latest_price")
            if (number := _number(quote.get(key))) is not None
        ),
        None,
    )
    source = _first_text((quote.get("source"), context.get("source"), candidate.get("source")))
    as_of = _first_text(
        (
            quote.get("updated_at"),
            quote.get("timestamp"),
            quote.get("as_of"),
            context.get("updated_at"),
            context.get("timestamp"),
        )
    )

    snapshot_as_of = _first_text((raw.get("updated_at"), raw.get("timestamp"), raw.get("ticktime"), as_of))
    observed_metrics: List[Dict[str, Any]] = []
    matched_condition_codes: List[str] = []
    market_metrics = (
        ("price", candidate.get("price") if candidate.get("price") is not None else raw.get("price")),
        ("change_pct", candidate.get("change_pct") if candidate.get("change_pct") is not None else raw.get("change_pct")),
        ("pe_ratio", raw.get("pe_ratio")),
        ("pb_ratio", raw.get("pb_ratio")),
        ("turnover_rate", raw.get("turnover_rate")),
        ("amount", candidate.get("amount") if candidate.get("amount") is not None else raw.get("amount")),
        ("total_mv", raw.get("total_mv")),
    )
    for code, raw_value in market_metrics:
        value = _number(raw_value)
        if value is not None:
            observed_metrics.append(_metric(code, value, source="market_snapshot", as_of=snapshot_as_of))
    for code in ("screen_score", "score"):
        value = _number(candidate.get(code))
        if value is None:
            continue
        observed_metrics.append(_metric(code, value, source="alphasift"))
        if code == "screen_score":
            matched_condition_codes.append(code)
    for key, value in numeric_factors[:3]:
        code = f"factor:{key}"
        observed_metrics.append(_metric(code, value, source="alphasift"))
        matched_condition_codes.append(code)
    if quote_price is not None and not any(item["code"] == "price" for item in observed_metrics):
        observed_metrics.append(_metric("quote_price", quote_price, source=source or "dsa_quote", as_of=as_of))

    completeness = 0
    if _text(candidate.get("code")):
        completeness += 10
    if any(_number(candidate.get(key)) is not None for key in ("screen_score", "score", "change_pct")):
        completeness += 15
    if numeric_factors:
        completeness += 25
    if quote_price is not None:
        completeness += 25
    if as_of:
        completeness += 15
    if source:
        completeness += 10
    if any(item["code"] in {"pe_ratio", "pb_ratio", "turnover_rate", "amount", "total_mv"} for item in observed_metrics):
        completeness += 15

    has_factors = bool(numeric_factors)
    has_quote = quote_price is not None
    if not has_factors and not has_quote:
        source_status = "unavailable"
    elif freshness in {"stale", "unavailable"} or warnings or not (has_factors and has_quote):
        source_status = "partial"
    else:
        source_status = "available"

    information_flags = _text_list(candidate.get("risk_flags"))
    if freshness == "stale":
        information_flags.append("data_stale")
    elif freshness == "unavailable":
        information_flags.append("data_unavailable")
    if warnings and freshness not in {"stale", "unavailable"}:
        information_flags.append("data_warning")
    information_flags = list(dict.fromkeys(information_flags))

    if freshness in {"stale", "unavailable"}:
        observation_codes = ["refresh_data"]
    elif has_factors:
        observation_codes = ["monitor_factor_values"]
    else:
        observation_codes = ["complete_factor_data"]

    condition_exit_codes = ["factor_condition_changed"] if has_factors else ["data_unavailable"]
    ai_used = any(candidate.get(key) not in (None, "", [], {}) for key in _AI_FIELDS)

    return {
        "matched_condition_codes": matched_condition_codes,
        "observed_metrics": observed_metrics,
        "information_flags": information_flags,
        "observation_codes": observation_codes,
        "condition_exit_codes": condition_exit_codes,
        "data_freshness": freshness,
        "data_completeness": min(completeness, 100),
        "source_status": source_status,
        "ai_used": ai_used,
    }
