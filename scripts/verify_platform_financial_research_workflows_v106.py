from __future__ import annotations

import json
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Sequence


REPO_ROOT = Path(__file__).resolve().parents[1]
OK_MARKER = "DSA_PLATFORM_FINANCIAL_RESEARCH_WORKFLOWS_V106_OK"
ACCEPTED_SOURCE_COMMIT = "4aa51ed3d379731f8f9beff498d749580372699c"
EXTERNAL_SOURCE = "external/anthropic-financial-services"
REQUIRED_FILES = (
    "src/services/financial_research_workflow_service.py",
    "api/v1/endpoints/stocks.py",
    "api/v1/schemas/basic_query.py",
    "api/middlewares/auth.py",
    "tests/test_financial_research_workflow_service_v106.py",
    "tests/test_financial_research_workflow_api_v106.py",
    "apps/dsa-web/src/api/researchWorkflows.ts",
    "apps/dsa-web/src/api/__tests__/researchWorkflows.test.ts",
    "apps/dsa-web/src/pages/ResearchWorkflowsPage.tsx",
    "apps/dsa-web/src/pages/__tests__/ResearchWorkflowsPage.test.tsx",
    "docs/superpowers/third-party/anthropic-financial-services.md",
    "docs/superpowers/plans/2026-07-11-dsa-v106-financial-research-workflows.md",
    "scripts/verify_platform_financial_research_workflows_v106.py",
    "tests/test_platform_financial_research_workflows_v106_verifier.py",
)
SOURCE_SKILLS = (
    "plugins/vertical-plugins/financial-analysis/skills/comps-analysis/SKILL.md",
    "plugins/vertical-plugins/equity-research/skills/earnings-analysis/SKILL.md",
    "plugins/vertical-plugins/equity-research/skills/sector-overview/SKILL.md",
    "plugins/vertical-plugins/equity-research/skills/catalyst-calendar/SKILL.md",
)


@dataclass(frozen=True)
class CheckResult:
    check_id: str
    status: str
    details: dict = field(default_factory=dict)


def _check_files(root: Path) -> CheckResult:
    missing = [path for path in REQUIRED_FILES if not (root / path).exists()]
    return CheckResult("v106_required_files", "failed" if missing else "passed", {"missing": missing})


def _check_contract(root: Path) -> CheckResult:
    requirements = {
        "src/services/financial_research_workflow_service.py": (
            "company_snapshot",
            "earnings_review",
            "sector_overview",
            "catalyst_calendar",
            '"external_code_executed": False',
            '"connectors_enabled": False',
            "deterministic_no_ai",
            "ACCEPTED_SOURCE_COMMIT",
            '"commit_verified": commit_verified',
            '"unit": cls._fact_unit',
            "_verified_event_fact",
        ),
        "api/middlewares/auth.py": ("re.fullmatch(", "research-workflows"),
        "api/v1/endpoints/stocks.py": ("/{stock_code}/research-workflows", "FinancialResearchWorkflowService"),
        "apps/dsa-web/src/pages/ResearchWorkflowsPage.tsx": (
            "Financial research center",
            "金融研究中心",
            "External connectors disabled",
            "外部连接器未启用",
        ),
        "docs/superpowers/third-party/anthropic-financial-services.md": (
            "Apache-2.0",
            "does not import or execute",
            "not a market-data license",
        ),
    }
    missing: list[str] = []
    for path, tokens in requirements.items():
        source = (root / path).read_text(encoding="utf-8", errors="replace") if (root / path).exists() else ""
        missing.extend(f"{path}:{token}" for token in tokens if token not in source)
    return CheckResult("v106_source_contract", "failed" if missing else "passed", {"missing": missing})


def _read_source_commit(source_root: Path) -> str | None:
    git_dir = source_root / ".git"
    try:
        head = (git_dir / "HEAD").read_text(encoding="utf-8").strip()
    except OSError:
        return None
    if not head.startswith("ref:"):
        return head or None
    ref = head.split(":", 1)[1].strip()
    try:
        return (git_dir / ref).read_text(encoding="utf-8").strip() or None
    except OSError:
        try:
            packed = (git_dir / "packed-refs").read_text(encoding="utf-8").splitlines()
        except OSError:
            return None
        for line in packed:
            if line and not line.startswith(("#", "^")):
                commit, _, packed_ref = line.partition(" ")
                if packed_ref == ref:
                    return commit
    return None


def _check_external_source(root: Path) -> CheckResult:
    source_root = root / EXTERNAL_SOURCE
    missing = [path for path in ("LICENSE", *SOURCE_SKILLS) if not (source_root / path).exists()]
    commit = _read_source_commit(source_root)
    license_ok = False
    try:
        license_ok = "apache license" in (source_root / "LICENSE").read_text(encoding="utf-8", errors="ignore").lower()
    except OSError:
        pass
    passed = not missing and license_ok and commit == ACCEPTED_SOURCE_COMMIT
    return CheckResult(
        "v106_external_source",
        "passed" if passed else "failed",
        {
            "missing": missing,
            "license_ok": license_ok,
            "commit": commit,
            "accepted_commit": ACCEPTED_SOURCE_COMMIT,
        },
    )


def _run(check_id: str, cwd: Path, command: Sequence[str]) -> CheckResult:
    completed = subprocess.run(list(command), cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    return CheckResult(
        check_id,
        "passed" if completed.returncode == 0 else "failed",
        {"returncode": completed.returncode, "stdout_tail": completed.stdout[-1200:], "stderr_tail": completed.stderr[-1200:]},
    )


def run_v106_checks(*, project_root: Path = REPO_ROOT, run_subprocess: bool = True) -> list[CheckResult]:
    root = project_root.resolve()
    results = [_check_files(root), _check_contract(root), _check_external_source(root)]
    if not run_subprocess:
        return results
    results.append(_run(
        "v106_backend_tests",
        root,
        [
            sys.executable,
            "-m",
            "unittest",
            "tests.test_financial_research_workflow_service_v106",
            "tests.test_financial_research_workflow_api_v106",
            "tests.test_platform_financial_research_workflows_v106_verifier",
        ],
    ))
    npm = shutil.which("npm.cmd") or shutil.which("npm") or "npm"
    results.append(_run(
        "v106_frontend_tests",
        root / "apps/dsa-web",
        [
            npm,
            "test",
            "--",
            "src/api/__tests__/researchWorkflows.test.ts",
            "src/pages/__tests__/ResearchWorkflowsPage.test.tsx",
            "src/App.test.tsx",
            "src/components/layout/__tests__/SidebarNav.test.tsx",
        ],
    ))
    return results


def main() -> int:
    results = run_v106_checks()
    for result in results:
        print(f"[{'OK' if result.status == 'passed' else 'FAIL'}] {result.check_id}")
        print(f"  {json.dumps(result.details, ensure_ascii=False)}")
    if any(result.status == "failed" for result in results):
        print("DSA_PLATFORM_FINANCIAL_RESEARCH_WORKFLOWS_V106_FAILED")
        return 1
    print(OK_MARKER)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
