from __future__ import annotations

import json
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Sequence


REPO_ROOT = Path(__file__).resolve().parents[1]
OK_MARKER = "DSA_PLATFORM_OLLAMA_LOCAL_RETENTION_V107_OK"
REQUIRED_FILES = (
    "src/services/ollama_runtime_service.py",
    "src/services/analysis_service.py",
    "src/core/pipeline.py",
    "src/analyzer.py",
    "api/v1/endpoints/analysis.py",
    "api/v1/endpoints/platform.py",
    "api/middlewares/auth.py",
    "tests/test_ollama_runtime_service_v107.py",
    "tests/test_platform_ollama_status_api_v107.py",
    "tests/test_platform_ollama_analysis_v107.py",
    "apps/dsa-web/src/api/platform.ts",
    "apps/dsa-web/src/components/retention/LocalModelStatusV107.tsx",
    "apps/dsa-web/src/components/retention/__tests__/LocalModelStatusV107.test.tsx",
    "docs/superpowers/plans/2026-07-11-dsa-v107-ollama-local-retention.md",
    "scripts/verify_platform_ollama_local_retention_v107.py",
    "tests/test_platform_ollama_local_retention_v107_verifier.py",
)


@dataclass(frozen=True)
class CheckResult:
    check_id: str
    status: str
    details: dict = field(default_factory=dict)


def _check_files(root: Path) -> CheckResult:
    missing = [path for path in REQUIRED_FILES if not (root / path).exists()]
    return CheckResult("v107_required_files", "failed" if missing else "passed", {"missing": missing})


def _check_contract(root: Path) -> CheckResult:
    requirements = {
        "src/services/ollama_runtime_service.py": (
            "LOCAL_LLM_QUICK_MODEL",
            "LOCAL_LLM_DEEP_MODEL",
            "local_model_unreachable",
            "litellm_fallback_models = []",
            "informational_only_mode = True",
        ),
        "api/v1/endpoints/analysis.py": (
            "local_model_status",
            "Login required",
            "readiness_reason",
        ),
        "src/core/pipeline.py": (
            "_apply_information_only_boundary",
            "仅供信息观察",
            'battle_plan["action_checklist"] = []',
        ),
        "apps/dsa-web/src/components/retention/LocalModelStatusV107.tsx": (
            "本地 AI 试用已就绪",
            "Run local AI detailed read",
            "只提供资讯和数据",
        ),
        ".env.example": (
            "LOCAL_LLM_ENABLED=false",
            "LOCAL_LLM_QUICK_MODEL=",
            "LOCAL_LLM_DEEP_MODEL=",
            "LOCAL_LLM_ALLOW_REMOTE=false",
        ),
    }
    missing: list[str] = []
    for path, tokens in requirements.items():
        source = (root / path).read_text(encoding="utf-8", errors="replace") if (root / path).exists() else ""
        missing.extend(f"{path}:{token}" for token in tokens if token not in source)
    return CheckResult("v107_source_contract", "failed" if missing else "passed", {"missing": missing})


def _check_live_runtime(root: Path) -> CheckResult:
    try:
        root_text = str(root)
        if root_text not in sys.path:
            sys.path.insert(0, root_text)
        from dotenv import load_dotenv

        load_dotenv(root / ".env", override=True)
        from src.services.ollama_runtime_service import OllamaRuntimeService

        status = OllamaRuntimeService().get_status()
    except Exception as exc:
        return CheckResult("v107_live_ollama", "failed", {"reason": type(exc).__name__})
    safe_status = {
        key: status.get(key)
        for key in (
            "enabled",
            "reachable",
            "ready",
            "quick_ready",
            "deep_ready",
            "reason",
            "runtime",
            "quick_model",
            "deep_model",
            "max_concurrent",
        )
    }
    return CheckResult("v107_live_ollama", "passed" if status.get("ready") else "failed", safe_status)


def _run(check_id: str, cwd: Path, command: Sequence[str]) -> CheckResult:
    completed = subprocess.run(
        list(command),
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return CheckResult(
        check_id,
        "passed" if completed.returncode == 0 else "failed",
        {
            "returncode": completed.returncode,
            "stdout_tail": completed.stdout[-1200:],
            "stderr_tail": completed.stderr[-1200:],
        },
    )


def run_v107_checks(
    *,
    project_root: Path = REPO_ROOT,
    run_subprocess: bool = True,
    check_live_runtime: bool = True,
) -> list[CheckResult]:
    root = project_root.resolve()
    results = [_check_files(root), _check_contract(root)]
    if check_live_runtime:
        results.append(_check_live_runtime(root))
    if not run_subprocess:
        return results
    results.append(_run(
        "v107_backend_tests",
        root,
        [
            sys.executable,
            "-m",
            "unittest",
            "tests.test_ollama_runtime_service_v107",
            "tests.test_platform_ollama_status_api_v107",
            "tests.test_platform_ollama_analysis_v107",
            "tests.test_platform_ollama_local_retention_v107_verifier",
        ],
    ))
    npm = shutil.which("npm.cmd") or shutil.which("npm") or "npm"
    results.append(_run(
        "v107_frontend_tests",
        root / "apps/dsa-web",
        [
            npm,
            "test",
            "--",
            "src/api/__tests__/platform.test.ts",
            "src/components/retention/__tests__/LocalModelStatusV107.test.tsx",
            "src/pages/__tests__/HomePage.test.tsx",
        ],
    ))
    return results


def main() -> int:
    results = run_v107_checks()
    for result in results:
        print(f"[{'OK' if result.status == 'passed' else 'FAIL'}] {result.check_id}")
        print(f"  {json.dumps(result.details, ensure_ascii=False)}")
    if any(result.status == "failed" for result in results):
        print("DSA_PLATFORM_OLLAMA_LOCAL_RETENTION_V107_FAILED")
        return 1
    print(OK_MARKER)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
