# DSA V67 Free Research Board

Status: local-only acceptance package.

## Goal

Make the free query result useful enough for ordinary users to keep reading. The first screen should expose a free research board with real scan value, not only feature entry buttons.

## Scope

- Add a free research board under the professional overview.
- The board summarizes four lanes:
  - news radar
  - K-line read
  - peer and sector context
  - risk explanation
- Free mode uses local/public-data summaries, No AI calls, and No public search by default.
- Premium/API mode keeps the same visible modules but upgrades freshness, source links, configured feeds, and model depth.

## Non-goals

- No real payment.
- No production deployment.
- No production secrets or real API Key committed.
- No investment advice; not investment advice.

## Acceptance

- `apps/dsa-web/src/pages/HomePage.tsx` renders `basic-query-free-research-board`.
- Chinese mode shows `免费研究看板`, `资讯雷达`, `K线推演`, `同业/板块`, and `风险解释`.
- The board surfaces concrete content such as news lanes, K-line horizon/support/resistance, peer references, and risk/source boundaries.
- `scripts/verify_platform_free_research_board_v67.py` prints `DSA_PLATFORM_FREE_RESEARCH_BOARD_V67_OK`.

## Verification

- `npm.cmd run test -- HomePage.test.tsx --reporter=dot -t "runs basic query without submitting AI analysis"`
- `python -m unittest tests.test_platform_free_research_board_v67`
- `python scripts/verify_platform_free_research_board_v67.py`

Marker: `DSA_PLATFORM_FREE_RESEARCH_BOARD_V67_OK`
