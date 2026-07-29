# DSA V133 市场事件后续追踪实施计划

> **For agentic workers:** Use `executing-plans` or an available multi-agent workflow to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** 让免费用户关注公开市场事件，并在后续访问时查看来源可追溯的新事件、公开行情观测变化和 1/3/5/20 日检查点，从而形成无需 AI 或额外网络请求的回访闭环。

**Architecture:** 新增纯前端 `marketEventFollowUpV133` 存储与计算模块，把事件事实、关注时公开行情基线和后续访问时的公开行情快照保存在浏览器本地；数据按 `guest` 或平台用户 ID 作用域隔离，登录时只把当前游客关注迁入当前用户。`DailyMarketEventCenterV126` 负责接线，独立 `MarketEventFollowUpPanelV133` 负责展示；所有行情和后续事件均复用 `PublicMarketHomeV116` 已加载数据。

**Tech Stack:** React 19、TypeScript、Vitest、Testing Library、浏览器 localStorage、现有 `PublicMarketEvent` / `MarketSecurityItem` 类型、Python verifier、Vite、8018 真实浏览器验收。

**Product boundary:** 仅展示公开事件、来源、行情观测和同期变化；关注时行情不是事件发生时价格，检查点以“开始关注时间”为基准。事件与价格同时展示不代表因果关系，不生成目标价、收益预测、买卖建议、仓位或交易指令。

---

### Task 1: 本地关注和观测计算

**Files:**
- Create: `apps/dsa-web/src/components/market-home/marketEventFollowUpV133.ts`
- Create: `apps/dsa-web/src/components/market-home/__tests__/marketEventFollowUpV133.test.ts`

- [x] **Step 1: 写失败测试**

```ts
expect(followMarketEvent(event, quote, 'guest', clock)).toHaveLength(1);
expect(loadFollowedMarketEvents('guest')[0].baseline?.price).toBe(100);
expect(adoptGuestFollowedMarketEvents('user-72')).toHaveLength(1);
expect(loadFollowedMarketEvents('guest')).toEqual([]);
expect(buildFollowUpCheckpoints(item, now)[0].state).toBe('observed');
```

- [x] **Step 2: 运行测试并确认因模块不存在而失败**

```powershell
cd apps/dsa-web
npm.cmd run test -- --run src/components/market-home/__tests__/marketEventFollowUpV133.test.ts
```

- [x] **Step 3: 实现最小存储契约**

```ts
export const MARKET_EVENT_FOLLOW_UP_STORAGE_PREFIX = 'dsa.marketEvents.followUp.v133';
export const MARKET_EVENT_FOLLOW_UP_CHANGED_EVENT = 'dsa:market-event-follow-up-v133';
export const FOLLOW_UP_HORIZON_DAYS = [1, 3, 5, 20] as const;
```

实现以下行为：

- 最多保存 12 个关注事件，每项最多 32 条观测。
- 存储事件 ID、证券代码、市场、标题、事件时间、发布方、关注时间和公开行情观测。
- 证券代码使用现有规范化规则，A 股指数和个股不得同号误配。
- 同一 UTC 日期重复观测时更新当日记录，不无限追加。
- 损坏 JSON、浏览器禁用存储、空值或非法字段均安全降级。
- 登录迁移只从 `guest` 移入当前 `user-<id>`，迁移后清空游客作用域。

- [x] **Step 4: 运行测试并确认通过**

```powershell
npm.cmd run test -- --run src/components/market-home/__tests__/marketEventFollowUpV133.test.ts
```

### Task 2: 后续追踪面板

**Files:**
- Create: `apps/dsa-web/src/components/market-home/MarketEventFollowUpPanelV133.tsx`
- Create: `apps/dsa-web/src/components/market-home/__tests__/MarketEventFollowUpPanelV133.test.tsx`

- [x] **Step 1: 写失败测试**

覆盖：

- 中英文标题、公开数据和“未使用 AI”边界。
- 展示事件事实、关注时间、关注时基线、最新公开行情与相对变化。
- 展示 1/3/5/20 日检查点的“待观察 / 已观察 / 暂无观测”真实状态。
- 展示同证券且晚于原事件的后续公开事件，排除其他证券和更早事件。
- 行情缺失、部分字段缺失、过期来源均诚实降级。
- 查询证券和停止关注按钮可用。
- 明确说明关注时价格不是事件发生时价格，变化不代表因果关系。

- [x] **Step 2: 运行测试并确认组件不存在**

```powershell
npm.cmd run test -- --run src/components/market-home/__tests__/MarketEventFollowUpPanelV133.test.tsx
```

- [x] **Step 3: 实现独立面板**

面板接收：

```ts
type Props = {
  language: 'zh' | 'en';
  followedEvents: FollowedMarketEventV133[];
  publicEvents: PublicMarketEvent[];
  now?: Date;
  onOpenSymbol: (symbol: string) => void;
  onRemove: (eventId: string) => void;
};
```

面板只格式化与比较已传入数据，不发请求、不调用 AI、不写数据库。

- [x] **Step 4: 运行测试并确认通过**

```powershell
npm.cmd run test -- --run src/components/market-home/__tests__/MarketEventFollowUpPanelV133.test.tsx
```

### Task 3: 事件研究卡和首页接线

**Files:**
- Modify: `apps/dsa-web/src/components/market-home/MarketEventResearchPanelV132.tsx`
- Modify: `apps/dsa-web/src/components/market-home/DailyMarketEventCenterV126.tsx`
- Modify: `apps/dsa-web/src/components/market-home/PublicMarketHomeV116.tsx`
- Modify: `apps/dsa-web/src/pages/HomePage.tsx`
- Modify: `apps/dsa-web/src/components/market-home/__tests__/DailyMarketEventCenterV126.test.tsx`
- Modify: `apps/dsa-web/src/pages/__tests__/HomePage.test.tsx`

- [x] **Step 1: 写失败测试**

覆盖：

- 研究卡出现“关注后续 / Following”按钮并可取消。
- 关注后追踪面板立即出现，刷新组件后仍从本地恢复。
- 新公开行情写入后续观测，同一天不重复膨胀。
- `guest` 与不同 `user-<id>` 互相隔离。
- HomePage 只传数值用户 ID 作用域，不传邮箱，不把关注事件上传公共首页 API。

- [x] **Step 2: 运行聚焦测试并确认失败原因是 V133 尚未接线**

```powershell
npm.cmd run test -- --run src/components/market-home/__tests__/DailyMarketEventCenterV126.test.tsx src/pages/__tests__/HomePage.test.tsx
```

- [x] **Step 3: 完成接线**

- `HomePage` 传入 `eventFollowUpScope={platformSession ? \`user-${platformSession.user.id}\` : 'guest'}`。
- `PublicMarketHomeV116` 透传作用域，不把作用域或关注数据加入公共 API 参数。
- `DailyMarketEventCenterV126` 加载、迁移、关注、取消和记录公开行情观测。
- `MarketEventResearchPanelV132` 只通过回调切换关注状态。
- 关注列表为空时不渲染空面板，不挤占首页首屏。

- [x] **Step 4: 运行聚焦测试并确认通过**

```powershell
npm.cmd run test -- --run src/components/market-home/__tests__/DailyMarketEventCenterV126.test.tsx src/pages/__tests__/HomePage.test.tsx
```

### Task 4: V133 门禁和文档

**Files:**
- Create: `scripts/verify_platform_market_event_follow_up_v133.py`
- Create: `tests/test_platform_market_event_follow_up_v133_verifier.py`
- Modify: `.gitignore`
- Modify: `scripts/verify_platform_release_candidate_package.py`
- Modify: `tests/test_platform_release_candidate_package.py`
- Modify: `docs/CHANGELOG.md`
- Modify: `docs/superpowers/platform-local-v1-acceptance-status.md`
- Modify: `docs/superpowers/platform-review-slices.md`
- Modify: `docs/superpowers/platform-release-candidate-manifest.md`

- [x] verifier 检查本地作用域隔离、游客迁移、容量上限、检查点、双语、非因果和无网络/AI/用户上传。
- [x] verifier 实际运行 V133 聚焦 Vitest，并继续检查首页包不超过 500,000 bytes。
- [x] 成功输出 `DSA_PLATFORM_MARKET_EVENT_FOLLOW_UP_V133_OK`。
- [x] 发布包清单覆盖全部 V133 文件。

### Task 5: 完整验收和本地提交

**Files:**
- Modify: `docs/superpowers/plans/2026-07-29-dsa-v133-market-event-follow-up.md`

- [x] 运行 V126-V133 verifier、聚焦与全量前端测试、lint、生产构建和发布包门禁。
- [x] 在 8018 验收中文、英文、关注、刷新恢复、取消、查询、桌面和移动端。
- [x] 确认控制台无错误、无横向溢出、`/health` 正常、敏感信息扫描 0 命中。
- [x] 运行 `git diff --check`，显式暂存 V133 文件并完成本地提交。
- [x] 不删除数据库、历史报告或用户数据；不推送远程，不创建 PR，不触碰真实支付、密钥或生产环境。
