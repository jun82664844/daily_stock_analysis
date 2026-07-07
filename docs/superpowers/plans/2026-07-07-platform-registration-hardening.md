# DSA Local Registration Hardening

## Goal

Upgrade the local platform registration flow so it feels like a real product account flow while keeping guest stock lookup open.

## Scope

- Add password confirmation in the browser registration form.
- Add a local email verification-code request endpoint.
- Require the browser registration path to submit a verification code.
- Let the backend verify the code when one is provided, and support a strict environment switch for future production/staging gates.
- Keep existing local tests compatible when strict verification is disabled.

## Boundaries

- No real SMTP provider.
- No production deployment, domain, HTTPS, WAF, or payment changes.
- No deletion of user data, history, reports, database files, or API keys.
- Stock analysis output remains information analysis only, not investment advice.

## Verification

- Backend tests cover requesting a registration code, rejecting wrong codes, accepting a valid code, and strict-mode rejection without a code.
- Frontend tests cover confirm-password mismatch, required verification code, sending a local code, and registering with the code.
- Build and live 8018 smoke verify the page can register through the hardened flow.
