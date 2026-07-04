import { beforeEach, describe, expect, it, vi } from 'vitest';
import { platformApi } from '../platform';

const get = vi.hoisted(() => vi.fn());
const post = vi.hoisted(() => vi.fn());
const patch = vi.hoisted(() => vi.fn());
const del = vi.hoisted(() => vi.fn());

vi.mock('../index', () => ({
  default: { get, post, patch, delete: del },
}));

describe('platformApi', () => {
  beforeEach(() => {
    get.mockReset();
    post.mockReset();
    patch.mockReset();
    del.mockReset();
  });

  it('loads current user and quota as camelCase', async () => {
    get.mockResolvedValueOnce({
      data: {
        user: { id: 1, email: 'user@example.com', role: 'user', plan: 'free', status: 'active' },
        quota: { user_id: 1, plan: 'free', weekly_limit: 5, used: 1, remaining: 4, period_start: '2026-06-29' },
      },
    });

    const result = await platformApi.me();

    expect(get).toHaveBeenCalledWith('/api/v1/platform/me');
    expect(result.quota.weeklyLimit).toBe(5);
    expect(result.quota.periodStart).toBe('2026-06-29');
  });

  it('stores user API keys without returning plaintext', async () => {
    post.mockResolvedValueOnce({
      data: {
        provider: 'deepseek',
        model: 'deepseek/deepseek-v4-flash',
        masked_key: 'sk-u...cret',
        enabled: true,
      },
    });

    const result = await platformApi.saveApiKey({
      provider: 'deepseek',
      apiKey: 'sk-user-secret',
      model: 'deepseek/deepseek-v4-flash',
    });

    expect(post).toHaveBeenCalledWith('/api/v1/platform/api-keys', {
      provider: 'deepseek',
      apiKey: 'sk-user-secret',
      model: 'deepseek/deepseek-v4-flash',
    });
    expect(JSON.stringify(result)).not.toContain('sk-user-secret');
    expect(result.maskedKey).toBe('sk-u...cret');
    expect(result.model).toBe('deepseek/deepseek-v4-flash');
  });

  it('loads the account summary with quota buckets and masked keys', async () => {
    get.mockResolvedValueOnce({
      data: {
        user: { id: 3, email: 'account@example.com', role: 'user', plan: 'free', status: 'active' },
        quota: { user_id: 3, plan: 'free', weekly_limit: 5, used: 1, remaining: 4, period_start: '2026-06-29' },
        quota_buckets: [
          {
            user_id: 3,
            plan: 'free',
            quota_bucket: 'ai_quick_user_key',
            weekly_limit: 25,
            used: 2,
            remaining: 23,
            period_start: '2026-06-29',
          },
        ],
        api_keys: [
          {
            id: 10,
            provider: 'deepseek',
            model: 'deepseek/deepseek-v4-flash',
            masked_key: 'sk-a...cret',
            enabled: true,
          },
        ],
        recommended_query_mode: 'user',
      },
    });

    const result = await platformApi.account();

    expect(get).toHaveBeenCalledWith('/api/v1/platform/account');
    expect(result.user.email).toBe('account@example.com');
    expect(result.quotaBuckets[0].quotaBucket).toBe('ai_quick_user_key');
    expect(result.apiKeys[0].maskedKey).toBe('sk-a...cret');
    expect(JSON.stringify(result)).not.toContain('sk-account-secret');
    expect(result.recommendedQueryMode).toBe('user');
  });

  it('manages platform watchlist and refreshes no-AI summary as camelCase', async () => {
    get.mockResolvedValueOnce({
      data: {
        user_id: 15,
        total: 1,
        ai_used: false,
        items: [{ id: 1, stock_code: 'HK00700', input_code: 'HK00700', market: 'hk' }],
      },
    });
    post
      .mockResolvedValueOnce({
        data: {
          user_id: 15,
          total: 2,
          ai_used: false,
          items: [
            { id: 1, stock_code: 'HK00700', input_code: 'HK00700', market: 'hk' },
            { id: 2, stock_code: 'BTC-USD', input_code: 'BTC-USD', market: 'crypto' },
          ],
        },
      })
      .mockResolvedValueOnce({
        data: {
          user_id: 15,
          requested: 2,
          refreshed: 2,
          degraded: 1,
          ai_used: false,
          items: [
            {
              stock_code: 'HK00700',
              stock_name: 'Tencent Holdings',
              market: 'hk',
              route_lane: 'hk_market_data',
              current_price: 380,
              change_percent: 0.5,
              freshness: 'fresh',
              degradation_status: 'degraded',
              warning_codes: ['missing_history'],
              ai_used: false,
              status: 'degraded',
            },
          ],
        },
      });
    del.mockResolvedValueOnce({
      data: {
        user_id: 15,
        total: 0,
        ai_used: false,
        items: [],
      },
    });

    const list = await platformApi.watchlist();
    const added = await platformApi.addWatchlistItem('BTC-USD');
    const refreshed = await platformApi.refreshWatchlist();
    const removed = await platformApi.removeWatchlistItem('HK00700');

    expect(get).toHaveBeenCalledWith('/api/v1/platform/watchlist');
    expect(post).toHaveBeenNthCalledWith(1, '/api/v1/platform/watchlist', { stockCode: 'BTC-USD' });
    expect(post).toHaveBeenNthCalledWith(2, '/api/v1/platform/watchlist/refresh');
    expect(del).toHaveBeenCalledWith('/api/v1/platform/watchlist/HK00700');
    expect(list.items[0].stockCode).toBe('HK00700');
    expect(added.items[1].stockCode).toBe('BTC-USD');
    expect(refreshed.items[0].routeLane).toBe('hk_market_data');
    expect(refreshed.items[0].degradationStatus).toBe('degraded');
    expect(refreshed.aiUsed).toBe(false);
    expect(removed.total).toBe(0);
  });

  it('creates a local sandbox checkout session', async () => {
    post.mockResolvedValueOnce({
      data: {
        checkout_url: '/sandbox/checkout/sandbox_3_pro_abc',
        provider_session_id: 'sandbox_3_pro_abc',
        provider: 'sandbox',
        plan: 'pro',
        mode: 'local_sandbox',
      },
    });

    const result = await platformApi.createSandboxCheckout('pro');

    expect(post).toHaveBeenCalledWith('/api/v1/billing/checkout', { plan: 'pro' });
    expect(result.checkoutUrl).toBe('/sandbox/checkout/sandbox_3_pro_abc');
    expect(result.providerSessionId).toBe('sandbox_3_pro_abc');
    expect(result.provider).toBe('sandbox');
  });

  it('loads user billing lifecycle state as camelCase', async () => {
    get.mockResolvedValueOnce({
      data: {
        billing_enabled: true,
        provider: 'sandbox',
        mode: 'local_sandbox',
        copy: 'Local sandbox billing only; not real payment processing.',
        subscription: {
          user_id: 3,
          provider: 'sandbox',
          provider_subscription_id: 'sub_test_1',
          plan: 'pro',
          status: 'active',
          created_at: '2026-07-02T08:00:00',
          updated_at: '2026-07-02T08:05:00',
        },
        checkout_sessions: [
          {
            id: 4,
            user_id: 3,
            provider: 'sandbox',
            provider_session_id: 'sandbox_3_pro_abc',
            checkout_url: '/sandbox/checkout/sandbox_3_pro_abc',
            plan: 'pro',
            status: 'completed',
            created_at: '2026-07-02T08:00:00',
            updated_at: '2026-07-02T08:05:00',
          },
        ],
        recent_events: [
          {
            id: 5,
            user_id: 3,
            provider: 'sandbox',
            provider_event_id: 'evt_completed_once',
            provider_session_id: 'sandbox_3_pro_abc',
            event_type: 'checkout.completed',
            plan: 'pro',
            processing_status: 'processed',
            created_at: '2026-07-02T08:05:00',
          },
        ],
      },
    });

    const result = await platformApi.billingAccount();

    expect(get).toHaveBeenCalledWith('/api/v1/billing/account');
    expect(result.billingEnabled).toBe(true);
    expect(result.subscription.providerSubscriptionId).toBe('sub_test_1');
    expect(result.checkoutSessions[0].providerSessionId).toBe('sandbox_3_pro_abc');
    expect(result.recentEvents[0].providerEventId).toBe('evt_completed_once');
    expect(result.recentEvents[0].eventType).toBe('checkout.completed');
  });

  it('loads admin users as camelCase', async () => {
    get.mockResolvedValueOnce({
      data: {
        users: [
          { id: 1, email: 'admin@example.com', role: 'admin', plan: 'enterprise', status: 'active' },
          { id: 2, email: 'user@example.com', role: 'user', plan: 'free', status: 'active' },
        ],
      },
    });

    const result = await platformApi.adminUsers();

    expect(get).toHaveBeenCalledWith('/api/v1/platform/admin/users');
    expect(result.users).toHaveLength(2);
    expect(result.users[0].email).toBe('admin@example.com');
    expect(result.users[1].plan).toBe('free');
  });

  it('loads admin usage buckets and audit events as camelCase', async () => {
    get.mockResolvedValueOnce({
      data: {
        usage: [
          {
            user_id: 2,
            email: 'user@example.com',
            plan: 'free',
            quota_bucket: 'ai_quick',
            used: 2,
            weekly_limit: 5,
            remaining: 3,
            period_start: '2026-06-29',
          },
        ],
        audit_events: [
          {
            id: 9,
            user_id: 2,
            action: 'quota_reserved',
            metadata: { quota_bucket: 'ai_quick' },
            created_at: '2026-07-01T09:00:00',
          },
        ],
      },
    });

    const result = await platformApi.adminUsage();

    expect(get).toHaveBeenCalledWith('/api/v1/platform/admin/usage');
    expect(result.usage[0].userId).toBe(2);
    expect(result.usage[0].quotaBucket).toBe('ai_quick');
    expect(result.auditEvents[0].createdAt).toBe('2026-07-01T09:00:00');
  });

  it('loads admin billing events as camelCase', async () => {
    get.mockResolvedValueOnce({
      data: {
        events: [
          {
            id: 7,
            user_id: 2,
            email: 'user@example.com',
            provider: 'sandbox',
            provider_event_id: 'evt_admin_billing',
            provider_session_id: 'sandbox_2_pro_abc',
            event_type: 'checkout.completed',
            plan: 'pro',
            processing_status: 'processed',
            created_at: '2026-07-02T10:00:00',
          },
        ],
      },
    });

    const result = await platformApi.adminBillingEvents();

    expect(get).toHaveBeenCalledWith('/api/v1/billing/admin/events');
    expect(result.events[0].userId).toBe(2);
    expect(result.events[0].providerEventId).toBe('evt_admin_billing');
    expect(result.events[0].eventType).toBe('checkout.completed');
  });

  it('loads local functional status as camelCase without plaintext secrets', async () => {
    get.mockResolvedValueOnce({
      data: {
        mode: 'local_only',
        ai_used: false,
        service: { webui: 'ok', host: '127.0.0.1', port: 8018 },
        auth: { platform_user_auth_enabled: true, admin_auth_enabled: true },
        billing: { enabled: false, provider: 'sandbox', mode: 'local_only' },
        ai: {
          default_model: 'deepseek/deepseek-v4-flash',
          local_model_enabled: false,
          byok_supported: true,
          public_search_enabled: false,
        },
        market: {
          summary: { lane_count: 4, degraded_source_count: 1 },
          cache: { mode: 'local_json', storage: 'local_market_cache' },
          lanes: [],
        },
        safety: { no_ai_status: true, secrets_redacted: true, real_payment_enabled: false },
      },
    });

    const result = await platformApi.adminLocalStatus();

    expect(get).toHaveBeenCalledWith('/api/v1/platform/admin/local-status');
    expect(result.mode).toBe('local_only');
    expect(result.aiUsed).toBe(false);
    expect(result.service.port).toBe(8018);
    expect(result.auth.platformUserAuthEnabled).toBe(true);
    expect(result.ai.defaultModel).toBe('deepseek/deepseek-v4-flash');
    expect(result.market.summary.degradedSourceCount).toBe(1);
    expect(result.safety.realPaymentEnabled).toBe(false);
    expect(JSON.stringify(result)).not.toContain('sk-');
  });
});
