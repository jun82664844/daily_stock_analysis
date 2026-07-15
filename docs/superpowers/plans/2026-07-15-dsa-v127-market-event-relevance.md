# DSA V127 免费市场事件提纯与相关性实施计划

> **For agentic workers:** Use `executing-plans` or an available multi-agent workflow to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 V126 事件中心从“有很多快讯”升级为“能快速看到与证券市场相关的重点事件”，减少低相关噪声，增加跨市场去重、重要度、相关原因、市场筛选和自选优先展示。

**Architecture:** 后端继续复用 `PublicMarketEventService`，仅对已加载的公开首页资讯做确定性规则评分，不新增抓取、不调用 AI、不消耗 API 额度。前端在 V126 组件中完成中英文市场筛选、重要度与相关原因展示，并在客户端将自选事件稳定排在同优先级事件之前。

**Tech Stack:** Python 3.12、FastAPI/Pydantic、React 19、TypeScript、unittest、Vitest、Vite、现有 DSA verifier 与真实浏览器验收工具。

---

### Task 1: 后端事件相关性规则

**Files:**
- Modify: `src/services/public_market_event_service.py`
- Modify: `tests/test_public_market_event_service.py`

- [x] **Step 1: Write failing relevance tests**

新增用例断言：

```python
events = PublicMarketEventService().build(markets, as_of)
assert "埃博拉确诊病例增加" not in [item["title"] for item in events]
assert events[0]["importance"] in {"high", "medium", "low"}
assert 0 <= events[0]["relevance_score"] <= 100
assert events[0]["relevance_reasons"]
```

覆盖低相关普通快讯被排除、财报/公告/分红/交易状态/宏观财经事件保留、关联证券加分、重复标题跨市场只保留一条。

- [x] **Step 2: Run RED**

Run: `E:\DSA项目\dsa-venv\Scripts\python.exe -m unittest tests.test_public_market_event_service -v`

Expected: FAIL because V126 events do not expose relevance fields and still retain low-relevance market headlines.

- [x] **Step 3: Implement deterministic scoring and filtering**

实现稳定规则：关联证券、结构化事件类别、财经市场关键词、来源新鲜度和可追溯链接贡献分数；总分限制在 `0..100`，映射为 `high / medium / low`。`market` 类且无证券关联、无财经信号的普通快讯不进入事件中心，但原始快讯区仍保留。

- [x] **Step 4: Run GREEN**

Run the same unittest command and require all V126/V127 event service cases to pass.

### Task 2: API 契约与兼容降级

**Files:**
- Modify: `api/v1/schemas/market_workspace.py`
- Modify: `apps/dsa-web/src/api/marketWorkspace.ts`
- Modify: `apps/dsa-web/src/api/__tests__/marketWorkspace.test.ts`
- Modify: `tests/test_public_market_home_v116.py`

- [x] **Step 1: Write failing contract tests**

断言事件契约新增 `relevance_score`、`importance`、`relevance_reasons`，老事件 payload 在默认值下仍可解析，`ai_used=false` 和 `informational_only=true` 不变。

- [x] **Step 2: Run RED**

Run focused backend and frontend API tests; expect missing-field assertions to fail.

- [x] **Step 3: Add backward-compatible fields**

Pydantic 字段使用安全默认：

```python
relevance_score: int = Field(0, ge=0, le=100)
importance: Literal["high", "medium", "low"] = "low"
relevance_reasons: List[str] = Field(default_factory=list)
```

TypeScript 对应保持驼峰命名。

- [x] **Step 4: Run GREEN**

Require focused API tests to pass without changing existing endpoint or authentication boundaries.

### Task 3: 前端市场筛选与自选优先

**Files:**
- Modify: `apps/dsa-web/src/components/market-home/DailyMarketEventCenterV126.tsx`
- Modify: `apps/dsa-web/src/components/market-home/__tests__/DailyMarketEventCenterV126.test.tsx`

- [x] **Step 1: Write failing UI tests**

测试中英文市场筛选、重要度标签、相关原因、重点事件计数，以及同优先级下自选事件排在非自选事件前。

- [x] **Step 2: Run RED**

Run: `npm.cmd run test -- --run src/components/market-home/__tests__/DailyMarketEventCenterV126.test.tsx`

Expected: FAIL because V126 has category filters only.

- [x] **Step 3: Implement focused UI**

保留 V126 单层带状布局，在分类筛选上方增加 `全部市场 / A股 / 港股 / 美股`。重要度和原因使用双语文案，不显示内部分数公式，不出现买入、卖出、目标价或收益预测。

- [x] **Step 4: Run GREEN**

Run the V126 component tests and public-home integration tests.

### Task 4: V127 门禁与文档

**Files:**
- Create: `scripts/verify_platform_market_event_relevance_v127.py`
- Create: `tests/test_platform_market_event_relevance_v127_verifier.py`
- Modify: `.gitignore`
- Modify: `scripts/verify_platform_release_candidate_package.py`
- Modify: `tests/test_platform_release_candidate_package.py`
- Modify: `docs/CHANGELOG.md`
- Modify: `docs/superpowers/platform-local-v1-acceptance-status.md`
- Modify: `docs/superpowers/platform-review-slices.md`
- Modify: `docs/superpowers/platform-release-candidate-manifest.md`

- [x] **Step 1: Write failing verifier test**

门禁必须检查低相关噪声规则、全局去重、三个契约字段、市场筛选、自选优先、双语文案、不调用 AI 以及合规提示。

- [x] **Step 2: Run RED and implement verifier**

Passing marker: `DSA_PLATFORM_MARKET_EVENT_RELEVANCE_V127_OK`.

- [x] **Step 3: Update release documents**

文档明确 V127 只对事件中心做展示提纯，不删除原始快讯、不改变用户数据、不构成投资建议。

### Task 5: 全量验证与本地交付

**Files:**
- Verify only; no production file added in this task.

- [x] **Step 1: Automated verification**

运行相关后端 unittest、相关前端 Vitest、`npm.cmd run build`、V126/V127 verifier、release package verifier、`git diff --check` 和变更文件敏感凭据扫描。

- [x] **Step 2: Real-browser acceptance**

在独立端口验收中英文、三市场筛选、类别筛选、自选优先、低相关噪声不进入事件中心、个股跳转、无横向溢出、控制台无错误。

- [x] **Step 3: Git closure boundary**

主项目始终保持干净。V127 未获得独立提交授权前不执行 `git commit`或 `git push`；交付时报告准确 dirty 清单和建议提交边界。
