import type React from 'react';
import {
  ArrowRight,
  CircleCheckBig,
  Clock3,
  Database,
  Gauge,
  Sparkles,
  TriangleAlert,
} from 'lucide-react';
import type {
  PlatformWatchlistDailyDigestItem,
  PlatformWatchlistRadarResponse,
  PlatformWatchlistResearchCondition,
} from '../../api/platform';

type Props = {
  language: string;
  radar: PlatformWatchlistRadarResponse;
  trialRemaining: number;
  trialLimit: number;
  onSelectSymbol: (stockCode: string) => void;
};

const percentText = (value: number | null | undefined): string => {
  if (typeof value !== 'number' || !Number.isFinite(value)) return '-';
  return `${value > 0 ? '+' : ''}${value.toLocaleString(undefined, { maximumFractionDigits: 2 })}%`;
};

const confidenceText = (value: string, en: boolean): string => {
  if (value === 'high') return en ? 'High' : '高';
  if (value === 'medium') return en ? 'Medium' : '中';
  return en ? 'Low' : '低';
};

const conditionText = (condition: PlatformWatchlistResearchCondition | undefined, en: boolean): string => {
  if (!condition) return '-';
  const value = typeof condition.value === 'number'
    ? condition.value.toLocaleString(undefined, { maximumFractionDigits: 4 })
    : '';
  const labels: Record<string, [string, string]> = {
    refresh_data: ['先刷新并确认数据新鲜度', 'Refresh and confirm data freshness'],
    fresh_data_restored: ['数据恢复后重新判断', 'Reassess after fresh data returns'],
    reclaim_ma20: [`重新站上 MA20 ${value}`, `Reclaim MA20 ${value}`],
    hold_above_ma20: [`继续守住 MA20 ${value}`, `Keep holding above MA20 ${value}`],
    lose_ma20: [`跌回 MA20 ${value} 下方`, `Move back below MA20 ${value}`],
    move_below_ma5: [`跌到 MA5 ${value} 下方`, `Move below MA5 ${value}`],
  };
  const pair = labels[condition.type];
  return pair ? pair[en ? 1 : 0] : condition.type;
};

const stateSummary = (state: string, en: boolean): string => {
  if (state === 'strong_confirmation') {
    return en ? 'Trend, volume and data quality align for continued review.' : '趋势、量能和数据质量形成一致确认。';
  }
  if (state === 'risk_review') {
    return en ? 'Review trend damage or data quality before interpreting the move.' : '先复核趋势走弱或数据质量，再解读波动。';
  }
  return en ? 'Wait for price, volume or moving-average conditions to confirm.' : '等待价格、量能或均线条件进一步确认。';
};

type GroupProps = {
  state: string;
  title: string;
  description: string;
  items: PlatformWatchlistDailyDigestItem[];
  radar: PlatformWatchlistRadarResponse;
  en: boolean;
  onSelectSymbol: (stockCode: string) => void;
};

const ResearchGroup: React.FC<GroupProps> = ({
  state,
  title,
  description,
  items,
  radar,
  en,
  onSelectSymbol,
}) => {
  const Icon = state === 'strong_confirmation'
    ? CircleCheckBig
    : state === 'risk_review'
      ? TriangleAlert
      : Clock3;
  const iconClass = state === 'strong_confirmation'
    ? 'text-success'
    : state === 'risk_review'
      ? 'text-warning'
      : 'text-primary';

  return (
    <section
      data-testid={`daily-research-group-${state}`}
      className="min-w-0 border-t border-subtle pt-4 lg:border-l lg:border-t-0 lg:pl-4 lg:pt-0 first:lg:border-l-0 first:lg:pl-0"
    >
      <div className="flex items-start gap-2">
        <Icon className={`mt-0.5 h-4 w-4 shrink-0 ${iconClass}`} aria-hidden="true" />
        <div className="min-w-0">
          <h4 className="text-sm font-semibold text-foreground">{title}</h4>
          <p className="mt-1 text-xs leading-relaxed text-secondary-text">{description}</p>
        </div>
      </div>

      <div className="mt-3 divide-y divide-subtle border-y border-subtle">
        {items.length > 0 ? items.map((item) => {
          const detail = radar.items.find((row) => row.stockCode === item.stockCode);
          return (
            <button
              key={item.stockCode}
              type="button"
              onClick={() => onSelectSymbol(item.stockCode)}
              className="grid min-h-24 w-full min-w-0 grid-cols-[minmax(0,1fr)_auto] gap-3 py-3 text-left hover:bg-primary/5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/50"
            >
              <span className="min-w-0">
                <span className="flex min-w-0 items-baseline gap-2">
                  <strong className="truncate text-sm text-foreground">{item.stockCode}</strong>
                  <span className="truncate text-xs text-secondary-text">{item.stockName || item.market.toUpperCase()}</span>
                </span>
                <span className="mt-1 block text-xs leading-relaxed text-secondary-text">
                  {stateSummary(state, en)}
                </span>
                <span className="mt-2 block text-[11px] text-secondary-text">
                  {en ? 'Next: ' : '下一步：'}{conditionText(detail?.researchBrief.nextWatch, en)}
                </span>
                <span className="mt-1 block text-[11px] text-secondary-text">
                  {en ? 'Invalidation: ' : '失效条件：'}{conditionText(detail?.researchBrief.invalidation, en)}
                </span>
              </span>
              <span className="shrink-0 text-right">
                <span className={item.changePercent !== null && item.changePercent !== undefined && item.changePercent < 0 ? 'block text-sm font-semibold text-danger' : 'block text-sm font-semibold text-success'}>
                  {percentText(item.changePercent)}
                </span>
                <span className="mt-1 block text-[11px] text-secondary-text">
                  {en ? 'Score' : '优先级'} {item.priorityScore}
                </span>
                <span className="mt-1 block text-[11px] text-secondary-text">
                  {en
                    ? `Data confidence: ${confidenceText(item.dataConfidence, en)}`
                    : `数据可信度：${confidenceText(item.dataConfidence, en)}`}
                </span>
                <ArrowRight className="ml-auto mt-2 h-4 w-4 text-primary" aria-hidden="true" />
              </span>
            </button>
          );
        }) : (
          <div className="py-4 text-xs text-secondary-text">
            {en ? 'No symbols in this group today.' : '今日暂无标的进入该分组。'}
          </div>
        )}
      </div>
    </section>
  );
};

export const DailyResearchCockpitV103: React.FC<Props> = ({
  language,
  radar,
  trialRemaining,
  trialLimit,
  onSelectSymbol,
}) => {
  const en = language === 'en';
  const digest = radar.dailyDigest;
  const groups = [
    {
      state: 'strong_confirmation',
      title: en ? 'Strong confirmation' : '重点确认',
      description: en ? 'Usable data with aligned trend and volume evidence.' : '数据可用，趋势与量能证据相互确认。',
      items: digest.strongConfirmation,
    },
    {
      state: 'risk_review',
      title: en ? 'Risk review' : '风险复核',
      description: en ? 'Trend damage, sharp moves or low-confidence data need review.' : '趋势走弱、显著波动或低可信数据需要复核。',
      items: digest.riskReview,
    },
    {
      state: 'wait_for_confirmation',
      title: en ? 'Wait for confirmation' : '等待确认',
      description: en ? 'The current evidence is not yet strong enough for a firm read.' : '当前证据尚不足以形成明确判断。',
      items: digest.waitForConfirmation,
    },
  ];

  return (
    <section
      data-testid="daily-research-cockpit-v103"
      className="border-y border-primary/30 py-5"
    >
      <div className="flex min-w-0 flex-col gap-4 xl:flex-row xl:items-end xl:justify-between">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <Gauge className="h-5 w-5 text-primary" aria-hidden="true" />
            <h3 className="text-base font-semibold text-foreground">
              {en ? 'Daily research cockpit' : '今日研究驾驶舱'}
            </h3>
            <span className="rounded-md border border-primary/40 px-2 py-1 text-[11px] text-primary">
              {en ? 'No AI used' : '未用 AI'}
            </span>
          </div>
          <p className="mt-1 max-w-3xl text-xs leading-relaxed text-secondary-text">
            {en
              ? 'Scan what deserves confirmation, what needs risk review, and what should wait. Rankings are deterministic and based on the current watchlist snapshot.'
              : '先看哪些标的值得确认、哪些需要风险复核、哪些应继续等待。排序来自当前自选快照的确定性规则。'}
          </p>
        </div>
        <div className="flex min-w-0 flex-wrap items-center gap-x-3 gap-y-2 text-xs text-secondary-text">
          <Database className="h-4 w-4 text-primary" aria-hidden="true" />
          <span>{en ? `Fresh ${digest.dataHealth.fresh}` : `新鲜 ${digest.dataHealth.fresh}`}</span>
          <span>{en ? `Cached ${digest.dataHealth.cached}` : `缓存 ${digest.dataHealth.cached}`}</span>
          <span>{en ? `Stale ${digest.dataHealth.stale}` : `过期 ${digest.dataHealth.stale}`}</span>
          <span>{en ? `Unavailable ${digest.dataHealth.unavailable}` : `不可用 ${digest.dataHealth.unavailable}`}</span>
        </div>
      </div>

      <div className="mt-5 grid min-w-0 gap-4 lg:grid-cols-3">
        {groups.map((group) => (
          <ResearchGroup
            key={group.state}
            {...group}
            radar={radar}
            en={en}
            onSelectSymbol={onSelectSymbol}
          />
        ))}
      </div>

      <div className="mt-5 flex min-w-0 flex-col gap-2 border-t border-subtle pt-4 text-xs text-secondary-text sm:flex-row sm:items-center sm:justify-between">
        <span className="inline-flex min-w-0 items-center gap-2">
          <Sparkles className="h-4 w-4 shrink-0 text-primary" aria-hidden="true" />
          <span>
            {en
              ? `Platform API trial ${trialRemaining}/${trialLimit} remaining`
              : `平台 API 试用剩余 ${trialRemaining}/${trialLimit}`}
          </span>
        </span>
        <span>
          {en
            ? 'Opening a symbol does not consume quota automatically; choose real-time enhancement on the stock page.'
            : '打开标的不会自动消耗额度；进入个股页后可自行选择实时增强。'}
        </span>
      </div>
      <p className="mt-3 text-[11px] text-secondary-text">
        {en ? 'Information analysis only; not investment advice.' : '仅作信息分析，不构成投资建议。'}
      </p>
    </section>
  );
};
