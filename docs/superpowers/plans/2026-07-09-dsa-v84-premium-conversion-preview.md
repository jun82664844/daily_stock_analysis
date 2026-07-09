# DSA V84 Premium Conversion Preview Implementation Plan

> **For agentic workers:** Use `executing-plans` or an available multi-agent workflow to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the free quick-analysis Premium preview more persuasive by showing exactly what Premium/API mode adds while keeping free-mode content useful.

**Architecture:** Reuse the existing `basicTodayBriefCard` premium preview toggle and add a V84 conversion section inside the same expanded panel. The section compares free visibility with Premium data-source upgrades and keeps the boundary local-only: no real payment, no AI run, no quota spend.

**Tech Stack:** React, TypeScript, Vitest, Testing Library, existing DSA local quick snapshot UI.

---

### Task 1: Add Failing Conversion Coverage

**Files:**
- Modify: `apps/dsa-web/src/pages/__tests__/HomePage.test.tsx`

- [x] **Step 1: Write the failing test**

Add assertions after the existing `basic-query-premium-preview-panel` checks:
- `basic-query-premium-conversion-v84` exists after clicking `查看高级版会新增哪些内容`
- panel shows `升级价值预览`
- panel shows `免费版同样可看`
- panel shows `高级版换 API 数据源`
- panel shows `实时新闻原文`
- panel shows `公告/SEC 原文链接`
- panel shows `同业强弱 API`
- panel shows `Kronos/API 预测`
- panel shows `持续跟踪提醒`
- panel shows `本地预览，不接真实支付`
- no AI call is made

- [x] **Step 2: Run the test to verify it fails**

Run:

```powershell
npm run test -- --run src/pages/__tests__/HomePage.test.tsx
```

Expected: fail because `basic-query-premium-conversion-v84` does not exist.

### Task 2: Implement Premium Conversion Section

**Files:**
- Modify: `apps/dsa-web/src/pages/HomePage.tsx`

- [x] **Step 1: Extend `basicTodayBriefCard` data**

Add localized fields:
- `premiumConversionTitle`
- `premiumConversionSubtitle`
- `premiumConversionBoundary`
- `premiumConversionColumns`
- `premiumConversionRows`

- [x] **Step 2: Render the V84 section inside the preview panel**

Render a section with `data-testid="basic-query-premium-conversion-v84"` that shows:
- free mode remains usable
- Premium/API improves source quality and depth
- Premium rows for realtime news, filings/SEC, peer strength, Kronos/API forecast, and continuous tracking
- local-only payment boundary

### Task 3: Verify And Commit

**Files:**
- Verify: `apps/dsa-web/src/pages/HomePage.tsx`
- Verify: `apps/dsa-web/src/pages/__tests__/HomePage.test.tsx`
- Verify: `docs/superpowers/plans/2026-07-09-dsa-v84-premium-conversion-preview.md`

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

Open `http://127.0.0.1:8018/?dsa_v84_smoke=1`, query `AAPL`, open quick analysis, click `查看高级版会新增哪些内容`, and confirm the V84 conversion section is visible.

Result: browser smoke passed; `basic-query-premium-conversion-v84` was visible for `AAPL` quick analysis and showed free-vs-Premium API upgrade rows plus the local-only no-real-payment boundary.

- [x] **Step 4: Commit cleanly**

Commit only V84 files and finish with a clean working tree.
