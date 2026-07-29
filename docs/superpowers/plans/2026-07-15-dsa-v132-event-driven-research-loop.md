# DSA V132 事件驱动研究闭环实施计划

> **For agentic workers:** Use `executing-plans` or an available multi-agent workflow to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让用户从首页公开市场事件直接进入一张可核验、可继续查询的研究卡，在不使用 AI 和不新增网络请求的前提下理解事件事实、关联证券与最新行情背景。

**Architecture:** 在 `DailyMarketEventCenterV126` 内维护当前研究事件 ID，并把事件与 `PublicMarketHomeV116` 已加载的三地公开榜单证券传给独立组件 `MarketEventResearchPanelV132`。研究卡只做客户端匹配和格式化；找不到关联行情时诚实降级，引导用户进入现有免费个股查询，不新增 API、数据库、用户追踪或后台任务。

**Tech Stack:** React 19、TypeScript、Vitest、Testing Library、Vite、现有 `PublicMarketEvent` / `MarketSecurityItem` 类型、Python verifier、8018 真实浏览器验收。

**Product boundary:** 只提供事件、来源、时间、关联证券和最新可用行情数据。价格与事件同时展示不代表因果关系；不得生成目标价、收益预测、买卖建议、仓位或交易指令。

---

### Task 1: 事件研究入口测试契约

**Files:**
- Modify: `apps/dsa-web/src/components/market-home/__tests__/DailyMarketEventCenterV126.test.tsx`

- [x] 新增失败测试：关联证券事件显示“研究事件 / Research event”入口。
- [x] 新增失败测试：打开研究卡展示事件事实、关联证券、最新价、涨跌、成交量、成交额、行情来源与时间。
- [x] 新增失败测试：研究卡明确说明量价与事件不是因果结论，并继续展示“不构成投资建议”。
- [x] 新增失败测试：点击查询关联证券复用 `onOpenSymbol`，关闭后移除研究卡。
- [x] 新增失败测试：公开榜单没有关联行情时显示诚实降级，不伪造价格或走势。

### Task 2: 独立事件研究卡

**Files:**
- Create: `apps/dsa-web/src/components/market-home/MarketEventResearchPanelV132.tsx`

- [x] 定义 `language`、`event`、`marketItem`、`onOpenSymbol` 和 `onClose` 明确接口。
- [x] 使用现有格式化工具展示事件类别、来源数量、发布时间、行情来源、新鲜度和观测时间。
- [x] 展示关联证券最新价、涨跌幅、成交量和成交额；空值统一显示“暂不可用 / Unavailable”。
- [x] 增加“价格变化与事件同时呈现，不代表事件导致涨跌”的中英文边界。
- [x] 提供查询关联证券与关闭两个明确操作，不增加 AI 或网络调用。

### Task 3: 事件中心与三地公开榜单接线

**Files:**
- Modify: `apps/dsa-web/src/components/market-home/DailyMarketEventCenterV126.tsx`
- Modify: `apps/dsa-web/src/components/market-home/PublicMarketHomeV116.tsx`

- [x] 在事件中心增加研究卡展开状态，研究入口只对具有关联证券的事件显示。
- [x] 使用规范化证券代码匹配三地榜单，兼容 A 股后缀、港股和美股代码。
- [x] 从所有市场的活跃榜、涨幅榜、跌幅榜和关注列表去重汇总候选证券，而不是只读取当前市场页签。
- [x] 研究卡展开、关闭、查询和现有来源详情互不干扰。

### Task 4: V132 独立门禁与发布包

**Files:**
- Create: `scripts/verify_platform_event_driven_research_v132.py`
- Create: `tests/test_platform_event_driven_research_v132_verifier.py`
- Modify: `.gitignore`
- Modify: `scripts/verify_platform_release_candidate_package.py`
- Modify: `tests/test_platform_release_candidate_package.py`

- [x] verifier 检查双语研究入口、行情字段、因果边界、无 AI/网络/追踪和降级状态。
- [x] verifier 检查 V132 聚焦测试与首页包 500,000 bytes 上限。
- [x] 成功时输出 `DSA_PLATFORM_EVENT_DRIVEN_RESEARCH_V132_OK`。
- [x] 发布候选清单覆盖全部 V132 文件。

### Task 5: 文档与完整验收

**Files:**
- Modify: `docs/CHANGELOG.md`
- Modify: `docs/superpowers/platform-local-v1-acceptance-status.md`
- Modify: `docs/superpowers/platform-review-slices.md`
- Modify: `docs/superpowers/platform-release-candidate-manifest.md`

- [x] 运行 V126-V132 verifier、前端聚焦/完整测试、lint、生产构建和发布包门禁。
- [x] 在 8018 验证中文、英文、港股现场关联事件、行情不可用降级、查询和关闭；A 股/港股/美股代码规范化及行情可用路径由自动化测试覆盖。
- [x] 检查 `/health`、敏感密钥、`git diff --check`、页面横向溢出和脏树分类。
- [x] 不删除数据库、历史报告或用户数据；不 push；完成前保留可审查变更清单。

## 验收记录（2026-07-15）

- 前端聚焦测试：5 个文件、101 项通过；全量前端：130 个文件、1086 项通过、2 项按既有配置跳过。
- 后端事件服务、V126-V132 verifier 与发布包：122 项通过；七个阶段 verifier 均输出正式 OK 标记。
- 生产构建通过；`HomePage-BobqX_8W.js` 为 482,850 bytes，低于 500,000 bytes 门限。
- 8018 中文/英文浏览器验收通过；现场港股事件可展开研究卡，缺少榜单行情时诚实降级，查询后进入 `02665.HK` 个股页并取得公开行情。
- 浏览器控制台无报错，桌面页面无横向溢出；研究卡明确标注无 AI、非因果关系和不构成投资建议。
