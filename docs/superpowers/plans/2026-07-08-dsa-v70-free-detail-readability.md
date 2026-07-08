# DSA V70 Free Detail Readability

Status: local-only completed slice.

Acceptance marker: `DSA_PLATFORM_FREE_DETAIL_READABILITY_V70_OK`

## Goal

Improve free detail readability so the no-AI free query result feels useful enough for ordinary users before they decide whether to upgrade. The free and premium versions keep the same visible modules; premium/API mode later improves freshness, source links, configured feeds, and model depth.

## Scope

- Add expand details rows to the free data board.
- Add an event checklist that turns degraded/free-source lanes into readable next actions.
- Add a peer comparison table using the existing broad-market and sector references.
- Add K-line triggers from the existing local K-line forecast preview.
- Keep free quick mode local-only, no AI calls, and no public search.

## Non-goals

- No production deployment.
- No real payment.
- No real API Key committed.
- Do not commit real API Key.
- No AI calls.
- No public search enablement.
- No market-data redistribution approval.
- No investment advice.

## Verification

- `npm.cmd run test -- HomePage.test.tsx --reporter=dot -t "runs basic query without submitting AI analysis"`
- `python -m unittest tests.test_platform_free_detail_readability_v70`
- `python scripts/verify_platform_free_detail_readability_v70.py`

## Boundaries

The V70 detail board is for information analysis only and is not investment advice. It uses the existing free snapshot fields and should not add hidden model, API, or search cost to the ordinary query path.
