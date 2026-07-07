from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
OK_MARKER = "DSA_PLATFORM_A_STOCK_DATA_USEFUL_V62_OK"


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
        "_fetch_public_a_stock_payload",
        "push2.eastmoney.com/api/qt/stock/fflow/kline/get",
        "push2.eastmoney.com/api/qt/slist/get",
        "reportapi.eastmoney.com/report/list",
        "datacenter-web.eastmoney.com/api/data/v1/get",
        "www.cninfo.com.cn/new/hisAnnouncement/query",
        "gssh0{code}",
        "_fallback_sector_bits",
        "default_timeout",
        "主力资金净额",
        "资金流通道已查询",
        "当前背景",
        "checked",
        "Information analysis only; not investment advice.",
    ],
    "tests/test_a_share_enrichment_service.py": [
        "test_default_a_stock_data_adapter_builds_useful_channels_from_public_payloads",
        "test_checked_empty_fund_flow_reports_clear_degradation_not_reserved_lane",
        "test_default_adapter_timeout_keeps_checked_channel_copy",
        "test_cninfo_fallback_uses_sse_gssh_orgid_for_shanghai_codes",
        "test_sector_channel_uses_moutai_local_fallback_when_public_source_empty",
        "test_a_stock_data_source_mode_uses_longer_default_timeout_than_local_poc",
        "主力资金",
        "当前背景",
    ],
    "apps/dsa-web/src/pages/HomePage.tsx": [
        "shouldApplyAShareSourceMode",
        "useState<AShareSourceMode>('a_stock_data')",
        "options.aShareSourceMode = selectedAShareSourceMode",
        "a-share-source-control",
    ],
    "apps/dsa-web/src/pages/__tests__/HomePage.test.tsx": [
        "aShareSourceMode: 'a_stock_data'",
        "a-share-source-control",
    ],
    "scripts/verify_platform_a_stock_data_useful_v62.py": [
        OK_MARKER,
        "_fetch_public_a_stock_payload",
        "shouldApplyAShareSourceMode",
    ],
    "tests/test_platform_a_stock_data_useful_v62.py": [
        "test_verifier_passes_when_all_v62_markers_exist",
        "test_verifier_fails_when_public_payload_marker_is_missing",
        OK_MARKER,
    ],
    ".gitignore": [
        "!scripts/verify_platform_a_stock_data_useful_v62.py",
    ],
    "docs/superpowers/plans/2026-07-07-dsa-v62-a-stock-data-useful.md": [
        OK_MARKER,
        "local-only",
        "No AI calls",
        "No public search",
        "a-stock-data",
        "CNINFO",
        "Eastmoney",
        "not investment advice",
        "Do not commit real API Key",
    ],
    "docs/superpowers/platform-review-slices.md": [
        "V62 A-Stock-Data Useful Data Addendum",
        "scripts/verify_platform_a_stock_data_useful_v62.py",
        OK_MARKER,
    ],
    "docs/superpowers/platform-release-candidate-manifest.md": [
        "V62 A-Stock-Data Useful Data Manifest Addendum",
        "scripts/verify_platform_a_stock_data_useful_v62.py",
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
        print("DSA_PLATFORM_A_STOCK_DATA_USEFUL_V62_FAILED")
        return 1
    print(OK_MARKER)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
