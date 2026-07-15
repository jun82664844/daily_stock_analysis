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


def backend_source_record_contract(source: str) -> CheckResult:
    required = (
        "source_record = self._source_record(headline, source_state, as_of)",
        'source_records = existing["source_records"]',
        "len(source_records) < 8",
        '"source_records": [source_record]',
        "def _safe_http_url",
        "urlparse(url)",
        '{"http", "https"}',
        "not parsed.netloc",
        "def _source_record",
        '"publisher": publisher',
        '"event_time": published_at or as_of',
    )
    forbidden = ("import requests", "import httpx", "openai", "litellm", "ollama")
    lowered = source.casefold()
    missing = [token for token in required if token not in source]
    forbidden_hits = [token for token in forbidden if token in lowered]
    return CheckResult(
        "bounded_safe_source_records",
        not missing and not forbidden_hits,
        {"missing": missing, "forbidden_hits": forbidden_hits},
    )


def api_source_record_contract(schema_source: str, frontend_source: str) -> CheckResult:
    schema_required = (
        "class PublicMarketEventSourceRecord(StrictModel)",
        "publisher: str",
        "source: str",
        "url: Optional[str] = None",
        "event_time: str",
        "time_kind: MarketEventTimeKind",
        "source_records: List[PublicMarketEventSourceRecord] = Field(default_factory=list, max_length=8)",
    )
    frontend_required = (
        "sourceRecords: PublicMarketEventSourceRecord[]",
        "function safeHttpUrl(value: unknown)",
        "function normalizeEventSourceRecords(event: PublicMarketEvent)",
        "Array.isArray(event.sourceRecords)",
        "publisher: event.publisher ?? event.sourceState?.source",
        "url: safeHttpUrl(event.url)",
        "if (records.length >= 8) break",
    )
    missing = [f"schema:{token}" for token in schema_required if token not in schema_source]
    missing.extend(f"frontend:{token}" for token in frontend_required if token not in frontend_source)
    return CheckResult("backward_compatible_source_records", not missing, {"missing": missing})


def frontend_source_evidence_contract(source: str) -> CheckResult:
    required = (
        "expandedEventId",
        "aria-expanded",
        "aria-controls",
        "sourceRecords",
        "safeSourceLink",
        "查看来源",
        "收起来源",
        "已显示",
        "原文链接不可用",
        "多条来源记录不代表事实已独立证实。",
        "View sources",
        "Hide sources",
        "Showing",
        "Original link unavailable",
        "Multiple source records do not mean the facts were independently verified.",
        "仅提供公开资讯和数据，不构成投资建议。",
        "Public information and data only. Not investment advice.",
    )
    forbidden = ("买入", "卖出", "目标价", "收益预测", "target price", "return forecast", "trade instruction")
    missing = [token for token in required if token not in source]
    forbidden_hits = [token for token in forbidden if token in source.casefold()]
    return CheckResult(
        "bilingual_source_evidence_disclosure",
        not missing and not forbidden_hits,
        {"missing": missing, "forbidden_hits": forbidden_hits},
    )


def regression_tests_contract(backend_tests: str, api_tests: str, component_tests: str) -> CheckResult:
    required = (
        (backend_tests, "test_source_records_remove_non_http_links"),
        (backend_tests, 'events[0]["source_records"]'),
        (backend_tests, 'self.assertNotIn("source_link", events[0]["relevance_reasons"])'),
        (api_tests, "sourceRecords"),
        (api_tests, "javascript:alert(document.domain)"),
        (component_tests, "expands source evidence on demand with bilingual safe links"),
        (component_tests, "已显示 2 / 共 2 条公开来源记录"),
        (component_tests, "Showing 2 of 2 public source records"),
    )
    missing = [token for source, token in required if token not in source]
    return CheckResult("v129_regression_tests", not missing, {"missing": missing})


def homepage_bundle_check(
    assets_dir: Path,
    *,
    source_paths: Iterable[Path] = (),
) -> CheckResult:
    chunks = list(assets_dir.glob("HomePage-*.js"))
    if not chunks:
        return CheckResult("homepage_bundle", False, {"reason": "homepage_chunk_missing"})
    newest = max(chunks, key=lambda path: path.stat().st_mtime_ns)
    size = newest.stat().st_size
    existing_sources = [path for path in source_paths if path.exists()]
    latest_source_mtime_ns = max(
        (path.stat().st_mtime_ns for path in existing_sources),
        default=0,
    )
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
    component_source = (repo_root / "apps/dsa-web/src/components/market-home/DailyMarketEventCenterV126.tsx").read_text(encoding="utf-8")
    backend_tests = (repo_root / "tests/test_public_market_event_service.py").read_text(encoding="utf-8")
    api_tests = (repo_root / "apps/dsa-web/src/api/__tests__/marketWorkspace.test.ts").read_text(encoding="utf-8")
    component_tests = (repo_root / "apps/dsa-web/src/components/market-home/__tests__/DailyMarketEventCenterV126.test.tsx").read_text(encoding="utf-8")
    yield backend_source_record_contract(backend_source)
    yield api_source_record_contract(schema_source, api_source)
    yield frontend_source_evidence_contract(component_source)
    yield regression_tests_contract(backend_tests, api_tests, component_tests)
    yield homepage_bundle_check(
        repo_root / "static/assets",
        source_paths=(
            repo_root / "apps/dsa-web/src/api/marketWorkspace.ts",
            repo_root / "apps/dsa-web/src/components/market-home/DailyMarketEventCenterV126.tsx",
        ),
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify DSA V129 public event source evidence details.")
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    args = parser.parse_args()
    checks = list(run_checks(args.repo_root.resolve()))
    for check in checks:
        print(f"[{'OK' if check.ok else 'FAIL'}] {check.name}: {check.details}")
    if not all(check.ok for check in checks):
        return 1
    print("DSA_PLATFORM_EVENT_SOURCE_EVIDENCE_V129_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
