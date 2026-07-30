# DSA V141 同类事件历史对比研究台 Implementation Plan

> **For agentic workers:** Use `executing-plans` or an available multi-agent workflow to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 V139/V140 个股事件档案中增加游客可用的同类事件历史统计与联动复盘，让用户比较同一证券过去同类事件后的客观价格分布，而不使用 AI、不形成因果结论或投资建议。

**Architecture:** 继续扩展 V139 的单证券事件档案响应，不增加前端第二次请求或新外部数据源。后端基于已经取得的最多 24 个事件及其 1/3/5/20 日观察窗口生成有界统计；前端新增独立 V141 研究台，并把事件选择状态提升到 V139 父组件，使 V141 的历史样本选择与 V140 曲线、观察窗口保持同步。

**Tech Stack:** FastAPI、Pydantic、Python `statistics`、Python unittest、React、TypeScript、Recharts、Vitest、Playwright。

---

## Task 1: 锁定同类事件统计契约

**Files:**
- Create: `tests/test_public_symbol_event_comparison_v141.py`
- Modify: `api/v1/schemas/market_workspace.py`

- [x] 写失败测试，要求档案响应新增 `comparison_summaries`，按财报、分红、拆股、回购和重要公告分别聚合。
- [x] 每个事件类型返回事件总数、有可用观察的事件数，以及 1/3/5/20 日四组统计。
- [x] 每个窗口分别返回个股、基准和相对变化样本数；个股返回中位数、最低、最高、正/负/持平样本数和完整度。
- [x] 缺失基准或相对变化时保持 `None` 与零样本数，不把缺失值伪装成 0%。
- [x] 继续断言 `ai_used=false`、`informational_only=true`、`causality_disclaimer=true`。
- [x] 运行 `python -m unittest tests.test_public_symbol_event_comparison_v141`，确认因契约尚未实现而失败。

## Task 2: 在单一档案响应内生成统计

**Files:**
- Modify: `src/services/public_symbol_event_archive_service.py`
- Modify: `api/v1/schemas/market_workspace.py`
- Modify: `tests/test_public_symbol_event_archive_v139.py`
- Modify: `tests/test_public_symbol_event_timeline_v140.py`

- [x] 使用固定事件类型顺序和固定 1/3/5/20 日窗口，不接受客户端自定义无限分组。
- [x] 只统计 `status=available` 且数值有效的观察，布尔值、非有限数和缺失字段不得进入样本。
- [x] 使用中位数降低极端值影响，所有百分比按现有接口精度四舍五入。
- [x] 完整度按“该窗口个股有效样本数 / 同类事件总数”计算，统计只来自当前 6/12/24 月有界档案。
- [x] 统计生成失败时只返回空数组并增加降级警告，不清空事件、曲线或基础行情。
- [x] 运行 V141、V140、V139、V138 和 V136 后端回归，确认单接口和旧字段兼容。

## Task 3: 实现中英文同类事件研究台与曲线联动

**Files:**
- Create: `apps/dsa-web/src/components/market-workspace/SymbolEventComparisonV141.tsx`
- Create: `apps/dsa-web/src/components/market-workspace/SymbolEventComparisonV141.test.tsx`
- Modify: `apps/dsa-web/src/api/marketWorkspace.ts`
- Modify: `apps/dsa-web/src/components/market-workspace/SymbolEventArchiveV139.tsx`
- Modify: `apps/dsa-web/src/components/market-workspace/SymbolEventArchiveV139.test.tsx`
- Modify: `apps/dsa-web/src/components/market-workspace/SymbolEventTimelineV140.tsx`
- Modify: `apps/dsa-web/src/components/market-workspace/SymbolEventTimelineV140.test.tsx`
- Modify: `apps/dsa-web/src/pages/__tests__/MarketWorkspacePage.test.tsx`

- [x] 先写失败测试，要求 V141 显示同类事件数、有效样本数、当前观察窗口的中位数、区间、正负分布、相对基准中位数和完整度。
- [x] 样本少于 3 个时显示“样本有限”，无可用观察时显示明确空状态，不渲染 0% 假值。
- [x] 历史样本按钮按事件日期展示当前窗口变化；点击后同步 V140 的事件高亮、曲线观察区间和数值。
- [x] V139 的月份、事件类型和 1/3/5/20 日状态同时驱动 V140 与 V141；切换筛选后不保留已不可见事件的错误选择。
- [x] 中文模式不混入平台英文状态词，英文模式不混入平台中文状态词；市场和公司外部专名按 V140 既有规则展示。
- [x] 采用稳定的响应式网格和有界样本列表，桌面及 `390x844` 手机视口不得出现横向溢出或动态布局跳动。
- [x] 页面持续显示“历史分布不代表未来表现、相关变化不表示因果、不构成投资建议”。

## Task 4: 增加 V141 门禁和发布包覆盖

**Files:**
- Create: `scripts/verify_platform_symbol_event_comparison_v141.py`
- Create: `tests/test_platform_symbol_event_comparison_v141_verifier.py`
- Modify: `.gitignore`
- Modify: `scripts/verify_platform_release_candidate_package.py`
- Modify: `tests/test_platform_release_candidate_package.py`
- Modify: `docs/CHANGELOG.md`
- Modify: `docs/superpowers/platform-product-rules.md`
- Modify: `docs/superpowers/platform-local-v1-acceptance-status.md`
- Modify: `docs/superpowers/platform-review-slices.md`
- Modify: `docs/superpowers/platform-release-candidate-manifest.md`

- [x] verifier 检查有界同类统计、三种样本数、缺失不补零、单接口、中英文联动、游客免 AI 和非建议边界。
- [x] 发布包门禁显式收录全部 V141 新增及修改文件，verifier 不得被 `.gitignore` 隐藏。
- [x] 文档明确 V141 是描述性历史统计，不是胜率承诺、收益预测、事件影响评级、目标价或交易指令。

## Task 5: 回归、真实浏览器验收和 Git 收口

- [x] 运行 V141 聚焦后端、前端测试、ESLint、全量 Vitest 和生产构建。
- [x] 运行 V136-V141、发布候选包、Local V1 operability 和 V2 readiness 门禁。
- [x] 重启 8018，真实浏览器验收 AAPL、`0700.HK` 和 `600519.SH` 的月份、事件类型、1/3/5/20 日与 V140/V141 双向联动。
- [x] 验收中文、英文、桌面和 `390x844` 手机视口，确认控制台 error 为 0 且无横向溢出。
- [x] 执行差异空白与密钥扫描，显式暂存 V141 文件，本地提交并确认 Git 工作树干净；不自动推送 V141。

## Acceptance Boundaries

- V141 只处理 V139 已取得的公开事件和 V136/V140 已取得的公开历史行情，不新增外部抓取或模型调用。
- 统计是描述性历史分布；样本数量、完整度、缺失基准和来源状态必须可见。
- 不生成买卖建议、交易指令、目标价、仓位、事件影响评级、收益预测、胜率承诺或收益承诺。
- 不修改历史报告、数据库、用户账户、支付状态或生产环境，不读取或接入真实 API Key。
