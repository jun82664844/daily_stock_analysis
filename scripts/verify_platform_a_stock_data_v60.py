from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
OK_MARKER = "DSA_PLATFORM_A_STOCK_DATA_V60_OK"


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
        "source_mode",
        "a_stock_data",
        "A_STOCK_DATA_SOURCE_MODE",
        "A_STOCK_DATA_CACHE_TTL_SEC",
        "A_STOCK_DATA_MIN_INTERVAL_SEC",
        "A_STOCK_DATA_SKILL_ROOT",
        "a-stock-data://",
        "_cache",
        "_last_request_at",
        "rate_limited_channels",
        "skill_revision",
        "Information analysis only; not investment advice.",
    ],
    "tests/test_a_share_enrichment_service.py": [
        "test_a_stock_data_source_mode_uses_skill_metadata_and_cache",
        "test_a_stock_data_source_mode_reuses_stale_cache_during_rate_limit",
        "test_a_stock_data_source_mode_degrades_failed_channel_only",
    ],
    "api/v1/schemas/basic_query.py": [
        "source_mode",
        "skill",
        "diagnostics",
        "BasicAShareEnrichmentPayload",
    ],
    "apps/dsa-web/src/api/stocks.ts": [
        "sourceMode",
        "skill?: Record<string, unknown>",
        "diagnostics?: Record<string, unknown>",
    ],
    "scripts/verify_platform_a_stock_data_v60.py": [
        OK_MARKER,
        "A_STOCK_DATA_CACHE_TTL_SEC",
        "a-stock-data://",
    ],
    "tests/test_platform_a_stock_data_v60.py": [
        "test_verifier_passes_when_all_v60_markers_exist",
        "test_verifier_fails_when_cache_marker_is_missing",
        OK_MARKER,
    ],
    ".gitignore": [
        "!scripts/verify_platform_a_stock_data_v60.py",
    ],
    "docs/superpowers/plans/2026-07-07-dsa-v60-a-stock-data-source.md": [
        OK_MARKER,
        "local-only",
        "external calls disabled by default",
        "a-stock-data",
        "cache",
        "rate limit",
        "not investment advice",
        "Do not commit real API Key",
    ],
    "docs/superpowers/platform-review-slices.md": [
        "V60 A-Stock-Data Source Addendum",
        "scripts/verify_platform_a_stock_data_v60.py",
        OK_MARKER,
    ],
    "docs/superpowers/platform-release-candidate-manifest.md": [
        "V60 A-Stock-Data Source Manifest Addendum",
        "scripts/verify_platform_a_stock_data_v60.py",
        OK_MARKER,
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
        print("DSA_PLATFORM_A_STOCK_DATA_V60_FAILED")
        return 1
    print(OK_MARKER)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
