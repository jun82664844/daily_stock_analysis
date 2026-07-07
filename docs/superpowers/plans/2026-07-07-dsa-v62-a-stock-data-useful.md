# DSA V62 A-Stock-Data Useful Data

Status: local-only. This is not production launch approval, not real payment, not market-data redistribution approval, and not investment advice.

## Goal

Make the A-share free snapshot useful enough for local user acceptance by turning the `a-stock-data` adapter from a visible switch into real no-AI data lanes:

- CNINFO announcements.
- Eastmoney fund-flow snapshots.
- Eastmoney sector/concept tags.
- Eastmoney research report titles and ratings.
- Eastmoney dragon-tiger list checks.
- Shanghai CNINFO fallback orgId handling for codes such as `600519`.
- Local sector fallback tags for common A-share names when the public sector endpoint is empty or slow.
- A slightly longer `a_stock_data` default timeout than the local POC mode so real announcement/research endpoints have a better chance to return useful titles.

## Boundaries

- No AI calls.
- No public search.
- No real API Key.
- Do not commit real API Key.
- No real payment.
- No production deployment.
- Do not delete history reports, databases, user data, or cache artifacts.
- Keep all analysis as information analysis only; not investment advice.

## Acceptance

- `AShareEnrichmentService(source_mode="a_stock_data")` maps pseudo URLs to public-source payload parsers.
- Shanghai CNINFO fallback uses `gssh0{code}` instead of the wrong `gssx0{code}` shape.
- 600519 / 贵州茅台 can show useful local sector tags when the public sector endpoint returns empty.
- `a_stock_data` mode keeps a 2.5s default timeout while local POC mode keeps the faster 1.2s default.
- Empty or timed-out upstream channels stay visible as checked degraded channels instead of falling back to vague reserved-lane copy.
- Chinese UI mode does not show obvious English phrases such as `current context` in the useful A-share card.
- HomePage defaults A-share inputs to `a_stock_data` while avoiding A-share source parameters for non-A-share inputs.
- The verifier prints `DSA_PLATFORM_A_STOCK_DATA_USEFUL_V62_OK`.

## Verification

- `python -m unittest tests.test_a_share_enrichment_service`
- `python -m unittest tests.test_platform_a_stock_data_useful_v62`
- `python scripts/verify_platform_a_stock_data_useful_v62.py`
- Frontend HomePage target test and production build.

DSA_PLATFORM_A_STOCK_DATA_USEFUL_V62_OK
