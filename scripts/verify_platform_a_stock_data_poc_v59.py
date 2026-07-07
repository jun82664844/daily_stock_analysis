from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
OK_MARKER = "DSA_PLATFORM_A_STOCK_DATA_POC_V59_OK"


@dataclass(frozen=True)
class CheckResult:
    check_id: str
    title: str
    status: str
    elapsed_sec: float
    missing: list[str]

    def to_dict(self) -> dict:
        return {
            "check_id": self.check_id,
            "title": self.title,
            "status": self.status,
            "elapsed_sec": round(self.elapsed_sec, 3),
            "missing": self.missing,
        }


REQUIRED_MARKERS: dict[str, list[str]] = {
    "src/services/a_share_enrichment_service.py": [
        "class AShareEnrichmentService",
        "CHANNEL_SLUGS",
        "fund-flow",
        "concept-blocks",
        '"ai_used": False',
        '"public_search_used": False',
        "not investment advice",
    ],
    "src/services/basic_query_service.py": [
        "AShareEnrichmentService",
        "a_share_enrichment_service",
        "a_share_enrichment",
        'route.market != "cn"',
    ],
    "api/v1/schemas/basic_query.py": [
        "BasicAShareEnrichmentChannelPayload",
        "BasicAShareEnrichmentPayload",
        "a_share_enrichment",
    ],
    "tests/test_a_share_enrichment_service.py": [
        "test_builds_five_channel_payload_from_fixture_http_data",
        "test_degrades_without_breaking_quick_query_when_upstream_fails",
        "fund-flow",
    ],
    "tests/test_basic_query_no_ai.py": [
        "test_a_share_snapshot_includes_a_stock_data_enrichment_poc",
        "a_share_enrichment",
        "dragon_tiger",
    ],
    "apps/dsa-web/src/api/stocks.ts": [
        "aShareEnrichment",
        "publicSearchUsed",
        "premiumUnlock",
    ],
    "apps/dsa-web/src/api/__tests__/stocks.test.ts": [
        "loads A-share enrichment channels as camelCase snapshot data",
        "aShareEnrichment",
    ],
    "apps/dsa-web/src/pages/HomePage.tsx": [
        'data-testid="basic-query-a-share-enrichment"',
        "A-share data expansion",
        "Fund-flow channel",
        "a_stock_data_poc_adapter",
    ],
    "apps/dsa-web/src/pages/__tests__/HomePage.test.tsx": [
        "basic-query-a-share-enrichment",
        "A股增强数据",
        "资金流通道",
        "龙虎榜通道",
    ],
    "docs/superpowers/plans/2026-07-07-dsa-v59-a-stock-data-poc.md": [
        OK_MARKER,
        "local-only",
        "not investment advice",
        "Do not commit real API Key",
    ],
}


def _read_text(root: Path, rel_path: str) -> str:
    return (root / rel_path).read_text(encoding="utf-8", errors="replace")


def _check_markers(root: Path, rel_path: str, markers: list[str]) -> CheckResult:
    started = time.monotonic()
    path = root / rel_path
    if not path.exists():
        return CheckResult(rel_path, rel_path, "failed", time.monotonic() - started, ["file missing"])
    text = _read_text(root, rel_path)
    missing = [marker for marker in markers if marker not in text]
    return CheckResult(
        rel_path,
        rel_path,
        "failed" if missing else "passed",
        time.monotonic() - started,
        missing,
    )


def run_checks(root: Path = REPO_ROOT) -> list[CheckResult]:
    return [
        _check_markers(root, rel_path, markers)
        for rel_path, markers in REQUIRED_MARKERS.items()
    ]


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
        print("DSA_PLATFORM_A_STOCK_DATA_POC_V59_FAILED")
        return 1
    print(OK_MARKER)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
