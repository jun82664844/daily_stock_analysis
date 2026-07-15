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


def backend_sector_contract(source: str) -> CheckResult:
    required = (
        'linked_symbol, linked_name, linked_sector = self._linked_security(title, securities)',
        '"sector": sector',
        '"sector": str(item.get("sector") or "").strip()',
        'return symbol, name or None, security.get("sector") or None',
    )
    forbidden = (
        "import requests",
        "import httpx",
        "platform_user_id",
        "watchlist_symbols",
        "openai",
        "litellm",
        "ollama",
    )
    lowered = source.casefold()
    missing = [token for token in required if token not in source]
    forbidden_hits = [token for token in forbidden if token in lowered]
    return CheckResult(
        "public_sector_without_user_or_network_lookup",
        not missing and not forbidden_hits,
        {"missing": missing, "forbidden_hits": forbidden_hits},
    )


def api_sector_contract(schema_source: str, api_source: str) -> CheckResult:
    required = (
        (schema_source, "sector: Optional[str] = None"),
        (api_source, "sector?: string | null"),
        (api_source, "sector: String(event.sector ?? '').trim() || null"),
    )
    missing = [token for source, token in required if token not in source]
    return CheckResult("backward_compatible_sector_contract", not missing, {"missing": missing})


def personalization_contract(source: str) -> CheckResult:
    required = (
        "export function personalizeMarketEvents",
        "watchlist: 3, sector: 2, market: 1",
        "right.match ? priority[right.match] : 0",
        "left.match ? priority[left.match] : 0",
        "if (personalized)",
        "return left.index - right.index",
        "export function deriveWatchlistSectors",
        "if (/^[A-Z0-9]{2,12}-(?:USD|USDT|USDC|BTC|ETH)$/.test(raw)) return null",
    )
    forbidden = ("fetch(", "axios", "localstorage", "platform_user_id", "openai", "litellm", "ollama")
    lowered = source.casefold()
    missing = [token for token in required if token not in source]
    forbidden_hits = [token for token in forbidden if token in lowered]
    return CheckResult(
        "stable_client_side_personalization",
        not missing and not forbidden_hits,
        {"missing": missing, "forbidden_hits": forbidden_hits},
    )


def frontend_contract(source: str) -> CheckResult:
    required = (
        "const hasWatchlist = watchlist.size > 0",
        "const focusActive = hasWatchlist && (viewMode === 'auto' || viewMode === 'focus')",
        "personalizeMarketEvents(",
        "{hasWatchlist ? (",
        "aria-label={t.eventViewLabel}",
        "focusFirst: '为我优先'",
        "allEvents: '全部事件'",
        "matchLabels: { watchlist: '自选相关', sector: '相关行业', market: '关注市场' }",
        "focusFirst: 'For me first'",
        "allEvents: 'All events'",
        "matchLabels: { watchlist: 'Watchlist match', sector: 'Related industry', market: 'Followed market' }",
        "仅提供公开资讯和数据，不构成投资建议。",
        "Public information and data only. Not investment advice.",
    )
    forbidden = ("目标价", "收益预测", "交易指令", "target price", "return forecast", "trade instruction")
    lowered = source.casefold()
    missing = [token for token in required if token not in source]
    forbidden_hits = [token for token in forbidden if token in lowered]
    return CheckResult(
        "bilingual_watchlist_only_controls",
        not missing and not forbidden_hits,
        {"missing": missing, "forbidden_hits": forbidden_hits},
    )


def regression_tests_contract(helper_tests: str, component_tests: str, home_tests: str) -> CheckResult:
    required = (
        (helper_tests, "uses watchlist, sector and market matches before general relevance"),
        (helper_tests, "does not treat crypto as US equity"),
        (component_tests, "defaults to explainable personalized priority and can return to relevance order"),
        (component_tests, "keeps the public event feed unpersonalized for visitors without a watchlist"),
        (home_tests, "lazy-loads the V126 event center and forwards watchlist context"),
    )
    missing = [token for source, token in required if token not in source]
    return CheckResult("v130_regression_tests", not missing, {"missing": missing})


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
    backend_source = (repo_root / "src/services/public_market_event_service.py").read_text(encoding="utf-8")
    schema_source = (repo_root / "api/v1/schemas/market_workspace.py").read_text(encoding="utf-8")
    api_source = (repo_root / "apps/dsa-web/src/api/marketWorkspace.ts").read_text(encoding="utf-8")
    helper_source = (repo_root / "apps/dsa-web/src/components/market-home/marketEventPersonalizationV130.ts").read_text(encoding="utf-8")
    component_source = (repo_root / "apps/dsa-web/src/components/market-home/DailyMarketEventCenterV126.tsx").read_text(encoding="utf-8")
    helper_tests = (repo_root / "apps/dsa-web/src/components/market-home/__tests__/marketEventPersonalizationV130.test.ts").read_text(encoding="utf-8")
    component_tests = (repo_root / "apps/dsa-web/src/components/market-home/__tests__/DailyMarketEventCenterV126.test.tsx").read_text(encoding="utf-8")
    home_tests = (repo_root / "apps/dsa-web/src/components/market-home/__tests__/PublicMarketHomeV116.test.tsx").read_text(encoding="utf-8")
    yield backend_sector_contract(backend_source)
    yield api_sector_contract(schema_source, api_source)
    yield personalization_contract(helper_source)
    yield frontend_contract(component_source)
    yield regression_tests_contract(helper_tests, component_tests, home_tests)
    yield homepage_bundle_check(
        repo_root / "static/assets",
        source_paths=(
            repo_root / "apps/dsa-web/src/components/market-home/marketEventPersonalizationV130.ts",
            repo_root / "apps/dsa-web/src/components/market-home/DailyMarketEventCenterV126.tsx",
            repo_root / "apps/dsa-web/src/components/market-home/PublicMarketHomeV116.tsx",
        ),
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify DSA V130 personalized public market events.")
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    args = parser.parse_args()
    checks = list(run_checks(args.repo_root.resolve()))
    for check in checks:
        print(f"[{'OK' if check.ok else 'FAIL'}] {check.name}: {check.details}")
    if not all(check.ok for check in checks):
        return 1
    print("DSA_PLATFORM_PERSONALIZED_MARKET_EVENTS_V130_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
