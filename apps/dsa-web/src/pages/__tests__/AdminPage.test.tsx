import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { UiLanguageProvider } from '../../contexts/UiLanguageContext';
import AdminPage from '../AdminPage';

const { adminUsers, adminUsage, adminBillingEvents, adminLocalStatus, adminProductionReadiness, adminOpsHealth } = vi.hoisted(() => ({
  adminUsers: vi.fn(),
  adminUsage: vi.fn(),
  adminBillingEvents: vi.fn(),
  adminLocalStatus: vi.fn(),
  adminProductionReadiness: vi.fn(),
  adminOpsHealth: vi.fn(),
}));

const { marketSourceHealth, prewarm, recoverMarketSources } = vi.hoisted(() => ({
  marketSourceHealth: vi.fn(),
  prewarm: vi.fn(),
  recoverMarketSources: vi.fn(),
}));

vi.mock('../../api/platform', () => ({
  platformApi: {
    adminUsers,
    adminUsage,
    adminBillingEvents,
    adminLocalStatus,
    adminProductionReadiness,
    adminOpsHealth,
  },
}));

vi.mock('../../api/stocks', () => ({
  stocksApi: {
    marketSourceHealth,
    prewarm,
    recoverMarketSources,
  },
}));

function renderPage() {
  window.localStorage.setItem('dsa.uiLanguage', 'en');
  return render(
    <UiLanguageProvider>
      <AdminPage />
    </UiLanguageProvider>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  adminUsers.mockResolvedValue({
    users: [
      { id: 1, email: 'admin@example.com', role: 'admin', plan: 'enterprise', status: 'active' },
      { id: 2, email: 'user@example.com', role: 'user', plan: 'free', status: 'active' },
    ],
  });
  adminUsage.mockResolvedValue({
    usage: [
      {
        userId: 2,
        email: 'user@example.com',
        plan: 'free',
        quotaBucket: 'ai_quick',
        used: 2,
        weeklyLimit: 5,
        remaining: 3,
        periodStart: '2026-06-29',
      },
      {
        userId: 2,
        email: 'user@example.com',
        plan: 'free',
        quotaBucket: 'ai_deep_user_key',
        used: 1,
        weeklyLimit: 50,
        remaining: 49,
        periodStart: '2026-06-29',
      },
    ],
    auditEvents: [
      {
        id: 9,
        userId: 2,
        action: 'quota_reserved',
        metadata: { quota_bucket: 'ai_quick' },
        createdAt: '2026-07-01T09:00:00',
      },
      {
        id: 10,
        userId: 1,
        action: 'admin_usage_viewed',
        metadata: {},
        createdAt: '2026-07-01T09:05:00',
      },
    ],
  });
  adminBillingEvents.mockResolvedValue({
    events: [
      {
        id: 12,
        userId: 2,
        email: 'user@example.com',
        provider: 'sandbox',
        providerEventId: 'evt_admin_billing',
        providerSessionId: 'sandbox_2_pro_abc',
        eventType: 'checkout.completed',
        plan: 'pro',
        processingStatus: 'processed',
        createdAt: '2026-07-02T10:00:00',
      },
    ],
  });
  adminLocalStatus.mockResolvedValue({
    mode: 'local_only',
    aiUsed: false,
    generatedAt: '2026-07-03T02:00:00Z',
    service: { webui: 'ok', host: '127.0.0.1', port: 8018 },
    auth: { platformUserAuthEnabled: true, adminAuthEnabled: true },
    billing: { enabled: false, provider: 'sandbox', mode: 'local_only' },
    ai: {
      defaultModel: 'deepseek/deepseek-v4-flash',
      localModelEnabled: false,
      byokSupported: true,
      publicSearchEnabled: false,
    },
    market: {
      summary: { laneCount: 4, sourceCount: 8, degradedSourceCount: 1 },
      cache: { mode: 'local_json', storage: 'local_market_cache' },
      lanes: [],
    },
    safety: { noAiStatus: true, secretsRedacted: true, realPaymentEnabled: false },
  });
  adminProductionReadiness.mockResolvedValue({
    mode: 'production_preflight',
    aiUsed: false,
    generatedAt: '2026-07-05T08:00:00Z',
    launchDecision: 'blocked',
    productionReady: false,
    analysisBoundary: 'not_investment_advice',
    summary: { total: 9, passed: 3, blocked: 6, manualActions: 6 },
    checks: [
      {
        id: 'cors_locked_down',
        category: 'security',
        title: 'CORS wildcard disabled',
        status: 'passed',
        severity: 'info',
        message: 'Ready for launch review.',
        evidence: { configured: true },
      },
      {
        id: 'real_payment_disabled',
        category: 'billing',
        title: 'Real payment provider approved',
        status: 'blocked',
        severity: 'critical',
        message: 'No real payment provider is enabled; paid public launch remains blocked.',
        evidence: { providerMode: 'disabled', webhookApproved: false },
      },
      {
        id: 'legal_terms_not_approved',
        category: 'legal',
        title: 'Legal terms approved',
        status: 'blocked',
        severity: 'critical',
        message: 'Terms must be reviewed by humans before public launch.',
        evidence: { configured: false },
      },
      {
        id: 'market_data_license_not_approved',
        category: 'data_sources',
        title: 'Market data commercial license approved',
        status: 'blocked',
        severity: 'critical',
        message: 'Commercial data license approval is missing.',
        evidence: { configured: false },
      },
    ],
    blockingChecks: [],
    manualActions: [],
  });
  adminOpsHealth.mockResolvedValue({
    mode: 'local_ops_health',
    aiUsed: false,
    generatedAt: '2026-07-05T10:00:00Z',
    overallStatus: 'degraded',
    summary: { total: 8, ok: 6, degraded: 2, criticalDegraded: 0 },
    checks: [
      {
        id: 'database_reachable',
        category: 'database',
        title: 'Database reachable',
        status: 'ok',
        severity: 'info',
        message: 'Database is reachable and quick_check is ok.',
        evidence: { reachable: true, quickCheck: 'ok' },
      },
      {
        id: 'billing_provider_readiness',
        category: 'billing',
        title: 'Billing provider readiness',
        status: 'degraded',
        severity: 'warning',
        message: 'Billing provider readiness is visible and sanitized.',
        evidence: { provider: 'stripe', adapterImplemented: false },
      },
      {
        id: 'backup_runner_available',
        category: 'backup',
        title: 'Backup restore dry-run runner available',
        status: 'ok',
        severity: 'info',
        message: 'Backup restore dry-run runner and verifier are available.',
        evidence: { runnerExists: true },
      },
    ],
  });
  marketSourceHealth.mockResolvedValue({
    mode: 'local_only',
    aiUsed: false,
    cache: { mode: 'local_json', storage: 'local_market_cache' },
    lanes: [
      {
        market: 'hk',
        channel: 'hk_equity',
        routeLane: 'hk_market_data',
        quoteSources: [
          {
            source: 'hk_realtime',
            priorityRank: 1,
            status: 'cooling_down',
            consecutiveFailures: 2,
            lastError: 'timeout',
            lastLatencyMs: 4200,
            cooldownRemainingSec: 55,
          },
        ],
        historySources: [
          {
            source: 'hk_history',
            priorityRank: 1,
            status: 'ok',
            consecutiveFailures: 0,
            lastError: null,
            lastLatencyMs: null,
            cooldownRemainingSec: 0,
          },
        ],
      },
    ],
  });
  prewarm.mockResolvedValue({
    requested: 4,
    warmed: 4,
    degraded: 0,
    symbols: ['600519', 'AAPL', 'HK00700', 'BTC-USD'],
    results: {},
    elapsedMs: 123,
    aiUsed: false,
  });
  recoverMarketSources.mockResolvedValue({
    mode: 'local_only',
    action: 'reset_source_health',
    market: 'all',
    resetSources: ['hk_realtime', 'hk_history'],
    resetCount: 2,
    prewarm: {
      requested: 4,
      warmed: 4,
      degraded: 0,
      symbols: ['600519', 'AAPL', 'HK00700', 'BTC-USD'],
      results: {},
      elapsedMs: 88,
      aiUsed: false,
    },
    health: {
      mode: 'local_only',
      aiUsed: false,
      cache: { mode: 'local_json', storage: 'local_market_cache' },
      lanes: [],
    },
    aiUsed: false,
  });
});

describe('AdminPage', () => {
  it('renders platform users, quota buckets, audit events, and billing boundary state', async () => {
    renderPage();

    expect(await screen.findByRole('heading', { name: 'Operations' })).toBeInTheDocument();
    expect(screen.getByText('admin@example.com')).toBeInTheDocument();
    expect(screen.getAllByText('user@example.com')[0]).toBeInTheDocument();
    expect(screen.getByText('Quick AI')).toBeInTheDocument();
    expect(screen.getByText('User API deep AI')).toBeInTheDocument();
    expect(screen.getByText('quota_reserved')).toBeInTheDocument();
    expect(screen.getByText('Billing events')).toBeInTheDocument();
    expect(screen.getByText('checkout.completed')).toBeInTheDocument();
    expect(screen.getByText('evt_admin_billing')).toBeInTheDocument();
    expect(screen.getByText('Local functional status')).toBeInTheDocument();
    expect(screen.getByText('8018')).toBeInTheDocument();
    expect(screen.getByText('No AI status')).toBeInTheDocument();
    expect(screen.getByText('BYOK supported')).toBeInTheDocument();
    expect(screen.getByText('Public search off')).toBeInTheDocument();
    expect(screen.getByText('Real payment off')).toBeInTheDocument();
    expect(screen.getByText('Production readiness')).toBeInTheDocument();
    expect(screen.getByText('Ops health')).toBeInTheDocument();
    expect(screen.getByText('DEGRADED')).toBeInTheDocument();
    expect(screen.getByText('Billing provider readiness')).toBeInTheDocument();
    expect(screen.getAllByText('backup').length).toBeGreaterThan(0);
    expect(screen.getByText('BLOCKED')).toBeInTheDocument();
    expect(screen.getAllByText('security').length).toBeGreaterThan(0);
    expect(screen.getAllByText('billing').length).toBeGreaterThan(0);
    expect(screen.getAllByText('legal').length).toBeGreaterThan(0);
    expect(screen.getAllByText('data_sources').length).toBeGreaterThan(0);
    expect(screen.getByText('No real payment provider is enabled; paid public launch remains blocked.')).toBeInTheDocument();
    expect(screen.getByText('Market source health')).toBeInTheDocument();
    expect(screen.getAllByText('hk_market_data').length).toBeGreaterThan(0);
    expect(screen.getByText('hk_realtime')).toBeInTheDocument();
    expect(screen.getByText('cooling_down')).toBeInTheDocument();
    expect(screen.getAllByText('local_json').length).toBeGreaterThan(0);
  });

  it('reloads admin data when refreshed', async () => {
    renderPage();

    await screen.findByRole('heading', { name: 'Operations' });
    fireEvent.click(screen.getByRole('button', { name: 'Refresh' }));

    await waitFor(() => {
      expect(adminUsers).toHaveBeenCalledTimes(2);
      expect(adminUsage).toHaveBeenCalledTimes(2);
      expect(adminBillingEvents).toHaveBeenCalledTimes(2);
      expect(adminLocalStatus).toHaveBeenCalledTimes(2);
      expect(adminProductionReadiness).toHaveBeenCalledTimes(2);
      expect(adminOpsHealth).toHaveBeenCalledTimes(2);
      expect(marketSourceHealth).toHaveBeenCalledTimes(2);
    });
  });

  it('prewarms local no-AI market cache and refreshes market source health', async () => {
    renderPage();

    await screen.findByRole('heading', { name: 'Operations' });
    fireEvent.click(screen.getByRole('button', { name: 'Prewarm market cache' }));

    await waitFor(() => {
      expect(prewarm).toHaveBeenCalledWith(['600519', 'AAPL', 'HK00700', 'BTC-USD']);
      expect(marketSourceHealth).toHaveBeenCalledTimes(2);
    });
    expect(screen.getByText('Latest prewarm')).toBeInTheDocument();
    expect(screen.getByText('Requested 4')).toBeInTheDocument();
    expect(screen.getByText('Warmed 4')).toBeInTheDocument();
    expect(screen.getByText('Degraded 0')).toBeInTheDocument();
    expect(screen.getByText('No AI used')).toBeInTheDocument();
    expect(screen.getByText('600519, AAPL, HK00700, BTC-USD')).toBeInTheDocument();
  });

  it('recovers local market sources and shows no-AI recovery summary', async () => {
    renderPage();

    await screen.findByRole('heading', { name: 'Operations' });
    fireEvent.click(screen.getByRole('button', { name: 'Recover local sources' }));

    await waitFor(() => {
      expect(recoverMarketSources).toHaveBeenCalledWith({
        market: 'all',
        symbols: ['600519', 'AAPL', 'HK00700', 'BTC-USD'],
        prewarm: true,
      });
      expect(marketSourceHealth).toHaveBeenCalledTimes(2);
    });
    expect(screen.getByText('Latest recovery')).toBeInTheDocument();
    expect(screen.getByText('Reset 2')).toBeInTheDocument();
    expect(screen.getByText('Warmed 4')).toBeInTheDocument();
    expect(screen.getByText('No AI used')).toBeInTheDocument();
    expect(screen.getByText('hk_realtime, hk_history')).toBeInTheDocument();
  });

  it('does not render plaintext secrets from audit metadata', async () => {
    adminUsage.mockResolvedValueOnce({
      usage: [],
      auditEvents: [
        {
          id: 11,
          userId: 2,
          action: 'diagnostic_failed',
          metadata: {
            apiKey: 'sk-admin-leak-123456',
            headers: { Authorization: 'Bearer sk-admin-bearer-abcdef' },
            message: 'provider rejected sk-inline-admin-secret-xyz789',
          },
          createdAt: '2026-07-01T09:10:00',
        },
      ],
    });

    renderPage();

    expect(await screen.findByText('diagnostic_failed')).toBeInTheDocument();
    expect(screen.queryByText(/sk-admin-leak-123456/)).not.toBeInTheDocument();
    expect(screen.queryByText(/sk-admin-bearer-abcdef/)).not.toBeInTheDocument();
    expect(screen.queryByText(/sk-inline-admin-secret-xyz789/)).not.toBeInTheDocument();
    expect(screen.getByText(/\[REDACTED\]/)).toBeInTheDocument();
  });
});
