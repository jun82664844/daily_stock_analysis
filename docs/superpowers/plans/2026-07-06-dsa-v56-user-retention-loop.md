# DSA V56 Local User Retention Loop Plan

## Scope

V56 keeps the V55 guest-first no-AI query experience, then closes the local ordinary-user retention loop:

- Guest opens Home and runs an AAPL quick snapshot without login.
- Registration or login must not discard the current no-AI snapshot.
- A signed-in ordinary user can save the current no-AI snapshot to their own history.
- A signed-in ordinary user can add the current snapshot symbol to their own watchlist.
- The Home snapshot view shows the distinction between free no-AI quota, platform API AI quota, BYOK AI quota, and local-model quota.
- Logout and login back as the same user must show the saved history/watchlist data, while another user must not see it.

## Non-Goals

- No real payment provider, real merchant account, or production billing copy.
- No real API key, production secret, domain, HTTPS, WAF, email, SMS, or public deployment.
- No deletion of historical reports, user data, database files, static build artifacts, or user files.
- No investment advice. All analysis remains informational only.

## Test-First Slices

1. Backend retention API
   - Add a failing unit test for a login-required endpoint that saves a provided no-AI snapshot into platform-scoped history.
   - Assert the endpoint rejects anonymous calls and AI-used payloads.
   - Assert saved history is visible only to the same platform user.

2. Frontend guest-to-user continuity
   - Add a failing HomePage test for guest AAPL query, registration, retained snapshot, save-to-history, add-to-watchlist, and no secret leakage.
   - Ensure the current snapshot action uses `basicSnapshot.stockCode` when the query input has been reset.

3. Browser smoke path
   - Extend the existing mock Playwright platform E2E so a guest can query first, register, save the current result, add it to watchlist, logout, login, and still see the saved item.
   - Keep the E2E deterministic and mock-backed; it must not use a real API key.

4. V56 verifier
   - Add `scripts/verify_platform_local_user_retention_v56.py`.
   - Check static boundaries, run focused unit tests, and optionally probe a live 8018 URL.
   - Success marker: `DSA_PLATFORM_LOCAL_USER_RETENTION_V56_OK`.

5. Documentation and release manifest
   - Add a concise V56 acceptance note to docs/superpowers.
   - Register the V56 test and verifier in the release package verifier so the dirty package remains explainable.

## Validation Targets

- `python -m unittest tests.test_platform_local_user_retention_v56`
- `python scripts/verify_platform_local_user_retention_v56.py`
- `npm test -- --run src/pages/__tests__/HomePage.test.tsx src/api/__tests__/platform.test.ts`
- `npm run test:smoke`
- Existing V1/V2/release/package verifiers before commit.
