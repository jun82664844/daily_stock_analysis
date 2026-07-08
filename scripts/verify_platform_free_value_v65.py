from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
OK_MARKER = "DSA_PLATFORM_FREE_VALUE_V65_OK"


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
        "basic-query-free-value-summary",
        "basic-query-free-complete-read",
        "basic-query-free-feature-entry",
        "basic-query-feature-entry-news",
        "basic-query-feature-entry-kline",
        "basic-query-diagnostics-details",
        "免费版重点结论",
        "免费版完整速读",
        "机会看点",
        "下一步观察",
        "数据来源",
        "当前看点",
        "风险边界",
        "升级可解锁",
        "t('home.deepAnalyze')",
    ],
    "apps/dsa-web/src/pages/__tests__/HomePage.test.tsx": [
        "basic-query-free-value-summary",
        "basic-query-free-complete-read",
        "basic-query-free-feature-entry",
        "basic-query-feature-entry-news",
        "basic-query-feature-entry-kline",
        "basic-query-diagnostics-details",
        "免费版重点结论",
        "免费版完整速读",
        "机会看点",
        "下一步观察",
        "数据来源",
        "升级可解锁",
    ],
    ".gitignore": [
        "!scripts/verify_platform_free_value_v65.py",
    ],
    "docs/superpowers/plans/2026-07-08-dsa-v65-free-value-experience.md": [
        OK_MARKER,
        "local-only",
        "No AI calls",
        "No public search",
        "free value summary",
        "not investment advice",
    ],
    "docs/superpowers/platform-review-slices.md": [
        "V65 Free-Value Experience Addendum",
        OK_MARKER,
    ],
    "docs/superpowers/platform-release-candidate-manifest.md": [
        "V65 Free-Value Experience Manifest Addendum",
        OK_MARKER,
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
        print("DSA_PLATFORM_FREE_VALUE_V65_FAILED")
        return 1
    print(OK_MARKER)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
