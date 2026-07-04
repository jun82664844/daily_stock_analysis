# -*- coding: utf-8 -*-
"""Verify local platform user E2E, isolation, rate-limit, and cleanup gates."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Iterable


OK_MARKER = "DSA_PLATFORM_USER_E2E_V1_OK"


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _run_step(name: str, command: list[str], *, cwd: Path, env: dict[str, str] | None = None) -> None:
    executable = shutil.which(command[0])
    if executable is None and os.name == "nt":
        executable = shutil.which(f"{command[0]}.cmd")
    if executable is None:
        raise RuntimeError(f"{name} executable not found: {command[0]}")
    command = [executable, *command[1:]]
    print(f"[RUN] {name}: {' '.join(command)}")
    completed = subprocess.run(
        command,
        cwd=str(cwd),
        env=env,
        text=True,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
    )
    if completed.returncode != 0:
        sys.stdout.write(completed.stdout)
        sys.stderr.write(completed.stderr)
        raise RuntimeError(f"{name} failed with exit code {completed.returncode}")
    print(f"[OK] {name}")


def _cleanup_dry_run(repo_root: Path, python_executable: str) -> None:
    command = [
        python_executable,
        "scripts/cleanup_platform_e2e_data.py",
        "--email-prefix",
        "e2e+",
        "--json",
    ]
    print(f"[RUN] cleanup dry-run: {' '.join(command)}")
    completed = subprocess.run(
        command,
        cwd=str(repo_root),
        text=True,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
    )
    if completed.returncode != 0:
        sys.stdout.write(completed.stdout)
        sys.stderr.write(completed.stderr)
        raise RuntimeError(f"cleanup dry-run failed with exit code {completed.returncode}")
    payload = json.loads(completed.stdout)
    if payload.get("dry_run") is not True:
        raise RuntimeError("cleanup dry-run did not report dry_run=true")
    print(
        "[OK] cleanup dry-run: "
        f"matched_users={payload.get('matched_users')}, "
        f"api_keys={payload.get('api_keys')}, "
        f"usage_events={payload.get('usage_events')}, "
        f"analysis_history={payload.get('analysis_history')}"
    )


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run local DSA platform user E2E readiness checks.")
    parser.add_argument("--skip-playwright", action="store_true")
    parser.add_argument("--skip-backend", action="store_true")
    parser.add_argument("--skip-cleanup", action="store_true")
    args = parser.parse_args(list(argv) if argv is not None else None)

    repo_root = _repo_root()
    web_root = repo_root / "apps" / "dsa-web"
    python_executable = sys.executable

    if not args.skip_backend:
        _run_step(
            "backend user E2E safety tests",
            [python_executable, "-m", "unittest", "tests.test_platform_user_e2e_safety"],
            cwd=repo_root,
        )

    if not args.skip_playwright:
        env = os.environ.copy()
        env["DSA_PLATFORM_E2E"] = "1"
        _run_step(
            "platform browser E2E",
            ["npm", "run", "test:smoke", "--", "platform-user-e2e.spec.ts"],
            cwd=web_root,
            env=env,
        )

    if not args.skip_cleanup:
        _cleanup_dry_run(repo_root, python_executable)

    print(OK_MARKER)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
