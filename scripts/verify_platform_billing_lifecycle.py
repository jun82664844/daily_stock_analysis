from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path
from typing import Sequence


REPO_ROOT = Path(__file__).resolve().parents[1]
OK_MARKER = "DSA_PLATFORM_BILLING_LIFECYCLE_V1_OK"

BACKEND_TESTS = (
    "tests.test_billing_api",
    "tests.test_billing_sandbox_flow",
    "tests.test_billing_subscription_lifecycle",
)


def run_billing_lifecycle_checks(*, project_root: str | Path | None = None) -> int:
    root = Path(project_root).resolve() if project_root is not None else REPO_ROOT
    command = [sys.executable, "-m", "unittest", *BACKEND_TESTS]
    completed = subprocess.run(
        command,
        cwd=root,
        check=False,
        env={**os.environ, "PLATFORM_CSRF_ENABLED": "false"},
    )
    if completed.returncode != 0:
        return completed.returncode
    print(OK_MARKER)
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify local sandbox billing lifecycle closure")
    parser.add_argument("--project-root", default=str(REPO_ROOT), help="DSA project root")
    args = parser.parse_args(argv)
    return run_billing_lifecycle_checks(project_root=args.project_root)


if __name__ == "__main__":
    raise SystemExit(main())
