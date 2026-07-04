# DSA Local V9 Market Source Health Plan

Date: 2026-07-02

Scope: local-only functional upgrade for quick/no-AI market queries. This stage adds source health scoring, temporary cooldown after repeated source failures, prewarm cache support, and visible diagnostics for operators and users.

No-go: no public deployment, no real payment, no production secrets, no production API keys, no legal/privacy finalization, and no investment advice. Do not commit real API Key.

## Goals

1. Keep quick/no-AI queries cheap and fast by avoiding repeated calls to unhealthy public market sources.
2. Add a deterministic source-health registry for quote and history source status.
3. Add a local prewarm path for common symbols across A-share, US, HK, and crypto routes.
4. Preserve V8 timeout/fallback behavior and `ai_used=false`.
5. Surface source-health diagnostics without exposing secrets or raw exception details.

## Functional Contract

- A source starts as `ok`.
- Repeated timeout or error events move the source to `cooling_down` for a bounded local cooldown window.
- While cooling down, quick/no-AI queries skip the live source call and return a degraded snapshot with sanitized diagnostics.
- A later successful source call resets the source back to `ok`.
- Cache hits are still allowed during cooldown and must be labeled as cache or stale cache fallback.
- Prewarm fetches snapshots for a local symbol list and stores any successful quote/history payloads in the existing market data cache.
- Prewarm must not call AI, consume AI quota, use payment flows, or require production credentials.

## Expected New Evidence

- `tests/test_platform_local_market_source_health_v9.py`
- `scripts/verify_platform_local_market_source_health_v9.py`
- `DSA_PLATFORM_LOCAL_MARKET_SOURCE_HEALTH_V9_OK`

## Verification

```powershell
& "C:\Users\26879\Documents\Codex\2026-06-05\https-x-com-wy-mask-status\work\dsa-venv\Scripts\python.exe" -m unittest tests.test_platform_local_market_source_health_v9
& "C:\Users\26879\Documents\Codex\2026-06-05\https-x-com-wy-mask-status\work\dsa-venv\Scripts\python.exe" scripts\verify_platform_local_market_source_health_v9.py
& "C:\Users\26879\Documents\Codex\2026-06-05\https-x-com-wy-mask-status\work\dsa-venv\Scripts\python.exe" scripts\verify_platform_release_candidate_package.py
```

## Completion Boundary

This stage is complete only when the V9 unit tests, V9 verifier, release-candidate package verifier, targeted backend/frontend tests, frontend build, smoke gate, local health check, and `git diff --check` pass. Optional live market data may degrade when public sources are slow, but it must not be treated as a successful full-data response unless diagnostics say so.
