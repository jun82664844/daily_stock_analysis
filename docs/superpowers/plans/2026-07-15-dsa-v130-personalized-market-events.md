# DSA V130 自选关联市场事件实施计划

> **For agentic workers:** Use `executing-plans` or an available multi-agent workflow to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在不新增网络请求、AI 调用或服务端用户追踪的前提下，让登录用户优先看到与自选股、相关行业和关注市场有关的公开事件，同时保留完整公共事件流和游客体验。

**Architecture:** 后端只为事件补充从当前市场快照中已经存在的可选 `sector` 字段；前端根据已加载的用户自选代码和公共首页证券数据，在浏览器内推导自选行业与关注市场。个性化排序严格发生在客户端，公共首页接口不接收用户标识或自选数据。默认“为我优先”只调整排序，不隐藏其他公开事件；用户可切换回“全部事件”。

**Product boundary:** 只提供公开资讯、数据来源、关联依据和查询入口，不输出买卖建议、目标价、收益预测或交易指令。

---

### Task 1: 后端事件行业契约

**Files:**
- Modify: `tests/test_public_market_event_service.py`
- Modify: `src/services/public_market_event_service.py`
- Modify: `api/v1/schemas/market_workspace.py`
- Modify: `tests/test_public_market_home_v116.py`

- [x] 先写失败测试，要求事件在匹配证券时保留已有 `sector`，未匹配时保持空值。
- [x] 实现可选行业字段，不新增数据源或网络调用。
- [x] 验证旧缓存缺失 `sector` 时仍兼容。

### Task 2: 前端个性化排序模型

**Files:**
- Create: `apps/dsa-web/src/components/market-home/marketEventPersonalizationV130.ts`
- Create: `apps/dsa-web/src/components/market-home/__tests__/marketEventPersonalizationV130.test.ts`
- Modify: `apps/dsa-web/src/api/marketWorkspace.ts`

- [x] 先写失败测试，覆盖自选股、相关行业、关注市场和普通事件四级排序。
- [x] 统一 A 股、港股和美股代码归一化，避免代码格式差异导致漏匹配。
- [x] 保持稳定排序，相关性分数和时间继续作为同级排序依据。

### Task 3: 双语“为我优先”界面

**Files:**
- Modify: `apps/dsa-web/src/components/market-home/DailyMarketEventCenterV126.tsx`
- Modify: `apps/dsa-web/src/components/market-home/PublicMarketHomeV116.tsx`
- Modify: `apps/dsa-web/src/components/market-home/__tests__/DailyMarketEventCenterV126.test.tsx`
- Modify: `apps/dsa-web/src/components/market-home/__tests__/PublicMarketHomeV116.test.tsx`

- [x] 登录且有自选时默认启用“为我优先”，显示匹配数量和排序依据。
- [x] 支持切换“全部事件”，只改变排序，不隐藏公开事件。
- [x] 事件显示“自选相关 / 相关行业 / 关注市场”解释标签；游客不显示个性化控件。
- [x] 中英文文案完整对应，并保留“不构成投资建议”提示。

### Task 4: V130 门禁与交付记录

**Files:**
- Create: `scripts/verify_platform_personalized_market_events_v130.py`
- Create: `tests/test_platform_personalized_market_events_v130_verifier.py`
- Modify: `.gitignore`
- Modify: `scripts/verify_platform_release_candidate_package.py`
- Modify: `tests/test_platform_release_candidate_package.py`
- Modify: `docs/CHANGELOG.md`
- Modify: `docs/superpowers/platform-local-v1-acceptance-status.md`
- Modify: `docs/superpowers/platform-review-slices.md`
- Modify: `docs/superpowers/platform-release-candidate-manifest.md`

- [x] 门禁覆盖客户端个性化、行业字段兼容、游客边界、双语文案、无新增 AI/网络请求和首页 bundle 上限。
- [x] 成功时输出 `DSA_PLATFORM_PERSONALIZED_MARKET_EVENTS_V130_OK`。
- [x] 发布包完整覆盖本阶段 dirty 文件。

### Task 5: 自动化与真实浏览器验收

- [x] 运行聚焦后端、前端测试及 V126-V130 回归。
- [x] 运行 lint、生产构建、V130 verifier、发布包和 `git diff --check`。
- [x] 重启 8018 后，在中文、英文、游客和登录用户场景验证排序、标签、切换、来源详情、无横向溢出及控制台无错误。
- [x] 不删除数据库、历史报告或用户数据；未经单独授权不 push。

## 验收证据

- 后端 V126-V130 聚焦回归：46 tests passed。
- 前端聚焦回归：4 files / 27 tests passed；ESLint 0 errors / 0 warnings；production build passed。
- 发布包与 verifier 测试：98 tests passed；24 个 dirty 文件全部归入 review slices。
- V126、V127、V128、V129、V130 独立门禁全部通过；V130 输出 `DSA_PLATFORM_PERSONALIZED_MARKET_EVENTS_V130_OK`。
- 首页主包 `HomePage-B0QlnVSu.js` 为 482,590 bytes，低于 500,000 bytes 门限。
- 8018 已使用项目虚拟环境重启，`/health` 返回 200。
- 真实浏览器：登录测试账号加入 AAPL 后，“为我优先”将美股关注事件排在普通事件前；“全部事件”恢复相关度排序；中英文、来源展开、合规提示、游客隐藏个性化控件均通过；页面无横向溢出，控制台无错误或警告。
- 浏览器验收只为现有本地测试账号增加 AAPL 自选并执行退出；没有删除数据库、历史报告或任何用户记录，没有 commit 或 push。
