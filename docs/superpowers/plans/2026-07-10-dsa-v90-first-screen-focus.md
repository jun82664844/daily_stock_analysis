# DSA V90 First Screen Focus Implementation Plan

> **For agentic workers:** Use `executing-plans` or an available multi-agent workflow to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reduce free quick-analysis first-screen clutter by making the top path read as a professional decision flow and moving repeated legacy analysis cards into a secondary evidence-library role.

**Architecture:** Reuse the existing quick snapshot, V89 decision desk, and local jump handlers. Add one compact V90 focus strip between `basic-query-mode-banner` and the V89 decision desk, then mark V86/V87/V88 detailed modules as secondary evidence modules without removing their content or changing quota behavior.

**Tech Stack:** React, TypeScript, Vitest, Testing Library, existing DSA quick snapshot UI.

---

### Task 1: Add Failing First-Screen Coverage

**Files:**
- Modify: `apps/dsa-web/src/pages/__tests__/HomePage.test.tsx`

- [x] **Step 1: Write the failing test**

Add assertions in the no-AI quick-query test:
- `basic-query-first-screen-focus-v90` exists
- appears after `basic-query-mode-banner`
- appears before `basic-query-broker-decision-desk-v89`
- shows `首屏聚焦`
- shows `第一屏先看四件事`
- shows `结论`
- shows `证据`
- shows `风险`
- shows `升级差异`
- shows `下方模块降为证据库`
- shows `免费版不锁内容`
- shows `未用 AI，不扣额度`
- clicking `看决策台`, `看证据库`, and `看升级差异` must not call `analysisApi.analyzeAsync`
- V86/V87/V88 detailed sections have `data-density="secondary"`

- [x] **Step 2: Run the test to verify it fails**

```powershell
npm run test -- --run src/pages/__tests__/HomePage.test.tsx
```

Expected: fail because `basic-query-first-screen-focus-v90` does not exist yet.

### Task 2: Implement First-Screen Focus

**Files:**
- Modify: `apps/dsa-web/src/pages/HomePage.tsx`

- [x] **Step 1: Add V90 focus data model**

Create `basicFirstScreenFocus` from `basicSnapshot` and `basicFreeReport`. It should include localized title, subtitle, no-AI boundary, four focus points, and action labels.

- [x] **Step 2: Render compact focus strip**

Render `data-testid="basic-query-first-screen-focus-v90"` immediately after `basic-query-mode-banner` and before `basic-query-broker-decision-desk-v89`.

- [x] **Step 3: Mark repeated modules as secondary**

Add `data-density="secondary"` to:
- `basic-query-free-analyst-workbench-v86`
- `basic-query-visual-analyst-page-v87`
- `basic-query-reading-roadmap-v88`

Keep all content visible and all actions local/no-AI.

### Task 3: Verify And Commit

**Files:**
- Verify: `apps/dsa-web/src/pages/HomePage.tsx`
- Verify: `apps/dsa-web/src/pages/__tests__/HomePage.test.tsx`
- Verify: `docs/superpowers/plans/2026-07-10-dsa-v90-first-screen-focus.md`

- [x] **Step 1: Run target tests**

```powershell
npm run test -- --run src/pages/__tests__/HomePage.test.tsx
```

- [x] **Step 2: Run build and local gates**

```powershell
npx tsc --noEmit -p tsconfig.app.json
npm run build
python scripts\verify_local_v1_operability.py
git diff --check
```

- [x] **Step 3: Browser smoke**

Open `http://127.0.0.1:8018/?dsa_v90_smoke=1`, query `AAPL`, open quick analysis, confirm the V90 focus strip appears near the top before V89, and confirm its buttons navigate to the intended sections.

- [x] **Step 4: Commit cleanly**

Commit only V90 files and finish with a clean working tree.
