import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { UiLanguageProvider } from '../../contexts/UiLanguageContext';
import AccountPage from '../AccountPage';

const { account, billingAccount, saveApiKey, createSandboxCheckout } = vi.hoisted(() => ({
  account: vi.fn(),
  billingAccount: vi.fn(),
  saveApiKey: vi.fn(),
  createSandboxCheckout: vi.fn(),
}));

vi.mock('../../api/platform', () => ({
  platformApi: {
    account,
    billingAccount,
    saveApiKey,
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

function renderPage() {
  window.localStorage.setItem('dsa.uiLanguage', 'en');
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
  createSandboxCheckout.mockResolvedValue({
    checkoutUrl: '/sandbox/checkout/sandbox_7_pro_abc',
    providerSessionId: 'sandbox_7_pro_abc',
    provider: 'sandbox',
    plan: 'pro',
    mode: 'local_sandbox',
  });
});

describe('AccountPage', () => {
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

  it('saves a deepseek API key and refreshes account data without rendering the plaintext value', async () => {
    renderPage();
    await screen.findByRole('heading', { name: 'Account' });

    fireEvent.change(screen.getByLabelText('Provider'), { target: { value: 'deepseek' } });
    fireEvent.change(screen.getByLabelText('Model'), { target: { value: 'deepseek/deepseek-v4-flash' } });
    fireEvent.change(screen.getByLabelText('API key'), { target: { value: 'sk-user-plaintext-secret' } });
    fireEvent.click(screen.getByRole('button', { name: 'Save API key' }));

    await waitFor(() => {
      expect(saveApiKey).toHaveBeenCalledWith({
        provider: 'deepseek',
        model: 'deepseek/deepseek-v4-flash',
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
    saveApiKey.mockRejectedValueOnce({
      parsedError: { message: 'Too many requests. Please wait before trying again.' },
    });

    renderPage();
    await screen.findByRole('heading', { name: 'Account' });

    fireEvent.change(screen.getByLabelText('API key'), { target: { value: 'sk-user-plaintext-secret' } });
    fireEvent.click(screen.getByRole('button', { name: 'Save API key' }));

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
