import { expect, test, type Page, type Route } from '@playwright/test';

test.skip(!process.env.DSA_PLATFORM_E2E, 'Set DSA_PLATFORM_E2E=1 to run V116 browser tests.');

const marketHome = {
  as_of: '2026-07-13T01:30:00Z', ai_used: false, informational_only: true,
  markets: [
    { market: 'cn', session_state: 'unknown', display_mode: 'latest_available', ranking_scope: 'configured_universe', selection_basis: 'turnover_then_absolute_change', indices: [], sources: [], warnings: [], attention: [{ symbol: '600519.SH', name: '贵州茅台', market: 'cn', currency: 'CNY', current_price: 1188.8, change_percent: -1.5, source_state: { source: 'cn_quote', status: 'fresh', observed_at: '2026-07-13T01:29:00Z' } }] },
    { market: 'hk', session_state: 'unknown', display_mode: 'delayed', ranking_scope: 'configured_universe', selection_basis: 'turnover_then_absolute_change', indices: [], sources: [], warnings: [], attention: [{ symbol: '0700.HK', name: '腾讯控股', market: 'hk', currency: 'HKD', current_price: 500, change_percent: 1.25, source_state: { source: 'hk_quote', status: 'cached' } }] },
    { market: 'us', session_state: 'unknown', display_mode: 'latest_available', ranking_scope: 'configured_universe', selection_basis: 'turnover_then_absolute_change', indices: [], sources: [], warnings: ['market_home_unavailable'], attention: [] },
  ],
};

function json(route: Route, body: unknown, status = 200) {
  return route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(body) });
}

async function mockV116(page: Page) {
  await page.route('**/api/v1/**', async (route) => {
    const url = new URL(route.request().url());
    if (url.pathname === '/api/v1/market-workspace/home') return json(route, marketHome);
    if (url.pathname === '/api/v1/auth/status') return json(route, {
      authEnabled: false,
      loggedIn: false,
      passwordSet: false,
      passwordChangeable: false,
      setupState: 'no_password',
    });
    if (url.pathname === '/api/v1/platform/status') return json(route, { platform_auth_enabled: true });
    if (url.pathname === '/api/v1/platform/me') return json(route, { error: 'unauthorized' }, 401);
    if (url.pathname === '/api/v1/platform/local-model/status') return json(route, {
      enabled: false, reachable: false, ready: false, quick_ready: false, deep_ready: false,
      reason: 'disabled', runtime: 'ollama', quick_model_available: false, deep_model_available: false, max_concurrent: 1,
    });
    if (url.pathname.includes('/prewarm')) return json(route, { requested: 0, warmed: 0, degraded: 0, symbols: [], results: {}, elapsed_ms: 0, ai_used: false });
    return json(route, { error: `not_mocked:${url.pathname}` }, 404);
  });
}

test('guest sees three-market home and keeps an alert draft for registration', async ({ page }) => {
  await mockV116(page);
  await page.goto('/?dsa_v116_smoke=1');
  await expect(page.getByRole('heading', { name: '三地市场速览' })).toBeVisible();
  await expect(page.getByRole('heading', { name: '贵州茅台' })).toBeVisible();
  await expect(page.getByRole('heading', { name: '腾讯控股' })).toBeVisible();
  await expect(page.getByText('该市场暂时不可用')).toBeVisible();
  await page.getByRole('button', { name: '为 贵州茅台 设置到价提醒' }).click();
  await page.getByRole('spinbutton', { name: '到价阈值' }).fill('1200');
  await page.getByRole('button', { name: '保存到价提醒' }).click();
  await expect(page.getByText('注册后可保存这条私有到价提醒；登录后仍需再次确认。')).toBeVisible();
  await expect(page.getByTestId('platform-registration-benefit-v116')).toContainText('每周赠送 5 次快速分析');
  expect(await page.evaluate(() => sessionStorage.getItem('dsa_v116_pending_price_alert'))).toContain('600519.SH');
});

test('V116 market home has no horizontal overflow on mobile', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await mockV116(page);
  await page.goto('/?dsa_v116_mobile=1');
  await expect(page.getByRole('heading', { name: '三地市场速览' })).toBeVisible();
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth + 1);
  expect(overflow).toBe(false);
});
