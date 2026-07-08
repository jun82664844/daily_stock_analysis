# DSA V63 A-Stock-Data Experience

Status: local-only functional upgrade.

## Goal

Turn the V62 A-share data expansion from raw channel cards into a clearer product experience for ordinary users:

- Show a first-read `reader_summary` before individual channels.
- Surface why the result is worth reading.
- Explain checked-but-empty or degraded channels instead of looking blank.
- Show a premium unlock ladder without blocking the free no-AI query.
- Keep the output informational only and not investment advice.

## Boundaries

- No AI calls in the free quick query path.
- No public search in the free quick query path.
- No real payment integration.
- No production deployment, DNS, HTTPS, WAF, or legal approval work.
- Do not commit real API Key values.
- Do not delete reports, database rows, user data, or local history.

## Implementation Notes

- Backend adds `reader_summary` to A-share enrichment payloads.
- Frontend renders `basic-query-a-share-reader-summary` above channel cards.
- The summary includes key facts, missing/degraded notes, premium features, and the safety boundary.
- Existing A-share channels remain visible for source-level detail.

## Verification

- Backend unittest covers `reader_summary`.
- Frontend HomePage test covers the Chinese V63 reader summary block.
- `scripts/verify_platform_a_stock_data_experience_v63.py` checks marker coverage.

OK marker: `DSA_PLATFORM_A_STOCK_DATA_EXPERIENCE_V63_OK`
