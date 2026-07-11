from __future__ import annotations

import json
import os
from datetime import datetime, time as daytime, timezone
from pathlib import Path
from typing import Any, Dict, Optional
from zoneinfo import ZoneInfo


TRADING_CACHE_TTL_SECONDS = 5 * 60
OFF_HOURS_CACHE_TTL_SECONDS = 6 * 60 * 60


def _parse_datetime(value: Any) -> Optional[datetime]:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def resolve_snapshot_cache_ttl_seconds(*, now: Optional[datetime] = None) -> int:
    override = str(os.getenv("DSA_ALPHASIFT_SCREEN_CACHE_TTL_SECONDS", "")).strip()
    if override:
        try:
            return max(0, int(float(override)))
        except ValueError:
            pass

    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    shanghai = current.astimezone(ZoneInfo("Asia/Shanghai"))
    in_session = (
        shanghai.weekday() < 5
        and daytime(9, 15) <= shanghai.time().replace(tzinfo=None) <= daytime(15, 30)
    )
    return TRADING_CACHE_TTL_SECONDS if in_session else OFF_HOURS_CACHE_TTL_SECONDS


def inspect_snapshot_cache(
    path: Path,
    *,
    now: Optional[datetime] = None,
    max_age_seconds: Optional[int] = None,
    force_refresh: bool = False,
) -> Dict[str, Any]:
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    current = current.astimezone(timezone.utc)
    ttl = resolve_snapshot_cache_ttl_seconds(now=current) if max_age_seconds is None else max(0, max_age_seconds)
    result: Dict[str, Any] = {
        "available": False,
        "use_cache": False,
        "reason": "missing",
        "path": str(path),
        "cached_at": None,
        "age_seconds": None,
        "max_age_seconds": ttl,
        "source": "",
        "row_count": 0,
        "force_refresh": bool(force_refresh),
    }
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        frame = payload.get("frame")
        columns = frame.get("columns") if isinstance(frame, dict) else None
        rows = frame.get("data") if isinstance(frame, dict) else None
        if payload.get("version") != 1 or not isinstance(columns, list) or not isinstance(rows, list) or not rows:
            raise ValueError("invalid snapshot cache schema")
        created_at = _parse_datetime(payload.get("created_at"))
        if created_at is None:
            created_at = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        result["reason"] = "invalid" if path.exists() else "missing"
        result["error"] = str(exc)
        return result

    age_seconds = max(0, int((current - created_at).total_seconds()))
    metadata = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
    result.update(
        {
            "available": True,
            "cached_at": created_at.isoformat().replace("+00:00", "Z"),
            "age_seconds": age_seconds,
            "source": str(metadata.get("snapshot_source") or "last_good_cache"),
            "row_count": len(rows),
        }
    )
    if force_refresh:
        result["reason"] = "force_refresh"
    elif ttl > 0 and age_seconds <= ttl:
        result["use_cache"] = True
        result["reason"] = "hit"
    else:
        result["reason"] = "expired"
    return result
