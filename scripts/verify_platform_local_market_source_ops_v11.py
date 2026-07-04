from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
import urllib.request
from dataclasses import dataclass, field
from http.cookiejar import CookieJar
from pathlib import Path
from typing import Any, Sequence


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.verify_platform_local_functional_v5 import (  # noqa: E402
    DEFAULT_BASE_URL,
    _get_json,
    _json_request,
    _new_smoke_credentials,
    _open_json,
    _url_join,
)
from scripts.verify_platform_local_persistent_market_cache_v10 import run_local_persistent_market_cache_v10_checks  # noqa: E402


OK_MARKER = "DSA_PLATFORM_LOCAL_MARKET_SOURCE_OPS_V11_OK"

REQUIRED_FILES = (
    "docs/superpowers/plans/2026-07-02-dsa-local-v11-market-source-ops.md",
    "scripts/verify_platform_local_market_source_ops_v11.py",
    "src/services/market_source_ops.py",
    "tests/test_platform_local_market_source_ops_v11.py",
)

VERIFIER_FILES = (
    "scripts/verify_platform_local_market_source_ops_v11.py",
)


@dataclass(frozen=True)
class MarketSourceOpsV11Result:
    check_id: str
    title: str
    status: str
    elapsed_sec: float = 0.0
    error: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    optional: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "check_id": self.check_id,
            "title": self.title,
            "status": self.status,
            "elapsed_sec": round(self.elapsed_sec, 3),
            "error": self.error,
            "metadata": self.metadata,
            "optional": self.optional,
        }


def _result(
    check_id: str,
    title: str,
    started: float,
    *,
    status: str = "passed",
    error: str = "",
    metadata: dict[str, Any] | None = None,
    optional: bool = False,
) -> MarketSourceOpsV11Result:
    return MarketSourceOpsV11Result(
        check_id=check_id,
        title=title,
        status=status,
        elapsed_sec=time.monotonic() - started,
        error=error,
        metadata=metadata or {},
        optional=optional,
    )


def _is_git_worktree(root: Path) -> bool:
    completed = subprocess.run(
        ["git", "rev-parse", "--is-inside-work-tree"],
        cwd=root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    return completed.returncode == 0 and completed.stdout.strip() == "true"


def _run_required_files_check(root: Path) -> MarketSourceOpsV11Result:
    started = time.monotonic()
    missing = sorted(rel_path for rel_path in REQUIRED_FILES if not (root / rel_path).exists())
    if missing:
        return _result(
            "v11_required_files_present",
            "Local Market Source Ops V11 required files exist",
            started,
            status="failed",
            error="required files are missing",
            metadata={"missing_files": missing},
        )
    return _result(
        "v11_required_files_present",
        "Local Market Source Ops V11 required files exist",
        started,
        metadata={"checked_files": sorted(REQUIRED_FILES)},
    )


def _run_verifiers_visible_check(root: Path) -> MarketSourceOpsV11Result:
    started = time.monotonic()
    if not _is_git_worktree(root):
        return _result(
            "v11_verifiers_visible_to_git",
            "V11 verifier files are not gitignored",
            started,
            metadata={"checked_files": [], "git_worktree": False},
        )
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
            "v11_verifiers_visible_to_git",
            "V11 verifier files are not gitignored",
            started,
            status="failed",
            error="verifier files are hidden by gitignore",
            metadata={"ignored_files": ignored},
        )
    return _result(
        "v11_verifiers_visible_to_git",
        "V11 verifier files are not gitignored",
        started,
        metadata={"checked_files": sorted(VERIFIER_FILES), "git_worktree": True},
    )


def _run_v11_unittest_check(root: Path, python_exe: str) -> MarketSourceOpsV11Result:
    started = time.monotonic()
    completed = subprocess.run(
        [python_exe, "-m", "unittest", "tests.test_platform_local_market_source_ops_v11"],
        cwd=root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    metadata = {
        "returncode": completed.returncode,
        "stdout_tail": completed.stdout[-1200:],
        "stderr_tail": completed.stderr[-1200:],
    }
    if completed.returncode != 0:
        return _result(
            "v11_backend_unittest",
            "V11 market-source ops tests pass",
            started,
            status="failed",
            error="tests.test_platform_local_market_source_ops_v11 failed",
            metadata=metadata,
        )
    return _result(
        "v11_backend_unittest",
        "V11 market-source ops tests pass",
        started,
        metadata=metadata,
    )


def _run_v10_required_gate(
    *,
    root: Path,
    python_exe: str,
    base_url: str,
    run_subprocess: bool,
    run_live: bool,
) -> MarketSourceOpsV11Result:
    started = time.monotonic()
    results = run_local_persistent_market_cache_v10_checks(
        project_root=root,
        python_exe=python_exe,
        base_url=base_url,
        run_subprocess=run_subprocess,
        run_live=run_live,
    )
    failed = [
        getattr(result, "check_id", "unknown")
        for result in results
        if getattr(result, "status", "failed") == "failed"
    ]
    metadata = {
        "checked_results": len(results),
        "failed_checks": failed,
        "degraded_checks": [
            getattr(result, "check_id", "unknown")
            for result in results
            if getattr(result, "status", "") == "degraded"
        ],
    }
    if failed:
        return _result(
            "v10_persistent_cache_gate",
            "V10 persistent-cache gate remains compatible with V11",
            started,
            status="failed",
            error="V10 verifier has failed checks",
            metadata=metadata,
        )
    return _result(
        "v10_persistent_cache_gate",
        "V10 persistent-cache gate remains compatible with V11",
        started,
        metadata=metadata,
    )


def evaluate_market_source_ops_payload(payload: dict[str, Any]) -> list[str]:
    problems: list[str] = []
    if payload.get("ai_used") is not False:
        problems.append("ai_used_not_false")
    if payload.get("mode") != "local_only":
        problems.append("mode_not_local_only")
    cache = payload.get("cache")
    if not isinstance(cache, dict) or cache.get("mode") not in {"local_json", "memory"}:
        problems.append("cache_mode_missing")
    lanes = payload.get("lanes")
    if not isinstance(lanes, list) or len(lanes) < 4:
        problems.append("lanes_missing")
        return problems
    expected_markets = {"cn", "us", "hk", "crypto"}
    seen_markets = {str(lane.get("market")) for lane in lanes if isinstance(lane, dict)}
    if not expected_markets.issubset(seen_markets):
        problems.append("market_lanes_incomplete")
    valid_statuses = {"ok", "slow", "cooling_down"}
    for lane in lanes:
        if not isinstance(lane, dict):
            problems.append("lane_not_object")
            continue
        for key in ("quote_sources", "history_sources"):
            sources = lane.get(key)
            if not isinstance(sources, list) or not sources:
                problems.append(f"{lane.get('market', 'unknown')}_{key}_missing")
                continue
            first = sources[0]
            if not isinstance(first, dict) or first.get("priority_rank") != 1 or not first.get("source"):
                problems.append(f"{lane.get('market', 'unknown')}_{key}_priority_missing")
            for source in sources:
                if isinstance(source, dict) and source.get("status") not in valid_statuses:
                    problems.append(f"{lane.get('market', 'unknown')}_{key}_bad_status")
    return problems


def _run_optional_live_source_ops_check(base_url: str) -> MarketSourceOpsV11Result:
    started = time.monotonic()
    email, password = _new_smoke_credentials("local-v11-source-ops")
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(CookieJar()))
    metadata: dict[str, Any] = {"smoke_email": email, "cleanup_prefix": "e2e+"}
    try:
        register_status, _ = _open_json(
            opener,
            _json_request(_url_join(base_url, "/api/v1/platform/register"), {"email": email, "password": password}),
            timeout=15,
        )
        metadata["register_status_code"] = register_status
        if register_status >= 400:
            return _result(
                "optional_live_market_source_ops",
                "Optional live V11 market-source ops smoke",
                started,
                status="degraded",
                error="platform smoke user registration failed",
                metadata=metadata,
                optional=True,
            )
        status_code, payload = _get_json(opener, _url_join(base_url, "/api/v1/stocks/sources/health"), timeout=12)
        metadata["status_code"] = status_code
        metadata["payload"] = payload
    except Exception as exc:
        return _result(
            "optional_live_market_source_ops",
            "Optional live V11 market-source ops smoke",
            started,
            status="degraded",
            error=str(exc),
            metadata=metadata,
            optional=True,
        )

    problems = evaluate_market_source_ops_payload(payload if isinstance(payload, dict) else {})
    if status_code != 200 or problems:
        return _result(
            "optional_live_market_source_ops",
            "Optional live V11 market-source ops smoke",
            started,
            status="degraded",
            error="live source ops payload is incomplete",
            metadata={**metadata, "problems": problems},
            optional=True,
        )
    return _result(
        "optional_live_market_source_ops",
        "Optional live V11 market-source ops smoke",
        started,
        metadata=metadata,
        optional=True,
    )


def run_local_market_source_ops_v11_checks(
    *,
    project_root: str | Path | None = None,
    python_exe: str | None = None,
    base_url: str = DEFAULT_BASE_URL,
    run_subprocess: bool = True,
    run_live: bool = True,
) -> list[MarketSourceOpsV11Result]:
    root = Path(project_root).resolve() if project_root is not None else REPO_ROOT
    py = python_exe or sys.executable
    results = [
        _run_required_files_check(root),
        _run_verifiers_visible_check(root),
    ]
    if run_subprocess:
        results.append(_run_v11_unittest_check(root, py))
        results.append(
            _run_v10_required_gate(
                root=root,
                python_exe=py,
                base_url=base_url,
                run_subprocess=False,
                run_live=run_live,
            )
        )
    if run_live:
        results.append(_run_optional_live_source_ops_check(base_url))
    return results


def _passed_for_marker(results: Sequence[MarketSourceOpsV11Result]) -> bool:
    return all(result.status != "failed" for result in results)


def _print_text_report(results: Sequence[MarketSourceOpsV11Result]) -> None:
    for result in results:
        if result.status == "passed":
            marker = "[OK]"
        elif result.status in {"degraded", "skipped", "planned"}:
            marker = "[--]"
        else:
            marker = "[FAIL]"
        print(f"{marker} {result.check_id}: {result.title}")
        if result.error:
            print(f"  error: {result.error}")
        if result.metadata:
            print(f"  metadata: {json.dumps(result.metadata, ensure_ascii=False)}")
    if _passed_for_marker(results):
        print(OK_MARKER)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify DSA platform Local Market Source Ops V11 closure")
    parser.add_argument("--project-root", default=str(REPO_ROOT), help="DSA project root")
    parser.add_argument("--python", dest="python_exe", default=sys.executable, help="Python executable for subprocess checks")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help="Local running WebUI base URL")
    parser.add_argument("--skip-subprocess", action="store_true", help="Skip V11 unittest and V10 verifier subprocess checks")
    parser.add_argument("--skip-live", action="store_true", help="Skip live 8018 HTTP checks")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON")
    args = parser.parse_args(argv)

    results = run_local_market_source_ops_v11_checks(
        project_root=args.project_root,
        python_exe=args.python_exe,
        base_url=args.base_url,
        run_subprocess=not args.skip_subprocess,
        run_live=not args.skip_live,
    )
    if args.json:
        print(json.dumps([result.to_dict() for result in results], ensure_ascii=False, indent=2))
        if _passed_for_marker(results):
            print(OK_MARKER)
    else:
        _print_text_report(results)
    return 0 if _passed_for_marker(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
