from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable


REPO_ROOT = Path(__file__).resolve().parents[1]
MAX_HOMEPAGE_BYTES = 500_000


@dataclass(frozen=True)
class CheckResult:
    name: str
    ok: bool
    details: Dict[str, Any]


def frontend_contract(source: str) -> CheckResult:
    required = (
        "type ViewMode = 'auto' | 'focus' | 'unread' | 'all'",
        "const unreadActive = viewMode === 'unread'",
        'data-testid="market-event-inbox-summary-v131"',
        "newOnly: '只看新增'",
        "noNewEvents: '当前没有新增市场事件'",
        "viewAllEvents: '查看全部事件'",
        "newOnly: 'New only'",
        "noNewEvents: 'No new market events'",
        "viewAllEvents: 'View all events'",
        "aria-pressed={unreadActive}",
        "onClick={() => setViewMode('unread')}",
        "onClick={() => setViewMode('all')}",
    )
    missing = [token for token in required if token not in source]
    return CheckResult("bilingual_returning_event_inbox", not missing, {"missing": missing})


def filter_contract(source: str) -> CheckResult:
    required = (
        "const filtered = useMemo(() => personalizedEvents",
        "filter === 'all' || event.category === filter",
        "marketFilter === 'all' || event.market === marketFilter",
        "!unreadActive || unseenEventIds.has(event.eventId)",
        ".slice(0, 12)",
    )
    forbidden = ("markEventsSeen", "markEventSeen", "localStorage", "sessionStorage")
    missing = [token for token in required if token not in source]
    forbidden_hits = [token for token in forbidden if token in source]
    return CheckResult(
        "read_state_separate_from_new_only_filter",
        not missing and not forbidden_hits,
        {"missing": missing, "forbidden_hits": forbidden_hits},
    )


def privacy_cost_contract(source: str) -> CheckResult:
    forbidden = (
        "fetch(",
        "axios",
        "apiClient",
        "platform_user_id",
        "email",
        "openai",
        "litellm",
        "ollama",
    )
    lowered = source.casefold()
    forbidden_hits = [token for token in forbidden if token.casefold() in lowered]
    return CheckResult(
        "no_new_network_ai_or_user_tracking",
        not forbidden_hits,
        {"forbidden_hits": forbidden_hits},
    )


def regression_tests_contract(source: str) -> CheckResult:
    required = (
        "lets returning visitors read only new events without changing read state",
        "shows an honest new-event empty state and can return to all events",
        "MARKET_EVENT_SEEN_STORAGE_KEY",
        "getByRole('button', { name: '只看新增' })",
        "getByRole('button', { name: '查看全部事件' })",
    )
    missing = [token for token in required if token not in source]
    return CheckResult("v131_returning_visitor_regressions", not missing, {"missing": missing})


def homepage_bundle_check(assets_dir: Path, *, source_paths: Iterable[Path] = ()) -> CheckResult:
    chunks = list(assets_dir.glob("HomePage-*.js"))
    if not chunks:
        return CheckResult("homepage_bundle", False, {"reason": "homepage_chunk_missing"})
    newest = max(chunks, key=lambda path: path.stat().st_mtime_ns)
    existing_sources = [path for path in source_paths if path.exists()]
    latest_source_mtime_ns = max((path.stat().st_mtime_ns for path in existing_sources), default=0)
    size = newest.stat().st_size
    bundle_fresh = newest.stat().st_mtime_ns >= latest_source_mtime_ns
    return CheckResult(
        "homepage_bundle",
        size < MAX_HOMEPAGE_BYTES and bundle_fresh,
        {
            "filename": newest.name,
            "size_bytes": size,
            "limit_bytes": MAX_HOMEPAGE_BYTES,
            "bundle_fresh": bundle_fresh,
        },
    )


def run_checks(repo_root: Path) -> Iterable[CheckResult]:
    component_path = repo_root / "apps/dsa-web/src/components/market-home/DailyMarketEventCenterV126.tsx"
    test_path = repo_root / "apps/dsa-web/src/components/market-home/__tests__/DailyMarketEventCenterV126.test.tsx"
    component_source = component_path.read_text(encoding="utf-8")
    test_source = test_path.read_text(encoding="utf-8")
    filter_start = component_source.index("const filtered = useMemo")
    filter_end = component_source.index("const priorityEventCount", filter_start)
    filter_source = component_source[filter_start:filter_end]

    yield frontend_contract(component_source)
    yield filter_contract(filter_source)
    yield privacy_cost_contract(component_source)
    yield regression_tests_contract(test_source)
    yield homepage_bundle_check(
        repo_root / "static/assets",
        source_paths=(component_path, test_path),
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify DSA V131 returning-user public event inbox.")
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    args = parser.parse_args()
    checks = list(run_checks(args.repo_root.resolve()))
    for check in checks:
        print(f"[{'OK' if check.ok else 'FAIL'}] {check.name}: {check.details}")
    if not all(check.ok for check in checks):
        return 1
    print("DSA_PLATFORM_RETURNING_EVENT_INBOX_V131_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
