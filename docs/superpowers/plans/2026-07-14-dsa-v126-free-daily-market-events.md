# DSA V126 免费每日市场事件中心实施计划

> **For agentic workers:** Use `executing-plans` or an available multi-agent workflow to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将现有 A 股、港股、美股公开资讯归一化为来源可追溯、可分类、可关联个股、可突出自选股的免费每日市场事件中心，让游客和免费用户每天都有可阅读、可继续查询的内容。

**Architecture:** 后端新增纯规则 `PublicMarketEventService`，只消费现有首页 `headlines` 和榜单证券，不新增第三方抓取，也不调用 AI。`PublicMarketHomeService` 在三地市场数据完成后生成统一事件数组；前端以懒加载组件展示分类筛选、时间、来源、关联股票和自选标记，点击关联股票复用现有免费查询入口。

**Tech Stack:** Python 3.12、FastAPI/Pydantic、React 19、TypeScript、Vitest、unittest、Vite、现有 DSA release verifier 和浏览器验收工具。

---

### Task 1: 事件归一化服务

**Files:**
- Create: `src/services/public_market_event_service.py`
- Create: `tests/test_public_market_event_service.py`

- [x] **Step 1: Write failing classification tests**

测试输入包含“业绩预增”“派息回购”“停复牌”“美联储利率”“收购合作”和普通市场新闻，断言输出类别分别为 `earnings`、`dividend`、`trading_status`、`macro`、`corporate`、`market`。

- [x] **Step 2: Run tests to verify RED**

Run: `E:\DSA项目\dsa-venv\Scripts\python.exe -m unittest tests.test_public_market_event_service -v`

Expected: FAIL because `PublicMarketEventService` does not exist.

- [x] **Step 3: Implement deterministic normalization**

服务必须：

```python
events = PublicMarketEventService().build(markets, as_of)
```

输出稳定 `event_id`、`market`、`category`、`title`、`summary`、`symbol`、`name`、`event_time`、`time_kind`、`publisher`、`url`、`source_state`、`classification_source="keyword_rules"`。使用标题关键词分类；标题明确出现 `.SH`、`.SZ`、`.HK` 时以交易所代码校正混合资讯源的市场标签并允许直接查询；其他情况只在标题确实包含带边界的榜单证券代码或名称时关联股票，1 至 2 位美股代码需要 `$` cashtag；已知发布时间的事件优先并按时间倒序，缺少发布时间的抓取记录随后按抓取时间倒序，避免把抓取时刻伪装成事件发生时刻；相同市场、标题和时间去重。

- [x] **Step 4: Verify GREEN and edge cases**

覆盖缺失时间、重复标题、危险 URL 不由本服务扩写、无关联股票、三市场顺序和总条数上限。

### Task 2: 首页 API 契约与降级

**Files:**
- Modify: `api/v1/schemas/market_workspace.py`
- Modify: `src/services/public_market_home_service.py`
- Modify: `tests/test_public_market_home_v116.py`

- [x] **Step 1: Write failing API-contract tests**

断言首页响应新增 `events`，事件服务异常时首页仍返回三地行情并追加 `market_events_unavailable`，且 `ai_used=false`、`informational_only=true` 不变。

- [x] **Step 2: Run tests to verify RED**

Run: `E:\DSA项目\dsa-venv\Scripts\python.exe -m unittest tests.test_public_market_home_v116 -v`

Expected: FAIL because the home response has no structured events.

- [x] **Step 3: Add additive Pydantic models and integration**

新增 `PublicMarketEvent`，事件分类枚举只允许 `earnings|announcement|dividend|trading_status|macro|corporate|market`，时间语义只允许 `published|observed|retrieved|unknown`。旧响应缺少 `events` 时使用空数组，保持兼容。

- [x] **Step 4: Verify GREEN**

事件生成只处理已经完成的首页数据，不增加网络请求；事件服务失败必须 fail-open，不影响行情和新闻。

### Task 3: 前端事件数据契约

**Files:**
- Modify: `apps/dsa-web/src/api/marketWorkspace.ts`
- Modify: `apps/dsa-web/src/api/__tests__/marketWorkspace.test.ts`

- [x] **Step 1: Write failing camel-case/default tests**

断言 snake_case 事件转换为 camelCase，旧响应缺少 `events` 时返回 `[]`。

- [x] **Step 2: Run RED**

Run: `npm.cmd run test -- --run src/api/__tests__/marketWorkspace.test.ts`

- [x] **Step 3: Add TypeScript event types and safe defaults**

事件类型与后端枚举完全一致，不接受交易指令、目标价、收益预测字段。

- [x] **Step 4: Run GREEN**

同 Step 2，Expected: PASS.

### Task 4: 双语每日事件中心

**Files:**
- Create: `apps/dsa-web/src/components/market-home/DailyMarketEventCenterV126.tsx`
- Create: `apps/dsa-web/src/components/market-home/__tests__/DailyMarketEventCenterV126.test.tsx`
- Modify: `apps/dsa-web/src/components/market-home/PublicMarketHomeV116.tsx`
- Modify: `apps/dsa-web/src/components/market-home/__tests__/PublicMarketHomeV116.test.tsx`

- [x] **Step 1: Write failing UI tests**

中文断言“今日市场事件、全部、财报业绩、公告披露、分红回购、交易状态、宏观数据、公司事项、仅提供资讯和数据”；英文断言对应英文且不残留中文。测试类别筛选、自选标记、来源时间、外链安全属性和关联股票点击。

- [x] **Step 2: Run RED**

Run: `npm.cmd run test -- --run src/components/market-home/__tests__/DailyMarketEventCenterV126.test.tsx src/components/market-home/__tests__/PublicMarketHomeV116.test.tsx`

- [x] **Step 3: Implement a dense, lazy-loaded event center**

使用标签按钮筛选全部事件类别，包括一般市场动态；每行显示市场或资讯源、类别、标题、发布时间语义、发布者、来源状态；未关联证券的跨市场资讯明确标为资讯源，避免把频道误解为受影响市场；关联股票使用按钮进入现有免费查询；自选股只显示“自选”标记，不改变公开响应。组件通过 `lazy(() => import(...))` 加载，并提供稳定高度占位，避免首页包体和布局回退。

- [x] **Step 4: Run GREEN**

同 Step 2，Expected: PASS.

### Task 5: 首页自选个性化接线

**Files:**
- Modify: `apps/dsa-web/src/pages/HomePage.tsx`
- Modify: `apps/dsa-web/src/pages/__tests__/HomePage.test.tsx`

- [x] **Step 1: Write failing source/interaction test**

断言 `HomePage` 将 `platformWatchlist.items[].stockCode` 作为 `watchlistSymbols` 传入公开首页；游客传空数组；不得把用户自选写回公开首页 API 或缓存。

- [x] **Step 2: Run RED**

Run: `npm.cmd run test -- --run src/pages/__tests__/HomePage.test.tsx`

- [x] **Step 3: Implement client-side personalization**

只在浏览器内建立大写股票代码集合并传给事件中心。登录、退出或切换用户后复用现有自选状态刷新，不新增私有接口。

- [x] **Step 4: Run GREEN**

同 Step 2，Expected: PASS.

### Task 6: 发布门禁、文档与验收

**Files:**
- Create: `scripts/verify_platform_free_daily_market_events_v126.py`
- Create: `tests/test_platform_free_daily_market_events_v126_verifier.py`
- Modify: `.gitignore`
- Modify: `scripts/verify_platform_release_candidate_package.py`
- Modify: `tests/test_platform_release_candidate_package.py`
- Modify: `docs/CHANGELOG.md`
- Modify: `docs/superpowers/platform-local-v1-acceptance-status.md`
- Modify: `docs/superpowers/platform-review-slices.md`
- Modify: `docs/superpowers/platform-release-candidate-manifest.md`

- [x] **Step 1: Write failing verifier tests**

门禁检查事件服务、API schema、懒加载组件、双语文案、自选只在客户端处理、`ai_used=false`、合规提示和最新 `HomePage-*.js < 500000 bytes`。

- [x] **Step 2: Run RED and implement verifier**

Run: `E:\DSA项目\dsa-venv\Scripts\python.exe -m unittest tests.test_platform_free_daily_market_events_v126_verifier -v`

Expected before implementation: FAIL. Passing marker: `DSA_PLATFORM_FREE_DAILY_MARKET_EVENTS_V126_OK`.

- [x] **Step 3: Run complete local verification**

Run focused backend suites, focused frontend suites, `npm.cmd run build`, V125/V126 verifiers, release package verifier, `git diff --check` and changed-file secret scan.

- [x] **Step 4: Browser acceptance**

在独立端口实测桌面与 390px 移动端：首页有三地事件、分类筛选、自选标记、公开来源链接、关联股票查询、中英文切换、无横向溢出、控制台无错误。事件源不可用时诚实显示空状态，行情区域继续可用。

- [x] **Step 5: Local delivery**

未获得单独提交授权前不执行 `git commit` 或 `git push`。完成后报告验证证据、脏树文件清单和建议提交命令；如用户已明确授权本地提交，则仅暂存验证过的文件并本地提交，不推送。
