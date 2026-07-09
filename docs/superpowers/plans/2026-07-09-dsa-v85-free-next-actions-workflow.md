# DSA V85 Free Next Actions Workflow Implementation Plan

> **For agentic workers:** Use `executing-plans` or an available multi-agent workflow to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the free quick-analysis “next action” guidance into clickable workflow buttons that keep users moving inside the result page.

**Architecture:** Add a V85 workflow card to the quick snapshot view, reusing existing handlers for refresh, module jumps, and watchlist persistence. The workflow stays no-AI by default and makes the login boundary explicit for saving watchlist/history state.

**Tech Stack:** React, TypeScript, Vitest, Testing Library, existing DSA local quick snapshot UI.

---

### Task 1: Add Failing Workflow Coverage

**Files:**
- Modify: `apps/dsa-web/src/pages/__tests__/HomePage.test.tsx`

- [x] **Step 1: Write the failing test**

Add assertions after the quick-analysis mode banner:
- `basic-query-next-actions-v85` exists
- panel shows `下一步工作流`
- panel shows `刷新行情`
- panel shows `看资讯`
- panel shows `看同业`
- panel shows `看K线`
- panel shows `保存自选`
- panel shows `未用 AI，不扣额度`
- clicking `刷新行情` calls `stocksApi.snapshot('AAPL', { refresh: true })`
- clicking `保存自选` while logged out shows `注册或登录后可保存自选`
- no AI call is made

- [x] **Step 2: Run the test to verify it fails**

Run:

```powershell
npm run test -- --run src/pages/__tests__/HomePage.test.tsx
```

Expected: fail because `basic-query-next-actions-v85` does not exist.

### Task 2: Implement Clickable Free Workflow

**Files:**
- Modify: `apps/dsa-web/src/pages/HomePage.tsx`

- [x] **Step 1: Add no-login watchlist boundary**

Update `handleAddCurrentQueryToPlatformWatchlist` so unauthenticated users see a local Chinese/English prompt instead of a raw API failure.

- [x] **Step 2: Add workflow data model**

Add a `basicNextActionsWorkflow` memo with localized title, subtitle, boundary label, and actions:
- refresh quote
- jump to news
- jump to peers
- jump to K-line
- save watchlist

- [x] **Step 3: Render workflow card**

Render `data-testid="basic-query-next-actions-v85"` in quick mode near the top of the result, with icon buttons and short helper text.

### Task 3: Verify And Commit

**Files:**
- Verify: `apps/dsa-web/src/pages/HomePage.tsx`
- Verify: `apps/dsa-web/src/pages/__tests__/HomePage.test.tsx`
- Verify: `docs/superpowers/plans/2026-07-09-dsa-v85-free-next-actions-workflow.md`

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

Open `http://127.0.0.1:8018/?dsa_v85_smoke=1`, query `AAPL`, open quick analysis, confirm the V85 workflow card appears, click `看资讯`, `看同业`, `看K线`, and confirm each target module is reachable.

- [x] **Step 4: Commit cleanly**

Commit only V85 files and finish with a clean working tree.
