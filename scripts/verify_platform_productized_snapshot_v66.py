from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
OK_MARKER = "DSA_PLATFORM_PRODUCTIZED_SNAPSHOT_V66_OK"


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
        "basicProfessionalOverview",
        "basic-query-professional-overview",
        "Professional overview",
        "专业速览",
        "Trend score",
        "趋势评分",
        "Risk level",
        "风险等级",
        "Data channel",
        "数据通道",
        "Free web source",
        "免费网络源",
        "Premium API source",
        "高级 API 源",
        "Module navigation",
        "模块导航",
        "Quote overview",
        "行情概览",
        "Technical view",
        "技术面",
        "News center",
        "资讯中心",
        "K-line forecast",
        "K线预测",
        "not investment advice",
    ],
    "apps/dsa-web/src/pages/__tests__/HomePage.test.tsx": [
        "basic-query-professional-overview",
        "专业速览",
        "趋势评分",
        "82/100",
        "风险等级",
        "免费网络源",
        "高级 API 源",
        "模块导航",
        "行情概览",
        "技术面",
        "资讯中心",
        "K线预测",
        "高级版解锁",
    ],
    ".gitignore": [
        "!scripts/verify_platform_productized_snapshot_v66.py",
    ],
    "docs/superpowers/plans/2026-07-08-dsa-v66-productized-snapshot.md": [
        OK_MARKER,
        "local-only",
        "No AI calls",
        "No public search",
        "same visible modules",
        "free web source",
        "premium API source",
        "not investment advice",
    ],
    "docs/superpowers/platform-review-slices.md": [
        "V66 Productized Snapshot Addendum",
        OK_MARKER,
        "apps/dsa-web/src/pages/HomePage.tsx",
        "scripts/verify_platform_productized_snapshot_v66.py",
    ],
    "docs/superpowers/platform-release-candidate-manifest.md": [
        "V66 Productized Snapshot Manifest Addendum",
        OK_MARKER,
        "apps/dsa-web/src/pages/__tests__/HomePage.test.tsx",
        "tests/test_platform_productized_snapshot_v66.py",
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
        print("DSA_PLATFORM_PRODUCTIZED_SNAPSHOT_V66_FAILED")
        return 1
    print(OK_MARKER)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
