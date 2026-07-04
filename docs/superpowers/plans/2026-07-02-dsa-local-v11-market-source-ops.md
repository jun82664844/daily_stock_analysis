# DSA Local V11 Market Source Ops Implementation Plan

> **For agentic workers:** Use `executing-plans` or an available multi-agent workflow to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a local-only market source operations view so admins can see quick-query source priority, cooldown state, latency, and cache fallback health across A-share, US, HK, and crypto lanes.

**Architecture:** Keep the existing V8/V9/V10 quick-query stack as the source of truth. Add a read-only backend summary service and API under `/api/v1/stocks/sources/health`, then show the result on the existing Admin page without exposing filesystem paths, API keys, or production controls.

**Tech Stack:** FastAPI, Pydantic, `BasicQueryService`, `MarketSourceHealthRegistry`, React, Vitest, Playwright smoke/verifier scripts.

---

### Task 1: Backend Source Operations Summary

**Files:**
- Create: `src/services/market_source_ops.py`
- Modify: `api/v1/schemas/basic_query.py`
- Modify: `api/v1/endpoints/stocks.py`
- Test: `tests/test_platform_local_market_source_ops_v11.py`

- [ ] **Step 1: Write failing tests**

Add tests that expect:
- `build_market_source_ops_snapshot()` returns four lanes: `cn`, `us`, `hk`, `crypto`.
- Each lane includes ordered quote/history sources, source health, priority rank, cooldown seconds, and cache mode.
- `GET /api/v1/stocks/sources/health` returns no AI usage and does not require a live market call.

- [ ] **Step 2: Run tests and verify RED**

Run:

```powershell
& "C:\Users\26879\Documents\Codex\2026-06-05\https-x-com-wy-mask-status\work\dsa-venv\Scripts\python.exe" -m unittest tests.test_platform_local_market_source_ops_v11
```

Expected: fail because `src.services.market_source_ops` and the endpoint do not exist yet.

- [ ] **Step 3: Implement minimal backend**

Create a service that reads `BasicQueryService().describe_routes()` and `default_market_source_health.snapshot(source)` without invoking live quote/history fetches.

- [ ] **Step 4: Verify backend GREEN**

Run the V11 test and the V9/V10 target tests.

### Task 2: Frontend Admin Diagnostics Panel

**Files:**
- Modify: `apps/dsa-web/src/api/stocks.ts`
- Modify: `apps/dsa-web/src/pages/AdminPage.tsx`
- Modify: `apps/dsa-web/src/i18n/uiText.ts`
- Test: `apps/dsa-web/src/api/__tests__/stocks.test.ts`
- Test: `apps/dsa-web/src/pages/__tests__/AdminPage.test.tsx`

- [ ] **Step 1: Write failing frontend tests**

Add tests that expect:
- `stocksApi.marketSourceHealth()` maps snake_case payloads to camelCase.
- Admin page loads and renders a "Market source health" panel, lane labels, status, fallback/cache mode, and priority rank.

- [ ] **Step 2: Run frontend tests and verify RED**

Run:

```powershell
npm test -- --run src/api/__tests__/stocks.test.ts src/pages/__tests__/AdminPage.test.tsx
```

Expected: fail because the API client method and Admin panel do not exist yet.

- [ ] **Step 3: Implement minimal frontend**

Fetch `stocksApi.marketSourceHealth()` with other admin data, render a compact table, and keep wording local-only/read-only.

- [ ] **Step 4: Verify frontend GREEN**

Run frontend target tests and `npm run build`.

### Task 3: V11 Verifier and Release Package

**Files:**
- Create: `scripts/verify_platform_local_market_source_ops_v11.py`
- Modify: `.gitignore`
- Modify: `scripts/verify_platform_release_candidate_package.py`
- Modify: `tests/test_platform_release_candidate_package.py`
- Modify: `docs/superpowers/platform-local-v1-acceptance-status.md`
- Modify: `docs/superpowers/platform-review-slices.md`
- Modify: `docs/superpowers/platform-release-candidate-manifest.md`

- [ ] **Step 1: Write verifier test coverage**

The verifier must check required files, backend unit tests, V10 compatibility, optional live `/api/v1/stocks/sources/health`, and output `DSA_PLATFORM_LOCAL_MARKET_SOURCE_OPS_V11_OK`.

- [ ] **Step 2: Run release/package checks**

Run V11 verifier, V10 verifier, release package verifier, build, smoke, and `git diff --check`.

### Self-Review Notes

The plan covers local-only backend diagnostics, frontend operator visibility, verifier wiring, and release documentation. It intentionally excludes production data-source credentials, cloud monitoring, paid billing changes, and real deployment work.
