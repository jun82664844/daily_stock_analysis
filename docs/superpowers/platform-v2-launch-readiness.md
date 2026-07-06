# DSA Platform V2 Launch Readiness

Date: 2026-07-01

Scope: release-candidate preparation for platform evaluation only. This package does not approve public launch, does not connect real payment, does not deploy a public service, and does not use production secrets.

## V1 completed

- Local V1 platform auth, local admin auth, CSRF boundaries, user API key custody, plan/quota buckets, BYOK accounting, local-model accounting, admin users/usage/audit views, and billing-disabled contract routes have passing local tests.
- User-owned API keys are encrypted at rest and only masked metadata is returned through APIs.
- Audit metadata is redacted before storage and redacted again before AdminPage rendering.
- Ordinary platform users now have a local account center for own profile, quota buckets, masked API key custody state, and sandbox checkout initiation.
- Local sandbox billing can create mock checkout sessions and process signed test webhooks for free-to-pro upgrade verification when explicitly enabled with `BILLING_PROVIDER=sandbox`.
- Query Quality V4 adds local market-aware quick-query routing for A-share, US equity, HK equity, and crypto spot symbols; no-AI snapshots expose quote freshness, deterministic indicators, route lanes, and degradation warnings.
- The default V1 operability verifier covers backend gates, frontend admin tests, production build, and live local health/admin shell checks.

## V2 before launch

- Replace template placeholders with production configuration managed by a protected secret store or deployment environment.
- Run `scripts/verify_platform_v2_readiness.py` against the release candidate and any proposed env file before a launch review.
- Complete production database backup, restore, migration, retention, and rollback drills on staging copies.
- Add HTTPS, real domain, reverse proxy, WAF/CDN policy, production log retention, audit export controls, and dependency/container/exposed-route scans.
- Add real payment provider only after merchant, pricing, webhook reconciliation, refund, invoice, and compliance decisions are approved.
- Add email verification, password reset, account recovery, and external login/SSO only after product and security review.
- Ensure every user-facing analysis surface states that output is for information only and is not investment advice.
- Before public launch, run load/error-path evaluation for quick-query market data sources, public search degradation, AI timeout handling, and quota-cost dashboards on staging data.

## No-go

- No public launch if `ADMIN_AUTH_ENABLED`, `PLATFORM_USER_AUTH_ENABLED`, or `PLATFORM_CSRF_ENABLED` is false.
- No public launch if `BILLING_ENABLED=true` without a real provider contract, signed webhook validation, reconciliation tests, and rollback plan.
- No public launch by treating the local sandbox payment provider as production payment. Sandbox billing is test-only.
- No public launch by treating `BILLING_PROVIDER=stripe` config detection as a live payment adapter. The local boundary must still fail closed until the real adapter and merchant controls are reviewed.
- No public launch with real API keys committed to the repository, docs, screenshots, logs, or frontend state.
- No public launch with public SearXNG auto-discovery enabled by default.
- No public launch if quick-query market routing can silently call AI, hide stale/missing market data, or consume paid model quota without explicit user action.
- No public launch without database backup/restore proof on a staging copy.
- No public launch without legal, privacy, and not investment advice copy approved by humans.
- No public launch while dirty/untracked V1 platform files remain unreviewed and uncommitted.
- No public launch while the admin production-readiness preflight reports `launch_decision=blocked`.

## Manual decisions

- Final plan names, free/pro/enterprise quota numbers, paid limits, abuse thresholds, and pricing.
- Payment provider, merchant entity, refund policy, invoice/tax handling, and user account upgrade process.
- Production hosting, domain, TLS certificate, WAF/CDN, monitoring, alerting, and incident-response ownership.
- Data retention periods for audit logs, analysis history, user accounts, API key metadata, and billing events.
- Legal terms, privacy policy, risk disclaimers, and wording for not investment advice.

## Release candidate checklist

- V1 verification commands still pass.
- V2 readiness verifier passes with the production-evaluation env template.
- Query Quality V4 verifier passes and prints `DSA_PLATFORM_QUERY_QUALITY_V4_OK`.
- Local History Center V24 verifier passes and prints `DSA_PLATFORM_LOCAL_HISTORY_CENTER_V24_OK`.
- Production Readiness V48 verifier passes and prints `DSA_PLATFORM_PRODUCTION_READINESS_V48_OK`, while still reporting blocked launch until external approvals are complete.
- Billing Provider Boundary V49 verifier passes and prints `DSA_PLATFORM_BILLING_PROVIDER_BOUNDARY_V49_OK`, while real provider config remains fail-closed until a live adapter is implemented.
- Production Env Gates V50 verifier passes and prints `DSA_PLATFORM_PRODUCTION_ENV_GATES_V50_OK`, while all public-launch approval gates remain explicit safe defaults until humans approve evidence.
- Backup Restore Drill V51 verifier passes and prints `DSA_PLATFORM_BACKUP_RESTORE_DRILL_V51_OK` on temporary databases; a staging-copy restore record is still required before public launch.
- Ops Health V52 verifier passes and prints `DSA_PLATFORM_OPS_HEALTH_V52_OK`, while real production monitoring/alerting remains a human No-go item.
- Ops Health Panel V53 verifier passes and prints `DSA_PLATFORM_OPS_HEALTH_PANEL_V53_OK`, showing local ops health in AdminPage without treating it as production monitoring.
- Backup/restore dry-run passes and staging-copy restore is scheduled before launch.
- Migration schema check confirms platform tables and `analysis_history.platform_user_id`.
- Dirty handoff is reviewed and split into intentional commits before any release tag.
