# DSA V115 统一数据中台与来源仲裁

## 目标

让 Kronos、A 股增强、AlphaSift、Financial Services、市场工作台及后续资讯简报复用同一份 DSA 股票事实快照，避免重复抓取、重复展示和冲突数据互相覆盖。

V115 只处理资讯和数据，不产生投资建议、交易指令、目标价、仓位或收益承诺。

## 数据边界

1. `BasicQueryService` 继续作为单股事实快照主入口，不新建第二套账号、数据库或查询页面。
2. 行情、历史 K 线和公司资料分别保留选中来源、新鲜度、观测时间、缓存状态和字段级来源。
3. 来源冲突时按“新鲜度、市场来源优先级、观测时间”选择单一事实，不计算平均价格。
4. 公告、资讯和事件记录按原始编号或规范化 URL 去重；移除常见跟踪参数后再比较。
5. Kronos 和 AI 输出属于派生信息，不得覆盖事实字段。
6. OpenStock 仍只作为产品体验参考；其 AGPL 代码和运行时不进入 DSA。
7. `ai-market-pulse` 仍是隔离 POC；后续产品化只能读取 DSA 原生统一快照。

## 实现范围

- `src/services/market_data_contract.py`
  - 字段候选来源仲裁。
  - 资讯、公告和事件记录去重。
  - 构建 `canonical_data` 数据契约。
- `src/services/basic_query_service.py`
  - 对已有快照执行统一去重。
  - 追加选中来源、字段来源、冲突和去重统计。
- `api/v1/schemas/basic_query.py`
  - 通过响应模型保留统一契约。
- `apps/dsa-web/src/api/stocks.ts`
  - 增加统一数据契约类型。
- `apps/dsa-web/src/pages/HomePage.tsx`
  - 在免费版“数据可信度”区域展示来源类型、冲突数和去重数。

## 验收标准

1. 新鲜候选优先于过期候选。
2. 新鲜度相同时按当前市场来源优先级选取。
3. 冲突值不取平均，并保留冲突状态。
4. 带不同追踪参数的同一链接只保留一条。
5. `/api/v1/stocks/{code}/snapshot` 返回 `canonical_data`，且 `ai_used=false`。
6. 中文界面显示“统一事实快照”，英文界面显示 `Canonical fact snapshot`。
7. 页面继续显示“仅作信息分析，不构成投资建议”。
8. 验收脚本输出 `DSA_PLATFORM_UNIFIED_MARKET_DATA_V115_OK`。

## 后续迁移顺序

1. 让新增资讯简报只读取 `canonical_data` 和 DSA 事件数据，不直接调用上游项目。
2. 为 AlphaSift 批量候选追加同一来源状态契约，但不触发逐股网络查询。
3. 增加跨来源数值差异阈值和管理员诊断，不向普通用户展示内部异常堆栈。
4. 在取得数据授权前，不把未授权实时行情或全文资讯作为付费权益销售。
