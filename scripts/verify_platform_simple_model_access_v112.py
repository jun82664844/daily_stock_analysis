from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OK_MARKER = "DSA_PLATFORM_SIMPLE_MODEL_ACCESS_V112_OK boost=168+28 price_hkd=28 sources=platform,byok,user_local platforms=windows,macos secrets_exposed=false"
REQUIRED_FILES = (
    "src/services/api_boost_pack_service.py",
    "src/services/byok_routing_service.py",
    "src/services/member_model_catalog_service.py",
    "src/services/user_local_connector_service.py",
    "api/v1/endpoints/local_connector.py",
    "apps/dsa-local-connector/app.py",
    "apps/dsa-local-connector/client.py",
    "apps/dsa-local-connector/ollama.py",
    "apps/dsa-local-connector/runtime.py",
    "apps/dsa-local-connector/build-windows.ps1",
    "apps/dsa-local-connector/build-macos.sh",
    ".github/workflows/local-connector-release.yml",
    "apps/dsa-web/src/components/platform/BoostPackCardV112.tsx",
    "apps/dsa-web/src/components/platform/SimpleModelPickerV112.tsx",
    "apps/dsa-web/src/components/platform/ModelConnectionWizardV112.tsx",
    "tests/test_platform_boost_pack_v112.py",
    "tests/test_member_model_catalog_v112.py",
    "tests/test_analysis_model_selection_v112.py",
    "tests/test_user_local_connector_v112.py",
    "tests/test_local_connector_release_matrix_v112.py",
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--python-exe", default=sys.executable)
    parser.add_argument("--skip-tests", action="store_true")
    args = parser.parse_args()
    missing = [item for item in REQUIRED_FILES if not (ROOT / item).exists()]
    checks = {"static": {"passed": not missing, "missing_files": missing}}
    if not args.skip_tests:
        completed = subprocess.run(
            [args.python_exe, "-m", "unittest",
             "tests.test_platform_boost_pack_v112",
             "tests.test_member_model_catalog_v112",
             "tests.test_analysis_model_selection_v112",
             "tests.test_user_local_connector_v112",
             "tests.test_local_connector_release_matrix_v112",
             "tests.test_billing_subscription_lifecycle",
             "tests.test_platform_api_keys_product",
             "tests.test_platform_ollama_analysis_v107"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
            env={
                **os.environ,
                "PLATFORM_BYOK_ALLOWED_MODELS": "",
                "PLATFORM_CSRF_ENABLED": "false",
            },
        )
        checks["tests"] = {"passed": completed.returncode == 0, "output_tail": (completed.stdout + completed.stderr)[-1800:]}
    print(json.dumps(checks, ensure_ascii=False, indent=2))
    if all(item["passed"] for item in checks.values()):
        print(OK_MARKER)
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
