# DSA Platform Local V1 Security Checklist

Date: 2026-07-01

Scope: local-first platform development. Payment, public deployment, merchant onboarding, CDN/WAF, and production compliance are V2 work.

## Local V1 Completed Gates

- Platform user auth can be enabled with `PLATFORM_USER_AUTH_ENABLED=true`.
- Existing local admin auth remains separate from platform user auth.
- Free, pro, premium-compatible, and enterprise quota plans are enforced before expensive analysis work.
- Platform users can choose platform API mode, their own encrypted API key mode, or local model mode.
- Platform API mode, BYOK mode, and local model mode use separate quota buckets for model-cost and abuse-control accounting.
- User API keys are encrypted at rest and are not returned in API responses.
- User API key audit metadata is recursively redacted, including nested headers and inline token-like diagnostic strings.
- Admin console audit metadata is redacted again before rendering as a frontend safety net.
- CSRF protection is available for cookie-authenticated write endpoints with `PLATFORM_CSRF_ENABLED=true`.
- Platform login and local admin login both issue a readable CSRF cookie; platform logout and local admin logout clear it.
- Local admin cookie writes and platform user cookie writes reject missing or mismatched CSRF headers when CSRF is enabled.
- Async stock-analysis tasks are tagged with `platform_user_id` in both platform API mode and user API key mode.
- Persisted stock-analysis and market-review history rows can be tagged with `platform_user_id`.
- Market-review background tasks are tagged with the current platform user.
- Platform users only see their own task list, task status, task run-flow, and SSE task events.
- Platform users only see and delete their own history reports; existing admin sessions keep global history access.
- Existing admin session and platform admin role can still inspect global task state.
- Existing admin session and platform admin role can view platform users, usage buckets, and audit events.
- Existing admin session and platform admin role can change user plans while ordinary platform users cannot.
- Platform login now rate-limits repeated bad-password attempts and clears the limit after successful login.
- Public SearXNG, fundamental pipeline, chip distribution, and daily market context are disabled by default for fast local use.

## Verification Commands

```powershell
& "C:\Users\26879\Documents\Codex\2026-06-05\https-x-com-wy-mask-status\work\dsa-venv\Scripts\python.exe" scripts\verify_local_v1_operability.py
& "C:\Users\26879\Documents\Codex\2026-06-05\https-x-com-wy-mask-status\work\dsa-venv\Scripts\python.exe" -m unittest tests.test_platform_api tests.test_platform_accounts tests.test_platform_security_boundaries tests.test_platform_api_keys_product tests.test_platform_audit tests.test_platform_feature_policy tests.test_billing_api tests.test_local_v1_operability
cd apps\dsa-web
npm test -- --run src/api/__tests__/index.test.ts src/api/__tests__/platform.test.ts src/pages/__tests__/AdminPage.test.tsx
npm run build
```

## V2 Before Public Launch

- Put the app behind HTTPS and a reverse proxy.
- Move production secrets to a managed secret store or production environment variables with rotation.
- Add database migration, backup, and restore procedures.
- Add production audit retention, export controls, and alerting.
- Add stronger per-user and per-IP API rate limits for analysis endpoints.
- Add payment provider abstraction, checkout, webhook signature verification, and plan upgrade reconciliation.
- Add legal copy that clearly states analysis output is informational and not investment advice.
- Add production email verification, password reset, and account recovery flows.
- Run dependency, container, and exposed-route security scans before opening public access.
