from __future__ import annotations

import argparse
import re
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


def backend_relevance_contract(source: str) -> CheckResult:
    required = (
        "FINANCE_SIGNAL_KEYWORDS",
        "PROMOTIONAL_NOISE_KEYWORDS",
        "CATEGORY_REASONS",
        "title_key in seen_titles",
        "not symbol and not has_market_signal",
        "relevance_score",
        "relevance_reasons",
        "_relevance",
        "_importance",
        "_is_promotional_noise",
    )
    forbidden = ("import requests", "import httpx", "openai", "litellm", "ollama")
    missing = [token for token in required if token not in source]
    if not re.search(r"seen_titles(?:\s*:\s*[^=]+)?\s*=\s*set\(\)", source):
        missing.append("global_seen_titles_set")
    forbidden_hits = [token for token in forbidden if token in source.casefold()]
    return CheckResult(
        "backend_relevance",
        not missing and not forbidden_hits,
        {"missing": missing, "forbidden_hits": forbidden_hits},
    )


def api_contract(schema_source: str, frontend_source: str) -> CheckResult:
    schema_required = (
        "relevance_score",
        "ge=0",
        "le=100",
        "importance: MarketEventImportance",
        "relevance_reasons: List[str]",
        "default_factory=list",
    )
    frontend_required = (
        "relevanceScore: number",
        "importance: 'high' | 'medium' | 'low'",
        "relevanceReasons: string[]",
        "Number.isFinite(event.relevanceScore)",
        "event.importance ?? 'low'",
        "Array.isArray(event.relevanceReasons)",
    )
    missing = [f"schema:{token}" for token in schema_required if token not in schema_source]
    missing.extend(f"frontend:{token}" for token in frontend_required if token not in frontend_source)
    return CheckResult("backward_compatible_api", not missing, {"missing": missing})


def frontend_contract(source: str) -> CheckResult:
    required = (
        "const MARKET_FILTERS",
        "'all', 'cn', 'hk', 'us'",
        "setMarketFilter",
        "event.market === marketFilter",
        "watchlist.has",
        "event.relevanceScore",
        "event.importance",
        "event.relevanceReasons",
        "全部市场",
        "A股",
        "港股",
        "美股",
        "高重要度",
        "中重要度",
        "重点事件",
        "关联证券",
        "All markets",
        "High importance",
        "Medium importance",
        "Priority events",
        "Linked security",
        "仅提供公开资讯和数据，不构成投资建议。",
        "Public information and data only. Not investment advice.",
    )
    forbidden = ("买入", "卖出", "目标价", "收益预测", "target price", "return forecast", "trade instruction")
    missing = [token for token in required if token not in source]
    forbidden_hits = [token for token in forbidden if token in source.casefold()]
    return CheckResult(
        "focused_bilingual_frontend",
        not missing and not forbidden_hits,
        {"missing": missing, "forbidden_hits": forbidden_hits},
    )


def regression_tests_contract(backend_tests: str, frontend_tests: str) -> CheckResult:
    required_backend = (
        "test_filters_low_relevance_noise_and_explains_retained_events",
        "test_deduplicates_the_same_title_across_market_channels",
    )
    required_frontend = (
        "filters by market and explains why retained events matter",
        "puts watchlist-linked events before higher-scored general events",
    )
    missing = [token for token in required_backend if token not in backend_tests]
    missing.extend(token for token in required_frontend if token not in frontend_tests)
    return CheckResult("v127_regression_tests", not missing, {"missing": missing})


def homepage_bundle_check(assets_dir: Path) -> CheckResult:
    chunks = list(assets_dir.glob("HomePage-*.js"))
    if not chunks:
        return CheckResult("homepage_bundle", False, {"reason": "homepage_chunk_missing"})
    newest = max(chunks, key=lambda path: path.stat().st_mtime_ns)
    size = newest.stat().st_size
    return CheckResult(
        "homepage_bundle",
        size < MAX_HOMEPAGE_BYTES,
        {"filename": newest.name, "size_bytes": size, "limit_bytes": MAX_HOMEPAGE_BYTES},
    )


def run_checks(repo_root: Path) -> Iterable[CheckResult]:
    backend_source = (repo_root / "src/services/public_market_event_service.py").read_text(encoding="utf-8")
    schema_source = (repo_root / "api/v1/schemas/market_workspace.py").read_text(encoding="utf-8")
    api_source = (repo_root / "apps/dsa-web/src/api/marketWorkspace.ts").read_text(encoding="utf-8")
    component_source = (repo_root / "apps/dsa-web/src/components/market-home/DailyMarketEventCenterV126.tsx").read_text(encoding="utf-8")
    backend_tests = (repo_root / "tests/test_public_market_event_service.py").read_text(encoding="utf-8")
    frontend_tests = (repo_root / "apps/dsa-web/src/components/market-home/__tests__/DailyMarketEventCenterV126.test.tsx").read_text(encoding="utf-8")
    yield backend_relevance_contract(backend_source)
    yield api_contract(schema_source, api_source)
    yield frontend_contract(component_source)
    yield regression_tests_contract(backend_tests, frontend_tests)
    yield homepage_bundle_check(repo_root / "static/assets")


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify DSA V127 market-event relevance.")
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    args = parser.parse_args()
    checks = list(run_checks(args.repo_root.resolve()))
    for check in checks:
        print(f"[{'OK' if check.ok else 'FAIL'}] {check.name}: {check.details}")
    if not all(check.ok for check in checks):
        return 1
    print("DSA_PLATFORM_MARKET_EVENT_RELEVANCE_V127_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
