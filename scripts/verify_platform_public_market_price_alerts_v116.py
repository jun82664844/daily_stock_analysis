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
    "DSA_PLATFORM_PUBLIC_MARKET_PRICE_ALERTS_V116_OK markets=cn,hk,us guest_home=true "
    "exact_price_alerts=true background_monitor=true private_events=true ai_required=false realtime_claim=false"
)
REQUIRED_FILES = (
    "src/services/public_market_home_service.py",
    "src/services/platform_price_alert_worker.py",
    "tests/test_public_market_home_v116.py",
    "tests/test_platform_price_alert_worker_v116.py",
    "apps/dsa-web/src/components/market-home/PublicMarketHomeV116.tsx",
    "apps/dsa-web/src/components/market-home/__tests__/PublicMarketHomeV116.test.tsx",
    "apps/dsa-web/src/components/alerts/PriceAlertFormV116.tsx",
    "apps/dsa-web/src/components/alerts/PriceAlertInboxV116.tsx",
    "apps/dsa-web/e2e/public-market-home-price-alerts-v116.spec.ts",
    "docs/superpowers/plans/2026-07-13-dsa-v116-public-market-home-and-price-alerts.md",
)
PROHIBITED_COPY = ("实时股价", "real-time price", "全市场热门推荐")


@dataclass(frozen=True)
class CheckResult:
    check_id: str
    status: str
    details: dict = field(default_factory=dict)


def _check_files(root: Path) -> CheckResult:
    missing = [path for path in REQUIRED_FILES if not (root / path).exists()]
    return CheckResult("v116_required_files", "failed" if missing else "passed", {"missing": missing})


def _check_contract(root: Path) -> CheckResult:
    requirements = {
        "src/services/public_market_home_service.py": (
            'MARKETS = ("cn", "hk", "us")', "configured_universe", "latest_available", '"ai_used": False',
        ),
        "src/services/platform_price_alert_worker.py": ("previous < threshold <= price", "freshness != \"fresh\""),
        "src/platform_watchlist_automation.py": ("price_above", "price_below", "read_at", "price_monitor"),
        "api/v1/endpoints/platform.py": ("/watchlist/alert-events", "/watchlist/alert-events/read-all"),
        "apps/dsa-web/src/pages/HomePage.tsx": ("dsa_v116_pending_price_alert", "注册后每周赠送 5 次快速分析及 1 次深度分析"),
    }
    missing: list[str] = []
    for path, tokens in requirements.items():
        source = (root / path).read_text(encoding="utf-8", errors="replace") if (root / path).exists() else ""
        missing.extend(f"{path}:{token}" for token in tokens if token not in source)
    return CheckResult("v116_source_contract", "failed" if missing else "passed", {"missing": missing})


def _check_copy(root: Path) -> CheckResult:
    targets = (
        "apps/dsa-web/src/components/market-home/PublicMarketHomeV116.tsx",
        "apps/dsa-web/src/components/alerts/PriceAlertFormV116.tsx",
        "apps/dsa-web/src/components/alerts/PriceAlertInboxV116.tsx",
    )
    hits: list[str] = []
    for path in targets:
        source = (root / path).read_text(encoding="utf-8", errors="replace").lower() if (root / path).exists() else ""
        for phrase in PROHIBITED_COPY:
            if phrase.lower() in source:
                hits.append(f"{path}:{phrase}")
    return CheckResult("v116_prohibited_claims", "failed" if hits else "passed", {"hits": hits})


def _check_secrets(root: Path) -> CheckResult:
    patterns = (re.compile(r"\bsk-[A-Za-z0-9._-]{12,}\b"), re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"))
    hits: list[str] = []
    for rel_path in REQUIRED_FILES:
        path = root / rel_path
        if not path.exists() or path.suffix.lower() in {".png", ".jpg"}:
            continue
        source = path.read_text(encoding="utf-8", errors="replace")
        if any(pattern.search(source) for pattern in patterns):
            hits.append(rel_path)
    return CheckResult("v116_secret_scan", "failed" if hits else "passed", {"hits": hits})


def _run(check_id: str, cwd: Path, command: Sequence[str]) -> CheckResult:
    completed = subprocess.run(list(command), cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace", check=False)
    return CheckResult(check_id, "passed" if completed.returncode == 0 else "failed", {
        "returncode": completed.returncode,
        "stdout_tail": completed.stdout[-1600:],
        "stderr_tail": completed.stderr[-1600:],
    })


def run_v116_checks(*, project_root: Path = REPO_ROOT, run_subprocess: bool = True) -> list[CheckResult]:
    root = project_root.resolve()
    results = [_check_files(root), _check_contract(root), _check_copy(root), _check_secrets(root)]
    if not run_subprocess:
        return results
    results.append(_run("v116_backend_tests", root, [sys.executable, "-m", "unittest",
        "tests.test_public_market_home_v116", "tests.test_platform_price_alert_worker_v116",
        "tests.test_platform_watchlist_alert_loop_v100", "tests.test_market_workspace_v113"]))
    npm = shutil.which("npm.cmd") or shutil.which("npm") or "npm"
    frontend = root / "apps/dsa-web"
    results.append(_run("v116_frontend_tests", frontend, [npm, "test", "--",
        "src/components/market-home", "src/components/alerts", "src/components/layout/__tests__/ShellHeader.test.tsx",
        "src/pages/__tests__/HomePage.test.tsx", "src/pages/__tests__/MarketWorkspacePage.test.tsx",
        "src/api/__tests__/marketWorkspace.test.ts", "src/api/__tests__/platform.test.ts"]))
    results.append(_run("v116_lint", frontend, [npm, "run", "lint"]))
    results.append(_run("v116_build", frontend, [npm, "run", "build"]))
    results.append(_run("v116_release_package", root, [sys.executable, "scripts/verify_platform_release_candidate_package.py"]))
    return results


def main() -> int:
    results = run_v116_checks()
    for result in results:
        print(f"[{'OK' if result.status == 'passed' else 'FAIL'}] {result.check_id}")
        print(f"  {json.dumps(result.details, ensure_ascii=False)}")
    if any(result.status == "failed" for result in results):
        print("DSA_PLATFORM_PUBLIC_MARKET_PRICE_ALERTS_V116_FAILED")
        return 1
    print(OK_MARKER)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
