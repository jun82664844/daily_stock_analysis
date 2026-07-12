from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Sequence


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
OK_MARKER = "DSA_PLATFORM_KRONOS_RTX5090_V108_OK"

REQUIRED_FILES = (
    "src/services/kronos_runtime.py",
    "src/services/kronos_forecast_service.py",
    "api/v1/endpoints/stocks.py",
    "api/v1/schemas/basic_query.py",
    "apps/dsa-web/src/api/stocks.ts",
    "apps/dsa-web/src/pages/HomePage.tsx",
    "tests/test_kronos_runtime_v108.py",
    "tests/test_platform_kronos_rtx5090_v108_verifier.py",
    "docs/superpowers/plans/2026-07-12-dsa-v108-kronos-rtx5090-runtime.md",
)

RUNTIME_MARKERS = (
    "KronosRuntime",
    "KRONOS_RUNTIME",
    "local_files_only",
    "model_cache_hit",
    "model_load_ms",
    "inference_ms",
    "peak_vram_mb",
    "allow_model",
    "basic-query-kronos-runtime-metrics",
)

BOUNDARY_MARKERS = (
    "information analysis only",
    "not investment advice",
    "require_model=true",
    "not consume the real Kronos runtime",
)

UNITTEST_MODULES = (
    "tests.test_kronos_runtime_v108",
    "tests.test_kronos_forecast_service_v58",
    "tests.test_kronos_forecast_api_v58",
    "tests.test_platform_kronos_rtx5090_v108_verifier",
)


def _check(check_id: str, passed: bool, **metadata: Any) -> dict[str, Any]:
    return {"check_id": check_id, "passed": bool(passed), "metadata": metadata}


def run_static_checks(root: Path) -> list[dict[str, Any]]:
    missing_files = [relative for relative in REQUIRED_FILES if not (root / relative).exists()]
    texts = []
    for relative in REQUIRED_FILES:
        path = root / relative
        if path.exists():
            texts.append(path.read_text(encoding="utf-8", errors="replace"))
    combined = "\n".join(texts)
    missing_runtime = [marker for marker in RUNTIME_MARKERS if marker not in combined]
    combined_lower = combined.lower()
    missing_boundaries = [marker for marker in BOUNDARY_MARKERS if marker.lower() not in combined_lower]
    return [
        _check("required_files", not missing_files, missing=missing_files),
        _check("runtime_contract", not missing_runtime, missing=missing_runtime),
        _check("information_only_boundary", not missing_boundaries, missing=missing_boundaries),
    ]


def run_unit_tests(root: Path, python_exe: str) -> dict[str, Any]:
    started = time.perf_counter()
    env = os.environ.copy()
    env["KRONOS_ENABLED"] = "false"
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
    return _check(
        "backend_tests",
        completed.returncode == 0,
        elapsed_ms=round((time.perf_counter() - started) * 1000, 1),
        returncode=completed.returncode,
        output_tail=(completed.stdout + completed.stderr)[-1500:],
    )


def run_frontend_tests(root: Path) -> dict[str, Any]:
    started = time.perf_counter()
    command = [
        "npm.cmd" if os.name == "nt" else "npm",
        "run",
        "test",
        "--",
        "--run",
        "src/api/__tests__/stocks.test.ts",
        "src/pages/__tests__/HomePage.test.tsx",
    ]
    completed = subprocess.run(
        command,
        cwd=root / "apps" / "dsa-web",
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    return _check(
        "frontend_tests",
        completed.returncode == 0,
        elapsed_ms=round((time.perf_counter() - started) * 1000, 1),
        returncode=completed.returncode,
        output_tail=(completed.stdout + completed.stderr)[-1500:],
    )


def run_real_model_probe(root: Path) -> dict[str, Any]:
    started = time.perf_counter()
    kronos_repo = root / "local" / "kronos"
    if str(kronos_repo) not in sys.path:
        sys.path.insert(0, str(kronos_repo))
    try:
        import torch

        from src.services.kronos_runtime import KronosRuntime

        rows = []
        for index in range(64):
            close = 100.0 + index * 0.2
            rows.append(
                {
                    "timestamp": f"2026-01-{(index % 28) + 1:02d}",
                    "open": close - 0.2,
                    "high": close + 0.8,
                    "low": close - 0.9,
                    "close": close,
                    "volume": 1_000_000 + index * 1000,
                    "amount": close * (1_000_000 + index * 1000),
                }
            )
        result = KronosRuntime().predict(
            rows,
            horizon=5,
            model_id="NeoQuasar/Kronos-mini",
            tokenizer_id="NeoQuasar/Kronos-Tokenizer-2k",
            device="cuda",
            max_context=512,
            local_files_only=True,
        )
        metrics = result["metrics"]
        passed = (
            torch.cuda.is_available()
            and "5090" in torch.cuda.get_device_name(0)
            and len(result["points"]) == 5
            and str(metrics["resolved_device"]).startswith("cuda")
        )
        return _check(
            "rtx5090_real_model_probe",
            passed,
            elapsed_ms=round((time.perf_counter() - started) * 1000, 1),
            gpu=torch.cuda.get_device_name(0) if torch.cuda.is_available() else "unavailable",
            metrics=metrics,
        )
    except Exception as exc:
        return _check(
            "rtx5090_real_model_probe",
            False,
            elapsed_ms=round((time.perf_counter() - started) * 1000, 1),
            error=f"{type(exc).__name__}: {exc}",
        )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify DSA V108 local Kronos RTX 5090 runtime.")
    parser.add_argument("--python-exe", default=sys.executable)
    parser.add_argument("--skip-tests", action="store_true")
    parser.add_argument("--run-model", action="store_true")
    args = parser.parse_args(argv)

    checks = run_static_checks(REPO_ROOT)
    if not args.skip_tests:
        checks.extend([run_unit_tests(REPO_ROOT, args.python_exe), run_frontend_tests(REPO_ROOT)])
    if args.run_model:
        checks.append(run_real_model_probe(REPO_ROOT))

    print(json.dumps({"checks": checks}, ensure_ascii=False, indent=2))
    if all(item["passed"] for item in checks):
        print(OK_MARKER)
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
