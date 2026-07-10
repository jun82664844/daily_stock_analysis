# DSA V96 Free Trial Report Conversion

Date: 2026-07-10

Scope: local-only retention and conversion improvement after the bounded free platform-API trial. No production deployment, real payment, real credentials, or data deletion.

## Goal

When a free user's trial task completes, open the newly generated report automatically, preserve the complete report content, and provide a clear path to review premium API/model options.

## Changes

- Capture the visible history-id baseline and trial start time before submission.
- Match only a newly created, equivalent-symbol report after completion.
- Retry the immediate history lookup briefly so database/list refresh timing does not strand the user on the old snapshot.
- Allow a newer history refresh to replace a cancelled lookup without leaving a stale pending lock.
- Open the report detail automatically and show a localized conversion band for free users.
- Route the conversion action to `/account`; do not start checkout or change plan.

## Acceptance

- Old or baseline reports are not selected as the completed trial result.
- Chinese and English conversion copy covers Platform API, user API, local model, and the disabled real-payment boundary.
- Browser E2E covers registration, AAPL lookup, one trial, automatic report opening, report content, and account navigation.
- Related HomePage/store/component tests and the production frontend build pass.
- Existing backend, release package, local operability, and V2 readiness gates remain green.

## Verification

PowerShell:

    npm test -- --run src/pages/__tests__/HomePage.test.tsx src/stores/__tests__/stockPoolStore.test.ts src/components/retention/__tests__/FreeApiTrialPanelV93.test.tsx src/components/retention/__tests__/FreeApiTrialTaskStatusV95.test.tsx src/components/retention/__tests__/queryChangeTracker.test.ts src/components/retention/__tests__/freeApiTrialReport.test.ts src/components/retention/__tests__/FreeApiTrialConversionV96.test.tsx
    $env:DSA_PLATFORM_E2E='1'; npm run test:smoke -- e2e/platform-user-e2e.spec.ts
    npm run build

Rollback: revert the V96 helper, conversion component, HomePage/E2E integration, and V96 docs together. Do not delete reports, databases, cache files, user data, or prior local slices.
