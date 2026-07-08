# DSA V66 Productized Snapshot

Status: local-only acceptance package.

## Goal

Make the free quick-query result feel like a useful product dashboard, not a bare quote response. Free and premium should expose the same visible modules on the query page; the difference is the data channel.

- Free mode: free web source, local public cache, local rules, No AI calls, No public search by default.
- Premium mode: premium API source, user API, platform API, or configured local model for fresher, steadier, and deeper reads.
- All content remains information analysis only and is not investment advice.

## Scope

- Add a professional overview block to the first query result screen.
- Show trend score, risk level, support/resistance, data channel, and module navigation.
- Keep the same visible modules for free and premium: quote overview, technical view, news center, and K-line forecast.
- Keep local-only guardrails: no real payment, no production deployment, no real API Key committed.

## Acceptance

- `apps/dsa-web/src/pages/HomePage.tsx` renders `basic-query-professional-overview`.
- Chinese mode shows Chinese labels: `专业速览`, `趋势评分`, `风险等级`, `数据通道`, `模块导航`, `免费网络源`, `高级 API 源`.
- HomePage unit test covers the professional overview and proves it is not a locked teaser.
- `scripts/verify_platform_productized_snapshot_v66.py` prints `DSA_PLATFORM_PRODUCTIZED_SNAPSHOT_V66_OK` only when all V66 markers exist.

## Verification

- `npm.cmd run test -- HomePage.test.tsx --reporter=dot -t "runs basic query without submitting AI analysis"`
- `python -m unittest tests.test_platform_productized_snapshot_v66`
- `python scripts/verify_platform_productized_snapshot_v66.py`

Marker: `DSA_PLATFORM_PRODUCTIZED_SNAPSHOT_V66_OK`
