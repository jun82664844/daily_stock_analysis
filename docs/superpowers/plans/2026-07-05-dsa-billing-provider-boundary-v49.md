# DSA Billing Provider Boundary V49

Date: 2026-07-05

Scope: local-only production-readiness hardening for real payment provider boundaries. This does not connect Stripe or any real merchant account, does not process real payment, and does not use real secrets.

## Goal

Make billing provider state explicit and machine-checkable before public launch:

- `disabled`: billing remains unavailable for public payment.
- `sandbox`: local signed test flow only, not real payment.
- `stripe`: recognized as a real provider name, but checkout and webhook stay blocked until required config exists and a real adapter is implemented.

## TDD

Add `tests/test_billing_provider_boundary_v49.py` before implementation. The tests must prove:

- `get_payment_provider_status()` redacts secret values and reports disabled/sandbox/stripe state.
- Missing Stripe-like config returns `billing_provider_not_ready` from checkout without leaking `sk-...` values.
- Fully populated Stripe-like config still returns `billing_provider_adapter_not_implemented` and does not perform network calls or payment processing.
- `/api/v1/billing/account` includes provider readiness metadata without exposing secrets.

Expected RED before implementation: import or assertion failure around provider readiness helpers and endpoint payloads.

## Implementation

- Extend `src/billing/payment_provider.py` with provider status helpers and required-config definitions.
- Update `api/v1/endpoints/billing.py` to route non-sandbox real providers through safe readiness errors instead of a generic 501.
- Update billing account summary to include sanitized provider readiness.
- Keep production readiness V48 billing check aligned with provider status.

## Verifier

Add `scripts/verify_platform_billing_provider_boundary_v49.py`.

Expected OK marker:

- `DSA_PLATFORM_BILLING_PROVIDER_BOUNDARY_V49_OK`

## Boundaries

- No real payment, no real merchant account, no live Stripe calls, no checkout URL to a real provider.
- Do not commit real API Key or webhook secret.
- Do not delete reports, databases, users, API key metadata, billing history, or cache data.
- All analysis remains information-only and not investment advice.
