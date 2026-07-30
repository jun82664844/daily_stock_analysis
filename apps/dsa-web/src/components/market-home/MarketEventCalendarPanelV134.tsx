import { useEffect, useMemo, useState } from 'react';
import {
  BellRing,
  CalendarRange,
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

type CalendarView = 'all' | 'mine' | 'due';

const copy = {
  zh: {
    eyebrow: '公开资讯 · 本地提醒 · 未使用 AI',
    title: '免费市场日历',
    subtitle: '汇总三市场已发布事件、来源明确给出的计划日期，以及关注事件的 1/3/5/20 日复盘节点。',
    dueCount: (count: number) => `待复盘 ${count}`,
    all: '全部日历',
    mine: '我的日历',
    due: '待复盘',
    viewLabel: '市场日历查看模式',
    acknowledge: '全部标为已查看',
    explicitSchedule: '计划日期',
    published: '发布时间',
    checkpoint: (days: number) => `${days}日复盘节点`,
    states: {
      recent: '近期已发布',
      today: '今日',
      upcoming: '后续日期',
      due: '待复盘',
      completed: '已观察',
    },
    markets: { cn: 'A股', hk: '港股', us: '美股' },
    statuses: { fresh: '新鲜', cached: '缓存', stale: '过期', unavailable: '暂无数据' },
    source: '来源',
    query: '查询',
    queryLabel: (symbol: string) => `查询 ${symbol}`,
    empty: '当前时间窗口暂无可展示的市场日历条目',
    emptyDue: '当前没有待复盘节点',
    emptyMine: '自选股和关注事件暂未匹配到日历条目',
    scheduleRule: '来源明确给出日期时才标记为计划事件。',
    noCausality: '事件与行情并列展示不代表因果关系。',
    disclaimer: '日历仅整理公开资讯和本地检查点，不构成投资建议。',
    noAi: '未使用 AI',
  },
  en: {
    eyebrow: 'Public information · Local reminders · No AI used',
    title: 'Free market calendar',
    subtitle: 'Combines published events across three markets, source-explicit schedule dates, and 1/3/5/20-day follow-up checkpoints.',
    dueCount: (count: number) => `${count} due`,
    all: 'All calendar',
    mine: 'My calendar',
    due: 'Due reviews',
    viewLabel: 'Market calendar view',
    acknowledge: 'Mark all reviewed',
    explicitSchedule: 'Scheduled date',
    published: 'Published time',
    checkpoint: (days: number) => `${days}-day follow-up`,
    states: {
      recent: 'Recently published',
      today: 'Today',
      upcoming: 'Later date',
      due: 'Due for review',
      completed: 'Observed',
    },
    markets: { cn: 'China', hk: 'Hong Kong', us: 'US' },
    statuses: { fresh: 'Fresh', cached: 'Cached', stale: 'Stale', unavailable: 'Unavailable' },
    source: 'Source',
    query: 'Query',
    queryLabel: (symbol: string) => `Query ${symbol}`,
    empty: 'No market calendar entries are available in the current time window',
    emptyDue: 'No follow-up checkpoints are due',
    emptyMine: 'No calendar entries currently match your watchlist or followed events',
    scheduleRule: 'An item is marked as scheduled only when the source explicitly provides a date.',
    noCausality: 'Showing an event beside market observations does not establish causality.',
    disclaimer: 'This calendar only organizes public information and local checkpoints. Not investment advice.',
    noAi: 'No AI used',
  },
} as const;

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

function basisLabel(
  entry: MarketEventCalendarEntryV134,
  language: 'zh' | 'en',
): string {
  const t = copy[language];
  if (entry.dateBasis === 'explicit_schedule') return t.explicitSchedule;
  if (entry.dateBasis === 'follow_up_checkpoint') {
    return t.checkpoint(entry.checkpointDays ?? 1);
  }
  return t.published;
}

export default function MarketEventCalendarPanelV134({
  language,
  events,
  followedEvents,
  watchlistSymbols,
  scope,
  now = new Date(),
  onOpenSymbol,
}: Props) {
  const t = copy[language];
  const [view, setView] = useState<CalendarView>('all');
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
  const visibleEntries = useMemo(() => {
    const filteredEntries = entries.filter((entry) => {
      if (view === 'mine') return entry.personalized;
      if (view === 'due') return dueEntryIdSet.has(entry.id);
      return true;
    });
    const pinnedFollowUps = filteredEntries
      .filter((entry) => entry.kind === 'follow_up')
      .slice(0, 4);
    const pinnedIds = new Set(pinnedFollowUps.map((entry) => entry.id));
    return [
      ...pinnedFollowUps,
      ...filteredEntries.filter((entry) => !pinnedIds.has(entry.id)),
    ].slice(0, 10);
  }, [dueEntryIdSet, entries, view]);

  useEffect(() => {
    const syncTimer = window.setTimeout(() => {
      setAcknowledgedEntryIds(
        scope === 'guest'
          ? loadCalendarAcknowledgements('guest')
          : adoptGuestCalendarAcknowledgements(scope),
      );
    }, 0);
    return () => window.clearTimeout(syncTimer);
  }, [scope]);

  const acknowledgeDue = () => {
    setAcknowledgedEntryIds(acknowledgeCalendarEntries(scope, dueEntryIds));
  };

  const emptyMessage = view === 'due'
    ? t.emptyDue
    : view === 'mine'
      ? t.emptyMine
      : t.empty;

  return (
    <section
      data-testid="market-event-calendar-v134"
      className="mt-5 border-y border-cyan-400/20 bg-cyan-400/[0.035] py-5"
    >
      <div className="flex flex-col gap-4 px-1 sm:px-2">
        <div className="flex flex-col gap-3 xl:flex-row xl:items-end xl:justify-between">
          <div className="min-w-0">
            <p className="text-xs font-semibold text-cyan-400">{t.eyebrow}</p>
            <h3 className="mt-1 flex flex-wrap items-center gap-2 text-lg font-semibold text-white">
              <CalendarRange className="h-5 w-5 text-cyan-400" aria-hidden="true" />
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
                ['all', t.all],
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
            {emptyMessage}
          </div>
        ) : (
          <div className="divide-y divide-white/10 border-y border-white/10">
            {visibleEntries.map((entry) => (
              <article
                key={entry.id}
                className="grid min-w-0 gap-3 py-4 md:grid-cols-[150px_minmax(0,1fr)_auto] md:items-center"
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
                    <p className="min-w-0 break-words font-medium text-slate-100">{entry.title}</p>
                    {entry.personalized ? (
                      <span className="inline-flex items-center gap-1 rounded-lg bg-cyan-400/10 px-2 py-1 text-xs text-cyan-300">
                        <Sparkles className="h-3.5 w-3.5" aria-hidden="true" />
                        {t.mine}
                      </span>
                    ) : null}
                    {dueEntryIdSet.has(entry.id) ? (
                      <span className="inline-flex items-center gap-1 rounded-lg bg-amber-400/10 px-2 py-1 text-xs text-amber-200">
                        <BellRing className="h-3.5 w-3.5" aria-hidden="true" />
                        {t.states.due}
                      </span>
                    ) : null}
                  </div>
                  <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-slate-500">
                    <span className="inline-flex items-center gap-1">
                      <Clock3 className="h-3.5 w-3.5" aria-hidden="true" />
                      {formatDate(entry.scheduledAt, language)}
                    </span>
                    <span>{t.states[entry.state]}</span>
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
          <p className="flex items-start gap-2">
            <span className="rounded-lg border border-cyan-400/20 px-2 py-0.5 text-cyan-300">{t.noAi}</span>
            <span>{t.disclaimer}</span>
          </p>
        </div>
      </div>
    </section>
  );
}
