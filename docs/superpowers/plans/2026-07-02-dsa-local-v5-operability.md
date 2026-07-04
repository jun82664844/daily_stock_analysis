# DSA Local V5 Operability Implementation Plan

> **For agentic workers:** Use `executing-plans` or an available multi-agent workflow to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make local-only live smoke verification easier by allowing an explicit verifier flag to create a disposable platform smoke user for authenticated snapshot checks.

**Architecture:** Keep production behavior unchanged. Extend `scripts/verify_local_v1_operability.py` with an opt-in `--auto-smoke-user` flag that registers an `e2e+local-smoke...` user through the local running API only when live snapshot auth is required and no smoke credentials are provided. Keep the default behavior as skip-with-guidance.

**Tech Stack:** Python `unittest`, FastAPI local HTTP endpoints, existing platform cookie auth, existing E2E cleanup namespace.

---

### Task 1: Add Auto Smoke User Test

**Files:**
- Modify: `tests/test_local_v1_operability.py`
- Modify: `scripts/verify_local_v1_operability.py`

- [ ] **Step 1: Write the failing test**

Add a unit test showing that an authenticated live snapshot can proceed without environment credentials when `auto_smoke_user=True`. The fake opener should receive a register request first and a snapshot request second; the generated password must not appear in result output or metadata.

- [ ] **Step 2: Run the focused test and verify it fails**

Run:

```powershell
& "C:\Users\26879\Documents\Codex\2026-06-05\https-x-com-wy-mask-status\work\dsa-venv\Scripts\python.exe" -m unittest tests.test_local_v1_operability.LocalV1OperabilityCheckTestCase.test_optional_live_snapshot_can_auto_register_local_smoke_user_when_explicitly_enabled
```

Expected: fail because `_run_url_check` does not yet accept or use `auto_smoke_user`.

- [ ] **Step 3: Implement minimal code**

Add `auto_smoke_user` plumbing to `run_operability_checks`, `_run_url_check`, and the CLI. Add a helper that registers a unique `e2e+local-smoke-<timestamp>-<nonce>@example.com` account with a generated password and reuses the registration cookie for the snapshot request.

- [ ] **Step 4: Run focused tests**

Run:

```powershell
& "C:\Users\26879\Documents\Codex\2026-06-05\https-x-com-wy-mask-status\work\dsa-venv\Scripts\python.exe" -m unittest tests.test_local_v1_operability
```

Expected: pass.

### Task 2: Document Local-Only Boundary

**Files:**
- Modify: `docs/superpowers/platform-local-v1-operability.md`
- Modify: `docs/superpowers/platform-release-candidate-manifest.md`

- [ ] **Step 1: Update local operability docs**

Document that `--auto-smoke-user` is opt-in, local-only, creates only `e2e+local-smoke...` platform users, does not use real API keys, does not delete data, and can be inspected through the existing cleanup dry-run.

- [ ] **Step 2: Update release candidate package docs**

Ensure the new behavior remains covered by the existing `tests/test_local_v1_operability.py` and release package verifier inventory.

- [ ] **Step 3: Run focused verification**

Run:

```powershell
& "C:\Users\26879\Documents\Codex\2026-06-05\https-x-com-wy-mask-status\work\dsa-venv\Scripts\python.exe" -m unittest tests.test_local_v1_operability
& "C:\Users\26879\Documents\Codex\2026-06-05\https-x-com-wy-mask-status\work\dsa-venv\Scripts\python.exe" scripts\verify_local_v1_operability.py --dry-run --json
git diff --check
```

Expected: tests pass, dry-run remains non-mutating, and diff check has no whitespace errors.

### Pause Conditions

- Pause before deleting any user, report, database row, or historical analysis.
- Pause before touching production deployment, real payment, real merchant configuration, real secrets, domain, HTTPS, WAF, email, SMS, legal copy, or commercial pricing.
- Pause if the local running service is unavailable or if the verifier would need a real API key.

---

## Local Functional V5 Aggregate Update

This plan is extended by `scripts/verify_platform_local_functional_v5.py`, which is the local-only aggregate gate for the V5 functional smoke package.

Required local checks:

- Local 8018 `/health` and SPA page shell.
- `e2e+local-v5...` platform register/login smoke without printing generated passwords.
- Ordinary user account/API boundary, including admin API denial.
- Deterministic unit coverage for quick/no-AI A-share, US, HK, and crypto route lanes.
- Deterministic unit coverage for platform deep, BYOK deep, and local model quota buckets.
- Platform-user history isolation and sandbox billing summary.
- Existing V4 query quality, platform user E2E, billing lifecycle, and release package verifiers.

Success marker: `DSA_PLATFORM_LOCAL_FUNCTIONAL_V5_OK`.

No-go remains unchanged: this is local functional verification only, not real payment, not public deployment, not production secret use, and not investment advice. Do not commit real API Key.
