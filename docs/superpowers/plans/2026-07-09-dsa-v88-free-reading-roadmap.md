# DSA V88 Free Reading Roadmap Implementation Plan

> **For agentic workers:** Use `executing-plans` or an available multi-agent workflow to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the free quick-analysis result into an easy-to-follow reading route so users know how to consume the report and why premium adds value.

**Architecture:** Add a no-AI V88 reading roadmap section in `HomePage.tsx` after the V87 visual analyst page. It should reuse existing quick snapshot, V86/V87 summary, and existing jump handlers to guide users through conclusion, chart evidence, news, peers, K-line, and premium data-source upgrade triggers.

**Tech Stack:** React, TypeScript, Vitest, Testing Library, existing DSA quick snapshot UI.

---

### Task 1: Add Failing Roadmap Coverage

**Files:**
- Modify: `apps/dsa-web/src/pages/__tests__/HomePage.test.tsx`

- [x] **Step 1: Write the failing test**

Add assertions in the no-AI quick-query test:
- `basic-query-reading-roadmap-v88` exists
- shows `3分钟研判路线`
- shows `第一步：看结论`
- shows `第二步：看图形证据`
- shows `第三步：核对资讯与同业`
- shows `第四步：看K线情景`
- shows `免费版可完整阅读`
- shows `高级版补数据源`
- clicking `看资讯`, `看同业`, and `看K线` does not call `analysisApi.analyzeAsync`

- [x] **Step 2: Run the test to verify it fails**

```powershell
npm run test -- --run src/pages/__tests__/HomePage.test.tsx
```

Expected: fail because `basic-query-reading-roadmap-v88` does not exist.

### Task 2: Implement Reading Roadmap

**Files:**
- Modify: `apps/dsa-web/src/pages/HomePage.tsx`

- [x] **Step 1: Add roadmap data model**

Create `basicReadingRoadmap` from `basicSnapshot` and `basicFreeReport`. It should include localized title, subtitle, no-AI boundary, four reading steps, action labels, and free-vs-premium explanation.

- [x] **Step 2: Render V88 section**

Render `data-testid="basic-query-reading-roadmap-v88"` in quick mode after the V87 visual analyst page. Include:
- four numbered steps
- compact action buttons for news, peers, and K-line
- free complete-read label
- premium data-source upgrade label
- no-AI boundary

- [x] **Step 3: Keep it no-AI**

All actions must reuse existing jump handlers and must not call `analysisApi.analyzeAsync`.

### Task 3: Verify And Commit

**Files:**
- Verify: `apps/dsa-web/src/pages/HomePage.tsx`
- Verify: `apps/dsa-web/src/pages/__tests__/HomePage.test.tsx`
- Verify: `docs/superpowers/plans/2026-07-09-dsa-v88-free-reading-roadmap.md`

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

Open `http://127.0.0.1:8018/?dsa_v88_smoke=1`, query `AAPL`, open quick analysis, confirm the V88 reading roadmap appears after the visual analyst page, and confirm its `看资讯`, `看同业`, and `看K线` buttons reach target modules.

- [x] **Step 4: Commit cleanly**

Commit only V88 files and finish with a clean working tree.
