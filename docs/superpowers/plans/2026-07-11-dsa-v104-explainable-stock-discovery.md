# DSA V104 市场数据筛选与条件提醒实施计划

> 状态：已按“只提供资讯和数据，不提供投资建议”重新定义。本文档保留原文件名，避免历史链接失效。

## 1. 产品目标

将现有 `/screening` AlphaSift 选股页升级为 DSA 市场数据筛选中心，让用户完成以下闭环：

```text
用户选择市场、数据条件和排序方式
    -> 系统返回符合条件的证券数据
    -> 用户查看条件匹配说明、数据来源和更新时间
    -> 用户横向比较 2 至 5 只证券
    -> 登录用户加入个人自选
    -> 用户设置客观条件提醒
    -> 条件触发后收到事实性通知
    -> 返回首页查看自选数据和历史变化
```

本功能只整理和展示证券资讯、客观数据、用户筛选结果及条件触发记录，不判断证券是否值得投资，不生成交易动作。

## 2. 永久合规边界

### 2.1 允许提供

- 行情、K 线、均线、成交量、涨跌幅和历史区间数据。
- 财务、估值、行业、板块、公告、新闻和来源链接。
- 用户主动选择条件后产生的筛选结果。
- 指标匹配情况、数据完整度、数据新鲜度和来源状态。
- 多只证券的客观数据横向比较。
- 用户设置条件后的触发提醒和历史触发记录。
- AI 对已有数据和资讯的中性摘要，但必须标注 AI 来源。

### 2.2 禁止提供

- 买入、卖出、加仓、减仓、持有、止损、止盈等交易指令。
- 必涨、看多、看空、抄底、逃顶、首选标的、推荐股票等引导性判断。
- 目标价、上涨空间、预期收益、收益概率或个性化仓位建议。
- 根据用户资产、持仓或风险偏好生成交易动作。
- 将模型方向、LLM 文本或单一评分作为证券优劣结论。
- 将“数据完整”表达成“上涨概率高”或“值得购买”。

免责声明不能代替产品边界。API 字段、排序逻辑、页面标题、按钮、空状态、错误信息和提醒消息都必须遵守本节。

## 3. 中立术语

| 禁止或高风险表达 | V104 统一表达 |
| --- | --- |
| 股票发现、推荐股票 | 市场数据筛选、符合条件的证券 |
| 候选股票 | 筛选结果 |
| 入选原因 | 条件匹配说明 |
| 综合评分、投资评分 | 指标匹配度 |
| 高可信度 | 数据完整度高 |
| 风险评分 | 信息提示 |
| 下一步建议 | 后续数据观察项 |
| 失效条件 | 筛选条件不再满足的情形 |
| 强势、弱势、看多、看空 | 指标上升、指标下降、条件已触发 |
| AlphaSift 选股 | 市场数据筛选；AlphaSift 仅作为来源标记 |

证券代码、证券名称、法定公告标题和原始来源名称不做不必要改写。

## 4. 当前基线

- 仓库：`F:\DSA项目`
- 基线提交：`d1822e57695bcb86cd9283947f25e42683e8f894`
- 当前入口：`/screening`
- 当前筛选市场：AlphaSift 适配器当前只真实支持 `cn`，V104 页面必须明确显示“A 股数据筛选”。
- 当前结果页使用 `min-w-[860px]` 表格，移动端阅读成本高。
- 当前关键数据藏在展开行，缺少数据比较、平台自选和提醒闭环。
- 当前页面存在中文硬编码，需要纳入统一中英文文案系统。
- 当前平台已有个人自选、V99 事件雷达和 V100 私有提醒规则，V104 必须复用，不新增提醒数据库。

## 5. 功能范围

### 5.1 市场数据筛选

- 用户主动选择市场、筛选策略、结果数量和排序方式。
- 系统只返回符合用户所选条件的数据记录。
- 默认排序必须透明，页面显示当前排序字段和方向。
- 不使用“系统推荐顺序”或隐藏的个性化投资排序。
- 当前只开放 A 股筛选；美股和港股只保留单股数据查询入口，不伪装成已支持筛选。

### 5.2 筛选结果数据卡

每张卡片固定展示：

1. 证券代码、名称、市场和行业。
2. 用户所选条件及该证券的条件匹配情况。
3. 最多三项关键客观指标及其值。
4. 行情或财务数据更新时间。
5. 数据来源和来源状态。
6. 数据新鲜度：`fresh`、`cached`、`stale` 或 `unavailable`。
7. 数据完整度：只描述字段覆盖，不代表投资价值。
8. 信息提示，例如估值数据缺失、成交量变化或来源超时。
9. 后续数据观察项。
10. 筛选条件不再满足的情形。
11. 是否使用 AI；AI 只能摘要已有信息。

卡片不得渲染 provider 原始错误堆栈、密钥、Cookie、Token、绝对数据库路径或完整 `raw` 对象。

### 5.3 数据比较

- 用户可选择 2 至 5 只证券比较。
- 比较项只来自本次筛选结果，不重复请求行情、新闻或 LLM。
- 比较项包括价格、涨跌幅、行业、用户选定指标、数据新鲜度、更新时间和来源。
- 缺失值显示 `-`，不能当作零参与颜色或排序。
- 移动端按证券卡片纵向排列；桌面端可使用表格，但只允许比较容器内部滚动。

### 5.4 加入个人自选

- 游客可以筛选、阅读和比较。
- 加入自选必须登录，并复用 `/api/v1/platform/watchlist`。
- 401 只能显示“登录后可保存自选”，不能伪装保存成功。
- 保存失败时保留当前筛选结果和比较状态。
- 自选归属于当前平台用户，禁止写入全局系统自选。

### 5.5 条件提醒

复用现有 V100 私有提醒规则，不新增提醒数据库。允许的提醒类型：

- 价格达到用户设置的数值。
- 涨跌幅达到用户设置的绝对比例。
- 成交量相对历史均量变化达到用户设置的比例。
- 价格穿越用户选择的 MA5、MA10 或 MA20。
- 发布新公告、财报或具备可追溯链接的资讯。
- 证券进入或退出用户保存的筛选条件。
- 行情数据变为过期、缺失或来源异常。

提醒规则：

- 数值阈值必须由用户输入或确认。
- 系统可以提供“常用监控模板”，但不得称为推荐阈值。
- 提醒只描述事实，不附带交易动作。
- 示例：`AAPL 当前价格已达到您设置的 315.00 提醒条件。`
- 禁止示例：`AAPL 到达买点，建议买入。`
- 提醒记录必须包含证券代码、规则类型、设置值、观测值、触发时间和数据来源。
- 免费版和高级版遵循现有提醒配额策略，不在 V104 新建计费逻辑。

## 6. 数据模型

新建 `src/services/market_screening_brief.py`，从已经归一化并完成 DSA 增强的筛选结果生成确定性数据摘要。该服务不得重新请求行情、资讯或 LLM。

建议输出：

```python
{
    "matched_condition_codes": ["factor:quality", "pe_lte"],
    "observed_metrics": [
        {
            "code": "factor:quality",
            "value": 92.0,
            "source": "alphasift",
            "as_of": "2026-07-11T09:30:00+08:00",
        }
    ],
    "information_flags": ["valuation_data_partial"],
    "observation_codes": ["refresh_financial_data"],
    "condition_exit_codes": ["quality_below_threshold"],
    "data_freshness": "cached",
    "data_completeness": 75,
    "source_status": "partial",
    "ai_used": False,
}
```

约束：

- `data_completeness` 只依据字段覆盖计算。
- `data_freshness` 必须依据明确时间戳或现有来源状态计算。
- 有数据不等于数据新鲜；缓存或过期必须单独显示。
- LLM 字段只能改变 `ai_used` 和来源标记，不能提高数据完整度或新鲜度。
- 输出中不得存在 `recommendation`、`action`、`target_price`、`expected_return` 或同义字段。

## 7. 免费版与高级版

免费版和高级版保持相同的信息结构，均可看到：

- 条件匹配说明。
- 客观指标。
- 数据来源、更新时间和新鲜度。
- 信息提示。
- 最多五只证券的数据比较。
- 加入自选和设置提醒入口。

套餐只影响现有能力边界，例如处理数量、刷新频率、数据源深度、提醒规则数量和 API 使用方式。高级版不能获得买卖建议。

## 8. 非目标

- 不新增真实支付、生产密钥、生产部署或公开数据再分发授权结论。
- 不新增公共搜索或未经批准的数据源。
- 不复制或安装外部金融服务整仓库。
- 不创建或删除用户、历史报告、自选股、API Key 或 SQLite 数据库。
- 不新增全市场美股或港股筛选能力。
- 不把 Kronos 或其他模型方向输出接入筛选排序。
- 不自动执行 `git commit`、`git tag` 或 `git push`。

## 9. 文件计划

### 新建

- `src/services/market_screening_brief.py`
- `tests/test_market_screening_brief.py`
- `apps/dsa-web/src/components/screening/screeningModelV104.ts`
- `apps/dsa-web/src/components/screening/MarketScreeningCardV104.tsx`
- `apps/dsa-web/src/components/screening/ScreeningCompareTrayV104.tsx`
- `apps/dsa-web/src/components/screening/ScreeningReminderPanelV104.tsx`
- `apps/dsa-web/src/components/screening/__tests__/screeningModelV104.test.ts`
- `apps/dsa-web/src/components/screening/__tests__/MarketScreeningCardV104.test.tsx`
- `apps/dsa-web/src/components/screening/__tests__/ScreeningCompareTrayV104.test.tsx`
- `apps/dsa-web/src/components/screening/__tests__/ScreeningReminderPanelV104.test.tsx`
- `scripts/verify_platform_market_screening_alerts_v104.py`
- `tests/test_platform_market_screening_alerts_v104_verifier.py`

### 修改

- `src/services/alphasift_service.py`
- `tests/test_alphasift_api.py`
- `apps/dsa-web/src/api/alphasift.ts`
- `apps/dsa-web/src/api/platform.ts`
- `apps/dsa-web/src/api/__tests__/alphasift.test.ts`
- `apps/dsa-web/src/pages/StockScreeningPage.tsx`
- `apps/dsa-web/src/pages/__tests__/StockScreeningPage.test.tsx`
- `apps/dsa-web/src/components/layout/SidebarNav.tsx`
- `apps/dsa-web/src/i18n/uiText.ts`
- `apps/dsa-web/e2e/platform-user-e2e.spec.ts`
- `scripts/verify_platform_release_candidate_package.py`
- `tests/test_platform_release_candidate_package.py`
- `docs/CHANGELOG.md`
- `docs/superpowers/platform-product-rules.md`
- `docs/superpowers/platform-local-v1-acceptance-status.md`
- `docs/superpowers/platform-review-slices.md`
- `docs/superpowers/platform-release-candidate-manifest.md`

## 10. 实施任务

### Task 1：内容安全契约

- 先写后端和前端失败测试，禁止建议性字段和文案。
- 建立中英文禁用表达测试，只检查 DSA 自有文案，不改写原始公告标题。
- 错误响应不得包含密钥、Cookie、绝对数据库路径或 provider 堆栈。
- 通过条件：违规字段或违规自有文案出现时测试必须失败。

### Task 2：确定性市场筛选摘要

- 实现 `build_market_screening_brief()`。
- 只读取现有 AlphaSift 候选和 DSA 增强结果。
- 计算条件匹配、数据完整度、新鲜度、来源状态和信息提示。
- 缺失、缓存和过期数据必须降级显示。
- 无 LLM 时必须正常工作；有 LLM 时只标记来源。

### Task 3：API 与类型

- 在 AlphaSift 候选响应追加 `screening_brief`，保持向后兼容。
- 前端完成 snake_case 到 camelCase 映射。
- 不返回完整 `raw` 给新的卡片组件。
- 保留现有异步筛选任务、恢复和降级逻辑。

### Task 4：响应式数据卡与比较

- 用响应式数据卡替换 `min-w-[860px]` 结果表。
- 卡片圆角不超过 8px，固定展示第 5.2 节的数据。
- 使用图标按钮完成比较、加入自选、设置提醒和打开详情。
- 比较最多五只，不增加新的 API 请求。
- 390px 移动端无页面级横向溢出。

### Task 5：复用自选与提醒

- 登录用户通过平台自选接口保存证券。
- 提醒通过现有 `platformApi.watchlistAlertRules()` 和规则创建接口保存。
- 游客保存时显示登录提示，不能写入系统全局自选。
- 提醒消息使用事实性模板，并记录设置值和观测值。
- 同一来源更新或同一穿越事件不得重复触发。

### Task 6：页面入口与双语

- 侧边栏固定显示“市场筛选”入口；AlphaSift 未启用时展示可恢复状态，不直接隐藏入口。
- 页面主标题使用“市场数据筛选”，AlphaSift 只显示为来源。
- 中文和英文模式覆盖标题、状态、按钮、错误、空状态、动态标签和提醒消息。
- 切换市场、策略或重新运行筛选时清空旧比较状态。
- 打开证券详情时进入现有单股数据页，不自动消耗 AI 额度。

### Task 7：自动化验收

新建 verifier，依次执行：

1. 后端市场筛选摘要和 AlphaSift 回归测试。
2. 前端模型、卡片、比较、提醒和页面测试。
3. `npm.cmd run lint`。
4. `npm.cmd run build`。
5. release-candidate package 覆盖检查。

全部成功后才输出：

```text
DSA_PLATFORM_MARKET_SCREENING_ALERTS_V104_OK
```

### Task 8：真实浏览器验收

至少覆盖：

- 游客运行 A 股筛选、查看数据卡和比较两只证券。
- 游客尝试加入自选或保存提醒时看到登录提示。
- 登录免费用户加入自选并保存一条自定义条件提醒。
- 触发事实性提醒后，消息不包含交易动作。
- 返回首页后，自选和提醒归属于当前用户。
- 中文和英文模式。
- 1440x900 与 390x844。
- 新鲜、缓存、过期、不可用和无 LLM 数据。
- 浏览器无控制台错误和页面级横向溢出。

## 11. 完成定义

只有同时满足以下条件，才能声明 V104 完成：

- `DSA_PLATFORM_MARKET_SCREENING_ALERTS_V104_OK` 实际输出。
- 后端、前端、lint、build、E2E 和 release package verifier 全部通过。
- 页面和 API 不包含投资建议字段、交易动作或收益承诺。
- 提醒阈值由用户设置或确认，触发消息只陈述事实。
- 游客、登录用户和用户隔离边界有真实证据。
- 当前仅声明 A 股筛选，不伪造美股或港股筛选支持。
- 免费版和高级版信息结构一致，仅容量、刷新、来源深度和提醒数量不同。
- 不泄漏密钥、Cookie、用户数据、绝对数据库路径或原始 provider 错误。
- 8018 当前服务与工作树代码一致。
- Git diff 可审查；是否提交由潘总另行确认。

## 12. 回滚方案

1. 从 `StockScreeningPage.tsx` 移除 V104 数据卡、比较和提醒接线，恢复原结果表。
2. 删除 `components/screening/`、`market_screening_brief.py`、对应测试和 verifier。
3. 从 `alphasift_service.py` 移除追加的 `screening_brief` 字段。
4. 从 release package、产品规则和验收文档移除 V104 条目。
5. 不删除或清理用户、自选、提醒、历史报告、API Key 或数据库。

## 13. 下一阶段

文档确认后，下一步就是正式接入 V104：先实现内容安全契约和确定性后端摘要，再完成数据卡、比较、自选与提醒，最后执行自动化和真实浏览器验收。
