# DSA V110 港美股公开数据适配器

## 目标

在不调用 AI、不使用通用网页搜索、也不要求用户提供 API Key 的前提下，为免费版补充可核验的美股和港股公开数据。港股、美股使用独立适配器，不复用 A 股 `a-stock-data` 逻辑。

## 已完成范围

- 美股：Yahoo Finance 直接资讯源、SEC EDGAR 官方申报文件、公司资料。
- 港股：Yahoo Finance 直接资讯源、公司资料、港交所披露易官方查询入口。
- 资讯仅保留标题中直接点名公司或代码的内容，减少宽泛市场新闻噪音。
- 美股 SEC 文件展示表单类型、申报日期、报告日期和官方原文链接。
- 港股若无法获得稳定的股票级港交所文件源，公告通道明确显示降级，不生成虚假公告。
- 页面中文/英文界面跟随系统语言；外部来源原文标题保持原文。
- 所有通道都返回来源、时间、状态和原文链接；失败只降级，不阻断行情快照。
- 首次请求使用网络，后续在 TTL 内使用进程缓存。

## 配置

代码和 `.env.example` 默认关闭：

```dotenv
GLOBAL_EQUITY_ENRICHMENT_ENABLED=false
GLOBAL_EQUITY_HTTP_TIMEOUT_SEC=5
GLOBAL_EQUITY_CACHE_TTL_SEC=600
GLOBAL_EQUITY_MAX_NEWS_ITEMS=5
GLOBAL_EQUITY_MAX_FILING_ITEMS=5
GLOBAL_EQUITY_SEC_USER_AGENT=DSA-local-research/1.0 contact@example.invalid
```

本机 8018 已在被 Git 忽略的 `.env` 中启用。正式使用 SEC 自动访问前，应把 User-Agent 联系方式替换为真实运营联系信息，并遵守来源访问规则。

## 数据与合规边界

- 仅提供资讯和数据，不提供投资建议、交易指令、目标价、仓位建议或收益承诺。
- `public_search_used=false` 表示未使用 SearXNG/搜索引擎式通用网页搜索；Yahoo Finance 入口是指定股票数据源的直接 JSON 通道。
- SEC 数据来自官方无密钥公开 API；系统保留缓存并限制刷新频率。
- 港交所股票级公告接口尚未批准接入时，只展示官方查询入口和降级状态。
- 外部新闻标题不等于平台观点；用户应打开原文确认时间、上下文和来源。

## 关键文件

- `src/services/global_equity_enrichment_service.py`
- `src/services/basic_query_service.py`
- `src/services/stock_service.py`
- `api/v1/schemas/basic_query.py`
- `api/v1/endpoints/stocks.py`
- `apps/dsa-web/src/api/stocks.ts`
- `apps/dsa-web/src/components/research/GlobalEquityEnrichmentCard.tsx`
- `apps/dsa-web/src/pages/HomePage.tsx`
- `tests/test_global_equity_enrichment_service_v110.py`
- `tests/test_basic_query_global_equity_v110.py`
- `tests/test_platform_global_equity_public_data_v110_verifier.py`
- `apps/dsa-web/src/components/research/__tests__/GlobalEquityEnrichmentCard.test.tsx`
- `scripts/verify_platform_global_equity_public_data_v110.py`

## 验收标准

1. AAPL 返回符号相关资讯、公司资料和至少一条 `sec.gov` 官方文件链接。
2. 0700.HK 返回符号相关资讯和公司资料；港交所公告状态及官方入口如实展示。
3. 两个市场都明确 `ai_used=false`、`public_search_used=false`。
4. 中文/英文界面、桌面/移动端均无横向溢出，原文链接可见。
5. 缓存命中明显快于首次网络请求。
6. V110 门禁输出 `DSA_PLATFORM_GLOBAL_EQUITY_PUBLIC_DATA_V110_OK`。

## 暂不进入本阶段

- 真实付费数据 API、生产密钥、生产部署。
- 未经授权抓取港交所股票级文档列表。
- 新闻自动翻译、AI 摘要或投资结论。
