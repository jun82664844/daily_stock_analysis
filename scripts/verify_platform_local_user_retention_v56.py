from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Sequence


REPO_ROOT = Path(__file__).resolve().parents[1]
OK_MARKER = "DSA_PLATFORM_LOCAL_USER_RETENTION_V56_OK"

REQUIRED_FILES = (
    "api/v1/endpoints/platform.py",
    "api/v1/schemas/platform.py",
    "tests/test_platform_local_user_retention_v56.py",
    "apps/dsa-web/src/api/platform.ts",
    "apps/dsa-web/src/pages/HomePage.tsx",
    "apps/dsa-web/src/pages/__tests__/HomePage.test.tsx",
    "apps/dsa-web/e2e/platform-user-e2e.spec.ts",
    "docs/superpowers/plans/2026-07-06-dsa-v56-user-retention-loop.md",
)

STATIC_MARKERS = (
    "/history/snapshot",
    "PlatformSnapshotHistorySaveRequest",
    "PlatformSnapshotHistorySaveResponse",
    "snapshot_saved_to_history",
    "platform_snapshot_save_v56",
    "saveSnapshotToHistory",
    "basic-query-save-current-history",
    "basic-query-add-current-watchlist",
    "basic-query-retention-mode-guide",
    "basic-query-retention-status",
    "Free no-AI",
    "Platform API",
    "BYOK",
    "Local model",
    "DSA_PLATFORM_LOCAL_USER_RETENTION_V56_OK",
    "not investment advice",
)

UNITTEST_MODULES = (
    "tests.test_platform_local_user_retention_v56",
)


@dataclass(frozen=True)
class CheckResult:
    check_id: str
    title: str
    status: str
    elapsed_sec: float = 0.0
    error: str = ""
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "check_id": self.check_id,
            "title": self.title,
            "status": self.status,
            "elapsed_sec": round(self.elapsed_sec, 3),
            "error": self.error,
            "metadata": self.metadata,
        }


def _result(
    check_id: str,
    title: str,
    started: float,
    *,
    status: str = "passed",
    error: str = "",
    metadata: dict | None = None,
) -> CheckResult:
    return CheckResult(
        check_id=check_id,
        title=title,
        status=status,
        elapsed_sec=time.monotonic() - started,
        error=error,
        metadata=metadata or {},
    )


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _run_required_files_check(root: Path) -> CheckResult:
    started = time.monotonic()
    missing = [rel_path for rel_path in REQUIRED_FILES if not (root / rel_path).exists()]
    if missing:
        return _result(
            "v56_required_files_present",
            "V56 user retention files exist",
            started,
            status="failed",
            error="required files missing",
            metadata={"missing_files": missing},
        )
    return _result(
        "v56_required_files_present",
        "V56 user retention files exist",
        started,
        metadata={"checked_files": list(REQUIRED_FILES)},
    )


def _run_static_boundary_check(root: Path) -> CheckResult:
    started = time.monotonic()
    texts: list[str] = []
    for rel_path in REQUIRED_FILES:
        path = root / rel_path
        if path.exists():
            texts.append(_read_text(path))
    combined = "\n".join(texts)
    missing = [marker for marker in STATIC_MARKERS if marker not in combined]
    unsafe = []
    for marker in ("sk-live-", "stripe_live", "BILLING_PROVIDER=stripe", "SEARXNG_PUBLIC_INSTANCES_ENABLED=true"):
        marker_lower = marker.lower()
        for line in combined.splitlines():
            line_lower = line.lower()
            if marker_lower not in line_lower:
                continue
            if "not.tohavetextcontent" in line_lower or "notin" in line_lower or "not in" in line_lower:
                continue
            unsafe.append(marker)
            break
    if missing or unsafe:
        return _result(
            "v56_static_retention_boundaries",
            "V56 retention markers and local-only boundaries are present",
            started,
            status="failed",
            error="static V56 retention check failed",
            metadata={"missing_markers": missing, "unsafe_markers": unsafe},
        )
    return _result(
        "v56_static_retention_boundaries",
        "V56 retention markers and local-only boundaries are present",
        started,
        metadata={"markers": list(STATIC_MARKERS)},
    )


def _run_unittest_check(root: Path, python_exe: str) -> CheckResult:
    started = time.monotonic()
    env = os.environ.copy()
    env.setdefault("SEARXNG_PUBLIC_INSTANCES_ENABLED", "false")
    completed = subprocess.run(
        [python_exe, "-m", "unittest", *UNITTEST_MODULES],
        cwd=root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        env=env,
    )
    if completed.returncode != 0:
        return _result(
            "v56_unittests",
            "V56 user retention tests pass",
            started,
            status="failed",
            error="unittest command failed",
            metadata={
                "returncode": completed.returncode,
                "stdout_tail": completed.stdout[-2000:],
                "stderr_tail": completed.stderr[-2000:],
                "modules": list(UNITTEST_MODULES),
            },
        )
    return _result(
        "v56_unittests",
        "V56 user retention tests pass",
        started,
        metadata={"modules": list(UNITTEST_MODULES), "stderr_tail": completed.stderr[-1000:]},
    )


def _json_get(url: str, timeout_sec: float = 20.0) -> dict:
    request = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=timeout_sec) as response:
        raw = response.read().decode("utf-8", errors="replace")
        return json.loads(raw)


def _run_live_read_check(live_url: str) -> CheckResult:
    started = time.monotonic()
    base = live_url.rstrip("/")
    try:
        health = _json_get(f"{base}/health", timeout_sec=10)
        snapshot = _json_get(
            f"{base}/api/v1/stocks/{urllib.parse.quote('AAPL', safe='')}/snapshot",
            timeout_sec=30,
        )
        failures = []
        if health.get("status") != "ok":
            failures.append("health_not_ok")
        if snapshot.get("ai_used") is not False:
            failures.append("snapshot_ai_used_not_false")
        if not snapshot.get("stock_code") and not snapshot.get("stockCode"):
            failures.append("snapshot_stock_code_missing")
        if failures:
            return _result(
                "v56_live_read_smoke",
                "Live 8018 no-write read smoke",
                started,
                status="failed",
                error="live read smoke failed",
                metadata={"failures": failures},
            )
        return _result(
            "v56_live_read_smoke",
            "Live 8018 no-write read smoke",
            started,
            metadata={"health": health.get("status"), "stock_code": snapshot.get("stock_code") or snapshot.get("stockCode")},
        )
    except Exception as exc:
        return _result(
            "v56_live_read_smoke",
            "Live 8018 no-write read smoke",
            started,
            status="failed",
            error=str(exc),
        )


def run_local_user_retention_v56_checks(
    *,
    project_root: Path = REPO_ROOT,
    python_exe: str = sys.executable,
    run_subprocess: bool = True,
    live_url: str | None = None,
) -> list[CheckResult]:
    root = Path(project_root)
    results = [
        _run_required_files_check(root),
        _run_static_boundary_check(root),
    ]
    if run_subprocess:
        results.append(_run_unittest_check(root, python_exe))
    else:
        results.append(
            CheckResult(
                "v56_unittests",
                "V56 user retention tests pass",
                "skipped",
                metadata={"reason": "subprocess disabled"},
            )
        )
    if live_url:
        results.append(_run_live_read_check(live_url))
    return results


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify DSA platform local user retention V56.")
    parser.add_argument("--project-root", default=str(REPO_ROOT))
    parser.add_argument("--python-exe", default=sys.executable)
    parser.add_argument("--skip-subprocess", action="store_true")
    parser.add_argument("--live-url", default=None)
    args = parser.parse_args(argv)

    results = run_local_user_retention_v56_checks(
        project_root=Path(args.project_root),
        python_exe=args.python_exe,
        run_subprocess=not args.skip_subprocess,
        live_url=args.live_url,
    )
    for result in results:
        prefix = "[OK]" if result.status == "passed" else "[SKIP]" if result.status == "skipped" else "[FAIL]"
        print(f"{prefix} {result.check_id}: {result.title}")
        if result.error:
            print(f"  error: {result.error}")
        if result.metadata:
            print(f"  metadata: {json.dumps(result.metadata, ensure_ascii=False, sort_keys=True)}")
    failed = [result for result in results if result.status == "failed"]
    if failed:
        return 1
    print(OK_MARKER)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
