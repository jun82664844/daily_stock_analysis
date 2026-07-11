from __future__ import annotations

import json
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Sequence


REPO_ROOT = Path(__file__).resolve().parents[1]
OK_MARKER = "DSA_PLATFORM_FAST_USEFUL_SCREENING_V105_OK"
REQUIRED_FILES = (
    "src/services/alphasift_screen_cache.py",
    "src/services/market_screening_brief.py",
    "src/services/alphasift_service.py",
    "api/v1/endpoints/alphasift.py",
    "tests/test_alphasift_screen_cache_v105.py",
    "tests/test_market_screening_brief.py",
    "apps/dsa-web/src/api/alphasift.ts",
    "apps/dsa-web/src/components/screening/screeningModelV104.ts",
    "apps/dsa-web/src/components/screening/MarketScreeningCardV104.tsx",
    "apps/dsa-web/src/pages/StockScreeningPage.tsx",
    "docs/superpowers/plans/2026-07-11-dsa-v105-fast-useful-market-screening.md",
    "scripts/verify_platform_fast_useful_screening_v105.py",
    "tests/test_platform_fast_useful_screening_v105_verifier.py",
)


@dataclass(frozen=True)
class CheckResult:
    check_id: str
    status: str
    details: dict = field(default_factory=dict)


def _check_files(root: Path) -> CheckResult:
    missing = [path for path in REQUIRED_FILES if not (root / path).exists()]
    return CheckResult("v105_required_files", "failed" if missing else "passed", {"missing": missing})


def _check_contract(root: Path) -> CheckResult:
    requirements = {
        "src/services/alphasift_screen_cache.py": ("inspect_snapshot_cache", "TRADING_CACHE_TTL_SECONDS", "force_refresh"),
        "src/services/alphasift_service.py": ("snapshot_cache_used", "screen_elapsed_ms", "prefer_snapshot_cache"),
        "src/services/market_screening_brief.py": ('"pe_ratio"', '"pb_ratio"', '"turnover_rate"', '"total_mv"'),
        "apps/dsa-web/src/pages/StockScreeningPage.tsx": ("filterAndSortScreeningCandidates", "强制刷新源数据", "快照：近期缓存"),
        "apps/dsa-web/src/components/screening/screeningModelV104.ts": ("filterAndSortScreeningCandidates", "pe_ratio", "liquidity"),
    }
    missing: list[str] = []
    for path, tokens in requirements.items():
        source = (root / path).read_text(encoding="utf-8", errors="replace") if (root / path).exists() else ""
        missing.extend(f"{path}:{token}" for token in tokens if token not in source)
    return CheckResult("v105_source_contract", "failed" if missing else "passed", {"missing": missing})


def _run(check_id: str, cwd: Path, command: Sequence[str]) -> CheckResult:
    completed = subprocess.run(list(command), cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    return CheckResult(
        check_id,
        "passed" if completed.returncode == 0 else "failed",
        {"returncode": completed.returncode, "stdout_tail": completed.stdout[-1000:], "stderr_tail": completed.stderr[-1000:]},
    )


def run_v105_checks(*, project_root: Path = REPO_ROOT, run_subprocess: bool = True) -> list[CheckResult]:
    root = project_root.resolve()
    results = [_check_files(root), _check_contract(root)]
    if not run_subprocess:
        return results
    results.append(_run(
        "v105_backend_tests",
        root,
        [sys.executable, "-m", "unittest", "tests.test_alphasift_screen_cache_v105", "tests.test_market_screening_brief", "tests.test_alphasift_api"],
    ))
    npm = shutil.which("npm.cmd") or shutil.which("npm") or "npm"
    results.append(_run(
        "v105_frontend_tests",
        root / "apps/dsa-web",
        [npm, "test", "--", "src/components/screening/__tests__/screeningModelV104.test.ts", "src/components/screening/__tests__/MarketScreeningCardV104.test.tsx", "src/api/__tests__/alphasift.test.ts", "src/pages/__tests__/StockScreeningPage.test.tsx"],
    ))
    return results


def main() -> int:
    results = run_v105_checks()
    for result in results:
        print(f"[{'OK' if result.status == 'passed' else 'FAIL'}] {result.check_id}")
        print(f"  {json.dumps(result.details, ensure_ascii=False)}")
    if any(result.status == "failed" for result in results):
        print("DSA_PLATFORM_FAST_USEFUL_SCREENING_V105_FAILED")
        return 1
    print(OK_MARKER)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
