# DSA V68 Free Commercial Journey

Status: local-only

Marker: DSA_PLATFORM_FREE_COMMERCIAL_JOURNEY_V68_OK

## Goal

Improve the free query result so ordinary visitors understand the report flow, see that the useful modules are already open, and understand that premium changes data source quality instead of hiding the core page.

## Scope

- Add a free commercial journey block near the top of the basic query result.
- Keep guest query works / anonymous query as a first-class path.
- Show the same visible modules in free mode: quote, technicals, news, K-line, peers, risk.
- Make the premium distinction explicit: premium changes data source, realtime links, and model depth.
- Keep the module copy localized in Chinese and English.

## Safety Boundaries

- No-go for production deployment.
- local-only.
- not real payment.
- not investment advice.
- Do not commit real API Key.
- Do not delete user history, reports, databases, watchlists, or billing sandbox data.
- No AI calls.
- No public search.

## Acceptance

- `basic-query-commercial-journey` appears after the primary summary and before deeper result modules.
- Chinese UI contains: 免费查询完整路径, 免费版已开放, 高级版只换数据源, 不登录也能查.
- English UI has equivalent copy without implying hidden paid-only core modules.
- The block explains same visible modules and premium changes data source.
- `scripts/verify_platform_free_commercial_journey_v68.py` prints `DSA_PLATFORM_FREE_COMMERCIAL_JOURNEY_V68_OK`.
