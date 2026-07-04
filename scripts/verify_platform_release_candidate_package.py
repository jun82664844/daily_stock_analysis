from __future__ import annotations

import argparse
import json
import re
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Sequence


REPO_ROOT = Path(__file__).resolve().parents[1]

REVIEW_SLICES_DOC = "docs/superpowers/platform-review-slices.md"
RELEASE_MANIFEST_DOC = "docs/superpowers/platform-release-candidate-manifest.md"
ENV_TEMPLATE = "docs/superpowers/platform-production-env.example"

REQUIRED_FILES = (
    "docs/superpowers/platform-local-v1-acceptance-status.md",
    "docs/superpowers/platform-local-v1-operability.md",
    "docs/superpowers/platform-local-v1-security-checklist.md",
    "docs/superpowers/platform-product-rules.md",
    "docs/superpowers/platform-v2-launch-readiness.md",
    "docs/superpowers/platform-v2-handoff-status.md",
    "docs/superpowers/platform-legal-copy-draft.md",
    ENV_TEMPLATE,
    "docs/superpowers/plans/2026-07-02-dsa-local-v5-operability.md",
    "docs/superpowers/plans/2026-07-02-dsa-local-v6-usability.md",
    "docs/superpowers/plans/2026-07-02-dsa-local-v7-query-speed.md",
    "docs/superpowers/plans/2026-07-02-dsa-local-v8-query-resilience.md",
    "docs/superpowers/plans/2026-07-02-dsa-local-v9-market-source-health.md",
    "docs/superpowers/plans/2026-07-02-dsa-local-v10-persistent-market-cache.md",
    "docs/superpowers/plans/2026-07-02-dsa-local-v11-market-source-ops.md",
    "docs/superpowers/plans/2026-07-02-dsa-local-v12-market-prewarm-console.md",
    "docs/superpowers/plans/2026-07-03-dsa-local-v13-market-recovery-console.md",
    "docs/superpowers/plans/2026-07-03-dsa-local-v14-real-use-loop.md",
    "docs/superpowers/plans/2026-07-03-dsa-local-v15-user-query-loop.md",
    "docs/superpowers/plans/2026-07-03-dsa-local-v16-browser-user-loop.md",
    "docs/superpowers/plans/2026-07-03-dsa-local-v17-user-watchlist.md",
    "docs/superpowers/plans/2026-07-03-dsa-local-v18-watchlist-board.md",
    "docs/superpowers/plans/2026-07-03-dsa-local-v19-query-workspace.md",
    "docs/superpowers/plans/2026-07-03-dsa-local-v20-public-entry.md",
    "docs/superpowers/plans/2026-07-03-dsa-local-v21-public-user-flow.md",
    "docs/superpowers/plans/2026-07-03-dsa-local-v22-market-refresh.md",
    "docs/superpowers/plans/2026-07-03-dsa-local-v23-history-snapshot-boundary.md",
    "docs/superpowers/plans/2026-07-03-dsa-local-v24-history-center.md",
    "docs/superpowers/plans/2026-07-03-dsa-local-v25-history-center-persistence.md",
    "docs/superpowers/plans/2026-07-03-dsa-local-v26-history-center-usability.md",
    "docs/superpowers/plans/2026-07-04-dsa-local-v27-history-export.md",
    "docs/superpowers/plans/2026-07-04-dsa-local-v28-history-state.md",
    "docs/superpowers/plans/2026-07-04-dsa-local-v29-history-ops.md",
    "docs/superpowers/plans/2026-07-04-dsa-local-v30-history-detail.md",
    REVIEW_SLICES_DOC,
    RELEASE_MANIFEST_DOC,
    "scripts/verify_local_v1_operability.py",
    "scripts/verify_platform_v2_readiness.py",
    "scripts/verify_platform_release_candidate_package.py",
    "scripts/verify_platform_user_e2e.py",
    "scripts/verify_platform_billing_lifecycle.py",
    "scripts/verify_platform_query_quality_v4.py",
    "scripts/verify_platform_local_functional_v5.py",
    "scripts/verify_platform_local_usability_v6.py",
    "scripts/verify_platform_local_query_speed_v7.py",
    "scripts/verify_platform_local_query_resilience_v8.py",
    "scripts/verify_platform_local_market_source_health_v9.py",
    "scripts/verify_platform_local_persistent_market_cache_v10.py",
    "scripts/verify_platform_local_market_source_ops_v11.py",
    "scripts/verify_platform_local_market_prewarm_console_v12.py",
    "scripts/verify_platform_local_market_recovery_console_v13.py",
    "scripts/verify_platform_local_real_use_loop_v14.py",
    "scripts/verify_platform_local_user_query_loop_v15.py",
    "scripts/verify_platform_local_browser_user_loop_v16.py",
    "scripts/verify_platform_local_watchlist_v17.py",
    "scripts/verify_platform_local_watchlist_board_v18.py",
    "scripts/verify_platform_local_query_workspace_v19.py",
    "scripts/verify_platform_local_public_entry_v20.py",
    "scripts/verify_platform_local_public_user_flow_v21.py",
    "scripts/verify_platform_local_market_refresh_v22.py",
    "scripts/verify_platform_local_history_snapshot_boundary_v23.py",
    "scripts/verify_platform_local_history_center_v24.py",
    "scripts/verify_platform_local_history_center_v25.py",
    "scripts/verify_platform_local_history_center_v26.py",
    "scripts/verify_platform_local_history_export_v27.py",
    "scripts/verify_platform_local_history_state_v28.py",
    "scripts/verify_platform_local_history_ops_v29.py",
    "scripts/verify_platform_local_history_detail_v30.py",
    "scripts/cleanup_platform_e2e_data.py",
    "src/platform_watchlist.py",
    "src/services/market_source_ops.py",
    "src/services/local_functional_status.py",
    "tests/test_platform_release_candidate_package.py",
    "tests/test_platform_user_e2e_safety.py",
    "tests/test_billing_subscription_lifecycle.py",
    "tests/test_platform_query_quality_v4.py",
    "tests/test_platform_local_functional_v5.py",
    "tests/test_platform_local_usability_v6.py",
    "tests/test_platform_local_query_speed_v7.py",
    "tests/test_platform_local_query_resilience_v8.py",
    "tests/test_platform_local_market_source_health_v9.py",
    "tests/test_platform_local_persistent_market_cache_v10.py",
    "tests/test_platform_local_market_source_ops_v11.py",
    "tests/test_platform_local_market_prewarm_console_v12.py",
    "tests/test_platform_local_market_recovery_console_v13.py",
    "tests/test_platform_local_real_use_loop_v14.py",
    "tests/test_platform_local_user_query_loop_v15.py",
    "tests/test_platform_local_browser_user_loop_v16.py",
    "tests/test_platform_local_watchlist_v17.py",
    "tests/test_platform_local_watchlist_v17_verifier.py",
    "tests/test_platform_local_watchlist_board_v18.py",
    "tests/test_platform_local_query_workspace_v19.py",
    "tests/test_platform_local_public_entry_v20.py",
    "tests/test_platform_local_public_user_flow_v21.py",
    "tests/test_platform_local_market_refresh_v22.py",
    "tests/test_platform_local_history_snapshot_boundary_v23.py",
    "tests/test_platform_local_history_center_v24.py",
    "tests/test_platform_local_history_center_v25.py",
    "tests/test_platform_local_history_center_v26.py",
    "tests/test_platform_local_history_export_v27.py",
    "tests/test_platform_local_history_state_v28.py",
    "tests/test_platform_local_history_ops_v29.py",
    "tests/test_platform_local_history_detail_v30.py",
    "apps/dsa-web/playwright.config.ts",
    "apps/dsa-web/e2e/platform-user-e2e.spec.ts",
)

VERIFIER_FILES = (
    "scripts/verify_local_v1_operability.py",
    "scripts/verify_platform_v2_readiness.py",
    "scripts/verify_platform_release_candidate_package.py",
    "scripts/verify_platform_user_e2e.py",
    "scripts/verify_platform_billing_lifecycle.py",
    "scripts/verify_platform_query_quality_v4.py",
    "scripts/verify_platform_local_functional_v5.py",
    "scripts/verify_platform_local_usability_v6.py",
    "scripts/verify_platform_local_query_speed_v7.py",
    "scripts/verify_platform_local_query_resilience_v8.py",
    "scripts/verify_platform_local_market_source_health_v9.py",
    "scripts/verify_platform_local_persistent_market_cache_v10.py",
    "scripts/verify_platform_local_market_source_ops_v11.py",
    "scripts/verify_platform_local_market_prewarm_console_v12.py",
    "scripts/verify_platform_local_market_recovery_console_v13.py",
    "scripts/verify_platform_local_real_use_loop_v14.py",
    "scripts/verify_platform_local_user_query_loop_v15.py",
    "scripts/verify_platform_local_browser_user_loop_v16.py",
    "scripts/verify_platform_local_watchlist_v17.py",
    "scripts/verify_platform_local_watchlist_board_v18.py",
    "scripts/verify_platform_local_query_workspace_v19.py",
    "scripts/verify_platform_local_public_entry_v20.py",
    "scripts/verify_platform_local_public_user_flow_v21.py",
    "scripts/verify_platform_local_market_refresh_v22.py",
    "scripts/verify_platform_local_history_snapshot_boundary_v23.py",
    "scripts/verify_platform_local_history_center_v24.py",
    "scripts/verify_platform_local_history_center_v25.py",
    "scripts/verify_platform_local_history_center_v26.py",
    "scripts/verify_platform_local_history_export_v27.py",
    "scripts/verify_platform_local_history_state_v28.py",
    "scripts/verify_platform_local_history_ops_v29.py",
    "scripts/verify_platform_local_history_detail_v30.py",
    "scripts/cleanup_platform_e2e_data.py",
)

SLICE_IDS = (
    "backend-platform-foundation",
    "frontend-platform-experience",
    "tests-and-verifiers",
    "docs-and-config",
    "build-and-ignore-impact",
    "manual-confirmation",
)

EXPECTED_SAFE_VALUES = {
    "ADMIN_AUTH_ENABLED": "true",
    "PLATFORM_USER_AUTH_ENABLED": "true",
    "PLATFORM_CSRF_ENABLED": "true",
    "BILLING_ENABLED": "false",
    "SEARXNG_PUBLIC_INSTANCES_ENABLED": "false",
    "ENABLE_FUNDAMENTAL_PIPELINE": "false",
    "ENABLE_CHIP_DISTRIBUTION": "false",
    "DAILY_MARKET_CONTEXT_ENABLED": "false",
    "DEBUG": "false",
    "CORS_ALLOW_ALL": "false",
}

REQUIRED_ENV_KEYS = {
    "ADMIN_AUTH_ENABLED",
    "PLATFORM_USER_AUTH_ENABLED",
    "PLATFORM_CSRF_ENABLED",
    "DATABASE_PATH",
    "DSA_SECRET_SOURCE",
    "LITELLM_MODEL",
    "SEARXNG_PUBLIC_INSTANCES_ENABLED",
    "ENABLE_FUNDAMENTAL_PIPELINE",
    "ENABLE_CHIP_DISTRIBUTION",
    "DAILY_MARKET_CONTEXT_ENABLED",
    "REALTIME_CACHE_TTL",
    "BILLING_ENABLED",
    "DEBUG",
    "CORS_ALLOW_ALL",
    "LOCAL_LLM_ENABLED",
    "LOCAL_LLM_MAX_CONCURRENT",
}

SECRET_VALUE_PATTERNS = (
    re.compile(r"\bsk-[A-Za-z0-9._-]{8,}\b"),
    re.compile(r"\bAIza[0-9A-Za-z_-]{20,}\b"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"\bghp_[0-9A-Za-z]{20,}\b"),
    re.compile(r"\bxox[baprs]-[0-9A-Za-z-]{20,}\b"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
)


@dataclass(frozen=True)
class PackageResult:
    check_id: str
    title: str
    status: str
    elapsed_sec: float = 0.0
    error: str = ""
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "check_id": self.check_id,
            "title": self.title,
            "status": self.status,
            "elapsed_sec": round(self.elapsed_sec, 3),
            "error": self.error,
            "metadata": self.metadata,
        }


@dataclass(frozen=True)
class DirtyEntry:
    status: str
    path: str


def _result(
    check_id: str,
    title: str,
    started: float,
    *,
    status: str = "passed",
    error: str = "",
    metadata: dict | None = None,
) -> PackageResult:
    return PackageResult(
        check_id=check_id,
        title=title,
        status=status,
        elapsed_sec=time.monotonic() - started,
        error=error,
        metadata=metadata or {},
    )


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _parse_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw_line in _read_text(path).splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def _contains_secret_like_value(value: str) -> bool:
    return any(pattern.search(value or "") for pattern in SECRET_VALUE_PATTERNS)


def _normalize_rel_path(value: str) -> str:
    return value.replace("\\", "/").strip()


def parse_git_status(stdout: str) -> list[DirtyEntry]:
    entries: list[DirtyEntry] = []
    for line in stdout.splitlines():
        if not line.strip():
            continue
        status = line[:2].strip() or line[:2]
        path = _normalize_rel_path(line[3:])
        if " -> " in path:
            path = _normalize_rel_path(path.split(" -> ", 1)[1])
        entries.append(DirtyEntry(status=status, path=path))
    return entries


def _git_status_entries(root: Path) -> list[DirtyEntry]:
    completed = subprocess.run(
        ["git", "status", "--short", "--untracked-files=all"],
        cwd=root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError("git status --short --untracked-files=all failed")
    return parse_git_status(completed.stdout)


def classify_dirty_path(path: str) -> str | None:
    normalized = _normalize_rel_path(path)
    if normalized in {".gitignore"} or normalized.startswith("static/"):
        return "build-and-ignore-impact"
    if normalized == "requirements.txt":
        return "manual-confirmation"
    if normalized.startswith("docs/superpowers/"):
        return "docs-and-config"
    if normalized in {"apps/dsa-web/playwright.config.ts"} or normalized.startswith("apps/dsa-web/e2e/"):
        return "tests-and-verifiers"
    if (
        normalized.startswith("scripts/verify_")
        or normalized == "scripts/cleanup_platform_e2e_data.py"
        or normalized.startswith("tests/")
    ):
        return "tests-and-verifiers"
    if normalized == "apps/dsa-web/index.html" or normalized.startswith("apps/dsa-web/src/"):
        return "frontend-platform-experience"
    if normalized.startswith("api/") or normalized.startswith("src/"):
        return "backend-platform-foundation"
    return None


def _run_required_files_check(root: Path) -> PackageResult:
    started = time.monotonic()
    missing = sorted(rel_path for rel_path in REQUIRED_FILES if not (root / rel_path).exists())
    if missing:
        return _result(
            "required_files_present",
            "Required V1/V2 release-candidate files exist",
            started,
            status="failed",
            error="required files are missing",
            metadata={"missing_files": missing},
        )
    return _result(
        "required_files_present",
        "Required V1/V2 release-candidate files exist",
        started,
        metadata={"checked_files": sorted(REQUIRED_FILES)},
    )


def _run_verifiers_visible_check(root: Path) -> PackageResult:
    started = time.monotonic()
    ignored: list[str] = []
    for rel_path in VERIFIER_FILES:
        completed = subprocess.run(
            ["git", "check-ignore", "-q", rel_path],
            cwd=root,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        if completed.returncode == 0:
            ignored.append(rel_path)
    if ignored:
        return _result(
            "verifiers_visible_to_git",
            "Critical verifier files are not gitignored",
            started,
            status="failed",
            error="verifier files are hidden by gitignore",
            metadata={"ignored_files": ignored},
        )
    return _result(
        "verifiers_visible_to_git",
        "Critical verifier files are not gitignored",
        started,
        metadata={"checked_files": sorted(VERIFIER_FILES)},
    )


def _run_prod_env_check(root: Path) -> PackageResult:
    started = time.monotonic()
    path = root / ENV_TEMPLATE
    if not path.exists():
        return _result(
            "prod_env_template_safe",
            "Production env template has safe defaults",
            started,
            status="failed",
            error="production env template is missing",
        )
    values = {key: value.strip() for key, value in _parse_env_file(path).items()}
    missing = sorted(REQUIRED_ENV_KEYS - set(values))
    unsafe_values = {
        key: {"expected": expected, "actual_present": key in values}
        for key, expected in EXPECTED_SAFE_VALUES.items()
        if values.get(key, "").lower() != expected
    }
    secret_like_keys = sorted(key for key, value in values.items() if _contains_secret_like_value(value))
    if missing or unsafe_values or secret_like_keys:
        return _result(
            "prod_env_template_safe",
            "Production env template has safe defaults",
            started,
            status="failed",
            error="production env template is incomplete or unsafe",
            metadata={
                "missing_keys": missing,
                "unsafe_values": unsafe_values,
                "secret_like_keys": secret_like_keys,
            },
        )
    return _result(
        "prod_env_template_safe",
        "Production env template has safe defaults",
        started,
        metadata={"checked_keys": sorted(REQUIRED_ENV_KEYS), "safe_flags": sorted(EXPECTED_SAFE_VALUES)},
    )


def _run_docs_safety_copy_check(root: Path) -> PackageResult:
    started = time.monotonic()
    doc_paths = (
        "docs/superpowers/platform-v2-launch-readiness.md",
        "docs/superpowers/platform-legal-copy-draft.md",
        "docs/superpowers/platform-production-env.example",
        REVIEW_SLICES_DOC,
        RELEASE_MANIFEST_DOC,
    )
    missing_docs = [rel_path for rel_path in doc_paths if not (root / rel_path).exists()]
    combined = "\n".join(_read_text(root / rel_path) for rel_path in doc_paths if (root / rel_path).exists())
    lower = combined.lower()
    requirements = {
        "No-go": "no-go" in lower,
        "real payment disabled": "real payment" in lower and ("disabled" in lower or "does not connect" in lower),
        "not investment advice": "not investment advice" in lower or "不构成投资建议" in combined,
        "do not commit real API Key": (
            "do not commit real api key" in lower
            or "do not paste real api keys" in lower
            or "不得提交真实 api key" in lower
            or "real api keys committed" in lower
        ),
    }
    missing_phrases = sorted(label for label, present in requirements.items() if not present)
    if missing_docs or missing_phrases:
        return _result(
            "docs_keep_no_go_safety_copy",
            "Docs keep launch blockers and product safety copy",
            started,
            status="failed",
            error="release-candidate docs are missing required safety copy",
            metadata={"missing_docs": missing_docs, "missing_phrases": missing_phrases},
        )
    return _result(
        "docs_keep_no_go_safety_copy",
        "Docs keep launch blockers and product safety copy",
        started,
        metadata={"checked_docs": list(doc_paths), "requirements": sorted(requirements)},
    )


def _run_dirty_inventory_check(entries: Sequence[DirtyEntry]) -> PackageResult:
    started = time.monotonic()
    slice_counts: dict[str, int] = {slice_id: 0 for slice_id in SLICE_IDS}
    unclassified: list[str] = []
    for entry in entries:
        slice_id = classify_dirty_path(entry.path)
        if slice_id is None:
            unclassified.append(entry.path)
            continue
        slice_counts[slice_id] += 1
    if unclassified:
        return _result(
            "dirty_inventory_classified",
            "Dirty inventory is classified into review slices",
            started,
            status="failed",
            error="dirty files are not classified",
            metadata={
                "total_dirty": len(entries),
                "slice_counts": slice_counts,
                "unclassified_files": sorted(unclassified),
            },
        )
    return _result(
        "dirty_inventory_classified",
        "Dirty inventory is classified into review slices",
        started,
        metadata={"total_dirty": len(entries), "slice_counts": slice_counts},
    )


def _run_manifest_coverage_check(root: Path, entries: Sequence[DirtyEntry]) -> PackageResult:
    started = time.monotonic()
    doc_paths = [REVIEW_SLICES_DOC, RELEASE_MANIFEST_DOC]
    missing_docs = [rel_path for rel_path in doc_paths if not (root / rel_path).exists()]
    if missing_docs:
        return _result(
            "manifest_covers_dirty_files",
            "Review slices and manifest cover current dirty files",
            started,
            status="failed",
            error="review slices or release manifest document is missing",
            metadata={"missing_docs": missing_docs},
        )
    review_text = _read_text(root / REVIEW_SLICES_DOC)
    manifest_text = _read_text(root / RELEASE_MANIFEST_DOC)
    combined = review_text + "\n" + manifest_text
    missing_files = sorted(entry.path for entry in entries if entry.path not in combined)
    missing_slice_ids = sorted(slice_id for slice_id in SLICE_IDS if slice_id not in combined)
    if missing_files or missing_slice_ids:
        return _result(
            "manifest_covers_dirty_files",
            "Review slices and manifest cover current dirty files",
            started,
            status="failed",
            error="dirty files or required slice ids are missing from docs",
            metadata={"missing_files": missing_files, "missing_slice_ids": missing_slice_ids},
        )
    return _result(
        "manifest_covers_dirty_files",
        "Review slices and manifest cover current dirty files",
        started,
        metadata={"covered_files": len(entries), "slice_ids": sorted(SLICE_IDS)},
    )


def run_release_candidate_checks(*, project_root: str | Path | None = None) -> list[PackageResult]:
    root = Path(project_root).resolve() if project_root is not None else REPO_ROOT
    entries = _git_status_entries(root)
    return [
        _run_required_files_check(root),
        _run_dirty_inventory_check(entries),
        _run_verifiers_visible_check(root),
        _run_docs_safety_copy_check(root),
        _run_prod_env_check(root),
        _run_manifest_coverage_check(root, entries),
    ]


def _print_text_report(results: Sequence[PackageResult]) -> None:
    for result in results:
        marker = "[OK]" if result.status == "passed" else "[FAIL]"
        print(f"{marker} {result.check_id}: {result.title}")
        if result.error:
            print(f"  error: {result.error}")
        if result.metadata:
            print(f"  metadata: {json.dumps(result.metadata, ensure_ascii=False)}")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify DSA platform release-candidate review package")
    parser.add_argument("--project-root", default=str(REPO_ROOT), help="DSA project root")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON")
    args = parser.parse_args(argv)

    results = run_release_candidate_checks(project_root=args.project_root)
    if args.json:
        print(json.dumps([result.to_dict() for result in results], ensure_ascii=False, indent=2))
    else:
        _print_text_report(results)
    return 0 if all(result.status == "passed" for result in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
