import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Activity, CreditCard, Gauge, RefreshCw, RotateCcw, Server, ShieldAlert, ShieldCheck, Users, Zap } from 'lucide-react';
import { platformApi, type PlatformAuditEvent, type PlatformBillingEvent, type PlatformLocalStatusResponse, type PlatformOpsHealthResponse, type PlatformProductionReadinessResponse, type PlatformRetentionFunnelResponse, type PlatformUsageBucket, type PlatformUser } from '../api/platform';
import { stocksApi, type BasicPrewarmResponse, type MarketSourceHealthResponse, type MarketSourceRecoveryResponse } from '../api/stocks';
import type { ParsedApiError } from '../api/error';
import { ApiErrorAlert, AppPage, Card, EmptyState, PageHeader, StatCard } from '../components/common';
import { RetentionFunnelPanelV97 } from '../components/admin/RetentionFunnelPanelV97';
import { useUiLanguage } from '../contexts/UiLanguageContext';
import type { UiLanguage, UiTextKey, UiTextParams } from '../i18n/uiText';
import { cn } from '../utils/cn';

type Translate = (key: UiTextKey, params?: UiTextParams) => string;

const BUCKET_LABEL_KEYS: Record<string, UiTextKey> = {
  ai_quick: 'admin.bucket.aiQuick',
  ai_quick_user_key: 'admin.bucket.aiQuickUserKey',
  ai_deep: 'admin.bucket.aiDeep',
  ai_deep_user_key: 'admin.bucket.aiDeepUserKey',
  ai_local: 'admin.bucket.aiLocal',
  market_review: 'admin.bucket.marketReview',
};

const DEFAULT_PREWARM_SYMBOLS = ['600519', 'AAPL', 'HK00700', 'BTC-USD'] as const;

function getLocale(language: UiLanguage): string {
  return language === 'en' ? 'en-US' : 'zh-CN';
}

function formatNumber(value: number | null | undefined, language: UiLanguage): string {
  return new Intl.NumberFormat(getLocale(language)).format(value ?? 0);
}

function formatDateTime(value: string | null | undefined, language: UiLanguage): string {
  if (!value) {
    return '-';
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return new Intl.DateTimeFormat(getLocale(language), {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  }).format(date);
}

function getBucketLabel(bucket: string, t: Translate): string {
  const key = BUCKET_LABEL_KEYS[bucket];
  return key ? t(key) : bucket || '-';
}

function formatLimit(value: number | null | undefined, language: UiLanguage, t: Translate): string {
  if (value === null || value === undefined) {
    return t('admin.unlimited');
  }
  return formatNumber(value, language);
}

function buildParsedError(error: unknown, t: Translate): ParsedApiError {
  if (error && typeof error === 'object' && 'parsedError' in error) {
    const parsedError = (error as { parsedError?: ParsedApiError }).parsedError;
    if (parsedError) {
      return parsedError;
    }
  }

  const message = error instanceof Error ? error.message : t('admin.errorMessage');
  return {
    title: t('admin.errorTitle'),
    message,
    rawMessage: message,
    category: 'http_error',
  };
}

function formatLatency(value: number | null | undefined, language: UiLanguage): string {
  if (value === null || value === undefined) {
    return '-';
  }
  return `${formatNumber(value, language)} ms`;
}

const SECRET_VALUE_PATTERNS = [
  /\bsk-[A-Za-z0-9._-]{6,}\b/g,
  /\bBearer\s+[A-Za-z0-9._-]{8,}\b/gi,
];

function normalizeMetadataKey(key: string): string {
  return key.replace(/[^A-Za-z0-9]/g, '').toLowerCase();
}

function isSecretMetadataKey(key: string): boolean {
  const normalized = normalizeMetadataKey(key);
  return normalized === 'apikey'
    || normalized === 'authorization'
    || normalized === 'password'
    || normalized === 'secret'
    || normalized === 'token'
    || normalized.endsWith('apikey')
    || normalized.endsWith('token')
    || normalized.includes('secret')
    || normalized.includes('password');
}

function redactMetadataText(value: string): string {
  return SECRET_VALUE_PATTERNS.reduce(
    (text, pattern) => text.replace(pattern, '[REDACTED]'),
    value,
  );
}

function redactAuditMetadata(value: unknown): unknown {
  if (Array.isArray(value)) {
    return value.map((item) => redactAuditMetadata(item));
  }
  if (value && typeof value === 'object') {
    return Object.fromEntries(
      Object.entries(value as Record<string, unknown>).map(([key, item]) => [
        key,
        isSecretMetadataKey(key) ? '[REDACTED]' : redactAuditMetadata(item),
      ]),
    );
  }
  if (typeof value === 'string') {
    return redactMetadataText(value);
  }
  return value;
}

function auditMetadataDisplay(metadata: PlatformAuditEvent['metadata']): string {
  return JSON.stringify(redactAuditMetadata(metadata ?? {}));
}

const AdminPage: React.FC = () => {
  const { language, t } = useUiLanguage();
  const [users, setUsers] = useState<PlatformUser[]>([]);
  const [usage, setUsage] = useState<PlatformUsageBucket[]>([]);
  const [auditEvents, setAuditEvents] = useState<PlatformAuditEvent[]>([]);
  const [billingEvents, setBillingEvents] = useState<PlatformBillingEvent[]>([]);
  const [localStatus, setLocalStatus] = useState<PlatformLocalStatusResponse | null>(null);
  const [productionReadiness, setProductionReadiness] = useState<PlatformProductionReadinessResponse | null>(null);
  const [opsHealth, setOpsHealth] = useState<PlatformOpsHealthResponse | null>(null);
  const [retentionFunnel, setRetentionFunnel] = useState<PlatformRetentionFunnelResponse | null>(null);
  const [marketSourceHealth, setMarketSourceHealth] = useState<MarketSourceHealthResponse | null>(null);
  const [prewarmResult, setPrewarmResult] = useState<BasicPrewarmResponse | null>(null);
  const [recoveryResult, setRecoveryResult] = useState<MarketSourceRecoveryResponse | null>(null);
  const [prewarming, setPrewarming] = useState(false);
  const [recovering, setRecovering] = useState(false);
  const [prewarmError, setPrewarmError] = useState<ParsedApiError | null>(null);
  const [recoveryError, setRecoveryError] = useState<ParsedApiError | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<ParsedApiError | null>(null);
  const requestSeqRef = useRef(0);

  const loadAdminData = useCallback(async () => {
    const requestSeq = requestSeqRef.current + 1;
    requestSeqRef.current = requestSeq;
    setLoading(true);
    setError(null);
    try {
      const [usersResponse, usageResponse, billingResponse, localStatusResponse, productionReadinessResponse, opsHealthResponse, retentionFunnelResponse, marketSourceResponse] = await Promise.all([
        platformApi.adminUsers(),
        platformApi.adminUsage(),
        platformApi.adminBillingEvents(),
        platformApi.adminLocalStatus(),
        platformApi.adminProductionReadiness(),
        platformApi.adminOpsHealth(),
        platformApi.adminRetentionFunnel(),
        stocksApi.marketSourceHealth(),
      ]);
      if (requestSeq !== requestSeqRef.current) {
        return;
      }
      setUsers(usersResponse.users ?? []);
      setUsage(usageResponse.usage ?? []);
      setAuditEvents(usageResponse.auditEvents ?? []);
      setBillingEvents(billingResponse.events ?? []);
      setLocalStatus(localStatusResponse);
      setProductionReadiness(productionReadinessResponse);
      setOpsHealth(opsHealthResponse);
      setRetentionFunnel(retentionFunnelResponse);
      setMarketSourceHealth(marketSourceResponse);
    } catch (err) {
      if (requestSeq !== requestSeqRef.current) {
        return;
      }
      setError(buildParsedError(err, t));
    } finally {
      if (requestSeq === requestSeqRef.current) {
        setLoading(false);
      }
    }
  }, [t]);

  useEffect(() => {
    void loadAdminData();
    return () => {
      requestSeqRef.current += 1;
    };
  }, [loadAdminData]);

  const handlePrewarmMarketCache = useCallback(async () => {
    setPrewarming(true);
    setPrewarmError(null);
    try {
      const result = await stocksApi.prewarm([...DEFAULT_PREWARM_SYMBOLS]);
      setPrewarmResult(result);
      const sourceResponse = await stocksApi.marketSourceHealth();
      setMarketSourceHealth(sourceResponse);
    } catch (err) {
      setPrewarmError(buildParsedError(err, t));
    } finally {
      setPrewarming(false);
    }
  }, [t]);

  const handleRecoverMarketSources = useCallback(async () => {
    setRecovering(true);
    setRecoveryError(null);
    try {
      const result = await stocksApi.recoverMarketSources({
        market: 'all',
        symbols: [...DEFAULT_PREWARM_SYMBOLS],
        prewarm: true,
      });
      setRecoveryResult(result);
      const sourceResponse = await stocksApi.marketSourceHealth();
      setMarketSourceHealth(sourceResponse);
    } catch (err) {
      setRecoveryError(buildParsedError(err, t));
    } finally {
      setRecovering(false);
    }
  }, [t]);

  const totalUsageUnits = useMemo(() => usage.reduce((total, row) => total + (row.used ?? 0), 0), [usage]);
  const marketSourceRows = useMemo(
    () => (marketSourceHealth?.lanes ?? []).flatMap((lane) => [
      ...lane.quoteSources.map((source) => ({ lane, source, kind: 'quote' })),
      ...lane.historySources.map((source) => ({ lane, source, kind: 'history' })),
    ]),
    [marketSourceHealth],
  );

  return (
    <AppPage>
      <div className="space-y-5">
        <PageHeader
          eyebrow={t('admin.eyebrow')}
          title={t('admin.title')}
          description={t('admin.description')}
          actions={(
            <>
              <button
                type="button"
                className="btn-primary inline-flex items-center gap-2"
                onClick={() => void handlePrewarmMarketCache()}
                disabled={loading || prewarming || recovering}
              >
                <Zap className={cn('h-4 w-4', prewarming ? 'animate-pulse' : '')} />
                {prewarming ? t('admin.prewarmingMarketCache') : t('admin.prewarmMarketCache')}
              </button>
              <button
                type="button"
                className="btn-secondary inline-flex items-center gap-2"
                onClick={() => void handleRecoverMarketSources()}
                disabled={loading || prewarming || recovering}
              >
                <RotateCcw className={cn('h-4 w-4', recovering ? 'animate-spin' : '')} />
                {recovering ? t('admin.recoveringMarketSources') : t('admin.recoverMarketSources')}
              </button>
              <button
                type="button"
                className="btn-secondary inline-flex items-center gap-2"
                onClick={() => void loadAdminData()}
                disabled={loading || prewarming || recovering}
              >
                <RefreshCw className={cn('h-4 w-4', loading ? 'animate-spin' : '')} />
                {loading ? t('admin.refreshing') : t('admin.refresh')}
              </button>
            </>
          )}
        />

        {error ? <ApiErrorAlert error={error} actionLabel={t('common.retry')} onAction={() => void loadAdminData()} /> : null}
        {prewarmError ? <ApiErrorAlert error={prewarmError} actionLabel={t('common.retry')} onAction={() => void handlePrewarmMarketCache()} /> : null}
        {recoveryError ? <ApiErrorAlert error={recoveryError} actionLabel={t('common.retry')} onAction={() => void handleRecoverMarketSources()} /> : null}

        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          <StatCard label={t('admin.totalUsers')} value={formatNumber(users.length, language)} hint={t('admin.totalUsersHint')} icon={<Users className="h-5 w-5" />} tone="primary" />
          <StatCard label={t('admin.aiUsageUnits')} value={formatNumber(totalUsageUnits, language)} hint={t('admin.aiUsageHint')} icon={<Gauge className="h-5 w-5" />} />
          <StatCard label={t('admin.auditEvents')} value={formatNumber(auditEvents.length, language)} hint={t('admin.auditEventsHint')} icon={<Activity className="h-5 w-5" />} />
          <StatCard label="Billing events" value={formatNumber(billingEvents.length, language)} hint="Local sandbox event ledger only" icon={<CreditCard className="h-5 w-5" />} tone="warning" />
        </div>

        {loading && !retentionFunnel ? (
          <div className="h-40 animate-pulse border-y border-subtle bg-hover/35" />
        ) : retentionFunnel ? (
          <RetentionFunnelPanelV97 language={language} summary={retentionFunnel} />
        ) : null}

        <Card title="Local functional status" subtitle="Local 8018 readiness, cost controls, and safety boundaries" className="rounded-lg">
          {loading && !localStatus ? (
            <div className="h-28 animate-pulse rounded-lg bg-hover/70" />
          ) : !localStatus ? (
            <EmptyState title="No local status" description="Refresh to load the local functional status snapshot." />
          ) : (
            <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
              <div className="rounded-lg border border-border/70 bg-hover/35 p-3">
                <div className="text-xs uppercase tracking-[0.16em] text-secondary-text">Service</div>
                <div className="mt-2 text-lg font-semibold text-foreground">{localStatus.service.port}</div>
                <div className="mt-1 text-xs text-secondary-text">{localStatus.service.host} / {localStatus.service.webui}</div>
              </div>
              <div className="rounded-lg border border-border/70 bg-hover/35 p-3">
                <div className="text-xs uppercase tracking-[0.16em] text-secondary-text">Market cache</div>
                <div className="mt-2 text-lg font-semibold text-foreground">{String(localStatus.market.cache.mode ?? '-')}</div>
                <div className="mt-1 text-xs text-secondary-text">
                  lanes {formatNumber(Number(localStatus.market.summary.laneCount ?? 0), language)}
                  {' / '}
                  degraded {formatNumber(Number(localStatus.market.summary.degradedSourceCount ?? 0), language)}
                </div>
              </div>
              <div className="rounded-lg border border-border/70 bg-hover/35 p-3">
                <div className="text-xs uppercase tracking-[0.16em] text-secondary-text">AI boundary</div>
                <div className="mt-2 flex flex-wrap gap-2 text-xs">
                  <span className="rounded-full border border-emerald-500/30 px-2 py-1 text-emerald-500">
                    {localStatus.safety.noAiStatus ? 'No AI status' : 'AI status changed'}
                  </span>
                  <span className="rounded-full border border-border/70 px-2 py-1 text-secondary-text">
                    {localStatus.ai.byokSupported ? 'BYOK supported' : 'BYOK unavailable'}
                  </span>
                  <span className="rounded-full border border-border/70 px-2 py-1 text-secondary-text">
                    {localStatus.ai.localModelEnabled ? 'Local model on' : 'Local model off'}
                  </span>
                </div>
              </div>
              <div className="rounded-lg border border-border/70 bg-hover/35 p-3">
                <div className="text-xs uppercase tracking-[0.16em] text-secondary-text">Safety</div>
                <div className="mt-2 flex flex-wrap gap-2 text-xs">
                  <span className="rounded-full border border-border/70 px-2 py-1 text-secondary-text">
                    {localStatus.ai.publicSearchEnabled ? 'Public search on' : 'Public search off'}
                  </span>
                  <span className="rounded-full border border-border/70 px-2 py-1 text-secondary-text">
                    {localStatus.safety.realPaymentEnabled ? 'Real payment on' : 'Real payment off'}
                  </span>
                  <span className="rounded-full border border-border/70 px-2 py-1 text-secondary-text">
                    {localStatus.safety.secretsRedacted ? 'Secrets redacted' : 'Secrets check needed'}
                  </span>
                </div>
              </div>
            </div>
          )}
        </Card>

        <Card title="Ops health" subtitle="Read-only local operations health; not production monitoring" className="rounded-lg">
          {loading && !opsHealth ? (
            <div className="h-28 animate-pulse rounded-lg bg-hover/70" />
          ) : !opsHealth ? (
            <EmptyState title="No ops health" description="Refresh to load the local operations health snapshot." />
          ) : (
            <div className="space-y-3">
              <div className="grid gap-3 md:grid-cols-[minmax(0,0.8fr)_minmax(0,1.2fr)]">
                <div className="rounded-lg border border-border/70 bg-hover/35 p-3">
                  <div className="text-xs uppercase tracking-[0.16em] text-secondary-text">Overall</div>
                  <div className={cn(
                    'mt-2 inline-flex items-center gap-2 rounded-full border px-3 py-1 text-sm font-semibold',
                    opsHealth.overallStatus === 'ok'
                      ? 'border-emerald-500/30 text-emerald-500'
                      : opsHealth.overallStatus === 'failed'
                        ? 'border-rose-500/30 text-rose-500'
                        : 'border-amber-500/30 text-amber-500',
                  )}>
                    <Server className="h-4 w-4" />
                    {String(opsHealth.overallStatus).toUpperCase()}
                  </div>
                  <div className="mt-2 text-xs leading-relaxed text-secondary-text">
                    {opsHealth.aiUsed ? 'AI used' : 'No AI used'}
                    {' / '}
                    {opsHealth.mode}
                  </div>
                </div>
                <div className="grid gap-2 sm:grid-cols-4">
                  <div className="rounded-lg border border-border/70 bg-hover/35 p-3">
                    <div className="text-xs text-secondary-text">Total</div>
                    <div className="mt-1 text-lg font-semibold text-foreground">{formatNumber(opsHealth.summary.total, language)}</div>
                  </div>
                  <div className="rounded-lg border border-border/70 bg-hover/35 p-3">
                    <div className="text-xs text-secondary-text">OK</div>
                    <div className="mt-1 text-lg font-semibold text-emerald-500">{formatNumber(opsHealth.summary.ok, language)}</div>
                  </div>
                  <div className="rounded-lg border border-border/70 bg-hover/35 p-3">
                    <div className="text-xs text-secondary-text">Degraded</div>
                    <div className="mt-1 text-lg font-semibold text-amber-500">{formatNumber(opsHealth.summary.degraded, language)}</div>
                  </div>
                  <div className="rounded-lg border border-border/70 bg-hover/35 p-3">
                    <div className="text-xs text-secondary-text">Critical</div>
                    <div className="mt-1 text-lg font-semibold text-rose-500">{formatNumber(opsHealth.summary.criticalDegraded, language)}</div>
                  </div>
                </div>
              </div>
              <div className="flex flex-wrap gap-1.5 text-xs text-secondary-text">
                {opsHealth.checks.map((check) => (
                  <span
                    key={check.id}
                    className={cn(
                      'rounded-full border px-2 py-1',
                      check.status === 'ok'
                        ? 'border-emerald-500/25 text-emerald-500'
                        : 'border-amber-500/25 text-amber-500',
                    )}
                    aria-label={check.title}
                  >
                    {check.category}
                  </span>
                ))}
              </div>
              {opsHealth.checks.some((check) => check.status !== 'ok') ? (
                <div className="grid gap-2 md:grid-cols-2">
                  {opsHealth.checks.filter((check) => check.status !== 'ok').slice(0, 4).map((check) => (
                    <div key={check.id} className="rounded-lg border border-border/70 bg-hover/35 p-3">
                      <div className="flex items-start justify-between gap-2">
                        <div className="min-w-0">
                          <div className="truncate text-sm font-semibold text-foreground">{check.title}</div>
                          <div className="mt-1 text-xs leading-relaxed text-secondary-text">{check.message}</div>
                        </div>
                        <span className="shrink-0 rounded-full border border-amber-500/25 px-2 py-1 text-[11px] text-amber-500">
                          {check.category}
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              ) : null}
            </div>
          )}
        </Card>

        <Card title="Production readiness" subtitle="Machine-checkable launch preflight; external approvals still block public launch" className="rounded-lg">
          {loading && !productionReadiness ? (
            <div className="h-32 animate-pulse rounded-lg bg-hover/70" />
          ) : !productionReadiness ? (
            <EmptyState title="No production readiness" description="Refresh to load production readiness preflight." />
          ) : (
            <div className="space-y-3">
              <div className="grid gap-3 md:grid-cols-[minmax(0,0.85fr)_minmax(0,1.15fr)]">
                <div className="rounded-lg border border-border/70 bg-hover/35 p-3">
                  <div className="text-xs uppercase tracking-[0.16em] text-secondary-text">Launch decision</div>
                  <div className={cn(
                    'mt-2 inline-flex items-center gap-2 rounded-full border px-3 py-1 text-sm font-semibold',
                    productionReadiness.productionReady
                      ? 'border-emerald-500/30 text-emerald-500'
                      : 'border-amber-500/30 text-amber-500',
                  )}>
                    <ShieldAlert className="h-4 w-4" />
                    {productionReadiness.launchDecision.toUpperCase()}
                  </div>
                  <div className="mt-2 text-xs leading-relaxed text-secondary-text">
                    {productionReadiness.analysisBoundary}
                    {' / '}
                    {productionReadiness.aiUsed ? 'AI used' : 'No AI used'}
                  </div>
                </div>
                <div className="grid gap-2 sm:grid-cols-4">
                  <div className="rounded-lg border border-border/70 bg-hover/35 p-3">
                    <div className="text-xs text-secondary-text">Total</div>
                    <div className="mt-1 text-lg font-semibold text-foreground">{formatNumber(productionReadiness.summary.total, language)}</div>
                  </div>
                  <div className="rounded-lg border border-border/70 bg-hover/35 p-3">
                    <div className="text-xs text-secondary-text">Passed</div>
                    <div className="mt-1 text-lg font-semibold text-emerald-500">{formatNumber(productionReadiness.summary.passed, language)}</div>
                  </div>
                  <div className="rounded-lg border border-border/70 bg-hover/35 p-3">
                    <div className="text-xs text-secondary-text">Blocked</div>
                    <div className="mt-1 text-lg font-semibold text-amber-500">{formatNumber(productionReadiness.summary.blocked, language)}</div>
                  </div>
                  <div className="rounded-lg border border-border/70 bg-hover/35 p-3">
                    <div className="text-xs text-secondary-text">Manual</div>
                    <div className="mt-1 text-lg font-semibold text-foreground">{formatNumber(productionReadiness.summary.manualActions, language)}</div>
                  </div>
                </div>
              </div>
              <div className="flex flex-wrap gap-1.5 text-xs text-secondary-text">
                {productionReadiness.checks.map((check) => (
                  <span
                    key={check.id}
                    className={cn(
                      'rounded-full border px-2 py-1',
                      check.status === 'passed'
                        ? 'border-emerald-500/25 text-emerald-500'
                        : 'border-amber-500/25 text-amber-500',
                    )}
                    aria-label={check.title}
                  >
                    {check.category}
                  </span>
                ))}
              </div>
              {productionReadiness.checks.some((check) => check.status === 'blocked') ? (
                <div className="grid gap-2 md:grid-cols-2">
                  {productionReadiness.checks.filter((check) => check.status === 'blocked').slice(0, 4).map((check) => (
                    <div key={check.id} className="rounded-lg border border-border/70 bg-hover/35 p-3">
                      <div className="flex items-start justify-between gap-2">
                        <div className="min-w-0">
                          <div className="truncate text-sm font-semibold text-foreground">{check.title}</div>
                          <div className="mt-1 text-xs leading-relaxed text-secondary-text">{check.message}</div>
                        </div>
                        <span className="shrink-0 rounded-full border border-amber-500/25 px-2 py-1 text-[11px] text-amber-500">
                          {check.category}
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              ) : null}
            </div>
          )}
        </Card>

        <Card
          title={t('admin.marketSourcesTitle')}
          subtitle={`${t('admin.marketSourcesSubtitle')} · ${marketSourceHealth?.cache?.mode ?? '-'}`}
          className="rounded-lg"
        >
          {loading && marketSourceRows.length === 0 ? (
            <div className="h-36 animate-pulse rounded-lg bg-hover/70" />
          ) : marketSourceRows.length === 0 ? (
            <EmptyState title={t('admin.noMarketSourcesTitle')} description={t('admin.noMarketSourcesDescription')} />
          ) : (
            <div className="space-y-3">
              {recoveryResult ? (
                <div className="rounded-lg border border-border/70 bg-hover/35 p-3">
                  <div className="flex flex-wrap items-center gap-2 text-xs text-secondary-text">
                    <span className="font-medium text-foreground">{t('admin.latestRecovery')}</span>
                    <span className="rounded-full border border-border/70 px-2 py-1">
                      {t('admin.recoveryReset', { count: formatNumber(recoveryResult.resetCount, language) })}
                    </span>
                    <span className="rounded-full border border-border/70 px-2 py-1">
                      {t('admin.prewarmWarmed', { count: formatNumber(recoveryResult.prewarm.warmed, language) })}
                    </span>
                    <span className="rounded-full border border-border/70 px-2 py-1">
                      {t('admin.prewarmDegraded', { count: formatNumber(recoveryResult.prewarm.degraded, language) })}
                    </span>
                    <span className="rounded-full border border-emerald-500/30 px-2 py-1 text-emerald-500">
                      {recoveryResult.aiUsed || recoveryResult.prewarm.aiUsed ? 'AI used' : t('admin.prewarmNoAiUsed')}
                    </span>
                  </div>
                  <div className="mt-2 text-xs text-secondary-text">{recoveryResult.resetSources.join(', ') || '-'}</div>
                </div>
              ) : null}
              {prewarmResult ? (
                <div className="rounded-lg border border-border/70 bg-hover/35 p-3">
                  <div className="flex flex-wrap items-center gap-2 text-xs text-secondary-text">
                    <span className="font-medium text-foreground">{t('admin.latestPrewarm')}</span>
                    <span className="rounded-full border border-border/70 px-2 py-1">
                      {t('admin.prewarmRequested', { count: formatNumber(prewarmResult.requested, language) })}
                    </span>
                    <span className="rounded-full border border-border/70 px-2 py-1">
                      {t('admin.prewarmWarmed', { count: formatNumber(prewarmResult.warmed, language) })}
                    </span>
                    <span className="rounded-full border border-border/70 px-2 py-1">
                      {t('admin.prewarmDegraded', { count: formatNumber(prewarmResult.degraded, language) })}
                    </span>
                    <span className="rounded-full border border-border/70 px-2 py-1">
                      {t('admin.prewarmElapsed', { ms: formatNumber(prewarmResult.elapsedMs, language) })}
                    </span>
                    <span className="rounded-full border border-emerald-500/30 px-2 py-1 text-emerald-500">
                      {prewarmResult.aiUsed ? 'AI used' : t('admin.prewarmNoAiUsed')}
                    </span>
                  </div>
                  <div className="mt-2 text-xs text-secondary-text">{prewarmResult.symbols.join(', ')}</div>
                </div>
              ) : null}
              <div className="flex flex-wrap items-center gap-2 text-xs text-secondary-text">
                <span className="rounded-full border border-border/70 px-2 py-1">{marketSourceHealth?.mode ?? '-'}</span>
                <span className="rounded-full border border-border/70 px-2 py-1">{marketSourceHealth?.cache?.mode ?? '-'}</span>
                <span className="rounded-full border border-border/70 px-2 py-1">{marketSourceHealth?.cache?.storage ?? '-'}</span>
              </div>
              <div className="overflow-x-auto">
                <table className="min-w-full divide-y divide-border/70 text-sm">
                  <thead className="text-left text-xs uppercase tracking-[0.16em] text-secondary-text">
                    <tr>
                      <th className="px-3 py-2 font-medium">{t('admin.table.market')}</th>
                      <th className="px-3 py-2 font-medium">{t('admin.table.routeLane')}</th>
                      <th className="px-3 py-2 font-medium">{t('admin.table.sourceKind')}</th>
                      <th className="px-3 py-2 font-medium">{t('admin.table.source')}</th>
                      <th className="px-3 py-2 text-right font-medium">{t('admin.table.priority')}</th>
                      <th className="px-3 py-2 font-medium">{t('admin.table.sourceStatus')}</th>
                      <th className="px-3 py-2 text-right font-medium">{t('admin.table.latency')}</th>
                      <th className="px-3 py-2 text-right font-medium">{t('admin.table.cooldown')}</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border/60">
                    {marketSourceRows.map(({ lane, source, kind }) => (
                      <tr key={`${lane.market}-${kind}-${source.source}`} className="hover:bg-hover/60">
                        <td className="whitespace-nowrap px-3 py-2 text-secondary-text">{lane.market}</td>
                        <td className="whitespace-nowrap px-3 py-2 font-medium text-foreground">
                          <Server className="mr-2 inline h-4 w-4 text-cyan" />
                          {lane.routeLane}
                        </td>
                        <td className="whitespace-nowrap px-3 py-2 text-secondary-text">{kind}</td>
                        <td className="whitespace-nowrap px-3 py-2 font-mono text-xs text-secondary-text">{source.source}</td>
                        <td className="px-3 py-2 text-right text-secondary-text">{formatNumber(source.priorityRank, language)}</td>
                        <td className="whitespace-nowrap px-3 py-2 text-secondary-text">{source.status}</td>
                        <td className="px-3 py-2 text-right text-secondary-text">{formatLatency(source.lastLatencyMs, language)}</td>
                        <td className="px-3 py-2 text-right text-secondary-text">{formatNumber(source.cooldownRemainingSec, language)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </Card>

        <section className="grid gap-5 xl:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)]">
          <Card title={t('admin.usersTitle')} subtitle={t('admin.usersSubtitle')} className="rounded-lg">
            {loading && users.length === 0 ? (
              <div className="h-36 animate-pulse rounded-lg bg-hover/70" />
            ) : users.length === 0 ? (
              <EmptyState title={t('admin.noUsersTitle')} description={t('admin.noUsersDescription')} />
            ) : (
              <div className="overflow-x-auto">
                <table className="min-w-full divide-y divide-border/70 text-sm">
                  <thead className="text-left text-xs uppercase tracking-[0.16em] text-secondary-text">
                    <tr>
                      <th className="px-3 py-2 font-medium">{t('admin.table.user')}</th>
                      <th className="px-3 py-2 font-medium">{t('admin.table.role')}</th>
                      <th className="px-3 py-2 font-medium">{t('admin.table.plan')}</th>
                      <th className="px-3 py-2 font-medium">{t('admin.table.status')}</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border/60">
                    {users.map((user) => (
                      <tr key={user.id} className="hover:bg-hover/60">
                        <td className="px-3 py-2">
                          <div className="font-medium text-foreground">{user.email}</div>
                          <div className="text-xs text-secondary-text">ID #{user.id}</div>
                        </td>
                        <td className="px-3 py-2 text-secondary-text">{user.role}</td>
                        <td className="px-3 py-2 text-secondary-text">{user.plan}</td>
                        <td className="px-3 py-2 text-secondary-text">{user.status}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Card>

          <Card title={t('admin.usageTitle')} subtitle={t('admin.usageSubtitle')} className="rounded-lg">
            {loading && usage.length === 0 ? (
              <div className="h-36 animate-pulse rounded-lg bg-hover/70" />
            ) : usage.length === 0 ? (
              <EmptyState title={t('admin.noUsageTitle')} description={t('admin.noUsageDescription')} />
            ) : (
              <div className="overflow-x-auto">
                <table className="min-w-full divide-y divide-border/70 text-sm">
                  <thead className="text-left text-xs uppercase tracking-[0.16em] text-secondary-text">
                    <tr>
                      <th className="px-3 py-2 font-medium">{t('admin.table.user')}</th>
                      <th className="px-3 py-2 font-medium">{t('admin.table.quotaBucket')}</th>
                      <th className="px-3 py-2 text-right font-medium">{t('admin.table.used')}</th>
                      <th className="px-3 py-2 text-right font-medium">{t('admin.table.limit')}</th>
                      <th className="px-3 py-2 text-right font-medium">{t('admin.table.remaining')}</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border/60">
                    {usage.map((row) => (
                      <tr key={`${row.userId}-${row.quotaBucket}`} className="hover:bg-hover/60">
                        <td className="px-3 py-2 text-secondary-text">{row.email} / {row.plan}</td>
                        <td className="px-3 py-2 font-medium text-foreground">
                          <ShieldCheck className="mr-2 inline h-4 w-4 text-cyan" />
                          {getBucketLabel(row.quotaBucket, t)}
                        </td>
                        <td className="px-3 py-2 text-right text-secondary-text">{formatNumber(row.used, language)}</td>
                        <td className="px-3 py-2 text-right text-secondary-text">{formatLimit(row.weeklyLimit, language, t)}</td>
                        <td className="px-3 py-2 text-right text-secondary-text">{formatLimit(row.remaining, language, t)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Card>
        </section>

        <Card title={t('admin.auditTitle')} subtitle={t('admin.auditSubtitle')} className="rounded-lg">
          {loading && auditEvents.length === 0 ? (
            <div className="h-32 animate-pulse rounded-lg bg-hover/70" />
          ) : auditEvents.length === 0 ? (
            <EmptyState title={t('admin.noAuditTitle')} description={t('admin.noAuditDescription')} />
          ) : (
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-border/70 text-sm">
                <thead className="text-left text-xs uppercase tracking-[0.16em] text-secondary-text">
                  <tr>
                    <th className="px-3 py-2 font-medium">{t('admin.table.time')}</th>
                    <th className="px-3 py-2 font-medium">{t('admin.table.action')}</th>
                    <th className="px-3 py-2 font-medium">{t('admin.table.userId')}</th>
                    <th className="px-3 py-2 font-medium">{t('admin.table.metadata')}</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border/60">
                  {auditEvents.map((event, index) => (
                    <tr key={event.id ?? `${event.action}-${index}`} className="hover:bg-hover/60">
                      <td className="whitespace-nowrap px-3 py-2 text-secondary-text">{formatDateTime(event.createdAt, language)}</td>
                      <td className="whitespace-nowrap px-3 py-2 font-medium text-foreground">{event.action}</td>
                      <td className="whitespace-nowrap px-3 py-2 text-secondary-text">{event.userId ?? '-'}</td>
                      <td className="min-w-72 px-3 py-2 text-xs text-secondary-text">{auditMetadataDisplay(event.metadata)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>

        <Card title="Sandbox billing events" subtitle="Local mock payment audit; not real payment processing" className="rounded-lg">
          {loading && billingEvents.length === 0 ? (
            <div className="h-32 animate-pulse rounded-lg bg-hover/70" />
          ) : billingEvents.length === 0 ? (
            <EmptyState title="No billing events" description="No local sandbox billing events have been recorded." />
          ) : (
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-border/70 text-sm">
                <thead className="text-left text-xs uppercase tracking-[0.16em] text-secondary-text">
                  <tr>
                    <th className="px-3 py-2 font-medium">Time</th>
                    <th className="px-3 py-2 font-medium">User</th>
                    <th className="px-3 py-2 font-medium">Event</th>
                    <th className="px-3 py-2 font-medium">Provider event</th>
                    <th className="px-3 py-2 font-medium">Plan</th>
                    <th className="px-3 py-2 font-medium">Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border/60">
                  {billingEvents.map((event, index) => (
                    <tr key={event.id ?? `${event.providerEventId}-${index}`} className="hover:bg-hover/60">
                      <td className="whitespace-nowrap px-3 py-2 text-secondary-text">{formatDateTime(event.createdAt, language)}</td>
                      <td className="px-3 py-2 text-secondary-text">{event.email ?? event.userId ?? '-'}</td>
                      <td className="whitespace-nowrap px-3 py-2 font-medium text-foreground">{event.eventType}</td>
                      <td className="min-w-64 break-all px-3 py-2 font-mono text-xs text-secondary-text">{event.providerEventId}</td>
                      <td className="whitespace-nowrap px-3 py-2 text-secondary-text">{event.plan ?? '-'}</td>
                      <td className="whitespace-nowrap px-3 py-2 text-secondary-text">{event.processingStatus ?? '-'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>
      </div>
    </AppPage>
  );
};

export default AdminPage;
