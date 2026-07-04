import tempfile
import unittest
from pathlib import Path

from scripts.verify_platform_local_public_user_flow_v21 import (
    evaluate_public_user_flow_summary,
    run_local_public_user_flow_v21_checks,
)


class PlatformLocalPublicUserFlowV21TestCase(unittest.TestCase):
    def _valid_summary(self):
        return {
            "public_entry": {
                "reachable": True,
                "admin_login_visible": False,
                "admin_nav_visible": False,
                "login_required_error_visible": False,
            },
            "auth": {
                "registered": True,
                "logged_in": True,
                "password_exposed": False,
            },
            "account": {
                "status_code": 200,
                "email_matches": True,
                "masked_api_key_only": True,
                "quota_present": True,
                "quota_buckets_present": True,
            },
            "queries": {
                "600519": {"status_code": 200, "lane": "a_share_market_data", "ai_used": False},
                "AAPL": {"status_code": 200, "lane": "us_market_data", "ai_used": False},
                "HK00700": {"status_code": 200, "lane": "hk_market_data", "ai_used": False},
                "BTC-USD": {"status_code": 200, "lane": "crypto_market_data", "ai_used": False},
            },
            "watchlist": {
                "added": 4,
                "refresh_status_code": 200,
                "private": True,
                "ai_used": False,
            },
            "admin_boundary": {
                "ordinary_admin_status": 403,
                "admin_nav_visible": False,
            },
        }

    def test_evaluate_public_user_flow_summary_accepts_complete_local_flow(self):
        self.assertEqual(evaluate_public_user_flow_summary(self._valid_summary()), [])

    def test_evaluate_public_user_flow_summary_rejects_admin_visible_or_ai_quick_query(self):
        summary = self._valid_summary()
        summary["public_entry"]["admin_nav_visible"] = True
        summary["queries"]["AAPL"]["ai_used"] = True

        problems = evaluate_public_user_flow_summary(summary)

        self.assertIn("public_entry:admin_nav_visible", problems)
        self.assertIn("AAPL:ai_used_not_false", problems)

    def test_required_files_check_reports_missing_v21_plan(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
            results = run_local_public_user_flow_v21_checks(
                project_root=Path(temp_dir),
                run_subprocess=False,
                run_live=False,
            )

        by_id = {result.check_id: result for result in results}
        self.assertEqual(by_id["v21_required_files_present"].status, "failed")
        self.assertIn(
            "docs/superpowers/plans/2026-07-03-dsa-local-v21-public-user-flow.md",
            by_id["v21_required_files_present"].metadata["missing_files"],
        )


if __name__ == "__main__":
    unittest.main()
