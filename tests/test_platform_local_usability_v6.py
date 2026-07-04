# -*- coding: utf-8 -*-
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


def _fake_result(check_id: str, status: str = "passed", *, optional: bool = False):
    return SimpleNamespace(
        check_id=check_id,
        title=check_id,
        status=status,
        elapsed_sec=0.0,
        error="",
        metadata={},
        optional=optional,
        to_dict=lambda: {
            "check_id": check_id,
            "title": check_id,
            "status": status,
            "elapsed_sec": 0.0,
            "error": "",
            "metadata": {},
            "optional": optional,
        },
    )


class PlatformLocalUsabilityV6VerifierTestCase(unittest.TestCase):
    def _write_file(self, root: Path, rel_path: str, content: str = "ok\n") -> None:
        path = root / rel_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    def _write_minimal_package(self, root: Path, *, include_v6_script: bool = True) -> None:
        safety_doc = (
            "No-go\n"
            "sandbox billing is local only\n"
            "not real payment\n"
            "not investment advice\n"
            "Do not commit real API Key\n"
            "DSA_PLATFORM_LOCAL_FUNCTIONAL_V5_OK\n"
            "DSA_PLATFORM_LOCAL_USABILITY_V6_OK\n"
        )
        for rel_path in (
            "docs/superpowers/platform-local-v1-acceptance-status.md",
            "docs/superpowers/platform-review-slices.md",
            "docs/superpowers/platform-release-candidate-manifest.md",
            "docs/superpowers/platform-product-rules.md",
            "docs/superpowers/plans/2026-07-02-dsa-local-v5-operability.md",
            "docs/superpowers/plans/2026-07-02-dsa-local-v6-usability.md",
        ):
            self._write_file(root, rel_path, safety_doc)
        for rel_path in (
            "scripts/verify_local_v1_operability.py",
            "scripts/verify_platform_query_quality_v4.py",
            "scripts/verify_platform_user_e2e.py",
            "scripts/verify_platform_billing_lifecycle.py",
            "scripts/verify_platform_release_candidate_package.py",
            "scripts/verify_platform_local_functional_v5.py",
            "tests/test_platform_local_functional_v5.py",
            "tests/test_platform_local_usability_v6.py",
            "tests/test_platform_query_quality_v4.py",
            "tests/test_platform_user_journey.py",
            "tests/test_billing_sandbox_flow.py",
            "tests/test_billing_subscription_lifecycle.py",
            "apps/dsa-web/src/pages/HomePage.tsx",
            "apps/dsa-web/src/pages/AccountPage.tsx",
            "apps/dsa-web/src/pages/AdminPage.tsx",
            "apps/dsa-web/src/components/layout/SidebarNav.tsx",
            "apps/dsa-web/src/api/stocks.ts",
            "apps/dsa-web/src/api/platform.ts",
        ):
            self._write_file(root, rel_path, "# local usability v6\n")
        if include_v6_script:
            self._write_file(root, "scripts/verify_platform_local_usability_v6.py", "# verifier\n")

    def _run_with_fake_git(self, root: Path, *, ignored_paths: set[str] | None = None):
        from scripts.verify_platform_local_usability_v6 import run_local_usability_v6_checks

        ignored_paths = ignored_paths or set()

        def fake_run(args, **kwargs):
            if args[:3] == ["git", "check-ignore", "-q"]:
                returncode = 0 if args[-1] in ignored_paths else 1
                return subprocess.CompletedProcess(args=args, returncode=returncode, stdout="", stderr="")
            raise AssertionError(f"unexpected command: {args}")

        with patch("scripts.verify_platform_local_usability_v6.subprocess.run", side_effect=fake_run):
            return run_local_usability_v6_checks(
                project_root=root,
                run_subprocess=False,
                run_live=False,
                v5_results=[
                    _fake_result("live_health"),
                    _fake_result("live_page_shell"),
                    _fake_result("live_platform_smoke"),
                    _fake_result("optional_live_snapshot", "degraded", optional=True),
                ],
            )

    def test_verifier_reports_missing_v6_script(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
            root = Path(temp_dir)
            self._write_minimal_package(root, include_v6_script=False)

            results = self._run_with_fake_git(root)

        by_id = {result.check_id: result for result in results}
        self.assertEqual(by_id["required_files_present"].status, "failed")
        self.assertIn(
            "scripts/verify_platform_local_usability_v6.py",
            by_id["required_files_present"].metadata["missing_files"],
        )

    def test_verifier_reports_gitignored_v6_verifier(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
            root = Path(temp_dir)
            self._write_minimal_package(root)

            results = self._run_with_fake_git(
                root,
                ignored_paths={"scripts/verify_platform_local_usability_v6.py"},
            )

        by_id = {result.check_id: result for result in results}
        self.assertEqual(by_id["verifiers_visible_to_git"].status, "failed")
        self.assertIn(
            "scripts/verify_platform_local_usability_v6.py",
            by_id["verifiers_visible_to_git"].metadata["ignored_files"],
        )

    def test_verifier_fails_when_v5_live_platform_smoke_is_degraded(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
            root = Path(temp_dir)
            self._write_minimal_package(root)

            from scripts.verify_platform_local_usability_v6 import run_local_usability_v6_checks

            results = run_local_usability_v6_checks(
                project_root=root,
                run_subprocess=False,
                run_live=False,
                v5_results=[
                    _fake_result("live_health"),
                    _fake_result("live_page_shell"),
                    _fake_result("live_platform_smoke", "degraded"),
                    _fake_result("optional_live_snapshot", "degraded", optional=True),
                ],
            )

        by_id = {result.check_id: result for result in results}
        self.assertEqual(by_id["v5_required_live_gate"].status, "failed")
        self.assertIn("live_platform_smoke", by_id["v5_required_live_gate"].metadata["bad_required_checks"])

    def test_verifier_allows_optional_live_snapshot_degradation(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
            root = Path(temp_dir)
            self._write_minimal_package(root)

            from scripts.verify_platform_local_usability_v6 import run_local_usability_v6_checks

            results = run_local_usability_v6_checks(
                project_root=root,
                run_subprocess=False,
                run_live=False,
                v5_results=[
                    _fake_result("live_health"),
                    _fake_result("live_page_shell"),
                    _fake_result("live_platform_smoke"),
                    _fake_result("optional_live_snapshot", "degraded", optional=True),
                ],
            )

        by_id = {result.check_id: result for result in results}
        self.assertEqual(by_id["v5_required_live_gate"].status, "passed")
        self.assertEqual(by_id["v5_optional_live_degradation"].status, "degraded")
        self.assertFalse(any(result.status == "failed" for result in results))

    def test_script_path_execution_can_import_v5_verifier(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
            root = Path(temp_dir)
            self._write_minimal_package(root)

            completed = subprocess.run(
                [
                    sys.executable,
                    str(Path(__file__).resolve().parents[1] / "scripts" / "verify_platform_local_usability_v6.py"),
                    "--project-root",
                    str(root),
                    "--skip-subprocess",
                    "--skip-live",
                    "--json",
                ],
                cwd=Path(__file__).resolve().parents[1],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                check=False,
            )

        self.assertEqual(completed.returncode, 0, completed.stderr + completed.stdout)
        self.assertIn("DSA_PLATFORM_LOCAL_USABILITY_V6_OK", completed.stdout)

    def test_multi_market_snapshot_evaluator_accepts_no_ai_expected_lanes(self) -> None:
        from scripts.verify_platform_local_usability_v6 import evaluate_market_snapshot_results

        bad = evaluate_market_snapshot_results(
            {
                "600519": {"status_code": 200, "market": "cn", "ai_used": False, "lane": "a_share_market_data"},
                "AAPL": {"status_code": 200, "market": "us", "ai_used": False, "lane": "us_market_data"},
                "HK00700": {"status_code": 200, "market": "hk", "ai_used": False, "lane": "hk_market_data"},
                "BTC-USD": {"status_code": 200, "market": "crypto", "ai_used": False, "lane": "crypto_market_data"},
            }
        )

        self.assertEqual(bad, [])

    def test_multi_market_snapshot_evaluator_degrades_on_timeout_or_wrong_lane(self) -> None:
        from scripts.verify_platform_local_usability_v6 import evaluate_market_snapshot_results

        bad = evaluate_market_snapshot_results(
            {
                "600519": {"status_code": 200, "market": "cn", "ai_used": False, "lane": "a_share_market_data"},
                "AAPL": {"status_code": 200, "market": "us", "ai_used": False, "lane": "us_market_data"},
                "HK00700": {"error": "timed out"},
                "BTC-USD": {"status_code": 200, "market": "crypto", "ai_used": True, "lane": "crypto_market_data"},
            }
        )

        self.assertIn("HK00700", bad)
        self.assertIn("BTC-USD", bad)


if __name__ == "__main__":
    unittest.main()
