# DSA V64 A-Stock-Data Details

Status: local-only functional upgrade.

Goal: make the A-share enrichment cards more useful by adding structured channel details above the existing summary/action text. This keeps free quick query readable while preserving the raw channel cards from V63.

Scope:

- Add `details` to A-share enrichment channel payloads.
- Preserve `details` through the FastAPI response schema.
- Render compact detail rows in the HomePage A-share channel cards.
- Cover announcement, fund-flow, sector, research, and dragon-tiger channels.

Boundaries:

- No AI calls.
- No public search.
- No production deployment.
- No real payment or real production secrets.
- Do not commit real API Key.
- All output remains information analysis only; not investment advice.

Acceptance:

- Backend service tests verify channel-level details.
- API schema tests verify `details` is not filtered out.
- HomePage tests verify details render in Chinese mode.
- `scripts/verify_platform_a_stock_data_details_v64.py` prints `DSA_PLATFORM_A_STOCK_DATA_DETAILS_V64_OK`.
