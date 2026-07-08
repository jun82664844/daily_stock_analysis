# DSA V65 Free Value Experience

Status: local-only frontend value upgrade.

Acceptance marker: `DSA_PLATFORM_FREE_VALUE_V65_OK`

## Goal

Make the free no-AI query result feel useful enough for ordinary users to continue using the site and understand why deep or premium analysis is worth unlocking.

## Scope

- Add a first-screen free value summary after the quote header.
- Show a readable conclusion, current watch points, risk boundary, and upgrade unlock path.
- Add a "Complete free quick read" block that combines opportunity lens, risk boundary, next watchlist, data source, and premium unlocks in the first screen.
- Keep first-screen entries for News Center and K-line forecast so those free functions do not look missing.
- Keep the free flow no-AI and no public search.
- Move low-level diagnostics behind a collapsed details block by default.

## Boundaries

- local-only
- No AI calls in the free snapshot.
- No public search in the free snapshot.
- No real payment, production deployment, real API Key, or production secret changes.
- All output is information analysis only, not investment advice.

## Verification

- `npm.cmd run test -- HomePage.test.tsx --reporter=dot -t "runs basic query without submitting AI analysis"`
- `python scripts/verify_platform_free_value_v65.py`
