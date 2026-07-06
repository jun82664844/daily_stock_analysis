# DSA V54 Local User Acceptance Implementation Plan

> **For agentic workers:** Use `executing-plans` or an available multi-agent workflow to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the local DSA free user journey feel usable before production work: anonymous users can query supported markets, the no-AI free report is rich enough to retain users, and Codex verifies the browser before handing it to the user.

**Architecture:** Keep this stage local-first and no-AI by default. Use the existing `GET /api/v1/stocks/{code}/snapshot` lane for free queries, display deterministic quote/profile/technical/intelligence fields in `HomePage`, and reserve AI/API-key consumption for explicit quick/deep analysis buttons.

**Tech Stack:** FastAPI, Pydantic, Python unittest, React, TypeScript, Vitest, Playwright, Vite.

---

### Task 1: Baseline And Plan Boundary

**Files:**
- Create: `docs/superpowers/plans/2026-07-06-dsa-v54-local-user-acceptance.md`
- Inspect: `api/v1/schemas/basic_query.py`
- Inspect: `src/services/basic_query_service.py`
- Inspect: `apps/dsa-web/src/pages/HomePage.tsx`
- Inspect: `apps/dsa-web/src/pages/__tests__/HomePage.test.tsx`

- [ ] **Step 1: Confirm clean tree before work**

```powershell
git status -sb --untracked-files=all
```

Expected: only branch line before V54 edits.

- [ ] **Step 2: Confirm no-AI snapshot schema has rich fields**

Check that `BasicStockSnapshot` includes `profile`, `trend`, `intelligence`, `route`, `warnings`, `degradation`, `diagnostics`, and `ai_used`.

- [ ] **Step 3: Confirm frontend has product sections**

Check `HomePage.tsx` for these `data-testid` anchors:

```text
basic-query-primary-summary
basic-query-free-report
basic-query-mini-chart
basic-query-signal-score
basic-query-intelligence-panel
basic-query-market-brief
basic-query-free-insights
basic-query-peer-comparison
basic-query-watch-points
basic-query-product-brief
basic-query-user-guardrails
```

Expected: all anchors exist, otherwise add tests first in Task 3.

### Task 2: Targeted Automated Verification

**Files:**
- Test: `tests/test_basic_query_no_ai.py`
- Test: `tests/test_platform_query_quality_v4.py`
- Test: `apps/dsa-web/src/pages/__tests__/HomePage.test.tsx`
- Test: `apps/dsa-web/src/api/__tests__/stocks.test.ts`

- [ ] **Step 1: Run backend no-AI and route tests**

```powershell
& "C:\Users\26879\Documents\Codex\2026-06-05\https-x-com-wy-mask-status\work\dsa-venv\Scripts\python.exe" -m unittest tests.test_basic_query_no_ai tests.test_platform_query_quality_v4
```

Expected: tests pass and confirm no AI is called for snapshot queries.

- [ ] **Step 2: Run frontend no-AI report tests**

```powershell
npm run test -- src/pages/__tests__/HomePage.test.tsx src/api/__tests__/stocks.test.ts
```

Run from `apps/dsa-web`.

Expected: tests pass and confirm the rich free report renders.

### Task 3: Patch Only Verified Gaps

**Files:**
- Modify if needed: `src/services/basic_query_service.py`
- Modify if needed: `api/v1/schemas/basic_query.py`
- Modify if needed: `apps/dsa-web/src/api/stocks.ts`
- Modify if needed: `apps/dsa-web/src/pages/HomePage.tsx`
- Add if needed: `tests/test_platform_local_user_acceptance_v54.py`
- Add if needed: `apps/dsa-web/src/pages/__tests__/HomePage.test.tsx`

- [ ] **Step 1: If anonymous snapshot is blocked, write the failing backend test**

Add or confirm a test equivalent to:

```python
def test_snapshot_is_public_without_platform_login(self) -> None:
    response = anonymous_client.get("/api/v1/stocks/AAPL/snapshot")
    self.assertEqual(response.status_code, 200)
    self.assertFalse(response.json()["ai_used"])
```

Expected RED if the endpoint requires login; expected existing GREEN if already implemented.

- [ ] **Step 2: If free report is too thin, write the failing frontend test**

Assert that the AAPL free report contains:

```text
Signal score
Information digest
Market lane
Peer and market comparison
Next observation
Company profile
No AI
not investment advice
```

Expected RED only if a missing product section is found.

- [ ] **Step 3: Implement minimal fixes**

Keep fixes deterministic and low-cost:

```text
Do not call AI.
Do not call public search.
Do not require login for snapshot.
Do not consume platform/BYOK/local AI quota for basic snapshot.
Do not delete user reports, database, cache, or history.
```

- [ ] **Step 4: Re-run only the failed test group**

Expected: failed group turns GREEN.

### Task 4: Browser-Level Local Acceptance

**Files:**
- Add if useful: `scripts/verify_platform_local_user_acceptance_v54.py`
- Add if useful: `apps/dsa-web/e2e/platform-local-user-acceptance-v54.spec.ts`

- [ ] **Step 1: Verify live backend and page shell**

```powershell
Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8018/health
Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8018/
```

Expected: `200 OK`.

- [ ] **Step 2: Verify anonymous no-AI APIs**

```powershell
Invoke-RestMethod http://127.0.0.1:8018/api/v1/stocks/AAPL/snapshot
Invoke-RestMethod http://127.0.0.1:8018/api/v1/stocks/600519/snapshot
Invoke-RestMethod http://127.0.0.1:8018/api/v1/stocks/00700.HK/snapshot
Invoke-RestMethod http://127.0.0.1:8018/api/v1/stocks/BTC-USD/snapshot
```

Expected: response contains `ai_used=false`, a route lane, quote payload, and no login error.

- [ ] **Step 3: Run browser flow**

Use Playwright or equivalent browser automation to open `http://127.0.0.1:8018/?dsa_ui_reset=1`, type `AAPL`, click query, and verify these visible sections:

```text
basic-query-snapshot
basic-query-free-report
basic-query-signal-score
basic-query-quote-details
basic-query-technical-details
```

Expected: no page-load failure, no blank result, no login requirement for query.

### Task 5: Final Gates And Clean Commit

**Files:**
- Update if created: `scripts/verify_platform_release_candidate_package.py`
- Update if created: `docs/superpowers/platform-release-candidate-manifest.md`
- Update if created: `docs/superpowers/platform-review-slices.md`
- Update if created: `docs/superpowers/platform-local-v1-acceptance-status.md`

- [ ] **Step 1: Run build and local verifier stack**

```powershell
npm run build
& "C:\Users\26879\Documents\Codex\2026-06-05\https-x-com-wy-mask-status\work\dsa-venv\Scripts\python.exe" scripts\verify_local_v1_operability.py
git diff --check
```

Run `npm run build` from `apps/dsa-web`; run the Python verifier and Git checks from the repo root.

Expected: all pass.

- [ ] **Step 2: Commit explicit V54 files**

Use explicit file paths only, not `git add -A`.

```powershell
git status -sb --untracked-files=all
git add -- <explicit V54 files>
git diff --cached --check
git commit -m "test: verify local free user acceptance"
```

Expected: commit succeeds.

- [ ] **Step 3: Confirm clean tree**

```powershell
git status -sb --untracked-files=all
```

Expected: only branch line.
