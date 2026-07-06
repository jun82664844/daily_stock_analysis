import { expect, test, type Page, type Route } from '@playwright/test';

test.skip(!process.env.DSA_PLATFORM_E2E, 'Set DSA_PLATFORM_E2E=1 to run platform user E2E tests.');

test.use({
  locale: 'en-US',
  screenshot: 'off',
  video: 'off',
  trace: 'off',
});

type QuotaBucket = 'basic_query' | 'ai_quick' | 'ai_quick_user_key' | 'ai_deep' | 'ai_deep_user_key' | 'ai_local' | 'market_review';

type MockApiKey = {
  id: number;
  provider: string;
  model: string | null;
  maskedKey: string;
  enabled: boolean;
  createdAt: string;
  updatedAt: string;
};

type MockHistory = {
  id: number;
  queryId: string;
  stockCode: string;
  stockName: string;
  reportType: string;
  createdAt: string;
  sentimentScore: number;
  operationAdvice: string;
  analysisSummary: string;
  action: string;
  actionLabel: string;
};

type MockUser = {
  id: number;
  email: string;
  password: string;
  role: 'user';
  plan: 'free' | 'pro';
  status: 'active';
  apiKeys: MockApiKey[];
  usage: Record<QuotaBucket, number>;
  histories: MockHistory[];
  watchlist: string[];
};

type MockBackend = {
  getUserByEmail: (email: string) => MockUser | undefined;
  getCurrentUser: () => MockUser | null;
};

const quotaBuckets: QuotaBucket[] = [
  'basic_query',
  'ai_quick',
  'ai_quick_user_key',
  'ai_deep',
  'ai_deep_user_key',
  'ai_local',
  'market_review',
];

function createUsage(): Record<QuotaBucket, number> {
  return Object.fromEntries(quotaBuckets.map((bucket) => [bucket, 0])) as Record<QuotaBucket, number>;
}

function maskKey(secret: string): string {
  return secret.length <= 8 ? '*'.repeat(secret.length) : `${secret.slice(0, 4)}...${secret.slice(-4)}`;
}

function weeklyLimitForPlan(plan: MockUser['plan']): number {
  return plan === 'pro' ? 500 : 5;
}

function quotaPayload(user: MockUser) {
  const used = user.usage.ai_quick + user.usage.ai_quick_user_key + user.usage.ai_deep + user.usage.ai_deep_user_key + user.usage.ai_local;
  const weeklyLimit = weeklyLimitForPlan(user.plan);
  return {
    user_id: user.id,
    plan: user.plan,
    weekly_limit: weeklyLimit,
    used,
    remaining: weeklyLimit - used,
    period_start: '2026-06-29',
  };
}

function accountPayload(user: MockUser) {
  return {
    user: userPayload(user),
    quota: quotaPayload(user),
    quota_buckets: quotaBuckets.map((bucket) => {
      const weeklyLimit = bucket === 'basic_query' ? 500 : weeklyLimitForPlan(user.plan);
      const used = user.usage[bucket];
      return {
        user_id: user.id,
        plan: user.plan,
        quota_bucket: bucket,
        weekly_limit: weeklyLimit,
        used,
        remaining: weeklyLimit - used,
        period_start: '2026-06-29',
      };
    }),
    api_keys: user.apiKeys,
    recommended_query_mode: user.apiKeys.some((item) => item.enabled) ? 'user' : 'platform',
  };
}

function userPayload(user: MockUser) {
  return {
    id: user.id,
    email: user.email,
    role: user.role,
    plan: user.plan,
    status: user.status,
  };
}

function authPayload(user: MockUser) {
  return {
    user: userPayload(user),
    quota: quotaPayload(user),
  };
}

function json(route: Route, data: unknown, status = 200) {
  return route.fulfill({
    status,
    contentType: 'application/json',
    body: JSON.stringify(data),
  });
}

async function readJson(route: Route): Promise<Record<string, unknown>> {
  return JSON.parse(route.request().postData() || '{}') as Record<string, unknown>;
}

function reportFor(history: MockHistory) {
  return {
    meta: {
      id: history.id,
      query_id: history.queryId,
      stock_code: history.stockCode,
      stock_name: history.stockName,
      report_type: history.reportType,
      report_language: 'en',
      created_at: history.createdAt,
      current_price: 1688.5,
      change_pct: 1.2,
      model_used: 'deepseek/deepseek-v4-flash',
    },
    summary: {
      analysis_summary: history.analysisSummary,
      operation_advice: history.operationAdvice,
      action: history.action,
      action_label: history.actionLabel,
      trend_prediction: 'sideways',
      sentiment_score: history.sentimentScore,
      sentiment_label: 'Neutral',
    },
    strategy: {
      ideal_buy: 'Informational mock range only.',
      secondary_buy: 'Informational mock range only.',
      stop_loss: 'Informational mock risk boundary only.',
      take_profit: 'Informational mock range only.',
    },
    details: {
      news_content: 'Mock E2E news context. Informational only; not investment advice.',
      raw_result: {},
    },
  };
}

function snapshotMetaFor(code: string) {
  if (code === 'AAPL') {
    return {
      stockName: 'Apple',
      market: 'us',
      normalizedCode: 'AAPL',
      channel: 'us_equity',
      lane: 'us_market_data',
      quoteSources: ['yahoo_chart'],
      historySources: ['yfinance'],
    };
  }
  if (code === 'HK00700') {
    return {
      stockName: 'Tencent Holdings',
      market: 'hk',
      normalizedCode: '0700.HK',
      channel: 'hk_equity',
      lane: 'hk_market_data',
      quoteSources: ['yahoo_chart'],
      historySources: ['yfinance'],
    };
  }
  if (code === 'BTC-USD') {
    return {
      stockName: 'Bitcoin',
      market: 'crypto',
      normalizedCode: 'BTC-USD',
      channel: 'crypto_spot',
      lane: 'crypto_market_data',
      quoteSources: ['crypto_yahoo_chart'],
      historySources: ['crypto_yahoo_chart'],
    };
  }
  return {
    stockName: 'Kweichow Moutai',
    market: 'cn',
    normalizedCode: code.includes('.') ? code : `${code}.SH`,
    channel: 'a_share_equity',
    lane: 'a_share_market_data',
    quoteSources: ['akshare'],
    historySources: ['akshare'],
  };
}

function historyListPayload(user: MockUser | null, url: URL) {
  if (!user || url.searchParams.get('report_type') === 'market_review') {
    return { total: 0, page: 1, limit: 20, items: [] };
  }
  return {
    total: user.histories.length,
    page: Number(url.searchParams.get('page') || 1),
    limit: Number(url.searchParams.get('limit') || 20),
    items: user.histories.map((history) => ({
      id: history.id,
      query_id: history.queryId,
      stock_code: history.stockCode,
      stock_name: history.stockName,
      report_type: history.reportType,
      trend_prediction: 'sideways',
      analysis_summary: history.analysisSummary,
      sentiment_score: history.sentimentScore,
      operation_advice: history.operationAdvice,
      action: history.action,
      action_label: history.actionLabel,
      current_price: 1688.5,
      change_pct: 1.2,
      model_used: 'deepseek/deepseek-v4-flash',
      created_at: history.createdAt,
    })),
  };
}

async function installMockBackend(page: Page): Promise<MockBackend> {
  const users = new Map<string, MockUser>();
  let currentUserId: number | null = null;
  let nextUserId = 1;
  let nextApiKeyId = 1;
  let nextHistoryId = 100;
  let pendingStreamResolvers: Array<(task: Record<string, unknown>) => void> = [];

  const getCurrentUser = () => {
    if (currentUserId === null) {
      return null;
    }
    return [...users.values()].find((user) => user.id === currentUserId) ?? null;
  };

  const completePendingStreams = (task: Record<string, unknown>) => {
    const resolvers = pendingStreamResolvers;
    pendingStreamResolvers = [];
    resolvers.forEach((resolve) => resolve(task));
  };

  await page.addInitScript(() => {
    window.localStorage.setItem('dsa.uiLanguage', 'en');
  });

  await page.route('**/api/v1/**', async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname;
    const method = request.method();
    const currentUser = getCurrentUser();

    if (path === '/api/v1/analysis/tasks/stream') {
      const task = await new Promise<Record<string, unknown>>((resolve) => {
        pendingStreamResolvers.push(resolve);
      });
      return route.fulfill({
        status: 200,
        headers: {
          'content-type': 'text/event-stream; charset=utf-8',
          'cache-control': 'no-cache',
        },
        body: [
          'event: connected',
          'data: {}',
          '',
          'event: task_completed',
          `data: ${JSON.stringify(task)}`,
          '',
          '',
        ].join('\n'),
      });
    }

    if (path === '/api/v1/auth/status') {
      return json(route, {
        authEnabled: false,
        loggedIn: false,
        passwordSet: false,
        passwordChangeable: false,
        setupState: 'no_password',
      });
    }
    if (path === '/api/v1/platform/status') {
      return json(route, { platform_auth_enabled: true });
    }
    if (path === '/api/v1/system/config/setup/status') {
      return json(route, { is_complete: true, checks: [] });
    }
    if (path === '/api/v1/agent/skills') {
      return json(route, { skills: [], default_skill_id: '' });
    }
    if (path === '/api/v1/alphasift/status') {
      return json(route, { enabled: false });
    }
    if (path === '/api/v1/platform/me') {
      if (!currentUser) {
        return json(route, { error: 'unauthorized', message: 'Login required' }, 401);
      }
      return json(route, authPayload(currentUser));
    }
    if (path === '/api/v1/platform/register' && method === 'POST') {
      const body = await readJson(route);
      const email = String(body.email || '').trim().toLowerCase();
      const password = String(body.password || '');
      if (users.has(email)) {
        return json(route, { error: 'email_exists', message: 'Email already exists' }, 409);
      }
      const user: MockUser = {
        id: nextUserId++,
        email,
        password,
        role: 'user',
        plan: 'free',
        status: 'active',
        apiKeys: [],
        usage: createUsage(),
        histories: [],
        watchlist: [],
      };
      users.set(email, user);
      currentUserId = user.id;
      return json(route, authPayload(user));
    }
    if (path === '/api/v1/platform/login' && method === 'POST') {
      const body = await readJson(route);
      const email = String(body.email || '').trim().toLowerCase();
      const password = String(body.password || '');
      const user = users.get(email);
      if (!user || user.password !== password) {
        return json(route, { error: 'invalid_credentials', message: 'Invalid login' }, 401);
      }
      currentUserId = user.id;
      return json(route, authPayload(user));
    }
    if (path === '/api/v1/platform/logout' && method === 'POST') {
      currentUserId = null;
      return route.fulfill({ status: 204 });
    }
    if (path === '/api/v1/platform/api-keys' && method === 'GET') {
      return json(route, currentUser?.apiKeys ?? [], currentUser ? 200 : 401);
    }
    if (path === '/api/v1/platform/api-keys' && method === 'POST') {
      if (!currentUser) {
        return json(route, { error: 'unauthorized', message: 'Login required' }, 401);
      }
      const body = await readJson(route);
      const item: MockApiKey = {
        id: currentUser.apiKeys[0]?.id ?? nextApiKeyId++,
        provider: String(body.provider || 'deepseek'),
        model: body.model ? String(body.model) : null,
        maskedKey: maskKey(String(body.apiKey || '')),
        enabled: true,
        createdAt: new Date().toISOString(),
        updatedAt: new Date().toISOString(),
      };
      currentUser.apiKeys = [item];
      return json(route, {
        id: item.id,
        provider: item.provider,
        model: item.model,
        masked_key: item.maskedKey,
        enabled: item.enabled,
        created_at: item.createdAt,
        updated_at: item.updatedAt,
      });
    }
    if (path === '/api/v1/platform/watchlist' && method === 'GET') {
      if (!currentUser) {
        return json(route, { error: 'unauthorized', message: 'Login required' }, 401);
      }
      const items = currentUser.watchlist.map((stockCode, index) => {
        const meta = snapshotMetaFor(stockCode);
        return {
          id: index + 1,
          stock_code: stockCode,
          input_code: stockCode,
          market: meta.market,
          created_at: '2026-07-06T10:00:00Z',
          updated_at: '2026-07-06T10:00:00Z',
        };
      });
      return json(route, {
        user_id: currentUser.id,
        items,
        total: items.length,
        ai_used: false,
      });
    }
    if (path === '/api/v1/platform/watchlist' && method === 'POST') {
      if (!currentUser) {
        return json(route, { error: 'unauthorized', message: 'Login required' }, 401);
      }
      const body = await readJson(route);
      const stockCode = String(body.stockCode || body.stock_code || '').trim().toUpperCase();
      if (stockCode && !currentUser.watchlist.includes(stockCode)) {
        currentUser.watchlist.push(stockCode);
      }
      const items = currentUser.watchlist.map((item, index) => {
        const meta = snapshotMetaFor(item);
        return {
          id: index + 1,
          stock_code: item,
          input_code: item,
          market: meta.market,
          created_at: '2026-07-06T10:00:00Z',
          updated_at: '2026-07-06T10:00:00Z',
        };
      });
      return json(route, {
        user_id: currentUser.id,
        items,
        total: items.length,
        ai_used: false,
      });
    }
    if (path === '/api/v1/platform/account') {
      return currentUser ? json(route, accountPayload(currentUser)) : json(route, { error: 'unauthorized', message: 'Login required' }, 401);
    }
    if (path === '/api/v1/platform/quota') {
      return currentUser ? json(route, quotaPayload(currentUser)) : json(route, { error: 'unauthorized', message: 'Login required' }, 401);
    }
    if (path.startsWith('/api/v1/platform/admin/')) {
      return json(route, { error: 'forbidden', message: 'Admin role required' }, 403);
    }
    if (path === '/api/v1/platform/history/snapshot' && method === 'POST') {
      if (!currentUser) {
        return json(route, { error: 'unauthorized', message: 'Login required' }, 401);
      }
      const body = await readJson(route);
      const snapshot = (body.snapshot || {}) as Record<string, unknown>;
      if (snapshot.aiUsed === true || snapshot.ai_used === true) {
        return json(route, { error: 'invalid_request', message: 'Only no-AI snapshots can be saved.' }, 400);
      }
      const stockCode = String(snapshot.stockCode || snapshot.stock_code || 'AAPL').trim().toUpperCase();
      const stockName = String(snapshot.stockName || snapshot.stock_name || snapshotMetaFor(stockCode).stockName);
      const history: MockHistory = {
        id: nextHistoryId++,
        queryId: `snapshot_${currentUser.id}_${Date.now()}`,
        stockCode,
        stockName,
        reportType: 'basic_snapshot',
        createdAt: new Date().toISOString(),
        sentimentScore: 61,
        operationAdvice: 'informational_no_ai_snapshot',
        action: 'watch',
        actionLabel: 'Watch',
        analysisSummary: `${stockCode} no-AI snapshot saved. Informational only; not investment advice.`,
      };
      currentUser.histories = [history, ...currentUser.histories];
      return json(route, {
        record_id: history.id,
        stock_code: history.stockCode,
        stock_name: history.stockName,
        report_type: history.reportType,
        saved_to_history: true,
        ai_used: false,
      });
    }
    if (path === '/api/v1/billing/checkout' && method === 'POST') {
      if (!currentUser) {
        return json(route, { error: 'unauthorized', message: 'Login required' }, 401);
      }
      currentUser.plan = 'pro';
      return json(route, {
        checkout_url: `http://127.0.0.1:4173/sandbox-checkout/session_${currentUser.id}`,
        provider_session_id: `sandbox_${currentUser.id}_pro_e2e`,
        provider: 'sandbox',
        plan: 'pro',
        mode: 'local_sandbox',
      });
    }
    if (path === '/api/v1/history/stocks') {
      const items = (currentUser?.histories ?? []).map((history) => ({
        id: history.id,
        stock_code: history.stockCode,
        stock_name: history.stockName,
        report_type: history.reportType,
        sentiment_score: history.sentimentScore,
        operation_advice: history.operationAdvice,
        action: history.action,
        action_label: history.actionLabel,
        analysis_count: 1,
        last_analysis_time: history.createdAt,
        model_used: 'deepseek/deepseek-v4-flash',
      }));
      return json(route, { total: items.length, items });
    }
    if (path === '/api/v1/history') {
      return json(route, historyListPayload(currentUser, url));
    }
    if (path.startsWith('/api/v1/history/')) {
      const id = Number(path.split('/').at(-1));
      const history = currentUser?.histories.find((item) => item.id === id);
      if (!history) {
        return json(route, { error: 'not_found', message: 'History record not found' }, 404);
      }
      return json(route, reportFor(history));
    }
    if (path === '/api/v1/analysis/tasks') {
      return json(route, { total: 0, pending: 0, processing: 0, tasks: [] });
    }
    if (path.match(/^\/api\/v1\/stocks\/[^/]+\/snapshot$/)) {
      if (currentUser) {
        currentUser.usage.basic_query += 1;
      }
      const code = decodeURIComponent(path.split('/').at(-2) || '600519');
      const meta = snapshotMetaFor(code);
      return json(route, {
        stock_code: code,
        stock_name: meta.stockName,
        market: meta.market,
        quote: {
          current_price: 1688.5,
          change: 20.1,
          change_percent: 1.2,
          open: 1660,
          high: 1690,
          low: 1650,
          prev_close: 1668.4,
          volume: 123456,
          amount: 987654321,
          update_time: new Date().toISOString(),
          source: 'e2e-mock',
          freshness: 'mocked',
        },
        indicators: { ma5: 1666.1, ma20: 1620.2 },
        route: {
          input_code: code,
          normalized_code: meta.normalizedCode,
          market: meta.market,
          channel: meta.channel,
          data_source_lane: meta.lane,
          quote_sources: meta.quoteSources,
          history_sources: meta.historySources,
          ai_required: false,
        },
        diagnostics: {
          elapsed_ms: 12,
          quote_elapsed_ms: 5,
          history_elapsed_ms: 7,
          cache: { quote: 'hit', history: 'hit' },
          sources: { quote: meta.quoteSources[0], history: meta.historySources[0] },
          freshness: { quote: 'mocked', history: 'mocked' },
          timeouts: { quote: false, history: false },
          errors: { quote: null, history: null },
          fallback: { quote: 'mock', history: 'mock' },
          source_health: {
            quote: { source: meta.quoteSources[0], status: 'ok', consecutive_failures: 0 },
            history: { source: meta.historySources[0], status: 'ok', consecutive_failures: 0 },
          },
          persistent_cache: { quote: 'memory', history: 'memory', mode: 'local_json' },
          route_lane: meta.lane,
          performance: { status: 'ok', slow_threshold_ms: 3000 },
        },
        degradation: { status: 'ok', severity: 'info', message: '' },
        warnings: [],
        ai_used: false,
      });
    }
    if (path === '/api/v1/analysis/analyze' && method === 'POST') {
      if (!currentUser) {
        return json(route, { error: 'unauthorized', message: 'Login required' }, 401);
      }
      const body = await readJson(route);
      const apiKeyMode = String(body.api_key_mode || 'platform');
      const depth = String(body.analysis_depth || 'fast');
      const bucket: QuotaBucket = depth === 'deep'
        ? (apiKeyMode === 'user' ? 'ai_deep_user_key' : 'ai_deep')
        : (apiKeyMode === 'user' ? 'ai_quick_user_key' : 'ai_quick');
      currentUser.usage[bucket] += 1;
      const stockCode = String(body.stock_code || '600519');
      const history: MockHistory = {
        id: nextHistoryId++,
        queryId: `query_${currentUser.id}_${Date.now()}`,
        stockCode,
        stockName: stockCode === 'AAPL' ? 'Apple' : 'Kweichow Moutai',
        reportType: depth === 'deep' ? 'detailed' : 'brief',
        createdAt: new Date().toISOString(),
        sentimentScore: 55,
        operationAdvice: 'hold',
        action: 'hold',
        actionLabel: 'Hold',
        analysisSummary: 'Mock AI quick analysis. Informational only; not investment advice.',
      };
      currentUser.histories = [history, ...currentUser.histories];
      const task = {
        task_id: `task_${history.id}`,
        trace_id: `trace_${history.id}`,
        stock_code: history.stockCode,
        stock_name: history.stockName,
        status: 'completed',
        progress: 100,
        message: 'Mock analysis completed',
        report_type: history.reportType,
        created_at: history.createdAt,
        started_at: history.createdAt,
        completed_at: history.createdAt,
        analysis_phase: 'auto',
        analysis_depth: depth,
      };
      completePendingStreams(task);
      return json(route, {
        task_id: task.task_id,
        trace_id: task.trace_id,
        status: 'pending',
        message: 'Mock analysis accepted',
        analysis_phase: 'auto',
        analysis_depth: depth,
      }, 202);
    }

    return json(route, {});
  });

  return {
    getUserByEmail: (email: string) => users.get(email.toLowerCase()),
    getCurrentUser,
  };
}

test.describe('platform user local E2E', () => {
  test('completes user journey and proves multi-user isolation', async ({ page }) => {
    const backend = await installMockBackend(page);
    const timestamp = Date.now();
    const userAEmail = `e2e+alice-${timestamp}@example.test`;
    const userBEmail = `e2e+bob-${timestamp}@example.test`;
    const password = 'password123';
    const placeholderSecret = 'placeholder-e2e-user-secret';

    await page.goto('/');
    await expect(page.getByTestId('platform-auth-register-tab')).toBeVisible({ timeout: 15_000 });

    await page.getByTestId('platform-auth-register-tab').click();
    await page.getByTestId('platform-auth-email').fill(userAEmail);
    await page.getByTestId('platform-auth-password').fill(password);
    await page.getByTestId('platform-auth-submit').click();

    await expect(page.getByTestId('platform-query-status')).toContainText(`Signed in ${userAEmail}`);
    await expect(page.getByRole('link', { name: 'Account' })).toBeVisible();
    await expect(page.getByRole('link', { name: 'Admin' })).toHaveCount(0);
    await expect(page.getByTestId('platform-query-status')).toContainText('Plan free');
    await expect(page.getByTestId('platform-query-status')).toContainText('BYOK not set');
    await expect(page.getByTestId('platform-ai-cost-warning')).toContainText('Quick snapshot stays no-AI');
    const adminStatus = await page.evaluate(async () => {
      const response = await fetch('/api/v1/platform/admin/users', { credentials: 'include' });
      return response.status;
    });
    expect(adminStatus).toBe(403);

    await page.getByTestId('platform-api-key-secret').fill(placeholderSecret);
    await page.getByTestId('platform-api-key-save').click();
    await expect(page.locator('body')).not.toContainText(placeholderSecret);
    await expect(page.getByTestId('platform-mode-user')).toBeEnabled();
    await expect(page.getByTestId('platform-query-status')).toContainText(`BYOK ready ${maskKey(placeholderSecret)}`);
    await expect(page.getByTestId('platform-query-status')).toContainText('Recommended BYOK');

    await page.getByRole('link', { name: 'Account' }).click();
    await expect(page.getByRole('heading', { name: 'Account', exact: true })).toBeVisible();
    await expect(page.locator('dd', { hasText: userAEmail })).toBeVisible();
    await expect(page.getByText(maskKey(placeholderSecret))).toBeVisible();
    await expect(page.locator('body')).not.toContainText(placeholderSecret);

    await page.getByRole('link', { name: 'Home' }).click();
    const stockInput = page.getByPlaceholder(/Enter a stock code/);
    const runQuickSnapshot = async (symbol: string, laneText: string) => {
      await stockInput.fill('');
      await stockInput.click();
      await stockInput.pressSequentially(symbol);
      await expect(page.getByRole('button', { name: 'Query' })).toBeEnabled();
      await page.getByRole('button', { name: 'Query' }).click();
      await expect(page.getByTestId('basic-query-snapshot')).toBeVisible();
      const guardrails = page.getByTestId('basic-query-user-guardrails');
      await expect(guardrails).toContainText('Current quick snapshot');
      await expect(guardrails).toContainText('No AI used');
      await expect(guardrails).toContainText(laneText);
      await expect(guardrails).toContainText('Historical reports stay separate');
      await expect(guardrails).toContainText('Cache local_json');
    };
    await runQuickSnapshot('600519', 'A-share market data');
    await runQuickSnapshot('AAPL', 'US market data');
    await runQuickSnapshot('HK00700', 'HK market data');
    await runQuickSnapshot('BTC-USD', 'Crypto market data');
    expect(backend.getUserByEmail(userAEmail)?.usage.ai_quick).toBe(0);
    expect(backend.getUserByEmail(userAEmail)?.usage.ai_quick_user_key).toBe(0);

    await page.getByTestId('platform-mode-user').click();
    await stockInput.fill('');
    await stockInput.pressSequentially('600519');
    await page.locator('header').getByRole('button', { name: 'Quick AI' }).click();
    await expect(page.getByTestId('home-stock-bar-scroll')).toContainText('Kweichow Moutai', { timeout: 15_000 });
    expect(backend.getUserByEmail(userAEmail)?.usage.ai_quick_user_key).toBe(1);

    await page.getByRole('link', { name: 'Account' }).click();
    await page.getByRole('button', { name: 'Start sandbox upgrade' }).click();
    await expect(page.getByText('Local sandbox checkout created')).toBeVisible();
    await page.getByRole('button', { name: 'Refresh' }).click();
    await expect(page.getByText('pro').first()).toBeVisible();

    await page.getByRole('link', { name: 'Home' }).click();
    await page.getByTestId('platform-logout-button').click();
    await expect(page.getByTestId('platform-auth-register-tab')).toBeVisible();

    await page.getByTestId('platform-auth-register-tab').click();
    await page.getByTestId('platform-auth-email').fill(userBEmail);
    await page.getByTestId('platform-auth-password').fill(password);
    await page.getByTestId('platform-auth-submit').click();
    await expect(page.getByTestId('platform-query-status')).toContainText(`Signed in ${userBEmail}`);
    await expect(page.getByRole('link', { name: 'Admin' })).toHaveCount(0);

    await page.getByRole('link', { name: 'Account' }).click();
    await expect(page.locator('dd', { hasText: userBEmail })).toBeVisible();
    await expect(page.locator('body')).not.toContainText(userAEmail);
    await expect(page.locator('body')).not.toContainText(maskKey(placeholderSecret));
    await expect(page.getByText('No user API key saved.')).toBeVisible();
    expect(backend.getCurrentUser()?.email).toBe(userBEmail);
    expect(backend.getCurrentUser()?.histories).toHaveLength(0);
    expect(backend.getCurrentUser()?.usage.ai_quick_user_key).toBe(0);

    await page.getByRole('link', { name: 'Home' }).click();
    await expect(page.getByTestId('home-stock-bar-scroll')).not.toContainText('Kweichow Moutai');

    await page.getByTestId('platform-logout-button').click();
    await page.getByTestId('platform-auth-login-tab').click();
    await page.getByTestId('platform-auth-email').fill(userAEmail);
    await page.getByTestId('platform-auth-password').fill(password);
    await page.getByTestId('platform-auth-submit').click();
    await expect(page.getByTestId('platform-query-status')).toContainText(`Signed in ${userAEmail}`);
    await expect(page.getByTestId('home-stock-bar-scroll')).toContainText('Kweichow Moutai');
  });

  test('retains a guest AAPL snapshot after register and reloads saved history after login', async ({ page }) => {
    const backend = await installMockBackend(page);
    const timestamp = Date.now();
    const email = `e2e+retention-${timestamp}@example.test`;
    const password = 'password123';

    await page.goto('/');
    await expect(page.getByTestId('guest-query-entry')).toBeVisible({ timeout: 15_000 });

    await page.getByTestId('guest-example-AAPL').click();
    await expect(page.getByTestId('basic-query-snapshot')).toContainText('Apple');
    await expect(page.getByTestId('guest-conversion-guide')).toContainText('Login is optional');

    await page.getByTestId('guest-guide-register').click();
    await page.getByTestId('guest-auth-email').fill(email);
    await page.getByTestId('guest-auth-password').fill(password);
    await page.getByTestId('guest-auth-submit').click();

    await expect(page.getByTestId('basic-query-snapshot')).toContainText('Apple');
    await expect(page.getByTestId('basic-query-retention-mode-guide')).toContainText('Free no-AI');
    await expect(page.getByTestId('basic-query-retention-mode-guide')).toContainText('Platform API');
    await expect(page.getByTestId('basic-query-retention-mode-guide')).toContainText('BYOK');
    await expect(page.getByTestId('basic-query-retention-mode-guide')).toContainText('Local model');

    await page.getByTestId('basic-query-save-current-history').click();
    await expect(page.getByTestId('basic-query-retention-status')).toContainText('Saved to history');
    expect(backend.getUserByEmail(email)?.histories.map((item) => item.stockCode)).toContain('AAPL');

    await page.getByTestId('basic-query-add-current-watchlist').click();
    await expect(page.getByTestId('basic-query-retention-status')).toContainText('Added to watchlist');
    expect(backend.getUserByEmail(email)?.watchlist).toContain('AAPL');

    await page.getByTestId('platform-logout-button').click();
    await page.getByTestId('platform-auth-login-tab').click();
    await page.getByTestId('platform-auth-email').fill(email);
    await page.getByTestId('platform-auth-password').fill(password);
    await page.getByTestId('platform-auth-submit').click();

    await expect(page.getByTestId('platform-query-status')).toContainText(`Signed in ${email}`);
    await expect(page.getByTestId('home-stock-bar-scroll')).toContainText('Apple');
    await expect(page.getByTestId('platform-watchlist-panel')).toContainText('AAPL');
    await expect(page.locator('body')).not.toContainText('sk-live');
  });
});
