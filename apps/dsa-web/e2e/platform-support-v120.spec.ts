import { expect, test, type Route } from '@playwright/test';

test.skip(!process.env.DSA_PLATFORM_E2E, 'Set DSA_PLATFORM_E2E=1 to run platform support E2E tests.');

function json(route: Route, data: unknown, status = 200) {
  return route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(data) });
}

async function body(route: Route): Promise<Record<string, unknown>> {
  return JSON.parse(route.request().postData() || '{}') as Record<string, unknown>;
}

test('completes the user and administrator support ticket loop on desktop and mobile', async ({ page }) => {
  let nextMessageId = 2;
  let ticket: Record<string, unknown> | null = null;
  const messages: Array<Record<string, unknown>> = [];

  await page.addInitScript(() => window.localStorage.setItem('dsa.uiLanguage', 'zh'));
  await page.route('**/api/v1/**', async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname;
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
    if (path === '/api/v1/support/tickets' && method === 'GET') {
      return json(route, { tickets: ticket ? [ticket] : [], total: ticket ? 1 : 0 });
    }
    if (path === '/api/v1/support/tickets' && method === 'POST') {
      const input = await body(route);
      const now = '2026-07-14T09:00:00';
      messages.push({ id: 1, ticket_id: 12, author_role: 'user', body: input.message, created_at: now });
      ticket = {
        id: 12, user_id: 7, requester_email: 'support-admin@example.com', category: input.category,
        subject: input.subject, status: 'open', unread_by_user: false, unread_by_admin: true,
        message_count: messages.length, created_at: now, updated_at: now, closed_at: null,
      };
      return json(route, { ticket: { ...ticket, messages } }, 201);
    }
    if (path === '/api/v1/support/tickets/12' && method === 'GET') {
      return json(route, { ticket: { ...ticket, unread_by_user: false, messages } });
    }
    if (path === '/api/v1/support/tickets/12/messages' && method === 'POST') {
      const input = await body(route);
      messages.push({ id: nextMessageId++, ticket_id: 12, author_role: 'user', body: input.message, created_at: '2026-07-14T09:05:00' });
      ticket = { ...ticket, unread_by_admin: true, message_count: messages.length, updated_at: '2026-07-14T09:05:00' };
      return json(route, { ticket: { ...ticket, messages } });
    }
    if (path === '/api/v1/support/admin/tickets' && method === 'GET') {
      return json(route, { tickets: ticket ? [ticket] : [], total: ticket ? 1 : 0 });
    }
    if (path === '/api/v1/support/admin/tickets/12' && method === 'GET') {
      ticket = { ...ticket, unread_by_admin: false };
      return json(route, { ticket: { ...ticket, messages } });
    }
    if (path === '/api/v1/support/admin/tickets/12/messages' && method === 'POST') {
      const input = await body(route);
      messages.push({ id: nextMessageId++, ticket_id: 12, author_role: 'admin', body: input.message, created_at: '2026-07-14T09:10:00' });
      ticket = { ...ticket, status: 'in_progress', unread_by_user: true, unread_by_admin: false, message_count: messages.length, updated_at: '2026-07-14T09:10:00' };
      return json(route, { ticket: { ...ticket, messages } });
    }
    if (path === '/api/v1/support/admin/tickets/12/status' && method === 'PATCH') {
      const input = await body(route);
      ticket = { ...ticket, status: input.status, unread_by_user: true, closed_at: input.status === 'closed' ? '2026-07-14T09:15:00' : null };
      return json(route, { ticket: { ...ticket, messages } });
    }
    if (path === '/api/v1/platform/watchlist-alerts/events') {
      return json(route, { user_id: 7, total: 0, unread: 0, items: [], ai_used: false });
    }
    if (path.startsWith('/api/v1/platform/admin/') || path === '/api/v1/billing/admin/events') {
      return json(route, { error: 'not_available_in_support_e2e' }, 503);
    }
    return json(route, {});
  });

  await page.goto('/support');
  await expect(page.getByRole('heading', { name: '客服中心' })).toBeVisible();
  await page.getByLabel('问题分类').selectOption('bug');
  await page.getByLabel('问题主题').fill('Browser support path failed');
  await page.getByLabel('问题描述').fill('The support page stayed blank after refresh.');
  await page.getByRole('button', { name: '提交工单' }).click();
  await expect(page.getByText('The support page stayed blank after refresh.')).toBeVisible();
  await page.getByLabel('追加消息').fill('The issue is still reproducible.');
  await page.getByRole('button', { name: '发送消息' }).click();
  await expect(page.getByText('The issue is still reproducible.')).toBeVisible();

  await page.goto('/admin');
  await expect(page.getByRole('heading', { name: '客服工单' })).toBeVisible();
  await page.getByRole('button', { name: /Browser support path failed/ }).click();
  await page.getByLabel('管理员回复').fill('We reproduced the product issue and are checking it.');
  await page.getByRole('button', { name: '发送回复' }).click();
  await expect(page.getByText('We reproduced the product issue and are checking it.')).toBeVisible();
  await page.getByRole('button', { name: '标记已关闭' }).click();
  await expect(page.getByText(/support-admin@example.com.*已关闭/)).toBeVisible();

  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/support');
  await expect(page.getByRole('heading', { name: '客服中心' })).toBeVisible();
  const hasOverflow = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth);
  expect(hasOverflow).toBe(false);
});
