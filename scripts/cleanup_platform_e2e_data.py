# -*- coding: utf-8 -*-
"""Dry-run cleanup helper for local platform E2E test data."""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from sqlalchemy import create_engine, delete, func, select
from sqlalchemy.orm import sessionmaker

from src.storage import (
    AnalysisHistory,
    PlatformAuditEvent,
    PlatformUsageEvent,
    PlatformUser,
    PlatformUserApiKey,
)


@dataclass(frozen=True)
class E2ECleanupPlan:
    database_path: str
    email_prefix: str
    dry_run: bool
    matched_users: int
    api_keys: int
    usage_events: int
    audit_events: int
    analysis_history: int
    deleted_users: int = 0
    deleted_api_keys: int = 0
    deleted_usage_events: int = 0
    deleted_audit_events: int = 0
    deleted_analysis_history: int = 0


def _resolve_database_path(database_path: str | os.PathLike[str] | None) -> Path:
    return Path(database_path or os.getenv("DATABASE_PATH", "./data/stock_analysis.db")).resolve()


def _validate_e2e_prefix(email_prefix: str) -> str:
    prefix = (email_prefix or "").strip().lower()
    if not prefix.startswith("e2e+"):
        raise ValueError("E2E cleanup is limited to email prefixes starting with 'e2e+'")
    if any(ch in prefix for ch in {"%", "_", "*"}):
        raise ValueError("E2E cleanup prefix must not contain wildcard characters")
    return prefix


def _count(session, model, condition) -> int:
    return int(session.execute(select(func.count()).select_from(model).where(condition)).scalar_one())


def _rowcount(result) -> int:
    value = getattr(result, "rowcount", 0)
    return int(value or 0)


def collect_e2e_cleanup_plan(
    *,
    database_path: str | os.PathLike[str] | None = None,
    email_prefix: str = "e2e+",
    execute: bool = False,
) -> E2ECleanupPlan:
    """Collect or execute cleanup for local E2E accounts only.

    The default is a dry-run. Execution is still limited to platform users whose
    email begins with the validated E2E prefix.
    """

    prefix = _validate_e2e_prefix(email_prefix)
    db_path = _resolve_database_path(database_path)
    engine = create_engine(f"sqlite:///{db_path}")
    SessionLocal = sessionmaker(bind=engine)

    with SessionLocal() as session:
        users = list(
            session.execute(
                select(PlatformUser.id).where(func.lower(PlatformUser.email).like(f"{prefix}%"))
            ).scalars()
        )
        user_ids = [int(user_id) for user_id in users]
        if user_ids:
            api_key_condition = PlatformUserApiKey.user_id.in_(user_ids)
            usage_condition = PlatformUsageEvent.user_id.in_(user_ids)
            audit_condition = PlatformAuditEvent.user_id.in_(user_ids)
            history_condition = AnalysisHistory.platform_user_id.in_(user_ids)
            user_condition = PlatformUser.id.in_(user_ids)
            api_keys = _count(session, PlatformUserApiKey, api_key_condition)
            usage_events = _count(session, PlatformUsageEvent, usage_condition)
            audit_events = _count(session, PlatformAuditEvent, audit_condition)
            analysis_history = _count(session, AnalysisHistory, history_condition)
        else:
            api_key_condition = usage_condition = audit_condition = history_condition = user_condition = None
            api_keys = usage_events = audit_events = analysis_history = 0

        deleted = {
            "deleted_api_keys": 0,
            "deleted_usage_events": 0,
            "deleted_audit_events": 0,
            "deleted_analysis_history": 0,
            "deleted_users": 0,
        }
        if execute and user_ids:
            deleted["deleted_analysis_history"] = _rowcount(session.execute(delete(AnalysisHistory).where(history_condition)))
            deleted["deleted_api_keys"] = _rowcount(session.execute(delete(PlatformUserApiKey).where(api_key_condition)))
            deleted["deleted_usage_events"] = _rowcount(session.execute(delete(PlatformUsageEvent).where(usage_condition)))
            deleted["deleted_audit_events"] = _rowcount(session.execute(delete(PlatformAuditEvent).where(audit_condition)))
            deleted["deleted_users"] = _rowcount(session.execute(delete(PlatformUser).where(user_condition)))
            session.commit()

        return E2ECleanupPlan(
            database_path=str(db_path),
            email_prefix=prefix,
            dry_run=not execute,
            matched_users=len(user_ids),
            api_keys=api_keys,
            usage_events=usage_events,
            audit_events=audit_events,
            analysis_history=analysis_history,
            **deleted,
        )


def _format_summary(plan: E2ECleanupPlan) -> str:
    mode = "DRY RUN" if plan.dry_run else "EXECUTED"
    return (
        f"{mode}: matched_users={plan.matched_users}, api_keys={plan.api_keys}, "
        f"usage_events={plan.usage_events}, audit_events={plan.audit_events}, "
        f"analysis_history={plan.analysis_history}"
    )


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Dry-run cleanup for DSA platform E2E test data.")
    parser.add_argument("--database-path", default=None)
    parser.add_argument("--email-prefix", default="e2e+")
    parser.add_argument("--execute", action="store_true", help="Delete matched E2E rows. Defaults to dry-run.")
    parser.add_argument("--json", action="store_true", help="Print JSON output.")
    args = parser.parse_args(list(argv) if argv is not None else None)

    plan = collect_e2e_cleanup_plan(
        database_path=args.database_path,
        email_prefix=args.email_prefix,
        execute=bool(args.execute),
    )
    if args.json:
        print(json.dumps(asdict(plan), ensure_ascii=False, indent=2))
    else:
        print(_format_summary(plan))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
