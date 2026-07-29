from __future__ import annotations

import subprocess
import unittest
from pathlib import Path
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[1]


class MarketEventFollowUpV133VerifierTestCase(unittest.TestCase):
    def test_verifier_entrypoint_exists(self) -> None:
        self.assertTrue(
            (REPO_ROOT / "scripts/verify_platform_market_event_follow_up_v133.py").is_file()
        )

    def test_frontend_contract_requires_follow_up_checkpoints_and_legal_boundaries(self) -> None:
        from scripts.verify_platform_market_event_follow_up_v133 import frontend_contract

        valid = """
data-testid="market-event-follow-up-panel-v133"
事件后续追踪
Event follow-up
关注时基准
Follow-time baseline
后续公开事件
Later public events
不代表事件导致行情变化
does not mean the event caused the market change
仅提供公开资讯和数据，不构成投资建议。
Public information and data only. Not investment advice.
FOLLOW_UP_HORIZON_DAYS = [1, 3, 5, 20]
"""
        self.assertTrue(frontend_contract(valid).ok)
        self.assertFalse(frontend_contract(valid.replace("不构成投资建议", "建议立即买入")).ok)

    def test_privacy_cost_contract_rejects_network_ai_and_identity_leaks(self) -> None:
        from scripts.verify_platform_market_event_follow_up_v133 import privacy_cost_contract

        valid = "localStorage.setItem(key, JSON.stringify(items)); const scope = 'user-72';"
        self.assertTrue(privacy_cost_contract(valid).ok)
        self.assertFalse(privacy_cost_contract(valid + " fetch('/api/events')").ok)
        self.assertFalse(privacy_cost_contract(valid + " const provider = 'ollama';").ok)
        self.assertFalse(privacy_cost_contract(valid + " const identity = user.email;").ok)

    def test_scope_contract_requires_numeric_user_scope_and_guest_migration(self) -> None:
        from scripts.verify_platform_market_event_follow_up_v133 import scope_contract

        helper = """
/^user-\\d+$/
adoptGuestFollowedMarketEvents
marketEventFollowUpStorageKey('guest')
MAX_FOLLOWED_EVENTS = 12
MAX_OBSERVATIONS = 32
"""
        home = "eventFollowUpScope={platformSession ? `user-${platformSession.user.id}` : 'guest'}"
        self.assertTrue(scope_contract(helper, home).ok)
        self.assertFalse(scope_contract(helper, home.replace("user.id", "user.email")).ok)

    def test_regression_contract_requires_storage_panel_and_integration_paths(self) -> None:
        from scripts.verify_platform_market_event_follow_up_v133 import regression_tests_contract

        valid = """
persists a followed event with an honest follow-time quote baseline
moves current guest follows into the signed-in user scope without leaking to another user
records exact-symbol public quote observations and replaces the same UTC day
builds 1/3/5/20 day checkpoints without inventing missing observations
shows a Chinese follow-up record with checkpoints and explicit information-only boundaries
lets a guest follow and remove an event from the V132 research card
"""
        self.assertTrue(regression_tests_contract(valid).ok)
        self.assertFalse(regression_tests_contract(valid.replace("exact-symbol", "partial-symbol")).ok)

    def test_focused_vitest_check_uses_real_test_process_exit_code(self) -> None:
        from scripts.verify_platform_market_event_follow_up_v133 import focused_vitest_check

        with (
            patch(
                "scripts.verify_platform_market_event_follow_up_v133.shutil.which",
                return_value="npm.cmd",
            ),
            patch(
                "scripts.verify_platform_market_event_follow_up_v133.subprocess.run",
            ) as run,
        ):
            run.return_value = subprocess.CompletedProcess(
                args=[],
                returncode=0,
                stdout="Tests 37 passed",
                stderr="",
            )
            result = focused_vitest_check(REPO_ROOT)
            self.assertTrue(result.ok)
            command = " ".join(run.call_args.args[0])
            self.assertIn("marketEventFollowUpV133.test.ts", command)
            self.assertIn("MarketEventFollowUpPanelV133.test.tsx", command)
            self.assertIn("DailyMarketEventCenterV126.test.tsx", command)

            run.return_value = subprocess.CompletedProcess(
                args=[],
                returncode=1,
                stdout="Tests 1 failed",
                stderr="",
            )
            self.assertFalse(focused_vitest_check(REPO_ROOT).ok)


if __name__ == "__main__":
    unittest.main()
