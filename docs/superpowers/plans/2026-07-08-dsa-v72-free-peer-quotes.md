# DSA V72 Free Peer Reference Quotes

Status: local-only functional upgrade. This does not approve production deployment, real payment, production secrets, market-data redistribution, or investment advice.

Goal:

- Make the free no-AI result more useful by showing lightweight peer and market reference quote values in the same visible modules that premium users will later see with steadier API-backed sources.
- This is the free peer reference quotes slice.

Implemented scope:

- Backend comparison targets now include `reference_quote` when a lightweight public/local quote can be fetched within a short timeout.
- Peer comparison rows also carry the same `reference_quote` payload so the free comparison table can show actual reference price, change, freshness, and source status.
- Reference quote fetching uses existing cache and a short timeout. If the reference source is unavailable, the main stock snapshot still completes and the reference quote is marked unavailable.
- When the platform reference source returns empty, the reference lane can use a no-key Yahoo chart fallback for public benchmark symbols.
- Frontend Chinese mode now shows `参照行情`, `参照价`, `涨跌幅`, and localized freshness state instead of reserving comparison values for deep mode only.
- Free and premium keep the same visible modules. Premium/API mode should improve freshness, source stability, source links, configured feeds, and model depth rather than hiding basic useful fields from free users.

Guardrails:

- No AI calls.
- No public search.
- No real payment.
- No production deployment.
- No real API Key in code, docs, tests, or logs.
- Do not commit real API Key.
- Short timeout boundary keeps this out of the deep-analysis path.
- All analysis text remains information analysis only and not investment advice.

Verification marker:

- `DSA_PLATFORM_FREE_PEER_QUOTES_V72_OK`

Primary verification:

- `python -m unittest tests.test_basic_query_no_ai.BasicQueryNoAiTestCase.test_no_ai_snapshot_enriches_free_comparison_targets_with_reference_quotes`
- `npm run test -- --run src/pages/__tests__/HomePage.test.tsx -t "shows free comparison reference quote values"`
- `python scripts/verify_platform_free_peer_quotes_v72.py`

Review notes:

- Review `src/services/basic_query_service.py` for timeout/cache behavior and unavailable fallback.
- Review `api/v1/schemas/basic_query.py` and `apps/dsa-web/src/api/stocks.ts` together so snake_case to camelCase mapping stays intact.
- Review `apps/dsa-web/src/pages/HomePage.tsx` at desktop and narrow widths because the peer comparison table now has an extra reference quote column.
