from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
OK_MARKER = "DSA_PLATFORM_A_STOCK_DATA_UI_V61_OK"


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
    "api/v1/endpoints/stocks.py": [
        "a_share_source_mode",
        "pattern=\"^(poc|a_stock_data|off)$\"",
        "AShareEnrichmentService(source_mode=a_share_source_mode)",
    ],
    "tests/test_basic_query_no_ai.py": [
        "test_snapshot_accepts_a_share_source_mode_query_param",
        "source_mode",
        "a_stock_data",
    ],
    "apps/dsa-web/src/api/stocks.ts": [
        "BasicSnapshotOptions",
        "aShareSourceMode",
        "a_share_source_mode",
    ],
    "apps/dsa-web/src/api/__tests__/stocks.test.ts": [
        "loads A-share snapshots with a selected enrichment source mode",
        "a_share_source_mode=a_stock_data",
    ],
    "apps/dsa-web/src/pages/HomePage.tsx": [
        "a-share-source-control",
        "A_SHARE_SOURCE_MODES",
        "handleAShareSourceModeSelect",
        "handleAShareSourceProbe",
        "a_stock_data",
        "a-share-source-mode-${mode}",
        "a-share-source-probe-${symbol}",
        "'000001'",
        "formatAShareCacheDiagnostics",
        "formatAShareSkillRevision",
    ],
    "apps/dsa-web/src/pages/__tests__/HomePage.test.tsx": [
        "lets users switch A-share enrichment source mode and run sample probes",
        "a-share-source-control",
        "cache H1 / M0 / S0",
        "repo bcda405",
        "aShareSourceMode: 'a_stock_data'",
    ],
    ".gitignore": [
        "!scripts/verify_platform_a_stock_data_ui_v61.py",
    ],
    "docs/superpowers/plans/2026-07-07-dsa-v61-a-stock-data-ui.md": [
        OK_MARKER,
        "local-only",
        "a-stock-data",
        "600519",
        "000001",
        "not investment advice",
        "Do not commit real API Key",
    ],
    "docs/superpowers/platform-review-slices.md": [
        "V61 A-Stock-Data UI Addendum",
        "scripts/verify_platform_a_stock_data_ui_v61.py",
        OK_MARKER,
    ],
    "docs/superpowers/platform-release-candidate-manifest.md": [
        "V61 A-Stock-Data UI Manifest Addendum",
        "scripts/verify_platform_a_stock_data_ui_v61.py",
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
        print("DSA_PLATFORM_A_STOCK_DATA_UI_V61_FAILED")
        return 1
    print(OK_MARKER)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
