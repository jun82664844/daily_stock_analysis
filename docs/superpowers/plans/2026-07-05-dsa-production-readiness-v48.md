# DSA Production Readiness V48 Implementation Plan

> **For agentic workers:** Use `executing-plans` or an available multi-agent workflow to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a local, machine-checkable production readiness preflight that turns the launch checklist into admin-visible GO/NO-GO evidence without enabling real payment, real secrets, public deployment, or investment advice.

**Architecture:** Build a pure backend readiness service that reads configuration and policy flags, produces sanitized category checks, exposes it through an admin-only platform endpoint, renders the result in AdminPage, and verifies the package through a dedicated script plus tests. Real merchant, domain, data license, and legal approvals remain explicit blockers until humans provide approved evidence.

**Tech Stack:** FastAPI, Pydantic response typing by convention, React/Vite, Vitest, Python unittest, PowerShell verifier commands.

---

### Task 1: Backend Production Readiness Status

**Files:**
- Create: `src/services/production_readiness.py`
- Modify: `api/v1/endpoints/platform.py`
- Test: `tests/test_platform_production_readiness_v48.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_platform_production_readiness_v48.py` with tests that import `build_production_readiness_status`, verify `mode=production_preflight`, `ai_used=false`, `launch_decision=blocked`, category coverage for security, auth, billing, deployment, legal, privacy, data sources, observability, and backup, and verify no secret-like env value appears in the JSON.

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
& "C:\Users\26879\Documents\Codex\2026-06-05\https-x-com-wy-mask-status\work\dsa-venv\Scripts\python.exe" -m unittest tests.test_platform_production_readiness_v48
```

Expected: FAIL because `src.services.production_readiness` and `/api/v1/platform/admin/production-readiness` do not exist yet.

- [ ] **Step 3: Implement the service and endpoint**

Implement `build_production_readiness_status()` with deterministic checks:

- `auth`: admin auth, platform auth, CSRF.
- `security`: CORS, debug mode, secret source, public search disabled.
- `billing`: real payment disabled unless provider and webhook approval flags exist.
- `deployment`: domain, HTTPS, WAF, staging approval flags.
- `data_sources`: market data commercial approval flag.
- `legal`: legal/privacy/not-investment-advice approval flags.
- `observability`: monitoring, logs, alerting flags.
- `backup`: backup and restore drill flags.

Return sanitized payload with `blocking_checks`, `manual_actions`, and `launch_decision`.

- [ ] **Step 4: Run test to verify it passes**

Run the same unittest command and expect OK.

### Task 2: Admin UI Production Readiness Panel

**Files:**
- Modify: `apps/dsa-web/src/api/platform.ts`
- Modify: `apps/dsa-web/src/pages/AdminPage.tsx`
- Test: `apps/dsa-web/src/pages/__tests__/AdminPage.test.tsx`

- [ ] **Step 1: Write the failing frontend test**

Extend AdminPage test mocks with `adminProductionReadiness`, expect the page to call it, and assert visible text: `Production readiness`, `BLOCKED`, `security`, `billing`, `legal`, `data_sources`, and `No real payment`.

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
cd apps\dsa-web
npm run test -- src/pages/__tests__/AdminPage.test.tsx -t "renders platform users"
cd ..\..
```

Expected: FAIL because AdminPage does not call or render the production readiness payload.

- [ ] **Step 3: Add API type/client and panel**

Add `PlatformProductionReadinessResponse`, `adminProductionReadiness()`, state loading in `AdminPage`, and a compact admin card showing launch decision, blocking count, category statuses, and manual action count.

- [ ] **Step 4: Run test to verify it passes**

Run the same Vitest command and expect pass.

### Task 3: V48 Verifier And Package Visibility

**Files:**
- Create: `scripts/verify_platform_production_readiness_v48.py`
- Modify: `.gitignore`
- Modify: `scripts/verify_platform_release_candidate_package.py`
- Modify: `tests/test_platform_release_candidate_package.py`
- Modify: `docs/superpowers/platform-v2-launch-readiness.md`
- Modify: `docs/superpowers/platform-release-candidate-manifest.md`

- [ ] **Step 1: Write the failing verifier test**

Extend `tests/test_platform_production_readiness_v48.py` to require `OK_MARKER == "DSA_PLATFORM_PRODUCTION_READINESS_V48_OK"` and import the verifier module.

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
& "C:\Users\26879\Documents\Codex\2026-06-05\https-x-com-wy-mask-status\work\dsa-venv\Scripts\python.exe" -m unittest tests.test_platform_production_readiness_v48
```

Expected: FAIL because the verifier does not exist.

- [ ] **Step 3: Implement verifier and release package wiring**

Create verifier checks for service file, endpoint route, frontend client, AdminPage panel, no-go docs, production env flags, and no real secret patterns. Update `.gitignore` to expose the verifier and release manifest checks to include the new plan/test/script files.

- [ ] **Step 4: Run verifier and package tests**

Run:

```powershell
& "C:\Users\26879\Documents\Codex\2026-06-05\https-x-com-wy-mask-status\work\dsa-venv\Scripts\python.exe" scripts\verify_platform_production_readiness_v48.py
& "C:\Users\26879\Documents\Codex\2026-06-05\https-x-com-wy-mask-status\work\dsa-venv\Scripts\python.exe" scripts\verify_platform_release_candidate_package.py
```

Expected: both pass; V48 verifier prints `DSA_PLATFORM_PRODUCTION_READINESS_V48_OK`.

### Task 4: Final Verification

**Files:** no new files.

- [ ] **Step 1: Run backend tests**

```powershell
& "C:\Users\26879\Documents\Codex\2026-06-05\https-x-com-wy-mask-status\work\dsa-venv\Scripts\python.exe" -m unittest tests.test_platform_production_readiness_v48 tests.test_platform_local_real_use_loop_v14 tests.test_platform_release_candidate_package
```

- [ ] **Step 2: Run frontend tests and build**

```powershell
cd apps\dsa-web
npm run test -- src/pages/__tests__/AdminPage.test.tsx src/api/__tests__/platform.test.ts
npm run build
cd ..\..
```

- [ ] **Step 3: Run platform verifiers**

```powershell
& "C:\Users\26879\Documents\Codex\2026-06-05\https-x-com-wy-mask-status\work\dsa-venv\Scripts\python.exe" scripts\verify_platform_production_readiness_v48.py
& "C:\Users\26879\Documents\Codex\2026-06-05\https-x-com-wy-mask-status\work\dsa-venv\Scripts\python.exe" scripts\verify_platform_release_candidate_package.py
& "C:\Users\26879\Documents\Codex\2026-06-05\https-x-com-wy-mask-status\work\dsa-venv\Scripts\python.exe" scripts\verify_local_v1_operability.py
git diff --check
git status -sb --untracked-files=all
```

Expected: all commands pass; any dirty files are intentional V48 files only.
