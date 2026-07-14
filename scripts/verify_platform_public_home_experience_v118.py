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
    "DSA_PLATFORM_PUBLIC_HOME_EXPERIENCE_V118_OK markets=cn,hk,us public_news=true "
    "account_clickthrough=true mobile=true api_auto_run=false investment_advice=false"
)
REQUIRED_FILES = (
    "api/v1/schemas/market_workspace.py",
    "src/services/public_market_index_service.py",
    "src/services/public_market_news_service.py",
    "src/services/public_market_home_service.py",
    "tests/test_public_market_news_service_v118.py",
    "tests/test_public_market_index_service_v118.py",
    "tests/test_public_market_home_v116.py",
    "apps/dsa-web/src/api/marketWorkspace.ts",
    "apps/dsa-web/src/components/market-home/PublicMarketHomeV116.tsx",
    "apps/dsa-web/src/components/market-home/__tests__/PublicMarketHomeV116.test.tsx",
    "apps/dsa-web/src/pages/HomePage.tsx",
    "apps/dsa-web/src/pages/AccountPage.tsx",
    "apps/dsa-web/src/stores/stockPoolStore.ts",
    "apps/dsa-web/src/pages/__tests__/HomePage.test.tsx",
    "apps/dsa-web/src/pages/__tests__/AccountPage.test.tsx",
    "apps/dsa-web/src/stores/__tests__/stockPoolStore.test.ts",
    "docs/superpowers/plans/2026-07-13-dsa-v118-public-home-information-architecture.md",
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
    return CheckResult("v118_required_files", "failed" if missing else "passed", {"missing": missing})


def _check_contract(root: Path) -> CheckResult:
    requirements = {
        "api/v1/schemas/market_workspace.py": ("headlines: List[MarketHeadline]",),
        "src/services/public_market_home_service.py": ('MARKETS = ("cn", "hk", "us")', '"headlines"', '"ai_used": False'),
        "src/services/public_market_news_service.py": (
            "_MARKET_SOURCES",
            "public_newsnow_",
            "PLATFORM_PUBLIC_MARKET_NEWS_CACHE_TTL_SECONDS",
            "PLATFORM_PUBLIC_MARKET_NEWS_TIMEOUT_SECONDS",
        ),
        "src/services/public_market_index_service.py": (
            "_INDEX_DEFINITIONS",
            "yahoo_public_index",
            "PLATFORM_PUBLIC_MARKET_INDEX_CACHE_TTL_SECONDS",
            "PLATFORM_PUBLIC_MARKET_INDEX_TIMEOUT_SECONDS",
        ),
        "apps/dsa-web/src/components/market-home/PublicMarketHomeV116.tsx": (
            "public-home-market-dashboard-v118",
            "public-home-index-strip",
            "Market information",
            "Quote-derived",
            "No investment advice.",
            "不构成投资建议",
        ),
        "apps/dsa-web/src/pages/HomePage.tsx": (
            "platform-personal-workspace-toggle",
            "Account and models",
            "账户与模型",
            "home-analysis-workspace",
            "!publicMarketHome",
        ),
        "apps/dsa-web/src/stores/stockPoolStore.ts": (
            "loadInitialHistory: async () =>",
            "await fetchHistory(get, set, { reset: true })",
        ),
        "apps/dsa-web/src/pages/AccountPage.tsx": ("SimpleModelPickerV112", "dsa.modelOptionId", "分析模型"),
    }
    missing: list[str] = []
    for path, tokens in requirements.items():
        text = _source(root, path)
        missing.extend(f"{path}:{token}" for token in tokens if token not in text)
    return CheckResult("v118_source_contract", "failed" if missing else "passed", {"missing": missing})


def _check_public_home_boundary(root: Path) -> CheckResult:
    component = _source(root, "apps/dsa-web/src/components/market-home/PublicMarketHomeV116.tsx")
    public_services = "\n".join((
        _source(root, "src/services/public_market_index_service.py"),
        _source(root, "src/services/public_market_news_service.py"),
    ))
    violations = []
    for token in ("analysisApi", "analyzeAsync", "Kronos", "SimpleModelPickerV112", "API Key"):
        if token in component:
            violations.append(token)
    for token in ("litellm", "api_key", "ollama", "kronos"):
        if token in public_services.lower():
            violations.append(f"public-service:{token}")
    if re.search(r"\bsk-[A-Za-z0-9._-]{8,}\b", component):
        violations.append("secret-like-key")
    return CheckResult(
        "v118_public_home_no_api_auto_run",
        "failed" if violations else "passed",
        {"violations": violations},
    )


def _run(check_id: str, cwd: Path, command: Sequence[str]) -> CheckResult:
    completed = subprocess.run(
        list(command), cwd=cwd, capture_output=True, text=True,
        encoding="utf-8", errors="replace", check=False,
    )
    return CheckResult(check_id, "passed" if completed.returncode == 0 else "failed", {
        "returncode": completed.returncode,
        "stdout_tail": completed.stdout[-1600:],
        "stderr_tail": completed.stderr[-1600:],
    })


def run_v118_checks(*, project_root: Path = REPO_ROOT, run_subprocess: bool = True) -> list[CheckResult]:
    root = project_root.resolve()
    results = [_check_files(root), _check_contract(root), _check_public_home_boundary(root)]
    if not run_subprocess:
        return results

    results.append(_run("v118_backend_tests", root, [
        sys.executable, "-m", "unittest",
        "tests.test_public_market_index_service_v118",
        "tests.test_public_market_news_service_v118",
        "tests.test_public_market_home_v116",
        "tests.test_platform_public_home_experience_v118_verifier",
    ]))
    npm = shutil.which("npm.cmd") or shutil.which("npm") or "npm"
    frontend = root / "apps/dsa-web"
    results.append(_run("v118_frontend_tests", frontend, [
        npm, "test", "--", "--run",
        "src/components/market-home/__tests__/PublicMarketHomeV116.test.tsx",
        "src/pages/__tests__/HomePage.test.tsx",
        "src/pages/__tests__/AccountPage.test.tsx",
        "src/stores/__tests__/stockPoolStore.test.ts",
    ]))
    results.append(_run("v118_build", frontend, [npm, "run", "build"]))
    results.append(_run("v118_release_package", root, [sys.executable, "scripts/verify_platform_release_candidate_package.py"]))
    return results


def main() -> int:
    results = run_v118_checks()
    for result in results:
        print(f"[{'OK' if result.status == 'passed' else 'FAIL'}] {result.check_id}")
        print(f"  {json.dumps(result.details, ensure_ascii=False)}")
    if any(result.status == "failed" for result in results):
        print("DSA_PLATFORM_PUBLIC_HOME_EXPERIENCE_V118_FAILED")
        return 1
    print(OK_MARKER)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
