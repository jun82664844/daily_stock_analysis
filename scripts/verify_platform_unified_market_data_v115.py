from __future__ import annotations

import json
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Sequence


REPO_ROOT = Path(__file__).resolve().parents[1]
OK_MARKER = (
    "DSA_PLATFORM_UNIFIED_MARKET_DATA_V115_OK canonical_snapshot=true "
    "source_arbitration=true deduplication=true no_averaging=true ai_required=false"
)
REQUIRED_FILES = (
    "src/services/market_data_contract.py",
    "src/services/basic_query_service.py",
    "api/v1/schemas/basic_query.py",
    "tests/test_market_data_contract_v115.py",
    "apps/dsa-web/src/api/stocks.ts",
    "apps/dsa-web/src/pages/HomePage.tsx",
    "apps/dsa-web/src/pages/__tests__/HomePage.test.tsx",
    "docs/superpowers/plans/2026-07-12-dsa-v115-unified-market-data-contract.md",
)


@dataclass(frozen=True)
class CheckResult:
    check_id: str
    status: str
    details: dict = field(default_factory=dict)


def _check_files(root: Path) -> CheckResult:
    missing = [path for path in REQUIRED_FILES if not (root / path).exists()]
    return CheckResult("v115_required_files", "failed" if missing else "passed", {"missing": missing})


def _check_contract(root: Path) -> CheckResult:
    requirements = {
        "src/services/market_data_contract.py": (
            "freshness_then_priority_then_observed_at",
            '"no_averaging": True',
            "deduplicate_records",
            "build_snapshot_contract",
        ),
        "src/services/basic_query_service.py": (
            "deduplicate_snapshot_intelligence",
            '"canonical_data": canonical_data',
        ),
        "apps/dsa-web/src/pages/HomePage.tsx": (
            "统一事实快照",
            "冲突数据不取平均值",
        ),
        "api/v1/schemas/basic_query.py": (
            "BasicCanonicalDataPayload",
            "informational_only",
            "ai_used",
        ),
    }
    missing: list[str] = []
    for path, tokens in requirements.items():
        source = (root / path).read_text(encoding="utf-8", errors="replace") if (root / path).exists() else ""
        missing.extend(f"{path}:{token}" for token in tokens if token not in source)
    return CheckResult("v115_source_contract", "failed" if missing else "passed", {"missing": missing})


def _run(check_id: str, cwd: Path, command: Sequence[str]) -> CheckResult:
    completed = subprocess.run(
        list(command),
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    return CheckResult(
        check_id,
        "passed" if completed.returncode == 0 else "failed",
        {
            "returncode": completed.returncode,
            "stdout_tail": completed.stdout[-1200:],
            "stderr_tail": completed.stderr[-1200:],
        },
    )


def run_v115_checks(*, project_root: Path = REPO_ROOT, run_subprocess: bool = True) -> list[CheckResult]:
    root = project_root.resolve()
    results = [_check_files(root), _check_contract(root)]
    if not run_subprocess:
        return results
    results.append(_run(
        "v115_backend_tests",
        root,
        [sys.executable, "-m", "unittest", "tests.test_market_data_contract_v115"],
    ))
    npm = shutil.which("npm.cmd") or shutil.which("npm") or "npm"
    results.append(_run(
        "v115_frontend_tests",
        root / "apps/dsa-web",
        [npm, "test", "--", "--run", "src/pages/__tests__/HomePage.test.tsx"],
    ))
    return results


def main() -> int:
    results = run_v115_checks()
    for result in results:
        print(f"[{'OK' if result.status == 'passed' else 'FAIL'}] {result.check_id}")
        print(f"  {json.dumps(result.details, ensure_ascii=False)}")
    if any(result.status == "failed" for result in results):
        print("DSA_PLATFORM_UNIFIED_MARKET_DATA_V115_FAILED")
        return 1
    print(OK_MARKER)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
