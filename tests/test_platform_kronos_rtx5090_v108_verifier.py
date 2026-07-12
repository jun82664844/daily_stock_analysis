from __future__ import annotations

import unittest
from pathlib import Path


class PlatformKronosRtx5090V108VerifierTestCase(unittest.TestCase):
    def test_static_checks_cover_runtime_metrics_and_information_boundary(self) -> None:
        from scripts.verify_platform_kronos_rtx5090_v108 import REPO_ROOT, run_static_checks

        checks = run_static_checks(REPO_ROOT)

        self.assertTrue(checks)
        self.assertTrue(all(item["passed"] for item in checks), checks)
        check_ids = {item["check_id"] for item in checks}
        self.assertIn("required_files", check_ids)
        self.assertIn("runtime_contract", check_ids)
        self.assertIn("information_only_boundary", check_ids)

    def test_verifier_is_not_hidden_by_gitignore(self) -> None:
        root = Path(__file__).resolve().parents[1]
        gitignore = (root / ".gitignore").read_text(encoding="utf-8")

        self.assertIn("!scripts/verify_platform_kronos_rtx5090_v108.py", gitignore)


if __name__ == "__main__":
    unittest.main()
