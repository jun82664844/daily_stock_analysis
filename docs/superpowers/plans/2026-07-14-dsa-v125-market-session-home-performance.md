# DSA V125 市场时段与首页性能 Implementation Plan

> **For agentic workers:** Use `executing-plans` or an available multi-agent workflow to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让公开首页准确展示 A 股、港股和美股的交易阶段、当地时间及开收盘倒计时，并将 `HomePage` 路由主包降到 500KB 以下。

**Architecture:** 后端新增独立的市场时段解析服务，复用 `exchange_calendars` 和现有 `trading_calendar`，只在日历结果可靠时给出明确阶段，异常时诚实降级为 `unknown`。前端通过扩展后的公开首页 DTO 展示中英文阶段和倒计时；查询后才需要的重组件改为动态加载，公开首页首屏组件保持直接可用。

**Tech Stack:** Python 3、FastAPI/Pydantic、exchange-calendars、React、TypeScript、Vite、Vitest、Playwright、unittest

---

### Task 1: 固定市场时段服务契约

**Files:**
- Create: `src/services/public_market_session_service.py`
- Create: `tests/test_public_market_session_service.py`
- Modify: `src/services/market_workspace_service.py`
- Modify: `src/services/public_market_home_service.py`

- [x] **Step 1: Write the failing tests**

覆盖 `premarket`、`intraday`、`lunch_break`、`closing_auction`、`postmarket`、`non_trading`、`unknown`，并断言只有 `intraday` 和 `closing_auction` 映射为 `open`。

- [x] **Step 2: Run tests to verify RED**

Run: `E:\DSA项目\dsa-venv\Scripts\python.exe -m unittest tests.test_public_market_session_service -v`

Expected: FAIL because `PublicMarketSessionService` does not exist.

- [x] **Step 3: Implement the minimal service**

服务接收 ISO 时间或时区感知 `datetime`，调用 `build_market_phase_context`，返回阶段、当地时间、距开盘/收盘分钟数、来源和警告码。日历异常必须返回 `unknown`，不得把未知状态包装为已开盘或已收盘。

- [x] **Step 4: Integrate overview and public home**

`MarketWorkspaceService.get_overview()` 和 `PublicMarketHomeService.build()` 都使用同一时段契约；即使行情或榜单超时，公开首页仍可独立展示交易阶段。

- [x] **Step 5: Run tests to verify GREEN**

Run: `E:\DSA项目\dsa-venv\Scripts\python.exe -m unittest tests.test_public_market_session_service tests.test_public_market_home_v116 -v`

Expected: PASS.

### Task 2: 扩展 API Schema 与前端类型

**Files:**
- Modify: `api/v1/schemas/market_workspace.py`
- Modify: `apps/dsa-web/src/api/marketWorkspace.ts`
- Modify: `apps/dsa-web/src/api/__tests__/marketWorkspace.test.ts`

- [x] **Step 1: Write the failing API mapping test**

断言 snake_case 的 `session_phase`、`market_local_time`、`minutes_to_open`、`minutes_to_close`、`session_source` 和 `session_warning_codes` 能完整转换为 camelCase。

- [x] **Step 2: Run test to verify RED**

Run: `npm.cmd run test -- --run src/api/__tests__/marketWorkspace.test.ts`

Expected: FAIL because the fields are not represented in the TypeScript contract.

- [x] **Step 3: Extend schemas and types**

阶段只允许七个既定枚举值；分钟字段必须非负或为空；来源只允许 `exchange_calendar` 或 `unavailable`。

- [x] **Step 4: Run test to verify GREEN**

Run: `npm.cmd run test -- --run src/api/__tests__/marketWorkspace.test.ts`

Expected: PASS.

### Task 3: 首页交易时段中英文展示

**Files:**
- Modify: `apps/dsa-web/src/components/market-home/DailyMarketWorkbenchV124.tsx`
- Modify: `apps/dsa-web/src/components/market-home/__tests__/DailyMarketWorkbenchV124.test.tsx`

- [x] **Step 1: Write failing UI tests**

中文模式断言“盘前、交易中、午间休市、收盘集合阶段、已收盘、今日休市、时段待确认”和“距开盘/距收盘”；英文模式断言对应英文，不出现中文残留。

- [x] **Step 2: Run tests to verify RED**

Run: `npm.cmd run test -- --run src/components/market-home/__tests__/DailyMarketWorkbenchV124.test.tsx`

Expected: FAIL because the component only understands open/closed/unknown.

- [x] **Step 3: Implement phase-aware labels**

优先使用后端返回的 `marketLocalTime`；来源标注为交易所日历；未知状态显示待确认并保留警告，不推测交易状态。

- [x] **Step 4: Run tests to verify GREEN**

Run: same command as Step 2. Expected: PASS.

### Task 4: 拆分查询后重组件并设置 500KB 门禁

**Files:**
- Modify: `apps/dsa-web/src/pages/HomePage.tsx`
- Modify: `apps/dsa-web/src/pages/__tests__/HomePage.test.tsx` or focused source-contract test
- Create: `scripts/verify_platform_market_sessions_home_performance_v125.py`
- Create: `tests/test_platform_market_sessions_home_performance_v125_verifier.py`

- [x] **Step 1: Write failing verifier tests**

断言查询后才显示的研究、留存、雷达和全球增强组件使用动态导入；构建后最新 `HomePage-*.js` 原始大小小于 500,000 bytes。

- [x] **Step 2: Run tests to verify RED**

Run: `E:\DSA项目\dsa-venv\Scripts\python.exe -m unittest tests.test_platform_market_sessions_home_performance_v125_verifier -v`

Expected: FAIL because V125 verifier and dynamic imports do not exist.

- [x] **Step 3: Convert heavy conditional components to lazy chunks**

动态加载 `DecisionJourneyV91`、`FreeApiTrialPanelV93`、`WatchlistEventRadarV99`、`DailyResearchCockpitV103` 和 `GlobalEquityEnrichmentCard`，使用稳定尺寸的加载占位，避免布局跳动。

- [x] **Step 4: Build and enforce size gate**

Run: `npm.cmd run build`

Expected: PASS and newest `HomePage-*.js` < 500,000 bytes.

### Task 5: 总验收、文档与本地提交

**Files:**
- Modify: `.gitignore`
- Modify: `scripts/verify_platform_release_candidate_package.py`
- Modify: `docs/superpowers/platform-release-candidate-manifest.md`
- Modify: `docs/superpowers/platform-local-v1-acceptance-status.md`

- [x] **Step 1: Run focused backend and frontend suites**

运行 V125 服务、公开首页、API、工作台和 HomePage 相关测试。

- [x] **Step 2: Run build and release verifiers**

运行 V125 verifier、release candidate package verifier、`git diff --check` 和敏感信息扫描。

- [x] **Step 3: Browser acceptance**

桌面和移动端实测公开首页：三地市场阶段、当地时间、倒计时、中英文切换、股票点击查询、无横向溢出、控制台无错误。

- [x] **Step 4: Local commit and main integration**

仅本地提交，不 push；合入主工作区后重启 8018，复测 `/health` 和最终浏览器路径，确认主工作区与 V125 工作区都干净。
