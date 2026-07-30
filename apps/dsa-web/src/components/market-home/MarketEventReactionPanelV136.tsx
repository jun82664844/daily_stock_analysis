import { useCallback, useEffect, useState } from 'react';
import { BarChart3, Clock3, Database, RefreshCw, Search } from 'lucide-react';
import {
  marketWorkspaceApi,
  type MarketEventReactionWindow,
  type PublicMarketEventReaction,
  type PublicMarketEventReactionResponse,
} from '../../api/marketWorkspace';
import { getParsedApiError } from '../../api/error';

type Props = {
  language: 'zh' | 'en';
  onOpenSymbol: (symbol: string) => void;
};

type WindowDays = 1 | 3 | 5 | 20;

const WINDOWS: WindowDays[] = [1, 3, 5, 20];

const copy = {
  zh: {
    eyebrow: '公开历史行情 · 未使用 AI',
    boundaryEyebrow: '数据边界校验',
    title: '事件后市场观察',
    subtitle: '按计划事件日期，对照后续 1、3、5、20 个交易日的证券、基准指数和成交量数据。',
    windowLabel: '观察时间窗口',
    window: (days: number) => `${days}个交易日`,
    observedChange: '证券同期变化',
    benchmarkChange: '基准同期变化',
    relativeChange: '相对基准变化',
    volumeRatio: '同期量比',
    baseline: '基准交易日',
    observed: '观察交易日',
    eventDate: '事件日期',
    marketBenchmark: '市场基准',
    markets: { cn: 'A股', hk: '港股', us: '美股' },
    statuses: { fresh: '新鲜', cached: '缓存', stale: '陈旧缓存', unavailable: '暂无数据' },
    scheduleTypes: {
      earnings_release: '财报披露',
      ex_dividend: '除息日',
      macro_policy: '宏观计划事件',
    },
    pending: '等待足够的交易日数据',
    insufficient: '历史行情不足，暂不能计算',
    unavailable: '事件窗口行情暂时不可用，其他市场资讯仍可继续浏览。',
    partialUnavailable: '部分事件行情源暂时不可用，以下成功取得的数据仍可查看。',
    boundaryViolation: '响应未满足免 AI 数据边界，暂不展示该批数据。',
    rateLimited: (seconds: number) => `请求过于频繁，请等待 ${seconds} 秒后重新加载。`,
    empty: '暂未取得可计算的历史计划事件',
    retry: '重新加载',
    query: '查询',
    queryLabel: (symbol: string) => `查询 ${symbol}`,
    cache: (minutes: number) => `缓存约 ${minutes} 分钟`,
    source: '来源',
    sourceProvider: 'Yahoo 公开图表',
    noCausality: '同期表现不代表事件导致行情变化。仅提供资讯和数据，不构成投资建议。',
  },
  en: {
    eyebrow: 'Public historical prices · No AI used',
    boundaryEyebrow: 'Data-boundary check',
    title: 'Post-event market observations',
    subtitle: 'Security, benchmark-index and volume data 1, 3, 5 and 20 trading sessions after source-scheduled events.',
    windowLabel: 'Observation window',
    window: (days: number) => `${days} trading ${days === 1 ? 'day' : 'days'}`,
    observedChange: 'Security change',
    benchmarkChange: 'Benchmark change',
    relativeChange: 'Relative change',
    volumeRatio: 'Volume ratio',
    baseline: 'Baseline session',
    observed: 'Observed session',
    eventDate: 'Event date',
    marketBenchmark: 'Market benchmark',
    markets: { cn: 'China', hk: 'Hong Kong', us: 'US' },
    statuses: { fresh: 'Fresh', cached: 'Cached', stale: 'Stale cache', unavailable: 'Unavailable' },
    scheduleTypes: {
      earnings_release: 'Earnings release',
      ex_dividend: 'Ex-dividend date',
      macro_policy: 'Scheduled macro event',
    },
    pending: 'Awaiting enough trading sessions',
    insufficient: 'Insufficient historical prices for this window',
    unavailable: 'Event-window prices are temporarily unavailable. Other market information remains available.',
    partialUnavailable: 'Some event-price sources are unavailable. Successfully loaded observations remain visible below.',
    boundaryViolation: 'This response did not satisfy the no-AI data boundary, so the batch is not displayed.',
    rateLimited: (seconds: number) => `Too many requests. Reload after ${seconds} seconds.`,
    empty: 'No eligible historical scheduled events are available yet',
    retry: 'Reload',
    query: 'Query',
    queryLabel: (symbol: string) => `Query ${symbol}`,
    cache: (minutes: number) => `Cached for about ${minutes} min`,
    source: 'Source',
    sourceProvider: 'Yahoo public chart',
    noCausality: 'Same-period performance does not establish that the event caused a market move. Information and data only. Not investment advice.',
  },
} as const;

function signedPercent(value: number | null | undefined, language: 'zh' | 'en'): string {
  if (value == null || !Number.isFinite(value)) return language === 'zh' ? '暂无' : 'Unavailable';
  return `${value > 0 ? '+' : ''}${value.toLocaleString(language === 'zh' ? 'zh-CN' : 'en-US', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}%`;
}

function ratio(value: number | null | undefined, language: 'zh' | 'en'): string {
  if (value == null || !Number.isFinite(value)) return language === 'zh' ? '暂无' : 'Unavailable';
  const formatted = value.toLocaleString(language === 'zh' ? 'zh-CN' : 'en-US', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
  return language === 'zh' ? `${formatted} 倍` : `${formatted}x`;
}

function valueClass(value: number | null | undefined): string {
  if (value == null || !Number.isFinite(value) || value === 0) return 'text-slate-100';
  return value > 0 ? 'text-emerald-300' : 'text-rose-300';
}

function dateLabel(value: string | null | undefined, language: 'zh' | 'en'): string {
  if (!value) return language === 'zh' ? '暂无' : 'Unavailable';
  const parsed = new Date(`${value}T00:00:00Z`);
  if (!Number.isFinite(parsed.getTime())) return value;
  return new Intl.DateTimeFormat(language === 'zh' ? 'zh-CN' : 'en-US', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    timeZone: 'UTC',
  }).format(parsed);
}

function windowFor(
  windows: MarketEventReactionWindow[],
  days: WindowDays,
): MarketEventReactionWindow | undefined {
  return windows.find((item) => item.tradingDays === days);
}

function benchmarkLabel(
  item: PublicMarketEventReaction,
  language: 'zh' | 'en',
): string {
  const symbol = item.benchmarkSymbol ?? (
    item.subjectType === 'market_benchmark' ? item.historySymbol : null
  );
  const labels = {
    '000001.SS': { zh: '上证指数', en: 'SSE Composite' },
    '^HSI': { zh: '恒生指数', en: 'Hang Seng Index' },
    '^GSPC': { zh: '标普500指数', en: 'S&P 500 Index' },
  } as const;
  if (symbol && symbol in labels) {
    return labels[symbol as keyof typeof labels][language];
  }
  return item.benchmarkName || (language === 'zh' ? '暂无' : 'Unavailable');
}

export default function MarketEventReactionPanelV136({ language, onOpenSymbol }: Props) {
  const t = copy[language];
  const [windowDays, setWindowDays] = useState<WindowDays>(1);
  const [payload, setPayload] = useState<PublicMarketEventReactionResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [failed, setFailed] = useState(false);
  const [hidden, setHidden] = useState(false);
  const [retryAfterSeconds, setRetryAfterSeconds] = useState<number | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setFailed(false);
    setHidden(false);
    setRetryAfterSeconds(null);
    try {
      setPayload(await marketWorkspaceApi.getEventReactions());
    } catch (error) {
      const parsed = getParsedApiError(error);
      setPayload(null);
      setHidden(parsed.status === 404);
      setFailed(parsed.status !== 404);
      setRetryAfterSeconds(parsed.status === 429 ? parsed.retryAfterSeconds ?? null : null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  if (hidden) return null;

  const sourceUnavailable = Boolean(
    payload?.warnings.some((warning) => (
      warning === 'event_reaction_events_unavailable'
      || warning === 'event_reaction_source_unavailable'
    )),
  );
  const partialUnavailable = Boolean(sourceUnavailable && payload?.items.length);
  const boundaryViolation = Boolean(
    payload && (payload.aiUsed || !payload.informationalOnly)
  );

  return (
    <section
      data-testid="market-event-reactions-v136"
      className="mt-5 border-y border-white/10 py-5"
      aria-label={t.title}
    >
      <div className="flex flex-col gap-4 px-1 sm:px-2">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
          <div className="min-w-0">
            <p className="text-xs font-semibold text-cyan-400">
              {boundaryViolation ? t.boundaryEyebrow : t.eyebrow}
            </p>
            <h3 className="mt-1 flex items-center gap-2 text-lg font-semibold text-white">
              <BarChart3 className="h-5 w-5 text-cyan-400" aria-hidden="true" />
              {t.title}
            </h3>
            <p className="mt-1 max-w-4xl text-sm leading-6 text-slate-400">{t.subtitle}</p>
          </div>
          <div className="flex flex-wrap gap-2" aria-label={t.windowLabel}>
            {WINDOWS.map((days) => (
              <button
                key={days}
                type="button"
                aria-pressed={windowDays === days}
                aria-label={t.window(days)}
                onClick={() => setWindowDays(days)}
                className={`min-h-9 rounded-lg border px-3 text-sm transition-colors ${
                  windowDays === days
                    ? 'border-cyan-400/60 bg-cyan-400/10 text-cyan-200'
                    : 'border-white/10 text-slate-300 hover:border-white/25 hover:text-white'
                }`}
              >
                {language === 'zh' ? `${days}日` : `${days}D`}
              </button>
            ))}
          </div>
        </div>

        {loading ? (
          <div className="flex min-h-28 items-center justify-center gap-2 text-sm text-slate-400">
            <RefreshCw className="h-4 w-4 animate-spin" aria-hidden="true" />
            {language === 'zh' ? '正在读取公开历史行情' : 'Loading public historical prices'}
          </div>
        ) : failed ? (
          <div className="flex min-h-28 flex-col items-center justify-center gap-3 border-y border-white/10 py-6 text-center">
            <p className="text-sm text-slate-400">
              {retryAfterSeconds ? t.rateLimited(retryAfterSeconds) : t.unavailable}
            </p>
            <button
              type="button"
              onClick={() => void load()}
              className="inline-flex min-h-9 items-center gap-2 rounded-lg border border-white/15 px-3 text-sm text-slate-200 hover:border-cyan-400/40"
            >
              <RefreshCw className="h-4 w-4" aria-hidden="true" />
              {t.retry}
            </button>
          </div>
        ) : boundaryViolation ? (
          <div
            role="alert"
            className="border-y border-rose-400/25 bg-rose-400/5 px-4 py-6 text-center text-sm text-rose-200"
          >
            {t.boundaryViolation}
          </div>
        ) : sourceUnavailable && !payload?.items.length ? (
          <div className="flex min-h-28 flex-col items-center justify-center gap-3 border-y border-white/10 py-6 text-center">
            <p className="text-sm text-slate-400">{t.unavailable}</p>
            <button
              type="button"
              onClick={() => void load()}
              className="inline-flex min-h-9 items-center gap-2 rounded-lg border border-white/15 px-3 text-sm text-slate-200 hover:border-cyan-400/40"
            >
              <RefreshCw className="h-4 w-4" aria-hidden="true" />
              {t.retry}
            </button>
          </div>
        ) : !payload || payload.items.length === 0 ? (
          <div className="border-y border-white/10 py-8 text-center text-sm text-slate-400">{t.empty}</div>
        ) : (
          <div>
            {partialUnavailable ? (
              <div
                role="status"
                className="mb-3 border-y border-amber-300/20 bg-amber-300/5 px-4 py-3 text-sm text-amber-100"
              >
                {t.partialUnavailable}
              </div>
            ) : null}
            <div className="divide-y divide-white/10 border-y border-white/10">
              {payload.items.map((item) => {
              const observation = windowFor(item.windows, windowDays);
              const schedule = item.scheduleType ? t.scheduleTypes[item.scheduleType] : item.title;
              return (
                <article
                  key={item.eventId}
                  className="grid gap-4 py-4 xl:grid-cols-[minmax(220px,1.1fr)_minmax(420px,2fr)_auto]"
                >
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2 text-xs text-slate-500">
                      <span className="font-semibold text-cyan-300">{t.markets[item.market]}</span>
                      <span>{schedule}</span>
                      <span>{t.statuses[item.sourceState.status]}</span>
                    </div>
                    <h4 className="mt-1 truncate text-base font-semibold text-slate-100">
                      {item.name} <span className="font-normal text-slate-400">{item.symbol}</span>
                    </h4>
                    {item.title && item.title !== item.name ? (
                      <p className="mt-1 line-clamp-2 text-xs leading-5 text-slate-400">
                        {item.title}
                      </p>
                    ) : null}
                    <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-slate-500">
                      <span>{t.eventDate} {dateLabel(item.eventTime.slice(0, 10), language)}</span>
                      <span>{t.baseline} {dateLabel(item.baselineDate, language)}</span>
                      <span>{t.observed} {dateLabel(observation?.observedDate, language)}</span>
                      <span>{t.marketBenchmark} {benchmarkLabel(item, language)}</span>
                    </div>
                  </div>

                  {observation?.status === 'available' ? (
                    <dl className="grid grid-cols-2 gap-px overflow-hidden bg-white/10 sm:grid-cols-4">
                      <div className="bg-[#080e18] px-3 py-3">
                        <dt className="text-xs text-slate-500">{t.observedChange}</dt>
                        <dd className={`mt-1 text-base font-semibold ${valueClass(observation.symbolReturnPercent)}`}>
                          {signedPercent(observation.symbolReturnPercent, language)}
                        </dd>
                      </div>
                      <div className="bg-[#080e18] px-3 py-3">
                        <dt className="text-xs text-slate-500">{t.benchmarkChange}</dt>
                        <dd className={`mt-1 text-base font-semibold ${valueClass(observation.benchmarkReturnPercent)}`}>
                          {signedPercent(observation.benchmarkReturnPercent, language)}
                        </dd>
                      </div>
                      <div className="bg-[#080e18] px-3 py-3">
                        <dt className="text-xs text-slate-500">{t.relativeChange}</dt>
                        <dd className={`mt-1 text-base font-semibold ${valueClass(observation.relativeReturnPercent)}`}>
                          {signedPercent(observation.relativeReturnPercent, language)}
                        </dd>
                      </div>
                      <div className="bg-[#080e18] px-3 py-3">
                        <dt className="text-xs text-slate-500">{t.volumeRatio}</dt>
                        <dd className="mt-1 text-base font-semibold text-slate-100">
                          {ratio(observation.volumeRatio, language)}
                        </dd>
                      </div>
                    </dl>
                  ) : (
                    <div className="flex min-h-20 items-center border-y border-white/10 px-4 text-sm text-slate-400">
                      <Clock3 className="mr-2 h-4 w-4 shrink-0 text-amber-300" aria-hidden="true" />
                      {observation?.status === 'pending' ? t.pending : t.insufficient}
                    </div>
                  )}

                  {item.subjectType === 'security' ? (
                    <button
                      type="button"
                      onClick={() => onOpenSymbol(item.symbol)}
                      aria-label={t.queryLabel(item.symbol)}
                      className="inline-flex min-h-10 items-center justify-center gap-2 self-center rounded-lg border border-cyan-400/30 px-3 text-sm text-cyan-300 hover:bg-cyan-400/10"
                    >
                      <Search className="h-4 w-4" aria-hidden="true" />
                      {t.query}
                    </button>
                  ) : <span />}
                </article>
              );
              })}
            </div>
          </div>
        )}

        <div className="flex flex-col gap-1 text-xs leading-5 text-slate-500 sm:flex-row sm:items-center sm:justify-between">
          <span className="inline-flex items-center gap-2">
            <Database className="h-4 w-4" aria-hidden="true" />
            {t.source}: {t.sourceProvider} · {t.cache(Math.max(1, Math.round((payload?.cache.ttlSeconds ?? 900) / 60)))}
          </span>
          <span>{t.noCausality}</span>
        </div>
      </div>
    </section>
  );
}
