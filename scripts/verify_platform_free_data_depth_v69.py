from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
OK_MARKER = "DSA_PLATFORM_FREE_DATA_DEPTH_V69_OK"


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
        "basicDataDepthBoard",
        "basic-query-data-depth-board",
        "Free data depth board",
        "免费版真实数据面板",
        "A-share key data",
        "A股重点数据",
        "US equity key data",
        "美股重点数据",
        "Core data",
        "核心数据",
        "Technical structure",
        "技术结构",
        "Events and filings",
        "资讯与事件",
        "Peers and risks",
        "同业与风险",
        "免费版先展示可用的真实数据",
        "仅作信息分析，不构成投资建议",
    ],
    "apps/dsa-web/src/pages/__tests__/HomePage.test.tsx": [
        "basic-query-data-depth-board",
        "免费版真实数据面板",
        "美股重点数据",
        "核心数据",
        "技术结构",
        "资讯与事件",
        "同业与风险",
        "SEC 文件通道",
        "财务快照通道",
        "QQQ",
        "XLK",
        "仅作信息分析，不构成投资建议",
        "Free data depth board",
    ],
    ".gitignore": [
        "!scripts/verify_platform_free_data_depth_v69.py",
    ],
    "docs/superpowers/plans/2026-07-08-dsa-v69-free-data-depth.md": [
        OK_MARKER,
        "local-only",
        "No AI calls",
        "No public search",
        "free data depth",
        "same visible modules",
        "A-share",
        "US equity",
        "not investment advice",
        "Do not commit real API Key",
    ],
    "docs/superpowers/platform-review-slices.md": [
        "V69 Free Data Depth Addendum",
        OK_MARKER,
        "scripts/verify_platform_free_data_depth_v69.py",
    ],
    "docs/superpowers/platform-release-candidate-manifest.md": [
        "V69 Free Data Depth Manifest Addendum",
        OK_MARKER,
        "tests/test_platform_free_data_depth_v69.py",
    ],
    "scripts/verify_platform_release_candidate_package.py": [
        "verify_platform_free_data_depth_v69.py",
        "test_platform_free_data_depth_v69.py",
        "2026-07-08-dsa-v69-free-data-depth.md",
    ],
    "tests/test_platform_release_candidate_package.py": [
        "include_v69",
        "test_reports_missing_free_data_depth_v69_files",
        "verify_platform_free_data_depth_v69.py",
        "test_platform_free_data_depth_v69.py",
        "2026-07-08-dsa-v69-free-data-depth.md",
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
        print("DSA_PLATFORM_FREE_DATA_DEPTH_V69_FAILED")
        return 1
    print(OK_MARKER)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
