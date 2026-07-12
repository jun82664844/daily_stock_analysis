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
    "DSA_PLATFORM_MARKET_WORKSPACE_V113_OK markets=cn,hk,us guest=true "
    "watchlist=true alerts=true ai_required=false agpl_code_copied=false"
)
REQUIRED_FILES = (
    "api/v1/endpoints/market_workspace.py",
    "api/v1/schemas/market_workspace.py",
    "src/services/market_workspace_service.py",
    "src/services/market_search_service.py",
    "src/services/market_daily_brief_service.py",
    "tests/test_market_workspace_v113.py",
    "tests/test_market_search_v113.py",
    "tests/test_market_daily_brief_v113.py",
    "apps/dsa-web/src/api/marketWorkspace.ts",
    "apps/dsa-web/src/api/__tests__/marketWorkspace.test.ts",
    "apps/dsa-web/src/pages/MarketWorkspacePage.tsx",
    "apps/dsa-web/src/pages/__tests__/MarketWorkspacePage.test.tsx",
    "apps/dsa-web/src/components/market-workspace/GlobalStockCommandV113.tsx",
    "apps/dsa-web/src/components/market-workspace/MarketPulseV113.tsx",
    "apps/dsa-web/src/components/market-workspace/MarketHeatmapV113.tsx",
    "apps/dsa-web/src/components/market-workspace/MarketMoversV113.tsx",
    "apps/dsa-web/src/components/market-workspace/MarketNewsTimelineV113.tsx",
    "apps/dsa-web/src/components/market-workspace/SymbolWorkspaceV113.tsx",
    "apps/dsa-web/src/components/market-workspace/WatchlistBriefV113.tsx",
    "docs/superpowers/plans/2026-07-12-dsa-v113-openstock-inspired-market-workspace.md",
)


@dataclass(frozen=True)
class CheckResult:
    check_id: str
    status: str
    details: dict = field(default_factory=dict)


def _check_files(root: Path) -> CheckResult:
    missing = [path for path in REQUIRED_FILES if not (root / path).exists()]
    return CheckResult("v113_required_files", "failed" if missing else "passed", {"missing": missing})


def _check_contract(root: Path) -> CheckResult:
    requirements = {
        "src/services/market_workspace_service.py": (
            "PLATFORM_MARKET_WORKSPACE_OVERVIEW_TIMEOUT_SECONDS",
            "get_quote_card",
            "market_symbol_timeout",
            '"ai_used": False',
        ),
        "api/v1/endpoints/market_workspace.py": (
            'pattern="^(cn|hk|us)$"',
            '"/daily-brief"',
            "platform_identity_from_request",
        ),
        "apps/dsa-web/src/api/marketWorkspace.ts": (
            "/api/v1/market-workspace/overview",
            "/api/v1/market-workspace/search",
            "/api/v1/market-workspace/symbol/",
            "/api/v1/market-workspace/daily-brief",
        ),
        "apps/dsa-web/src/pages/MarketWorkspacePage.tsx": (
            "key={overview.market}",
            "addWatchlistItem",
            "saveWatchlistAlertRule",
            "不提供投资建议",
        ),
    }
    missing: list[str] = []
    for path, tokens in requirements.items():
        source = (root / path).read_text(encoding="utf-8", errors="replace") if (root / path).exists() else ""
        missing.extend(f"{path}:{token}" for token in tokens if token not in source)
    return CheckResult("v113_source_contract", "failed" if missing else "passed", {"missing": missing})


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


def run_v113_checks(*, project_root: Path = REPO_ROOT, run_subprocess: bool = True) -> list[CheckResult]:
    root = project_root.resolve()
    results = [_check_files(root), _check_contract(root)]
    if not run_subprocess:
        return results
    results.append(_run(
        "v113_backend_tests",
        root,
        [
            sys.executable,
            "-m",
            "unittest",
            "tests.test_market_workspace_v113",
            "tests.test_market_search_v113",
            "tests.test_market_daily_brief_v113",
        ],
    ))
    npm = shutil.which("npm.cmd") or shutil.which("npm") or "npm"
    results.append(_run(
        "v113_frontend_tests",
        root / "apps/dsa-web",
        [
            npm,
            "test",
            "--",
            "--run",
            "src/api/__tests__/marketWorkspace.test.ts",
            "src/pages/__tests__/MarketWorkspacePage.test.tsx",
        ],
    ))
    return results


def main() -> int:
    results = run_v113_checks()
    for result in results:
        print(f"[{'OK' if result.status == 'passed' else 'FAIL'}] {result.check_id}")
        print(f"  {json.dumps(result.details, ensure_ascii=False)}")
    if any(result.status == "failed" for result in results):
        print("DSA_PLATFORM_MARKET_WORKSPACE_V113_FAILED")
        return 1
    print(OK_MARKER)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
