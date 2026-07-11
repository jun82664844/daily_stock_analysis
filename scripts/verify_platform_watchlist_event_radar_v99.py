from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Sequence


REPO_ROOT = Path(__file__).resolve().parents[1]
OK_MARKER = "DSA_PLATFORM_WATCHLIST_EVENT_RADAR_V99_OK"
REQUIRED_FILES = (
    "src/platform_watchlist_radar.py",
    "src/platform_watchlist.py",
    "api/v1/endpoints/platform.py",
    "api/v1/schemas/platform.py",
    "tests/test_platform_watchlist_event_radar_v99.py",
    "tests/test_platform_watchlist_event_radar_v99_verifier.py",
    "apps/dsa-web/src/api/platform.ts",
    "apps/dsa-web/src/components/radar/WatchlistEventRadarV99.tsx",
    "apps/dsa-web/src/components/radar/__tests__/WatchlistEventRadarV99.test.tsx",
    "apps/dsa-web/src/pages/HomePage.tsx",
    "apps/dsa-web/src/pages/__tests__/HomePage.test.tsx",
    "docs/superpowers/plans/2026-07-11-dsa-v99-watchlist-event-radar.md",
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
        check_id="v99_required_files",
        title="V99 required files exist",
        status="failed" if missing else "passed",
        elapsed_sec=time.monotonic() - started,
        error="required files are missing" if missing else "",
        metadata={"missing_files": missing, "checked": len(REQUIRED_FILES)},
    )


def _git_visibility(root: Path) -> CheckResult:
    started = time.monotonic()
    verifier = "scripts/verify_platform_watchlist_event_radar_v99.py"
    completed = subprocess.run(
        ["git", "check-ignore", "-q", verifier],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    ignored = completed.returncode == 0
    return CheckResult(
        check_id="v99_verifier_visible",
        title="V99 verifier is visible to git",
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
            "stdout_tail": completed.stdout[-1600:],
            "stderr_tail": completed.stderr[-1600:],
        },
    )


def run_v99_checks(
    *,
    project_root: Path = REPO_ROOT,
    python_exe: str | None = None,
    run_subprocess: bool = True,
) -> list[CheckResult]:
    root = project_root.resolve()
    results = [_required_files(root)]
    if (root / ".git").exists():
        results.append(_git_visibility(root))
    if not run_subprocess:
        return results
    python_path = python_exe or sys.executable
    npm = "npm.cmd" if sys.platform == "win32" else "npm"
    results.extend(
        [
            _command(
                "v99_backend_tests",
                "V99 backend and verifier tests pass",
                root,
                [python_path, "-m", "unittest", "tests.test_platform_watchlist_event_radar_v99", "tests.test_platform_watchlist_event_radar_v99_verifier"],
            ),
            _command(
                "v99_frontend_component",
                "V99 radar component tests pass",
                root / "apps" / "dsa-web",
                [npm, "run", "test", "--", "--run", "src/components/radar/__tests__/WatchlistEventRadarV99.test.tsx"],
            ),
            _command(
                "v99_frontend_homepage",
                "V99 HomePage integration test passes",
                root / "apps" / "dsa-web",
                [npm, "run", "test", "--", "--run", "src/pages/__tests__/HomePage.test.tsx", "-t", "V99 watchlist event radar"],
            ),
            _command(
                "v99_frontend_build",
                "V99 frontend production build passes",
                root / "apps" / "dsa-web",
                [npm, "run", "build"],
            ),
        ]
    )
    return results


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify the local DSA V99 watchlist event radar.")
    parser.add_argument("--project-root", default=str(REPO_ROOT))
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument("--skip-subprocess", action="store_true")
    args = parser.parse_args(argv)
    results = run_v99_checks(
        project_root=Path(args.project_root),
        python_exe=args.python,
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
        print("DSA_PLATFORM_WATCHLIST_EVENT_RADAR_V99_FAILED")
        return 1
    print(OK_MARKER)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
