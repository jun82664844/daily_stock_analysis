# DSA Local V6 Usability Implementation Plan

> **For agentic workers:** Use `executing-plans` or an available multi-agent workflow to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a local-only V6 usability gate that proves the running 8018 service is loaded with the current platform account and billing routes, while preserving V5 query-quality and safety boundaries.

**Architecture:** V6 builds on V5 instead of replacing it. The new verifier treats stale live routes such as `/api/v1/platform/account` returning 404 after login as a hard failure, while keeping optional market-data instability as a degraded diagnostic.

**Tech Stack:** Python unittest, FastAPI live HTTP smoke via `urllib`, existing V5/V4/user/billing/release verifiers, React/Vite target checks, local SQLite only.

---

### Task 1: Add V6 Verifier Contract

**Files:**
- Create: `tests/test_platform_local_usability_v6.py`
- Create: `scripts/verify_platform_local_usability_v6.py`
- Modify: `.gitignore`

- [ ] **Step 1: Write the failing tests**

Create tests that expect:
- `scripts/verify_platform_local_usability_v6.py` exists.
- `DSA_PLATFORM_LOCAL_USABILITY_V6_OK` appears only when required checks pass.
- V5 `live_platform_smoke` with `status="degraded"` fails V6.
- Optional market snapshot degradation does not fail V6.
- V6 verifier is not hidden by `.gitignore`.

- [ ] **Step 2: Run test to verify RED**

Run:

```powershell
& "C:\Users\26879\Documents\Codex\2026-06-05\https-x-com-wy-mask-status\work\dsa-venv\Scripts\python.exe" -m unittest tests.test_platform_local_usability_v6
```

Expected before implementation: FAIL because the V6 verifier module/file is missing.

- [ ] **Step 3: Implement minimal V6 verifier**

The verifier should:
- Reuse existing V5/V4/user/billing/release gates.
- Add hard gate rules for live health, page shell, platform account, admin boundary, and billing account.
- Allow optional live snapshot degradation as diagnostic only.
- Print `DSA_PLATFORM_LOCAL_USABILITY_V6_OK` only when required checks pass.

- [ ] **Step 4: Run test to verify GREEN**

Run the same unittest command and require OK.

### Task 2: Wire V6 Into Release Package Checks

**Files:**
- Modify: `scripts/verify_platform_release_candidate_package.py`
- Modify: `tests/test_platform_release_candidate_package.py`
- Modify: `docs/superpowers/platform-release-candidate-manifest.md`
- Modify: `docs/superpowers/platform-review-slices.md`
- Modify: `docs/superpowers/platform-local-v1-acceptance-status.md`

- [ ] **Step 1: Write/update package tests first**

Update release package tests so a minimal package must include:
- `scripts/verify_platform_local_usability_v6.py`
- `tests/test_platform_local_usability_v6.py`
- `docs/superpowers/plans/2026-07-02-dsa-local-v6-usability.md`

- [ ] **Step 2: Run package test to verify RED**

Run:

```powershell
& "C:\Users\26879\Documents\Codex\2026-06-05\https-x-com-wy-mask-status\work\dsa-venv\Scripts\python.exe" -m unittest tests.test_platform_release_candidate_package
```

Expected before implementation: FAIL if release verifier does not require or classify V6 files.

- [ ] **Step 3: Implement release verifier updates**

Add V6 script/test/plan to required files and verifier visibility checks. Update docs to keep no-go, sandbox, not real payment, not investment advice, and no real API key boundaries.

- [ ] **Step 4: Run package test to verify GREEN**

Run the same package unittest and require OK.

### Task 3: Full Local Verification

**Files:**
- No new functional files unless tests reveal a real local-only defect.

- [ ] **Step 1: Run focused backend checks**

```powershell
& "C:\Users\26879\Documents\Codex\2026-06-05\https-x-com-wy-mask-status\work\dsa-venv\Scripts\python.exe" -m unittest tests.test_platform_local_usability_v6 tests.test_platform_local_functional_v5 tests.test_platform_query_quality_v4 tests.test_platform_user_journey tests.test_billing_sandbox_flow tests.test_billing_subscription_lifecycle tests.test_platform_release_candidate_package
```

- [ ] **Step 2: Run verifier stack**

```powershell
& "C:\Users\26879\Documents\Codex\2026-06-05\https-x-com-wy-mask-status\work\dsa-venv\Scripts\python.exe" scripts\verify_platform_local_functional_v5.py
& "C:\Users\26879\Documents\Codex\2026-06-05\https-x-com-wy-mask-status\work\dsa-venv\Scripts\python.exe" scripts\verify_platform_local_usability_v6.py
& "C:\Users\26879\Documents\Codex\2026-06-05\https-x-com-wy-mask-status\work\dsa-venv\Scripts\python.exe" scripts\verify_platform_release_candidate_package.py
```

- [ ] **Step 3: Run frontend checks**

```powershell
cd apps\dsa-web
npm test -- --run src/api/__tests__/platform.test.ts src/pages/__tests__/HomePage.test.tsx src/pages/__tests__/AccountPage.test.tsx src/pages/__tests__/AdminPage.test.tsx src/components/layout/__tests__/SidebarNav.test.tsx
npm run build
npm run test:smoke
cd ..\..
```

- [ ] **Step 4: Final hygiene**

```powershell
git diff --check
git status --short --untracked-files=all
```

Completion requires V6 OK marker, no live account 404, no unclassified dirty files, no secret leak, no real payment, and no launch claims.
