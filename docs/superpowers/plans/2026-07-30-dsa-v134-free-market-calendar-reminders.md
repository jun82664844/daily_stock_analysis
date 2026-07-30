# DSA V134 免费市场日历与事件提醒中心实施计划

> **For agentic workers:** Use `executing-plans` or an available multi-agent workflow to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在不新增 AI、额外公共网络请求或数据库写入的前提下，把现有 A 股、港股、美股公开事件与 V133 关注事件复盘节点整理为可回访的免费市场日历和站内提醒中心。

**Architecture:** 新增纯前端 `marketEventCalendarV134` 领域模块，把 `PublicMarketEvent`、`FollowedMarketEventV133` 和自选代码转换为有明确时间依据的日历条目。只有来源标题或摘要明确给出日期时才标记为“计划日期”；其余事件标记为“发布时间”，V133 的 1/3/5/20 日节点标记为“复盘节点”。提醒已读状态按 `guest` 或数值平台用户作用域保存在浏览器本地，登录时只迁移当前游客状态。`MarketEventCalendarPanelV134` 负责中英文、筛选、提醒确认和查询跳转，`DailyMarketEventCenterV126` 只负责接线。

**Tech Stack:** React 19、TypeScript、Vitest、Testing Library、浏览器 localStorage、现有 `PublicMarketEvent` / `FollowedMarketEventV133` 类型、Python verifier、Vite、8018 真实浏览器验收。

**Product boundary:** 仅展示公开资讯、来源时间、明确计划日期和关注后的复盘节点；不推断事件导致行情变化，不生成目标价、收益预测、买卖建议、仓位或交易指令。没有明确计划日期的公开资讯不得包装成未来事件。

---

### Task 1: 市场日历领域模型与本地提醒状态

**Files:**
- Create: `apps/dsa-web/src/components/market-home/marketEventCalendarV134.ts`
- Create: `apps/dsa-web/src/components/market-home/__tests__/marketEventCalendarV134.test.ts`

- [x] **Step 1: 写失败测试**

覆盖以下行为：

```ts
expect(extractExplicitScheduleAt(eventWithChineseDate, now)).toBe('2026-08-02T00:00:00.000Z');
expect(buildMarketEventCalendarV134(events, followed, watchlist, now))
  .toEqual(expect.arrayContaining([expect.objectContaining({ dateBasis: 'follow_up_checkpoint' })]));
expect(unseenDueCalendarEntryIds(entries, acknowledged)).toEqual(['checkpoint:event-1:1']);
expect(adoptGuestCalendarAcknowledgements('user-72')).toContain('checkpoint:event-1:1');
```

同时验证：
- 英文月份、ISO 日期和中文月日可解析；非法日期和普通数字不解析。
- 无明确日期的公开事件使用 `published` 时间依据，不显示为未来计划。
- 仅保留最近 7 日和未来 30 日条目，最多 48 条。
- 自选代码必须使用现有规范化逻辑精确匹配，A 股指数与个股不得同号误匹配。
- `guest`、不同 `user-<id>` 相互隔离；损坏 JSON 和禁用存储安全降级。
- 已读 ID 最多 128 条，登录迁移后清空游客作用域。

- [x] **Step 2: 运行测试并确认因模块不存在而失败**

```powershell
cd apps/dsa-web
npm.cmd run test -- --run src/components/market-home/__tests__/marketEventCalendarV134.test.ts
```

- [x] **Step 3: 实现最小领域模型**

核心常量和类型：

```ts
export const MARKET_EVENT_CALENDAR_STORAGE_PREFIX = 'dsa.marketEvents.calendar.v134';
export const MARKET_EVENT_CALENDAR_CHANGED_EVENT = 'dsa:market-event-calendar-v134';
export const CALENDAR_PAST_DAYS = 7;
export const CALENDAR_FUTURE_DAYS = 30;

export type MarketEventCalendarEntryV134 = {
  id: string;
  kind: 'public_event' | 'follow_up';
  dateBasis: 'explicit_schedule' | 'published' | 'follow_up_checkpoint';
  state: 'recent' | 'today' | 'upcoming' | 'due' | 'completed';
  scheduledAt: string;
  market: MarketCode;
  symbol: string | null;
  title: string;
  personalized: boolean;
  sourceStatus: SourceStatus;
  checkpointDays?: 1 | 3 | 5 | 20;
};
```

实现日期提取、时间窗口、复盘节点、个性化匹配、已读状态、游客迁移和容量上限。领域模块不得调用 `fetch`、Axios、AI、通知渠道或数据库。

- [x] **Step 4: 运行测试并确认通过**

```powershell
npm.cmd run test -- --run src/components/market-home/__tests__/marketEventCalendarV134.test.ts
```

### Task 2: 免费市场日历与事件提醒界面

**Files:**
- Create: `apps/dsa-web/src/components/market-home/MarketEventCalendarPanelV134.tsx`
- Create: `apps/dsa-web/src/components/market-home/__tests__/MarketEventCalendarPanelV134.test.tsx`

- [x] **Step 1: 写失败测试**

覆盖：
- 中英文标题、三市场、日期依据、数据来源、新鲜度和“未使用 AI”边界。
- “为我优先”“全部日历”“待复盘”分段模式。
- 计划日期、发布时间和复盘节点使用不同标签。
- 待复盘数量、全部标为已查看、查询证券按钮可用。
- 空日历、缺少证券代码、过期来源均诚实降级。
- 明确显示“事件和行情并列不代表因果关系”及“不构成投资建议”。

- [x] **Step 2: 运行测试并确认组件不存在**

```powershell
npm.cmd run test -- --run src/components/market-home/__tests__/MarketEventCalendarPanelV134.test.tsx
```

- [x] **Step 3: 实现响应式日历面板**

组件接口：

```ts
type Props = {
  language: 'zh' | 'en';
  events: PublicMarketEvent[];
  followedEvents: FollowedMarketEventV133[];
  watchlistSymbols: string[];
  scope: string;
  now?: Date;
  onOpenSymbol: (symbol: string) => void;
};
```

面板使用稳定网格尺寸，移动端不得横向溢出。没有明确计划日期时必须显示“发布时间”，不得使用“即将发生”等误导文案。

- [x] **Step 4: 运行测试并确认通过**

```powershell
npm.cmd run test -- --run src/components/market-home/__tests__/MarketEventCalendarPanelV134.test.tsx
```

### Task 3: 首页事件中心接线

**Files:**
- Modify: `apps/dsa-web/src/components/market-home/DailyMarketEventCenterV126.tsx`
- Modify: `apps/dsa-web/src/components/market-home/__tests__/DailyMarketEventCenterV126.test.tsx`
- Modify: `apps/dsa-web/src/pages/__tests__/HomePage.test.tsx`

- [x] **Step 1: 写失败集成测试**

验证：
- V134 位于事件列表之前，关注 V133 事件后立即生成 1/3/5/20 日复盘节点。
- 登录作用域继续只使用 `user-<numeric-id>`，不把邮箱写入本地键或公共 API。
- 自选相关事件优先展示，查询按钮调用既有 `onOpenSymbol`。
- 取消 V133 关注后，对应未来复盘节点从 V134 消失。

- [x] **Step 2: 运行聚焦测试并确认 V134 尚未接线**

```powershell
npm.cmd run test -- --run src/components/market-home/__tests__/DailyMarketEventCenterV126.test.tsx src/pages/__tests__/HomePage.test.tsx
```

- [x] **Step 3: 完成最小接线**

`DailyMarketEventCenterV126` 把已有 `events`、`followedEvents`、`watchlistSymbols`、`eventFollowUpScope` 和 `onOpenSymbol` 传给 V134。不得新增首页请求，不得把本地提醒状态上传到 `/api/v1/market-workspace/public-home`。

- [x] **Step 4: 运行聚焦测试并确认通过**

```powershell
npm.cmd run test -- --run src/components/market-home/__tests__/DailyMarketEventCenterV126.test.tsx src/pages/__tests__/HomePage.test.tsx
```

### Task 4: V134 门禁、发布包与文档

**Files:**
- Create: `scripts/verify_platform_free_market_calendar_v134.py`
- Create: `tests/test_platform_free_market_calendar_v134_verifier.py`
- Modify: `.gitignore`
- Modify: `scripts/verify_platform_release_candidate_package.py`
- Modify: `tests/test_platform_release_candidate_package.py`
- Modify: `docs/CHANGELOG.md`
- Modify: `docs/superpowers/platform-local-v1-acceptance-status.md`
- Modify: `docs/superpowers/platform-review-slices.md`
- Modify: `docs/superpowers/platform-release-candidate-manifest.md`

- [x] verifier 检查日期依据、三市场、复盘节点、数值用户作用域、容量上限、中英文、非因果和不构成投资建议文案。
- [x] verifier 禁止新增 `fetch`、Axios、AI、邮件、短信、推送和公共 API 上传。
- [x] verifier 运行 V134 聚焦 Vitest，并继续检查首页包小于 500,000 bytes。
- [x] 成功输出 `DSA_PLATFORM_FREE_MARKET_CALENDAR_V134_OK`。
- [x] 发布包清单覆盖全部 V134 文件。

### Task 5: 完整验收和本地提交

**Files:**
- Modify: `docs/superpowers/plans/2026-07-30-dsa-v134-free-market-calendar-reminders.md`

- [x] 运行 V126-V134 verifier、V134 后端 verifier 单测、发布包测试、全量前端测试、lint 和生产构建。
- [x] 在 8018 真实验收游客与登录用户、中英文、三市场、计划日期、发布时间、复盘节点、已读、查询、取消关注、桌面端和移动端。
- [x] 确认浏览器控制台无错误、无横向溢出、`/health` 为 200、敏感令牌扫描 0 命中。
- [x] 运行 `git diff --check`，显式暂存 V134 文件并完成本地提交。
- [x] 不删除数据库、历史报告或用户数据；不推送远程，不创建 PR，不启用真实支付、生产密钥或生产部署。
