# DSA Platform Monetization Implementation Plan

> **For agentic workers:** Use `executing-plans` or an available multi-agent workflow to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the local DSA stock analysis system into a multi-user, quota-controlled platform that can support free users, paid users, and user-supplied LLM API keys.

**Architecture:** Add a platform account layer beside the existing local admin layer. Keep admin configuration routes separate from end-user routes, store user/subscription/quota/API-key data in SQLite through `src.storage`, and gate expensive analysis routes before task submission.

**Tech Stack:** FastAPI, SQLAlchemy/SQLite, PBKDF2-HMAC password hashing, HMAC-signed HTTP-only session cookies, React/Vite frontend, existing DSA analysis pipeline.

---

### Task 1: Platform Account And Quota Storage

**Files:**
- Modify: `src/storage.py`
- Create: `src/platform_accounts.py`
- Test: `tests/test_platform_accounts.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_free_user_weekly_quota_blocks_after_limit(tmp_path):
    DatabaseManager.reset_instance()
    db = DatabaseManager(db_url=f"sqlite:///{tmp_path / 'platform.db'}")
    service = PlatformAccountService(db)
    user = service.create_user("free@example.com", "password123")
    service.reserve_analysis_quota(user.id, 5, reason="unit-test")
    with pytest.raises(QuotaExceeded):
        service.reserve_analysis_quota(user.id, 1, reason="unit-test")
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python -m unittest tests.test_platform_accounts`
Expected: import failure for `src.platform_accounts`.

- [ ] **Step 3: Implement storage models and service**

Create tables `platform_users`, `platform_user_api_keys`, and `platform_usage_events`. Implement `PlatformAccountService.create_user`, `verify_login`, `reserve_analysis_quota`, `get_quota_status`, `store_api_key`, `list_api_keys`, and `apply_user_llm_config`.

- [ ] **Step 4: Run the test to verify it passes**

Run: `python -m unittest tests.test_platform_accounts`
Expected: all platform account tests pass.

### Task 2: Platform Auth API And Middleware Boundary

**Files:**
- Create: `api/v1/schemas/platform.py`
- Create: `api/v1/endpoints/platform.py`
- Modify: `api/v1/router.py`
- Modify: `api/middlewares/auth.py`
- Test: `tests/test_platform_api.py`

- [ ] **Step 1: Write failing API tests**

```python
def test_platform_register_login_and_me(client):
    response = client.post("/api/v1/platform/register", json={"email": "u@example.com", "password": "password123"})
    assert response.status_code == 200
    assert response.json()["user"]["email"] == "u@example.com"
    response = client.get("/api/v1/platform/me")
    assert response.status_code == 200
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python -m unittest tests.test_platform_api`
Expected: 404 for `/api/v1/platform/register`.

- [ ] **Step 3: Implement platform endpoints**

Add `/register`, `/login`, `/logout`, `/me`, `/quota`, `/api-keys`, and admin-only `/admin/users`. Use a separate `dsa_user_session` cookie and keep the existing `dsa_session` admin cookie.

- [ ] **Step 4: Run the test to verify it passes**

Run: `python -m unittest tests.test_platform_api`
Expected: platform auth API tests pass.

### Task 3: Analysis Quota Enforcement

**Files:**
- Modify: `api/v1/endpoints/analysis.py`
- Modify: `src/services/task_queue.py`
- Modify: `src/services/analysis_service.py`
- Test: `tests/test_platform_analysis_quota.py`

- [ ] **Step 1: Write failing analysis quota tests**

```python
def test_analysis_rejects_user_without_remaining_quota(client, quota_exhausted_user_cookie):
    response = client.post("/api/v1/analysis/analyze", json={"stock_code": "AAPL", "async_mode": True})
    assert response.status_code == 402
    assert response.json()["error"] == "quota_exceeded"
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python -m unittest tests.test_platform_analysis_quota`
Expected: request is accepted instead of quota-blocked.

- [ ] **Step 3: Implement quota reservation**

Before async task submission, reserve one quota unit per accepted stock request. Preserve admin behavior as unlimited. Pass `platform_user_id` and API key mode into the task so workers can apply user-owned keys.

- [ ] **Step 4: Run the test to verify it passes**

Run: `python -m unittest tests.test_platform_analysis_quota`
Expected: quota-blocked users receive 402 and users with quota consume one unit per accepted task.

### Task 4: User API Key Runtime Selection

**Files:**
- Modify: `api/v1/schemas/analysis.py`
- Modify: `api/v1/endpoints/analysis.py`
- Modify: `src/services/analysis_service.py`
- Test: `tests/test_platform_user_api_keys.py`

- [ ] **Step 1: Write failing runtime override tests**

```python
def test_user_api_key_mode_overrides_deepseek_keys_without_mutating_global_config(tmp_path):
    config = SimpleNamespace(deepseek_api_keys=["platform-key"], report_language="zh")
    scoped = service.apply_user_llm_config(config, user_id, mode="user")
    assert scoped.deepseek_api_keys == ["user-key"]
    assert config.deepseek_api_keys == ["platform-key"]
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python -m unittest tests.test_platform_user_api_keys`
Expected: user runtime override not implemented.

- [ ] **Step 3: Implement request field and config overlay**

Add `api_key_mode: platform|user`, defaulting to `platform`. If `user`, load the active provider key from `platform_user_api_keys` and copy/override the runtime config for that request only.

- [ ] **Step 4: Run the test to verify it passes**

Run: `python -m unittest tests.test_platform_user_api_keys`
Expected: user-owned key mode passes and raw secret is not returned by APIs.

### Task 5: Frontend User Experience

**Files:**
- Create: `apps/dsa-web/src/api/platform.ts`
- Create: `apps/dsa-web/src/stores/platformAuthStore.ts`
- Modify: `apps/dsa-web/src/pages/LoginPage.tsx`
- Modify: `apps/dsa-web/src/pages/HomePage.tsx`
- Modify: `apps/dsa-web/src/pages/SettingsPage.tsx`
- Test: `apps/dsa-web/src/api/__tests__/platform.test.ts`

- [ ] **Step 1: Write failing frontend tests**

```ts
it('shows quota status after login', async () => {
  server.use(mockMe({ plan: 'free', remaining: 3 }));
  render(<HomePage />);
  expect(await screen.findByText(/剩余 3 次/)).toBeInTheDocument();
});
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `npm run test -- src/api/__tests__/platform.test.ts src/pages/__tests__/HomePage.test.tsx`
Expected: missing platform API/store behavior.

- [ ] **Step 3: Implement UI**

Add user login/register, quota badge, API key management, and admin user list. Keep admin settings hidden unless an admin session is present.

- [ ] **Step 4: Build and test**

Run: `npm run test -- src/api/__tests__/platform.test.ts src/pages/__tests__/HomePage.test.tsx && npm run build`
Expected: frontend tests and production build pass.

### Task 6: Payment Provider Boundary

**Files:**
- Create: `src/billing/payment_provider.py`
- Create: `api/v1/endpoints/billing.py`
- Create: `api/v1/schemas/billing.py`
- Test: `tests/test_billing_api.py`

- [ ] **Step 1: Write failing payment tests**

```python
def test_checkout_requires_authenticated_user(client):
    response = client.post("/api/v1/billing/checkout", json={"plan": "premium"})
    assert response.status_code == 401
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python -m unittest tests.test_billing_api`
Expected: billing routes do not exist.

- [ ] **Step 3: Implement provider abstraction**

Add provider-neutral checkout/session/webhook schema. Leave concrete Stripe/国内支付 provider behind env-selected adapters so the platform can choose payment rails later without rewriting quotas.

- [ ] **Step 4: Run billing tests**

Run: `python -m unittest tests.test_billing_api`
Expected: checkout and webhook signature boundaries pass.

---

**Self-review notes:** The plan covers multi-user login, paid/free quota, user-owned API keys, admin operations, analysis gating, and payment boundary. Concrete provider credentials and merchant onboarding are intentionally isolated behind Task 6 because payment rails differ by market and legal entity.
