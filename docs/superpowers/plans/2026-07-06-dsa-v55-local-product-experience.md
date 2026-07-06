# DSA V55 Local Product Experience Implementation Plan

> **For agentic workers:** Use `executing-plans` or an available multi-agent workflow to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the local DSA Web UI feel useful for first-time visitors before login while preserving the local-only, no-real-payment, no-real-key boundary.

**Architecture:** Keep the existing unified HomePage and market-routing backend. Add product-facing guest surfaces in the React UI, add richer deterministic no-AI report payload fields in `BasicQueryService`, and protect the work with unit tests plus a V55 verifier.

**Tech Stack:** FastAPI, Python unittest, React, TypeScript, Vitest, Vite, local browser smoke on `http://127.0.0.1:8018`.

---

### Task 1: Baseline And Scope Guard

**Files:**
- Read: `apps/dsa-web/src/pages/HomePage.tsx`
- Read: `src/services/basic_query_service.py`
- Read: `tests/test_basic_query_no_ai.py`
- Read: `apps/dsa-web/src/pages/__tests__/HomePage.test.tsx`

- [x] **Step 1: Confirm clean tree**

```powershell
git status -sb --untracked-files=all
```

Expected: only the branch line before V55 starts.

- [x] **Step 2: Run targeted baseline tests**

```powershell
& "C:\Users\26879\Documents\Codex\2026-06-05\https-x-com-wy-mask-status\work\dsa-venv\Scripts\python.exe" -m unittest tests.test_basic_query_no_ai tests.test_platform_query_quality_v4
cd apps\dsa-web
npm run test -- src/pages/__tests__/HomePage.test.tsx src/api/__tests__/stocks.test.ts
```

Expected: tests pass before V55 changes.

### Task 2: Guest Homepage First Screen

**Files:**
- Modify: `apps/dsa-web/src/pages/HomePage.tsx`
- Modify: `apps/dsa-web/src/pages/__tests__/HomePage.test.tsx`

- [x] **Step 1: Write failing frontend test**

Add a test asserting that anonymous users see a product-focused guest entry panel with example query buttons and that History Center remains secondary.

Expected markers:
- `data-testid="guest-query-entry"`
- `data-testid="guest-example-AAPL"`
- `data-testid="guest-example-600519"`
- `data-testid="guest-example-00700.HK"`
- `data-testid="guest-example-BTC-USD"`
- text explaining no login is required for quick no-AI checks

- [x] **Step 2: Run test and confirm RED**

```powershell
npm run test -- src/pages/__tests__/HomePage.test.tsx -t "shows a guest-first query entry before login"
```

Expected: FAIL because the guest panel does not exist yet.

- [x] **Step 3: Implement guest-first panel**

Add a compact unframed guest panel near the top of HomePage for unauthenticated users. It should not hide the main search, should not require login, and should keep examples as buttons that fill and run a quick query.

- [x] **Step 4: Run test and confirm GREEN**

```powershell
npm run test -- src/pages/__tests__/HomePage.test.tsx -t "shows a guest-first query entry before login"
```

Expected: PASS.

### Task 3: Free Report Retention Content

**Files:**
- Modify: `src/services/basic_query_service.py`
- Modify: `tests/test_basic_query_no_ai.py`
- Modify: `apps/dsa-web/src/api/stocks.ts`
- Modify: `apps/dsa-web/src/pages/HomePage.tsx`
- Modify: `apps/dsa-web/src/pages/__tests__/HomePage.test.tsx`

- [x] **Step 1: Write failing backend test**

Add a test proving no-AI snapshots include a `retention_brief` object under `intelligence` with:
- `headline`
- `why_it_matters`
- `support_resistance`
- `next_steps`
- `upgrade_hint`
- `boundary`

Expected: no AI service called.

- [x] **Step 2: Run test and confirm RED**

```powershell
& "C:\Users\26879\Documents\Codex\2026-06-05\https-x-com-wy-mask-status\work\dsa-venv\Scripts\python.exe" -m unittest tests.test_basic_query_no_ai.BasicQueryNoAiTestCase.test_no_ai_snapshot_includes_retention_brief
```

Expected: FAIL because `retention_brief` is missing.

- [x] **Step 3: Implement deterministic retention brief**

Build it from quote, indicators, trend, profile and route. Do not invoke AI or public search.

- [x] **Step 4: Render the retention brief**

Add `data-testid="basic-query-retention-brief"` to HomePage under the free report, showing why it matters, support/resistance, next steps, and a soft upgrade hint.

- [x] **Step 5: Run backend and frontend tests**

```powershell
& "C:\Users\26879\Documents\Codex\2026-06-05\https-x-com-wy-mask-status\work\dsa-venv\Scripts\python.exe" -m unittest tests.test_basic_query_no_ai
cd apps\dsa-web
npm run test -- src/pages/__tests__/HomePage.test.tsx src/api/__tests__/stocks.test.ts
```

Expected: PASS.

### Task 4: Login Guidance Without Blocking

**Files:**
- Modify: `apps/dsa-web/src/pages/HomePage.tsx`
- Modify: `apps/dsa-web/src/pages/__tests__/HomePage.test.tsx`

- [x] **Step 1: Write failing frontend test**

Add a test proving anonymous users can query first, then see `data-testid="guest-conversion-guide"` after a snapshot. It should explain that login saves history, watchlist, and quotas without blocking the current query.

- [x] **Step 2: Run test and confirm RED**

```powershell
npm run test -- src/pages/__tests__/HomePage.test.tsx -t "lets guests query first and then shows a non-blocking login guide"
```

Expected: FAIL before the guide is implemented.

- [x] **Step 3: Implement non-blocking guide**

Render the guide only for unauthenticated users after `basicSnapshot` exists. Buttons should switch auth mode but not clear the snapshot.

- [x] **Step 4: Run test and confirm GREEN**

```powershell
npm run test -- src/pages/__tests__/HomePage.test.tsx -t "lets guests query first and then shows a non-blocking login guide"
```

Expected: PASS.

### Task 5: Ordinary User Acceptance Path

**Files:**
- Create: `scripts/verify_platform_local_product_experience_v55.py`
- Create: `tests/test_platform_local_product_experience_v55.py`
- Modify: `.gitignore`
- Modify: `scripts/verify_platform_release_candidate_package.py`
- Modify: `tests/test_platform_release_candidate_package.py`
- Modify: `docs/superpowers/platform-local-v1-acceptance-status.md`
- Modify: `docs/superpowers/platform-review-slices.md`
- Modify: `docs/superpowers/platform-release-candidate-manifest.md`

- [x] **Step 1: Write failing verifier test**

Test that the V55 verifier file exists and checks:
- guest entry marker
- retention brief marker
- guest conversion guide marker
- no-AI backend retention brief marker
- release package visibility

- [x] **Step 2: Run test and confirm RED**

```powershell
& "C:\Users\26879\Documents\Codex\2026-06-05\https-x-com-wy-mask-status\work\dsa-venv\Scripts\python.exe" -m unittest tests.test_platform_local_product_experience_v55
```

Expected: FAIL because verifier is missing.

- [x] **Step 3: Implement verifier**

The verifier prints `DSA_PLATFORM_LOCAL_PRODUCT_EXPERIENCE_V55_OK` on success and supports optional `--live-url http://127.0.0.1:8018` checks.

- [x] **Step 4: Sync release package docs and `.gitignore`**

Add the verifier, test and plan to release package coverage.

- [x] **Step 5: Run V55 verification stack**

```powershell
& "C:\Users\26879\Documents\Codex\2026-06-05\https-x-com-wy-mask-status\work\dsa-venv\Scripts\python.exe" scripts\verify_platform_local_product_experience_v55.py --live-url http://127.0.0.1:8018
& "C:\Users\26879\Documents\Codex\2026-06-05\https-x-com-wy-mask-status\work\dsa-venv\Scripts\python.exe" scripts\verify_platform_release_candidate_package.py
```

Expected: both pass.

### Task 6: Final Gate And Commit

**Files:**
- All V55 files only.

- [x] **Step 1: Run final backend/frontend gates**

```powershell
& "C:\Users\26879\Documents\Codex\2026-06-05\https-x-com-wy-mask-status\work\dsa-venv\Scripts\python.exe" -m unittest tests.test_basic_query_no_ai tests.test_platform_query_quality_v4 tests.test_platform_local_product_experience_v55 tests.test_platform_release_candidate_package
cd apps\dsa-web
npm run test -- src/pages/__tests__/HomePage.test.tsx src/api/__tests__/stocks.test.ts
npm run build
```

Expected: PASS.

- [x] **Step 2: Run local verifier stack**

```powershell
& "C:\Users\26879\Documents\Codex\2026-06-05\https-x-com-wy-mask-status\work\dsa-venv\Scripts\python.exe" scripts\verify_local_v1_operability.py
& "C:\Users\26879\Documents\Codex\2026-06-05\https-x-com-wy-mask-status\work\dsa-venv\Scripts\python.exe" scripts\verify_platform_v2_readiness.py
& "C:\Users\26879\Documents\Codex\2026-06-05\https-x-com-wy-mask-status\work\dsa-venv\Scripts\python.exe" scripts\verify_platform_local_product_experience_v55.py --live-url http://127.0.0.1:8018
git diff --check
```

Expected: PASS.

- [x] **Step 3: Commit explicit V55 files**

```powershell
git add -- <explicit V55 files>
git diff --cached --check
git commit -m "feat: improve local guest product experience"
git status -sb --untracked-files=all
```

Expected: commit succeeds and the tree is clean.
