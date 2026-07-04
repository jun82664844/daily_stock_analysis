# DSA Local V8 Query Resilience Implementation Plan

> **For agentic workers:** Use `executing-plans` or an available multi-agent workflow to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make quick/no-AI market snapshots resilient when A-share, HK, or other public market sources are slow by adding bounded local fetch timeouts, stale-cache fallback diagnostics, and a V8 local verifier.

**Architecture:** V8 builds on V7 diagnostics. The quick lane remains deterministic and no-AI; slow quote/history calls are bounded and degraded into visible warnings instead of blocking the local UI. Production launch, real payment, real API keys, and legal/commercial decisions remain out of scope.

**Tech Stack:** Python unittest, FastAPI/Pydantic response schema, local in-memory market data cache, React/Vite type/display updates, existing V4/V5/V6/V7 verifier stack.

---

### Task 1: Add V8 Resilience Contract

**Files:**
- Create: `tests/test_platform_local_query_resilience_v8.py`
- Modify: `src/services/basic_query_service.py`
- Modify: `api/v1/schemas/basic_query.py`

- [ ] **Step 1: Write the failing tests**

Create tests that expect:
- A slow quote fetch returns within the configured local timeout and keeps `ai_used=false`.
- Timeout degradation adds `quote_timeout` or `history_timeout` warnings.
- Diagnostics include `timeouts`, sanitized `errors`, and explicit `fallback` state.
- Stale quote/history cache hits are returned immediately and marked as `stale_cache` fallback.

- [ ] **Step 2: Run test to verify RED**

Run:

```powershell
& "C:\Users\26879\Documents\Codex\2026-06-05\https-x-com-wy-mask-status\work\dsa-venv\Scripts\python.exe" -m unittest tests.test_platform_local_query_resilience_v8
```

Expected before implementation: FAIL because timeout/fallback diagnostics and the V8 verifier are missing.

- [ ] **Step 3: Implement minimal resilience**

Use a bounded background executor for market-data calls. Do not expose raw exceptions, headers, tokens, URLs with keys, or API keys in diagnostics.

- [ ] **Step 4: Run test to verify GREEN**

Run the same unittest command and require OK.

### Task 2: Add Frontend V8 Diagnostics Display

**Files:**
- Modify: `apps/dsa-web/src/api/stocks.ts`
- Modify: `apps/dsa-web/src/pages/HomePage.tsx`
- Modify: `apps/dsa-web/src/pages/__tests__/HomePage.test.tsx`
- Modify: `apps/dsa-web/src/i18n/uiText.ts`

- [ ] **Step 1: Extend frontend types**

Add optional `timeouts`, `errors`, and `fallback` to `BasicStockSnapshot.diagnostics`.

- [ ] **Step 2: Display fallback compactly**

Add a compact row showing quote/history fallback state. Keep it operational and safe, not marketing copy.

- [ ] **Step 3: Run frontend tests**

```powershell
cd apps\dsa-web
npm test -- --run src/api/__tests__/stocks.test.ts src/pages/__tests__/HomePage.test.tsx
cd ..\..
```

### Task 3: Add V8 Verifier And Release Coverage

**Files:**
- Create: `scripts/verify_platform_local_query_resilience_v8.py`
- Modify: `.gitignore`
- Modify: `scripts/verify_platform_release_candidate_package.py`
- Modify: `tests/test_platform_release_candidate_package.py`
- Modify: `docs/superpowers/platform-release-candidate-manifest.md`
- Modify: `docs/superpowers/platform-review-slices.md`
- Modify: `docs/superpowers/platform-local-v1-acceptance-status.md`

- [ ] **Step 1: Write/update package tests first**

Require the V8 script, test, and plan files in the release package.

- [ ] **Step 2: Implement V8 verifier**

Print `DSA_PLATFORM_LOCAL_QUERY_RESILIENCE_V8_OK` only when required checks pass. Optional live multi-market checks should report source timeouts as degradation but should not fake data freshness.

### Task 4: Full Local Verification

- [ ] **Step 1: Run focused backend checks**

```powershell
& "C:\Users\26879\Documents\Codex\2026-06-05\https-x-com-wy-mask-status\work\dsa-venv\Scripts\python.exe" -m unittest tests.test_platform_local_query_resilience_v8 tests.test_platform_local_query_speed_v7 tests.test_platform_local_usability_v6 tests.test_platform_local_functional_v5 tests.test_platform_query_quality_v4 tests.test_platform_release_candidate_package
```

- [ ] **Step 2: Run verifier stack**

```powershell
& "C:\Users\26879\Documents\Codex\2026-06-05\https-x-com-wy-mask-status\work\dsa-venv\Scripts\python.exe" scripts\verify_platform_local_query_resilience_v8.py
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

Completion requires the V8 OK marker, no secret exposure, no AI use in quick/no-AI mode, no unclassified dirty files, and no launch claims.
