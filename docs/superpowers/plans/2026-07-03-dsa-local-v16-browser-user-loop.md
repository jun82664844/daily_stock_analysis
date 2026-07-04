# DSA Local V16 Browser User Loop Implementation Plan

> **For agentic workers:** Use `executing-plans` or an available multi-agent workflow to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prove the local ordinary-user query journey in a browser and against the running 8018 local backend without crossing into production launch work.

**Architecture:** Keep the existing mocked Playwright E2E for deterministic UI behavior, then add a V16 verifier that also runs a live local ordinary-user HTTP smoke against 8018 for A-share, US, HK, and crypto no-AI quick snapshots. The live smoke creates only `e2e+` local users, records degraded market-source failures honestly, and never deletes data.

**Tech Stack:** React/Vite, Playwright, Python verifier scripts, FastAPI local backend, existing release-package verifier.

---

### Task 1: Browser UI Guardrail Coverage

**Files:**
- Modify: `apps/dsa-web/e2e/platform-user-e2e.spec.ts`

- [ ] **Step 1: Write failing Playwright assertions**

Add assertions that the ordinary-user browser journey sees `platform-query-status`, `platform-ai-cost-warning`, and `basic-query-user-guardrails` after quick queries.

- [ ] **Step 2: Run the Playwright target**

Run:

```powershell
cd apps\dsa-web
$env:DSA_PLATFORM_E2E="1"
npm run test:smoke -- platform-user-e2e.spec.ts
Remove-Item Env:\DSA_PLATFORM_E2E
```

Expected before implementation: failure because the mock snapshot payload does not yet expose all market-lane data needed by the new assertions.

- [ ] **Step 3: Update the mock snapshot payload**

Return route, diagnostics, degradation, cache, and market-specific stock names for `600519`, `AAPL`, `HK00700`, and `BTC-USD`.

- [ ] **Step 4: Re-run Playwright**

Expected after implementation: the deterministic browser E2E passes and proves ordinary users do not see Admin, API keys stay masked, no-AI quick snapshot stays separate from history, and BYOK quick analysis consumes only BYOK quota.

### Task 2: V16 Verifier

**Files:**
- Create: `scripts/verify_platform_local_browser_user_loop_v16.py`
- Create: `tests/test_platform_local_browser_user_loop_v16.py`
- Modify: `.gitignore`

- [ ] **Step 1: Write failing verifier unittest**

Assert the V16 OK marker is `DSA_PLATFORM_LOCAL_BROWSER_USER_LOOP_V16_OK`, required files are present, and sample multi-market no-AI snapshot payloads validate.

- [ ] **Step 2: Run unittest and watch it fail**

Run:

```powershell
& "C:\Users\26879\Documents\Codex\2026-06-05\https-x-com-wy-mask-status\work\dsa-venv\Scripts\python.exe" -m unittest tests.test_platform_local_browser_user_loop_v16
```

Expected: import or missing verifier failure.

- [ ] **Step 3: Implement the verifier**

The verifier checks required files, gitignore visibility, V15 compatibility, focused Playwright E2E, and an optional live 8018 ordinary-user multi-market no-AI smoke.

- [ ] **Step 4: Re-run unittest and verifier**

Expected: unittest passes and verifier prints `DSA_PLATFORM_LOCAL_BROWSER_USER_LOOP_V16_OK`.

### Task 3: Release Package Integration

**Files:**
- Modify: `scripts/verify_platform_release_candidate_package.py`
- Modify: `tests/test_platform_release_candidate_package.py`
- Modify: `docs/superpowers/platform-review-slices.md`
- Modify: `docs/superpowers/platform-release-candidate-manifest.md`
- Modify: `docs/superpowers/platform-local-v1-acceptance-status.md`

- [ ] **Step 1: Add V16 to required files and visibility checks**

The release package verifier must fail if the V16 verifier, V16 unittest, or V16 plan is missing.

- [ ] **Step 2: Update docs and expected dirty counts**

Document the V16 local-only browser/user loop and the new dirty-tree handoff counts.

- [ ] **Step 3: Run package verifier and final gates**

Run V16 verifier, release package verifier, V1 operability, V2 readiness, frontend build, and `git diff --check`.

### Boundaries

- No real payment.
- No production deployment, domain, HTTPS, WAF, CDN, cloud migration, or legal/commercial launch decision.
- No real API Key in tests, docs, screenshots, verifier output, or logs.
- No deletion of reports, databases, users, API keys, billing rows, cache files, or `static/` build outputs.
- No `git add`, `git commit`, or `git push`.
- Analysis remains informational only and is not investment advice.
