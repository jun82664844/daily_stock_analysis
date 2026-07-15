# DSA V129 事件来源对照与证据详情实施计划

> **For agentic workers:** Use `executing-plans` or an available multi-agent workflow to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在不增加网络请求、AI 调用或服务端用户追踪的前提下，让免费市场事件中心保留并展示去重后的公开来源明细，帮助用户核对发布方、时间和原文链接。

**Architecture:** 后端继续复用 `PublicMarketEventService` 的同标题合并逻辑，为每条事件保留最多 8 条轻量来源记录，同时继续用 `source_count` 表示最多 20 条去重来源总数。API 对旧缓存保持兼容；前端默认折叠来源详情，仅在用户点击时展示安全的 HTTP/HTTPS 原文链接。来源数量和来源对照只表示公开记录聚合，不表示事实已被独立证实。

**Tech Stack:** Python 3.12、FastAPI/Pydantic、React 19、TypeScript、unittest、Vitest、Vite、现有 DSA verifier 与真实浏览器验收工具。

---

### Task 1: 后端来源记录保留

**Files:**
- Modify: `tests/test_public_market_event_service.py`
- Modify: `src/services/public_market_event_service.py`

- [x] **Step 1: Write failing source-record tests**

断言同标题事件被多个来源收录时，除了 `source_count` 和 `source_publishers`，还返回去重后的 `source_records`。记录只包含发布方、来源代码、事件时间、时间类型和安全原文链接；完全重复记录不增加数量，非 HTTP/HTTPS 链接必须移除。

- [x] **Step 2: Run RED**

Run: `E:\DSA项目\dsa-venv\Scripts\python.exe -m unittest tests.test_public_market_event_service -v`

Expected: FAIL because V128 does not retain source records.

- [x] **Step 3: Implement bounded source aggregation**

复用现有来源指纹完成去重，保留最多 8 条来源详情、最多 20 条来源计数。不得保存正文、用户信息或密钥，不得新增网络请求。

- [x] **Step 4: Run GREEN**

Run the same unittest command and require all event-service tests to pass.

### Task 2: API 契约与旧缓存兼容

**Files:**
- Modify: `api/v1/schemas/market_workspace.py`
- Modify: `apps/dsa-web/src/api/marketWorkspace.ts`
- Modify: `apps/dsa-web/src/api/__tests__/marketWorkspace.test.ts`
- Modify: `tests/test_public_market_home_v116.py`

- [x] **Step 1: Write failing contract tests**

后端模型新增有界 `source_records`；TypeScript mapper 使用 `sourceRecords`。旧缓存缺少新字段时，从事件主来源合成最多一条兼容记录；不安全链接不得进入前端链接字段。

- [x] **Step 2: Run RED**

Run focused backend schema and frontend API tests. Expected: missing-field assertions fail.

- [x] **Step 3: Add backward-compatible mapping**

限制来源明细最多 8 条，清洗空白字段、重复记录和 URL 协议。保持现有接口路径、认证、额度及缓存策略不变。

- [x] **Step 4: Run GREEN**

Require focused backend and frontend API tests to pass.

### Task 3: 双语来源对照界面

**Files:**
- Modify: `apps/dsa-web/src/components/market-home/DailyMarketEventCenterV126.tsx`
- Modify: `apps/dsa-web/src/components/market-home/__tests__/DailyMarketEventCenterV126.test.tsx`

- [x] **Step 1: Write failing interaction tests**

断言来源明细默认折叠；点击“查看来源”后显示“已显示 X / 共 N 条公开来源记录”、发布方、时间和可用原文链接；再次点击折叠。中文和英文模式必须完整对应。

- [x] **Step 2: Run RED**

Run the focused component test. Expected: source detail controls are absent.

- [x] **Step 3: Implement accessible disclosure UI**

使用明确按钮和展开状态，不嵌套卡片，不影响事件标题主链接和已读状态。无原文链接的记录显示“原文链接不可用”；文案明确“来源对照不代表事实已独立证实”。

- [x] **Step 4: Run GREEN**

Run the focused component, public-home integration and HomePage tests.

### Task 4: V129 门禁与交付文档

**Files:**
- Create: `scripts/verify_platform_event_source_evidence_v129.py`
- Create: `tests/test_platform_event_source_evidence_v129_verifier.py`
- Modify: `.gitignore`
- Modify: `scripts/verify_platform_release_candidate_package.py`
- Modify: `tests/test_platform_release_candidate_package.py`
- Modify: `docs/CHANGELOG.md`
- Modify: `docs/superpowers/platform-local-v1-acceptance-status.md`
- Modify: `docs/superpowers/platform-review-slices.md`
- Modify: `docs/superpowers/platform-release-candidate-manifest.md`

- [x] **Step 1: Write failing verifier and package tests**

门禁覆盖来源明细上限、链接协议清洗、旧缓存兼容、双语展开/折叠、免责声明、无新增 AI/网络请求及首页 chunk 大小。

- [x] **Step 2: Run RED**

Expected: V129 marker and release-package coverage are absent.

- [x] **Step 3: Implement verifier and update delivery records**

Verifier 成功时输出 `DSA_PLATFORM_EVENT_SOURCE_EVIDENCE_V129_OK`。文档记录本地功能边界、测试证据和仍未上线事项。

- [x] **Step 4: Run GREEN**

Run V129 verifier, release-candidate verifier and their tests.

### Task 5: 自动化与真实浏览器验收

**Files:**
- No production file changes expected beyond prior tasks.

- [x] **Step 1: Run focused backend and frontend regressions**

覆盖 V126-V129、API mapper、事件组件、主页集成和构建。

- [x] **Step 2: Start isolated V129 runtime**

使用 `8029` 和独立 `.codex-runtime` 数据库启动工作树服务，保持主线 `8018` 不变。

- [x] **Step 3: Browser acceptance**

在桌面与移动视口验证中文/英文、展开/折叠、安全原文链接、事件筛选、无横向溢出、无控制台错误，并确认不展示投资建议或事实确认措辞。

- [x] **Step 4: Safety and Git closure**

运行 `git diff --check`、敏感信息扫描、发布候选覆盖检查，并分别报告主线与 V129 工作树状态。未经单独授权不得提交、合并或推送。
