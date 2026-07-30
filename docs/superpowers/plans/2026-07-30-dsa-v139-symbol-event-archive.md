# DSA V139 个股事件档案 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use executing-plans to implement this plan task-by-task.

**Goal:** 在公开个股工作区增加无需登录、无需 AI/API 的事件档案，按 6/12/24 个月展示真实可追溯事件及事件后 1/3/5/20 个交易日的客观价格观察。

**Architecture:** 新增独立的 `PublicSymbolEventArchiveService`，复用 V138 的公开事件日历和事件后行情观察服务。后端只接受受支持的 A 股、港股、美股代码，按单只证券加载并限制事件数量；前端在个股工作区异步加载档案，失败时不阻塞基础行情。

**Tech Stack:** FastAPI、Pydantic、Python unittest、React、TypeScript、Vitest、Playwright。

---

## Task 1: 锁定后端数据契约

**Files:**
- Create: `tests/test_public_symbol_event_archive_v139.py`
- Modify: `api/v1/schemas/market_workspace.py`

- [x] 先写服务与 API 失败测试。
- [x] 覆盖精确证券过滤、6/12/24 月边界、安全来源链接、缺失观察值和匿名限流。
- [x] 运行测试并确认因 V139 尚未实现而失败。

## Task 2: 实现个股事件档案服务和 API

**Files:**
- Create: `src/services/public_symbol_event_archive_service.py`
- Modify: `src/services/public_market_event_reaction_service.py`
- Modify: `src/services/public_market_calendar_service.py`
- Modify: `api/v1/endpoints/market_workspace.py`
- Modify: `.env.example`
- Modify: `docs/superpowers/platform-production-env.example`

- [x] 复用公开事件日历加载单只证券的定期披露、分红和拆股事件。
- [x] 复用行情观察逻辑生成 1/3/5/20 个交易日的证券、基准及相对变化。
- [x] 允许 24 个月有界回看，同时限制响应条数、超时和下载体积。
- [x] 暴露来源、来源时间、新鲜度和警告，不把不可用值伪装为零。
- [x] API 保持匿名访问、独立限流、`ai_used=false`。

## Task 3: 实现中英文档案视图

**Files:**
- Create: `apps/dsa-web/src/components/market-workspace/SymbolEventArchiveV139.tsx`
- Create: `apps/dsa-web/src/components/market-workspace/SymbolEventArchiveV139.test.tsx`
- Modify: `apps/dsa-web/src/api/marketWorkspace.ts`
- Modify: `apps/dsa-web/src/pages/MarketWorkspacePage.tsx`
- Modify: `apps/dsa-web/src/pages/__tests__/MarketWorkspacePage.test.tsx`

- [x] 独立异步加载，不阻塞个股行情。
- [x] 提供 6/12/24 月、事件类型和 1/3/5/20 日观察筛选。
- [x] 展示事件时间、来源链接、数据新鲜度和缺失状态。
- [x] 中英文完整切换。
- [x] 明确提示“同期变化不代表事件导致价格变化”，只提供资讯和数据。

## Task 4: 增加 V139 验收门禁和发布文档

**Files:**
- Create: `scripts/verify_platform_symbol_event_archive_v139.py`
- Create: `tests/test_platform_symbol_event_archive_v139_verifier.py`
- Modify: `.gitignore`
- Modify: `scripts/verify_platform_release_candidate_package.py`
- Modify: `docs/superpowers/platform-release-candidate-manifest.md`
- Modify: `docs/superpowers/platform-local-v1-acceptance-status.md`
- Modify: `docs/superpowers/platform-product-rules.md`
- Modify: `docs/CHANGELOG.md`

- [x] verifier 检查契约、游客访问、无 AI、三市场样例和免责声明。
- [x] 发布清单覆盖所有新增/修改文件。
- [x] 文档明确当前事件类型与数据源能力，不宣称未接入的数据。

## Task 5: 全量验收、浏览器验证和本地收口

- [x] 运行 V139 后端、前端测试和构建。
- [x] 运行 V126-V139 相关门禁、发布包门禁及安全扫描。
- [x] 重启 8018，浏览器验收 A 股、港股、美股及中英文、桌面/移动布局。
- [x] 检查控制台、请求状态、横向溢出和来源链接。
- [x] 显式暂存本阶段文件，本地提交并确认 Git 干净；不推送。

## Final Verification Evidence

- 后端 V139 聚焦套件：38 tests OK；V139 verifier 输出 `DSA_PLATFORM_SYMBOL_EVENT_ARCHIVE_V139_OK`。
- 前端全量 Vitest：137 files passed，1135 passed，2 skipped；V139 聚焦前端：2 files / 12 tests passed。
- `npm run build` 通过；发布包、Local V1 operability 和 V2 readiness 门禁通过。
- 真实浏览器覆盖 `300750`、`HK09988`、`NVDA`，并验证规范化为 `300750.SZ`、`9988.HK`、`NVDA`。
- A 股、港股、美股分别取得 2、3、4 条公开事件；来源链接、1/3/5/20 日观察和非因果说明可见。
- 中文、英文及 `390x844` 手机视口通过；手机页面无横向溢出，最终控制台 error 为 0。
- 本地提交后确认 Git 工作树干净；未推送。

## Acceptance Boundaries

- 页面只提供公开资讯和客观数据，不提供投资建议、交易指令、目标价或收益预测。
- “事件后变化”仅表示时间窗口内的市场数据观察，不表示事件导致价格变化。
- 不使用真实 API Key，不接真实支付或生产服务，不删除历史报告、数据库或用户数据。
- 不可用的数据必须降级展示，不得伪造为成功或零值。
