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
OK_MARKER = "DSA_PLATFORM_A_SHARE_FREE_QUERY_SPEED_V102_OK"
REQUIRED_FILES = (
    "src/services/a_share_enrichment_service.py",
    "src/services/basic_query_service.py",
    "tests/test_a_share_enrichment_service.py",
    "tests/test_platform_market_data_freshness_v92.py",
    "docs/superpowers/plans/2026-07-11-dsa-v102-a-share-free-query-speed.md",
    "scripts/verify_platform_a_share_free_query_speed_v102.py",
    "tests/test_platform_a_share_free_query_speed_v102_verifier.py",
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
        check_id="v102_required_files",
        title="V102 required files exist",
        status="failed" if missing else "passed",
        elapsed_sec=time.monotonic() - started,
        error="required files are missing" if missing else "",
        metadata={"missing_files": missing, "checked": len(REQUIRED_FILES)},
    )


def _source_contract(root: Path) -> CheckResult:
    started = time.monotonic()
    source = root / "src/services/a_share_enrichment_service.py"
    basic_query = root / "src/services/basic_query_service.py"
    text = source.read_text(encoding="utf-8", errors="replace") if source.exists() else ""
    basic_text = basic_query.read_text(encoding="utf-8", errors="replace") if basic_query.exists() else ""
    required_tokens = (
        "_A_SHARE_ENRICHMENT_EXECUTOR",
        "A_STOCK_DATA_TOTAL_TIMEOUT_SEC",
        "_A_SHARE_ENRICHMENT_SHARED_CACHE",
        "cached_total_timeout",
        '"parallel"',
    )
    missing = [token for token in required_tokens if token not in text]
    if "self.source_health.should_skip(source_id)" not in basic_text:
        missing.append("reference_quote_source_cooldown")
    return CheckResult(
        check_id="v102_source_contract",
        title="V102 bounded parallel and shared-cache contract is present",
        status="failed" if missing else "passed",
        elapsed_sec=time.monotonic() - started,
        error="source contract is incomplete" if missing else "",
        metadata={"missing_tokens": missing},
    )


def _git_visibility(root: Path) -> CheckResult:
    started = time.monotonic()
    verifier = "scripts/verify_platform_a_share_free_query_speed_v102.py"
    completed = subprocess.run(
        ["git", "check-ignore", "-q", verifier],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    ignored = completed.returncode == 0
    return CheckResult(
        check_id="v102_verifier_visible",
        title="V102 verifier is visible to git",
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


def run_v102_checks(*, project_root: Path = REPO_ROOT, run_subprocess: bool = True) -> list[CheckResult]:
    root = project_root.resolve()
    results = [_required_files(root), _source_contract(root)]
    if (root / ".git").exists():
        results.append(_git_visibility(root))
    if not run_subprocess:
        return results
    results.append(
        _command(
            "v102_performance_contract_tests",
            "V102 concurrent budget, timeout degradation, and shared-cache tests pass",
            root,
            [
                sys.executable,
                "-m",
                "unittest",
                "tests.test_a_share_enrichment_service",
                "tests.test_platform_market_data_freshness_v92",
                "-v",
            ],
        )
    )
    return results


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify DSA V102 A-share free query speed.")
    parser.add_argument("--project-root", default=str(REPO_ROOT))
    parser.add_argument("--skip-subprocess", action="store_true")
    args = parser.parse_args(argv)
    results = run_v102_checks(
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
        print("DSA_PLATFORM_A_SHARE_FREE_QUERY_SPEED_V102_FAILED")
        return 1
    print(OK_MARKER)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
