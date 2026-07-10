# DSA V95 Free API Trial Result Loop

Date: 2026-07-10

Scope: local-only retention improvement for the bounded free platform-API trial. No production deployment, payment, real credentials, or data deletion.

## Goal

Turn a free user's platform-API trial from a one-line submission notice into a visible result loop. The user should know whether the task is pending, processing, completed, or failed, and should be told when history has refreshed.

## Changes

- Preserve the accepted asynchronous task id returned by submitAnalysis.
- Insert each accepted task into activeTasks immediately so an early SSE completion event cannot be lost.
- Add a localized task-status card with bounded progress.
- Subscribe the card to the existing activeTasks state so it does not create a second polling or API-spend path.
- Map cancellation to a visible failed outcome and avoid presenting an incomplete task as a report.
- Keep the existing weekly ai_quick quota boundary and no-AI guest lookup unchanged.

## Acceptance

- The component renders localized processing, completed, and retry-oriented failed states.
- The store returns the accepted task id to callers.
- HomePage regression tests and production build pass.
- The browser flow covers registration, AAPL query, one bounded platform-API trial, completed status, refreshed history, and unchanged quota separation.
- Combined V93/V94/auth/analysis backend tests remain order-independent.
- Existing release and local operability verifiers remain green.

## Verification

PowerShell:

    npm test -- --run src/components/retention/__tests__/FreeApiTrialTaskStatusV95.test.tsx src/stores/__tests__/stockPoolStore.test.ts
    npm test -- --run src/components/retention/__tests__/FreeApiTrialPanelV93.test.tsx src/pages/__tests__/HomePage.test.tsx
    $env:DSA_PLATFORM_E2E='1'; npm run test:smoke -- e2e/platform-user-e2e.spec.ts
    npm run build

Rollback: revert the V95 component, HomePage integration, store return-shape change, and V95 tests/docs together. Do not delete reports, cache, database files, or user data.
