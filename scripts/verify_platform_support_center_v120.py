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
    "DSA_PLATFORM_SUPPORT_CENTER_V120_OK user_loop=true admin_queue=true "
    "ownership_isolated=true csrf=true rate_limit=true ai_reply=false "
    "attachments=false investment_advice=false"
)
REQUIRED_FILES = (
    "api/middlewares/auth.py",
    "api/v1/endpoints/support.py",
    "api/v1/schemas/support.py",
    "src/services/platform_support_service.py",
    "tests/test_platform_support_api_v120.py",
    "tests/test_platform_support_center_v120_verifier.py",
    "apps/dsa-web/src/api/support.ts",
    "apps/dsa-web/src/api/__tests__/support.test.ts",
    "apps/dsa-web/src/pages/SupportPage.tsx",
    "apps/dsa-web/src/pages/__tests__/SupportPage.test.tsx",
    "apps/dsa-web/src/components/admin/SupportWorkbenchV120.tsx",
    "apps/dsa-web/src/components/admin/__tests__/SupportWorkbenchV120.test.tsx",
    "apps/dsa-web/e2e/platform-support-v120.spec.ts",
    "docs/platform-support-center.md",
    "docs/superpowers/plans/2026-07-14-dsa-v120-platform-support-center.md",
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
    return CheckResult("v120_required_files", "failed" if missing else "passed", {"missing": missing})


def _check_contract(root: Path) -> CheckResult:
    requirements = {
        "src/storage.py": (
            "class PlatformSupportTicket",
            "platform_support_tickets",
            "class PlatformSupportMessage",
            "platform_support_messages",
        ),
        "src/services/platform_support_service.py": (
            "class PlatformSupportService",
            "_owned_ticket",
            "SupportTicketClosed",
            "unread_by_user",
            "unread_by_admin",
            "update_admin_status",
        ),
        "api/v1/endpoints/support.py": (
            "require_csrf(request)",
            "check_platform_rate_limit",
            "support_ticket_created",
            "_require_admin",
            '@router.post("/tickets",',
            '@router.get("/admin/tickets",',
        ),
        "api/middlewares/auth.py": ('"/api/v1/support/"',),
        "apps/dsa-web/src/api/support.ts": (
            "listTickets",
            "createTicket",
            "adminListTickets",
            "adminUpdateStatus",
        ),
        "apps/dsa-web/src/pages/SupportPage.tsx": (
            "platformApi.current",
            "supportApi.createTicket",
            "supportApi.addMessage",
            "supportApi.closeTicket",
            "不构成投资建议",
        ),
        "apps/dsa-web/src/components/admin/SupportWorkbenchV120.tsx": (
            "supportApi.adminListTickets",
            "supportApi.adminAddMessage",
            "supportApi.adminUpdateStatus",
            "不启用 AI 自动回复",
        ),
        "apps/dsa-web/src/App.tsx": ('path="/support"', "<SupportPage />"),
    }
    missing: list[str] = []
    for path, tokens in requirements.items():
        text = _source(root, path)
        missing.extend(f"{path}:{token}" for token in tokens if token not in text)
    return CheckResult("v120_source_contract", "failed" if missing else "passed", {"missing": missing})


def _check_safety_boundary(root: Path) -> CheckResult:
    paths = (
        "api/v1/endpoints/support.py",
        "src/services/platform_support_service.py",
        "apps/dsa-web/src/api/support.ts",
        "apps/dsa-web/src/pages/SupportPage.tsx",
        "apps/dsa-web/src/components/admin/SupportWorkbenchV120.tsx",
    )
    combined = "\n".join(_source(root, path) for path in paths)
    lowered = combined.lower()
    violations: list[str] = []
    for token in ("import litellm", "import openai", "import anthropic", "ollama_runtime", "uploadfile", "formdata(", 'type="file"'):
        if token in lowered:
            violations.append(token)
    if re.search(r"\bsk-[A-Za-z0-9._-]{8,}\b", combined):
        violations.append("secret-like-key")
    return CheckResult(
        "v120_no_ai_reply_attachment_or_secret",
        "failed" if violations else "passed",
        {"violations": violations},
    )


def _run(check_id: str, cwd: Path, command: Sequence[str], *, env: dict[str, str] | None = None) -> CheckResult:
    completed = subprocess.run(
        list(command), cwd=cwd, capture_output=True, text=True,
        encoding="utf-8", errors="replace", check=False,
        env={**os.environ, **(env or {})},
    )
    return CheckResult(check_id, "passed" if completed.returncode == 0 else "failed", {
        "returncode": completed.returncode,
        "stdout_tail": completed.stdout[-1800:],
        "stderr_tail": completed.stderr[-1800:],
    })


def run_v120_checks(*, project_root: Path = REPO_ROOT, run_subprocess: bool = True) -> list[CheckResult]:
    root = project_root.resolve()
    results = [_check_files(root), _check_contract(root), _check_safety_boundary(root)]
    if not run_subprocess:
        return results

    results.append(_run("v120_backend_tests", root, [
        sys.executable, "-m", "unittest",
        "tests.test_platform_support_api_v120",
        "tests.test_platform_support_center_v120_verifier",
    ]))
    npm = shutil.which("npm.cmd") or shutil.which("npm") or "npm"
    npx = shutil.which("npx.cmd") or shutil.which("npx") or "npx"
    frontend = root / "apps/dsa-web"
    results.append(_run("v120_frontend_tests", frontend, [
        npm, "test", "--", "--run",
        "src/api/__tests__/support.test.ts",
        "src/pages/__tests__/SupportPage.test.tsx",
        "src/components/admin/__tests__/SupportWorkbenchV120.test.tsx",
        "src/App.test.tsx",
        "src/components/layout/__tests__/SidebarNav.test.tsx",
    ]))
    results.append(_run("v120_frontend_lint", frontend, [npm, "run", "lint"]))
    results.append(_run("v120_frontend_build", frontend, [npm, "run", "build"]))
    results.append(_run(
        "v120_browser_e2e",
        frontend,
        [npx, "playwright", "test", "e2e/platform-support-v120.spec.ts", "--project=chromium"],
        env={"DSA_PLATFORM_E2E": "1"},
    ))
    results.append(_run("v120_release_package", root, [sys.executable, "scripts/verify_platform_release_candidate_package.py"]))
    return results


def main() -> int:
    results = run_v120_checks()
    for result in results:
        print(f"[{'OK' if result.status == 'passed' else 'FAIL'}] {result.check_id}")
        print(f"  {json.dumps(result.details, ensure_ascii=False)}")
    if any(result.status == "failed" for result in results):
        print("DSA_PLATFORM_SUPPORT_CENTER_V120_FAILED")
        return 1
    print(OK_MARKER)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
