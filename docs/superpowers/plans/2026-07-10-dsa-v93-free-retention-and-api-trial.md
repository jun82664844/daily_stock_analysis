# DSA V93 Free Retention And API Trial Implementation Plan

> Local-only product work. Real payment, production deployment, production keys, and public launch remain out of scope.

**Goal:** Make the free experience useful enough to create repeat visits while giving free users a small, explicit platform-API trial and preserving premium access to both platform API and BYOK.

**Architecture:** Keep the existing no-AI snapshot as the unlimited acquisition lane. Expose the already-defined free `ai_quick` quota as a separate platform-API trial action, keep deep analysis and larger quotas as account upgrades, store same-symbol observations in versioned browser storage, reuse the private watchlist refresh API for a daily review, and add a Yahoo Chart history fallback for US/HK symbols when the normal history manager returns no rows.

**Tech Stack:** FastAPI/Python, React/TypeScript, Zustand, Vitest/Testing Library, unittest.

---

## Task 1: Lock Product And Data Boundaries With Failing Tests

- Add backend tests for free/pro quota policy and US/HK Yahoo history fallback.
- Add frontend model tests for first query, unchanged query, changed query, and symbol-isolated storage.
- Add HomePage integration coverage proving the API trial submits `analysisDepth=fast` and `apiKeyMode=platform`.
- Run focused tests and retain the expected RED evidence before implementation.

## Task 2: Expose The Free Platform API Trial

- Add a dedicated API trial panel after a free snapshot.
- Guests see a login/register action without losing no-AI access.
- Free members see the remaining weekly platform API trial count.
- Paid members see their larger platform API quick quota and can still select BYOK or local model.
- Keep no-AI quick analysis visually and behaviorally separate from API-backed AI trial analysis.

## Task 3: Add Same-Symbol Query Change Tracking

- Build a versioned, bounded local observation store with no secrets or account data.
- Compare price, daily change, MA20 position, signal score, freshness, warnings, and volume signal.
- Render a concise “since last query” strip and clearly label first-observation and unchanged states.
- Keep the content bilingual and informational-only.

## Task 4: Turn Watchlist Refresh Into A Daily Return Loop

- Reuse the existing private watchlist and no-AI refresh endpoint.
- Present the action as a daily review and summarize strongest move, weakest move, and degraded symbols.
- Keep click-through to the existing symbol query.
- Do not duplicate or expose another user’s watchlist.

## Task 5: Improve Free K-Line Reliability For US And HK Symbols

- Add a bounded Yahoo Chart daily-history fallback after the normal data manager returns no rows or fails.
- Preserve honest source labels and return an empty dataset when both lanes fail.
- Do not route A-share symbols through the US/HK fallback.

## Task 6: Verify, Review, And Commit A Clean Local Milestone

- Run focused backend and frontend tests first.
- Run the broader platform backend suite, HomePage suite, frontend build, local verifiers, and `git diff --check`.
- Restart/reload port 8018 if required and browser-test guest, free member, paid-member mode choices, same-symbol repeat query, watchlist review, and mobile layout.
- Review the diff for secret leakage, destructive data operations, and accidental production scope.
- Create one local commit only after all gates pass; do not push.

## Acceptance Criteria

- Unlimited no-AI lookup/quick research remains usable without login.
- A free signed-in user can intentionally consume one of 5 weekly platform API quick trials.
- The trial action cannot be confused with no-AI quick analysis.
- Pro users retain platform API, BYOK, and local model choices with larger quota buckets.
- Repeating a symbol query shows a useful comparison against the prior browser observation.
- Watchlist refresh produces a compact daily review summary.
- US/HK daily history falls back to Yahoo Chart when the primary history lane is empty.
- No real payment, production key, deployment, user-data deletion, or investment-advice claim is introduced.
- Final tree is clean and the local commit is reversible.
