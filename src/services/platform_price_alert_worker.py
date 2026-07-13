# -*- coding: utf-8 -*-
"""Single-process monitor for private exact-price alert rules."""

from __future__ import annotations

import math
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Optional

from src.platform_watchlist_automation import PlatformWatchlistAutomationService
from src.services.basic_query_service import BasicQueryService
from src.storage import DatabaseManager, PlatformWatchlistAlertRule


def _utc_naive_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class PlatformPriceAlertWorker:
    def __init__(
        self,
        *,
        db_manager: Optional[DatabaseManager] = None,
        quote_loader: Optional[Callable[[str], Dict[str, Any]]] = None,
        max_rules_per_cycle: int = 1000,
        max_workers: int = 8,
        quote_timeout_seconds: float = 3.0,
    ) -> None:
        self.service = PlatformWatchlistAutomationService(db_manager=db_manager)
        self.quote_timeout_seconds = max(0.5, min(float(quote_timeout_seconds), 10.0))
        if quote_loader is None:
            query_service = BasicQueryService(fetch_timeout_seconds=self.quote_timeout_seconds)
            self.quote_loader = query_service.get_quote_card
        else:
            self.quote_loader = quote_loader
        self.max_rules_per_cycle = max(1, min(int(max_rules_per_cycle), 10_000))
        self.max_workers = max(1, min(int(max_workers), 32))

    def run_once(self) -> Dict[str, int]:
        rules = self.service.list_enabled_exact_price_rules(limit=self.max_rules_per_cycle)
        stats = {"loaded": len(rules), "observed": 0, "triggered": 0, "degraded": 0, "failed": 0}
        if not rules:
            return stats
        quotes = self._load_unique_symbols(rules)
        results = []
        for rule in rules:
            quote = quotes.get(rule.stock_code)
            result = self._evaluate(rule, quote)
            results.append(result)
            if result["status"] == "observed":
                stats["observed"] += 1
                if result["triggered"]:
                    stats["triggered"] += 1
            else:
                stats[result["status"]] += 1
        self.service.apply_price_alert_results(results)
        return stats

    def _load_unique_symbols(self, rules: list[PlatformWatchlistAlertRule]) -> Dict[str, Any]:
        symbols = sorted({rule.stock_code for rule in rules})
        loaded: Dict[str, Any] = {}
        with ThreadPoolExecutor(max_workers=min(self.max_workers, len(symbols))) as executor:
            futures = {executor.submit(self.quote_loader, symbol): symbol for symbol in symbols}
            for future in as_completed(futures):
                symbol = futures[future]
                try:
                    loaded[symbol] = future.result()
                except Exception:
                    loaded[symbol] = None
        return loaded

    @staticmethod
    def _evaluate(rule: PlatformWatchlistAlertRule, payload: Any) -> Dict[str, Any]:
        quote = payload.get("quote") if isinstance(payload, dict) else None
        quote = quote if isinstance(quote, dict) else (payload if isinstance(payload, dict) else {})
        freshness = str(quote.get("freshness") or "unavailable").lower()
        price = PlatformPriceAlertWorker._number(quote.get("current_price", quote.get("price")))
        if freshness != "fresh":
            return {"rule_id": int(rule.id), "status": "degraded", "triggered": False}
        if price is None:
            return {"rule_id": int(rule.id), "status": "failed", "triggered": False}
        previous = PlatformPriceAlertWorker._number(rule.last_observed_value)
        threshold = PlatformPriceAlertWorker._number(rule.threshold)
        if threshold is None:
            return {"rule_id": int(rule.id), "status": "failed", "triggered": False}
        direction = "above" if rule.rule_type == "price_above" else "below"
        triggered = False
        if previous is not None:
            triggered = (
                previous < threshold <= price
                if rule.rule_type == "price_above"
                else previous > threshold >= price
            )
        return {
            "rule_id": int(rule.id),
            "status": "observed",
            "price": price,
            "observed_at": _utc_naive_now(),
            "source": str(quote.get("source") or "unknown")[:64],
            "direction": direction,
            "triggered": triggered,
        }

    @staticmethod
    def _number(value: Any) -> Optional[float]:
        try:
            number = float(value)
        except (TypeError, ValueError):
            return None
        return number if math.isfinite(number) else None
