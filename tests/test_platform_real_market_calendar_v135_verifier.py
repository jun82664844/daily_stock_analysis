from __future__ import annotations

import subprocess
import unittest
from pathlib import Path
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[1]


class RealMarketCalendarV135VerifierTestCase(unittest.TestCase):
    def test_verifier_entrypoint_exists(self) -> None:
        self.assertTrue(
            (REPO_ROOT / "scripts/verify_platform_real_market_calendar_v135.py").is_file()
        )

    def test_backend_contract_requires_sources_bounds_and_safe_flags(self) -> None:
        from scripts.verify_platform_real_market_calendar_v135 import backend_contract

        valid = """
CNINFO_REPORT_URL = "https://www.cninfo.com.cn/new/information/getPrbookInfo"
FOMC_CALENDAR_URL = "https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm"
YAHOO_QUOTE_URL = "https://finance.yahoo.com/quote/{symbol}/"
CALENDAR_PAST_DAYS = 7
CALENDAR_FUTURE_DAYS = 30
DEFAULT_MAX_EVENTS = 36
DEFAULT_CACHE_TTL_SECONDS = 900
DEFAULT_STALE_TTL_SECONDS = 21600
DEFAULT_TIMEOUT_SECONDS = 4.0
"time_kind": "scheduled"
"classification_source": "provider_schedule"
PLATFORM_PUBLIC_MARKET_CALENDAR_V135_ENABLED
_merge_events(scheduled_events, news_events)
if len(merged) >= 48:
"""
        safe_env = "PLATFORM_PUBLIC_MARKET_CALENDAR_V135_ENABLED=false"
        self.assertTrue(backend_contract(valid, safe_env, safe_env).ok)
        self.assertFalse(backend_contract(valid, safe_env.replace("false", "true"), safe_env).ok)

    def test_cost_privacy_contract_rejects_ai_keys_and_database_writes(self) -> None:
        from scripts.verify_platform_real_market_calendar_v135 import cost_privacy_contract

        valid = "requests.get(url); requests.post(url); ThreadPoolExecutor(max_workers=4)"
        self.assertTrue(cost_privacy_contract(valid).ok)
        self.assertFalse(cost_privacy_contract(valid + " openai.chat()").ok)
        self.assertFalse(cost_privacy_contract(valid + " api_key = secret").ok)
        self.assertFalse(cost_privacy_contract(valid + " database.insert(event)").ok)

    def test_frontend_contract_requires_bilingual_views_and_safety_copy(self) -> None:
        from scripts.verify_platform_real_market_calendar_v135 import frontend_contract

        valid = """
data-testid="market-event-calendar-v135"
今日
本周
我的日历
待复盘
Today
This week
My calendar
Due
公开数据 · 未使用 AI
Public data · No AI used
事件与行情并列展示不代表因果关系。
Events and market prices shown together do not establish causality.
仅提供资讯和数据，不构成投资建议。
Information and data only. Not investment advice.
"""
        self.assertTrue(frontend_contract(valid).ok)
        self.assertFalse(frontend_contract(valid.replace("不构成投资建议", "建议立即买入")).ok)

    def test_regression_contract_requires_backend_and_frontend_paths(self) -> None:
        from scripts.verify_platform_real_market_calendar_v135 import regression_tests_contract

        valid = """
builds scheduled events for three markets without forecast values
marks memory cache and stale fallback per source
timeout in one source does not block other market events
v135 merges scheduled events first and deduplicates ids
v135 calendar failure keeps news and adds truthful warning
uses a provider scheduled timestamp directly without parsing the title
defaults to this week and exposes today, mine, and due views in Chinese
renders localized English event labels, source status, and query action
adds and removes V135 follow-up calendar checkpoints with the V133 follow state
"""
        self.assertTrue(regression_tests_contract(valid).ok)
        self.assertFalse(regression_tests_contract(valid.replace("three markets", "one market")).ok)

    def test_guest_private_request_contract_keeps_public_home_available(self) -> None:
        from scripts.verify_platform_real_market_calendar_v135 import (
            guest_private_request_contract,
        )

        home = """
const privateWorkspaceEnabled = platformStatusLoaded
  && (!platformEnabled || Boolean(platformSession));
const legacyWorkspaceEnabled = platformStatusLoaded && !platformEnabled;
if (!privateWorkspaceEnabled) return undefined;
if (!privateWorkspaceEnabled) return;
if (!privateWorkspaceEnabled) {
if (!legacyWorkspaceEnabled) {
useDashboardLifecycle({
  enabled: privateWorkspaceEnabled,
});
const watchlistState = useWatchlist(privateWorkspaceEnabled);
useEffect(() => {
  let active = true;
  marketWorkspaceApi.getHome()
"""
        watchlist = """
export function useWatchlist(enabled = true): UseWatchlistReturn {
if (!enabled) {
if (!enabled || !stockCode || isActioning) return;
"""
        self.assertTrue(guest_private_request_contract(home, watchlist).ok)
        self.assertFalse(
            guest_private_request_contract(
                home.replace("enabled: privateWorkspaceEnabled", "enabled: true"),
                watchlist,
            ).ok
        )
        self.assertFalse(
            guest_private_request_contract(
                home.replace("marketWorkspaceApi.getHome()", "privateApi.getHome()"),
                watchlist,
            ).ok
        )

    def test_focused_checks_use_real_process_exit_codes(self) -> None:
        from scripts.verify_platform_real_market_calendar_v135 import (
            focused_backend_check,
            focused_frontend_check,
        )

        with patch(
            "scripts.verify_platform_real_market_calendar_v135.subprocess.run",
        ) as run:
            run.return_value = subprocess.CompletedProcess(
                args=[],
                returncode=0,
                stdout="OK",
                stderr="",
            )
            self.assertTrue(focused_backend_check(REPO_ROOT).ok)
            backend_command = " ".join(run.call_args.args[0])
            self.assertIn("tests.test_public_market_calendar_service_v135", backend_command)
            self.assertIn("tests.test_public_market_home_v116", backend_command)

            self.assertTrue(focused_frontend_check(REPO_ROOT).ok)
            frontend_command = " ".join(run.call_args.args[0])
            self.assertIn("MarketEventCalendarPanelV135.test.tsx", frontend_command)
            self.assertIn("DailyMarketEventCenterV126.test.tsx", frontend_command)

            run.return_value = subprocess.CompletedProcess(
                args=[],
                returncode=1,
                stdout="FAILED",
                stderr="",
            )
            self.assertFalse(focused_backend_check(REPO_ROOT).ok)
            self.assertFalse(focused_frontend_check(REPO_ROOT).ok)


if __name__ == "__main__":
    unittest.main()
