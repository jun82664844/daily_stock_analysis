# -*- coding: utf-8 -*-
"""Versioned local snapshot storage for public event-reaction data."""

from __future__ import annotations

import copy
import json
import os
import re
import time
from pathlib import Path
from typing import Any, Dict, Mapping, Optional


SNAPSHOT_VERSION = 1
DEFAULT_MAX_BYTES = 1024 * 1024
_FORBIDDEN_KEYS = {
    "api_key",
    "apikey",
    "authorization",
    "cookie",
    "email",
    "password",
    "platform_user_id",
    "secret",
    "session",
    "token",
    "user_id",
}
_SECRET_VALUE = re.compile(r"(?:^|[^a-z0-9])sk-[a-z0-9_-]{8,}", re.IGNORECASE)
_PAYLOAD_KEYS = {
    "as_of",
    "items",
    "market_sources",
    "warnings",
    "cache",
    "ai_used",
    "informational_only",
}


class PublicEventReactionSnapshotStore:
    """Persist a bounded, public-only response without user or credential data."""

    def __init__(
        self,
        *,
        path: str | Path | None = None,
        wall_clock=time.time,
        cache_ttl_seconds: int = 900,
        stale_ttl_seconds: int = 86_400,
        max_bytes: int = DEFAULT_MAX_BYTES,
    ) -> None:
        self.path = Path(
            path
            or os.getenv(
                "PLATFORM_PUBLIC_EVENT_REACTIONS_V137_CACHE_PATH",
                "local/public_event_reactions_v137.json",
            )
        )
        self.wall_clock = wall_clock
        self.cache_ttl_seconds = max(1, int(cache_ttl_seconds))
        self.stale_ttl_seconds = max(
            self.cache_ttl_seconds,
            int(stale_ttl_seconds),
        )
        self.max_bytes = max(512, min(int(max_bytes), DEFAULT_MAX_BYTES))

    def read(self) -> Optional[Dict[str, Any]]:
        try:
            if not self.path.is_file() or self.path.stat().st_size > self.max_bytes:
                return None
            document = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, ValueError):
            return None
        if not isinstance(document, Mapping) or document.get("version") != SNAPSHOT_VERSION:
            return None
        try:
            written_at = float(document.get("written_at"))
        except (TypeError, ValueError):
            return None
        age_seconds = max(0, int(self.wall_clock() - written_at))
        if age_seconds >= self.stale_ttl_seconds:
            return None
        payload = self._validated_payload(document.get("payload"))
        if payload is None:
            return None
        payload["cache"] = {
            "hit": True,
            "age_seconds": age_seconds,
            "ttl_seconds": self.cache_ttl_seconds,
            "storage": "disk",
            "refreshing": False,
        }
        return {
            "payload": payload,
            "age_seconds": age_seconds,
            "stale": age_seconds >= self.cache_ttl_seconds,
        }

    def write(self, payload: Mapping[str, Any]) -> bool:
        validated = self._validated_payload(payload)
        if validated is None:
            return False
        document = {
            "version": SNAPSHOT_VERSION,
            "written_at": float(self.wall_clock()),
            "payload": validated,
        }
        try:
            encoded = json.dumps(
                document,
                ensure_ascii=False,
                separators=(",", ":"),
                sort_keys=True,
            ).encode("utf-8")
        except (TypeError, ValueError):
            return False
        if len(encoded) > self.max_bytes:
            return False
        temp_path = self.path.with_suffix(self.path.suffix + ".tmp")
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temp_path.write_bytes(encoded)
            temp_path.replace(self.path)
        except OSError:
            try:
                temp_path.unlink(missing_ok=True)
            except OSError:
                pass
            return False
        return True

    def _validated_payload(self, value: Any) -> Optional[Dict[str, Any]]:
        if not isinstance(value, Mapping):
            return None
        if set(value) - _PAYLOAD_KEYS:
            return None
        if value.get("ai_used") is not False or value.get("informational_only") is not True:
            return None
        if self._contains_sensitive_data(value):
            return None
        items = value.get("items")
        market_sources = value.get("market_sources", [])
        warnings = value.get("warnings")
        if not isinstance(items, list) or len(items) > 6:
            return None
        if not isinstance(market_sources, list) or len(market_sources) > 3:
            return None
        if not isinstance(warnings, list) or len(warnings) > 12:
            return None
        payload = copy.deepcopy(dict(value))
        cache = payload.get("cache")
        if not isinstance(cache, Mapping):
            return None
        payload["cache"] = {
            "hit": bool(cache.get("hit")),
            "age_seconds": max(0, int(cache.get("age_seconds") or 0)),
            "ttl_seconds": max(
                1,
                int(cache.get("ttl_seconds") or self.cache_ttl_seconds),
            ),
            "storage": (
                str(cache.get("storage"))
                if str(cache.get("storage")) in {"none", "memory", "disk"}
                else "memory"
            ),
            "refreshing": bool(cache.get("refreshing")),
        }
        return payload

    @classmethod
    def _contains_sensitive_data(cls, value: Any) -> bool:
        if isinstance(value, Mapping):
            for key, nested in value.items():
                normalized = str(key).strip().lower().replace("-", "_")
                if normalized in _FORBIDDEN_KEYS:
                    return True
                if cls._contains_sensitive_data(nested):
                    return True
            return False
        if isinstance(value, (list, tuple)):
            return any(cls._contains_sensitive_data(item) for item in value)
        return isinstance(value, str) and bool(_SECRET_VALUE.search(value))
