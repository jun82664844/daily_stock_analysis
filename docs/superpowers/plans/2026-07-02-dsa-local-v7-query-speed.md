# DSA Local V7 Query Speed Implementation Plan

> **For agentic workers:** Use `executing-plans` or an available multi-agent workflow to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a local-only V7 gate for quick/no-AI market queries that exposes timing, source, freshness, cache, and degradation diagnostics for A-share, US, HK, and crypto snapshots.

**Architecture:** V7 builds on V6/V5. It does not change pricing, production deployment, real payment, legal copy, or real API key handling. The quick lane must remain deterministic and must not call an AI model.

**Tech Stack:** Python unittest, FastAPI/Pydantic response schema, local in-memory market data cache, React/Vite type mapping, existing V4/V5/V6 verifier stack.

---

### Task 1: Add V7 Query Diagnostics Contract

**Files:**
- Create: `tests/test_platform_local_query_speed_v7.py`
- Modify: `src/services/basic_query_service.py`
- Modify: `api/v1/schemas/basic_query.py`
- Modify: `apps/dsa-web/src/api/stocks.ts`
- Modify: `apps/dsa-web/src/api/__tests__/stocks.test.ts`

- [ ] **Step 1: Write the failing tests**

Create tests that expect quick snapshots to include:
- `diagnostics.elapsed_ms`, `quote_elapsed_ms`, and `history_elapsed_ms`.
- cache state for quote/history as `hit`, `miss`, or `unavailable`.
- source and freshness details for quote/history.
- performance status that can flag slow local lookups without calling AI.
- `ai_used=false` for every quick/no-AI snapshot.

- [ ] **Step 2: Run test to verify RED**

Run:

```powershell
& "C:\Users\26879\Documents\Codex\2026-06-05\https-x-com-wy-mask-status\work\dsa-venv\Scripts\python.exe" -m unittest tests.test_platform_local_query_speed_v7
```

Expected before implementation: FAIL because the V7 diagnostics contract is missing.

- [ ] **Step 3: Implement minimal diagnostics**

Add timing and cache diagnostics in `BasicQueryService.get_snapshot` without changing the no-AI behavior. Keep diagnostics safe for the UI: no secrets, no API keys, no raw headers, and no external credential material.

- [ ] **Step 4: Run test to verify GREEN**

Run the same unittest command and require OK.

### Task 2: Add V7 Local Verifier

**Files:**
- Create: `scripts/verify_platform_local_query_speed_v7.py`
- Modify: `.gitignore`

- [ ] **Step 1: Write verifier tests first**

The verifier should require:
- V7 plan/test/script files are present and visible to git.
- Existing V6/V5/V4 gates remain available.
- Multi-market quick snapshots keep the expected market lanes and `ai_used=false`.
- Live snapshot diagnostics are checked when the local 8018 service is available.

- [ ] **Step 2: Implement verifier**

Print `DSA_PLATFORM_LOCAL_QUERY_SPEED_V7_OK` only when required checks pass. Treat live market source timeouts or stale data as diagnostic degradation unless they prove the quick lane is using the wrong route or AI.

### Task 3: Wire V7 Into Release Package Checks

**Files:**
- Modify: `scripts/verify_platform_release_candidate_package.py`
- Modify: `tests/test_platform_release_candidate_package.py`
- Modify: `docs/superpowers/platform-release-candidate-manifest.md`
- Modify: `docs/superpowers/platform-review-slices.md`
- Modify: `docs/superpowers/platform-local-v1-acceptance-status.md`

- [ ] **Step 1: Update package tests**

Require the V7 script, V7 test, and V7 plan in the local release-candidate package.

- [ ] **Step 2: Update docs**

Keep all local-only boundaries explicit: No-go for production, sandbox only for billing, no real payment, do not commit real API keys, and analysis is not investment advice.

### Task 4: Full Local Verification

- [ ] **Step 1: Run focused backend checks**

```powershell
& "C:\Users\26879\Documents\Codex\2026-06-05\https-x-com-wy-mask-status\work\dsa-venv\Scripts\python.exe" -m unittest tests.test_platform_local_query_speed_v7 tests.test_platform_local_usability_v6 tests.test_platform_local_functional_v5 tests.test_platform_query_quality_v4 tests.test_platform_release_candidate_package
```

- [ ] **Step 2: Run verifier stack**

```powershell
& "C:\Users\26879\Documents\Codex\2026-06-05\https-x-com-wy-mask-status\work\dsa-venv\Scripts\python.exe" scripts\verify_platform_local_query_speed_v7.py
& "C:\Users\26879\Documents\Codex\2026-06-05\https-x-com-wy-mask-status\work\dsa-venv\Scripts\python.exe" scripts\verify_platform_release_candidate_package.py
```

- [ ] **Step 3: Run frontend checks**

```powershell
cd apps\dsa-web
npm test -- --run src/api/__tests__/stocks.test.ts src/pages/__tests__/HomePage.test.tsx src/pages/__tests__/AccountPage.test.tsx src/pages/__tests__/AdminPage.test.tsx src/components/layout/__tests__/SidebarNav.test.tsx
npm run build
npm run test:smoke
cd ..\..
```

- [ ] **Step 4: Final hygiene**

```powershell
git diff --check
git status --short --untracked-files=all
```

Completion requires the V7 OK marker, no unclassified dirty files, no secret exposure, no AI use in quick/no-AI mode, and no launch claims.
