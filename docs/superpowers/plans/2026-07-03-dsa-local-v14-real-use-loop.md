# DSA Local V14 Real Use Loop Implementation Plan

> **For agentic workers:** Use `executing-plans` or an available multi-agent workflow to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the local 8018 platform easier to operate in real local use by adding a read-only admin status surface, matching frontend status panel, and a single V14 verifier.

**Architecture:** Reuse the existing platform admin boundary and market-source diagnostics instead of adding a separate ops subsystem. The backend exposes one sanitized, admin-only local status endpoint; the frontend renders the same data in AdminPage; the verifier proves no-AI, no-secret, no-production boundaries.

**Tech Stack:** FastAPI, Pydantic-style dictionaries, unittest/TestClient, React/Vite/Vitest, PowerShell-compatible Python verifier scripts.

---

## Boundaries

- Local-only. No production deployment, no real payment, no real merchant keys, no DNS/HTTPS/WAF work.
- Do not delete reports, databases, historical analysis, user data, API keys, or `static/` build output.
- Do not run `git add`, `git commit`, or `git push`.
- Do not print API keys, admin passwords, tokens, cookies, local secret paths, or raw provider exceptions.
- Stock analysis remains informational only and is not investment advice.

## Files

- Create: `src/services/local_functional_status.py`
- Modify: `api/v1/endpoints/platform.py`
- Modify: `apps/dsa-web/src/api/platform.ts`
- Modify: `apps/dsa-web/src/pages/AdminPage.tsx`
- Modify: `apps/dsa-web/src/pages/__tests__/AdminPage.test.tsx`
- Modify: `apps/dsa-web/src/api/__tests__/platform.test.ts`
- Create: `tests/test_platform_local_real_use_loop_v14.py`
- Create: `scripts/verify_platform_local_real_use_loop_v14.py`
- Modify: `.gitignore`
- Modify: `scripts/verify_platform_release_candidate_package.py`
- Modify: `tests/test_platform_release_candidate_package.py`
- Modify: `docs/superpowers/platform-review-slices.md`
- Modify: `docs/superpowers/platform-release-candidate-manifest.md`
- Modify: `docs/superpowers/platform-local-v1-acceptance-status.md`

## Task 1: Backend Local Status Contract

**Files:**
- Create: `tests/test_platform_local_real_use_loop_v14.py`
- Create: `src/services/local_functional_status.py`
- Modify: `api/v1/endpoints/platform.py`

- [ ] **Step 1: Write failing backend tests**

Run:

```powershell
& "C:\Users\26879\Documents\Codex\2026-06-05\https-x-com-wy-mask-status\work\dsa-venv\Scripts\python.exe" -m unittest tests.test_platform_local_real_use_loop_v14
```

Expected before implementation:

```text
FAILED (errors=... or failures=...)
```

- [ ] **Step 2: Implement local status builder**

`build_local_functional_status()` must return:

```python
{
    "mode": "local_only",
    "ai_used": False,
    "generated_at": "...",
    "service": {"webui": "ok", "host": "127.0.0.1", "port": 8018},
    "auth": {"platform_user_auth_enabled": True, "admin_auth_enabled": True},
    "billing": {"enabled": False, "provider": "disabled", "mode": "local_only"},
    "ai": {"default_model": "...", "local_model_enabled": False, "byok_supported": True, "public_search_enabled": False},
    "market": {"summary": {...}, "cache": {...}, "lanes": [...]},
    "safety": {"no_ai_status": True, "secrets_redacted": True, "real_payment_enabled": False},
}
```

- [ ] **Step 3: Add admin endpoint**

Add `GET /api/v1/platform/admin/local-status`. It must reuse `_require_admin_identity(request)` and return the builder payload.

- [ ] **Step 4: Run backend test green**

Run the same unittest command and expect `OK`.

## Task 2: Frontend Status Panel

**Files:**
- Modify: `apps/dsa-web/src/api/platform.ts`
- Modify: `apps/dsa-web/src/api/__tests__/platform.test.ts`
- Modify: `apps/dsa-web/src/pages/AdminPage.tsx`
- Modify: `apps/dsa-web/src/pages/__tests__/AdminPage.test.tsx`

- [ ] **Step 1: Write failing frontend tests**

Run:

```powershell
cd apps\dsa-web
npm test -- --run src/api/__tests__/platform.test.ts src/pages/__tests__/AdminPage.test.tsx
cd ..\..
```

Expected before implementation: missing `adminLocalStatus` API or missing status panel text.

- [ ] **Step 2: Add typed API client**

Add `PlatformLocalStatusResponse` and `platformApi.adminLocalStatus()` calling `/api/v1/platform/admin/local-status`.

- [ ] **Step 3: Render AdminPage status panel**

Load `adminLocalStatus()` with existing admin data. Show service, market, cache, no-AI, BYOK/local model, public search, and billing boundary states.

- [ ] **Step 4: Run frontend tests green**

Same Vitest command must pass.

## Task 3: V14 Verifier and Package Coverage

**Files:**
- Create: `scripts/verify_platform_local_real_use_loop_v14.py`
- Modify: `.gitignore`
- Modify: `scripts/verify_platform_release_candidate_package.py`
- Modify: `tests/test_platform_release_candidate_package.py`

- [ ] **Step 1: Write verifier tests**

Backend test must import the verifier and assert the OK marker:

```text
DSA_PLATFORM_LOCAL_REAL_USE_LOOP_V14_OK
```

- [ ] **Step 2: Implement verifier**

The verifier must check required files, run backend V14 unittest, run frontend V14 target tests, run V13 compatibility checks, optionally smoke live 8018 `/api/v1/platform/admin/local-status`, and print the OK marker only when required checks do not fail.

- [ ] **Step 3: Make verifier visible to git**

Update `.gitignore` with an explicit unignore for `scripts/verify_platform_local_real_use_loop_v14.py`.

- [ ] **Step 4: Update release package verifier**

Add the V14 files to required files, visible verifier files, and dirty classification tests.

## Task 4: Docs and Final Validation

**Files:**
- Modify: `docs/superpowers/platform-review-slices.md`
- Modify: `docs/superpowers/platform-release-candidate-manifest.md`
- Modify: `docs/superpowers/platform-local-v1-acceptance-status.md`

- [ ] **Step 1: Update docs**

Add V14 gate notes and current dirty-tree counts after implementation.

- [ ] **Step 2: Run validation**

Run:

```powershell
& "C:\Users\26879\Documents\Codex\2026-06-05\https-x-com-wy-mask-status\work\dsa-venv\Scripts\python.exe" -m unittest tests.test_platform_local_real_use_loop_v14 tests.test_platform_release_candidate_package
cd apps\dsa-web
npm test -- --run src/api/__tests__/platform.test.ts src/pages/__tests__/AdminPage.test.tsx
npm run build
cd ..\..
& "C:\Users\26879\Documents\Codex\2026-06-05\https-x-com-wy-mask-status\work\dsa-venv\Scripts\python.exe" scripts\verify_platform_local_real_use_loop_v14.py
& "C:\Users\26879\Documents\Codex\2026-06-05\https-x-com-wy-mask-status\work\dsa-venv\Scripts\python.exe" scripts\verify_platform_release_candidate_package.py
& "C:\Users\26879\Documents\Codex\2026-06-05\https-x-com-wy-mask-status\work\dsa-venv\Scripts\python.exe" scripts\verify_local_v1_operability.py
git diff --check
git status --short --untracked-files=all
```

Expected: required checks pass; live-only admin smoke may be degraded if no safe admin password/session is available, but ordinary user access must remain forbidden in tests.
