# DSA Platform V2 Handoff Status

Date: 2026-07-01

Scope: read-only dirty work handoff for the platform V2 preparation package. This document records current workspace distribution and does not delete, revert, commit, or rewrite user files.

## Dirty snapshot

Observed with `git status --short` before adding the V2 readiness package:

- modified: 32
- untracked: 34
- deleted: 0
- total dirty entries: 66

Top-level distribution:

- apps: 22
- src: 14
- tests: 14
- api: 12
- scripts: 1
- docs: 1
- `.gitignore`: 1
- `requirements.txt`: 1

Current recheck with `git status --short --untracked-files=all` after adding the V2 readiness package:

- modified: 32
- untracked: 44
- deleted: 0
- total dirty entries: 76

Current top-level distribution:

- apps: 22
- src: 15
- tests: 14
- api: 12
- docs: 9
- scripts: 2
- `.gitignore`: 1
- `requirements.txt`: 1

## V1 platform related

The following dirty/untracked groups are part of the V1 platform foundation and should be reviewed together before packaging:

- `api/v1/endpoints/platform.py`, `api/v1/endpoints/billing.py`, platform schemas, router, auth middleware, and CSRF helper.
- `src/platform_accounts.py`, `src/platform_audit.py`, `src/platform_feature_policy.py`, `src/billing/`, `src/llm/local_model_router.py`.
- `tests/test_platform_*`, `tests/test_billing_api.py`, `tests/test_local_v1_operability.py`, local model and no-AI market snapshot tests.
- `apps/dsa-web/src/api/platform.ts`, `AdminPage.tsx`, AdminPage tests, platform API tests, and related navigation/UI files.
- `docs/superpowers/` V1 acceptance, security, operability, product rules, and plan documentation.
- `scripts/verify_local_v1_operability.py`.

## V2 readiness additions

The V2 preparation package adds or updates:

- `scripts/verify_platform_v2_readiness.py`
- `docs/superpowers/platform-production-env.example`
- `docs/superpowers/platform-v2-launch-readiness.md`
- `docs/superpowers/platform-legal-copy-draft.md`
- `docs/superpowers/platform-v2-handoff-status.md`
- `tests/test_local_v1_operability.py` coverage for the V2 readiness verifier.
- `.gitignore` keeps `scripts/verify_platform_v2_readiness.py` visible for handoff despite the broader `verify_*.py` ignore rule.

## Packaging guidance

- Do not delete historical reports, databases, `static` build output, user files, or untracked platform files.
- do not delete this dirty tree as cleanup; split it into reviewed commits only after V1/V2 verification is rerun.
- Keep V1 platform code, V2 readiness docs/scripts, and unrelated pre-existing changes as separate review slices where possible.
- Before any release tag, rerun V1 verification, V2 readiness verification, frontend build, and `git diff --check`.
