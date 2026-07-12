from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Sequence


REPO_ROOT = Path(__file__).resolve().parents[1]
OK_MARKER = "DSA_PLATFORM_A_STOCK_DATA_LIVE_V109_OK"
REQUIRED_FILES = (
    "src/services/a_share_enrichment_service.py",
    "tests/test_a_share_enrichment_service.py",
    "docs/superpowers/plans/2026-07-12-dsa-v109-a-stock-data-live-channels.md",
    "external/a-stock-data/SKILL.md",
)
MARKERS = (
    "_fetch_eastmoney_daily_fund_flow",
    "A_STOCK_DATA_EASTMONEY_MIN_INTERVAL_SEC",
    "recent_20_trading_days",
    "a_stock_data_skill_adapter",
    "not investment advice",
)


def static_checks(root: Path) -> dict:
    missing_files = [item for item in REQUIRED_FILES if not (root / item).exists()]
    texts = []
    for item in REQUIRED_FILES:
        path = root / item
        if path.exists():
            texts.append(path.read_text(encoding="utf-8", errors="replace"))
    combined = "\n".join(texts).lower()
    missing_markers = [item for item in MARKERS if item.lower() not in combined]
    return {"passed": not missing_files and not missing_markers, "missing_files": missing_files, "missing_markers": missing_markers}


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--python-exe", default=sys.executable)
    parser.add_argument("--skip-tests", action="store_true")
    args = parser.parse_args(argv)
    checks = {"static": static_checks(REPO_ROOT)}
    if not args.skip_tests:
        completed = subprocess.run(
            [args.python_exe, "-m", "unittest", "tests.test_a_share_enrichment_service"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
            env={**os.environ, "A_STOCK_DATA_HTTP_ENABLED": "false", "A_STOCK_DATA_SOURCE_MODE": "poc"},
        )
        checks["tests"] = {"passed": completed.returncode == 0, "output_tail": (completed.stdout + completed.stderr)[-1200:]}
    print(json.dumps(checks, ensure_ascii=False, indent=2))
    passed = all(item["passed"] for item in checks.values())
    if passed:
        print(OK_MARKER)
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
