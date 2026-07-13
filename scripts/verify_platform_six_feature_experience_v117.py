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
    "DSA_PLATFORM_SIX_FEATURE_EXPERIENCE_V117_OK features=6 ollama=true "
    "markets=cn,hk,us guest_data=true investment_advice=false"
)
CAPABILITIES = (
    "kronos",
    "a_stock_data",
    "alphasift",
    "financial_services",
    "market_workspace",
    "market_pulse",
)
REQUIRED_FILES = (
    "src/services/kronos_runtime.py",
    "src/services/a_share_enrichment_service.py",
    "src/services/alphasift_service.py",
    "src/services/financial_research_workflow_service.py",
    "src/services/market_workspace_service.py",
    "src/services/ollama_runtime_service.py",
    "apps/dsa-web/src/pages/StockScreeningPage.tsx",
    "apps/dsa-web/src/pages/ResearchWorkflowsPage.tsx",
    "apps/dsa-web/src/pages/MarketWorkspacePage.tsx",
    "apps/dsa-web/src/components/market-workspace/MarketPulseV113.tsx",
    "apps/dsa-web/src/components/market-workspace/marketWorkspaceFormat.ts",
    "apps/dsa-web/src/components/screening/MarketScreeningCardV104.tsx",
    "apps/dsa-web/src/components/analysis/decisionJourneyModel.ts",
    "docs/superpowers/plans/2026-07-13-dsa-v117-six-feature-experience-closure.md",
)


@dataclass(frozen=True)
class CheckResult:
    check_id: str
    status: str
    details: dict = field(default_factory=dict)


def _check_files(root: Path) -> CheckResult:
    missing = [path for path in REQUIRED_FILES if not (root / path).exists()]
    return CheckResult("v117_required_files", "failed" if missing else "passed", {"missing": missing})


def _check_contract(root: Path) -> CheckResult:
    requirements = {
        "src/services/market_workspace_service.py": ("get_overview", "get_symbol", "ai_used"),
        "src/services/alphasift_service.py": ("snapshot_cache_freshness", "snapshot_cache_stale"),
        "src/services/ollama_runtime_service.py": ("max_concurrent", "ready"),
        "apps/dsa-web/src/pages/MarketWorkspacePage.tsx": (
            "overviewRequestId", "formatMarketWarning", "Information and data only. No investment advice.",
        ),
        "apps/dsa-web/src/pages/StockScreeningPage.tsx": ("dsa.alphasift.lastScreenResult.v1",),
        "apps/dsa-web/src/components/screening/MarketScreeningCardV104.tsx": (
            "market_snapshot", "Yahoo 公司资料",
        ),
        "apps/dsa-web/src/pages/HomePage.tsx": (
            "formatGeneratedTimestamp", "Range-watch preview", "TencentFetcher",
            "publicMarketHomeExpanded", "public-market-home-toggle",
            "platformAuthPanelExpanded", "platform-auth-panel-collapsed",
        ),
        "apps/dsa-web/src/components/analysis/decisionJourneyModel.ts": (
            "localizeSource", "formatTimestamp",
        ),
        "apps/dsa-web/src/hooks/useDashboardLifecycle.ts": ("streamEnabled",),
    }
    missing: list[str] = []
    for path, tokens in requirements.items():
        source = (root / path).read_text(encoding="utf-8", errors="replace") if (root / path).exists() else ""
        missing.extend(f"{path}:{token}" for token in tokens if token not in source)
    return CheckResult("v117_source_contract", "failed" if missing else "passed", {"missing": missing})


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


def run_v117_checks(*, project_root: Path = REPO_ROOT, run_subprocess: bool = True) -> list[CheckResult]:
    root = project_root.resolve()
    results = [_check_files(root), _check_contract(root)]
    if not run_subprocess:
        return results

    results.append(_run("v117_backend_tests", root, [sys.executable, "-m", "unittest",
        "tests.test_basic_query_no_ai",
        "tests.test_market_workspace_v113",
        "tests.test_alphasift_api",
        "tests.test_financial_research_workflow_service_v106",
        "tests.test_ollama_runtime_service_v107",
    ]))
    npm = shutil.which("npm.cmd") or shutil.which("npm") or "npm"
    frontend = root / "apps/dsa-web"
    results.append(_run("v117_frontend_tests", frontend, [npm, "test", "--",
        "src/pages/__tests__/HomePage.test.tsx",
        "src/pages/__tests__/MarketWorkspacePage.test.tsx",
        "src/pages/__tests__/StockScreeningPage.test.tsx",
        "src/pages/__tests__/ResearchWorkflowsPage.test.tsx",
        "src/components/market-home/__tests__/PublicMarketHomeV116.test.tsx",
        "src/components/screening/__tests__/MarketScreeningCardV104.test.tsx",
        "src/components/analysis/__tests__/decisionJourneyModel.test.ts",
        "src/hooks/__tests__/useDashboardLifecycle.test.tsx",
    ]))
    results.append(_run("v117_build", frontend, [npm, "run", "build"]))
    results.append(_run("v117_release_package", root, [sys.executable, "scripts/verify_platform_release_candidate_package.py"]))
    return results


def main() -> int:
    results = run_v117_checks()
    for result in results:
        print(f"[{'OK' if result.status == 'passed' else 'FAIL'}] {result.check_id}")
        print(f"  {json.dumps(result.details, ensure_ascii=False)}")
    if any(result.status == "failed" for result in results):
        print("DSA_PLATFORM_SIX_FEATURE_EXPERIENCE_V117_FAILED")
        return 1
    print(OK_MARKER)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
