# DSA V69 Free Data Depth

Status: local-only

Marker: DSA_PLATFORM_FREE_DATA_DEPTH_V69_OK

## Goal

Make the free query result feel useful enough for ordinary visitors by showing a concrete data board, not only commercial copy. Free and premium should expose the same visible modules; premium changes data freshness, API source quality, source links, and model depth.

## Scope

- Add a free data depth board after the free commercial journey.
- Show concrete quote, volume, market cap, PE, moving averages, support, resistance, event lanes, peer references, and risk boundaries.
- Keep A-share and US equity labels visible so both markets can use the same component.
- Keep the board localized for Chinese and English UI.
- Keep free quick mode as No AI and no public search.

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

- `basic-query-data-depth-board` appears after `basic-query-commercial-journey`.
- Chinese UI contains `免费版真实数据面板`, `美股重点数据`, `A股重点数据`, `核心数据`, `技术结构`, `资讯与事件`, `同业与风险`, and `仅作信息分析，不构成投资建议`.
- The AAPL test fixture shows latest price, change, volume, market cap, PE, MA5, MA20, support, resistance, SEC lane, financial snapshot lane, QQQ, and XLK.
- The board keeps same visible modules for free and premium; premium only improves source/data/model quality.
- `scripts/verify_platform_free_data_depth_v69.py` prints `DSA_PLATFORM_FREE_DATA_DEPTH_V69_OK`.
