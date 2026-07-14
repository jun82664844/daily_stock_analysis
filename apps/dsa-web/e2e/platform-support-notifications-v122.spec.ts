import { expect, test, type Route } from '@playwright/test';

test.skip(!process.env.DSA_PLATFORM_E2E, 'Set DSA_PLATFORM_E2E=1 to run platform support notification tests.');

function json(route: Route, data: unknown, status = 200) {
  return route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(data) });
}

test('updates user and administrator support badges on desktop and mobile', async ({ page }) => {
  let userUnread = 3;
  let pendingCount = 1;
  let ticketStatus = 'open';
  const ticket = () => ({
    id: 12,
    user_id: 7,
    requester_email: 'support-admin@example.com',
    category: 'bug',
    subject: 'Notification test ticket',
    status: ticketStatus,
    unread_by_user: userUnread > 0,
    unread_by_admin: true,
    message_count: 2,
    created_at: '2026-07-14T09:00:00+00:00',
    updated_at: '2026-07-14T09:10:00+00:00',
    closed_at: ticketStatus === 'closed' ? '2026-07-14T09:15:00+00:00' : null,
  });
  const detail = () => ({
    ...ticket(),
    messages: [
      { id: 1, ticket_id: 12, author_role: 'user', body: 'The support badge did not refresh.', created_at: '2026-07-14T09:00:00+00:00' },
      { id: 2, ticket_id: 12, author_role: 'admin', body: 'Please reopen the ticket view.', created_at: '2026-07-14T09:10:00+00:00' },
    ],
  });

  await page.addInitScript(() => window.localStorage.setItem('dsa.uiLanguage', 'zh'));
  await page.route('**/api/v1/**', async (route) => {
    const request = route.request();
    const path = new URL(request.url()).pathname;
    const method = request.method();

    if (path === '/api/v1/auth/status') {
      return json(route, { authEnabled: false, loggedIn: false, passwordSet: false, passwordChangeable: false, setupState: 'no_password' });
    }
    if (path === '/api/v1/platform/me') {
      return json(route, {
        user: { id: 7, email: 'support-admin@example.com', role: 'admin', plan: 'enterprise', status: 'active' },
        quota: { user_id: 7, plan: 'enterprise', weekly_limit: null, used: 0, remaining: null, period_start: '2026-07-13' },
      });
    }
    if (path === '/api/v1/support/summary') {
      return json(route, { unread_count: userUnread, active_count: pendingCount });
    }
    if (path === '/api/v1/support/admin/summary') {
      return json(route, { unread_count: 1, pending_count: pendingCount, oldest_pending_at: pendingCount ? '2026-07-14T09:00:00+00:00' : null });
    }
    if (path === '/api/v1/support/tickets' && method === 'GET') {
      return json(route, { tickets: [ticket()], total: 1 });
    }
    if (path === '/api/v1/support/tickets/12' && method === 'GET') {
      userUnread = 0;
      return json(route, { ticket: detail() });
    }
    if (path === '/api/v1/support/admin/tickets' && method === 'GET') {
      return json(route, { tickets: [ticket()], total: 1 });
    }
    if (path === '/api/v1/support/admin/tickets/12' && method === 'GET') {
      return json(route, { ticket: detail() });
    }
    if (path === '/api/v1/support/admin/tickets/12/status' && method === 'PATCH') {
      ticketStatus = 'closed';
      pendingCount = 0;
      return json(route, { ticket: detail() });
    }
    if (path === '/api/v1/platform/watchlist-alerts/events') {
      return json(route, { user_id: 7, total: 0, unread: 0, items: [], ai_used: false });
    }
    if (path.startsWith('/api/v1/platform/admin/') || path === '/api/v1/billing/admin/events') {
      return json(route, { error: 'not_available_in_support_notification_e2e' }, 503);
    }
    return json(route, {});
  });

  await page.goto('/support');
  await expect(page.getByTestId('support-user-badge')).toHaveText('3');
  await expect(page.getByTestId('support-admin-badge')).toHaveText('1');
  await page.getByRole('button', { name: /Notification test ticket/ }).click();
  await expect(page.getByTestId('support-user-badge')).toHaveCount(0);

  await page.getByRole('link', { name: /1 张待处理客服工单/ }).click();
  await expect(page).toHaveURL(/\/admin$/);
  await expect(page.getByRole('heading', { name: '运营', exact: true })).toBeVisible();
  await page.getByRole('button', { name: /Notification test ticket/ }).click();
  await page.getByRole('button', { name: '标记已关闭' }).click();
  await expect(page.getByTestId('support-admin-badge')).toHaveCount(0);

  userUnread = 2;
  pendingCount = 1;
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/support');
  await page.getByRole('button', { name: '打开导航' }).click();
  await expect(page.getByTestId('support-user-badge')).toHaveText('2');
  await expect(page.getByTestId('support-admin-badge')).toHaveText('1');
  const hasOverflow = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth);
  expect(hasOverflow).toBe(false);
});
