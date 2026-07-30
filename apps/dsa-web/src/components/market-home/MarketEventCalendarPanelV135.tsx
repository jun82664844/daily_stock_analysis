import { useEffect, useMemo, useState } from 'react';
import {
  BellRing,
  CalendarDays,
  CheckCheck,
  Clock3,
  Search,
  Sparkles,
} from 'lucide-react';
import type { MarketCode, PublicMarketEvent } from '../../api/marketWorkspace';
import type { FollowedMarketEventV133 } from './marketEventFollowUpV133';
import {
  acknowledgeCalendarEntries,
  adoptGuestCalendarAcknowledgements,
  buildMarketEventCalendarV134,
  loadCalendarAcknowledgements,
  unseenDueCalendarEntryIds,
  type MarketEventCalendarEntryV134,
} from './marketEventCalendarV134';

type Props = {
  language: 'zh' | 'en';
  events: PublicMarketEvent[];
  followedEvents: FollowedMarketEventV133[];
  watchlistSymbols: string[];
  scope: string;
  now?: Date;
  onOpenSymbol: (symbol: string) => void;
};

type CalendarView = 'today' | 'week' | 'mine' | 'due';

const DAY_MILLISECONDS = 24 * 60 * 60 * 1000;

const copy = {
  zh: {
    eyebrow: '公开数据 · 未使用 AI',
    title: '本周市场大事',
    subtitle: '整理 A股、港股、美股来源明确的财报、除息和宏观计划日期，并保留关注事件复盘节点。',
    dueCount: (count: number) => `待复盘 ${count}`,
    today: '今日事件',
    week: '本周大事',
    mine: '我的日历',
    due: '待复盘',
    viewLabel: '真实市场日历查看模式',
    acknowledge: '全部标为已查看',
    explicitSchedule: '计划日期',
    published: '发布时间',
    checkpoint: (days: number) => `${days}日复盘节点`,
    markets: { cn: 'A股', hk: '港股', us: '美股' },
    statuses: { fresh: '新鲜', cached: '缓存', stale: '陈旧缓存', unavailable: '暂无数据' },
    source: '来源',
    query: '查询',
    queryLabel: (symbol: string) => `查询 ${symbol}`,
    empty: {
      today: '今日暂无来源明确的计划事件',
      week: '本周暂无来源明确的计划事件',
      mine: '自选股和关注事件暂未匹配到日历条目',
      due: '当前没有待复盘节点',
    },
    scheduleTypes: {
      earnings_release: '财报披露',
      ex_dividend: '除息日',
      stock_split: '拆股事件',
      macro_policy: '美联储 FOMC 会议',
    },
    scheduleRule: '只有来源明确给出日期的条目才标记为计划事件。',
    noCausality: '事件与行情并列展示不代表因果关系。',
    disclaimer: '仅提供资讯和数据，不构成投资建议。',
    mineBadge: '与我相关',
  },
  en: {
    eyebrow: 'Public data · No AI used',
    title: 'This week in markets',
    subtitle: 'Source-explicit earnings, ex-dividend and macro dates across China, Hong Kong and US markets, plus local follow-up checkpoints.',
    dueCount: (count: number) => `${count} due`,
    today: 'Today',
    week: 'This week',
    mine: 'My calendar',
    due: 'Due reviews',
    viewLabel: 'Real market calendar view',
    acknowledge: 'Mark all reviewed',
    explicitSchedule: 'Scheduled date',
    published: 'Published time',
    checkpoint: (days: number) => `${days}-day follow-up`,
    markets: { cn: 'China', hk: 'Hong Kong', us: 'US' },
    statuses: { fresh: 'Fresh', cached: 'Cached', stale: 'Stale cache', unavailable: 'Unavailable' },
    source: 'Source',
    query: 'Query',
    queryLabel: (symbol: string) => `Query ${symbol}`,
    empty: {
      today: 'No source-explicit scheduled events are available today',
      week: 'No source-explicit scheduled events are available this week',
      mine: 'No calendar entries currently match your watchlist or followed events',
      due: 'No follow-up checkpoints are due',
    },
    scheduleTypes: {
      earnings_release: 'earnings release',
      ex_dividend: 'ex-dividend date',
      stock_split: 'stock split',
      macro_policy: 'Federal Reserve FOMC meeting',
    },
    scheduleRule: 'An item is marked as scheduled only when its source explicitly provides a date.',
    noCausality: 'Events and market prices shown together do not establish causality.',
    disclaimer: 'Information and data only. Not investment advice.',
    mineBadge: 'Relevant to me',
  },
} as const;

function utcDay(value: Date | string): number {
  const parsed = value instanceof Date ? value : new Date(value);
  return Date.UTC(
    parsed.getUTCFullYear(),
    parsed.getUTCMonth(),
    parsed.getUTCDate(),
  );
}

function formatDate(value: string, language: 'zh' | 'en'): string {
  const parsed = new Date(value);
  if (!Number.isFinite(parsed.getTime())) return value;
  return new Intl.DateTimeFormat(language === 'zh' ? 'zh-CN' : 'en-US', {
    month: '2-digit',
    day: '2-digit',
    year: 'numeric',
    timeZone: 'UTC',
  }).format(parsed);
}

function basisLabel(entry: MarketEventCalendarEntryV134, language: 'zh' | 'en'): string {
  const t = copy[language];
  if (entry.dateBasis === 'follow_up_checkpoint') {
    return t.checkpoint(entry.checkpointDays ?? 1);
  }
  return entry.dateBasis === 'explicit_schedule' ? t.explicitSchedule : t.published;
}

function localizedTitle(entry: MarketEventCalendarEntryV134, language: 'zh' | 'en'): string {
  if (!entry.scheduleType) return entry.title;
  const label = copy[language].scheduleTypes[entry.scheduleType];
  if (entry.scheduleType === 'macro_policy') return label;
  return `${entry.name || entry.symbol || entry.title} ${label}`;
}

export default function MarketEventCalendarPanelV135({
  language,
  events,
  followedEvents,
  watchlistSymbols,
  scope,
  now = new Date(),
  onOpenSymbol,
}: Props) {
  const t = copy[language];
  const [view, setView] = useState<CalendarView>('week');
  const [acknowledgedEntryIds, setAcknowledgedEntryIds] = useState<string[]>(
    () => loadCalendarAcknowledgements(scope),
  );
  const entries = useMemo(
    () => buildMarketEventCalendarV134(events, followedEvents, watchlistSymbols, now),
    [events, followedEvents, now, watchlistSymbols],
  );
  const dueEntryIds = useMemo(
    () => unseenDueCalendarEntryIds(entries, acknowledgedEntryIds),
    [acknowledgedEntryIds, entries],
  );
  const dueEntryIdSet = useMemo(() => new Set(dueEntryIds), [dueEntryIds]);
  const today = utcDay(now);
  const visibleEntries = useMemo(() => {
    const filtered = entries.filter((entry) => {
      const scheduledDay = utcDay(entry.scheduledAt);
      if (view === 'today') return scheduledDay === today;
      if (view === 'week') {
        return scheduledDay >= today && scheduledDay <= today + 7 * DAY_MILLISECONDS;
      }
      if (view === 'mine') return entry.personalized;
      return dueEntryIdSet.has(entry.id);
    });
    const pinnedFollowUps = filtered
      .filter((entry) => entry.kind === 'follow_up')
      .slice(0, 4);
    const pinnedIds = new Set(pinnedFollowUps.map((entry) => entry.id));
    return [
      ...pinnedFollowUps,
      ...filtered.filter((entry) => !pinnedIds.has(entry.id)),
    ].slice(0, 14);
  }, [dueEntryIdSet, entries, today, view]);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      setAcknowledgedEntryIds(
        scope === 'guest'
          ? loadCalendarAcknowledgements('guest')
          : adoptGuestCalendarAcknowledgements(scope),
      );
    }, 0);
    return () => window.clearTimeout(timer);
  }, [scope]);

  const acknowledgeDue = () => {
    setAcknowledgedEntryIds(acknowledgeCalendarEntries(scope, dueEntryIds));
  };

  return (
    <section
      data-testid="market-event-calendar-v135"
      className="mt-5 border-y border-cyan-400/20 bg-cyan-400/[0.035] py-5"
    >
      <div className="flex flex-col gap-4 px-1 sm:px-2">
        <div className="flex flex-col gap-3 xl:flex-row xl:items-end xl:justify-between">
          <div className="min-w-0">
            <p className="text-xs font-semibold text-cyan-400">{t.eyebrow}</p>
            <h3 className="mt-1 flex flex-wrap items-center gap-2 text-lg font-semibold text-white">
              <CalendarDays className="h-5 w-5 text-cyan-400" aria-hidden="true" />
              {t.title}
              <span className="rounded-lg border border-amber-400/30 bg-amber-400/10 px-2 py-1 text-xs text-amber-200">
                {t.dueCount(dueEntryIds.length)}
              </span>
            </h3>
            <p className="mt-1 max-w-4xl text-sm leading-6 text-slate-400">{t.subtitle}</p>
          </div>
          <div className="flex flex-col gap-2 xl:items-end">
            <div className="flex flex-wrap gap-2" aria-label={t.viewLabel}>
              {([
                ['today', t.today],
                ['week', t.week],
                ['mine', t.mine],
                ['due', t.due],
              ] as const).map(([value, label]) => (
                <button
                  key={value}
                  type="button"
                  aria-pressed={view === value}
                  onClick={() => setView(value)}
                  className={`min-h-9 rounded-lg border px-3 text-sm transition-colors ${
                    view === value
                      ? 'border-cyan-400/60 bg-cyan-400/10 text-cyan-200'
                      : 'border-white/10 text-slate-300 hover:border-white/25 hover:text-white'
                  }`}
                >
                  {label}
                </button>
              ))}
            </div>
            {dueEntryIds.length > 0 ? (
              <button
                type="button"
                onClick={acknowledgeDue}
                className="inline-flex min-h-9 items-center gap-2 self-start rounded-lg border border-amber-400/30 px-3 text-sm text-amber-200 hover:bg-amber-400/10 xl:self-auto"
              >
                <CheckCheck className="h-4 w-4" aria-hidden="true" />
                {t.acknowledge}
              </button>
            ) : null}
          </div>
        </div>

        {visibleEntries.length === 0 ? (
          <div className="border-y border-white/10 py-8 text-center text-sm text-slate-400">
            {t.empty[view]}
          </div>
        ) : (
          <div className="divide-y divide-white/10 border-y border-white/10">
            {visibleEntries.map((entry) => (
              <article
                key={entry.id}
                className="grid min-w-0 gap-3 py-4 md:grid-cols-[160px_minmax(0,1fr)_auto] md:items-center"
              >
                <div className="flex min-w-0 flex-wrap items-center gap-2 text-xs">
                  <span className="rounded-lg border border-white/10 px-2 py-1 text-slate-300">
                    {t.markets[entry.market as MarketCode]}
                  </span>
                  <span className={`rounded-lg border px-2 py-1 ${
                    entry.dateBasis === 'explicit_schedule'
                      ? 'border-emerald-400/30 bg-emerald-400/10 text-emerald-300'
                      : entry.dateBasis === 'follow_up_checkpoint'
                        ? 'border-amber-400/30 bg-amber-400/10 text-amber-200'
                        : 'border-white/10 text-slate-400'
                  }`}>
                    {basisLabel(entry, language)}
                  </span>
                </div>
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <p className="min-w-0 break-words font-medium text-slate-100">
                      {localizedTitle(entry, language)}
                    </p>
                    {entry.personalized ? (
                      <span className="inline-flex items-center gap-1 rounded-lg bg-cyan-400/10 px-2 py-1 text-xs text-cyan-300">
                        <Sparkles className="h-3.5 w-3.5" aria-hidden="true" />
                        {t.mineBadge}
                      </span>
                    ) : null}
                    {dueEntryIdSet.has(entry.id) ? (
                      <span className="inline-flex items-center gap-1 rounded-lg bg-amber-400/10 px-2 py-1 text-xs text-amber-200">
                        <BellRing className="h-3.5 w-3.5" aria-hidden="true" />
                        {t.due}
                      </span>
                    ) : null}
                  </div>
                  <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-slate-500">
                    <span className="inline-flex items-center gap-1">
                      <Clock3 className="h-3.5 w-3.5" aria-hidden="true" />
                      {formatDate(entry.scheduledAt, language)}
                    </span>
                    <span>{t.source}: {entry.publisher}</span>
                    <span>{t.statuses[entry.sourceStatus]}</span>
                  </div>
                </div>
                {entry.symbol ? (
                  <button
                    type="button"
                    aria-label={t.queryLabel(entry.symbol)}
                    onClick={() => onOpenSymbol(entry.symbol!)}
                    className="inline-flex min-h-9 items-center justify-center gap-2 self-start rounded-lg border border-white/10 px-3 text-sm text-slate-200 hover:border-cyan-400/40 hover:text-cyan-300 md:self-auto"
                  >
                    <Search className="h-4 w-4" aria-hidden="true" />
                    {t.query}
                  </button>
                ) : null}
              </article>
            ))}
          </div>
        )}

        <div className="grid gap-2 text-xs leading-5 text-slate-500 md:grid-cols-3">
          <p>{t.scheduleRule}</p>
          <p>{t.noCausality}</p>
          <p>{t.disclaimer}</p>
        </div>
      </div>
    </section>
  );
}
