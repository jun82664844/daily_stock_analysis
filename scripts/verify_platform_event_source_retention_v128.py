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


def backend_source_contract(source: str) -> CheckResult:
    required = (
        "events_by_title",
        "source_refs_by_title",
        "events_by_title.get(title_key)",
        "source_ref not in source_refs",
        "len(source_refs) < 20",
        "len(publishers) < 8",
        "source_count",
        "source_publishers",
        "_source_reference",
    )
    forbidden = ("import requests", "import httpx", "openai", "litellm", "ollama")
    missing = [token for token in required if token not in source]
    forbidden_hits = [token for token in forbidden if token in source.casefold()]
    return CheckResult(
        "bounded_source_aggregation",
        not missing and not forbidden_hits,
        {"missing": missing, "forbidden_hits": forbidden_hits},
    )


def api_source_contract(schema_source: str, frontend_source: str) -> CheckResult:
    schema_required = (
        "source_count: int = Field(1, ge=1, le=20)",
        "source_publishers: List[str]",
        "default_factory=list",
        "max_length=8",
    )
    frontend_required = (
        "sourceCount: number",
        "sourcePublishers: string[]",
        "Number.isFinite(event.sourceCount)",
        "Array.isArray(event.sourcePublishers)",
        "[event.publisher]",
    )
    missing = [f"schema:{token}" for token in schema_required if token not in schema_source]
    missing.extend(f"frontend:{token}" for token in frontend_required if token not in frontend_source)
    return CheckResult("backward_compatible_source_api", not missing, {"missing": missing})


def read_state_contract(source: str) -> CheckResult:
    required = (
        "dsa.marketEvents.seen.v1",
        "window.localStorage",
        "JSON.parse",
        "JSON.stringify",
        "getUnseenMarketEventIds",
        "mergeSeenMarketEventIds",
    )
    forbidden = ("email", "apikey", "api_key", "title", "url", "publisher")
    lowered = source.casefold()
    missing = [token for token in required if token not in source]
    if not re.search(r"MAX_SEEN_EVENT_IDS\s*=\s*200\s*;", source):
        missing.append("MAX_SEEN_EVENT_IDS=200")
    forbidden_hits = [token for token in forbidden if token in lowered]
    return CheckResult(
        "bounded_private_read_state",
        not missing and not forbidden_hits,
        {"missing": missing, "forbidden_hits": forbidden_hits},
    )


def frontend_retention_contract(source: str) -> CheckResult:
    required = (
        "loadSeenMarketEventIds",
        "getUnseenMarketEventIds",
        "mergeSeenMarketEventIds",
        "saveSeenMarketEventIds",
        "sourceCount",
        "sourcePublishers",
        "markAllRead",
        "unseenEventIds",
        "新事件",
        "新增",
        "全部标为已读",
        "条公开来源记录",
        "多条来源记录不代表事实已独立证实。",
        "New event",
        "new",
        "Mark all as read",
        "public source",
        "Multiple source records do not mean the facts were independently verified.",
        "仅提供公开资讯和数据，不构成投资建议。",
        "Public information and data only. Not investment advice.",
    )
    forbidden = ("买入", "卖出", "目标价", "收益预测", "target price", "return forecast", "trade instruction")
    missing = [token for token in required if token not in source]
    forbidden_hits = [token for token in forbidden if token in source.casefold()]
    return CheckResult(
        "bilingual_source_retention_ui",
        not missing and not forbidden_hits,
        {"missing": missing, "forbidden_hits": forbidden_hits},
    )


def regression_tests_contract(backend_tests: str, api_tests: str, read_tests: str, component_tests: str) -> CheckResult:
    required = (
        (backend_tests, "test_identical_duplicate_records_do_not_inflate_source_count"),
        (backend_tests, "source_publishers"),
        (api_tests, "sourcePublishers"),
        (read_tests, "treats damaged storage as a missing baseline"),
        (read_tests, "keeps at most 200 recent values"),
        (component_tests, "locally marks new events as read"),
        (component_tests, "2 public source records"),
    )
    missing = [token for source, token in required if token not in source]
    return CheckResult("v128_regression_tests", not missing, {"missing": missing})


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
    read_source = (repo_root / "apps/dsa-web/src/lib/marketEventReadState.ts").read_text(encoding="utf-8")
    component_source = (repo_root / "apps/dsa-web/src/components/market-home/DailyMarketEventCenterV126.tsx").read_text(encoding="utf-8")
    backend_tests = (repo_root / "tests/test_public_market_event_service.py").read_text(encoding="utf-8")
    api_tests = (repo_root / "apps/dsa-web/src/api/__tests__/marketWorkspace.test.ts").read_text(encoding="utf-8")
    read_tests = (repo_root / "apps/dsa-web/src/lib/__tests__/marketEventReadState.test.ts").read_text(encoding="utf-8")
    component_tests = (repo_root / "apps/dsa-web/src/components/market-home/__tests__/DailyMarketEventCenterV126.test.tsx").read_text(encoding="utf-8")
    yield backend_source_contract(backend_source)
    yield api_source_contract(schema_source, api_source)
    yield read_state_contract(read_source)
    yield frontend_retention_contract(component_source)
    yield regression_tests_contract(backend_tests, api_tests, read_tests, component_tests)
    yield homepage_bundle_check(repo_root / "static/assets")


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify DSA V128 event-source transparency and local read retention.")
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    args = parser.parse_args()
    checks = list(run_checks(args.repo_root.resolve()))
    for check in checks:
        print(f"[{'OK' if check.ok else 'FAIL'}] {check.name}: {check.details}")
    if not all(check.ok for check in checks):
        return 1
    print("DSA_PLATFORM_EVENT_SOURCE_RETENTION_V128_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
