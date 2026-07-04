# -*- coding: utf-8 -*-
import hashlib
import hmac
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from api.app import create_app
from src.config import Config
from src.platform_accounts import PlatformAccountService
from src.services.basic_query_service import BasicQueryService
from src.services.market_data_cache import MarketDataCache
from src.storage import DatabaseManager


SANDBOX_SECRET = "local-functional-v5-secret"


def _json_body(payload: dict) -> bytes:
    return json.dumps(payload, separators=(",", ":")).encode("utf-8")


def _signature(body: bytes) -> str:
    return hmac.new(SANDBOX_SECRET.encode("utf-8"), body, hashlib.sha256).hexdigest()


def _history_rows(count: int = 24) -> list[dict]:
    return [
        {
            "date": f"2026-06-{day:02d}",
            "open": 90.0 + day,
            "high": 92.0 + day,
            "low": 89.0 + day,
            "close": 91.0 + day,
            "volume": 1000 + day * 10,
        }
        for day in range(1, count + 1)
    ]


def _quote(code: str, *, name: str | None = None) -> dict:
    return {
        "stock_code": code,
        "stock_name": name or code,
        "current_price": 120.0,
        "change_percent": 1.2,
        "volume": 123456,
        "amount": 456789.0,
        "source": "unit-test",
        "update_time": "2026-07-02T09:30:00",
    }


def _analysis_payload(stock_code: str = "AAPL") -> dict:
    return {
        "stock_code": stock_code,
        "stock_name": stock_code,
        "report": {
            "meta": {"stock_code": stock_code, "stock_name": stock_code, "report_language": "en"},
            "summary": {"analysis_summary": "informational test summary"},
            "strategy": {},
            "details": {},
        },
    }


def _history_result(stock_code: str = "AAPL") -> SimpleNamespace:
    return SimpleNamespace(
        code=stock_code,
        name=stock_code,
        sentiment_score=50,
        operation_advice="hold",
        trend_prediction="sideways",
        analysis_summary="informational test summary",
        news_summary="",
        technical_analysis="",
        fundamental_analysis="",
        risk_warning="",
        data_sources="unit-test",
        raw_response=None,
        success=True,
    )


class PlatformLocalFunctionalV5VerifierTestCase(unittest.TestCase):
    def _write_file(self, root: Path, rel_path: str, content: str = "ok\n") -> None:
        path = root / rel_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    def _write_minimal_package(self, root: Path, *, include_v5_script: bool = True) -> None:
        safety_doc = (
            "No-go\n"
            "sandbox billing is local only\n"
            "not investment advice\n"
            "Do not commit real API Key\n"
            "DSA_PLATFORM_LOCAL_FUNCTIONAL_V5_OK\n"
        )
        for rel_path in (
            "docs/superpowers/platform-local-v1-acceptance-status.md",
            "docs/superpowers/platform-review-slices.md",
            "docs/superpowers/platform-release-candidate-manifest.md",
            "docs/superpowers/platform-product-rules.md",
            "docs/superpowers/plans/2026-07-02-dsa-local-v5-operability.md",
        ):
            self._write_file(root, rel_path, safety_doc)
        for rel_path in (
            "scripts/verify_local_v1_operability.py",
            "scripts/verify_platform_query_quality_v4.py",
            "scripts/verify_platform_user_e2e.py",
            "scripts/verify_platform_billing_lifecycle.py",
            "scripts/verify_platform_release_candidate_package.py",
            "tests/test_platform_local_functional_v5.py",
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
            self._write_file(root, rel_path, "# local functional v5\n")
        if include_v5_script:
            self._write_file(root, "scripts/verify_platform_local_functional_v5.py", "# verifier\n")

    def _run_with_fake_git(self, root: Path, *, ignored_paths: set[str] | None = None):
        from scripts.verify_platform_local_functional_v5 import run_local_functional_v5_checks

        ignored_paths = ignored_paths or set()

        def fake_run(args, **kwargs):
            if args[:3] == ["git", "check-ignore", "-q"]:
                returncode = 0 if args[-1] in ignored_paths else 1
                return subprocess.CompletedProcess(args=args, returncode=returncode, stdout="", stderr="")
            raise AssertionError(f"unexpected command: {args}")

        with patch("scripts.verify_platform_local_functional_v5.subprocess.run", side_effect=fake_run):
            return run_local_functional_v5_checks(
                project_root=root,
                run_subprocess=False,
                run_live=False,
            )

    def test_verifier_reports_missing_v5_script(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
            root = Path(temp_dir)
            self._write_minimal_package(root, include_v5_script=False)

            results = self._run_with_fake_git(root)

        by_id = {result.check_id: result for result in results}
        self.assertEqual(by_id["required_files_present"].status, "failed")
        self.assertIn(
            "scripts/verify_platform_local_functional_v5.py",
            by_id["required_files_present"].metadata["missing_files"],
        )

    def test_verifier_reports_gitignored_v5_verifier(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
            root = Path(temp_dir)
            self._write_minimal_package(root)

            results = self._run_with_fake_git(
                root,
                ignored_paths={"scripts/verify_platform_local_functional_v5.py"},
            )

        by_id = {result.check_id: result for result in results}
        self.assertEqual(by_id["verifiers_visible_to_git"].status, "failed")
        self.assertIn(
            "scripts/verify_platform_local_functional_v5.py",
            by_id["verifiers_visible_to_git"].metadata["ignored_files"],
        )


class PlatformLocalFunctionalV5SmokeTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.db_path = os.path.join(self.temp_dir.name, "local-functional-v5.sqlite")
        self.static_dir = Path(self.temp_dir.name) / "static"
        self.static_dir.mkdir()
        (self.static_dir / "index.html").write_text("<html>ok</html>", encoding="utf-8")
        DatabaseManager.reset_instance()
        Config.reset_instance()
        self.env_patch = patch.dict(
            os.environ,
            {
                "DATABASE_PATH": self.db_path,
                "PLATFORM_USER_AUTH_ENABLED": "true",
                "ADMIN_AUTH_ENABLED": "true",
                "BILLING_ENABLED": "true",
                "BILLING_PROVIDER": "sandbox",
                "BILLING_SANDBOX_SECRET": SANDBOX_SECRET,
                "SEARXNG_PUBLIC_INSTANCES_ENABLED": "false",
            },
            clear=False,
        )
        self.env_patch.start()
        self.client = TestClient(create_app(static_dir=self.static_dir))

    def tearDown(self) -> None:
        self.client.close()
        self.env_patch.stop()
        DatabaseManager.reset_instance()
        Config.reset_instance()
        self.temp_dir.cleanup()

    def _register(self, email: str) -> int:
        response = self.client.post(
            "/api/v1/platform/register",
            json={"email": email, "password": "password123"},
        )
        self.assertEqual(response.status_code, 200)
        return int(response.json()["user"]["id"])

    def test_local_user_flow_routes_quota_history_billing_and_no_secret_leak(self) -> None:
        user_id = self._register("local-v5-a@example.com")
        other_user = PlatformAccountService().create_user("local-v5-b@example.com", "password123")
        PlatformAccountService().set_user_plan(user_id, "pro")

        key_response = self.client.post(
            "/api/v1/platform/api-keys",
            json={"provider": "deepseek", "apiKey": "sk-local-functional-v5-secret", "model": "deepseek/local-v5"},
        )
        self.assertEqual(key_response.status_code, 200)
        self.assertNotIn("sk-local-functional-v5-secret", str(key_response.json()))

        stock_service = MagicMock()
        stock_service.get_realtime_quote.side_effect = lambda code: _quote(code)
        stock_service.get_history_data.side_effect = lambda code, **_: {
            "stock_code": code,
            "stock_name": code,
            "data": _history_rows(),
        }
        route_service = BasicQueryService(stock_service=stock_service, cache=MarketDataCache(default_ttl_seconds=60))
        expected_routes = {
            "600519": ("cn", "a_share", "a_share_market_data"),
            "AAPL": ("us", "us_equity", "us_market_data"),
            "HK00700": ("hk", "hk_equity", "hk_market_data"),
            "BTC-USD": ("crypto", "crypto_spot", "crypto_market_data"),
        }
        for raw_code, (market, channel, lane) in expected_routes.items():
            snapshot = route_service.get_snapshot(raw_code)
            self.assertEqual(snapshot["market"], market)
            self.assertEqual(snapshot["route"]["channel"], channel)
            self.assertEqual(snapshot["route"]["data_source_lane"], lane)
            self.assertFalse(snapshot["ai_used"])
            self.assertFalse(snapshot["route"]["ai_required"])

        before_account = self.client.get("/api/v1/platform/account")
        self.assertEqual(before_account.status_code, 200)
        before_buckets = {bucket["quota_bucket"]: bucket for bucket in before_account.json()["quota_buckets"]}
        self.assertEqual(before_buckets["ai_quick"]["used"], 0)
        self.assertEqual(before_buckets["ai_deep"]["used"], 0)

        analysis_service = MagicMock()
        analysis_service.last_error = None
        analysis_service.analyze_stock.return_value = _analysis_payload("AAPL")
        with patch("src.services.analysis_service.AnalysisService", return_value=analysis_service), \
             patch("api.v1.endpoints.analysis._load_sync_fundamental_sources", return_value=(None, None)):
            platform_deep = self.client.post(
                "/api/v1/analysis/analyze",
                json={"stock_code": "AAPL", "async_mode": False, "analysisDepth": "deep"},
            )
            byok_deep = self.client.post(
                "/api/v1/analysis/analyze",
                json={
                    "stock_code": "AAPL",
                    "async_mode": False,
                    "analysisDepth": "deep",
                    "apiKeyMode": "user",
                },
            )
            local_quick = self.client.post(
                "/api/v1/analysis/analyze",
                json={
                    "stock_code": "AAPL",
                    "async_mode": False,
                    "analysisDepth": "fast",
                    "apiKeyMode": "local",
                },
            )

        self.assertEqual(platform_deep.status_code, 200)
        self.assertEqual(byok_deep.status_code, 200)
        self.assertEqual(local_quick.status_code, 200)
        account = self.client.get("/api/v1/platform/account")
        self.assertEqual(account.status_code, 200)
        buckets = {bucket["quota_bucket"]: bucket for bucket in account.json()["quota_buckets"]}
        self.assertEqual(buckets["ai_deep"]["used"], 3)
        self.assertEqual(buckets["ai_deep_user_key"]["used"], 1)
        self.assertEqual(buckets["ai_local"]["used"], 1)
        self.assertEqual(buckets["ai_quick"]["used"], 0)
        self.assertNotIn("sk-local-functional-v5-secret", str(account.json()))

        DatabaseManager.get_instance().save_analysis_history(
            result=_history_result("AAPL"),
            query_id="local-v5-owner-history",
            report_type="detailed",
            news_content=None,
            platform_user_id=user_id,
        )
        DatabaseManager.get_instance().save_analysis_history(
            result=_history_result("MSFT"),
            query_id="local-v5-other-history",
            report_type="detailed",
            news_content=None,
            platform_user_id=int(other_user.id),
        )
        history = self.client.get("/api/v1/history")
        self.assertEqual(history.status_code, 200)
        history_text = str(history.json())
        self.assertIn("local-v5-owner-history", history_text)
        self.assertNotIn("local-v5-other-history", history_text)

        admin_forbidden = self.client.get("/api/v1/platform/admin/users")
        self.assertEqual(admin_forbidden.status_code, 403)

        checkout = self.client.post("/api/v1/billing/checkout", json={"plan": "pro"})
        self.assertEqual(checkout.status_code, 200)
        payload = {
            "event": "checkout.completed",
            "provider_event_id": "evt_local_functional_v5_completed",
            "provider_session_id": checkout.json()["provider_session_id"],
        }
        body = _json_body(payload)
        webhook = self.client.post(
            "/api/v1/billing/webhook",
            content=body,
            headers={"X-DSA-Billing-Signature": _signature(body)},
        )
        self.assertEqual(webhook.status_code, 200)
        billing = self.client.get("/api/v1/billing/account")
        self.assertEqual(billing.status_code, 200)
        billing_body = billing.json()
        self.assertEqual(billing_body["provider"], "sandbox")
        self.assertEqual(billing_body["subscription"]["status"], "active")
        self.assertIn("local sandbox", billing_body["copy"].lower())
        self.assertIn("not real payment", billing_body["copy"].lower())
        self.assertIn("checkout.completed", {event["event_type"] for event in billing_body["recent_events"]})
        self.assertNotIn("sk-local-functional-v5-secret", str(billing_body))


if __name__ == "__main__":
    unittest.main()
