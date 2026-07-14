import { CalendarClock, Clock3, ExternalLink, History, Trash2 } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import type { MarketCode, MarketHeadline, PublicMarketHomeResponse } from '../../api/marketWorkspace';
import { formatMarketNumber, formatMarketTimestamp, formatSourceLabel } from '../market-workspace/marketWorkspaceFormat';
import {
  clearRecentMarketSymbols,
  readRecentMarketSymbols,
  RECENT_MARKET_SYMBOLS_EVENT,
  rememberRecentMarketSymbol,
  type RecentMarketSymbolV124,
} from './marketRecentV124';

type Props = {
  language: 'zh' | 'en';
  data: PublicMarketHomeResponse;
  onOpenSymbol: (symbol: string) => void;
};

const MARKET_LABELS: Record<MarketCode, { zh: string; en: string }> = {
  cn: { zh: 'A股', en: 'A-shares' },
  hk: { zh: '港股', en: 'Hong Kong' },
  us: { zh: '美股', en: 'US' },
};

const MARKET_TIME_ZONES: Record<MarketCode, string> = {
  cn: 'Asia/Shanghai',
  hk: 'Asia/Hong_Kong',
  us: 'America/New_York',
};

type TimelineEntry = {
  market: MarketCode;
  headline: MarketHeadline;
  timestamp: string | null;
  timestampKind: 'published' | 'observed' | 'fetched' | 'missing';
};

function localMarketClock(asOf: string, market: MarketCode, language: 'zh' | 'en'): string {
  const date = new Date(asOf);
  if (Number.isNaN(date.getTime())) return '-';
  return new Intl.DateTimeFormat(language === 'en' ? 'en-US' : 'zh-CN', {
    timeZone: MARKET_TIME_ZONES[market],
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  }).format(date);
}

function sessionLabel(market: MarketCode, state: 'open' | 'closed' | 'unknown', language: 'zh' | 'en'): string {
  const marketLabel = MARKET_LABELS[market][language];
  if (language === 'en') {
    if (state === 'open') return `${marketLabel} open`;
    if (state === 'closed') return `${marketLabel} closed`;
    return `${marketLabel} session unconfirmed`;
  }
  if (state === 'open') return `${marketLabel}交易中`;
  if (state === 'closed') return `${marketLabel}已收市`;
  return `${marketLabel}时段待确认`;
}

function timelineEntries(data: PublicMarketHomeResponse): TimelineEntry[] {
  const sorted = data.markets
    .flatMap((section) => (section.headlines ?? []).map((headline) => {
      const published = headline.publishedAt || null;
      const observed = headline.sourceState.observedAt || null;
      const fetched = headline.sourceState.fetchedAt || null;
      return {
        market: section.market,
        headline,
        timestamp: published || observed || fetched,
        timestampKind: published ? 'published' : observed ? 'observed' : fetched ? 'fetched' : 'missing',
      } as TimelineEntry;
    }))
    .sort((left, right) => {
      const leftTime = Date.parse(left.timestamp || '');
      const rightTime = Date.parse(right.timestamp || '');
      return (Number.isFinite(rightTime) ? rightTime : -Infinity)
        - (Number.isFinite(leftTime) ? leftTime : -Infinity);
    });

  const marketLeads = new Map<MarketCode, TimelineEntry>();
  sorted.forEach((entry) => {
    if (!marketLeads.has(entry.market)) marketLeads.set(entry.market, entry);
  });
  const guaranteed = new Set(marketLeads.values());
  const selected = [...marketLeads.values()];
  sorted.forEach((entry) => {
    if (selected.length < 6 && !guaranteed.has(entry)) selected.push(entry);
  });

  return selected
    .sort((left, right) => sorted.indexOf(left) - sorted.indexOf(right))
    .slice(0, 6);
}

function timelineTime(entry: TimelineEntry, language: 'zh' | 'en'): string {
  if (!entry.timestamp) return language === 'en' ? 'Time unavailable' : '时间暂不可用';
  const formatted = formatMarketTimestamp(entry.timestamp, language);
  if (entry.timestampKind === 'fetched') return language === 'en' ? `Retrieved ${formatted}` : `抓取时间 ${formatted}`;
  if (entry.timestampKind === 'observed') return language === 'en' ? `Observed ${formatted}` : `观察时间 ${formatted}`;
  return formatted;
}

export default function DailyMarketWorkbenchV124({ language, data, onOpenSymbol }: Props) {
  const en = language === 'en';
  const [recent, setRecent] = useState<RecentMarketSymbolV124[]>(() => readRecentMarketSymbols());
  const timeline = useMemo(() => timelineEntries(data), [data]);

  useEffect(() => {
    const refresh = () => setRecent(readRecentMarketSymbols());
    window.addEventListener(RECENT_MARKET_SYMBOLS_EVENT, refresh);
    return () => window.removeEventListener(RECENT_MARKET_SYMBOLS_EVENT, refresh);
  }, []);

  const openRecent = (item: RecentMarketSymbolV124) => {
    rememberRecentMarketSymbol(item);
    onOpenSymbol(item.symbol);
  };

  return (
    <section className="mt-4 border-y border-border/70 bg-background/25" data-testid="daily-market-workbench-v124">
      <div className="flex min-w-0 flex-col gap-2 border-b border-border/70 px-3 py-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="min-w-0">
          <h3 className="flex items-center gap-2 text-base font-semibold text-foreground">
            <CalendarClock className="h-4 w-4 text-primary" aria-hidden="true" />
            {en ? 'Daily market workbench' : '今日市场工作台'}
          </h3>
          <p className="mt-1 text-xs leading-5 text-secondary-text">
            {en ? 'Three-market status, source-linked events and your recent research.' : '三地市场状态、来源可追溯事件与最近查看集中呈现。'}
          </p>
        </div>
        <span className="shrink-0 text-[11px] text-secondary-text">
          {en ? 'Information and data only; not investment advice.' : '仅提供资讯和数据，不构成投资建议。'}
        </span>
      </div>

      <div className="grid sm:grid-cols-3" aria-label={en ? 'Market clocks' : '市场时钟'}>
        {data.markets.map((section) => {
          const index = section.indices[0];
          return (
            <div key={section.market} className="min-w-0 border-b border-border/60 px-3 py-3 last:border-b-0 sm:border-b-0 sm:border-r sm:last:border-r-0">
              <div className="flex items-center justify-between gap-2">
                <span className="text-sm font-semibold text-foreground">{sessionLabel(section.market, section.sessionState, language)}</span>
                <span className="flex items-center gap-1 text-xs text-secondary-text">
                  <Clock3 className="h-3.5 w-3.5" aria-hidden="true" />
                  {localMarketClock(data.asOf, section.market, language)}
                </span>
              </div>
              <div className="mt-2 flex min-w-0 items-end justify-between gap-3 text-xs">
                <span className="truncate text-secondary-text">{index?.name || (en ? 'Major index unavailable' : '主要指数暂不可用')}</span>
                <span className="shrink-0 font-medium text-foreground">{index ? formatMarketNumber(index.currentPrice, language) : '-'}</span>
              </div>
            </div>
          );
        })}
      </div>

      <div className="grid min-w-0 border-t border-border/70 lg:grid-cols-[minmax(0,1.45fr)_minmax(16rem,.7fr)]">
        <section className="min-w-0 px-3 py-4 lg:border-r lg:border-border/70" aria-label={en ? 'Cross-market timeline' : '跨市场今日时间线'}>
          <h4 className="font-semibold text-foreground">{en ? 'Cross-market timeline' : '跨市场今日时间线'}</h4>
          <div className="mt-2 divide-y divide-border/60">
            {timeline.length ? timeline.map((entry, index) => (
              <article key={`${entry.market}:${entry.headline.title}:${index}`} className="grid min-w-0 gap-1 py-2.5 sm:grid-cols-[5rem_minmax(0,1fr)_auto] sm:items-start sm:gap-3">
                <span className="text-xs font-medium text-primary">{MARKET_LABELS[entry.market][language]}</span>
                <div className="min-w-0">
                  {entry.headline.url ? (
                    <a href={entry.headline.url} target="_blank" rel="noopener noreferrer" className="inline-flex max-w-full items-start gap-1.5 text-sm font-medium leading-5 text-foreground hover:text-primary">
                      <span>{entry.headline.title}</span>
                      <ExternalLink className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden="true" />
                    </a>
                  ) : <p className="text-sm font-medium leading-5 text-foreground">{entry.headline.title}</p>}
                  <p className="mt-1 text-[11px] text-secondary-text">
                    {entry.headline.publisher || formatSourceLabel(entry.headline.sourceState.source, language)}
                  </p>
                </div>
                <span className="text-[11px] text-secondary-text sm:text-right">{timelineTime(entry, language)}</span>
              </article>
            )) : (
              <p className="py-6 text-sm text-secondary-text">{en ? 'No source-linked events are available yet.' : '暂时没有可追溯的跨市场事件。'}</p>
            )}
          </div>
        </section>

        <section className="min-w-0 px-3 py-4" aria-label={en ? 'Recent research' : '最近查看'}>
          <div className="flex items-center justify-between gap-3">
            <h4 className="flex items-center gap-2 font-semibold text-foreground">
              <History className="h-4 w-4 text-primary" aria-hidden="true" />
              {en ? 'Continue research' : '继续研究'}
            </h4>
            {recent.length ? (
              <button type="button" onClick={clearRecentMarketSymbols} className="inline-flex items-center gap-1 text-xs text-secondary-text hover:text-danger" aria-label={en ? 'Clear recent research' : '清空最近查看'}>
                <Trash2 className="h-3.5 w-3.5" aria-hidden="true" />
                {en ? 'Clear' : '清空'}
              </button>
            ) : null}
          </div>
          <div className="mt-2 divide-y divide-border/60">
            {recent.length ? recent.map((item) => (
              <button key={item.symbol} type="button" onClick={() => openRecent(item)} className="flex w-full min-w-0 items-center justify-between gap-3 py-2.5 text-left hover:text-primary" aria-label={en ? `Continue ${item.name} ${item.symbol}` : `继续查看 ${item.name} ${item.symbol}`}>
                <span className="min-w-0">
                  <span className="block truncate text-sm font-medium text-foreground">{item.name}</span>
                  <span className="mt-0.5 block text-[11px] text-secondary-text">{item.symbol} · {MARKET_LABELS[item.market][language]}</span>
                </span>
                <span className="shrink-0 text-xs text-primary">{en ? 'Open' : '查看'}</span>
              </button>
            )) : (
              <p className="py-6 text-sm leading-6 text-secondary-text">{en ? 'Browse a market ranking to continue research here.' : '浏览市场榜单后，可从这里继续研究。'}</p>
            )}
          </div>
        </section>
      </div>
    </section>
  );
}
