from __future__ import annotations

import tempfile
import unittest
from pathlib import Path


class PlatformLocalProductExperienceV55VerifierTestCase(unittest.TestCase):
    def _write_file(self, root: Path, rel_path: str, content: str = "ok\n") -> None:
        path = root / rel_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    def _write_minimal_tree(self, root: Path, *, include_retention: bool = True) -> None:
        self._write_file(
            root,
            "src/services/basic_query_service.py",
            "\n".join(
                [
                    "no_ai_low_cost",
                    "retention_brief" if include_retention else "free_insights",
                    "_retention_brief_payload" if include_retention else "_free_insights_payload",
                    "no_ai_retention_rules" if include_retention else "no_ai_rules",
                    "not investment advice",
                ]
            ),
        )
        self._write_file(
            root,
            "api/v1/schemas/basic_query.py",
            "BasicRetentionBriefPayload\nretention_brief\n" if include_retention else "BasicIntelligencePayload\n",
        )
        self._write_file(
            root,
            "tests/test_basic_query_no_ai.py",
            "test_no_ai_snapshot_includes_retention_brief\nanalysis_service.assert_not_called()\n",
        )
        self._write_file(
            root,
            "apps/dsa-web/src/api/stocks.ts",
            "retentionBrief\nwhyItMatters\nsupportResistance\nnextSteps\nupgradeHint\n",
        )
        self._write_file(
            root,
            "apps/dsa-web/src/pages/HomePage.tsx",
            "\n".join(
                [
                    "guest-query-entry",
                    "guest-example-AAPL",
                    "guest-example-600519",
                    "guest-example-00700.HK",
                    "guest-example-BTC-USD",
                    "No login required",
                    "basic-query-retention-brief" if include_retention else "basic-query-free-report",
                    "guest-conversion-guide",
                    "guest-guide-register",
                    "Login is optional",
                    "save history",
                    "watchlist",
                    "weekly quota",
                ]
            ),
        )
        self._write_file(
            root,
            "apps/dsa-web/src/pages/__tests__/HomePage.test.tsx",
            "\n".join(
                [
                    "shows a guest-first query entry before login",
                    "lets guests query first and then shows a non-blocking login guide",
                    "basic-query-retention-brief" if include_retention else "basic-query-free-report",
                ]
            ),
        )
        self._write_file(
            root,
            "docs/superpowers/plans/2026-07-06-dsa-v55-local-product-experience.md",
            "local-only\nNo-go\nnot real payment\nnot investment advice\nDSA_PLATFORM_LOCAL_PRODUCT_EXPERIENCE_V55_OK\n",
        )

    def test_static_checks_pass_for_v55_tree(self) -> None:
        from scripts.verify_platform_local_product_experience_v55 import run_local_product_experience_checks

        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
            root = Path(temp_dir)
            self._write_minimal_tree(root)

            results = run_local_product_experience_checks(project_root=root, run_tests=False, live_url=None)

        by_id = {result.check_id: result for result in results}
        self.assertEqual(by_id["required_files_present"].status, "passed")
        self.assertEqual(by_id["static_product_experience_boundaries"].status, "passed")

    def test_static_checks_fail_without_retention_brief(self) -> None:
        from scripts.verify_platform_local_product_experience_v55 import run_local_product_experience_checks

        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
            root = Path(temp_dir)
            self._write_minimal_tree(root, include_retention=False)

            results = run_local_product_experience_checks(project_root=root, run_tests=False, live_url=None)

        by_id = {result.check_id: result for result in results}
        self.assertEqual(by_id["static_product_experience_boundaries"].status, "failed")
        missing = by_id["static_product_experience_boundaries"].metadata["missing_markers"]
        self.assertIn("_retention_brief_payload", missing)
        self.assertIn("basic-query-retention-brief", missing)


if __name__ == "__main__":
    unittest.main()
