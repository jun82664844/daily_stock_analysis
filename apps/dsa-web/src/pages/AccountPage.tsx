import React, { useCallback, useEffect, useRef, useState } from 'react';
import { CreditCard, Gauge, KeyRound, RefreshCw, ShieldCheck, UserRound } from 'lucide-react';
import { platformApi, type BillingCheckoutSession, type PlatformAccountSummary, type PlatformBillingAccountResponse, type PlatformModelOption, type PlatformPlan, type PlatformQuotaBucket } from '../api/platform';
import { AppPage, Card, PageHeader, StatCard } from '../components/common';
import BoostPackCardV112 from '../components/platform/BoostPackCardV112';
import ModelConnectionWizardV112 from '../components/platform/ModelConnectionWizardV112';
import { useUiLanguage } from '../contexts/UiLanguageContext';
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

const ACCOUNT_TEXT = {
  zh: {
    pageEyebrow: '平台账户',
    pageTitle: '账户',
    pageDescription: '管理套餐、额度、自带 API Key、历史隔离和本地支付沙箱；分析内容仅供信息分析，不构成投资建议。',
    refresh: '刷新',
    refreshing: '刷新中',
    email: '邮箱',
    plan: '套餐',
    status: '状态',
    role: '角色',
    weeklyRemaining: '本周剩余额度',
    usedOf: '已用 {used} / {limit}',
    recommended: '推荐模式',
    recommendedMode: '推荐模式：{mode}',
    accountDetails: '账户详情',
    currentPlatformUser: '当前平台用户',
    noAccountData: '暂无账户数据。',
    quotaBuckets: '额度桶',
    quotaSubtitle: '按通道统计的每周额度',
    bucket: '额度类型',
    used: '已用',
    remaining: '剩余',
    noQuotaData: '暂无额度桶数据。',
    unlimited: '不限',
    apiKeyCustody: 'API Key 托管',
    apiKeySubtitle: '已保存密钥只显示脱敏值',
    noApiKeySaved: '未保存用户 API Key。',
    defaultModel: '默认模型',
    provider: '服务商',
    model: '模型',
    apiKey: 'API Key',
    saving: '保存中',
    saveApiKey: '保存 API Key',
    apiKeySaved: 'API Key 已保存为脱敏托管记录。',
    sandboxEyebrow: '仅本地模拟账单，真实支付仍关闭',
    paymentSandbox: '本地支付沙箱',
    paymentSandboxSubtitle: '模拟账单；真实支付仍关闭',
    sandboxCopy: '本地沙箱账单只会创建带签名的测试结账会话，用于模拟免费版升级到专业版；不会处理真实支付。',
    subscription: '订阅',
    billingMode: '账单模式',
    creatingSandboxSession: '创建沙箱会话中',
    startSandboxUpgrade: '启动沙箱升级',
    checkoutCreated: '本地沙箱结账已创建',
    checkoutUrl: '结账地址',
    sessionId: '会话 ID',
    recentCheckoutSessions: '最近结账会话',
    noCheckoutSessions: '暂无沙箱结账会话。',
    recentBillingEvents: '最近账单事件',
    noBillingEvents: '暂无沙箱账单事件。',
    errorLoad: '账户数据加载失败',
    errorApiKeyRequired: '请填写 API Key',
    errorApiKeySave: 'API Key 保存失败',
    errorSandboxCheckout: '沙箱结账创建失败',
    errorRateLimited: '请求过于频繁，请稍后再试。',
    errorBillingDisabled: '本地 V1 已关闭账单功能',
  },
  en: {
    pageEyebrow: 'Platform account',
    pageTitle: 'Account',
    pageDescription: 'Manage quota, user-owned API keys, history isolation, and local sandbox billing. Informational analysis only; not investment advice.',
    refresh: 'Refresh',
    refreshing: 'Refreshing',
    email: 'Email',
    plan: 'Plan',
    status: 'Status',
    role: 'Role',
    weeklyRemaining: 'Weekly remaining',
    usedOf: 'Used {used} of {limit}',
    recommended: 'Recommended',
    recommendedMode: 'Recommended mode: {mode}',
    accountDetails: 'Account details',
    currentPlatformUser: 'Current platform user',
    noAccountData: 'No account data.',
    quotaBuckets: 'Quota buckets',
    quotaSubtitle: 'Weekly quota by lane',
    bucket: 'Bucket',
    used: 'Used',
    remaining: 'Remaining',
    noQuotaData: 'No quota bucket data.',
    unlimited: 'Unlimited',
    apiKeyCustody: 'API key custody',
    apiKeySubtitle: 'Stored keys are shown only as masked values',
    noApiKeySaved: 'No user API key saved.',
    defaultModel: 'default model',
    provider: 'Provider',
    model: 'Model',
    apiKey: 'API key',
    saving: 'Saving',
    saveApiKey: 'Save API key',
    apiKeySaved: 'API key saved as masked custody record.',
    sandboxEyebrow: 'MOCK BILLING ONLY; REAL PAYMENT REMAINS DISABLED',
    paymentSandbox: 'Local payment sandbox',
    paymentSandboxSubtitle: 'Mock billing only; real payment remains disabled',
    sandboxCopy: 'Local sandbox checkout can create a signed test session for a free to pro upgrade. This is not real payment processing.',
    subscription: 'Subscription',
    billingMode: 'Billing mode',
    creatingSandboxSession: 'Creating sandbox session',
    startSandboxUpgrade: 'Start sandbox upgrade',
    checkoutCreated: 'Local sandbox checkout created',
    checkoutUrl: 'Checkout URL',
    sessionId: 'Session ID',
    recentCheckoutSessions: 'Recent checkout sessions',
    noCheckoutSessions: 'No sandbox checkout sessions.',
    recentBillingEvents: 'Recent billing events',
    noBillingEvents: 'No sandbox billing events.',
    errorLoad: 'Account data failed to load',
    errorApiKeyRequired: 'API key is required',
    errorApiKeySave: 'API key save failed',
    errorSandboxCheckout: 'Sandbox checkout failed',
    errorRateLimited: 'Too many requests. Please wait before trying again.',
    errorBillingDisabled: 'Billing is disabled in local V1',
  },
} as const;

type AccountText = Record<keyof typeof ACCOUNT_TEXT.en, string>;

function fillText(template: string, values: Record<string, string | number>): string {
  return template.replace(/\{(\w+)\}/g, (match, key) => {
    const value = values[key];
    return value === undefined ? match : String(value);
  });
}

function formatLimit(value: number | null | undefined, text: AccountText, language: 'zh' | 'en'): string {
  if (value === null || value === undefined) {
    return text.unlimited;
  }
  return new Intl.NumberFormat(language === 'en' ? 'en-US' : 'zh-CN').format(value);
}

function formatUsage(bucket: PlatformQuotaBucket, text: AccountText, language: 'zh' | 'en'): string {
  const used = new Intl.NumberFormat(language === 'en' ? 'en-US' : 'zh-CN').format(bucket.used ?? 0);
  return `${used} / ${formatLimit(bucket.weeklyLimit, text, language)}`;
}

function localizePlan(value: string | null | undefined, language: 'zh' | 'en'): string {
  if (!value || language === 'en') return value || '-';
  return ({
    free: '免费版',
    pro: '专业版',
    premium: '高级版',
  } as Record<string, string>)[value] || value;
}

function localizeRole(value: string | null | undefined, language: 'zh' | 'en'): string {
  if (!value || language === 'en') return value || '-';
  return ({
    user: '普通用户',
    admin: '管理员',
    operator: '运营',
  } as Record<string, string>)[value] || value;
}

function localizeStatus(value: string | null | undefined, language: 'zh' | 'en'): string {
  if (!value || language === 'en') return value || '-';
  return ({
    active: '正常',
    none: '未订阅',
    completed: '已完成',
    processed: '已处理',
    pending: '待处理',
    failed: '失败',
    cancelled: '已取消',
    canceled: '已取消',
    expired: '已过期',
    disabled: '已停用',
    suspended: '已暂停',
  } as Record<string, string>)[value] || value;
}

function localizeMode(value: string | null | undefined, language: 'zh' | 'en'): string {
  if (!value || language === 'en') return value || '-';
  return ({
    user: '用户自带 API',
    platform: '平台 API',
    local: '本地模型',
    no_ai: '不使用 AI',
    local_sandbox: '本地沙箱',
    disabled: '已关闭',
  } as Record<string, string>)[value] || value;
}

function localizeProvider(value: string | null | undefined, language: 'zh' | 'en'): string {
  if (!value || language === 'en') return value || '-';
  return value === 'sandbox' ? '沙箱' : value;
}

function localizeQuotaBucket(value: string | null | undefined, language: 'zh' | 'en'): string {
  if (!value || language === 'en') return value || '-';
  return ({
    basic_query: '免费行情查询',
    ai_quick: '平台快速 AI',
    ai_deep: '平台深度 AI',
    ai_quick_user_key: '自带 Key 快速 AI',
    ai_deep_user_key: '自带 Key 深度 AI',
    ai_local: '本地模型 AI',
    market_review: '大盘复盘',
  } as Record<string, string>)[value] || value;
}

function localizeBillingEvent(value: string | null | undefined, language: 'zh' | 'en'): string {
  if (!value || language === 'en') return value || '-';
  return ({
    'checkout.completed': '结账完成',
    'checkout.cancelled': '结账取消',
    'checkout.canceled': '结账取消',
    'checkout.expired': '结账过期',
    'payment.failed': '支付失败',
    'subscription.updated': '订阅更新',
  } as Record<string, string>)[value] || value;
}

function localizeBillingCopy(value: string | null | undefined, text: AccountText, language: 'zh' | 'en'): string {
  if (language === 'en') return value || text.sandboxCopy;
  if (!value) return text.sandboxCopy;
  if (value.includes('not real payment processing') || value.includes('sandbox billing')) {
    return '本地沙箱账单仅用于模拟；不处理真实支付。';
  }
  return value;
}

function localizeError(value: string, text: AccountText, language: 'zh' | 'en'): string {
  if (language === 'en') return value;
  if (/too many requests/i.test(value)) return text.errorRateLimited;
  if (/billing is disabled/i.test(value)) return text.errorBillingDisabled;
  return value;
}

const AccountPage: React.FC = () => {
  const { language } = useUiLanguage();
  const text = ACCOUNT_TEXT[language];
  const [account, setAccount] = useState<PlatformAccountSummary | null>(null);
  const [billing, setBilling] = useState<PlatformBillingAccountResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [saveState, setSaveState] = useState<'idle' | 'saving' | 'saved'>('idle');
  const [checkoutState, setCheckoutState] = useState<'idle' | 'creating'>('idle');
  const [checkoutSession, setCheckoutSession] = useState<BillingCheckoutSession | null>(null);
  const [modelOptions, setModelOptions] = useState<PlatformModelOption[]>([]);
  const requestSeqRef = useRef(0);

  const loadAccount = useCallback(async () => {
    const requestSeq = requestSeqRef.current + 1;
    requestSeqRef.current = requestSeq;
    setLoading(true);
    setError(null);
    try {
      const modelOptionsPromise = typeof platformApi.modelOptions === 'function'
        ? platformApi.modelOptions()
        : Promise.resolve({ selectedOptionId: 'platform_recommended', options: [], realByokStatus: '' });
      const [response, billingResponse, modelOptionsResponse] = await Promise.all([
        platformApi.account(),
        platformApi.billingAccount(),
        modelOptionsPromise,
      ]);
      if (requestSeq !== requestSeqRef.current) {
        return;
      }
      setAccount(response);
      setBilling(billingResponse);
      setModelOptions(modelOptionsResponse.options);
    } catch (err) {
      if (requestSeq !== requestSeqRef.current) {
        return;
      }
      setError(localizeError(errorMessage(err, text.errorLoad), text, language));
    } finally {
      if (requestSeq === requestSeqRef.current) {
        setLoading(false);
      }
    }
  }, [language, text]);

  useEffect(() => {
    void loadAccount();
    return () => {
      requestSeqRef.current += 1;
    };
  }, [loadAccount]);

  const handleConnectApiKey = async ({ provider, apiKey }: { provider: 'openai' | 'anthropic' | 'deepseek'; apiKey: string }) => {
    setSaveState('saving');
    setError(null);
    try {
      await platformApi.connectApiKey({ provider, apiKey });
      setSaveState('saved');
      await loadAccount();
    } catch (err) {
      setError(localizeError(errorMessage(err, text.errorApiKeySave), text, language));
      setSaveState('idle');
    }
  };

  const handleBoostPackPurchase = async () => {
    setCheckoutState('creating');
    setError(null);
    try {
      const session = await platformApi.createBoostPackCheckout();
      setCheckoutSession(session);
      await loadAccount();
    } catch (err) {
      setError(localizeError(errorMessage(err, text.errorSandboxCheckout), text, language));
    } finally {
      setCheckoutState('idle');
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
      setError(localizeError(errorMessage(err, text.errorSandboxCheckout), text, language));
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
          eyebrow={text.pageEyebrow}
          title={text.pageTitle}
          description={text.pageDescription}
          actions={(
            <button
              type="button"
              className="btn-secondary inline-flex items-center gap-2"
              onClick={() => void loadAccount()}
              disabled={loading}
            >
              <RefreshCw className={cn('h-4 w-4', loading ? 'animate-spin' : '')} />
              {loading ? text.refreshing : text.refresh}
            </button>
          )}
        />

        {error ? (
          <div role="alert" className="rounded-lg border border-danger/30 bg-danger/10 px-4 py-3 text-sm text-danger">
            {error}
          </div>
        ) : null}

        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          <StatCard label={text.email} value={account?.user.email ?? '-'} hint={localizeRole(account?.user.role, language)} icon={<UserRound className="h-5 w-5" />} tone="primary" />
          <StatCard label={text.plan} value={localizePlan(account?.user.plan, language)} hint={`${text.status}: ${localizeStatus(account?.user.status, language)}`} icon={<ShieldCheck className="h-5 w-5" />} />
          <StatCard label={text.weeklyRemaining} value={formatLimit(account?.quota.remaining, text, language)} hint={fillText(text.usedOf, { used: account?.quota.used ?? 0, limit: formatLimit(account?.quota.weeklyLimit, text, language) })} icon={<Gauge className="h-5 w-5" />} />
          <StatCard label={text.recommended} value={localizeMode(account?.recommendedQueryMode, language)} hint={fillText(text.recommendedMode, { mode: localizeMode(account?.recommendedQueryMode, language) })} icon={<KeyRound className="h-5 w-5" />} />
        </div>

        <section className="grid gap-5 xl:grid-cols-[minmax(0,0.95fr)_minmax(0,1.05fr)]">
          <Card title={text.accountDetails} subtitle={text.currentPlatformUser} className="rounded-lg">
            {loading && !account ? (
              <div className="h-32 animate-pulse rounded-lg bg-hover/70" />
            ) : account ? (
              <dl className="grid gap-3 text-sm">
                <div className="flex items-center justify-between gap-3 rounded-lg bg-hover/40 px-3 py-2">
                  <dt className="text-secondary-text">{text.email}</dt>
                  <dd className="truncate font-medium text-foreground">{account.user.email}</dd>
                </div>
                <div className="flex items-center justify-between gap-3 rounded-lg bg-hover/40 px-3 py-2">
                  <dt className="text-secondary-text">{text.role}</dt>
                  <dd className="font-medium text-foreground">{localizeRole(account.user.role, language)}</dd>
                </div>
                <div className="flex items-center justify-between gap-3 rounded-lg bg-hover/40 px-3 py-2">
                  <dt className="text-secondary-text">{text.plan}</dt>
                  <dd className="font-medium text-foreground">{localizePlan(account.user.plan, language)}</dd>
                </div>
                <div className="flex items-center justify-between gap-3 rounded-lg bg-hover/40 px-3 py-2">
                  <dt className="text-secondary-text">{text.recommended}</dt>
                  <dd className="font-medium text-foreground">{fillText(text.recommendedMode, { mode: localizeMode(account.recommendedQueryMode, language) })}</dd>
                </div>
              </dl>
            ) : (
              <p className="text-sm text-secondary-text">{text.noAccountData}</p>
            )}
          </Card>

          <Card title={text.quotaBuckets} subtitle={text.quotaSubtitle} className="rounded-lg">
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-border/70 text-sm">
                <thead className="text-left text-xs uppercase tracking-[0.16em] text-secondary-text">
                  <tr>
                    <th className="px-3 py-2 font-medium">{text.bucket}</th>
                    <th className="px-3 py-2 font-medium">{text.used}</th>
                    <th className="px-3 py-2 font-medium">{text.remaining}</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border/60">
                  {quotaBuckets.map((bucket) => (
                    <tr key={bucket.quotaBucket} className="hover:bg-hover/60">
                      <td className="px-3 py-2 font-medium text-foreground">{localizeQuotaBucket(bucket.quotaBucket, language)}</td>
                      <td className="px-3 py-2 text-secondary-text">{formatUsage(bucket, text, language)}</td>
                      <td className="px-3 py-2 text-secondary-text">{formatLimit(bucket.remaining, text, language)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {!loading && quotaBuckets.length === 0 ? (
                <p className="py-6 text-sm text-secondary-text">{text.noQuotaData}</p>
              ) : null}
            </div>
          </Card>
        </section>

        <section className="grid gap-5 xl:grid-cols-2">
          <Card title={text.apiKeyCustody} subtitle={text.apiKeySubtitle} className="rounded-lg">
            <div className="space-y-4">
              <div className="space-y-2">
                {enabledKeys.length > 0 ? enabledKeys.map((item) => (
                  <div key={`${item.provider}-${item.model ?? ''}`} className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-border/70 px-3 py-2 text-sm">
                    <div>
                      <p className="font-medium text-foreground">{item.provider}</p>
                      <p className="text-secondary-text">{item.model || text.defaultModel}</p>
                    </div>
                    <span className="rounded-md bg-hover px-2 py-1 font-mono text-xs text-secondary-text">{item.maskedKey}</span>
                  </div>
                )) : (
                  <p className="text-sm text-secondary-text">{text.noApiKeySaved}</p>
                )}
              </div>

              <ModelConnectionWizardV112
                language={language}
                onConnect={handleConnectApiKey}
                onCreatePairing={() => platformApi.createLocalConnectorPairing()}
                onRefreshModels={async () => {
                  const response = await platformApi.modelOptions();
                  setModelOptions(response.options);
                }}
              />
              {saveState === 'saved' ? <p className="text-sm text-success">{text.apiKeySaved}</p> : null}
              {modelOptions.length > 0 ? (
                <p className="text-xs text-secondary-text">
                  {language === 'zh' ? `已开放 ${modelOptions.length} 个安全模型选项。` : `${modelOptions.length} safe model options available.`}
                </p>
              ) : null}
            </div>
          </Card>

          <Card title={text.paymentSandbox} subtitle={text.paymentSandboxSubtitle} className="rounded-lg">
            <div className="space-y-4">
              <p className="label-uppercase">{text.sandboxEyebrow}</p>
              <div className="rounded-lg border border-warning/30 bg-warning/10 px-3 py-2 text-sm text-secondary-text">
                {localizeBillingCopy(billing?.copy, text, language)}
              </div>
              <div className="grid gap-3 md:grid-cols-2">
                <div className="rounded-lg border border-border/70 px-3 py-2 text-sm">
                  <p className="text-secondary-text">{text.subscription}</p>
                  <p className="mt-1 font-medium text-foreground">
                    {billing?.subscription ? `${localizePlan(billing.subscription.plan, language)} / ${localizeStatus(billing.subscription.status, language)}` : '-'}
                  </p>
                </div>
                <div className="rounded-lg border border-border/70 px-3 py-2 text-sm">
                  <p className="text-secondary-text">{text.billingMode}</p>
                  <p className="mt-1 font-medium text-foreground">{localizeMode(billing?.mode, language)}</p>
                </div>
              </div>
              <button
                type="button"
                className="btn-secondary inline-flex items-center gap-2"
                onClick={() => void handleSandboxUpgrade()}
                disabled={checkoutState === 'creating'}
              >
                <CreditCard className="h-4 w-4" />
                {checkoutState === 'creating' ? text.creatingSandboxSession : text.startSandboxUpgrade}
              </button>
              {checkoutSession ? (
                <div className="space-y-2 rounded-lg border border-border/70 px-3 py-3 text-sm">
                  <p className="font-medium text-foreground">{text.checkoutCreated}</p>
                  <div className="grid gap-1">
                    <span className="text-secondary-text">{text.checkoutUrl}</span>
                    <span className="break-all font-mono text-xs text-foreground">{checkoutSession.checkoutUrl}</span>
                  </div>
                  <div className="grid gap-1">
                    <span className="text-secondary-text">{text.sessionId}</span>
                    <span className="break-all font-mono text-xs text-foreground">{checkoutSession.providerSessionId}</span>
                  </div>
                </div>
              ) : null}
              <div className="space-y-2">
                <p className="text-sm font-medium text-foreground">{text.recentCheckoutSessions}</p>
                {billingSessions.length > 0 ? billingSessions.map((session) => (
                  <div key={session.providerSessionId} className="rounded-lg border border-border/70 px-3 py-2 text-sm">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <span className="font-mono text-xs text-foreground">{session.providerSessionId}</span>
                      <span className="rounded-md bg-hover px-2 py-1 text-xs text-secondary-text">{localizeStatus(session.status, language)}</span>
                    </div>
                    <p className="mt-1 text-secondary-text">{localizePlan(session.plan, language)} / {localizeProvider(session.provider, language)}</p>
                  </div>
                )) : (
                  <p className="text-sm text-secondary-text">{text.noCheckoutSessions}</p>
                )}
              </div>
              <div className="space-y-2">
                <p className="text-sm font-medium text-foreground">{text.recentBillingEvents}</p>
                {billingEvents.length > 0 ? billingEvents.map((event) => (
                  <div key={event.providerEventId} className="rounded-lg border border-border/70 px-3 py-2 text-sm">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <span className="font-medium text-foreground">{localizeBillingEvent(event.eventType, language)}</span>
                      <span className="rounded-md bg-hover px-2 py-1 text-xs text-secondary-text">{localizeStatus(event.processingStatus, language)}</span>
                    </div>
                    <p className="mt-1 break-all font-mono text-xs text-secondary-text">{event.providerEventId}</p>
                  </div>
                )) : (
                  <p className="text-sm text-secondary-text">{text.noBillingEvents}</p>
                )}
              </div>
            </div>
          </Card>
        </section>

        {billing?.boostPack ? (
          <BoostPackCardV112 language={language} product={billing.boostPack} onPurchase={() => void handleBoostPackPurchase()} />
        ) : null}
      </div>
    </AppPage>
  );
};

export default AccountPage;
