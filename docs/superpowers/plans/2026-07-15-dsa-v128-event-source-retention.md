# DSA V128 事件信源透明与回访留存实施计划

> **For agentic workers:** Use `executing-plans` or an available multi-agent workflow to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在不新增网络请求、AI 调用或服务端用户追踪的前提下，让免费事件中心显示同一事件被多少条公开来源记录收录，并用浏览器本地状态提示用户上次访问后出现的新事件。

**Architecture:** 后端继续复用 `PublicMarketEventService`，将规范化标题相同的公开资讯合并为一条事件，同时保留去重后的来源记录数和发布方名称。前端为旧缓存提供安全默认值，并使用独立、有限容量的 `localStorage` 工具保存已读事件 ID；首次访问只建立基线，后续新增事件才显示“新事件”，用户可显式标记全部已读。

**Tech Stack:** Python 3.12、FastAPI/Pydantic、React 19、TypeScript、localStorage、unittest、Vitest、Vite、现有 DSA verifier 与真实浏览器验收工具。

---

### Task 1: 多来源事件合并

**Files:**
- Modify: `tests/test_public_market_event_service.py`
- Modify: `src/services/public_market_event_service.py`

- [x] **Step 1: Write failing source-merge tests**

新增测试，要求同一规范化标题由两个不同 URL 或发布方收录时只返回一条事件，并返回：

```python
assert event["source_count"] == 2
assert event["source_publishers"] == ["Source A", "Source B"]
```

完全相同的重复记录不得增加 `source_count`，且原有低相关过滤、重要度和跨市场去重继续成立。

- [x] **Step 2: Run RED**

Run: `E:\DSA项目\dsa-venv\Scripts\python.exe -m unittest tests.test_public_market_event_service -v`

Expected: FAIL because V127 drops duplicate titles without retaining source metadata.

- [x] **Step 3: Implement bounded source aggregation**

为每个已保留事件建立内部来源指纹集合。URL 存在时优先以 URL 识别来源记录；URL 缺失时使用发布方和来源代码。只公开最多 20 条来源记录计数和最多 8 个去重发布方名称，不改变主要标题、主要原文链接、市场归属或相关度规则。

- [x] **Step 4: Run GREEN**

Run the same unittest command and require all event-service tests to pass.

### Task 2: API 契约与旧缓存兼容

**Files:**
- Modify: `api/v1/schemas/market_workspace.py`
- Modify: `apps/dsa-web/src/api/marketWorkspace.ts`
- Modify: `apps/dsa-web/src/api/__tests__/marketWorkspace.test.ts`
- Modify: `tests/test_public_market_home_v116.py`

- [x] **Step 1: Write failing contract tests**

断言事件响应新增：

```python
source_count: int = 1
source_publishers: list[str] = []
```

TypeScript 使用 `sourceCount` 和 `sourcePublishers`。旧缓存缺少字段时，前端回退到一条来源记录，并在存在 `publisher` 时将其作为唯一发布方。

- [x] **Step 2: Run RED**

Run focused backend and frontend API tests. Expected: missing-field assertions fail.

- [x] **Step 3: Add backward-compatible fields**

Pydantic 将 `source_count` 限制为 `1..20`，`source_publishers` 默认空数组。前端 mapper 对非有限值、零值、非数组和空白发布方做确定性清洗。

- [x] **Step 4: Run GREEN**

Require focused backend and frontend API tests to pass without changing endpoint、认证或额度边界。

### Task 3: 浏览器本地已读状态

**Files:**
- Create: `apps/dsa-web/src/lib/marketEventReadState.ts`
- Create: `apps/dsa-web/src/lib/__tests__/marketEventReadState.test.ts`

- [x] **Step 1: Write failing utility tests**

测试首次无状态返回 `null`、损坏 JSON 安全降级、事件 ID 去重、最多保存 200 条、合并当前事件并保持最近项优先。

- [x] **Step 2: Run RED**

Run: `npm.cmd run test -- --run src/lib/__tests__/marketEventReadState.test.ts`

Expected: FAIL because the module does not exist.

- [x] **Step 3: Implement the bounded storage helper**

使用固定键 `dsa.marketEvents.seen.v1`。工具只保存事件 ID，不保存邮箱、自选、查询内容、API Key、标题或原文链接；存储不可用时 fail open，不影响事件展示。

- [x] **Step 4: Run GREEN**

Run the same Vitest command and require all utility tests to pass.

### Task 4: 双语新事件与信源透明界面

**Files:**
- Modify: `apps/dsa-web/src/components/market-home/DailyMarketEventCenterV126.tsx`
- Modify: `apps/dsa-web/src/components/market-home/__tests__/DailyMarketEventCenterV126.test.tsx`

- [x] **Step 1: Write failing component tests**

预置本地已读 ID 后渲染两条事件，断言只对未读事件显示“新事件”、标题区显示“新增 1”、来源区域显示“2 条公开来源记录”和发布方，并且“全部标为已读”会清除新增提示。英文模式显示对应英文文案。

- [x] **Step 2: Run RED**

Run the focused component test. Expected: source count and read-state controls are absent.

- [x] **Step 3: Implement focused UI**

首次访问自动将当前事件建立为已读基线，不把全部历史事件误标为新增。后续只根据稳定 `eventId` 显示新增状态；筛选不会改变已读集合。发布方只作来源透明展示，不使用“已确认”“可信评级”等误导措辞。

- [x] **Step 4: Run GREEN**

Run component、public-home integration and HomePage tests in Chinese and English.

### Task 5: V128 门禁与交付文档

**Files:**
- Create: `scripts/verify_platform_event_source_retention_v128.py`
- Create: `tests/test_platform_event_source_retention_v128_verifier.py`
- Modify: `.gitignore`
- Modify: `scripts/verify_platform_release_candidate_package.py`
- Modify: `tests/test_platform_release_candidate_package.py`
- Modify: `docs/CHANGELOG.md`
- Modify: `docs/superpowers/platform-local-v1-acceptance-status.md`
- Modify: `docs/superpowers/platform-review-slices.md`
- Modify: `docs/superpowers/platform-release-candidate-manifest.md`

- [x] **Step 1: Write failing verifier test**

门禁检查多来源合并、旧缓存默认值、有限本地存储、新事件双语文案、首次访问基线、全部标记已读、无 AI/新增网络请求和资讯数据边界。

- [x] **Step 2: Implement verifier**

Passing marker: `DSA_PLATFORM_EVENT_SOURCE_RETENTION_V128_OK`.

- [x] **Step 3: Update release documents**

文档明确“多条来源记录”不等于事实被独立证实；V128 不删除原始资讯、不上传本地已读状态、不修改用户数据。

### Task 6: 完整验证与本地交付

**Files:**
- Verify only; do not add production deployment files.

- [x] **Step 1: Automated verification**

运行相关后端 unittest、前端 Vitest、`npm.cmd run build`、V127/V128 verifier、release package verifier、`git diff --check` 和敏感凭据扫描。

- [x] **Step 2: Real-browser acceptance**

独立端口验收首次访问无虚假新增、注入一条新公开事件后的新增提示、全部标为已读、来源数量和发布方、中英文、市场筛选、移动端无横向溢出、控制台无错误。

- [x] **Step 3: Git closure boundary**

主项目始终保持干净。V128 未获得单独提交授权前不得执行 `git commit`、合并或 `git push`；交付时报告准确 dirty 清单和建议提交边界。
