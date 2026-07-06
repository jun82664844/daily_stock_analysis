from __future__ import annotations

import tempfile
import unittest
from pathlib import Path


class PlatformLocalUserAcceptanceV54VerifierTestCase(unittest.TestCase):
    def _write_file(self, root: Path, rel_path: str, content: str = "ok\n") -> None:
        path = root / rel_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    def _write_minimal_tree(self, root: Path, *, include_hk_fallback: bool = True) -> None:
        basic_query = "\n".join(
            [
                "a_share_market_data",
                "us_market_data",
                "hk_market_data",
                "crypto_market_data",
                "no_ai_low_cost",
                "quote_from_history_close" if include_hk_fallback else "missing_quote",
                "_quote_from_history_close_fallback" if include_hk_fallback else "_quote_payload",
            ]
        )
        self._write_file(root, "src/services/basic_query_service.py", basic_query)
        self._write_file(
            root,
            "tests/test_basic_query_no_ai.py",
            "\n".join(
                [
                    "test_snapshot_is_public_without_platform_login",
                    "test_hk_snapshot_uses_history_close_when_realtime_quote_is_missing"
                    if include_hk_fallback
                    else "test_snapshot_returns_market_data_without_analysis_service",
                    "analysis_service.assert_not_called()",
                ]
            ),
        )
        self._write_file(root, "tests/test_platform_query_quality_v4.py", "hk_market_data\ncrypto_market_data\n")
        self._write_file(
            root,
            "apps/dsa-web/src/pages/HomePage.tsx",
            "\n".join(
                [
                    "basic-query-primary-summary",
                    "basic-query-free-report",
                    "basic-query-mini-chart",
                    "basic-query-signal-score",
                    "basic-query-intelligence-panel",
                    "basic-query-market-brief",
                    "basic-query-free-insights",
                    "basic-query-peer-comparison",
                    "basic-query-watch-points",
                    "basic-query-product-brief",
                    "basic-query-user-guardrails",
                    "No AI",
                ]
            ),
        )
        self._write_file(
            root,
            "apps/dsa-web/src/pages/__tests__/HomePage.test.tsx",
            "basic-query-free-report\nbasic-query-signal-score\nnot investment advice\n",
        )
        self._write_file(root, "apps/dsa-web/src/api/stocks.ts", "BasicStockSnapshot\nintelligence\n")
        self._write_file(
            root,
            "docs/superpowers/plans/2026-07-06-dsa-v54-local-user-acceptance.md",
            "anonymous\nNo AI\nnot investment advice\nDSA_PLATFORM_LOCAL_USER_ACCEPTANCE_V54_OK\n",
        )

    def test_static_checks_pass_for_v54_tree(self) -> None:
        from scripts.verify_platform_local_user_acceptance_v54 import run_local_user_acceptance_checks

        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
            root = Path(temp_dir)
            self._write_minimal_tree(root)

            results = run_local_user_acceptance_checks(project_root=root, run_tests=False, live_url=None)

        by_id = {result.check_id: result for result in results}
        self.assertEqual(by_id["required_files_present"].status, "passed")
        self.assertEqual(by_id["static_user_acceptance_boundaries"].status, "passed")

    def test_static_checks_fail_without_hk_history_close_fallback(self) -> None:
        from scripts.verify_platform_local_user_acceptance_v54 import run_local_user_acceptance_checks

        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
            root = Path(temp_dir)
            self._write_minimal_tree(root, include_hk_fallback=False)

            results = run_local_user_acceptance_checks(project_root=root, run_tests=False, live_url=None)

        by_id = {result.check_id: result for result in results}
        self.assertEqual(by_id["static_user_acceptance_boundaries"].status, "failed")
        self.assertIn("quote_from_history_close", by_id["static_user_acceptance_boundaries"].metadata["missing_markers"])


if __name__ == "__main__":
    unittest.main()
