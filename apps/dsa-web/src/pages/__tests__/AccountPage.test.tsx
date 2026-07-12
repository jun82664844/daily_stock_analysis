import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { UiLanguageProvider } from '../../contexts/UiLanguageContext';
import AccountPage from '../AccountPage';

const { account, billingAccount, saveApiKey, connectApiKey, createSandboxCheckout } = vi.hoisted(() => ({
  account: vi.fn(),
  billingAccount: vi.fn(),
  saveApiKey: vi.fn(),
  connectApiKey: vi.fn(),
  createSandboxCheckout: vi.fn(),
}));

vi.mock('../../api/platform', () => ({
  platformApi: {
    account,
    billingAccount,
    saveApiKey,
    connectApiKey,
    createSandboxCheckout,
  },
}));

function accountPayload(overrides: Record<string, unknown> = {}) {
  return {
    user: { id: 7, email: 'user@example.com', role: 'user', plan: 'free', status: 'active' },
    quota: { userId: 7, plan: 'free', weeklyLimit: 5, used: 1, remaining: 4, periodStart: '2026-06-29' },
    quotaBuckets: [
      { userId: 7, plan: 'free', quotaBucket: 'basic_query', weeklyLimit: null, used: 0, remaining: null, periodStart: '2026-06-29' },
      { userId: 7, plan: 'free', quotaBucket: 'ai_quick', weeklyLimit: 5, used: 1, remaining: 4, periodStart: '2026-06-29' },
      { userId: 7, plan: 'free', quotaBucket: 'ai_quick_user_key', weeklyLimit: 25, used: 2, remaining: 23, periodStart: '2026-06-29' },
      { userId: 7, plan: 'free', quotaBucket: 'ai_deep_user_key', weeklyLimit: 50, used: 0, remaining: 50, periodStart: '2026-06-29' },
      { userId: 7, plan: 'free', quotaBucket: 'ai_local', weeklyLimit: 50, used: 0, remaining: 50, periodStart: '2026-06-29' },
    ],
    apiKeys: [
      { id: 2, provider: 'deepseek', model: 'deepseek/deepseek-v4-flash', maskedKey: 'sk-u...cret', enabled: true },
    ],
    recommendedQueryMode: 'user',
    ...overrides,
  };
}

function billingPayload(overrides: Record<string, unknown> = {}) {
  return {
    billingEnabled: true,
    provider: 'sandbox',
    mode: 'local_sandbox',
    copy: 'Local sandbox billing only; not real payment processing.',
    subscription: {
      userId: 7,
      provider: 'sandbox',
      providerSubscriptionId: 'sub_test_7',
      plan: 'pro',
      status: 'active',
      createdAt: '2026-07-02T08:00:00',
      updatedAt: '2026-07-02T08:05:00',
    },
    checkoutSessions: [
      {
        id: 4,
        userId: 7,
        provider: 'sandbox',
        providerSessionId: 'sandbox_7_pro_abc',
        checkoutUrl: '/sandbox/checkout/sandbox_7_pro_abc',
        plan: 'pro',
        status: 'completed',
        createdAt: '2026-07-02T08:00:00',
        updatedAt: '2026-07-02T08:05:00',
      },
    ],
    recentEvents: [
      {
        id: 5,
        userId: 7,
        provider: 'sandbox',
        providerEventId: 'evt_completed_once',
        providerSessionId: 'sandbox_7_pro_abc',
        eventType: 'checkout.completed',
        plan: 'pro',
        processingStatus: 'processed',
        createdAt: '2026-07-02T08:05:00',
      },
    ],
    ...overrides,
  };
}

function renderPage(language: 'zh' | 'en' = 'en') {
  window.localStorage.setItem('dsa.uiLanguage', language);
  return render(
    <UiLanguageProvider>
      <AccountPage />
    </UiLanguageProvider>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  account.mockResolvedValue(accountPayload());
  billingAccount.mockResolvedValue(billingPayload());
  saveApiKey.mockResolvedValue({
    provider: 'deepseek',
    model: 'deepseek/deepseek-v4-flash',
    maskedKey: 'sk-n...cret',
    enabled: true,
  });
  connectApiKey.mockResolvedValue({
    apiKey: { provider: 'deepseek', model: 'deepseek/deepseek-v4-flash', maskedKey: 'sk-n...cret', enabled: true },
    modelOptions: [],
  });
  createSandboxCheckout.mockResolvedValue({
    checkoutUrl: '/sandbox/checkout/sandbox_7_pro_abc',
    providerSessionId: 'sandbox_7_pro_abc',
    provider: 'sandbox',
    plan: 'pro',
    mode: 'local_sandbox',
  });
});

describe('AccountPage', () => {
  it('localizes account and sandbox billing content in Chinese mode', async () => {
    billingAccount.mockResolvedValueOnce(billingPayload({
      mode: 'disabled',
      subscription: {
        userId: 7,
        provider: 'sandbox',
        providerSubscriptionId: null,
        plan: 'free',
        status: 'none',
        createdAt: '2026-07-02T08:00:00',
        updatedAt: '2026-07-02T08:05:00',
      },
    }));
    renderPage('zh');

    expect(await screen.findByRole('heading', { name: '账户' })).toBeInTheDocument();
    expect(screen.getByText('API Key 托管')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '连接并测试' })).toBeInTheDocument();
    expect(screen.getByText('本地支付沙箱')).toBeInTheDocument();
    expect(screen.getByText('仅本地模拟账单，真实支付仍关闭')).toBeInTheDocument();
    expect(screen.getByText(/本地沙箱账单/)).toBeInTheDocument();
    expect(screen.getByText('订阅')).toBeInTheDocument();
    expect(screen.getByText('账单模式')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '启动沙箱升级' })).toBeInTheDocument();
    expect(screen.getByText('最近结账会话')).toBeInTheDocument();
    expect(screen.getByText('最近账单事件')).toBeInTheDocument();
    expect(screen.getByText('结账完成')).toBeInTheDocument();
    expect(screen.getAllByText('专业版 / 沙箱')[0]).toBeInTheDocument();
    expect(screen.getByText('免费版 / 未订阅')).toBeInTheDocument();
    expect(screen.getByText('已关闭')).toBeInTheDocument();

    expect(screen.queryByText('Local payment sandbox')).not.toBeInTheDocument();
    expect(screen.queryByText('MOCK BILLING ONLY; REAL PAYMENT REMAINS DISABLED')).not.toBeInTheDocument();
    expect(screen.queryByText('Start sandbox upgrade')).not.toBeInTheDocument();
    expect(screen.queryByText('Recent checkout sessions')).not.toBeInTheDocument();
    expect(screen.queryByText('Recent billing events')).not.toBeInTheDocument();
    expect(screen.queryByText('none')).not.toBeInTheDocument();
    expect(screen.queryByText('disabled')).not.toBeInTheDocument();
  });

  it('renders account, quota buckets, masked API key state, and no plaintext key', async () => {
    renderPage();

    expect(await screen.findByRole('heading', { name: 'Account' })).toBeInTheDocument();
    expect(screen.getAllByText('user@example.com')[0]).toBeInTheDocument();
    expect(screen.getAllByText('user')[0]).toBeInTheDocument();
    expect(screen.getAllByText('free')[0]).toBeInTheDocument();
    expect(screen.getByText('sk-u...cret')).toBeInTheDocument();
    expect(screen.getByText('ai_quick_user_key')).toBeInTheDocument();
    expect(screen.getAllByText('Recommended mode: user')[0]).toBeInTheDocument();
    expect(screen.queryByText(/sk-user-plaintext-secret/)).not.toBeInTheDocument();
  });

  it('renders local sandbox subscription, checkout session, and billing events', async () => {
    renderPage();

    expect(await screen.findByRole('heading', { name: 'Account' })).toBeInTheDocument();
    expect(await screen.findByText('pro / active')).toBeInTheDocument();
    expect(screen.getByText('checkout.completed')).toBeInTheDocument();
    expect(screen.getByText('evt_completed_once')).toBeInTheDocument();
    expect(screen.getAllByText('sandbox_7_pro_abc')[0]).toBeInTheDocument();
    expect(screen.getByText(/not real payment processing/i)).toBeInTheDocument();
    expect(screen.queryByText(/sk-user-plaintext-secret/)).not.toBeInTheDocument();
  });

  it('connects a deepseek API key and refreshes account data without rendering the plaintext value', async () => {
    renderPage();
    await screen.findByRole('heading', { name: 'Account' });

    fireEvent.click(screen.getByRole('button', { name: 'DeepSeek' }));
    fireEvent.change(screen.getByLabelText('API Key'), { target: { value: 'sk-user-plaintext-secret' } });
    fireEvent.click(screen.getByRole('button', { name: 'Connect and test' }));

    await waitFor(() => {
      expect(connectApiKey).toHaveBeenCalledWith({
        provider: 'deepseek',
        apiKey: 'sk-user-plaintext-secret',
      });
    });
    expect(account).toHaveBeenCalledTimes(2);
    expect(screen.queryByText(/sk-user-plaintext-secret/)).not.toBeInTheDocument();
  });

  it('creates a local sandbox checkout session for a pro upgrade', async () => {
    renderPage();
    await screen.findByRole('heading', { name: 'Account' });

    fireEvent.click(screen.getByRole('button', { name: 'Start sandbox upgrade' }));

    await waitFor(() => {
      expect(createSandboxCheckout).toHaveBeenCalledWith('pro');
    });
    await waitFor(() => {
      expect(billingAccount).toHaveBeenCalledTimes(2);
    });
    expect(await screen.findByText('Local sandbox checkout created')).toBeInTheDocument();
    expect(screen.getByText('/sandbox/checkout/sandbox_7_pro_abc')).toBeInTheDocument();
    expect(screen.getAllByText('sandbox_7_pro_abc')[0]).toBeInTheDocument();
  });

  it('shows a clear quota error state', async () => {
    account.mockRejectedValueOnce(new Error('quota_exceeded: Weekly analysis quota exhausted'));

    renderPage();

    expect(await screen.findByText('quota_exceeded: Weekly analysis quota exhausted')).toBeInTheDocument();
  });

  it('shows a clear rate limited error when API key custody is throttled', async () => {
    connectApiKey.mockRejectedValueOnce({
      parsedError: { message: 'Too many requests. Please wait before trying again.' },
    });

    renderPage();
    await screen.findByRole('heading', { name: 'Account' });

    fireEvent.change(screen.getByLabelText('API Key'), { target: { value: 'sk-user-plaintext-secret' } });
    fireEvent.click(screen.getByRole('button', { name: 'Connect and test' }));

    expect(await screen.findByText('Too many requests. Please wait before trying again.')).toBeInTheDocument();
    expect(screen.queryByText(/sk-user-plaintext-secret/)).not.toBeInTheDocument();
  });

  it('shows a clear sandbox disabled error when billing is not enabled', async () => {
    createSandboxCheckout.mockRejectedValueOnce({
      parsedError: { message: 'Billing is disabled in local V1' },
    });

    renderPage();
    await screen.findByRole('heading', { name: 'Account' });

    fireEvent.click(screen.getByRole('button', { name: 'Start sandbox upgrade' }));

    expect(await screen.findByText('Billing is disabled in local V1')).toBeInTheDocument();
  });
});
