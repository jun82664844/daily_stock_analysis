# DSA V118 财经首页信息架构改版 Implementation Plan

> **For agentic workers:** Use `executing-plans` or an available multi-agent workflow to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 DSA 首次进入页面改成以 A 股、港股、美股热门行情和可信市场资讯为主的财经首页，并把账户、套餐、额度和模型设置收到账户入口。

**Architecture:** 继续复用 `/api/v1/market-workspace/home` 的三地并发聚合和缓存，不增加首页强制 AI 或公共搜索。后端把市场工作台已有的 `headlines` 透传到首页；前端使用单一市场标签、主要指数、紧凑行情表和资讯流，资讯不可用时只展示由当前行情生成且明确标注的“行情动态”。公开互联网行情和资讯可以自动展示；平台 API、BYOK、Ollama 和 Kronos 只允许在用户主动查询后运行。首页保留紧凑账户入口，详细账户和模型选择迁到 `/account`。

**Tech Stack:** FastAPI、Pydantic、React、TypeScript、Tailwind CSS、Vitest、Testing Library、unittest、Playwright/browser control。

---

### Task 1: 扩展公共首页数据契约

**Files:**
- Modify: `api/v1/schemas/market_workspace.py`
- Modify: `src/services/public_market_home_service.py`
- Test: `tests/test_public_market_home_v116.py`

- [x] **Step 1: 写失败测试**

在 `_overview()` 中加入一条带来源状态的 headline，并断言 `PublicMarketHomeService.build()` 的对应市场保留 `headlines`；市场失败时断言 `headlines == []`。

- [x] **Step 2: 运行测试确认失败**

Run: `E:\DSA项目\dsa-venv\Scripts\python.exe -m unittest tests.test_public_market_home_v116 -v`

Expected: headline 断言失败，因为首页 section 尚未透传该字段。

- [x] **Step 3: 最小实现**

给 `PublicMarketHomeSection` 增加 `headlines: List[MarketHeadline]`，并在正常与降级 section 中分别返回 overview headlines 或空列表。

- [x] **Step 4: 运行测试确认通过**

Run: `E:\DSA项目\dsa-venv\Scripts\python.exe -m unittest tests.test_public_market_home_v116 -v`

Expected: PASS。

### Task 2: 重构三地行情和资讯首屏

**Files:**
- Modify: `apps/dsa-web/src/api/marketWorkspace.ts`
- Modify: `apps/dsa-web/src/components/market-home/PublicMarketHomeV116.tsx`
- Test: `apps/dsa-web/src/components/market-home/__tests__/PublicMarketHomeV116.test.tsx`

- [x] **Step 1: 写失败测试**

断言新首页包含 `public-home-market-dashboard-v118`、A 股/港股/美股标签、紧凑行情表、正式市场快讯或明确的行情动态，不显示内部版本号 `DSA V116`；保留查看股票和到价提醒交互。

- [x] **Step 2: 运行测试确认失败**

Run: `npm.cmd run test -- --run src/components/market-home/__tests__/PublicMarketHomeV116.test.tsx`

Workdir: `apps/dsa-web`

Expected: 新标题、V118 test id 和资讯区域缺失。

- [x] **Step 3: 最小实现**

把三列大卡片替换成三市场标签条、当前市场紧凑行情表和右侧资讯流。正式 headline 存在时显示标题、发布方、时间和原始链接；否则仅根据当前行情展示“行情动态”。保留来源、新鲜度、价格、涨跌、查看股票和到价提醒。

- [x] **Step 4: 运行测试确认通过**

Run: `npm.cmd run test -- --run src/components/market-home/__tests__/PublicMarketHomeV116.test.tsx`

Expected: PASS。

### Task 3: 收纳主页账户信息和模型设置

**Files:**
- Modify: `apps/dsa-web/src/pages/HomePage.tsx`
- Modify: `apps/dsa-web/src/pages/AccountPage.tsx`
- Test: `apps/dsa-web/src/pages/__tests__/HomePage.test.tsx`
- Test: `apps/dsa-web/src/pages/__tests__/AccountPage.test.tsx`

- [x] **Step 1: 写失败测试**

断言已登录首页只显示邮箱、套餐、剩余额度、`账户与模型` 和退出，不再显示 BYOK 详情、自选控制、费用说明或完整模型选择器；断言账户页显示模型选择并把选择写入 `dsa.modelOptionId`。

- [x] **Step 2: 运行测试确认失败**

Run: `npm.cmd run test -- --run src/pages/__tests__/HomePage.test.tsx src/pages/__tests__/AccountPage.test.tsx`

Workdir: `apps/dsa-web`

Expected: 首页仍有完整账户面板，账户页尚无模型选择器。

- [x] **Step 3: 最小实现**

把登录态首页面板改为一行账户摘要和 `/account` 入口，游客登录表单默认折叠；账户页加载 `selectedOptionId` 并渲染 `SimpleModelPickerV112`，选择后写本地设置。已有分析页结果区的模型入口继续保留。

- [x] **Step 4: 运行测试确认通过**

Run: `npm.cmd run test -- --run src/pages/__tests__/HomePage.test.tsx src/pages/__tests__/AccountPage.test.tsx`

Expected: PASS。

### Task 4: V118 门禁和浏览器验收

**Files:**
- Create: `scripts/verify_platform_public_home_experience_v118.py`
- Create: `tests/test_platform_public_home_experience_v118_verifier.py`
- Modify: `scripts/verify_platform_release_candidate_package.py`
- Modify: `docs/superpowers/platform-release-candidate-manifest.md`
- Modify: `.gitignore`

- [x] **Step 1: 写 verifier 测试并确认失败**

验证 verifier 必须覆盖后端 headline 契约、前端 V118 test id、账户点击入口、中英文和“仅提供资讯和数据，不构成投资建议”边界，并输出 `DSA_PLATFORM_PUBLIC_HOME_EXPERIENCE_V118_OK`。

- [x] **Step 2: 实现 verifier 并运行验证**

Run: `E:\DSA项目\dsa-venv\Scripts\python.exe scripts\verify_platform_public_home_experience_v118.py`

Expected: 所有 V118 检查通过并输出唯一 OK marker。

- [x] **Step 3: 运行回归与构建**

Run: `E:\DSA项目\dsa-venv\Scripts\python.exe -m unittest tests.test_public_market_home_v116 tests.test_platform_public_home_experience_v118_verifier -v`

Run: `npm.cmd run test -- --run src/components/market-home/__tests__/PublicMarketHomeV116.test.tsx src/pages/__tests__/HomePage.test.tsx src/pages/__tests__/AccountPage.test.tsx`

Run: `npm.cmd run build`

Expected: 全部退出码 0。

- [x] **Step 4: 浏览器桌面和手机验收**

重启 8018 到当前代码，桌面和 390x844 手机视口检查：首屏三地市场入口可见、行情与资讯布局无横向溢出、账户详情不铺满主页、账户入口可达、查询仍可用、页面不含投资建议或交易指令。

- [x] **Step 5: 收口检查**

Run: `git diff --check`

Run: `git status --short --untracked-files=all`

扫描真实密钥模式并记录 dirty 分布；不执行 push，不删除用户数据。
