from __future__ import annotations

import subprocess
import unittest
from pathlib import Path
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[1]


class ObservedEventReactionsV136VerifierTestCase(unittest.TestCase):
    def test_verifier_entrypoint_exists(self) -> None:
        self.assertTrue(
            (REPO_ROOT / "scripts/verify_platform_observed_event_reactions_v136.py").is_file()
        )

    def test_backend_contract_requires_windows_bounds_sources_and_public_route(self) -> None:
        from scripts.verify_platform_observed_event_reactions_v136 import backend_contract

        service = """
REACTION_WINDOWS = (1, 3, 5, 20)
MARKET_BENCHMARKS = {"cn": ("000001.SS", "x"), "hk": ("^HSI", "x"), "us": ("^GSPC", "x")}
MARKET_TIMEZONES = {"cn": ZoneInfo("Asia/Shanghai")}
YAHOO_CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
_MAX_RESPONSE_BYTES = 768 * 1024
ThreadPoolExecutor(max_workers=8)
wait(tuple(pending), timeout=self.timeout_seconds)
min(int(max_events), 6)
PLATFORM_PUBLIC_EVENT_REACTIONS_V136_MAX_EVENTS
PLATFORM_PUBLIC_EVENT_REACTIONS_V136_CACHE_TTL_SECONDS
PLATFORM_PUBLIC_EVENT_REACTIONS_V136_STALE_TTL_SECONDS
PLATFORM_PUBLIC_EVENT_REACTIONS_V136_HISTORY_CACHE_MAX_ENTRIES
self._history_cache.pop(oldest_symbol, None)
rows[max(0, baseline_index - 5): baseline_index]
market_rows = benchmark_rows or subject_rows
target_date = str(market_rows[market_target_index].get("date") or "")
MARKET_TIMEZONES.get(market, timezone.utc)
"""
        calendar = """
PLATFORM_PUBLIC_MARKET_CALENDAR_CACHE_MAX_ENTRIES
max_cache_entries
fail_on_source_unavailable: bool = False
raise RuntimeError("calendar_sources_unavailable")
MAX_SOURCE_CACHE_EVENTS = 72
_cninfo_periods(
range(start_date.year, end_date.year + 1)
and not events
"""
        endpoint = """
@router.get("/event-reactions", response_model=PublicMarketEventReactionResponse)
"market_workspace_event_reactions"
PLATFORM_PUBLIC_EVENT_REACTIONS_V136_ENABLED
enforce=True
def _event_history_past_days():
    return 45
future_days=0
include_historical=True
fail_on_source_unavailable=True
"""
        auth = '"/api/v1/market-workspace/event-reactions"'
        rate_limit = """
def check_platform_rate_limit(*, enforce: bool = False):
    if not enforce and not platform_rate_limits_enabled():
        return None
PLATFORM_RATE_LIMIT_MAX_BUCKETS
if len(_buckets) >= _max_bucket_count():
oldest_live = min(
"""
        frontend_api = "{ withCredentials: false }; aiUsed: Boolean(body.aiUsed)"
        safe_env = """
PLATFORM_PUBLIC_EVENT_REACTIONS_V136_ENABLED=false
PLATFORM_PUBLIC_EVENT_REACTIONS_V136_HISTORY_CACHE_MAX_ENTRIES=32
PLATFORM_PUBLIC_MARKET_CALENDAR_CACHE_MAX_ENTRIES=64
PLATFORM_RATE_LIMIT_MAX_BUCKETS=4096
"""
        self.assertTrue(
            backend_contract(
                service,
                calendar,
                endpoint,
                auth,
                rate_limit,
                frontend_api,
                safe_env,
                safe_env,
            ).ok
        )
        self.assertFalse(
            backend_contract(
                service.replace("^HSI", "HSI"),
                calendar,
                endpoint,
                auth,
                rate_limit,
                frontend_api,
                safe_env,
                safe_env,
            ).ok
        )
        self.assertFalse(
            backend_contract(
                service.replace(
                    "market_rows = benchmark_rows or subject_rows",
                    "market_rows = subject_rows",
                ),
                calendar,
                endpoint,
                auth,
                rate_limit,
                frontend_api,
                safe_env,
                safe_env,
            ).ok
        )
        self.assertFalse(
            backend_contract(
                service,
                calendar.replace("MAX_SOURCE_CACHE_EVENTS = 72", ""),
                endpoint,
                auth,
                rate_limit,
                frontend_api,
                safe_env,
                safe_env,
            ).ok
        )
        self.assertFalse(
            backend_contract(
                service,
                calendar,
                endpoint + "\nplatform_identity_from_request(request)",
                auth,
                rate_limit,
                frontend_api,
                safe_env,
                safe_env,
            ).ok
        )
        self.assertFalse(
            backend_contract(
                service,
                calendar,
                endpoint,
                auth,
                rate_limit,
                "{ withCredentials: true }",
                safe_env,
                safe_env,
            ).ok
        )
        self.assertFalse(
            backend_contract(
                service,
                calendar,
                endpoint,
                auth,
                rate_limit,
                frontend_api,
                safe_env.replace("false", "true", 1),
                safe_env,
            ).ok
        )
        self.assertFalse(
            backend_contract(
                service,
                calendar.replace(
                    'raise RuntimeError("calendar_sources_unavailable")',
                    "return []",
                ),
                endpoint,
                auth,
                rate_limit,
                frontend_api,
                safe_env,
                safe_env,
            ).ok
        )

    def test_cost_privacy_contract_rejects_model_keys_database_and_notifications(self) -> None:
        from scripts.verify_platform_observed_event_reactions_v136 import cost_privacy_contract

        valid = "requests.get(url); ThreadPoolExecutor(max_workers=8)"
        self.assertTrue(cost_privacy_contract(valid).ok)
        self.assertFalse(cost_privacy_contract(valid + " openai.chat()").ok)
        self.assertFalse(cost_privacy_contract(valid + " api_key = secret").ok)
        self.assertFalse(cost_privacy_contract(valid + " database.insert(row)").ok)
        self.assertFalse(cost_privacy_contract(valid + " send_email(user)").ok)

    def test_frontend_contract_requires_windows_bilingual_copy_and_non_causality(self) -> None:
        from scripts.verify_platform_observed_event_reactions_v136 import frontend_contract

        valid = """
data-testid="market-event-reactions-v136"
const WINDOWS: WindowDays[] = [1, 3, 5, 20]
事件后市场观察
Post-event market observations
证券同期变化
Security change
基准同期变化
Benchmark change
相对基准变化
Relative change
同期量比
Volume ratio
同期表现不代表事件导致行情变化。仅提供资讯和数据，不构成投资建议。
Same-period performance does not establish that the event caused a market move. Information and data only. Not investment advice.
部分事件行情源暂时不可用，以下成功取得的数据仍可查看。
Some event-price sources are unavailable. Successfully loaded observations remain visible below.
响应未满足免 AI 数据边界，暂不展示该批数据。
This response did not satisfy the no-AI data boundary, so the batch is not displayed.
const boundaryViolation = Boolean(
const partialUnavailable = Boolean(
"""
        self.assertTrue(frontend_contract(valid).ok)
        self.assertFalse(frontend_contract(valid.replace("Relative change", "Buy signal")).ok)

    def test_integration_contract_requires_calendar_reaction_and_follow_up_order(self) -> None:
        from scripts.verify_platform_observed_event_reactions_v136 import integration_contract

        valid = """
<MarketEventCalendarPanelV135 />
<MarketEventReactionPanelV136 />
<MarketEventFollowUpPanelV133 />
"""
        self.assertTrue(integration_contract(valid).ok)
        self.assertFalse(
            integration_contract(
                valid.replace(
                    "<MarketEventReactionPanelV136 />",
                    "<MarketEventReactionPanelV136 />\n<MarketEventCalendarPanelV135 />",
                )
            ).ok
        )

    def test_focused_checks_use_real_process_exit_codes(self) -> None:
        from scripts.verify_platform_observed_event_reactions_v136 import (
            focused_backend_check,
            focused_frontend_check,
        )

        with patch(
            "scripts.verify_platform_observed_event_reactions_v136.subprocess.run",
        ) as run:
            run.return_value = subprocess.CompletedProcess(
                args=[],
                returncode=0,
                stdout="OK",
                stderr="",
            )
            self.assertTrue(focused_backend_check(REPO_ROOT).ok)
            self.assertIn(
                "tests.test_public_market_event_reaction_service_v136",
                " ".join(run.call_args.args[0]),
            )
            self.assertIn(
                "tests.test_public_market_calendar_service_v135",
                " ".join(run.call_args.args[0]),
            )

            self.assertTrue(focused_frontend_check(REPO_ROOT).ok)
            self.assertIn(
                "MarketEventReactionPanelV136.test.tsx",
                " ".join(run.call_args.args[0]),
            )

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
