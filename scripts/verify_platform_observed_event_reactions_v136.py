from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.verify_platform_event_driven_research_v132 import homepage_bundle_check


@dataclass(frozen=True)
class CheckResult:
    name: str
    ok: bool
    details: Dict[str, Any]


def backend_contract(
    service: str,
    calendar: str,
    endpoint: str,
    auth: str,
    rate_limit: str,
    frontend_api: str,
    env_example: str,
    production_env: str,
) -> CheckResult:
    service_required = (
        "REACTION_WINDOWS = (1, 3, 5, 20)",
        "MARKET_TIMEZONES = {",
        '"cn": ("000001.SS"',
        '"hk": ("^HSI"',
        '"us": ("^GSPC"',
        'YAHOO_CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"',
        "_MAX_RESPONSE_BYTES = 768 * 1024",
        "ThreadPoolExecutor(max_workers=8",
        "wait(tuple(pending), timeout=self.timeout_seconds)",
        "PLATFORM_PUBLIC_EVENT_REACTIONS_V136_MAX_EVENTS",
        "PLATFORM_PUBLIC_EVENT_REACTIONS_V136_CACHE_TTL_SECONDS",
        "PLATFORM_PUBLIC_EVENT_REACTIONS_V136_STALE_TTL_SECONDS",
        "PLATFORM_PUBLIC_EVENT_REACTIONS_V136_HISTORY_CACHE_MAX_ENTRIES",
        "self._history_cache.pop(oldest_symbol, None)",
        "rows[max(0, baseline_index - 5): baseline_index]",
        "market_rows = benchmark_rows or subject_rows",
        'target_date = str(market_rows[market_target_index].get("date") or "")',
        "MARKET_TIMEZONES.get(market, timezone.utc)",
    )
    calendar_required = (
        "PLATFORM_PUBLIC_MARKET_CALENDAR_CACHE_MAX_ENTRIES",
        "max_cache_entries",
        "fail_on_source_unavailable: bool = False",
        'raise RuntimeError("calendar_sources_unavailable")',
        "MAX_SOURCE_CACHE_EVENTS = 72",
        "_cninfo_periods(",
        "range(start_date.year, end_date.year + 1)",
        "and not events",
    )
    endpoint_required = (
        '@router.get("/event-reactions", response_model=PublicMarketEventReactionResponse)',
        '"market_workspace_event_reactions"',
        "PLATFORM_PUBLIC_EVENT_REACTIONS_V136_ENABLED",
        "def _event_history_past_days()",
        "return 45",
        "future_days=0",
        "include_historical=True",
        "fail_on_source_unavailable=True",
        "enforce=True",
    )
    rate_limit_required = (
        "enforce: bool = False",
        "if not enforce and not",
        "PLATFORM_RATE_LIMIT_MAX_BUCKETS",
        "if len(_buckets) >= _max_bucket_count():",
        "oldest_live = min(",
    )
    auth_required = '"/api/v1/market-workspace/event-reactions"'
    missing = [token for token in service_required if token not in service]
    missing.extend(token for token in calendar_required if token not in calendar)
    missing.extend(token for token in endpoint_required if token not in endpoint)
    missing.extend(token for token in rate_limit_required if token not in rate_limit)
    if auth_required not in auth:
        missing.append(auth_required)
    if "withCredentials: false" not in frontend_api:
        missing.append("withCredentials: false")
    if "aiUsed: Boolean(body.aiUsed)" not in frontend_api:
        missing.append("aiUsed: Boolean(body.aiUsed)")
    event_route_start = endpoint.find(
        '@router.get("/event-reactions", response_model=PublicMarketEventReactionResponse)'
    )
    event_route_end = endpoint.find("\n@router.", event_route_start + 1)
    event_route = endpoint[
        event_route_start : event_route_end if event_route_end >= 0 else len(endpoint)
    ]
    anonymous_public_route = (
        event_route_start >= 0
        and "platform_identity_from_request(request)" not in event_route
    )
    safe_default = (
        "PLATFORM_PUBLIC_EVENT_REACTIONS_V136_ENABLED=false" in env_example
        and "PLATFORM_PUBLIC_EVENT_REACTIONS_V136_ENABLED=false" in production_env
        and "PLATFORM_PUBLIC_EVENT_REACTIONS_V136_HISTORY_CACHE_MAX_ENTRIES=32"
        in env_example
        and "PLATFORM_PUBLIC_EVENT_REACTIONS_V136_HISTORY_CACHE_MAX_ENTRIES=32"
        in production_env
        and "PLATFORM_PUBLIC_MARKET_CALENDAR_CACHE_MAX_ENTRIES=64" in env_example
        and "PLATFORM_PUBLIC_MARKET_CALENDAR_CACHE_MAX_ENTRIES=64"
        in production_env
        and "PLATFORM_RATE_LIMIT_MAX_BUCKETS=4096" in env_example
        and "PLATFORM_RATE_LIMIT_MAX_BUCKETS=4096" in production_env
    )
    return CheckResult(
        "v136_sources_windows_bounds_anonymous_rate_limit_and_safe_flags",
        not missing and safe_default and anonymous_public_route,
        {
            "missing": missing,
            "safe_default": safe_default,
            "anonymous_public_route": anonymous_public_route,
        },
    )


def cost_privacy_contract(source: str) -> CheckResult:
    lowered = source.casefold()
    forbidden = (
        "openai",
        "litellm",
        "deepseek",
        "ollama",
        "api_key",
        "platform_user_id",
        "database.",
        "session.add(",
        "send_email",
        "sendemail",
        "sendsms",
        "pushnotification",
    )
    hits = [token for token in forbidden if token in lowered]
    return CheckResult(
        "v136_no_ai_key_database_or_notification",
        not hits,
        {"forbidden_hits": hits},
    )


def frontend_contract(source: str) -> CheckResult:
    required = (
        'data-testid="market-event-reactions-v136"',
        "const WINDOWS: WindowDays[] = [1, 3, 5, 20]",
        "事件后市场观察",
        "Post-event market observations",
        "证券同期变化",
        "Security change",
        "基准同期变化",
        "Benchmark change",
        "相对基准变化",
        "Relative change",
        "同期量比",
        "Volume ratio",
        "同期表现不代表事件导致行情变化。仅提供资讯和数据，不构成投资建议。",
        "Same-period performance does not establish that the event caused a market move. Information and data only. Not investment advice.",
        "部分事件行情源暂时不可用，以下成功取得的数据仍可查看。",
        "Some event-price sources are unavailable. Successfully loaded observations remain visible below.",
        "响应未满足免 AI 数据边界，暂不展示该批数据。",
        "This response did not satisfy the no-AI data boundary, so the batch is not displayed.",
        "const boundaryViolation = Boolean(",
        "const partialUnavailable = Boolean(",
    )
    missing = [token for token in required if token not in source]
    judgement_terms = (
        "建议买入",
        "建议卖出",
        "目标价",
        "收益预测",
        "仓位建议",
        "Buy signal",
        "Sell signal",
        "Target price",
    )
    hits = [token for token in judgement_terms if token.casefold() in source.casefold()]
    return CheckResult(
        "v136_bilingual_objective_observations",
        not missing and not hits,
        {"missing": missing, "judgement_hits": hits},
    )


def integration_contract(source: str) -> CheckResult:
    calendar = "<MarketEventCalendarPanelV135"
    reactions = "<MarketEventReactionPanelV136"
    follow_up = "<MarketEventFollowUpPanelV133"
    indexes = [source.find(token) for token in (calendar, reactions, follow_up)]
    ordered = (
        all(index >= 0 for index in indexes)
        and indexes[0] < indexes[1] < indexes[2]
        and source.count(calendar) == 1
        and source.count(reactions) == 1
        and source.count(follow_up) == 1
    )
    return CheckResult(
        "v136_calendar_reaction_follow_up_order",
        ordered,
        {"indexes": indexes},
    )


def _process_result(name: str, completed: subprocess.CompletedProcess[str]) -> CheckResult:
    output_lines = [
        line.strip()
        for line in f"{completed.stdout}\n{completed.stderr}".splitlines()
        if line.strip()
    ]
    return CheckResult(
        name,
        completed.returncode == 0,
        {
            "returncode": completed.returncode,
            "summary": " | ".join(output_lines[-7:]),
        },
    )


def focused_backend_check(repo_root: Path) -> CheckResult:
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "unittest",
            "tests.test_public_market_event_reaction_service_v136",
            "tests.test_public_market_event_reaction_api_v136",
            "tests.test_public_market_calendar_service_v135",
            "tests.test_public_market_home_v116",
        ],
        cwd=repo_root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    return _process_result("v136_focused_backend", completed)


def focused_frontend_check(repo_root: Path) -> CheckResult:
    npm_executable = shutil.which("npm.cmd") or shutil.which("npm")
    if npm_executable is None:
        return CheckResult("v136_focused_frontend", False, {"reason": "npm_not_found"})
    completed = subprocess.run(
        [
            npm_executable,
            "test",
            "--",
            "--run",
            "src/api/__tests__/marketWorkspace.test.ts",
            "src/components/market-home/__tests__/MarketEventReactionPanelV136.test.tsx",
            "src/components/market-home/__tests__/DailyMarketEventCenterV126.test.tsx",
            "src/pages/__tests__/HomePage.test.tsx",
        ],
        cwd=repo_root / "apps/dsa-web",
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    return _process_result("v136_focused_frontend", completed)


def run_checks(repo_root: Path) -> Iterable[CheckResult]:
    service_path = repo_root / "src/services/public_market_event_reaction_service.py"
    endpoint_path = repo_root / "api/v1/endpoints/market_workspace.py"
    schema_path = repo_root / "api/v1/schemas/market_workspace.py"
    auth_path = repo_root / "api/middlewares/auth.py"
    rate_limit_path = repo_root / "src/platform_rate_limit.py"
    calendar_path = repo_root / "src/services/public_market_calendar_service.py"
    api_path = repo_root / "apps/dsa-web/src/api/marketWorkspace.ts"
    panel_path = (
        repo_root
        / "apps/dsa-web/src/components/market-home/MarketEventReactionPanelV136.tsx"
    )
    daily_path = (
        repo_root
        / "apps/dsa-web/src/components/market-home/DailyMarketEventCenterV126.tsx"
    )
    backend_test_paths = (
        repo_root / "tests/test_public_market_event_reaction_service_v136.py",
        repo_root / "tests/test_public_market_event_reaction_api_v136.py",
        repo_root / "tests/test_public_market_calendar_service_v135.py",
        repo_root / "tests/test_public_market_home_v116.py",
    )
    frontend_test_paths = (
        repo_root / "apps/dsa-web/src/api/__tests__/marketWorkspace.test.ts",
        repo_root / "apps/dsa-web/src/components/market-home/__tests__/MarketEventReactionPanelV136.test.tsx",
        repo_root / "apps/dsa-web/src/components/market-home/__tests__/DailyMarketEventCenterV126.test.tsx",
        repo_root / "apps/dsa-web/src/pages/__tests__/HomePage.test.tsx",
    )

    service_source = service_path.read_text(encoding="utf-8")
    endpoint_source = endpoint_path.read_text(encoding="utf-8")
    auth_source = auth_path.read_text(encoding="utf-8")
    rate_limit_source = rate_limit_path.read_text(encoding="utf-8")
    api_source = api_path.read_text(encoding="utf-8")
    panel_source = panel_path.read_text(encoding="utf-8")
    daily_source = daily_path.read_text(encoding="utf-8")

    yield backend_contract(
        service_source,
        calendar_path.read_text(encoding="utf-8"),
        endpoint_source,
        auth_source,
        rate_limit_source,
        api_source,
        (repo_root / ".env.example").read_text(encoding="utf-8"),
        (repo_root / "docs/superpowers/platform-production-env.example").read_text(
            encoding="utf-8"
        ),
    )
    yield cost_privacy_contract(service_source)
    yield frontend_contract(panel_source)
    yield integration_contract(daily_source)
    yield focused_backend_check(repo_root)
    yield focused_frontend_check(repo_root)
    yield homepage_bundle_check(
        repo_root / "static/assets",
        source_paths=(
            service_path,
            endpoint_path,
            schema_path,
            auth_path,
            rate_limit_path,
            calendar_path,
            api_path,
            panel_path,
            daily_path,
            *backend_test_paths,
            *frontend_test_paths,
        ),
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verify DSA V136 public observed event-window market data."
    )
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    args = parser.parse_args()
    checks = list(run_checks(args.repo_root.resolve()))
    for check in checks:
        print(f"[{'OK' if check.ok else 'FAIL'}] {check.name}: {check.details}")
    if not all(check.ok for check in checks):
        return 1
    print("DSA_PLATFORM_OBSERVED_EVENT_REACTIONS_V136_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
