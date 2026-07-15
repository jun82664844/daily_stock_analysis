# DSA V131 回访用户事件收件箱实施计划

> **For agentic workers:** Use `executing-plans` or an available multi-agent workflow to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让游客和登录用户在再次访问首页时，可以一键只看自上次基线后新增的公开市场事件，并用清晰摘要判断是否有值得继续阅读的新资料。

**Architecture:** V131 只复用 V126-V130 已加载的公共事件、浏览器端有限容量已读 ID 和客户端个性化结果。新增事件模式在 `DailyMarketEventCenterV126` 内完成筛选，不向服务端上传已读状态、自选、筛选偏好或用户标识；V100 私有提醒与后台任务保持不变。

**Tech Stack:** React 19、TypeScript、localStorage、Vitest、Vite、Python verifier、现有 DSA 发布候选门禁与真实浏览器验收。

**Product boundary:** 只提供公开资讯、来源、时间、分类和查询入口，不生成目标价、收益预测、买卖建议、仓位或交易指令。V131 不新增网络请求、AI 调用、API 额度、数据库表或服务端用户追踪。

---

### Task 1: 回访模式测试契约

**Files:**
- Modify: `apps/dsa-web/src/components/market-home/__tests__/DailyMarketEventCenterV126.test.tsx`

- [x] 先写失败测试：存在未读事件时显示双语“只看新增 / New only”入口。
- [x] 先写失败测试：选择“只看新增”只展示未读事件，不改变完整事件集合或本地已读数据。
- [x] 先写失败测试：新增模式受当前市场和类别筛选约束，计数来自完整当前事件集合。
- [x] 先写失败测试：全部标记已读后显示“暂无新增事件”，并可一键返回全部事件。

### Task 2: 双语事件收件箱界面

**Files:**
- Modify: `apps/dsa-web/src/components/market-home/DailyMarketEventCenterV126.tsx`

- [x] 将显示模式扩展为“为我优先 / 只看新增 / 全部事件”，没有自选时不显示个性化入口。
- [x] 增加总事件、新增、重点和自选相关四项摘要；自选相关摘要仅在有自选时显示。
- [x] 新增模式只做显式过滤，默认模式仍不隐藏任何公共事件。
- [x] 新增模式空态明确说明当前没有新增事件，提供返回全部事件按钮。
- [x] 中英文文案完整对应，继续展示来源透明度和“不构成投资建议”提示。

### Task 3: V131 独立门禁

**Files:**
- Create: `scripts/verify_platform_returning_event_inbox_v131.py`
- Create: `tests/test_platform_returning_event_inbox_v131_verifier.py`
- Modify: `.gitignore`
- Modify: `scripts/verify_platform_release_candidate_package.py`
- Modify: `tests/test_platform_release_candidate_package.py`

- [x] 门禁检查新增模式、摘要、双语、游客边界、无网络/AI/服务端追踪和首页包上限。
- [x] 成功时输出 `DSA_PLATFORM_RETURNING_EVENT_INBOX_V131_OK`。
- [x] 发布候选清单覆盖全部 V131 文件，不使用通配暂存或未审查文件。

### Task 4: 文档、自动化与真实浏览器验收

**Files:**
- Modify: `docs/CHANGELOG.md`
- Modify: `docs/superpowers/platform-local-v1-acceptance-status.md`
- Modify: `docs/superpowers/platform-review-slices.md`
- Modify: `docs/superpowers/platform-release-candidate-manifest.md`

- [x] 运行 V126-V131 聚焦回归、前端测试、lint、生产构建和发布包门禁。
- [x] 在 8018 验证中文、英文、游客基线、新增模式、返回全部、来源详情、合规提示和页面运行状态。
- [x] 检查敏感密钥、`git diff --check`、脏树分类与运行态健康。
- [x] 不删除数据库、历史报告或用户数据；未获单独授权不 commit、不 push。

## 实际验收结果

- V131 聚焦前端回归：5 个文件、34 项测试通过；V131 组件自身累计 13 项测试通过。
- 前端完整回归：130 个测试文件通过，1,084 项通过、2 项按配置跳过；使用 `--maxWorkers=4` 控制本机并发，避免全量运行时的资源争用。
- 后端事件、服务、verifier 与发布包相关回归：130 项测试通过；V131/V130/verifier/发布包专项：87 项测试通过。
- `npm run lint` 与 `npm run build` 通过；最新首页包 `HomePage-BdmKTw27.js` 为 482,510 bytes，低于 500,000 bytes 门限。
- V126-V131 六个独立门禁全部通过，V131 输出 `DSA_PLATFORM_RETURNING_EVENT_INBOX_V131_OK`。
- 真实浏览器覆盖中文、英文、只看新增、全部已读空态、返回全部、来源入口、合规提示与榜单操作名称；1280px 视口无横向溢出。
- 发布包门禁覆盖当前 18 个变更项；未删除数据库、历史报告或用户数据，未执行 commit 或 push。
