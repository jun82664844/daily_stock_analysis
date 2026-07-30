import { useEffect, useMemo, useState } from 'react';
import { BookOpenCheck, CalendarDays, CheckCheck, ChevronDown, ChevronUp, ExternalLink, Search, Star } from 'lucide-react';
import type { MarketCode, MarketEventCategory, MarketSecurityItem, PublicMarketEvent } from '../../api/marketWorkspace';
import {
  getUnseenMarketEventIds,
  loadSeenMarketEventIds,
  mergeSeenMarketEventIds,
  saveSeenMarketEventIds,
} from '../../lib/marketEventReadState';
import {
  marketForWatchlistSymbol,
  normalizeMarketEventSymbol,
  personalizeMarketEvents,
} from './marketEventPersonalizationV130';
import MarketEventResearchPanelV132 from './MarketEventResearchPanelV132';
import MarketEventFollowUpPanelV133 from './MarketEventFollowUpPanelV133';
import MarketEventCalendarPanelV134 from './MarketEventCalendarPanelV134';
import {
  adoptGuestFollowedMarketEvents,
  followMarketEvent,
  loadFollowedMarketEvents,
  recordFollowedMarketEventObservations,
  unfollowMarketEvent,
  type FollowedMarketEventV133,
} from './marketEventFollowUpV133';

type Props = {
  language: 'zh' | 'en';
  events: PublicMarketEvent[];
  marketItems?: MarketSecurityItem[];
  watchlistSymbols?: string[];
  watchlistSectors?: string[];
  eventFollowUpScope?: string;
  onOpenSymbol: (symbol: string) => void;
};

type Filter = 'all' | MarketEventCategory;
type MarketFilter = 'all' | MarketCode;
type ViewMode = 'auto' | 'focus' | 'unread' | 'all';

const FILTERS: Filter[] = ['all', 'earnings', 'announcement', 'dividend', 'trading_status', 'macro', 'corporate', 'market'];
const MARKET_FILTERS: MarketFilter[] = ['all', 'cn', 'hk', 'us'];
const EMPTY_MARKET_ITEMS: MarketSecurityItem[] = [];

const copy = {
  zh: {
    eyebrow: '公开资讯 · 未用 AI',
    title: '今日市场事件',
    priority: '重点事件',
    newEvent: '新事件',
    newCount: (count: number) => `新增 ${count}`,
    markAllRead: '全部标为已读',
    focusFirst: '为我优先',
    newOnly: '只看新增',
    allEvents: '全部事件',
    eventViewLabel: '事件查看模式',
    focusSummary: (symbols: number, sectors: number, markets: number) => `已按 ${symbols} 只自选、${sectors} 个关联行业和 ${markets} 个关注市场优先排序。`,
    inboxSummary: (total: number, unread: number, priority: number, matched: number | null) => `共 ${total} 条 · 新增 ${unread} · 重点 ${priority}${matched === null ? '' : ` · 自选相关 ${matched}`}`,
    noNewEvents: '当前没有新增市场事件',
    noNewEventsHint: '公开事件仍完整保留，可返回全部事件继续浏览。',
    viewAllEvents: '查看全部事件',
    matchLabels: { watchlist: '自选相关', sector: '相关行业', market: '关注市场' },
    sourceRecords: (count: number) => `${count} 条公开来源记录`,
    sourceRecordNote: '多条来源记录不代表事实已独立证实。',
    showSources: '查看来源',
    hideSources: '收起来源',
    sourceDetailsLabel: (title: string, expanded: boolean) => `${expanded ? '收起' : '查看'} ${title} 的来源`,
    sourceProgress: (shown: number, total: number) => `已显示 ${shown} / 共 ${total} 条公开来源记录`,
    sourceCode: '来源代码',
    openOriginal: (publisher: string) => `打开 ${publisher} 原文`,
    originalLink: '打开原文',
    originalUnavailable: '原文链接不可用',
    subtitle: '汇总 A 股、港股和美股公开事件，按类别快速浏览，并突出自选股相关信息。',
    marketFilterLabel: '按市场筛选',
    categoryFilterLabel: '按事件类型筛选',
    marketFilters: { all: '全部市场', cn: 'A股', hk: '港股', us: '美股' },
    filters: { all: '全部', earnings: '财报', announcement: '公告', dividend: '分红回购', trading_status: '交易状态', macro: '宏观', corporate: '公司动态', market: '市场' },
    categories: { earnings: '财报业绩', announcement: '公司公告', dividend: '分红回购', trading_status: '交易状态', macro: '宏观数据', corporate: '公司动态', market: '市场动态' },
    markets: { cn: 'A股', hk: '港股', us: '美股' },
    sourceMarkets: { cn: 'A股资讯源', hk: '港股资讯源', us: '美股资讯源' },
    statuses: { fresh: '新鲜', cached: '缓存', stale: '过期', unavailable: '不可用' },
    importance: { high: '高重要度', medium: '中重要度', low: '一般重要度' },
    reasons: {
      linked_security: '关联证券', earnings_event: '财报业绩', announcement_event: '公司公告',
      dividend_event: '分红回购', trading_status_event: '交易状态', macro_event: '宏观事件',
      corporate_event: '公司动态', market_signal: '市场关键词', fresh_source: '新鲜来源',
      cached_source: '缓存来源', source_link: '可追溯原文',
    },
    query: '查询',
    research: '研究事件',
    researchLabel: (symbol: string) => `研究 ${symbol} 关联事件`,
    source: '来源',
    retrieved: '抓取',
    empty: '暂未取得可展示的公开市场事件',
    emptyHint: '三地行情仍可继续浏览；公开资讯恢复后会自动显示。',
    disclaimer: '仅提供公开资讯和数据，不构成投资建议。',
  },
  en: {
    eyebrow: 'Public information · No AI',
    title: 'Daily market events',
    priority: 'Priority events',
    newEvent: 'New event',
    newCount: (count: number) => `${count} new`,
    markAllRead: 'Mark all as read',
    focusFirst: 'For me first',
    newOnly: 'New only',
    allEvents: 'All events',
    eventViewLabel: 'Event view mode',
    focusSummary: (symbols: number, sectors: number, markets: number) => `Prioritized from ${symbols} watchlist symbols, ${sectors} related industries and ${markets} followed markets.`,
    inboxSummary: (total: number, unread: number, priority: number, matched: number | null) => `${total} total · ${unread} new · ${priority} priority${matched === null ? '' : ` · ${matched} watchlist matches`}`,
    noNewEvents: 'No new market events',
    noNewEventsHint: 'The complete public event feed remains available in All events.',
    viewAllEvents: 'View all events',
    matchLabels: { watchlist: 'Watchlist match', sector: 'Related industry', market: 'Followed market' },
    sourceRecords: (count: number) => `${count} public source ${count === 1 ? 'record' : 'records'}`,
    sourceRecordNote: 'Multiple source records do not mean the facts were independently verified.',
    showSources: 'View sources',
    hideSources: 'Hide sources',
    sourceDetailsLabel: (title: string, expanded: boolean) => `${expanded ? 'Hide sources for' : 'View sources for'} ${title}`,
    sourceProgress: (shown: number, total: number) => `Showing ${shown} of ${total} public source records`,
    sourceCode: 'Source code',
    openOriginal: (publisher: string) => `Open original from ${publisher}`,
    originalLink: 'Open original',
    originalUnavailable: 'Original link unavailable',
    subtitle: 'Public events across China, Hong Kong and US markets, grouped for quick review with watchlist matches highlighted.',
    marketFilterLabel: 'Filter by market',
    categoryFilterLabel: 'Filter by event type',
    marketFilters: { all: 'All markets', cn: 'China', hk: 'Hong Kong', us: 'US' },
    filters: { all: 'All', earnings: 'Earnings', announcement: 'Filings', dividend: 'Dividends', trading_status: 'Trading status', macro: 'Macro', corporate: 'Corporate', market: 'Market' },
    categories: { earnings: 'Earnings', announcement: 'Announcement', dividend: 'Dividend / buyback', trading_status: 'Trading status', macro: 'Macro data', corporate: 'Corporate event', market: 'Market update' },
    markets: { cn: 'China', hk: 'Hong Kong', us: 'US' },
    sourceMarkets: { cn: 'China source', hk: 'Hong Kong source', us: 'US source' },
    statuses: { fresh: 'Fresh', cached: 'Cached', stale: 'Stale', unavailable: 'Unavailable' },
    importance: { high: 'High importance', medium: 'Medium importance', low: 'General importance' },
    reasons: {
      linked_security: 'Linked security', earnings_event: 'Earnings event', announcement_event: 'Company filing',
      dividend_event: 'Dividend / buyback', trading_status_event: 'Trading status', macro_event: 'Macro event',
      corporate_event: 'Corporate event', market_signal: 'Market signal', fresh_source: 'Fresh source',
      cached_source: 'Cached source', source_link: 'Traceable source',
    },
    query: 'Query',
    research: 'Research event',
    researchLabel: (symbol: string) => `Research event linked to ${symbol}`,
    source: 'Source',
    retrieved: 'Retrieved',
    empty: 'No public market events are available yet',
    emptyHint: 'Market data remains available; events will appear automatically when public feeds recover.',
    disclaimer: 'Public information and data only. Not investment advice.',
  },
} as const;

function eventTime(value: string, language: 'zh' | 'en'): string {
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return new Intl.DateTimeFormat(language === 'zh' ? 'zh-CN' : 'en-US', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  }).format(parsed);
}

function safeSourceLink(value?: string | null): string | null {
  const url = String(value ?? '').trim();
  if (!url) return null;
  try {
    const parsed = new URL(url);
    return parsed.protocol === 'http:' || parsed.protocol === 'https:' ? url : null;
  } catch {
    return null;
  }
}

export default function DailyMarketEventCenterV126({
  language,
  events,
  marketItems = EMPTY_MARKET_ITEMS,
  watchlistSymbols = [],
  watchlistSectors = [],
  eventFollowUpScope = 'guest',
  onOpenSymbol,
}: Props) {
  const t = copy[language];
  const [filter, setFilter] = useState<Filter>('all');
  const [marketFilter, setMarketFilter] = useState<MarketFilter>('all');
  const [viewMode, setViewMode] = useState<ViewMode>('auto');
  const [expandedEventId, setExpandedEventId] = useState<string | null>(null);
  const [researchEventId, setResearchEventId] = useState<string | null>(null);
  const [followedEvents, setFollowedEvents] = useState<FollowedMarketEventV133[]>(
    () => loadFollowedMarketEvents(eventFollowUpScope),
  );
  const currentEventIds = useMemo(() => events.map((event) => event.eventId), [events]);
  const [seenEventIds, setSeenEventIds] = useState<string[]>(
    () => loadSeenMarketEventIds() ?? saveSeenMarketEventIds(currentEventIds),
  );
  const unseenEventIds = useMemo(
    () => new Set(getUnseenMarketEventIds(currentEventIds, seenEventIds)),
    [currentEventIds, seenEventIds],
  );
  const watchlist = useMemo(
    () => new Set(watchlistSymbols.map(normalizeMarketEventSymbol)),
    [watchlistSymbols],
  );
  const hasWatchlist = watchlist.size > 0;
  const focusActive = hasWatchlist && (viewMode === 'auto' || viewMode === 'focus');
  const unreadActive = viewMode === 'unread';
  const allActive = !focusActive && !unreadActive;
  const personalizedEvents = useMemo(() => personalizeMarketEvents(
    events,
    watchlistSymbols,
    watchlistSectors,
    focusActive,
  ), [events, focusActive, watchlistSectors, watchlistSymbols]);
  const filtered = useMemo(() => personalizedEvents
    .filter(({ event }) => (filter === 'all' || event.category === filter)
      && (marketFilter === 'all' || event.market === marketFilter)
      && (!unreadActive || unseenEventIds.has(event.eventId)))
    .slice(0, 12), [filter, marketFilter, personalizedEvents, unreadActive, unseenEventIds]);
  const priorityEventCount = useMemo(
    () => events.filter((event) => event.importance === 'high').length,
    [events],
  );
  const matchedEventCount = useMemo(
    () => personalizedEvents.filter(({ match }) => match !== null).length,
    [personalizedEvents],
  );
  const followedMarketCount = useMemo(
    () => new Set(
      watchlistSymbols
        .map(marketForWatchlistSymbol)
        .filter((market): market is MarketCode => Boolean(market)),
    ).size,
    [watchlistSymbols],
  );
  const marketItemBySymbol = useMemo(() => {
    const items = new Map<string, MarketSecurityItem>();
    marketItems.forEach((item) => {
      const normalized = normalizeMarketEventSymbol(item.symbol);
      if (normalized && !items.has(normalized)) items.set(normalized, item);
    });
    return items;
  }, [marketItems]);
  const followedEventIds = useMemo(
    () => new Set(followedEvents.map((item) => item.eventId)),
    [followedEvents],
  );

  useEffect(() => {
    const syncTimer = window.setTimeout(() => {
      const loaded = eventFollowUpScope === 'guest'
        ? loadFollowedMarketEvents('guest')
        : adoptGuestFollowedMarketEvents(eventFollowUpScope);
      setFollowedEvents(
        loaded.length > 0
          ? recordFollowedMarketEventObservations(eventFollowUpScope, marketItems)
          : loaded,
      );
    }, 0);
    return () => window.clearTimeout(syncTimer);
  }, [eventFollowUpScope, marketItems]);

  const markAllRead = () => {
    const merged = mergeSeenMarketEventIds(seenEventIds, currentEventIds);
    setSeenEventIds(saveSeenMarketEventIds(merged));
  };

  const toggleFollow = (
    event: PublicMarketEvent,
    marketItem?: MarketSecurityItem,
  ) => {
    setFollowedEvents(
      followedEventIds.has(event.eventId)
        ? unfollowMarketEvent(event.eventId, eventFollowUpScope)
        : followMarketEvent(event, marketItem, eventFollowUpScope),
    );
  };

  const removeFollow = (eventId: string) => {
    setFollowedEvents(unfollowMarketEvent(eventId, eventFollowUpScope));
  };

  return (
    <section data-testid="daily-market-event-center-v126" className="border-y border-white/10 bg-[#0a101b] py-6">
      <div className="mx-auto w-full max-w-[1480px] px-4 sm:px-6">
        <div className="flex flex-col gap-3 border-b border-white/10 pb-4 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <p className="text-xs font-semibold text-cyan-400">{t.eyebrow}</p>
            <h2 className="mt-1 flex items-center gap-2 text-xl font-semibold text-white">
              <CalendarDays className="h-5 w-5 text-cyan-400" aria-hidden="true" />
              {t.title}
              <span aria-hidden="true" className="rounded-lg border border-rose-400/30 bg-rose-400/10 px-2 py-1 text-xs font-medium text-rose-300">
                {t.priority} {filtered.filter(({ event }) => event.importance === 'high').length}
              </span>
              {unseenEventIds.size > 0 ? (
                <span aria-hidden="true" className="rounded-lg border border-cyan-400/30 bg-cyan-400/10 px-2 py-1 text-xs font-medium text-cyan-300">
                  {t.newCount(unseenEventIds.size)}
                </span>
              ) : null}
            </h2>
            <p className="mt-1 max-w-3xl text-sm text-slate-400">{t.subtitle}</p>
            <p
              className="mt-2 text-xs font-medium text-slate-500"
              data-testid="market-event-inbox-summary-v131"
            >
              {t.inboxSummary(
                events.length,
                unseenEventIds.size,
                priorityEventCount,
                hasWatchlist ? matchedEventCount : null,
              )}
            </p>
          </div>
          <div className="flex flex-col gap-2 lg:items-end">
            {unseenEventIds.size > 0 ? (
              <button
                type="button"
                onClick={markAllRead}
                aria-label={t.markAllRead}
                className="inline-flex min-h-9 items-center gap-2 self-start rounded-lg border border-white/10 px-3 text-sm text-slate-300 hover:border-cyan-400/40 hover:text-cyan-300 lg:self-auto"
              >
                <CheckCheck className="h-4 w-4" aria-hidden="true" />
                {t.markAllRead}
              </button>
            ) : null}
            {hasWatchlist || unseenEventIds.size > 0 || unreadActive ? (
              <div className="flex flex-col gap-1 lg:items-end">
                <div className="flex flex-wrap gap-2" aria-label={t.eventViewLabel}>
                  {hasWatchlist ? (
                    <button
                      type="button"
                      aria-pressed={focusActive}
                      onClick={() => setViewMode('focus')}
                      className={`min-h-9 rounded-lg border px-3 text-sm ${focusActive ? 'border-amber-400/60 bg-amber-400/10 text-amber-200' : 'border-white/10 text-slate-300'}`}
                    >
                      {t.focusFirst}
                    </button>
                  ) : null}
                  {unseenEventIds.size > 0 || unreadActive ? (
                    <button
                      type="button"
                      aria-pressed={unreadActive}
                      onClick={() => setViewMode('unread')}
                      className={`min-h-9 rounded-lg border px-3 text-sm ${unreadActive ? 'border-cyan-400/60 bg-cyan-400/10 text-cyan-200' : 'border-white/10 text-slate-300'}`}
                    >
                      {t.newOnly}
                    </button>
                  ) : null}
                  <button
                    type="button"
                    aria-pressed={allActive}
                    onClick={() => setViewMode('all')}
                    className={`min-h-9 rounded-lg border px-3 text-sm ${allActive ? 'border-cyan-400/60 bg-cyan-400/10 text-cyan-200' : 'border-white/10 text-slate-300'}`}
                  >
                    {t.allEvents}
                  </button>
                </div>
                {hasWatchlist ? (
                  <p className="max-w-2xl text-xs text-slate-500" data-testid="market-event-personalization-summary-v130">
                    {t.focusSummary(
                      watchlist.size,
                      new Set(watchlistSectors.map((sector) => sector.trim()).filter(Boolean)).size,
                      followedMarketCount,
                    )}
                  </p>
                ) : null}
              </div>
            ) : null}
            <div className="flex flex-wrap gap-2" aria-label={t.marketFilterLabel}>
              {MARKET_FILTERS.map((item) => (
                <button
                  key={item}
                  type="button"
                  onClick={() => setMarketFilter(item)}
                  aria-pressed={marketFilter === item}
                  className={`min-h-9 rounded-lg border px-3 text-sm transition-colors ${
                    marketFilter === item
                      ? 'border-cyan-400/70 bg-cyan-400/10 text-cyan-300'
                      : 'border-white/10 bg-transparent text-slate-300 hover:border-white/25 hover:text-white'
                  }`}
                >
                  {t.marketFilters[item]}
                </button>
              ))}
            </div>
            <div className="flex flex-wrap gap-2" aria-label={t.categoryFilterLabel}>
              {FILTERS.map((item) => (
                <button
                  key={item}
                  type="button"
                  onClick={() => setFilter(item)}
                  aria-pressed={filter === item}
                  className={`min-h-9 rounded-lg border px-3 text-sm transition-colors ${
                    filter === item
                      ? 'border-cyan-400/70 bg-cyan-400/10 text-cyan-300'
                      : 'border-white/10 bg-transparent text-slate-300 hover:border-white/25 hover:text-white'
                  }`}
                >
                  {t.filters[item]}
                </button>
              ))}
            </div>
          </div>
        </div>

        <MarketEventCalendarPanelV134
          language={language}
          events={events}
          followedEvents={followedEvents}
          watchlistSymbols={watchlistSymbols}
          scope={eventFollowUpScope}
          onOpenSymbol={onOpenSymbol}
        />

        <MarketEventFollowUpPanelV133
          language={language}
          followedEvents={followedEvents}
          publicEvents={events}
          onOpenSymbol={onOpenSymbol}
          onRemove={removeFollow}
        />

        {unreadActive && filtered.length === 0 ? (
          <div className="py-10 text-center">
            <p className="font-medium text-slate-200">{t.noNewEvents}</p>
            <p className="mt-1 text-sm text-slate-500">{t.noNewEventsHint}</p>
            <button
              type="button"
              onClick={() => setViewMode('all')}
              className="mt-4 min-h-10 rounded-lg border border-cyan-400/30 px-4 text-sm text-cyan-300 hover:bg-cyan-400/10"
            >
              {t.viewAllEvents}
            </button>
          </div>
        ) : filtered.length === 0 ? (
          <div className="py-10 text-center">
            <p className="font-medium text-slate-200">{t.empty}</p>
            <p className="mt-1 text-sm text-slate-500">{t.emptyHint}</p>
          </div>
        ) : (
          <div className="divide-y divide-white/10">
            {filtered.map(({ event, match }) => {
              const isNew = unseenEventIds.has(event.eventId);
              const sourceCount = Number.isFinite(event.sourceCount) && event.sourceCount >= 1
                ? Math.min(20, Math.floor(event.sourceCount))
                : 1;
              const sourcePublishers = Array.from(new Set(
                (event.sourcePublishers?.length ? event.sourcePublishers : [event.publisher])
                  .map((publisher) => String(publisher ?? '').trim())
                  .filter(Boolean),
              )).slice(0, 3);
              const sourceRecords = (Array.isArray(event.sourceRecords) ? event.sourceRecords : []).slice(0, 8);
              const sourceDetailsOpen = expandedEventId === event.eventId;
              const researchOpen = researchEventId === event.eventId;
              const linkedMarketItem = event.symbol
                ? marketItemBySymbol.get(normalizeMarketEventSymbol(event.symbol))
                : undefined;
              const sourceDetailsId = `event-sources-${event.eventId.replace(/[^a-zA-Z0-9_-]/g, '-')}`;
              const researchTriggerId = `event-research-${event.eventId.replace(/[^a-zA-Z0-9_-]/g, '-')}`;
              return (
                <article key={event.eventId} className="grid gap-3 py-4 md:grid-cols-[150px_minmax(0,1fr)_auto] md:items-start">
                  <div className="flex flex-wrap items-center gap-2 text-xs">
                    <span className="rounded-lg border border-white/10 px-2 py-1 text-slate-300">
                      {event.symbol ? t.markets[event.market as MarketCode] : t.sourceMarkets[event.market as MarketCode]}
                    </span>
                    <span className="rounded-lg bg-cyan-400/10 px-2 py-1 text-cyan-300">{t.categories[event.category]}</span>
                    <span className="text-slate-500">{eventTime(event.eventTime, language)}</span>
                  </div>
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      {event.url ? (
                        <a className="font-medium text-slate-100 hover:text-cyan-300" href={event.url} target="_blank" rel="noreferrer">
                          {event.title}
                          <ExternalLink className="ml-1 inline h-3.5 w-3.5" aria-hidden="true" />
                        </a>
                      ) : (
                        <h3 className="font-medium text-slate-100">{event.title}</h3>
                      )}
                      {match ? (
                        <span className="inline-flex items-center gap-1 rounded-lg border border-amber-400/30 bg-amber-400/10 px-2 py-1 text-xs text-amber-300">
                          <Star className="h-3.5 w-3.5" aria-hidden="true" />
                          {t.matchLabels[match]}
                        </span>
                      ) : null}
                      {isNew ? (
                        <span className="rounded-lg border border-cyan-400/30 bg-cyan-400/10 px-2 py-1 text-xs text-cyan-300">
                          {t.newEvent}
                        </span>
                      ) : null}
                      <span className={`rounded-lg border px-2 py-1 text-xs ${
                        event.importance === 'high'
                          ? 'border-rose-400/30 bg-rose-400/10 text-rose-300'
                          : event.importance === 'medium'
                            ? 'border-amber-400/30 bg-amber-400/10 text-amber-300'
                            : 'border-white/10 text-slate-400'
                      }`}>
                        {t.importance[event.importance]}
                      </span>
                    </div>
                    {event.summary ? <p className="mt-1 line-clamp-2 text-sm leading-6 text-slate-400">{event.summary}</p> : null}
                    {event.relevanceReasons.length > 0 ? (
                      <div className="mt-2 flex flex-wrap gap-1.5">
                        {event.relevanceReasons.slice(0, 3).map((reason) => (
                          <span key={reason} className="rounded-md bg-white/[0.04] px-2 py-1 text-xs text-slate-400">
                            {t.reasons[reason as keyof typeof t.reasons] ?? reason}
                          </span>
                        ))}
                      </div>
                    ) : null}
                    <div className="mt-2 flex flex-wrap items-center gap-1.5 text-xs text-slate-400">
                      <span className="rounded-md border border-white/10 px-2 py-1">{t.sourceRecords(sourceCount)}</span>
                      {sourcePublishers.map((publisher) => (
                        <span key={publisher} className="rounded-md bg-white/[0.04] px-2 py-1">{publisher}</span>
                      ))}
                      {sourceRecords.length > 0 ? (
                        <button
                          type="button"
                          aria-expanded={sourceDetailsOpen}
                          aria-controls={sourceDetailsId}
                          aria-label={t.sourceDetailsLabel(event.title, sourceDetailsOpen)}
                          onClick={() => setExpandedEventId(sourceDetailsOpen ? null : event.eventId)}
                          className="inline-flex min-h-7 items-center gap-1 rounded-md border border-cyan-400/25 px-2 text-cyan-300 hover:bg-cyan-400/10"
                        >
                          {sourceDetailsOpen ? <ChevronUp className="h-3.5 w-3.5" aria-hidden="true" /> : <ChevronDown className="h-3.5 w-3.5" aria-hidden="true" />}
                          {sourceDetailsOpen ? t.hideSources : t.showSources}
                        </button>
                      ) : null}
                    </div>
                    <p className="mt-1 text-xs text-slate-500">
                      {t.source}: {event.publisher || event.sourceState.source} · <span>{t.statuses[event.sourceState.status]}</span> · {event.timeKind === 'retrieved' ? t.retrieved : eventTime(event.eventTime, language)}
                    </p>
                    {sourceDetailsOpen ? (
                      <div id={sourceDetailsId} className="mt-3 border-t border-white/10 pt-3">
                        <div className="flex flex-col gap-1 text-xs text-slate-500 sm:flex-row sm:items-center sm:justify-between">
                          <span>{t.sourceProgress(sourceRecords.length, sourceCount)}</span>
                          <span>{t.sourceRecordNote}</span>
                        </div>
                        <div className="mt-2 divide-y divide-white/10 border-y border-white/10">
                          {sourceRecords.map((record, index) => {
                            const originalUrl = safeSourceLink(record.url);
                            return (
                              <div key={`${record.url || record.source}-${record.eventTime}-${index}`} className="flex flex-col gap-2 py-3 sm:flex-row sm:items-center sm:justify-between">
                                <div className="min-w-0">
                                  <p className="font-medium text-slate-200">{record.publisher}</p>
                                  <p className="mt-0.5 break-words text-xs text-slate-500">
                                    {t.sourceCode}: {record.source} · {eventTime(record.eventTime, language)}
                                  </p>
                                </div>
                                {originalUrl ? (
                                  <a
                                    href={originalUrl}
                                    target="_blank"
                                    rel="noreferrer"
                                    aria-label={t.openOriginal(record.publisher)}
                                    className="inline-flex min-h-9 shrink-0 items-center gap-1.5 self-start text-sm text-cyan-300 hover:text-cyan-200 sm:self-auto"
                                  >
                                    <ExternalLink className="h-3.5 w-3.5" aria-hidden="true" />
                                    {t.originalLink}
                                  </a>
                                ) : (
                                  <span className="text-xs text-slate-500">{t.originalUnavailable}</span>
                                )}
                              </div>
                            );
                          })}
                        </div>
                      </div>
                    ) : null}
                  </div>
                  {event.symbol ? (
                    <div className="flex flex-wrap gap-2 md:flex-col">
                      <button
                        id={researchTriggerId}
                        type="button"
                        onClick={() => setResearchEventId(researchOpen ? null : event.eventId)}
                        aria-expanded={researchOpen}
                        aria-label={t.researchLabel(event.symbol)}
                        className="inline-flex min-h-10 items-center justify-center gap-2 rounded-lg border border-white/10 px-3 text-sm text-slate-300 hover:border-cyan-400/30 hover:text-cyan-300"
                      >
                        <BookOpenCheck className="h-4 w-4" aria-hidden="true" />
                        {t.research}
                      </button>
                      <button
                        type="button"
                        onClick={() => onOpenSymbol(event.symbol as string)}
                        aria-label={`${t.query} ${event.symbol}`}
                        className="inline-flex min-h-10 items-center justify-center gap-2 rounded-lg border border-cyan-400/30 px-3 text-sm text-cyan-300 hover:bg-cyan-400/10"
                      >
                        <Search className="h-4 w-4" aria-hidden="true" />
                        {event.symbol}
                      </button>
                    </div>
                  ) : null}
                  {researchOpen && event.symbol ? (
                    <div className="md:col-span-3">
                      <MarketEventResearchPanelV132
                        language={language}
                        event={event}
                        marketItem={linkedMarketItem}
                        isFollowed={followedEventIds.has(event.eventId)}
                        onToggleFollow={() => toggleFollow(event, linkedMarketItem)}
                        onOpenSymbol={onOpenSymbol}
                        onClose={() => {
                          setResearchEventId(null);
                          document.getElementById(researchTriggerId)?.focus();
                        }}
                      />
                    </div>
                  ) : null}
                </article>
              );
            })}
          </div>
        )}
        <p className="border-t border-white/10 pt-3 text-xs text-slate-500">
          <span>{t.sourceRecordNote}</span> · <span>{t.disclaimer}</span>
        </p>
      </div>
    </section>
  );
}
