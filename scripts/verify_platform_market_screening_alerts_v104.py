from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Sequence


REPO_ROOT = Path(__file__).resolve().parents[1]
OK_MARKER = "DSA_PLATFORM_MARKET_SCREENING_ALERTS_V104_OK"
REQUIRED_FILES = (
    "src/services/market_screening_brief.py",
    "src/services/alphasift_service.py",
    "api/middlewares/auth.py",
    "tests/test_market_screening_brief.py",
    "tests/test_alphasift_api.py",
    "tests/test_auth_api.py",
    "apps/dsa-web/src/api/alphasift.ts",
    "apps/dsa-web/src/api/__tests__/alphasift.test.ts",
    "apps/dsa-web/src/components/screening/screeningModelV104.ts",
    "apps/dsa-web/src/components/screening/MarketScreeningCardV104.tsx",
    "apps/dsa-web/src/components/screening/ScreeningCompareTrayV104.tsx",
    "apps/dsa-web/src/components/screening/ScreeningReminderPanelV104.tsx",
    "apps/dsa-web/src/components/screening/__tests__/screeningModelV104.test.ts",
    "apps/dsa-web/src/components/screening/__tests__/MarketScreeningCardV104.test.tsx",
    "apps/dsa-web/src/components/screening/__tests__/ScreeningCompareTrayV104.test.tsx",
    "apps/dsa-web/src/components/screening/__tests__/ScreeningReminderPanelV104.test.tsx",
    "apps/dsa-web/src/pages/StockScreeningPage.tsx",
    "apps/dsa-web/src/pages/__tests__/StockScreeningPage.test.tsx",
    "docs/superpowers/plans/2026-07-11-dsa-v104-explainable-stock-discovery.md",
    "scripts/verify_platform_market_screening_alerts_v104.py",
    "tests/test_platform_market_screening_alerts_v104_verifier.py",
)


@dataclass(frozen=True)
class CheckResult:
    check_id: str
    title: str
    status: str
    elapsed_sec: float = 0.0
    error: str = ""
    metadata: dict = field(default_factory=dict)


def _read(root: Path, relative_path: str) -> str:
    path = root / relative_path
    return path.read_text(encoding="utf-8", errors="replace") if path.exists() else ""


def _required_files(root: Path) -> CheckResult:
    started = time.monotonic()
    missing = sorted(path for path in REQUIRED_FILES if not (root / path).exists())
    return CheckResult(
        check_id="v104_required_files",
        title="V104 required files exist",
        status="failed" if missing else "passed",
        elapsed_sec=time.monotonic() - started,
        error="required files are missing" if missing else "",
        metadata={"missing_files": missing, "checked": len(REQUIRED_FILES)},
    )


def _source_contract(root: Path) -> CheckResult:
    started = time.monotonic()
    paths_and_tokens = {
        "src/services/market_screening_brief.py": (
            "build_market_screening_brief",
            '"matched_condition_codes"',
            '"observed_metrics"',
            '"data_freshness"',
            '"data_completeness"',
        ),
        "src/services/alphasift_service.py": ("screening_brief", "build_market_screening_brief"),
        "api/middlewares/auth.py": (
            "_public_market_screening_path",
            '"/api/v1/alphasift/screen/tasks"',
        ),
        "apps/dsa-web/src/pages/StockScreeningPage.tsx": (
            "MarketScreeningCardV104",
            "ScreeningCompareTrayV104",
            "ScreeningReminderPanelV104",
            "platformApi.addWatchlistItem",
            "platformApi.saveWatchlistAlertRule",
        ),
        "apps/dsa-web/src/components/layout/SidebarNav.tsx": (
            "key: 'screening'",
            "to: '/screening'",
        ),
    }
    missing: list[str] = []
    for relative_path, tokens in paths_and_tokens.items():
        source = _read(root, relative_path)
        missing.extend(f"{relative_path}:{token}" for token in tokens if token not in source)
    return CheckResult(
        check_id="v104_source_contract",
        title="V104 market screening and alert contract is present",
        status="failed" if missing else "passed",
        elapsed_sec=time.monotonic() - started,
        error="source contract is incomplete" if missing else "",
        metadata={"missing_tokens": missing},
    )


def _information_boundary(root: Path) -> CheckResult:
    started = time.monotonic()
    backend = _read(root, "src/services/market_screening_brief.py")
    card = _read(root, "apps/dsa-web/src/components/screening/MarketScreeningCardV104.tsx")
    reminder = _read(root, "apps/dsa-web/src/components/screening/ScreeningReminderPanelV104.tsx")
    page = _read(root, "apps/dsa-web/src/pages/StockScreeningPage.tsx")
    failures: list[str] = []
    for forbidden in ('"recommendation"', '"target_price"', '"expected_return"', '"buy_signal"', '"sell_signal"'):
        if forbidden in backend:
            failures.append(f"backend output contains {forbidden}")
    for forbidden in ("candidate.reason", "candidate.raw", "candidate.llmThesis", "candidate.riskLevel"):
        if forbidden in card:
            failures.append(f"data card renders provider field {forbidden}")
    required_copy = (
        (reminder, "不包含交易指令", "reminder boundary copy"),
        (page, "不提供投资建议、交易指令、目标价或收益预测", "page boundary copy"),
    )
    failures.extend(label for source, token, label in required_copy if token not in source)
    return CheckResult(
        check_id="v104_information_boundary",
        title="V104 exposes information and data without advisory output",
        status="failed" if failures else "passed",
        elapsed_sec=time.monotonic() - started,
        error="information-only boundary is incomplete" if failures else "",
        metadata={"failures": failures},
    )


def _git_visibility(root: Path) -> CheckResult:
    started = time.monotonic()
    verifier = "scripts/verify_platform_market_screening_alerts_v104.py"
    completed = subprocess.run(
        ["git", "check-ignore", "-q", verifier],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    ignored = completed.returncode == 0
    return CheckResult(
        check_id="v104_verifier_visible",
        title="V104 verifier is visible to git",
        status="failed" if ignored else "passed",
        elapsed_sec=time.monotonic() - started,
        error="verifier is hidden by gitignore" if ignored else "",
        metadata={"path": verifier},
    )


def _command(check_id: str, title: str, cwd: Path, command: Sequence[str]) -> CheckResult:
    started = time.monotonic()
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
        check_id=check_id,
        title=title,
        status="passed" if completed.returncode == 0 else "failed",
        elapsed_sec=time.monotonic() - started,
        error="" if completed.returncode == 0 else "command failed",
        metadata={
            "returncode": completed.returncode,
            "stdout_tail": completed.stdout[-1800:],
            "stderr_tail": completed.stderr[-1800:],
        },
    )


def run_v104_checks(*, project_root: Path = REPO_ROOT, run_subprocess: bool = True) -> list[CheckResult]:
    root = project_root.resolve()
    results = [_required_files(root), _source_contract(root), _information_boundary(root)]
    if (root / ".git").exists():
        results.append(_git_visibility(root))
    if not run_subprocess:
        return results

    results.append(
        _command(
            "v104_backend_contract_tests",
            "V104 screening brief, AlphaSift API, and alert boundary tests pass",
            root,
            [
                sys.executable,
                "-m",
                "unittest",
                "tests.test_market_screening_brief",
                "tests.test_alphasift_api",
                "tests.test_platform_watchlist_alert_loop_v100",
                "tests.test_auth_api",
                "-v",
            ],
        )
    )
    npm = shutil.which("npm.cmd") or shutil.which("npm") or "npm"
    results.append(
        _command(
            "v104_frontend_contract_tests",
            "V104 model, cards, page, API, navigation, and locale tests pass",
            root / "apps/dsa-web",
            [
                npm,
                "test",
                "--",
                "src/api/__tests__/alphasift.test.ts",
                "src/components/screening/__tests__/screeningModelV104.test.ts",
                "src/components/screening/__tests__/MarketScreeningCardV104.test.tsx",
                "src/components/screening/__tests__/ScreeningCompareTrayV104.test.tsx",
                "src/components/screening/__tests__/ScreeningReminderPanelV104.test.tsx",
                "src/pages/__tests__/StockScreeningPage.test.tsx",
                "src/components/layout/__tests__/SidebarNav.test.tsx",
            ],
        )
    )
    return results


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify DSA V104 market data screening and condition alerts.")
    parser.add_argument("--project-root", default=str(REPO_ROOT))
    parser.add_argument("--skip-subprocess", action="store_true")
    args = parser.parse_args(argv)
    results = run_v104_checks(
        project_root=Path(args.project_root),
        run_subprocess=not args.skip_subprocess,
    )
    failed = [result for result in results if result.status == "failed"]
    for result in results:
        prefix = "[OK]" if result.status == "passed" else "[FAIL]"
        print(f"{prefix} {result.check_id}: {result.title} ({result.elapsed_sec:.2f}s)")
        if result.error:
            print(f"     error: {result.error}")
        if result.metadata:
            print(f"     metadata: {json.dumps(result.metadata, ensure_ascii=False, sort_keys=True)}")
    if failed:
        print("DSA_PLATFORM_MARKET_SCREENING_ALERTS_V104_FAILED")
        return 1
    print(OK_MARKER)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
