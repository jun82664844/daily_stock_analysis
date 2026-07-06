from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.services.platform_backup import run_sqlite_backup_restore_dry_run


def _default_output_dir() -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return REPO_ROOT / "local" / "backups" / "dry-runs" / stamp


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run a non-destructive DSA SQLite backup/restore dry-run")
    parser.add_argument(
        "--database",
        default=os.getenv("DATABASE_PATH", ""),
        help="SQLite database path. Defaults to DATABASE_PATH.",
    )
    parser.add_argument(
        "--output-dir",
        default="",
        help="Directory for backup/restored copies. Defaults to local/backups/dry-runs/<timestamp>.",
    )
    parser.add_argument("--label", default="", help="Optional filename label")
    args = parser.parse_args(argv)

    if not args.database:
        print(json.dumps({"success": False, "error": "database_required"}, ensure_ascii=False))
        return 2

    output_dir = Path(args.output_dir).resolve() if args.output_dir else _default_output_dir()
    result = run_sqlite_backup_restore_dry_run(
        args.database,
        output_dir=output_dir,
        label=args.label or None,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result.get("success") else 1


if __name__ == "__main__":
    raise SystemExit(main())
