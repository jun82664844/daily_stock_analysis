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

  it('loads public Ollama readiness as camelCase', async () => {
    get.mockResolvedValueOnce({
      data: {
        enabled: true,
        reachable: true,
        ready: true,
        quick_ready: true,
        deep_ready: true,
        reason: 'ready',
        runtime: 'ollama',
        quick_model: 'quick-model',
        deep_model: 'deep-model',
        quick_model_available: true,
        deep_model_available: true,
        max_concurrent: 1,
      },
    });

    const result = await platformApi.localModelStatus();

    expect(get).toHaveBeenCalledWith('/api/v1/platform/local-model/status');
    expect(result.quickReady).toBe(true);
    expect(result.deepModel).toBe('deep-model');
    expect(result.maxConcurrent).toBe(1);
  });

  it('requests a local registration verification code as camelCase', async () => {
    post.mockResolvedValueOnce({
      data: {
        email: 'user@example.com',
        sent: true,
        expires_in_seconds: 600,
        dev_code: '123456',
        message: 'Local verification code generated',
      },
    });

    const result = await platformApi.requestRegistrationCode('User@Example.com');

    expect(post).toHaveBeenCalledWith('/api/v1/platform/register/verification-code', {
      email: 'User@Example.com',
    });
    expect(result.email).toBe('user@example.com');
    expect(result.expiresInSeconds).toBe(600);
    expect(result.devCode).toBe('123456');
  });

  it('sends the registration verification code when creating a user', async () => {
    post.mockResolvedValueOnce({
      data: {
        user: { id: 2, email: 'user@example.com', role: 'user', plan: 'free', status: 'active' },
        quota: { user_id: 2, plan: 'free', weekly_limit: 5, used: 0, remaining: 5, period_start: '2026-07-06' },
      },
    });

    const result = await platformApi.register('user@example.com', 'password123', '654321');

    expect(post).toHaveBeenCalledWith('/api/v1/platform/register', {
      email: 'user@example.com',
      password: 'password123',
      verificationCode: '654321',
    });
    expect(result.user.email).toBe('user@example.com');
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

  it('loads the user-scoped watchlist event radar as camelCase', async () => {
    get.mockResolvedValueOnce({
      data: {
        user_id: 15,
        plan: 'free',
        visible_limit: 10,
        total_watchlist: 1,
        processed: 1,
        hidden_count: 0,
        degraded: 0,
        summary: {
          strongest: { stock_code: 'AAPL', stock_name: 'Apple Inc.', change_percent: 3.2 },
          weakest: { stock_code: 'AAPL', stock_name: 'Apple Inc.', change_percent: 3.2 },
          event_count: 1,
          risk_count: 0,
          source_event_count: 0,
        },
        daily_digest: {
          strong_confirmation: [{
            stock_code: 'AAPL',
            stock_name: 'Apple Inc.',
            market: 'us',
            state: 'strong_confirmation',
            priority_score: 92,
            change_percent: 3.2,
            signal_score: 75,
            data_confidence: 'high',
          }],
          risk_review: [],
          wait_for_confirmation: [],
          data_health: { fresh: 1, cached: 0, stale: 0, unavailable: 0 },
          upgrade_boundary: 'same_research_flow_better_sources_and_automation',
          ai_used: false,
        },
        items: [{
          stock_code: 'AAPL',
          stock_name: 'Apple Inc.',
          market: 'us',
          route_lane: 'us_market_data',
          current_price: 210,
          change_percent: 3.2,
          ma20: 205,
          volume_change_percent: 20,
          signal_score: 75,
          freshness: 'fresh',
          degradation_status: 'ok',
          warning_codes: [],
          ai_used: false,
          status: 'ok',
          source_status: 'no_traceable_source',
          research_brief: {
            state: 'strong_confirmation',
            priority_score: 92,
            data_confidence: 'high',
            evidence_codes: ['price_above_ma20', 'volume_expanded', 'usable_data'],
            next_watch: { type: 'hold_above_ma20', value: 205 },
            invalidation: { type: 'lose_ma20', value: 205 },
            ai_used: false,
          },
          events: [{
            stock_code: 'AAPL',
            type: 'price_move',
            severity: 'warning',
            direction: 'up',
            value: 3.2,
            warning_codes: [],
            ai_used: false,
          }],
          suggested_alerts: [{ stock_code: 'AAPL', type: 'ma20_cross', reference_value: 205, ai_used: false }],
        }],
        events: [],
        generated_at: '2026-07-11T09:30:00Z',
        ai_used: false,
        analysis_boundary: 'information_only_not_investment_advice',
      },
    });

    const result = await platformApi.watchlistRadar();

    expect(get).toHaveBeenCalledWith('/api/v1/platform/watchlist/radar');
    expect(result.visibleLimit).toBe(10);
    expect(result.summary.strongest?.stockCode).toBe('AAPL');
    expect(result.items[0].volumeChangePercent).toBe(20);
    expect(result.items[0].suggestedAlerts[0].referenceValue).toBe(205);
    expect(result.dailyDigest.strongConfirmation[0].priorityScore).toBe(92);
    expect(result.dailyDigest.dataHealth.fresh).toBe(1);
    expect(result.items[0].researchBrief.nextWatch.type).toBe('hold_above_ma20');
    expect(result.items[0].researchBrief.evidenceCodes).toContain('volume_expanded');
    expect(result.aiUsed).toBe(false);
  });

  it('loads and marks private price-alert events as camelCase', async () => {
    get.mockResolvedValueOnce({ data: {
      user_id: 15, total: 1, unread: 1, ai_used: false,
      items: [{ id: 81, stock_code: 'AAPL', rule_type: 'price_above', direction: 'above', value: 201.25, threshold: 200, source: 'us_quote', observed_at: '2026-07-13T01:30:00', read_at: null, ai_used: false }],
    } });
    post.mockResolvedValue({ data: { user_id: 15, total: 1, unread: 0, items: [], ai_used: false } });

    const feed = await platformApi.alertEvents(true, 20);
    await platformApi.markAlertEventRead(81);
    await platformApi.markAllAlertEventsRead();

    expect(get).toHaveBeenCalledWith('/api/v1/platform/watchlist/alert-events', { params: { unread_only: true, limit: 20 } });
    expect(post).toHaveBeenNthCalledWith(1, '/api/v1/platform/watchlist/alert-events/81/read');
    expect(post).toHaveBeenNthCalledWith(2, '/api/v1/platform/watchlist/alert-events/read-all');
    expect(feed.items[0].stockCode).toBe('AAPL');
    expect(feed.items[0].observedAt).toBe('2026-07-13T01:30:00');
  });

  it('runs and manages the private V100 watchlist alert loop', async () => {
    post
      .mockResolvedValueOnce({ data: { user_id: 15, run_id: 9, visible_limit: 10, total_watchlist: 0, processed: 0, hidden_count: 0, degraded: 0, summary: { event_count: 0, risk_count: 0, source_event_count: 0 }, items: [], events: [], triggered_alerts: [], generated_at: '2026-07-11T09:30:00Z', ai_used: false, analysis_boundary: 'information_only_not_investment_advice' } })
      .mockResolvedValueOnce({ data: { user_id: 15, plan: 'free', limit: 3, total: 1, remaining: 2, items: [{ id: 31, stock_code: 'AAPL', rule_type: 'ma20_cross', reference_value: 205, enabled: true }], ai_used: false } });
    get
      .mockResolvedValueOnce({ data: { user_id: 15, total: 1, items: [{ id: 9, plan: 'free', processed: 4, event_count: 2, risk_count: 1, source_event_count: 0, triggered_count: 0, created_at: '2026-07-11T09:30:00Z' }], ai_used: false } })
      .mockResolvedValueOnce({ data: { user_id: 15, plan: 'free', limit: 3, total: 0, remaining: 3, items: [], ai_used: false } });
    del.mockResolvedValueOnce({ data: { user_id: 15, plan: 'free', limit: 3, total: 0, remaining: 3, items: [], ai_used: false } });

    const run = await platformApi.runWatchlistRadar();
    const history = await platformApi.watchlistRadarHistory(5);
    const emptyRules = await platformApi.watchlistAlertRules();
    const savedRules = await platformApi.saveWatchlistAlertRule({
      stockCode: 'AAPL',
      ruleType: 'ma20_cross',
      threshold: null,
      referenceValue: 205,
      enabled: true,
    });
    const deletedRules = await platformApi.deleteWatchlistAlertRule(31);

    expect(post).toHaveBeenNthCalledWith(1, '/api/v1/platform/watchlist/radar/run');
    expect(get).toHaveBeenNthCalledWith(1, '/api/v1/platform/watchlist/radar/history', { params: { limit: 5 } });
    expect(get).toHaveBeenNthCalledWith(2, '/api/v1/platform/watchlist/alert-rules');
    expect(post).toHaveBeenNthCalledWith(2, '/api/v1/platform/watchlist/alert-rules', {
      stockCode: 'AAPL',
      ruleType: 'ma20_cross',
      threshold: null,
      referenceValue: 205,
      enabled: true,
    });
    expect(del).toHaveBeenCalledWith('/api/v1/platform/watchlist/alert-rules/31');
    expect(run.runId).toBe(9);
    expect(history.items[0].triggeredCount).toBe(0);
    expect(emptyRules.remaining).toBe(3);
    expect(savedRules.items[0].ruleType).toBe('ma20_cross');
    expect(deletedRules.total).toBe(0);
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

  it('loads production readiness preflight as camelCase', async () => {
    get.mockResolvedValueOnce({
      data: {
        mode: 'production_preflight',
        ai_used: false,
        launch_decision: 'blocked',
        production_ready: false,
        analysis_boundary: 'not_investment_advice',
        summary: { total: 2, passed: 1, blocked: 1, manual_actions: 1 },
        checks: [
          {
            id: 'real_payment_disabled',
            category: 'billing',
            title: 'Real payment provider approved',
            status: 'blocked',
            severity: 'critical',
            message: 'No real payment provider is enabled.',
            evidence: { provider_mode: 'disabled', webhook_approved: false },
          },
        ],
        blocking_checks: [
          {
            id: 'real_payment_disabled',
            category: 'billing',
            title: 'Real payment provider approved',
            status: 'blocked',
            severity: 'critical',
            message: 'No real payment provider is enabled.',
            evidence: { provider_mode: 'disabled', webhook_approved: false },
          },
        ],
        manual_actions: [
          {
            id: 'real_payment_disabled',
            category: 'billing',
            action: 'No real payment provider is enabled.',
          },
        ],
      },
    });

    const result = await platformApi.adminProductionReadiness();

    expect(get).toHaveBeenCalledWith('/api/v1/platform/admin/production-readiness');
    expect(result.aiUsed).toBe(false);
    expect(result.launchDecision).toBe('blocked');
    expect(result.productionReady).toBe(false);
    expect(result.summary.manualActions).toBe(1);
    expect(result.checks[0].evidence?.providerMode).toBe('disabled');
    expect(result.blockingChecks[0].id).toBe('real_payment_disabled');
  });

  it('loads admin ops health as camelCase', async () => {
    get.mockResolvedValueOnce({
      data: {
        mode: 'local_ops_health',
        ai_used: false,
        generated_at: '2026-07-05T10:00:00Z',
        overall_status: 'degraded',
        summary: {
          total: 3,
          ok: 2,
          degraded: 1,
          critical_degraded: 0,
        },
        checks: [
          {
            id: 'billing_provider_readiness',
            category: 'billing',
            title: 'Billing provider readiness',
            status: 'degraded',
            severity: 'warning',
            message: 'Billing provider readiness is visible and sanitized.',
            evidence: {
              adapter_implemented: false,
              missing_config: ['BILLING_STRIPE_WEBHOOK_SECRET'],
            },
          },
        ],
      },
    });

    const result = await platformApi.adminOpsHealth();

    expect(get).toHaveBeenCalledWith('/api/v1/platform/admin/ops-health');
    expect(result.aiUsed).toBe(false);
    expect(result.overallStatus).toBe('degraded');
    expect(result.summary.criticalDegraded).toBe(0);
    expect(result.checks[0].evidence?.adapterImplemented).toBe(false);
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
