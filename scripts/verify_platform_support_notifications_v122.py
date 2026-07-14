from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Sequence


REPO_ROOT = Path(__file__).resolve().parents[1]
OK_MARKER = (
    "DSA_PLATFORM_SUPPORT_NOTIFICATIONS_V122_OK user_badge=true admin_badge=true "
    "polling=visible_only summary_redacted=true ai_reply=false external_notifications=false"
)
REQUIRED_FILES = (
    "api/v1/endpoints/support.py",
    "api/v1/schemas/support.py",
    "src/services/platform_support_service.py",
    "tests/test_platform_support_api_v120.py",
    "tests/test_platform_support_notifications_api_v122.py",
    "tests/test_platform_support_notifications_v122_verifier.py",
    "apps/dsa-web/src/api/support.ts",
    "apps/dsa-web/src/api/__tests__/support.test.ts",
    "apps/dsa-web/src/components/layout/SidebarNav.tsx",
    "apps/dsa-web/src/components/layout/__tests__/SidebarNav.test.tsx",
    "apps/dsa-web/e2e/platform-support-notifications-v122.spec.ts",
    "docs/platform-support-center.md",
    "docs/superpowers/plans/2026-07-14-dsa-v122-support-inbox-notifications.md",
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
    return CheckResult("v122_required_files", "failed" if missing else "passed", {"missing": missing})


def _check_contract(root: Path) -> CheckResult:
    requirements = {
        "src/services/platform_support_service.py": (
            "def user_summary(",
            "def admin_summary(",
            "unread_by_user",
            "unread_by_admin",
        ),
        "api/v1/endpoints/support.py": (
            '@router.get("/summary"',
            '@router.get("/admin/summary"',
            "SupportUserSummaryResponse",
            "SupportAdminSummaryResponse",
            "_require_admin",
        ),
        "apps/dsa-web/src/api/support.ts": (
            "SUPPORT_INBOX_CHANGED_EVENT",
            "async getSummary()",
            "async adminGetSummary()",
            "emitSupportInboxChanged()",
        ),
        "apps/dsa-web/src/components/layout/SidebarNav.tsx": (
            "support-user-badge",
            "support-admin-badge",
            "document.visibilityState === 'visible'",
            "60_000",
            "SUPPORT_INBOX_CHANGED_EVENT",
        ),
    }
    missing: list[str] = []
    for path, tokens in requirements.items():
        text = _source(root, path)
        missing.extend(f"{path}:{token}" for token in tokens if token not in text)
    return CheckResult("v122_source_contract", "failed" if missing else "passed", {"missing": missing})


def _check_redaction_and_boundaries(root: Path) -> CheckResult:
    schemas = _source(root, "api/v1/schemas/support.py")
    combined = "\n".join(_source(root, path) for path in (
        "api/v1/endpoints/support.py",
        "src/services/platform_support_service.py",
        "apps/dsa-web/src/api/support.ts",
        "apps/dsa-web/src/components/layout/SidebarNav.tsx",
    ))
    violations: list[str] = []
    for model in ("SupportUserSummaryResponse", "SupportAdminSummaryResponse"):
        match = re.search(rf"class {model}\b(?P<body>.*?)(?=\nclass |\Z)", schemas, re.DOTALL)
        if not match:
            violations.append(f"missing-schema:{model}")
            continue
        lowered = match.group("body").lower()
        for token in ("subject", "body", "message", "requester_email"):
            if token in lowered:
                violations.append(f"summary-exposes:{model}:{token}")
    lowered = combined.lower()
    for token in ("import openai", "import anthropic", "websocket", "send_email", "send_sms", "feishu_sender"):
        if token in lowered:
            violations.append(f"external-or-ai:{token}")
    if re.search(r"\bsk-[A-Za-z0-9._-]{8,}\b", combined):
        violations.append("secret-like-key")
    return CheckResult(
        "v122_redacted_local_only_boundary",
        "failed" if violations else "passed",
        {"violations": violations},
    )


def _run(check_id: str, cwd: Path, command: Sequence[str], *, env: dict[str, str] | None = None) -> CheckResult:
    completed = subprocess.run(
        list(command),
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        env={**os.environ, **(env or {})},
    )
    return CheckResult(check_id, "passed" if completed.returncode == 0 else "failed", {
        "returncode": completed.returncode,
        "stdout_tail": completed.stdout[-1800:],
        "stderr_tail": completed.stderr[-1800:],
    })


def run_v122_checks(*, project_root: Path = REPO_ROOT, run_subprocess: bool = True) -> list[CheckResult]:
    root = project_root.resolve()
    results = [_check_files(root), _check_contract(root), _check_redaction_and_boundaries(root)]
    if not run_subprocess:
        return results

    results.append(_run("v122_backend_tests", root, [
        sys.executable,
        "-m",
        "unittest",
        "tests.test_platform_support_api_v120",
        "tests.test_platform_support_notifications_api_v122",
        "tests.test_platform_support_notifications_v122_verifier",
    ]))
    npm = shutil.which("npm.cmd") or shutil.which("npm") or "npm"
    npx = shutil.which("npx.cmd") or shutil.which("npx") or "npx"
    frontend = root / "apps/dsa-web"
    results.append(_run("v122_frontend_tests", frontend, [
        npm,
        "test",
        "--",
        "--run",
        "src/api/__tests__/support.test.ts",
        "src/pages/__tests__/SupportPage.test.tsx",
        "src/components/admin/__tests__/SupportWorkbenchV120.test.tsx",
        "src/components/layout/__tests__/SidebarNav.test.tsx",
        "src/App.test.tsx",
    ]))
    results.append(_run("v122_frontend_lint", frontend, [npm, "run", "lint"]))
    results.append(_run("v122_frontend_build", frontend, [npm, "run", "build"]))
    results.append(_run(
        "v122_browser_e2e",
        frontend,
        [npx, "playwright", "test", "e2e/platform-support-notifications-v122.spec.ts", "--project=chromium"],
        env={"DSA_PLATFORM_E2E": "1"},
    ))
    results.append(_run(
        "v122_release_package",
        root,
        [sys.executable, "scripts/verify_platform_release_candidate_package.py"],
    ))
    return results


def main() -> int:
    results = run_v122_checks()
    for result in results:
        print(f"[{'OK' if result.status == 'passed' else 'FAIL'}] {result.check_id}")
        print(f"  {json.dumps(result.details, ensure_ascii=False)}")
    if any(result.status == "failed" for result in results):
        print("DSA_PLATFORM_SUPPORT_NOTIFICATIONS_V122_FAILED")
        return 1
    print(OK_MARKER)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
