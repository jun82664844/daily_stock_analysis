from __future__ import annotations

import hashlib
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _connect_readonly(path: Path) -> sqlite3.Connection:
    return sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)


def _integrity_check(path: Path) -> str:
    with _connect_readonly(path) as conn:
        row = conn.execute("PRAGMA integrity_check").fetchone()
    return str(row[0]) if row else "unknown"


def _table_counts(path: Path) -> dict[str, int]:
    with _connect_readonly(path) as conn:
        tables = [
            str(row[0])
            for row in conn.execute(
                "SELECT name FROM sqlite_schema WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
            ).fetchall()
        ]
        counts: dict[str, int] = {}
        for table in tables:
            quoted = '"' + table.replace('"', '""') + '"'
            counts[table] = int(conn.execute(f"SELECT COUNT(*) FROM {quoted}").fetchone()[0])
    return counts


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _payload(path: Path) -> dict[str, Any]:
    return {
        "path": str(path),
        "bytes": path.stat().st_size,
        "sha256": _sha256(path),
        "integrity_check": _integrity_check(path),
        "table_counts": _table_counts(path),
    }


def _safe_label(label: str | None) -> str:
    value = (label or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")).strip()
    safe = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "-" for ch in value)
    return safe[:80] or "backup"


def _copy_sqlite(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        raise FileExistsError(f"destination already exists: {destination}")
    with sqlite3.connect(source) as src_conn:
        with sqlite3.connect(destination) as dst_conn:
            src_conn.backup(dst_conn)


def run_sqlite_backup_restore_dry_run(
    database_path: str | Path,
    *,
    output_dir: str | Path,
    label: str | None = None,
) -> dict[str, Any]:
    """Create backup and restored SQLite copies without mutating the source DB."""

    source = Path(database_path).resolve()
    if not source.exists():
        raise FileNotFoundError(f"database does not exist: {source}")
    if not source.is_file():
        raise ValueError(f"database path is not a file: {source}")

    target_dir = Path(output_dir).resolve()
    target_dir.mkdir(parents=True, exist_ok=True)
    suffix = _safe_label(label)
    backup_path = target_dir / f"{source.stem}.{suffix}.backup.sqlite"
    restored_path = target_dir / f"{source.stem}.{suffix}.restored.sqlite"

    source_before = _payload(source)
    _copy_sqlite(source, backup_path)
    _copy_sqlite(backup_path, restored_path)
    source_after = _payload(source)
    backup = _payload(backup_path)
    restored = _payload(restored_path)

    return {
        "success": (
            source_before["integrity_check"] == "ok"
            and backup["integrity_check"] == "ok"
            and restored["integrity_check"] == "ok"
            and source_before["table_counts"] == restored["table_counts"]
            and source_before["sha256"] == source_after["sha256"]
        ),
        "mode": "sqlite_backup_restore_dry_run",
        "destructive": False,
        "ai_used": False,
        "source": source_after,
        "backup": backup,
        "restored": restored,
        "row_counts_match": source_before["table_counts"] == restored["table_counts"],
        "source_unchanged": source_before["sha256"] == source_after["sha256"],
    }
