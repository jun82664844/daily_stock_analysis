# -*- coding: utf-8 -*-
"""Privacy-bounded local retention funnel built on platform audit events."""

from __future__ import annotations

from datetime import datetime, timedelta
from hashlib import sha256
from typing import Any, Dict

from src.platform_audit import PlatformAuditLogger


RETENTION_EVENT_ORDER = (
    "free_query_completed",
    "registration_completed",
    "api_trial_submitted",
    "trial_report_opened",
    "premium_options_viewed",
)
RETENTION_ACTION_PREFIX = "retention_"


def _session_hash(session_id: str) -> str:
    return sha256(session_id.strip().encode("utf-8")).hexdigest()[:24]


def _parse_created_at(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        return None


def _percent(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return round((numerator / denominator) * 100, 1)


class PlatformRetentionFunnelService:
    def __init__(self, audit_logger: PlatformAuditLogger | None = None) -> None:
        self._audit = audit_logger or PlatformAuditLogger()

    def record_event(
        self,
        *,
        event: str,
        session_id: str,
        source: str,
        user_id: int | None,
    ) -> Dict[str, Any]:
        if event not in RETENTION_EVENT_ORDER:
            raise ValueError("Unsupported retention event")
        hashed_session = _session_hash(session_id)
        action = f"{RETENTION_ACTION_PREFIX}{event}"
        today = datetime.now().date()
        duplicate = any(
            item.get("action") == action
            and (item.get("metadata") or {}).get("session_hash") == hashed_session
            and (_parse_created_at(item.get("created_at")) or datetime.min).date() == today
            for item in self._audit.list_events(limit=500)
        )
        if not duplicate:
            self._audit.record(
                user_id=user_id,
                action=action,
                metadata={"session_hash": hashed_session, "source": source},
            )
        return {
            "event": event,
            "accepted": True,
            "duplicate": duplicate,
            "ai_used": False,
        }

    def build_summary(self, *, window_days: int = 30) -> Dict[str, Any]:
        bounded_window = max(1, min(int(window_days), 90))
        cutoff = datetime.now() - timedelta(days=bounded_window)
        stage_sessions: Dict[str, set[str]] = {event: set() for event in RETENTION_EVENT_ORDER}

        for item in self._audit.list_events(limit=500):
            action = str(item.get("action") or "")
            if not action.startswith(RETENTION_ACTION_PREFIX):
                continue
            event = action[len(RETENTION_ACTION_PREFIX):]
            if event not in stage_sessions:
                continue
            created_at = _parse_created_at(item.get("created_at"))
            if created_at is None or created_at < cutoff:
                continue
            session_hash = (item.get("metadata") or {}).get("session_hash")
            if isinstance(session_hash, str) and session_hash:
                stage_sessions[event].add(session_hash)

        all_sessions = set().union(*stage_sessions.values())
        start_sessions = set(stage_sessions[RETENTION_EVENT_ORDER[0]])
        previous_reached = set(start_sessions)
        stages = []
        for index, event in enumerate(RETENTION_EVENT_ORDER):
            raw_sessions = stage_sessions[event]
            reached = set(start_sessions) if index == 0 else previous_reached & raw_sessions
            previous_count = len(previous_reached) if index > 0 else len(reached)
            stages.append(
                {
                    "event": event,
                    "unique_sessions": len(raw_sessions),
                    "reached_from_start": len(reached),
                    "dropped_from_previous": max(0, previous_count - len(reached)),
                    "conversion_from_previous_pct": _percent(len(reached), previous_count),
                    "conversion_from_start_pct": _percent(len(reached), len(start_sessions)),
                }
            )
            previous_reached = reached

        return {
            "mode": "local_only",
            "window_days": bounded_window,
            "generated_at": datetime.now().isoformat(),
            "total_sessions": len(all_sessions),
            "stages": stages,
            "ai_used": False,
        }
