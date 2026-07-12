import io
import json
import os
import subprocess
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from urllib.error import HTTPError
from unittest.mock import patch


class LocalV1OperabilityCheckTestCase(unittest.TestCase):
    def test_checklist_covers_platform_operability_gates(self):
        from scripts.verify_local_v1_operability import build_operability_checks

        checks = build_operability_checks(
            python_exe="python-test",
            project_root="C:/repo",
            web_base_url="http://127.0.0.1:8018",
        )
        by_id = {check.id: check for check in checks}

        expected_ids = {
            "basic_query_no_ai",
            "feature_quota",
            "user_api_key_mode",
            "local_model_capacity",
            "security_boundaries",
            "billing_boundary",
            "admin_console_backend",
            "admin_console_frontend",
            "frontend_build",
            "live_health",
            "live_admin_page",
            "live_basic_snapshot",
        }
        self.assertTrue(expected_ids.issubset(by_id.keys()))
        self.assertIn("tests.test_basic_query_no_ai", by_id["basic_query_no_ai"].command)
        self.assertIn("tests.test_platform_ai_feature_quota", by_id["feature_quota"].command)
        self.assertIn("tests.test_platform_api_keys_product", by_id["user_api_key_mode"].command)
        self.assertIn("tests.test_local_model_router", by_id["local_model_capacity"].command)
        self.assertEqual(by_id["live_health"].url, "http://127.0.0.1:8018/health")
        self.assertEqual(by_id["live_admin_page"].url, "http://127.0.0.1:8018/admin")
        self.assertTrue(by_id["live_basic_snapshot"].optional)

    def test_frontend_checks_use_resolved_npm_cmd_on_windows(self):
        from scripts.verify_local_v1_operability import build_operability_checks

        def fake_which(name):
            return "C:/node/npm.cmd" if name == "npm.cmd" else None

        with patch("scripts.verify_local_v1_operability.sys.platform", "win32"), \
             patch("shutil.which", side_effect=fake_which):
            checks = build_operability_checks(project_root="C:/repo")

        by_id = {check.id: check for check in checks}
        self.assertEqual(by_id["admin_console_frontend"].command[0], "C:/node/npm.cmd")
        self.assertEqual(by_id["frontend_build"].command[0], "C:/node/npm.cmd")

    def test_command_checks_decode_subprocess_output_as_utf8_with_replacement(self):
        from scripts.verify_local_v1_operability import OperabilityCheck, _run_command_check

        completed = subprocess.CompletedProcess(args=["tool"], returncode=0, stdout="ok", stderr="")
        check = OperabilityCheck(
            id="command",
            title="Command",
            category="test",
            command=["tool"],
            cwd="C:/repo",
        )

        with patch("scripts.verify_local_v1_operability.subprocess.run", return_value=completed) as run_command:
            result = _run_command_check(check)

        kwargs = run_command.call_args.kwargs
        self.assertEqual(kwargs["encoding"], "utf-8")
        self.assertEqual(kwargs["errors"], "replace")
        self.assertEqual(kwargs["env"]["PLATFORM_CSRF_ENABLED"], "false")
        self.assertEqual(result.status, "passed")

    def test_dry_run_returns_serializable_plan_without_executing(self):
        from scripts.verify_local_v1_operability import run_operability_checks

        with patch("scripts.verify_local_v1_operability.subprocess.run") as run_command, \
             patch("scripts.verify_local_v1_operability.urlopen") as open_url:
            results = run_operability_checks(dry_run=True, include_optional=True)

        run_command.assert_not_called()
        open_url.assert_not_called()
        self.assertTrue(results)
        self.assertTrue(all(result.status == "planned" for result in results))
        encoded = json.dumps([result.to_dict() for result in results], ensure_ascii=False)
        self.assertIn("basic_query_no_ai", encoded)
        self.assertIn("live_basic_snapshot", encoded)

    def test_optional_live_market_check_is_skipped_by_default(self):
        from scripts.verify_local_v1_operability import run_operability_checks

        results = run_operability_checks(dry_run=True, include_optional=False)
        ids = {result.check.id for result in results}

        self.assertIn("live_health", ids)
        self.assertNotIn("live_basic_snapshot", ids)

    def test_optional_live_snapshot_skips_when_login_is_required_without_credentials(self):
        from scripts.verify_local_v1_operability import OperabilityCheck, _run_url_check

        check = OperabilityCheck(
            id="live_basic_snapshot",
            title="Snapshot",
            category="live",
            url="http://127.0.0.1:8018/api/v1/stocks/AAPL/snapshot",
            optional=True,
        )
        unauthorized = HTTPError(check.url, 401, "Unauthorized", hdrs=None, fp=None)

        with patch("scripts.verify_local_v1_operability.urlopen", side_effect=unauthorized), \
             patch.dict(
                 os.environ,
                 {
                     "DSA_OPERABILITY_PLATFORM_EMAIL": "",
                     "DSA_OPERABILITY_PLATFORM_PASSWORD": "",
                 },
                 clear=False,
             ):
            result = _run_url_check(check)

        self.assertEqual(result.status, "skipped")
        self.assertIn("DSA_OPERABILITY_PLATFORM_EMAIL", result.error)

    def test_optional_live_snapshot_uses_platform_login_credentials_when_available(self):
        from scripts.verify_local_v1_operability import OperabilityCheck, _run_url_check

        class FakeResponse:
            status = 200

            def __init__(self, body: bytes):
                self.body = body

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def getcode(self):
                return self.status

            def read(self, limit=-1):
                return self.body

        class FakeOpener:
            def __init__(self):
                self.requests = []

            def open(self, request, timeout=None):
                self.requests.append(request)
                if len(self.requests) == 1:
                    return FakeResponse(b'{"user":{"email":"smoke@example.com"}}')
                return FakeResponse(b'{"stock_code":"AAPL","ai_used":false}')

        check = OperabilityCheck(
            id="live_basic_snapshot",
            title="Snapshot",
            category="live",
            url="http://127.0.0.1:8018/api/v1/stocks/AAPL/snapshot",
            optional=True,
        )
        opener = FakeOpener()
        unauthorized = HTTPError(check.url, 401, "Unauthorized", hdrs=None, fp=None)

        with patch("scripts.verify_local_v1_operability.urlopen", side_effect=unauthorized), \
             patch("urllib.request.build_opener", return_value=opener), \
             patch.dict(
                 os.environ,
                 {
                     "DSA_OPERABILITY_PLATFORM_EMAIL": "smoke@example.com",
                     "DSA_OPERABILITY_PLATFORM_PASSWORD": "secret-password",
                 },
                 clear=False,
             ):
            result = _run_url_check(check)

        self.assertEqual(result.status, "passed")
        self.assertEqual(opener.requests[0].full_url, "http://127.0.0.1:8018/api/v1/platform/login")
        self.assertEqual(opener.requests[1].full_url, check.url)
        self.assertNotIn("secret-password", result.to_dict()["output"])

    def test_optional_live_snapshot_can_auto_register_local_smoke_user_when_explicitly_enabled(self):
        from scripts.verify_local_v1_operability import OperabilityCheck, _run_url_check

        class FakeResponse:
            status = 200

            def __init__(self, body: bytes):
                self.body = body

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def getcode(self):
                return self.status

            def read(self, limit=-1):
                return self.body

        class FakeOpener:
            def __init__(self):
                self.requests = []
                self.request_bodies = []

            def open(self, request, timeout=None):
                self.requests.append(request)
                body = getattr(request, "data", None)
                self.request_bodies.append(body.decode("utf-8") if body else "")
                if len(self.requests) == 1:
                    return FakeResponse(b'{"user":{"email":"e2e+local-smoke-test@example.com"}}')
                return FakeResponse(b'{"stock_code":"AAPL","ai_used":false}')

        check = OperabilityCheck(
            id="live_basic_snapshot",
            title="Snapshot",
            category="live",
            url="http://127.0.0.1:8018/api/v1/stocks/AAPL/snapshot",
            optional=True,
        )
        opener = FakeOpener()
        unauthorized = HTTPError(check.url, 401, "Unauthorized", hdrs=None, fp=None)

        with patch("scripts.verify_local_v1_operability.urlopen", side_effect=unauthorized), \
             patch("urllib.request.build_opener", return_value=opener), \
             patch.dict(
                 os.environ,
                 {
                     "DSA_OPERABILITY_PLATFORM_EMAIL": "",
                     "DSA_OPERABILITY_PLATFORM_PASSWORD": "",
                 },
                 clear=False,
             ):
            result = _run_url_check(check, auto_smoke_user=True)

        self.assertEqual(result.status, "passed")
        self.assertEqual(opener.requests[0].full_url, "http://127.0.0.1:8018/api/v1/platform/register")
        self.assertEqual(opener.requests[1].full_url, check.url)
        register_body = json.loads(opener.request_bodies[0])
        self.assertTrue(register_body["email"].startswith("e2e+local-smoke-"))
        self.assertNotIn(register_body["password"], json.dumps(result.to_dict()))
        self.assertEqual(result.metadata["auth"], "platform_auto_smoke_user")


    def test_cli_dry_run_json_prints_operability_plan(self):
        from scripts.verify_local_v1_operability import main

        stdout = io.StringIO()
        with redirect_stdout(stdout):
            exit_code = main(["--dry-run", "--json", "--include-optional"])

        self.assertEqual(exit_code, 0)
        payload = json.loads(stdout.getvalue())
        ids = {item["check"]["id"] for item in payload}
        self.assertIn("basic_query_no_ai", ids)
        self.assertIn("live_basic_snapshot", ids)

    def test_v2_readiness_checklist_covers_launch_package_gates(self):
        from scripts.verify_platform_v2_readiness import build_readiness_checks

        checks = build_readiness_checks(project_root="C:/repo")
        by_id = {check.id: check for check in checks}

        expected_ids = {
            "prod_env_template",
            "safe_config_flags",
            "security_scan_rules",
            "backup_restore_dry_run",
            "schema_migration_check",
            "launch_readiness_doc",
            "legal_copy_draft",
            "dirty_handoff_status",
        }
        self.assertTrue(expected_ids.issubset(by_id.keys()))
        self.assertTrue(any(path.endswith("platform-production-env.example") for path in by_id["prod_env_template"].paths))
        self.assertTrue(any(path.endswith("platform-v2-launch-readiness.md") for path in by_id["launch_readiness_doc"].paths))

    def test_v2_readiness_script_is_not_gitignored_for_handoff(self):
        script = Path(__file__).resolve().parents[1] / "scripts" / "verify_platform_v2_readiness.py"

        completed = subprocess.run(
            ["git", "check-ignore", "-q", str(script.relative_to(Path(__file__).resolve().parents[1]))],
            cwd=Path(__file__).resolve().parents[1],
            check=False,
        )

        self.assertNotEqual(completed.returncode, 0)

    def test_v2_dirty_handoff_check_uses_full_untracked_inventory(self):
        from scripts.verify_platform_v2_readiness import HANDOFF_DOC_REL, ReadinessCheck, _run_dirty_handoff_check

        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
            root = Path(temp_dir)
            doc = root / HANDOFF_DOC_REL
            doc.parent.mkdir(parents=True, exist_ok=True)
            doc.write_text("modified\nuntracked\nV1 platform\ndo not delete\n", encoding="utf-8")
            completed = subprocess.CompletedProcess(
                args=["git"],
                returncode=0,
                stdout=" M file.py\n?? docs/a.md\n?? docs/b.md\n",
                stderr="",
            )
            check = ReadinessCheck(
                "dirty_handoff_status",
                "Dirty work handoff status",
                "docs",
                paths=[HANDOFF_DOC_REL],
            )

            with patch("scripts.verify_platform_v2_readiness.subprocess.run", return_value=completed) as run_command:
                result = _run_dirty_handoff_check(check, root)

        self.assertEqual(result.status, "passed")
        self.assertIn("--untracked-files=all", run_command.call_args.args[0])
        self.assertEqual(result.metadata["modified_count"], 1)
        self.assertEqual(result.metadata["untracked_count"], 2)

    def test_v2_backup_restore_dry_run_uses_temp_databases(self):
        from scripts.verify_platform_v2_readiness import run_backup_restore_dry_run

        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
            result = run_backup_restore_dry_run(Path(temp_dir))

        self.assertEqual(result.status, "passed")
        self.assertEqual(result.metadata["source_row_count"], 1)
        self.assertEqual(result.metadata["restored_row_count"], 1)

    def test_v2_schema_check_covers_platform_tables_and_history_owner_column(self):
        from scripts.verify_platform_v2_readiness import run_schema_migration_check

        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
            result = run_schema_migration_check(Path(temp_dir))

        self.assertEqual(result.status, "passed")
        self.assertIn("platform_users", result.metadata["tables"])
        self.assertIn("platform_user_api_keys", result.metadata["tables"])
        self.assertIn("platform_usage_events", result.metadata["tables"])
        self.assertIn("platform_audit_events", result.metadata["tables"])
        self.assertIn("platform_user_id", result.metadata["analysis_history_columns"])


if __name__ == "__main__":
    unittest.main()
