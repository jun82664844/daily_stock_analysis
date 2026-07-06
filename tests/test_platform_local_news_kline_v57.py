from __future__ import annotations

import tempfile
import unittest
from pathlib import Path


class PlatformLocalNewsKlineV57VerifierTestCase(unittest.TestCase):
    def _write_file(self, root: Path, rel_path: str, content: str = "ok\n") -> None:
        path = root / rel_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    def _write_minimal_tree(self, root: Path, *, include_kline: bool = True) -> None:
        self._write_file(
            root,
            "src/services/basic_query_service.py",
            "\n".join(
                [
                    "news_center",
                    "_news_center_payload",
                    "public_search_used",
                    "no_ai_news_center_rules",
                    "kline_forecast" if include_kline else "retention_brief",
                    "_kline_forecast_payload" if include_kline else "_retention_brief_payload",
                    "local_kline_rules_kronos_ready" if include_kline else "no_ai_retention_rules",
                    "Kronos adapter ready" if include_kline else "No model",
                    "kronos_model_used" if include_kline else "ai_used",
                    "Premium" if include_kline else "free",
                    "not investment advice",
                ]
            ),
        )
        self._write_file(
            root,
            "api/v1/schemas/basic_query.py",
            (
                "BasicNewsCenterPayload\nBasicNewsCenterItemPayload\nnews_center\n"
                "BasicKlineForecastPayload\nBasicKlineForecastScenarioPayload\nkline_forecast\n"
                if include_kline
                else "BasicIntelligencePayload\nnews_center\n"
            ),
        )
        self._write_file(
            root,
            "tests/test_basic_query_no_ai.py",
            (
                "test_no_ai_snapshot_includes_news_center_and_kline_forecast_lab\n"
                "news_center\nkline_forecast\nanalysis_service.assert_not_called()\n"
                if include_kline
                else "test_no_ai_snapshot_includes_retention_brief\n"
            ),
        )
        self._write_file(
            root,
            "tests/test_platform_local_news_kline_v57.py",
            (
                "run_local_news_kline_v57_checks\n"
                "basic-query-news-center\nbasic-query-kline-forecast-lab\n"
                if include_kline
                else "run_local_news_kline_v57_checks\n"
            ),
        )
        self._write_file(
            root,
            "apps/dsa-web/src/api/stocks.ts",
            (
                "newsCenter\npublicSearchUsed\nklineForecast\nadapterStatus\n"
                "kronosModelUsed\npremiumUnlock\n"
                if include_kline
                else "newsCenter\n"
            ),
        )
        self._write_file(
            root,
            "apps/dsa-web/src/api/__tests__/stocks.test.ts",
            (
                "news_center\npublic_search_used\nkline_forecast\nadapter_status\n"
                "kronos_model_used\nnewsCenter\nklineForecast\n"
                if include_kline
                else "news_center\n"
            ),
        )
        self._write_file(
            root,
            "apps/dsa-web/src/pages/HomePage.tsx",
            (
                "basic-query-news-center\nbasic-query-kline-forecast-lab\n"
                "basic-query-premium-feature-ladder\nKronos-ready\nNo public search\n"
                if include_kline
                else "basic-query-news-center\n"
            ),
        )
        self._write_file(
            root,
            "apps/dsa-web/src/pages/__tests__/HomePage.test.tsx",
            (
                "basic-query-news-center\nbasic-query-kline-forecast-lab\n"
                "basic-query-premium-feature-ladder\nKronos-ready\n"
                if include_kline
                else "basic-query-news-center\n"
            ),
        )
        self._write_file(
            root,
            "docs/superpowers/plans/2026-07-06-dsa-v57-news-kline-forecast-lab.md",
            (
                "local-only\nNo real payment\nDo not commit real API Key\n"
                "No AI calls\nNo public search\nKronos-ready\nnot investment advice\n"
                "DSA_PLATFORM_LOCAL_NEWS_KLINE_V57_OK\n"
            ),
        )

    def test_static_checks_pass_for_v57_tree(self) -> None:
        from scripts.verify_platform_local_news_kline_v57 import run_local_news_kline_v57_checks

        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
            root = Path(temp_dir)
            self._write_minimal_tree(root)

            results = run_local_news_kline_v57_checks(project_root=root, run_subprocess=False, live_url=None)

        by_id = {result.check_id: result for result in results}
        self.assertEqual(by_id["v57_required_files_present"].status, "passed")
        self.assertEqual(by_id["v57_static_news_kline_boundaries"].status, "passed")

    def test_static_checks_fail_without_kline_forecast(self) -> None:
        from scripts.verify_platform_local_news_kline_v57 import run_local_news_kline_v57_checks

        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
            root = Path(temp_dir)
            self._write_minimal_tree(root, include_kline=False)

            results = run_local_news_kline_v57_checks(project_root=root, run_subprocess=False, live_url=None)

        by_id = {result.check_id: result for result in results}
        self.assertEqual(by_id["v57_static_news_kline_boundaries"].status, "failed")
        missing = by_id["v57_static_news_kline_boundaries"].metadata["missing_markers"]
        self.assertIn("_kline_forecast_payload", missing)
        self.assertIn("basic-query-kline-forecast-lab", missing)


if __name__ == "__main__":
    unittest.main()
