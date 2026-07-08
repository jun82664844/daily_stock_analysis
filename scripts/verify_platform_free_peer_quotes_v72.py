from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
OK_MARKER = "DSA_PLATFORM_FREE_PEER_QUOTES_V72_OK"


@dataclass(frozen=True)
class CheckResult:
    check_id: str
    status: str
    elapsed_sec: float
    missing: list[str]

    def to_dict(self) -> dict:
        return {
            "check_id": self.check_id,
            "status": self.status,
            "elapsed_sec": round(self.elapsed_sec, 3),
            "missing": self.missing,
        }


REQUIRED_MARKERS: dict[str, list[str]] = {
    "src/services/basic_query_service.py": [
        "_DEFAULT_REFERENCE_QUOTE_TIMEOUT_SECONDS",
        "reference_quote_timeout_seconds",
        "_comparison_targets_with_reference_quotes",
        "_reference_quote_payloads_for_targets",
        "_fetch_reference_quote_from_yahoo_chart",
        "_yahoo_reference_symbol",
        "_reference_quote_payload",
        "_unavailable_reference_quote_payload",
        "\"reference_quote\"",
        "yahoo_chart_reference",
        "concurrent.futures.wait",
    ],
    "api/v1/schemas/basic_query.py": [
        "BasicReferenceQuotePayload",
        "reference_quote: Optional[BasicReferenceQuotePayload]",
        "current_price",
        "change_percent",
        "status: str = Field(\"unavailable\"",
    ],
    "apps/dsa-web/src/api/stocks.ts": [
        "referenceQuote",
        "currentPrice",
        "changePercent",
        "freshness",
        "status",
    ],
    "apps/dsa-web/src/pages/HomePage.tsx": [
        "参照行情",
        "参照价",
        "参照行情暂不可用",
        "免费版会显示可用的公共参照行情",
        "API 数据源",
        "row.referenceQuote?.status === 'available'",
        "item.referenceQuote?.status === 'available'",
    ],
    "apps/dsa-web/src/pages/__tests__/HomePage.test.tsx": [
        "shows free comparison reference quote values in Chinese mode",
        "referenceQuote",
        "参照价",
        "512.34",
        "+0.87%",
        "实时对比数值留给后续深度视图",
    ],
    "tests/test_basic_query_no_ai.py": [
        "test_no_ai_snapshot_enriches_free_comparison_targets_with_reference_quotes",
        "test_no_ai_snapshot_uses_yahoo_reference_quote_fallback_when_platform_source_is_empty",
        "unit_reference_quote",
        "unit_yahoo_reference",
        "\"reference_quote\"",
        "512.34",
        "20234.56",
    ],
    "tests/test_market_data_cache.py": [
        "quote_calls.count(\"AAPL\")",
        "quote_calls.count(\"QQQ\")",
        "quote_calls.count(\"^IXIC\")",
        "len(quote_calls), 3",
    ],
    ".gitignore": [
        "!scripts/verify_platform_free_peer_quotes_v72.py",
    ],
    "docs/superpowers/plans/2026-07-08-dsa-v72-free-peer-quotes.md": [
        OK_MARKER,
        "local-only",
        "No AI calls",
        "No public search",
        "free peer reference quotes",
        "same visible modules",
        "short timeout",
        "API-backed sources",
        "not investment advice",
        "Do not commit real API Key",
    ],
    "docs/superpowers/platform-review-slices.md": [
        "V72 Free Peer Quotes Addendum",
        OK_MARKER,
        "scripts/verify_platform_free_peer_quotes_v72.py",
    ],
    "docs/superpowers/platform-release-candidate-manifest.md": [
        "V72 Free Peer Quotes Manifest Addendum",
        OK_MARKER,
        "tests/test_basic_query_no_ai.py",
        "tests/test_market_data_cache.py",
    ],
    "scripts/verify_platform_release_candidate_package.py": [
        "verify_platform_free_peer_quotes_v72.py",
        "2026-07-08-dsa-v72-free-peer-quotes.md",
    ],
    "tests/test_platform_release_candidate_package.py": [
        "include_v72",
        "test_reports_missing_free_peer_quotes_v72_files",
        "verify_platform_free_peer_quotes_v72.py",
        "2026-07-08-dsa-v72-free-peer-quotes.md",
    ],
}


def _read_text(root: Path, rel_path: str) -> str:
    return (root / rel_path).read_text(encoding="utf-8", errors="replace")


def _check_markers(root: Path, rel_path: str, markers: list[str]) -> CheckResult:
    started = time.monotonic()
    path = root / rel_path
    if not path.exists():
        return CheckResult(rel_path, "failed", time.monotonic() - started, ["file missing"])
    text = _read_text(root, rel_path)
    missing = [marker for marker in markers if marker not in text]
    return CheckResult(rel_path, "failed" if missing else "passed", time.monotonic() - started, missing)


def run_checks(root: Path = REPO_ROOT) -> list[CheckResult]:
    return [_check_markers(root, rel_path, markers) for rel_path, markers in REQUIRED_MARKERS.items()]


def main() -> int:
    results = run_checks(REPO_ROOT)
    failed = [result for result in results if result.status != "passed"]
    for result in results:
        prefix = "[OK]" if result.status == "passed" else "[FAIL]"
        print(f"{prefix} {result.check_id}")
        if result.missing:
            print(f"      missing={json.dumps(result.missing, ensure_ascii=False)}")
    print(json.dumps([result.to_dict() for result in results], ensure_ascii=False, indent=2))
    if failed:
        print("DSA_PLATFORM_FREE_PEER_QUOTES_V72_FAILED")
        return 1
    print(OK_MARKER)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
