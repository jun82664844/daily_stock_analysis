from __future__ import annotations

import tempfile
import unittest
from pathlib import Path


class PlatformKronosSandboxV58VerifierTestCase(unittest.TestCase):
    def _write_file(self, root: Path, rel_path: str, content: str = "ok\n") -> None:
        path = root / rel_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    def _write_minimal_tree(self, root: Path, *, include_service: bool = True) -> None:
        service_text = "\n".join(
            [
                "KronosForecastService" if include_service else "MissingService",
                "check_availability",
                "KRONOS_ENABLED",
                "KRONOS_MODEL_ID",
                "KRONOS_TOKENIZER_ID",
                "KRONOS_RECORD_PATH" if include_service else "record_path_missing",
                "model_unavailable",
                "model_disabled",
                "kronos_model_used",
                "public_search_used",
                "ai_used",
            ]
        )
        self._write_file(root, "src/services/kronos_forecast_service.py", service_text)
        self._write_file(root, "api/v1/endpoints/stocks.py", "kronos-forecast\nrequire_model\nKronosForecastService\n")
        self._write_file(root, "api/v1/schemas/basic_query.py", "KronosForecastResponse\nkronos_model_used\n")
        self._write_file(root, "api/middlewares/auth.py", "kronos-forecast\n")
        self._write_file(root, "tests/test_kronos_forecast_service_v58.py", "model_unavailable\npublic_search_used\n")
        self._write_file(root, "tests/test_kronos_forecast_api_v58.py", "kronos-forecast\nlogin_required\n")
        self._write_file(root, "tests/test_platform_kronos_sandbox_v58.py", "run_kronos_sandbox_v58_checks\n")
        self._write_file(root, "apps/dsa-web/src/api/stocks.ts", "kronosForecast\nKronosForecastResponse\n")
        self._write_file(root, "apps/dsa-web/src/api/__tests__/stocks.test.ts", "kronosForecast\nmodel_unavailable\n")
        self._write_file(
            root,
            "apps/dsa-web/src/pages/HomePage.tsx",
            "basic-query-kronos-run\nbasic-query-kronos-live-result\n"
            "basic-query-kronos-dependency-status\nbasic-query-kronos-backtest-summary\n",
        )
        self._write_file(root, "apps/dsa-web/src/pages/__tests__/HomePage.test.tsx", "basic-query-kronos-run\n")
        self._write_file(
            root,
            "docs/superpowers/plans/2026-07-06-dsa-v58-kronos-sandbox.md",
            "No-go\nlocal-only\nnot real payment\nnot investment advice\n"
            "Do not commit real API Key\nDSA_PLATFORM_KRONOS_SANDBOX_V58_OK\n",
        )

    def test_static_checks_pass_for_v58_tree(self) -> None:
        from scripts.verify_platform_kronos_sandbox_v58 import run_kronos_sandbox_v58_checks

        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
            root = Path(temp_dir)
            self._write_minimal_tree(root)

            results = run_kronos_sandbox_v58_checks(
                project_root=root,
                run_subprocess=False,
                run_frontend=False,
                live_url=None,
            )

        by_id = {result.check_id: result for result in results}
        self.assertEqual(by_id["v58_required_files_present"].status, "passed")
        self.assertEqual(by_id["v58_static_kronos_boundaries"].status, "passed")

    def test_static_checks_fail_without_kronos_record_marker(self) -> None:
        from scripts.verify_platform_kronos_sandbox_v58 import run_kronos_sandbox_v58_checks

        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
            root = Path(temp_dir)
            self._write_minimal_tree(root, include_service=False)

            results = run_kronos_sandbox_v58_checks(
                project_root=root,
                run_subprocess=False,
                run_frontend=False,
                live_url=None,
            )

        by_id = {result.check_id: result for result in results}
        self.assertEqual(by_id["v58_static_kronos_boundaries"].status, "failed")
        missing = by_id["v58_static_kronos_boundaries"].metadata["missing_markers"]
        self.assertIn("KRONOS_RECORD_PATH", missing)


if __name__ == "__main__":
    unittest.main()
