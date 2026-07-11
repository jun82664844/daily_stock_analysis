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
OK_MARKER = "DSA_PLATFORM_FREE_DAILY_RESEARCH_COCKPIT_V103_OK"
REQUIRED_FILES = (
    "src/platform_watchlist_radar.py",
    "api/v1/schemas/platform.py",
    "tests/test_platform_daily_research_cockpit_v103.py",
    "apps/dsa-web/src/api/platform.ts",
    "apps/dsa-web/src/components/radar/DailyResearchCockpitV103.tsx",
    "apps/dsa-web/src/components/radar/__tests__/DailyResearchCockpitV103.test.tsx",
    "apps/dsa-web/src/pages/HomePage.tsx",
    "apps/dsa-web/src/pages/__tests__/HomePage.test.tsx",
    "docs/superpowers/plans/2026-07-11-dsa-v103-free-daily-research-cockpit.md",
    "scripts/verify_platform_free_daily_research_cockpit_v103.py",
    "tests/test_platform_free_daily_research_cockpit_v103_verifier.py",
)


@dataclass(frozen=True)
class CheckResult:
    check_id: str
    title: str
    status: str
    elapsed_sec: float = 0.0
    error: str = ""
    metadata: dict = field(default_factory=dict)


def _required_files(root: Path) -> CheckResult:
    started = time.monotonic()
    missing = sorted(path for path in REQUIRED_FILES if not (root / path).exists())
    return CheckResult(
        check_id="v103_required_files",
        title="V103 required files exist",
        status="failed" if missing else "passed",
        elapsed_sec=time.monotonic() - started,
        error="required files are missing" if missing else "",
        metadata={"missing_files": missing, "checked": len(REQUIRED_FILES)},
    )


def _source_contract(root: Path) -> CheckResult:
    started = time.monotonic()
    paths_and_tokens = {
        "src/platform_watchlist_radar.py": (
            "_research_brief",
            "_daily_digest",
            '"strong_confirmation"',
            '"risk_review"',
            '"wait_for_confirmation"',
            '"data_confidence"',
        ),
        "api/v1/schemas/platform.py": (
            "PlatformWatchlistResearchBrief",
            "PlatformWatchlistDailyDigest",
            "daily_digest",
        ),
        "apps/dsa-web/src/components/radar/DailyResearchCockpitV103.tsx": (
            "daily-research-cockpit-v103",
            "trialRemaining",
            "does not consume quota automatically",
            "不会自动消耗额度",
            "不构成投资建议",
        ),
        "apps/dsa-web/src/pages/HomePage.tsx": ("DailyResearchCockpitV103",),
    }
    missing: list[str] = []
    for relative_path, tokens in paths_and_tokens.items():
        source = root / relative_path
        text = source.read_text(encoding="utf-8", errors="replace") if source.exists() else ""
        missing.extend(f"{relative_path}:{token}" for token in tokens if token not in text)
    return CheckResult(
        check_id="v103_source_contract",
        title="V103 daily research cockpit contract is present",
        status="failed" if missing else "passed",
        elapsed_sec=time.monotonic() - started,
        error="source contract is incomplete" if missing else "",
        metadata={"missing_tokens": missing},
    )


def _git_visibility(root: Path) -> CheckResult:
    started = time.monotonic()
    verifier = "scripts/verify_platform_free_daily_research_cockpit_v103.py"
    completed = subprocess.run(
        ["git", "check-ignore", "-q", verifier],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    ignored = completed.returncode == 0
    return CheckResult(
        check_id="v103_verifier_visible",
        title="V103 verifier is visible to git",
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


def run_v103_checks(*, project_root: Path = REPO_ROOT, run_subprocess: bool = True) -> list[CheckResult]:
    root = project_root.resolve()
    results = [_required_files(root), _source_contract(root)]
    if (root / ".git").exists():
        results.append(_git_visibility(root))
    if not run_subprocess:
        return results

    results.append(
        _command(
            "v103_backend_contract_tests",
            "V103 and existing watchlist radar backend tests pass",
            root,
            [
                sys.executable,
                "-m",
                "unittest",
                "tests.test_platform_daily_research_cockpit_v103",
                "tests.test_platform_watchlist_event_radar_v99",
                "tests.test_platform_watchlist_alert_loop_v100",
                "-v",
            ],
        )
    )
    npm = shutil.which("npm.cmd") or shutil.which("npm") or "npm"
    results.append(
        _command(
            "v103_frontend_contract_tests",
            "V103 component, API mapping, and HomePage integration tests pass",
            root / "apps/dsa-web",
            [
                npm,
                "test",
                "--",
                "src/components/radar/__tests__/DailyResearchCockpitV103.test.tsx",
                "src/api/__tests__/platform.test.ts",
                "src/pages/__tests__/HomePage.test.tsx",
            ],
        )
    )
    return results


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify DSA V103 free daily research cockpit.")
    parser.add_argument("--project-root", default=str(REPO_ROOT))
    parser.add_argument("--skip-subprocess", action="store_true")
    args = parser.parse_args(argv)
    results = run_v103_checks(
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
        print("DSA_PLATFORM_FREE_DAILY_RESEARCH_COCKPIT_V103_FAILED")
        return 1
    print(OK_MARKER)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
