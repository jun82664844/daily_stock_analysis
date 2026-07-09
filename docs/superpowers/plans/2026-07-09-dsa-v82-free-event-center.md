# DSA V82 Free Event Center Implementation Plan

> **For agentic workers:** Use `executing-plans` or an available multi-agent workflow to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade the free quick-analysis result into a more useful event-centered research view that can retain ordinary users without consuming AI quota.

**Architecture:** Reuse the existing `HomePage` quick snapshot data, free report, news center, peer comparison, profile, and diagnostics. Add one compact V82 event center card in the free quick-analysis page, with clear free-vs-premium boundaries and Chinese/English copy.

**Tech Stack:** React, TypeScript, Vitest, Testing Library, existing DSA local API snapshot contract.

---

### Task 1: Add Failing UI Coverage

**Files:**
- Modify: `apps/dsa-web/src/pages/__tests__/HomePage.test.tsx`

- [x] **Step 1: Write the failing test**

Add assertions in the existing quick-analysis test for `basic-query-free-event-center-v82`, including:
- title: `免费资讯与事件中心`
- why-now section: `为什么今天值得看`
- event timeline: `价格异动`, `资讯/公告`, `基本面背景`, `同业参照`
- free actions: `免费版可立即做`
- premium actions: `高级版补充验证`
- no AI guarantee: `未用 AI，不扣额度`

- [x] **Step 2: Run the test to verify it fails**

Run:

```powershell
npm run test -- --run src/pages/__tests__/HomePage.test.tsx
```

Expected: fail because `basic-query-free-event-center-v82` does not exist.

### Task 2: Implement V82 Event Center

**Files:**
- Modify: `apps/dsa-web/src/pages/HomePage.tsx`

- [x] **Step 1: Add memoized data model**

Create `basicFreeEventCenter` using existing `basicSnapshot`, `basicFreeReport`, `newsCenter`, `peerComparison`, quote, profile, and diagnostics data.

- [x] **Step 2: Render the V82 card**

Render after `basic-query-today-brief-card` and before the deeper panels so users see it early.

- [x] **Step 3: Preserve boundaries**

The card must show that free mode uses network/local public data, does not run AI, and premium adds API/source/model verification.

### Task 3: Verify And Commit

**Files:**
- Verify: `apps/dsa-web/src/pages/HomePage.tsx`
- Verify: `apps/dsa-web/src/pages/__tests__/HomePage.test.tsx`
- Verify: `docs/superpowers/plans/2026-07-09-dsa-v82-free-event-center.md`

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

Open `http://127.0.0.1:8018/?dsa_v82_smoke=1`, query `AAPL` and `600519.SH`, open quick analysis, and confirm the V82 event center is visible.

- [ ] **Step 4: Commit cleanly**

Commit only the V82 files and finish with a clean working tree.
