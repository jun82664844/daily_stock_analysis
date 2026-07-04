import tempfile
import unittest
from pathlib import Path

from scripts.verify_platform_local_public_entry_v20 import (
    evaluate_public_entry_routes,
    run_local_public_entry_v20_checks,
)


class PlatformLocalPublicEntryV20TestCase(unittest.TestCase):
    def test_evaluate_public_entry_routes_accepts_user_home_and_admin_boundaries(self):
        problems = evaluate_public_entry_routes(
            {
                "/": {"requires_admin": False, "page": "home"},
                "/portfolio": {"requires_admin": False, "page": "portfolio"},
                "/chat": {"requires_admin": False, "page": "chat"},
                "/account": {"requires_admin": False, "page": "account"},
                "/usage": {"requires_admin": False, "page": "usage"},
                "/login": {"requires_admin": False, "admin_login": True},
                "/admin": {"requires_admin": True, "page": "admin"},
                "/settings": {"requires_admin": True, "page": "settings"},
            }
        )

        self.assertEqual([], problems)

    def test_evaluate_public_entry_routes_rejects_admin_gated_user_home(self):
        problems = evaluate_public_entry_routes(
            {
                "/": {"requires_admin": True, "page": "home"},
                "/login": {"requires_admin": False, "admin_login": True},
                "/admin": {"requires_admin": True, "page": "admin"},
                "/settings": {"requires_admin": True, "page": "settings"},
            }
        )

        self.assertIn("/:admin_gate_blocks_public_entry", problems)

    def test_required_files_check_reports_missing_v20_plan(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
            results = run_local_public_entry_v20_checks(
                project_root=Path(temp_dir),
                run_subprocess=False,
            )

        by_id = {result.check_id: result for result in results}
        self.assertEqual(by_id["v20_required_files_present"].status, "failed")
        self.assertIn(
            "docs/superpowers/plans/2026-07-03-dsa-local-v20-public-entry.md",
            by_id["v20_required_files_present"].metadata["missing_files"],
        )


if __name__ == "__main__":
    unittest.main()
