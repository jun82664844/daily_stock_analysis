# -*- coding: utf-8 -*-
"""Private alert rules and persisted daily watchlist radar runs."""

from __future__ import annotations

import json
import math
from threading import RLock
from typing import Any, Dict, List, Optional

from sqlalchemy import and_, select

from src.platform_accounts import PlatformAccountService
from src.platform_watchlist import PlatformWatchlistService
from src.platform_watchlist_radar import PlatformWatchlistRadarService
from src.storage import (
    DatabaseManager,
    PlatformWatchlistAlertEvent,
    PlatformWatchlistAlertRule,
    PlatformWatchlistRadarRun,
    utc_naive_now,
)


ALERT_RULE_TYPES = {"price_move", "ma20_cross", "volume_change", "source_update", "data_quality"}
PAID_PLANS = {"pro", "premium", "enterprise"}


class AlertRuleLimitExceeded(ValueError):
    """Raised when a plan has no remaining private alert slots."""


class PlatformWatchlistAutomationService:
    _user_locks = tuple(RLock() for _ in range(64))

    def __init__(
        self,
        *,
        db_manager: Optional[DatabaseManager] = None,
        radar_service: Optional[PlatformWatchlistRadarService] = None,
    ) -> None:
        self.db = db_manager or DatabaseManager.get_instance()
        self.radar_service = radar_service or PlatformWatchlistRadarService()

    @staticmethod
    def rule_limit(plan: str) -> int:
        return 50 if str(plan or "free").lower() in PAID_PLANS else 3

    def list_rules(self, user_id: int, *, plan: Optional[str] = None) -> Dict[str, Any]:
        normalized_plan = plan or self._user_plan(user_id)
        limit = self.rule_limit(normalized_plan)
        with self.db.get_session() as session:
            rows = session.execute(
                select(PlatformWatchlistAlertRule)
                .where(
                    and_(
                        PlatformWatchlistAlertRule.user_id == int(user_id),
                        PlatformWatchlistAlertRule.enabled.is_(True),
                    )
                )
                .order_by(PlatformWatchlistAlertRule.updated_at.desc(), PlatformWatchlistAlertRule.id.desc())
                .limit(limit)
            ).scalars().all()
            items = [self._rule_payload(row) for row in rows]
        return {
            "user_id": int(user_id),
            "plan": str(normalized_plan),
            "limit": limit,
            "total": len(items),
            "remaining": max(0, limit - len(items)),
            "items": items,
            "ai_used": False,
        }

    def save_rule(
        self,
        *,
        user_id: int,
        plan: str,
        stock_code: str,
        rule_type: str,
        threshold: Optional[float] = None,
        reference_value: Optional[float] = None,
        enabled: bool = True,
    ) -> Dict[str, Any]:
        with self._user_lock(user_id):
            return self._save_rule_locked(
                user_id=user_id,
                plan=plan,
                stock_code=stock_code,
                rule_type=rule_type,
                threshold=threshold,
                reference_value=reference_value,
                enabled=enabled,
            )

    def _save_rule_locked(
        self,
        *,
        user_id: int,
        plan: str,
        stock_code: str,
        rule_type: str,
        threshold: Optional[float] = None,
        reference_value: Optional[float] = None,
        enabled: bool = True,
    ) -> Dict[str, Any]:
        normalized_type = str(rule_type or "").strip().lower()
        if normalized_type not in ALERT_RULE_TYPES:
            raise ValueError(f"unsupported alert rule type: {normalized_type}")
        normalized_code = PlatformWatchlistService.normalize_stock_code(stock_code)
        normalized_threshold = self._number(threshold)
        normalized_reference = self._number(reference_value)
        if threshold is not None and normalized_threshold is None:
            raise ValueError("threshold must be a finite number")
        if reference_value is not None and normalized_reference is None:
            raise ValueError("reference_value must be a finite number")
        if normalized_type in {"price_move", "volume_change"}:
            if normalized_threshold is None or normalized_threshold <= 0 or normalized_threshold > 1000:
                raise ValueError("threshold must be greater than zero")
        now = utc_naive_now()
        with self.db.session_scope() as session:
            existing = session.execute(
                select(PlatformWatchlistAlertRule).where(
                    and_(
                        PlatformWatchlistAlertRule.user_id == int(user_id),
                        PlatformWatchlistAlertRule.stock_code == normalized_code,
                        PlatformWatchlistAlertRule.rule_type == normalized_type,
                    )
                )
            ).scalars().first()
            if existing is None:
                enabled_count = len(
                    session.execute(
                        select(PlatformWatchlistAlertRule.id).where(
                            and_(
                                PlatformWatchlistAlertRule.user_id == int(user_id),
                                PlatformWatchlistAlertRule.enabled.is_(True),
                            )
                        )
                    ).all()
                )
                if enabled and enabled_count >= self.rule_limit(plan):
                    raise AlertRuleLimitExceeded("alert rule limit exceeded")
                session.add(
                    PlatformWatchlistAlertRule(
                        user_id=int(user_id),
                        stock_code=normalized_code,
                        rule_type=normalized_type,
                        threshold=normalized_threshold,
                        reference_value=normalized_reference,
                        enabled=bool(enabled),
                        created_at=now,
                        updated_at=now,
                    )
                )
            else:
                if enabled and not existing.enabled:
                    enabled_count = len(
                        session.execute(
                            select(PlatformWatchlistAlertRule.id).where(
                                and_(
                                    PlatformWatchlistAlertRule.user_id == int(user_id),
                                    PlatformWatchlistAlertRule.enabled.is_(True),
                                )
                            )
                        ).all()
                    )
                    if enabled_count >= self.rule_limit(plan):
                        raise AlertRuleLimitExceeded("alert rule limit exceeded")
                existing.threshold = normalized_threshold
                existing.reference_value = normalized_reference
                existing.enabled = bool(enabled)
                existing.updated_at = now
        return self.list_rules(user_id, plan=plan)

    def delete_rule(self, *, user_id: int, rule_id: int) -> bool:
        with self._user_lock(user_id):
            return self._delete_rule_locked(user_id=user_id, rule_id=rule_id)

    def _delete_rule_locked(self, *, user_id: int, rule_id: int) -> bool:
        with self.db.session_scope() as session:
            row = session.execute(
                select(PlatformWatchlistAlertRule).where(
                    and_(
                        PlatformWatchlistAlertRule.id == int(rule_id),
                        PlatformWatchlistAlertRule.user_id == int(user_id),
                    )
                )
            ).scalars().first()
            if row is None:
                return False
            row.enabled = False
            row.updated_at = utc_naive_now()
            return True

    def run_and_save(self, *, user_id: int, plan: str) -> Dict[str, Any]:
        with self._user_lock(user_id):
            return self._run_and_save_locked(user_id=user_id, plan=plan)

    def _run_and_save_locked(self, *, user_id: int, plan: str) -> Dict[str, Any]:
        previous_payload = self._latest_payload(user_id)
        radar = self.radar_service.build(user_id=int(user_id), plan=plan)
        radar["user_id"] = int(user_id)
        radar["plan"] = str(plan)
        rules = self._rule_rows(user_id, plan=plan)
        triggered = self._evaluate_rules(rules, radar, previous_payload)
        stored_payload = self._storage_payload(radar)
        summary = radar.get("summary") or {}
        with self.db.session_scope() as session:
            run = PlatformWatchlistRadarRun(
                user_id=int(user_id),
                plan=str(plan),
                processed=int(radar.get("processed") or 0),
                event_count=int(summary.get("event_count") or 0),
                risk_count=int(summary.get("risk_count") or 0),
                source_event_count=int(summary.get("source_event_count") or 0),
                triggered_count=len(triggered),
                payload_json=json.dumps(stored_payload, ensure_ascii=False, separators=(",", ":")),
                created_at=utc_naive_now(),
            )
            session.add(run)
            session.flush()
            for item in triggered:
                session.add(
                    PlatformWatchlistAlertEvent(
                        user_id=int(user_id),
                        rule_id=int(item["rule_id"]),
                        radar_run_id=int(run.id),
                        stock_code=item["stock_code"],
                        rule_type=item["rule_type"],
                        direction=item.get("direction"),
                        value=item.get("value"),
                        threshold=item.get("threshold"),
                        created_at=utc_naive_now(),
                    )
                )
            run_id = int(run.id)
        result = dict(radar)
        result["run_id"] = run_id
        result["triggered_alerts"] = triggered
        return result

    def list_history(self, user_id: int, *, limit: int = 7) -> Dict[str, Any]:
        safe_limit = max(1, min(int(limit), 30))
        with self.db.get_session() as session:
            rows = session.execute(
                select(PlatformWatchlistRadarRun)
                .where(PlatformWatchlistRadarRun.user_id == int(user_id))
                .order_by(PlatformWatchlistRadarRun.created_at.desc(), PlatformWatchlistRadarRun.id.desc())
                .limit(safe_limit)
            ).scalars().all()
            total = len(
                session.execute(
                    select(PlatformWatchlistRadarRun.id).where(PlatformWatchlistRadarRun.user_id == int(user_id))
                ).all()
            )
            items = [self._history_payload(row) for row in rows]
        return {"user_id": int(user_id), "items": items, "total": total, "ai_used": False}

    def _rule_rows(self, user_id: int, *, plan: str) -> List[PlatformWatchlistAlertRule]:
        with self.db.get_session() as session:
            rows = session.execute(
                select(PlatformWatchlistAlertRule).where(
                    and_(
                        PlatformWatchlistAlertRule.user_id == int(user_id),
                        PlatformWatchlistAlertRule.enabled.is_(True),
                    )
                )
                .order_by(PlatformWatchlistAlertRule.updated_at.desc(), PlatformWatchlistAlertRule.id.desc())
                .limit(self.rule_limit(plan))
            ).scalars().all()
            for row in rows:
                session.expunge(row)
            return list(rows)

    def _latest_payload(self, user_id: int) -> Dict[str, Any]:
        with self.db.get_session() as session:
            row = session.execute(
                select(PlatformWatchlistRadarRun)
                .where(PlatformWatchlistRadarRun.user_id == int(user_id))
                .order_by(PlatformWatchlistRadarRun.created_at.desc(), PlatformWatchlistRadarRun.id.desc())
                .limit(1)
            ).scalars().first()
            if row is None:
                return {}
            try:
                payload = json.loads(row.payload_json or "{}")
            except (TypeError, json.JSONDecodeError):
                return {}
            return payload if isinstance(payload, dict) else {}

    def _evaluate_rules(
        self,
        rules: List[PlatformWatchlistAlertRule],
        radar: Dict[str, Any],
        previous_payload: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        current_items = {str(item.get("stock_code")): item for item in radar.get("items") or [] if isinstance(item, dict)}
        previous_items = {
            str(item.get("stock_code")): item
            for item in previous_payload.get("items") or []
            if isinstance(item, dict)
        }
        triggered: List[Dict[str, Any]] = []
        for rule in rules:
            current = current_items.get(rule.stock_code)
            if current is None:
                continue
            event = self._evaluate_rule(rule, current, previous_items.get(rule.stock_code))
            if event is not None:
                triggered.append(event)
        return triggered

    def _evaluate_rule(
        self,
        rule: PlatformWatchlistAlertRule,
        current: Dict[str, Any],
        previous: Optional[Dict[str, Any]],
    ) -> Optional[Dict[str, Any]]:
        value: Optional[float] = None
        direction: Optional[str] = None
        events = [item for item in current.get("events") or [] if isinstance(item, dict)]
        if rule.rule_type == "price_move":
            value = self._number(current.get("change_percent"))
            if value is None or abs(value) < float(rule.threshold or 0):
                return None
            direction = "up" if value > 0 else "down"
        elif rule.rule_type == "volume_change":
            value = self._number(current.get("volume_change_percent"))
            if value is None or abs(value) < float(rule.threshold or 0):
                return None
            direction = "expanded" if value > 0 else "contracted"
        elif rule.rule_type == "source_update":
            current_urls = {
                str(item.get("source_url"))
                for item in events
                if item.get("type") == "source_update" and item.get("source_url")
            }
            previous_urls = {
                str(item.get("source_url"))
                for item in (previous or {}).get("events") or []
                if isinstance(item, dict) and item.get("type") == "source_update" and item.get("source_url")
            }
            if not current_urls.difference(previous_urls):
                return None
            direction = "new"
        elif rule.rule_type == "data_quality":
            if current.get("status") == "ok" and not any(item.get("type") == "data_quality" for item in events):
                return None
            direction = "degraded"
        elif rule.rule_type == "ma20_cross":
            if not previous:
                return None
            current_price = self._number(current.get("current_price"))
            current_ma20 = self._number(current.get("ma20"))
            previous_price = self._number(previous.get("current_price"))
            previous_ma20 = self._number(previous.get("ma20"))
            if None in {current_price, current_ma20, previous_price, previous_ma20}:
                return None
            previous_side = previous_price >= previous_ma20
            current_side = current_price >= current_ma20
            if previous_side == current_side:
                return None
            value = current_price
            direction = "above" if current_side else "below"
        else:
            return None
        return {
            "rule_id": int(rule.id),
            "stock_code": rule.stock_code,
            "rule_type": rule.rule_type,
            "direction": direction,
            "value": value,
            "threshold": self._number(rule.threshold),
            "reference_value": self._number(rule.reference_value),
            "ai_used": False,
        }

    @staticmethod
    def _storage_payload(radar: Dict[str, Any]) -> Dict[str, Any]:
        fields = (
            "stock_code", "stock_name", "market", "current_price", "change_percent", "ma20",
            "volume_change_percent", "signal_score", "freshness", "degradation_status", "status",
        )
        items = []
        for source in radar.get("items") or []:
            if not isinstance(source, dict):
                continue
            item = {field: source.get(field) for field in fields}
            item["events"] = [
                {
                    "type": event.get("type"),
                    "severity": event.get("severity"),
                    "direction": event.get("direction"),
                    "source_url": event.get("source_url") if str(event.get("source_url") or "").startswith(("http://", "https://")) else None,
                }
                for event in source.get("events") or []
                if isinstance(event, dict)
            ]
            items.append(item)
        return {
            "generated_at": radar.get("generated_at"),
            "summary": radar.get("summary") or {},
            "items": items,
            "ai_used": False,
        }

    @staticmethod
    def _rule_payload(row: PlatformWatchlistAlertRule) -> Dict[str, Any]:
        return {
            "id": int(row.id),
            "stock_code": row.stock_code,
            "rule_type": row.rule_type,
            "threshold": row.threshold,
            "reference_value": row.reference_value,
            "enabled": bool(row.enabled),
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "updated_at": row.updated_at.isoformat() if row.updated_at else None,
        }

    @staticmethod
    def _history_payload(row: PlatformWatchlistRadarRun) -> Dict[str, Any]:
        try:
            payload = json.loads(row.payload_json or "{}")
        except (TypeError, json.JSONDecodeError):
            payload = {}
        summary = payload.get("summary") if isinstance(payload, dict) else {}
        return {
            "id": int(row.id),
            "plan": row.plan,
            "processed": int(row.processed or 0),
            "event_count": int(row.event_count or 0),
            "risk_count": int(row.risk_count or 0),
            "source_event_count": int(row.source_event_count or 0),
            "triggered_count": int(row.triggered_count or 0),
            "strongest": (summary or {}).get("strongest"),
            "weakest": (summary or {}).get("weakest"),
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }

    def _user_plan(self, user_id: int) -> str:
        user = PlatformAccountService(self.db).get_user(int(user_id))
        return str(user.plan if user is not None else "free")

    @classmethod
    def _user_lock(cls, user_id: int) -> RLock:
        return cls._user_locks[int(user_id) % len(cls._user_locks)]

    @staticmethod
    def _number(value: Any) -> Optional[float]:
        try:
            number = None if value is None else float(value)
        except (TypeError, ValueError):
            return None
        return number if number is None or math.isfinite(number) else None
