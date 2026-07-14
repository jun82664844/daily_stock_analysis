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
    "DSA_PLATFORM_DYNAMIC_MARKET_HOME_V119_OK markets=cn,hk,us "
    "rankings=active,gainers,losers sectors=cn public_data=true ai_used=false "
    "fixed_pool=false investment_advice=false"
)
REQUIRED_FILES = (
    "api/v1/schemas/market_workspace.py",
    "api/v1/endpoints/market_workspace.py",
    "src/services/public_market_ranking_service.py",
    "src/services/public_market_home_service.py",
    "tests/test_public_market_ranking_service_v119.py",
    "tests/test_public_market_home_v116.py",
    "apps/dsa-web/src/api/marketWorkspace.ts",
    "apps/dsa-web/src/api/__tests__/marketWorkspace.test.ts",
    "apps/dsa-web/src/components/market-home/PublicMarketHomeV116.tsx",
    "apps/dsa-web/src/components/market-home/__tests__/PublicMarketHomeV116.test.tsx",
    "apps/dsa-web/src/pages/HomePage.tsx",
    "apps/dsa-web/src/pages/__tests__/HomePage.test.tsx",
    "docs/superpowers/plans/2026-07-14-dsa-v119-dynamic-market-home.md",
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
    return CheckResult("v119_required_files", "failed" if missing else "passed", {"missing": missing})


def _check_contract(root: Path) -> CheckResult:
    requirements = {
        "api/v1/schemas/market_workspace.py": (
            "most_active: List[MarketSecurityItem]",
            "gainers: List[MarketSecurityItem]",
            "losers: List[MarketSecurityItem]",
            "sector_highlights: List[MarketSectorItem]",
            'Literal["configured_universe", "market_wide", "unavailable"]',
        ),
        "src/services/public_market_ranking_service.py": (
            "Market_Center.getHQNodeData",
            "Market_Center.getHKStockData",
            "finance/screener/predefined/saved",
            "newSinaHy.php",
            "PLATFORM_PUBLIC_MARKET_RANKING_CACHE_TTL_SECONDS",
            "PLATFORM_PUBLIC_MARKET_RANKING_STALE_TTL_SECONDS",
            '"ai_used": False',
        ),
        "src/services/public_market_home_service.py": (
            "ranking_loader",
            'PLATFORM_PUBLIC_MARKET_HOME_TIMEOUT_SECONDS", "5.5"',
            '"ranking_scope": "market_wide" if has_market_rankings else "unavailable"',
            '"attention": most_active',
            'warnings.append("market_rankings_unavailable")',
            'section.get("ranking_scope") == "market_wide"',
        ),
        "api/v1/endpoints/market_workspace.py": (
            "PublicMarketRankingService",
            'market_symbols={"cn": (), "hk": (), "us": ()}',
            "ranking_loader=_public_market_ranking_service.load",
        ),
        "apps/dsa-web/src/components/market-home/PublicMarketHomeV116.tsx": (
            "public-home-dynamic-v119",
            "Market-wide public rankings",
            "全市场公开榜单",
            "mostActive",
            "gainers",
            "losers",
            "sectorHighlights",
            "No investment advice.",
            "不构成投资建议",
        ),
    }
    missing: list[str] = []
    for path, tokens in requirements.items():
        text = _source(root, path)
        missing.extend(f"{path}:{token}" for token in tokens if token not in text)
    return CheckResult("v119_source_contract", "failed" if missing else "passed", {"missing": missing})


def _check_public_data_boundary(root: Path) -> CheckResult:
    service = _source(root, "src/services/public_market_ranking_service.py")
    component = _source(root, "apps/dsa-web/src/components/market-home/PublicMarketHomeV116.tsx")
    violations: list[str] = []
    for token in ("litellm", "ollama", "kronos", "analysisapi", "analyzeasync", "api_key"):
        if token in service.lower():
            violations.append(f"service:{token}")
    for token in ("analysisApi", "analyzeAsync", "Kronos", "SimpleModelPickerV112", "API Key"):
        if token in component:
            violations.append(f"component:{token}")
    if "600519.SH" in service or "AAPL" in service:
        violations.append("fixed-symbol-in-ranking-service")
    if re.search(r"\bsk-[A-Za-z0-9._-]{8,}\b", service + component):
        violations.append("secret-like-key")
    return CheckResult("v119_public_data_no_ai_or_fixed_pool", "failed" if violations else "passed", {"violations": violations})


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


def run_v119_checks(*, project_root: Path = REPO_ROOT, run_subprocess: bool = True) -> list[CheckResult]:
    root = project_root.resolve()
    results = [_check_files(root), _check_contract(root), _check_public_data_boundary(root)]
    if not run_subprocess:
        return results

    results.append(_run("v119_backend_tests", root, [
        sys.executable, "-m", "unittest",
        "tests.test_public_market_ranking_service_v119",
        "tests.test_public_market_home_v116",
        "tests.test_platform_dynamic_market_home_v119_verifier",
    ]))
    npm = shutil.which("npm.cmd") or shutil.which("npm") or "npm"
    frontend = root / "apps/dsa-web"
    results.append(_run("v119_frontend_tests", frontend, [
        npm, "test", "--", "--run",
        "src/api/__tests__/marketWorkspace.test.ts",
        "src/components/market-home/__tests__/PublicMarketHomeV116.test.tsx",
        "src/pages/__tests__/HomePage.test.tsx",
    ]))
    results.append(_run("v119_build", frontend, [npm, "run", "build"]))
    results.append(_run("v119_release_package", root, [sys.executable, "scripts/verify_platform_release_candidate_package.py"]))
    return results


def main() -> int:
    results = run_v119_checks()
    for result in results:
        print(f"[{'OK' if result.status == 'passed' else 'FAIL'}] {result.check_id}")
        print(f"  {json.dumps(result.details, ensure_ascii=False)}")
    if any(result.status == "failed" for result in results):
        print("DSA_PLATFORM_DYNAMIC_MARKET_HOME_V119_FAILED")
        return 1
    print(OK_MARKER)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
