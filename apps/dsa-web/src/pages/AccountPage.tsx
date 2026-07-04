import React, { useCallback, useEffect, useRef, useState } from 'react';
import { CreditCard, Gauge, KeyRound, RefreshCw, ShieldCheck, UserRound } from 'lucide-react';
import { platformApi, type BillingCheckoutSession, type PlatformAccountSummary, type PlatformBillingAccountResponse, type PlatformPlan, type PlatformQuotaBucket } from '../api/platform';
import { AppPage, Card, PageHeader, StatCard } from '../components/common';
import { cn } from '../utils/cn';

function errorMessage(error: unknown, fallback: string): string {
  if (error && typeof error === 'object' && 'parsedError' in error) {
    const parsed = (error as { parsedError?: { message?: string; rawMessage?: string } }).parsedError;
    if (parsed?.message || parsed?.rawMessage) {
      return parsed.message || parsed.rawMessage || fallback;
    }
  }
  return error instanceof Error ? error.message : fallback;
}

function formatLimit(value: number | null | undefined): string {
  if (value === null || value === undefined) {
    return 'Unlimited';
  }
  return new Intl.NumberFormat('en-US').format(value);
}

function formatUsage(bucket: PlatformQuotaBucket): string {
  const used = new Intl.NumberFormat('en-US').format(bucket.used ?? 0);
  return `${used} / ${formatLimit(bucket.weeklyLimit)}`;
}

const AccountPage: React.FC = () => {
  const [account, setAccount] = useState<PlatformAccountSummary | null>(null);
  const [billing, setBilling] = useState<PlatformBillingAccountResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [saveState, setSaveState] = useState<'idle' | 'saving' | 'saved'>('idle');
  const [checkoutState, setCheckoutState] = useState<'idle' | 'creating'>('idle');
  const [checkoutSession, setCheckoutSession] = useState<BillingCheckoutSession | null>(null);
  const [provider, setProvider] = useState('deepseek');
  const [model, setModel] = useState('deepseek/deepseek-v4-flash');
  const apiKeyInputRef = useRef<HTMLInputElement | null>(null);
  const requestSeqRef = useRef(0);

  const loadAccount = useCallback(async () => {
    const requestSeq = requestSeqRef.current + 1;
    requestSeqRef.current = requestSeq;
    setLoading(true);
    setError(null);
    try {
      const [response, billingResponse] = await Promise.all([
        platformApi.account(),
        platformApi.billingAccount(),
      ]);
      if (requestSeq !== requestSeqRef.current) {
        return;
      }
      setAccount(response);
      setBilling(billingResponse);
    } catch (err) {
      if (requestSeq !== requestSeqRef.current) {
        return;
      }
      setError(errorMessage(err, 'Account data failed to load'));
    } finally {
      if (requestSeq === requestSeqRef.current) {
        setLoading(false);
      }
    }
  }, []);

  useEffect(() => {
    void loadAccount();
    return () => {
      requestSeqRef.current += 1;
    };
  }, [loadAccount]);

  const handleSaveApiKey = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const apiKey = apiKeyInputRef.current?.value?.trim() ?? '';
    if (!apiKey) {
      setError('API key is required');
      return;
    }
    setSaveState('saving');
    setError(null);
    try {
      await platformApi.saveApiKey({ provider, model, apiKey });
      if (apiKeyInputRef.current) {
        apiKeyInputRef.current.value = '';
      }
      setSaveState('saved');
      await loadAccount();
    } catch (err) {
      setError(errorMessage(err, 'API key save failed'));
      setSaveState('idle');
    }
  };

  const handleSandboxUpgrade = async () => {
    setCheckoutState('creating');
    setCheckoutSession(null);
    setError(null);
    try {
      const session = await platformApi.createSandboxCheckout('pro' as PlatformPlan);
      setCheckoutSession(session);
      await loadAccount();
    } catch (err) {
      setError(errorMessage(err, 'Sandbox checkout failed'));
    } finally {
      setCheckoutState('idle');
    }
  };

  const quotaBuckets = account?.quotaBuckets ?? [];
  const enabledKeys = account?.apiKeys?.filter((item) => item.enabled) ?? [];
  const billingEvents = billing?.recentEvents ?? [];
  const billingSessions = billing?.checkoutSessions ?? [];

  return (
    <AppPage>
      <div className="space-y-5">
        <PageHeader
          eyebrow="Platform account"
          title="Account"
          description="Manage quota, user-owned API keys, history isolation, and local sandbox billing. Informational analysis only; not investment advice."
          actions={(
            <button
              type="button"
              className="btn-secondary inline-flex items-center gap-2"
              onClick={() => void loadAccount()}
              disabled={loading}
            >
              <RefreshCw className={cn('h-4 w-4', loading ? 'animate-spin' : '')} />
              {loading ? 'Refreshing' : 'Refresh'}
            </button>
          )}
        />

        {error ? (
          <div role="alert" className="rounded-lg border border-danger/30 bg-danger/10 px-4 py-3 text-sm text-danger">
            {error}
          </div>
        ) : null}

        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          <StatCard label="Email" value={account?.user.email ?? '-'} hint={account?.user.role ?? '-'} icon={<UserRound className="h-5 w-5" />} tone="primary" />
          <StatCard label="Plan" value={account?.user.plan ?? '-'} hint={`Status: ${account?.user.status ?? '-'}`} icon={<ShieldCheck className="h-5 w-5" />} />
          <StatCard label="Weekly remaining" value={formatLimit(account?.quota.remaining)} hint={`Used ${account?.quota.used ?? 0} of ${formatLimit(account?.quota.weeklyLimit)}`} icon={<Gauge className="h-5 w-5" />} />
          <StatCard label="Recommended" value={account?.recommendedQueryMode ?? '-'} hint={`Recommended mode: ${account?.recommendedQueryMode ?? '-'}`} icon={<KeyRound className="h-5 w-5" />} />
        </div>

        <section className="grid gap-5 xl:grid-cols-[minmax(0,0.95fr)_minmax(0,1.05fr)]">
          <Card title="Account details" subtitle="Current platform user" className="rounded-lg">
            {loading && !account ? (
              <div className="h-32 animate-pulse rounded-lg bg-hover/70" />
            ) : account ? (
              <dl className="grid gap-3 text-sm">
                <div className="flex items-center justify-between gap-3 rounded-lg bg-hover/40 px-3 py-2">
                  <dt className="text-secondary-text">Email</dt>
                  <dd className="truncate font-medium text-foreground">{account.user.email}</dd>
                </div>
                <div className="flex items-center justify-between gap-3 rounded-lg bg-hover/40 px-3 py-2">
                  <dt className="text-secondary-text">Role</dt>
                  <dd className="font-medium text-foreground">{account.user.role}</dd>
                </div>
                <div className="flex items-center justify-between gap-3 rounded-lg bg-hover/40 px-3 py-2">
                  <dt className="text-secondary-text">Plan</dt>
                  <dd className="font-medium text-foreground">{account.user.plan}</dd>
                </div>
                <div className="flex items-center justify-between gap-3 rounded-lg bg-hover/40 px-3 py-2">
                  <dt className="text-secondary-text">Recommended mode</dt>
                  <dd className="font-medium text-foreground">Recommended mode: {account.recommendedQueryMode}</dd>
                </div>
              </dl>
            ) : (
              <p className="text-sm text-secondary-text">No account data.</p>
            )}
          </Card>

          <Card title="Quota buckets" subtitle="Weekly quota by lane" className="rounded-lg">
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-border/70 text-sm">
                <thead className="text-left text-xs uppercase tracking-[0.16em] text-secondary-text">
                  <tr>
                    <th className="px-3 py-2 font-medium">Bucket</th>
                    <th className="px-3 py-2 font-medium">Used</th>
                    <th className="px-3 py-2 font-medium">Remaining</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border/60">
                  {quotaBuckets.map((bucket) => (
                    <tr key={bucket.quotaBucket} className="hover:bg-hover/60">
                      <td className="px-3 py-2 font-medium text-foreground">{bucket.quotaBucket}</td>
                      <td className="px-3 py-2 text-secondary-text">{formatUsage(bucket)}</td>
                      <td className="px-3 py-2 text-secondary-text">{formatLimit(bucket.remaining)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {!loading && quotaBuckets.length === 0 ? (
                <p className="py-6 text-sm text-secondary-text">No quota bucket data.</p>
              ) : null}
            </div>
          </Card>
        </section>

        <section className="grid gap-5 xl:grid-cols-2">
          <Card title="API key custody" subtitle="Stored keys are shown only as masked values" className="rounded-lg">
            <div className="space-y-4">
              <div className="space-y-2">
                {enabledKeys.length > 0 ? enabledKeys.map((item) => (
                  <div key={`${item.provider}-${item.model ?? ''}`} className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-border/70 px-3 py-2 text-sm">
                    <div>
                      <p className="font-medium text-foreground">{item.provider}</p>
                      <p className="text-secondary-text">{item.model || 'default model'}</p>
                    </div>
                    <span className="rounded-md bg-hover px-2 py-1 font-mono text-xs text-secondary-text">{item.maskedKey}</span>
                  </div>
                )) : (
                  <p className="text-sm text-secondary-text">No user API key saved.</p>
                )}
              </div>

              <form className="grid gap-3" onSubmit={(event) => void handleSaveApiKey(event)}>
                <label className="grid gap-1 text-sm font-medium text-foreground">
                  Provider
                  <select className="input-base" value={provider} onChange={(event) => setProvider(event.target.value)}>
                    <option value="deepseek">deepseek</option>
                    <option value="openai">openai</option>
                    <option value="anthropic">anthropic</option>
                    <option value="gemini">gemini</option>
                  </select>
                </label>
                <label className="grid gap-1 text-sm font-medium text-foreground">
                  Model
                  <input className="input-base" value={model} onChange={(event) => setModel(event.target.value)} />
                </label>
                <label className="grid gap-1 text-sm font-medium text-foreground">
                  API key
                  <input ref={apiKeyInputRef} className="input-base" type="password" autoComplete="off" />
                </label>
                <button type="submit" className="btn-primary inline-flex items-center justify-center gap-2" disabled={saveState === 'saving'}>
                  <KeyRound className="h-4 w-4" />
                  {saveState === 'saving' ? 'Saving' : 'Save API key'}
                </button>
                {saveState === 'saved' ? <p className="text-sm text-success">API key saved as masked custody record.</p> : null}
              </form>
            </div>
          </Card>

          <Card title="Local payment sandbox" subtitle="Mock billing only; real payment remains disabled" className="rounded-lg">
            <div className="space-y-4">
              <div className="rounded-lg border border-warning/30 bg-warning/10 px-3 py-2 text-sm text-secondary-text">
                {billing?.copy ?? 'Local sandbox checkout can create a signed test session for a free to pro upgrade. This is not real payment processing.'}
              </div>
              <div className="grid gap-3 md:grid-cols-2">
                <div className="rounded-lg border border-border/70 px-3 py-2 text-sm">
                  <p className="text-secondary-text">Subscription</p>
                  <p className="mt-1 font-medium text-foreground">
                    {billing?.subscription ? `${billing.subscription.plan} / ${billing.subscription.status}` : '-'}
                  </p>
                </div>
                <div className="rounded-lg border border-border/70 px-3 py-2 text-sm">
                  <p className="text-secondary-text">Billing mode</p>
                  <p className="mt-1 font-medium text-foreground">{billing?.mode ?? '-'}</p>
                </div>
              </div>
              <button
                type="button"
                className="btn-secondary inline-flex items-center gap-2"
                onClick={() => void handleSandboxUpgrade()}
                disabled={checkoutState === 'creating'}
              >
                <CreditCard className="h-4 w-4" />
                {checkoutState === 'creating' ? 'Creating sandbox session' : 'Start sandbox upgrade'}
              </button>
              {checkoutSession ? (
                <div className="space-y-2 rounded-lg border border-border/70 px-3 py-3 text-sm">
                  <p className="font-medium text-foreground">Local sandbox checkout created</p>
                  <div className="grid gap-1">
                    <span className="text-secondary-text">Checkout URL</span>
                    <span className="break-all font-mono text-xs text-foreground">{checkoutSession.checkoutUrl}</span>
                  </div>
                  <div className="grid gap-1">
                    <span className="text-secondary-text">Session ID</span>
                    <span className="break-all font-mono text-xs text-foreground">{checkoutSession.providerSessionId}</span>
                  </div>
                </div>
              ) : null}
              <div className="space-y-2">
                <p className="text-sm font-medium text-foreground">Recent checkout sessions</p>
                {billingSessions.length > 0 ? billingSessions.map((session) => (
                  <div key={session.providerSessionId} className="rounded-lg border border-border/70 px-3 py-2 text-sm">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <span className="font-mono text-xs text-foreground">{session.providerSessionId}</span>
                      <span className="rounded-md bg-hover px-2 py-1 text-xs text-secondary-text">{session.status ?? '-'}</span>
                    </div>
                    <p className="mt-1 text-secondary-text">{session.plan} / {session.provider}</p>
                  </div>
                )) : (
                  <p className="text-sm text-secondary-text">No sandbox checkout sessions.</p>
                )}
              </div>
              <div className="space-y-2">
                <p className="text-sm font-medium text-foreground">Recent billing events</p>
                {billingEvents.length > 0 ? billingEvents.map((event) => (
                  <div key={event.providerEventId} className="rounded-lg border border-border/70 px-3 py-2 text-sm">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <span className="font-medium text-foreground">{event.eventType}</span>
                      <span className="rounded-md bg-hover px-2 py-1 text-xs text-secondary-text">{event.processingStatus ?? '-'}</span>
                    </div>
                    <p className="mt-1 break-all font-mono text-xs text-secondary-text">{event.providerEventId}</p>
                  </div>
                )) : (
                  <p className="text-sm text-secondary-text">No sandbox billing events.</p>
                )}
              </div>
            </div>
          </Card>
        </section>
      </div>
    </AppPage>
  );
};

export default AccountPage;
