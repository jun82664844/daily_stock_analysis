from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Sequence


REPO_ROOT = Path(__file__).resolve().parents[1]
OK_MARKER = (
    "DSA_PLATFORM_FREE_DAILY_MARKET_WORKBENCH_V124_OK guest=true public_data=true "
    "ai_used=false market_clocks=true cross_market_timeline=true recent_research=true "
    "bilingual=true investment_advice=false"
)
REQUIRED_FILES = (
    "apps/dsa-web/src/components/market-home/DailyMarketWorkbenchV124.tsx",
    "apps/dsa-web/src/components/market-home/marketRecentV124.ts",
    "apps/dsa-web/src/components/market-home/PublicMarketHomeV116.tsx",
    "apps/dsa-web/src/components/market-home/__tests__/DailyMarketWorkbenchV124.test.tsx",
    "apps/dsa-web/src/components/market-home/__tests__/marketRecentV124.test.ts",
    "apps/dsa-web/src/components/market-home/__tests__/PublicMarketHomeV116.test.tsx",
    "tests/test_platform_free_daily_market_workbench_v124_verifier.py",
    "docs/superpowers/plans/2026-07-14-dsa-v124-free-daily-market-workbench.md",
)


@dataclass(frozen=True)
class CheckResult:
    check_id: str
    status: str
    details: dict = field(default_factory=dict)


def _source(root: Path, relative_path: str) -> str:
    path = root / relative_path
    return path.read_text(encoding="utf-8", errors="replace") if path.exists() else ""


def _check_files(root: Path) -> CheckResult:
    missing = [path for path in REQUIRED_FILES if not (root / path).exists()]
    return CheckResult("v124_required_files", "failed" if missing else "passed", {"missing": missing})


def _check_contract(root: Path) -> CheckResult:
    requirements = {
        "apps/dsa-web/src/components/market-home/DailyMarketWorkbenchV124.tsx": (
            "daily-market-workbench-v124",
            "今日市场工作台",
            "Daily market workbench",
            "跨市场今日时间线",
            "Cross-market timeline",
            "仅提供资讯和数据，不构成投资建议",
            "Information and data only; not investment advice",
            "MARKET_TIME_ZONES",
            "readRecentMarketSymbols",
            "clearRecentMarketSymbols",
        ),
        "apps/dsa-web/src/components/market-home/marketRecentV124.ts": (
            "dsa.public-market.recent-symbols.v124",
            "MAX_ITEMS = 6",
            "rememberRecentMarketSymbol",
            "RECENT_MARKET_SYMBOLS_EVENT",
        ),
        "apps/dsa-web/src/components/market-home/PublicMarketHomeV116.tsx": (
            "DailyMarketWorkbenchV124",
            "rememberRecentMarketSymbol(item)",
            "openMarketItem(item)",
        ),
        "apps/dsa-web/src/components/market-home/__tests__/DailyMarketWorkbenchV124.test.tsx": (
            "A股交易中",
            "US session unconfirmed",
            "清空最近查看",
            "unrelated-setting",
        ),
        "apps/dsa-web/src/components/market-home/__tests__/marketRecentV124.test.ts": (
            "deduplicates by symbol",
            "keeps six items",
            "damaged local data",
        ),
    }
    missing: list[str] = []
    for path, tokens in requirements.items():
        text = _source(root, path)
        missing.extend(f"{path}:{token}" for token in tokens if token not in text)
    return CheckResult("v124_source_contract", "failed" if missing else "passed", {"missing": missing})


def _check_safety_boundary(root: Path) -> CheckResult:
    paths = (
        "apps/dsa-web/src/components/market-home/DailyMarketWorkbenchV124.tsx",
        "apps/dsa-web/src/components/market-home/marketRecentV124.ts",
    )
    source = "\n".join(_source(root, path) for path in paths)
    violations: list[str] = []
    for token in ("analysisApi", "analyzeAsync", "apiKey", "SimpleModelPickerV112", "Kronos"):
        if token in source:
            violations.append(f"ai-or-key-invocation:{token}")
    if re.search(r"\bsk-[A-Za-z0-9._-]{8,}\b", source):
        violations.append("secret-like-key")
    for token in ("建议买入", "建议卖出", "目标价为", "仓位建议为", "预计收益"):
        if token in source:
            violations.append(f"advice-language:{token}")
    return CheckResult("v124_public_data_no_ai_boundary", "failed" if violations else "passed", {"violations": violations})


def _run(check_id: str, cwd: Path, command: Sequence[str]) -> CheckResult:
    completed = subprocess.run(
        list(command), cwd=cwd, capture_output=True, text=True,
        encoding="utf-8", errors="replace", check=False,
    )
    return CheckResult(check_id, "passed" if completed.returncode == 0 else "failed", {
        "returncode": completed.returncode,
        "stdout_tail": completed.stdout[-1800:],
        "stderr_tail": completed.stderr[-1800:],
    })


def run_v124_checks(*, project_root: Path = REPO_ROOT, run_subprocess: bool = True) -> list[CheckResult]:
    root = project_root.resolve()
    results = [_check_files(root), _check_contract(root), _check_safety_boundary(root)]
    if not run_subprocess:
        return results

    results.append(_run("v124_verifier_tests", root, [
        sys.executable, "-m", "unittest",
        "tests.test_platform_free_daily_market_workbench_v124_verifier",
        "tests.test_platform_release_candidate_package.PlatformReleaseCandidatePackageVerifierTestCase.test_v124_free_daily_market_workbench_is_part_of_release_package",
    ]))
    npm = shutil.which("npm.cmd") or shutil.which("npm") or "npm"
    frontend = root / "apps/dsa-web"
    results.append(_run("v124_frontend_tests", frontend, [
        npm, "test", "--", "--run",
        "src/components/market-home/__tests__/marketRecentV124.test.ts",
        "src/components/market-home/__tests__/DailyMarketWorkbenchV124.test.tsx",
        "src/components/market-home/__tests__/PublicMarketHomeV116.test.tsx",
        "src/pages/__tests__/HomePage.test.tsx",
    ]))
    results.append(_run("v124_build", frontend, [npm, "run", "build"]))
    results.append(_run("v124_release_package", root, [sys.executable, "scripts/verify_platform_release_candidate_package.py"]))
    return results


def main() -> int:
    results = run_v124_checks()
    for result in results:
        print(f"[{'OK' if result.status == 'passed' else 'FAIL'}] {result.check_id}")
        print(f"  {json.dumps(result.details, ensure_ascii=False)}")
    if any(result.status == "failed" for result in results):
        print("DSA_PLATFORM_FREE_DAILY_MARKET_WORKBENCH_V124_FAILED")
        return 1
    print(OK_MARKER)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
