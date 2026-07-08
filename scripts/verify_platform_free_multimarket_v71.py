from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
OK_MARKER = "DSA_PLATFORM_FREE_MULTIMARKET_V71_OK"


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
    "apps/dsa-web/src/pages/HomePage.tsx": [
        "fallbackPeerRows",
        "fallbackKlineScenarios",
        "港股重点数据",
        "加密货币重点数据",
        "沪深300",
        "恒生指数",
        "以太坊",
        "香港市场参照",
        "加密参照",
        "港交所公告通道",
        "协议与交易所事件",
        "basic-query-peer-table",
        "basic-query-kline-triggers",
        "Free mode shows concrete data first",
        "免费版先展示可用的真实数据",
    ],
    "apps/dsa-web/src/pages/__tests__/HomePage.test.tsx": [
        "keeps the same free detail modules visible for all market routes with basic snapshots",
        "600519.SH",
        "AAPL",
        "00700.HK",
        "BTC-USD",
        "A股重点数据",
        "美股重点数据",
        "港股重点数据",
        "加密货币重点数据",
        "basic-query-kline-triggers",
        "basic-query-peer-table",
        "localizes backend comparison targets in the Chinese free detail view",
        "沪深300",
        "纳斯达克综合指数",
        "恒生指数",
        "以太坊",
        "Hong Kong market reference.",
        "Large-cap crypto rotation reference.",
        "香港市场参照",
        "大市值加密资产轮动参照",
    ],
    ".gitignore": [
        "!scripts/verify_platform_free_multimarket_v71.py",
    ],
    "docs/superpowers/plans/2026-07-08-dsa-v71-free-multimarket-modules.md": [
        OK_MARKER,
        "local-only",
        "No AI calls",
        "No public search",
        "free multimarket modules",
        "same visible modules",
        "A-share",
        "US equity",
        "HK equity",
        "crypto",
        "localized backend comparison targets",
        "peer comparison table",
        "K-line triggers",
        "not investment advice",
        "Do not commit real API Key",
    ],
    "docs/superpowers/platform-review-slices.md": [
        "V71 Free Multimarket Modules Addendum",
        OK_MARKER,
        "scripts/verify_platform_free_multimarket_v71.py",
    ],
    "docs/superpowers/platform-release-candidate-manifest.md": [
        "V71 Free Multimarket Modules Manifest Addendum",
        OK_MARKER,
        "tests/test_platform_free_multimarket_v71.py",
    ],
    "scripts/verify_platform_release_candidate_package.py": [
        "verify_platform_free_multimarket_v71.py",
        "test_platform_free_multimarket_v71.py",
        "2026-07-08-dsa-v71-free-multimarket-modules.md",
    ],
    "tests/test_platform_release_candidate_package.py": [
        "include_v71",
        "test_reports_missing_free_multimarket_v71_files",
        "verify_platform_free_multimarket_v71.py",
        "test_platform_free_multimarket_v71.py",
        "2026-07-08-dsa-v71-free-multimarket-modules.md",
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
        print("DSA_PLATFORM_FREE_MULTIMARKET_V71_FAILED")
        return 1
    print(OK_MARKER)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
