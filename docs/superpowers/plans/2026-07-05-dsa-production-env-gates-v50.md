# DSA Production Env Gates V50

Date: 2026-07-05

Scope: local-only production configuration hardening. This does not deploy production, does not enable real payment, and does not approve public launch.

## Goal

Make production approval gates explicit in `docs/superpowers/platform-production-env.example` so the admin production-readiness preflight does not rely on hidden defaults.

## Required Safe Defaults

- Auth/CSRF enabled.
- Billing disabled and provider set to `disabled`.
- Public SearXNG, fundamental pipeline, chip distribution, and daily market context disabled by default.
- Debug and CORS wildcard disabled.
- Real payment, payment webhook, domain, HTTPS, WAF, market-data license, legal terms, privacy policy, monitoring, and backup/restore approvals all explicitly `false`.
- Not-investment-advice display explicitly `true`.
- Stripe-like real-provider config keys present but blank, so they cannot be mistaken for working credentials.

## Verifier

Add `scripts/verify_platform_production_env_gates_v50.py`.

Expected OK marker:

- `DSA_PLATFORM_PRODUCTION_ENV_GATES_V50_OK`

## Boundaries

- Do not add real API keys, webhook secrets, merchant IDs, domains, or certificates.
- Do not enable real payment or public deployment.
- Do not delete reports, databases, users, API key metadata, billing history, or cache data.
- All analysis remains information-only and not investment advice.
