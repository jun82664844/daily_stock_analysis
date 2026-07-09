# DSA V83 Event Detail Layer Implementation Plan

> **For agentic workers:** Use `executing-plans` or an available multi-agent workflow to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the free V82 event center interactive by letting users click each event lane and inspect a richer detail panel without consuming AI quota.

**Architecture:** Reuse the existing `basicFreeEventCenter.timeline` data and add an active timeline state in `HomePage`. Timeline entries become buttons with a single detail panel showing current read, source/freshness, free action, premium verification, and the information-analysis boundary.

**Tech Stack:** React, TypeScript, Vitest, Testing Library, existing DSA local quick snapshot UI.

---

### Task 1: Add Failing Interaction Coverage

**Files:**
- Modify: `apps/dsa-web/src/pages/__tests__/HomePage.test.tsx`

- [x] **Step 1: Write the failing test**

Add assertions after the V82 event center checks:
- default detail panel exists with `事件详情`
- click `资讯/公告` and assert detail panel shows `来源状态`, `免费版下一步`, `高级版验证`, `查看来源状态与原文链接`
- click `同业参照` and assert detail panel shows `同业参照` plus `对照同业/指数强弱`
- confirm no AI call was made

- [x] **Step 2: Run the test to verify it fails**

Run:

```powershell
npm run test -- --run src/pages/__tests__/HomePage.test.tsx
```

Expected: fail because `basic-query-free-event-detail-v83` does not exist.

### Task 2: Implement Clickable Detail Layer

**Files:**
- Modify: `apps/dsa-web/src/pages/HomePage.tsx`

- [x] **Step 1: Add active state**

Add `basicEventCenterActiveIndex` and reset it when a new basic query starts.

- [x] **Step 2: Extend timeline model**

Each timeline item includes `sourceStatus`, `freeNext`, `premiumVerify`, and `detailTitle`.

- [x] **Step 3: Render accessible timeline buttons and detail panel**

Timeline buttons should use `aria-pressed`, keep stable `data-testid`, and update one detail panel.

### Task 3: Verify And Commit

**Files:**
- Verify: `apps/dsa-web/src/pages/HomePage.tsx`
- Verify: `apps/dsa-web/src/pages/__tests__/HomePage.test.tsx`
- Verify: `docs/superpowers/plans/2026-07-09-dsa-v83-event-detail-layer.md`

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

Open `http://127.0.0.1:8018/?dsa_v83_smoke=1`, query `AAPL` and `600519.SH`, open quick analysis, click `资讯/公告` and `同业参照`, and confirm the detail panel changes.

Result: browser smoke passed for both `AAPL` and `600519.SH`; the event detail panel switched to `资讯/公告` and `同业参照`, and quick mode stayed no-AI.

- [x] **Step 4: Commit cleanly**

Commit only V83 files and finish with a clean working tree.
