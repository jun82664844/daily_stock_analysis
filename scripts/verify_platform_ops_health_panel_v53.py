from __future__ import annotations

import argparse
import json
import os
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Sequence


REPO_ROOT = Path(__file__).resolve().parents[1]
WEB_ROOT = REPO_ROOT / "apps" / "dsa-web"
OK_MARKER = "DSA_PLATFORM_OPS_HEALTH_PANEL_V53_OK"

REQUIRED_MARKERS = {
    "apps/dsa-web/src/api/platform.ts": (
        "PlatformOpsHealthResponse",
        "adminOpsHealth",
        "/api/v1/platform/admin/ops-health",
    ),
    "apps/dsa-web/src/pages/AdminPage.tsx": (
        "Ops health",
        "opsHealth",
        "adminOpsHealth",
        "Read-only local operations health",
    ),
    "apps/dsa-web/src/pages/__tests__/AdminPage.test.tsx": (
        "adminOpsHealth",
        "Billing provider readiness",
        "DEGRADED",
    ),
    "apps/dsa-web/src/api/__tests__/platform.test.ts": (
        "loads admin ops health as camelCase",
        "adapterImplemented",
        "/api/v1/platform/admin/ops-health",
    ),
    "docs/superpowers/plans/2026-07-05-dsa-ops-health-panel-v53.md": (
        "DSA_PLATFORM_OPS_HEALTH_PANEL_V53_OK",
        "secret-free",
    ),
}


@dataclass(frozen=True)
class VerifyResult:
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
) -> VerifyResult:
    return VerifyResult(
        check_id=check_id,
        title=title,
        status=status,
        elapsed_sec=time.monotonic() - started,
        error=error,
        metadata=metadata or {},
    )


def _run_static_markers_check(root: Path) -> VerifyResult:
    started = time.monotonic()
    missing: dict[str, list[str]] = {}
    for rel_path, markers in REQUIRED_MARKERS.items():
        path = root / rel_path
        text = path.read_text(encoding="utf-8", errors="replace") if path.exists() else ""
        absent = [marker for marker in markers if marker not in text]
        if absent:
            missing[rel_path] = absent
    if missing:
        return _result(
            "static_markers_present",
            "V53 ops health panel markers are present",
            started,
            status="failed",
            error="required markers are missing",
            metadata={"missing_markers": missing},
        )
    return _result(
        "static_markers_present",
        "V53 ops health panel markers are present",
        started,
        metadata={"checked_files": sorted(REQUIRED_MARKERS)},
    )


def _run_frontend_tests(root: Path) -> VerifyResult:
    started = time.monotonic()
    npm_cmd = "npm.cmd" if os.name == "nt" else "npm"
    completed = subprocess.run(
        [npm_cmd, "run", "test", "--", "src/pages/__tests__/AdminPage.test.tsx", "src/api/__tests__/platform.test.ts"],
        cwd=root / "apps" / "dsa-web",
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if completed.returncode != 0:
        return _result(
            "frontend_tests",
            "AdminPage and platform API tests pass",
            started,
            status="failed",
            error="frontend tests failed",
            metadata={"stdout_tail": completed.stdout[-1200:], "stderr_tail": completed.stderr[-1200:]},
        )
    return _result(
        "frontend_tests",
        "AdminPage and platform API tests pass",
        started,
        metadata={"stdout_tail": completed.stdout[-800:]},
    )


def run_checks(*, project_root: str | Path | None = None) -> list[VerifyResult]:
    root = Path(project_root).resolve() if project_root is not None else REPO_ROOT
    return [
        _run_static_markers_check(root),
        _run_frontend_tests(root),
    ]


def _print_text_report(results: Sequence[VerifyResult]) -> None:
    for result in results:
        marker = "[OK]" if result.status == "passed" else "[FAIL]"
        print(f"{marker} {result.check_id}: {result.title}")
        if result.error:
            print(f"  error: {result.error}")
        if result.metadata:
            print(f"  metadata: {json.dumps(result.metadata, ensure_ascii=False)}")
    if all(result.status == "passed" for result in results):
        print(OK_MARKER)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify DSA ops health panel V53 package")
    parser.add_argument("--project-root", default=str(REPO_ROOT), help="DSA project root")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON")
    args = parser.parse_args(argv)

    results = run_checks(project_root=args.project_root)
    if args.json:
        print(json.dumps([result.to_dict() for result in results], ensure_ascii=False, indent=2))
    else:
        _print_text_report(results)
    return 0 if all(result.status == "passed" for result in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
