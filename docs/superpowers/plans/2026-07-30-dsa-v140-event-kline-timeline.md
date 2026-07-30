# DSA V140 事件与 K 线联动图 Implementation Plan

> **For agentic workers:** Use `executing-plans` or an available multi-agent workflow to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 V139 个股事件档案中增加游客可用的历史行情联动图，把可追溯事件、个股与市场基准的同期变化放在同一时间轴上，只展示公开历史数据，不使用 AI，不形成因果判断或投资建议。

**Architecture:** 继续使用 V139 的单证券事件档案接口，不新增平行数据源或第二次前端请求。`PublicMarketEventReactionService` 暴露有界历史图表上下文，`PublicSymbolEventArchiveService` 将最多两年的个股、市场基准和标准化变化合并进现有响应；前端新增独立图表组件，由 V139 的时间与事件筛选状态驱动，图表不可用时不阻塞事件列表和基础行情。

**Tech Stack:** FastAPI、Pydantic、Python unittest、React、TypeScript、Recharts、Vitest、Playwright。

---

## Task 1: 锁定历史图表数据契约

**Files:**
- Create: `tests/test_public_symbol_event_timeline_v140.py`
- Modify: `api/v1/schemas/market_workspace.py`

- [x] 写失败测试，要求历史服务按 A 股、港股、美股代码加载个股与对应基准，最多返回 560 个日线点。
- [x] 覆盖 6/12/24 个月裁剪、个股与基准标准化变化、相对变化、成交量、缺失基准和无行情降级。
- [x] 覆盖档案响应新增 `chart`，并继续强制 `ai_used=false`、`informational_only=true`、`causality_disclaimer=true`。
- [x] 运行 `python -m unittest tests.test_public_symbol_event_timeline_v140`，确认因图表契约尚未实现而失败。

## Task 2: 实现有界历史图表上下文

**Files:**
- Modify: `src/services/public_market_event_reaction_service.py`
- Modify: `src/services/public_symbol_event_archive_service.py`
- Modify: `api/v1/schemas/market_workspace.py`

- [x] 在既有事件行情服务中新增 `load_price_chart(market, symbol, days, max_points)`，复用历史缓存、超时和 Yahoo 公开行情边界。
- [x] 使用个股历史交易日作为时间轴；市场基准只在同一日期存在时展示，不前填或伪造数据。
- [x] 以所选区间各自首个有效收盘为零点，生成个股、基准和相对变化百分比。
- [x] 保留原始收盘、成交量、来源状态和警告；个股历史不可用时返回空点和 `unavailable`。
- [x] 档案服务复用该方法并把图表加入响应；图表失败只增加降级警告，不清空事件档案。
- [x] 运行 V140、V139、V138 和 V136 后端套件，确认新增字段保持向后兼容。

## Task 3: 实现中英文事件联动图

**Files:**
- Create: `apps/dsa-web/src/components/market-workspace/SymbolEventTimelineV140.tsx`
- Create: `apps/dsa-web/src/components/market-workspace/SymbolEventTimelineV140.test.tsx`
- Modify: `apps/dsa-web/src/api/marketWorkspace.ts`
- Modify: `apps/dsa-web/src/components/market-workspace/SymbolEventArchiveV139.tsx`
- Modify: `apps/dsa-web/src/components/market-workspace/SymbolEventArchiveV139.test.tsx`

- [x] 写失败测试，要求图表显示个股与市场基准标准化曲线、来源状态、事件标记和非因果声明。
- [x] 用事件按钮选择财报、分红或拆股；选中事件后高亮基准日到当前 1/3/5/20 日观察窗口。
- [x] V139 的 6/12/24 月、事件类型和观察窗口状态同时驱动图表与事件列表。
- [x] 图表点为空、基准缺失或事件没有可用观察时显示明确降级，不把缺失值变为零。
- [x] 中文模式不混入平台英文状态词；英文模式不混入平台中文状态词，外部专名保持来源原文。
- [x] 固定图表容器高度和响应式宽度，保证桌面与 390 像素手机视口无横向溢出。

## Task 4: 增加 V140 验收门禁和交付文档

**Files:**
- Create: `scripts/verify_platform_event_kline_timeline_v140.py`
- Create: `tests/test_platform_event_kline_timeline_v140_verifier.py`
- Modify: `.gitignore`
- Modify: `scripts/verify_platform_release_candidate_package.py`
- Modify: `tests/test_platform_release_candidate_package.py`
- Modify: `docs/CHANGELOG.md`
- Modify: `docs/superpowers/platform-product-rules.md`
- Modify: `docs/superpowers/platform-local-v1-acceptance-status.md`
- Modify: `docs/superpowers/platform-review-slices.md`
- Modify: `docs/superpowers/platform-release-candidate-manifest.md`

- [x] verifier 检查有界历史、三市场基准、标准化时间轴、中英文、游客免 AI 和非因果边界。
- [x] 发布包门禁显式收录全部 V140 新增及修改文件。
- [x] 文档明确图表是历史同期数据，不是 Kronos 预测、收益预测、影响评级或投资建议。

## Task 5: 全量回归、浏览器验收和本地收口

- [x] 运行 V140 聚焦后端、前端测试、ESLint、全量 Vitest 和生产构建。
- [x] 运行 V136-V140、发布候选包、Local V1 operability 和 V2 readiness 门禁。
- [x] 重启 8018，真实浏览器验收 A 股、港股、美股的 6/12/24 月图表、事件选择和 1/3/5/20 日联动。
- [x] 验收中文、英文、桌面和 `390x844` 手机视口，确认控制台 error 为零且无横向溢出。
- [x] 执行差异空白和密钥扫描，显式暂存 V140 文件，本地提交并确认 Git 工作树干净；不推送。

## Acceptance Boundaries

- 图表只展示公开历史行情与公开事件，不调用平台模型、BYOK、Ollama 或 Kronos。
- 事件标记与价格曲线同时出现不表示事件导致价格变化。
- 不生成买卖建议、交易指令、目标价、仓位、影响评级、收益预测或收益承诺。
- 来源失败、基准缺失或数据不足必须明确降级，不伪造日期、价格、百分比或来源。
- 不修改历史报告、数据库、用户账户、支付状态或生产环境，不接入真实 API Key。
