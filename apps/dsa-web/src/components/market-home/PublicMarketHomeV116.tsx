import { Activity, BellRing, Clock3, ExternalLink, Newspaper, RefreshCw, TrendingDown, TrendingUp } from 'lucide-react';
import { useMemo, useState } from 'react';
import type { MarketCode, MarketHeadline, MarketSecurityItem, PublicMarketHomeResponse } from '../../api/marketWorkspace';
import PriceAlertFormV116, { type PriceAlertDraft } from '../alerts/PriceAlertFormV116';
import {
  formatMarketNumber,
  formatMarketTimestamp,
  formatSourceLabel,
  formatSourceStatus,
} from '../market-workspace/marketWorkspaceFormat';

type Props = {
  language: 'zh' | 'en';
  data: PublicMarketHomeResponse | null;
  loading: boolean;
  onOpenSymbol: (symbol: string) => void;
  onCreateAlert: (draft: PriceAlertDraft) => Promise<void>;
};

const MARKET_LABELS: Record<MarketCode, { zh: string; en: string }> = {
  cn: { zh: 'A股', en: 'A-shares' },
  hk: { zh: '港股', en: 'Hong Kong' },
  us: { zh: '美股', en: 'US stocks' },
};

const SECURITY_NAMES: Record<string, { zh: string; en: string }> = {
  '000001.SS': { zh: '上证指数', en: 'SSE Composite' },
  '000001.SH': { zh: '上证指数', en: 'SSE Composite' },
  '^HSI': { zh: '恒生指数', en: 'Hang Seng Index' },
  '^GSPC': { zh: '标普500指数', en: 'S&P 500' },
  '600519': { zh: '贵州茅台', en: 'Kweichow Moutai' },
  '601318': { zh: '中国平安', en: 'Ping An Insurance' },
  '000001': { zh: '平安银行', en: 'Ping An Bank' },
  '300750': { zh: '宁德时代', en: 'CATL' },
  '600519.SH': { zh: '贵州茅台', en: 'Kweichow Moutai' },
  '601318.SH': { zh: '中国平安', en: 'Ping An Insurance' },
  '000001.SZ': { zh: '平安银行', en: 'Ping An Bank' },
  '300750.SZ': { zh: '宁德时代', en: 'CATL' },
  '0700.HK': { zh: '腾讯控股', en: 'Tencent' },
  '9988.HK': { zh: '阿里巴巴', en: 'Alibaba' },
  '3690.HK': { zh: '美团', en: 'Meituan' },
  '1299.HK': { zh: '友邦保险', en: 'AIA' },
  AAPL: { zh: '苹果', en: 'Apple' },
  MSFT: { zh: '微软', en: 'Microsoft' },
  NVDA: { zh: '英伟达', en: 'NVIDIA' },
  AMZN: { zh: '亚马逊', en: 'Amazon' },
  TSLA: { zh: '特斯拉', en: 'Tesla' },
};

const PUBLISHER_NAMES: Record<string, string> = {
  '\u8d22\u8054\u793e': 'CLS',
  '\u683c\u9686\u6c47': 'Gelonghui',
  '\u91d1\u5341\u6570\u636e': 'Jin10',
};

type RankingKey = 'mostActive' | 'gainers' | 'losers';

const RANKING_LABELS: Record<RankingKey, { zh: string; en: string }> = {
  mostActive: { zh: '活跃榜', en: 'Most active' },
  gainers: { zh: '涨幅榜', en: 'Gainers' },
  losers: { zh: '跌幅榜', en: 'Losers' },
};

const SESSION_LABELS: Record<string, { zh: string; en: string }> = {
  pre: { zh: '盘前', en: 'Pre-market' },
  regular: { zh: '盘中', en: 'Regular' },
  post: { zh: '盘后', en: 'Post-market' },
  closed: { zh: '休市', en: 'Closed' },
  unknown: { zh: '时段未知', en: 'Session unknown' },
};

const percent = (value: number | null | undefined) => value == null
  ? '-'
  : `${value > 0 ? '+' : ''}${value.toLocaleString(undefined, { maximumFractionDigits: 2 })}%`;

function securityName(item: MarketSecurityItem, language: 'zh' | 'en'): string {
  return SECURITY_NAMES[item.symbol]?.[language] || item.name || item.symbol;
}

function headlinePublisher(headline: MarketHeadline, language: 'zh' | 'en'): string {
  const publisher = headline.publisher || formatSourceLabel(headline.sourceState.source, language);
  return language === 'en' ? (PUBLISHER_NAMES[publisher] || publisher) : publisher;
}

function movementTone(value: number | null | undefined): string {
  if (value == null || value === 0) return 'text-secondary-text';
  return value > 0 ? 'text-success' : 'text-danger';
}

function formatTurnover(value: number | null | undefined, language: 'zh' | 'en'): string {
  if (value == null || !Number.isFinite(value)) return '-';
  const abs = Math.abs(value);
  if (language === 'zh') {
    if (abs >= 100_000_000) return `${(value / 100_000_000).toLocaleString('zh-CN', { maximumFractionDigits: 2 })}亿`;
    if (abs >= 10_000) return `${(value / 10_000).toLocaleString('zh-CN', { maximumFractionDigits: 1 })}万`;
    return value.toLocaleString('zh-CN', { maximumFractionDigits: 0 });
  }
  if (abs >= 1_000_000_000) return `${(value / 1_000_000_000).toLocaleString('en-US', { maximumFractionDigits: 2 })}B`;
  if (abs >= 1_000_000) return `${(value / 1_000_000).toLocaleString('en-US', { maximumFractionDigits: 1 })}M`;
  return value.toLocaleString('en-US', { maximumFractionDigits: 0 });
}

function dataModeLabel(mode: 'latest_available' | 'delayed' | 'realtime', language: 'zh' | 'en'): string {
  if (mode === 'realtime') return language === 'en' ? 'Realtime' : '实时';
  if (mode === 'delayed') return language === 'en' ? 'Delayed' : '延迟行情';
  return language === 'en' ? 'Latest available' : '最新可用';
}

function MarketFeed({
  language,
  headlines,
  items,
}: {
  language: 'zh' | 'en';
  headlines: MarketHeadline[];
  items: MarketSecurityItem[];
}) {
  const en = language === 'en';
  const hasHeadlines = headlines.length > 0;
  return (
    <section className="min-w-0 border-t border-border/70 pt-4 xl:border-l xl:border-t-0 xl:pl-5 xl:pt-0">
      <div className="flex items-center justify-between gap-3">
        <h3 className="flex items-center gap-2 text-base font-semibold text-foreground">
          <Newspaper className="h-4 w-4 text-primary" aria-hidden="true" />
          {hasHeadlines ? (en ? 'Market information' : '市场快讯') : (en ? 'Market moves' : '行情动态')}
        </h3>
        <span className="text-xs text-secondary-text">
          {hasHeadlines ? (en ? 'Source-linked' : '来源可追溯') : (en ? 'Quote-derived' : '基于行情')}
        </span>
      </div>
      <div className="mt-3 divide-y divide-border/60">
        {hasHeadlines ? headlines.slice(0, 5).map((headline, index) => {
          const publishedAt = headline.publishedAt || headline.sourceState.observedAt;
          const displayTime = publishedAt
            ? formatMarketTimestamp(publishedAt, language)
            : `${en ? 'Retrieved' : '抓取'} ${formatMarketTimestamp(headline.sourceState.fetchedAt, language)}`;
          return (
          <article key={`${headline.title}:${index}`} className="py-3 first:pt-0">
            {headline.url ? (
              <a
                href={headline.url}
                target="_blank"
                rel="noopener noreferrer"
                className="group inline-flex max-w-full items-start gap-1.5 font-medium leading-5 text-foreground hover:text-primary"
              >
                <span>{headline.title}</span>
                <ExternalLink className="mt-0.5 h-3.5 w-3.5 shrink-0 opacity-60 group-hover:opacity-100" aria-hidden="true" />
              </a>
            ) : <h4 className="font-medium leading-5 text-foreground">{headline.title}</h4>}
            {headline.summary ? <p className="mt-1 line-clamp-2 text-xs leading-5 text-secondary-text">{headline.summary}</p> : null}
            <p className="mt-1.5 flex flex-wrap items-center gap-1.5 text-[11px] text-secondary-text">
              <span>{headlinePublisher(headline, language)}</span>
              <span aria-hidden="true">·</span>
              <span>{displayTime}</span>
            </p>
          </article>
          );
        }) : items.slice(0, 5).map((item) => (
          <article key={item.symbol} className="py-3 first:pt-0">
            <h4 className="font-medium text-foreground">{securityName(item, language)} <span className="text-xs font-normal text-secondary-text">{item.symbol}</span></h4>
            <p className="mt-1 text-xs leading-5 text-secondary-text">
              {en
                ? `Latest available ${formatMarketNumber(item.currentPrice, language)}, change ${percent(item.changePercent)}.`
                : `最新可用价 ${formatMarketNumber(item.currentPrice, language)}，涨跌幅 ${percent(item.changePercent)}。`}
            </p>
            <p className="mt-1 text-[11px] text-secondary-text">
              {formatSourceStatus(item.sourceState.status, language)} · {formatSourceLabel(item.sourceState.source, language)}
            </p>
          </article>
        ))}
        {!hasHeadlines && items.length === 0 ? (
          <p className="py-8 text-center text-sm text-secondary-text">
            {en ? 'No market information is available for this market.' : '该市场暂时不可用'}
          </p>
        ) : null}
      </div>
    </section>
  );
}

export default function PublicMarketHomeV116({ language, data, loading, onOpenSymbol, onCreateAlert }: Props) {
  const en = language === 'en';
  const [activeMarket, setActiveMarket] = useState<MarketCode>('cn');
  const [rankingKey, setRankingKey] = useState<RankingKey>('mostActive');
  const [expandedSymbol, setExpandedSymbol] = useState('');
  const sections = data?.markets ?? [];
  const activeSection = useMemo(
    () => sections.find((section) => section.market === activeMarket) || sections[0],
    [activeMarket, sections],
  );
  const activeItems = useMemo(() => {
    if (!activeSection) return [];
    if (rankingKey === 'gainers') return activeSection.gainers ?? [];
    if (rankingKey === 'losers') return activeSection.losers ?? [];
    return activeSection.mostActive ?? activeSection.attention ?? [];
  }, [activeSection, rankingKey]);
  const selectedAlertItem = useMemo(() => {
    if (!activeSection || !expandedSymbol) return undefined;
    const candidates = [
      ...(activeSection.mostActive ?? activeSection.attention ?? []),
      ...(activeSection.gainers ?? []),
      ...(activeSection.losers ?? []),
    ];
    return candidates.find((item) => item.symbol === expandedSymbol);
  }, [activeSection, expandedSymbol]);

  if (loading && !data) {
    return (
      <section className="border-y border-border/70 py-8">
        <p className="flex items-center justify-center gap-2 text-secondary-text">
          <RefreshCw className="h-4 w-4 animate-spin" aria-hidden="true" />
          {en ? 'Loading market focus...' : '正在加载市场焦点...'}
        </p>
      </section>
    );
  }
  if (!data || !activeSection) return null;
  const sectorHighlights = activeSection.sectorHighlights ?? [];
  const rankingCache = activeSection.rankingCache ?? { hit: false, ageSeconds: 0, ttlSeconds: 120 };
  const rankingIcons = { mostActive: Activity, gainers: TrendingUp, losers: TrendingDown };

  return (
    <section
      className="border-y border-border/80 bg-surface/35"
      data-testid="public-market-home-v116"
    >
      <div className="px-4 py-4 md:px-5" data-testid="public-home-market-dashboard-v118">
        <span className="sr-only" data-testid="public-home-dynamic-v119">V119 dynamic market home</span>
        <div className="flex min-w-0 flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
          <div className="min-w-0">
            <h2 className="text-xl font-semibold text-foreground">{en ? 'Market focus' : '市场焦点'}</h2>
            <p className="mt-1 text-xs text-secondary-text">
              {en ? 'Market-wide activity, movers, sectors and source-linked information.' : 'A股、港股、美股全市场活跃度、涨跌榜、行业热点与来源可追溯资讯。'}
            </p>
          </div>
          <p className="flex shrink-0 items-center gap-1.5 text-xs text-secondary-text">
            <Clock3 className="h-3.5 w-3.5" aria-hidden="true" />
            {en ? 'Updated' : '更新'} {formatMarketTimestamp(data.asOf, language)}
          </p>
        </div>

        <div className="mt-4 grid grid-cols-3 border-y border-border/70" role="tablist" aria-label={en ? 'Markets' : '市场'}>
          {sections.map((section) => {
            const lead = section.mostActive?.[0] ?? section.attention[0];
            const selected = activeSection.market === section.market;
            return (
              <button
                type="button"
                role="tab"
                aria-selected={selected}
                key={section.market}
                onClick={() => {
                  setActiveMarket(section.market);
                  setRankingKey('mostActive');
                  setExpandedSymbol('');
                }}
                className={`min-w-0 border-r border-border/70 px-3 py-2.5 text-left last:border-r-0 ${selected ? 'bg-primary/10 text-foreground' : 'text-secondary-text hover:bg-hover/60 hover:text-foreground'}`}
              >
                <span className="block text-xs font-medium">{MARKET_LABELS[section.market][language]}</span>
                <span className="mt-1 flex min-w-0 items-center justify-between gap-2">
                  <span className="truncate text-sm font-semibold">{lead ? securityName(lead, language) : (en ? 'Unavailable' : '暂无')}</span>
                  <span className={`shrink-0 text-xs font-medium ${movementTone(lead?.changePercent)}`}>{percent(lead?.changePercent)}</span>
                </span>
              </button>
            );
          })}
        </div>

        {activeSection.indices.length > 0 ? (
          <div
            data-testid="public-home-index-strip"
            className="grid border-b border-border/70 sm:grid-cols-2 xl:grid-cols-4"
            aria-label={en ? 'Major indices' : '主要指数'}
          >
            {activeSection.indices.slice(0, 4).map((index) => (
              <button
                key={index.symbol}
                type="button"
                onClick={() => onOpenSymbol(index.symbol)}
                className="flex min-w-0 items-center justify-between gap-3 border-b border-border/60 px-3 py-2.5 text-left last:border-b-0 hover:bg-hover/45 sm:border-r sm:odd:border-l-0 xl:border-b-0"
              >
                <span className="min-w-0">
                  <span className="block truncate text-xs text-secondary-text">{securityName(index, language)}</span>
                  <span className="mt-0.5 block truncate text-sm font-semibold text-foreground">{formatMarketNumber(index.currentPrice, language)}</span>
                </span>
                <span className={`shrink-0 text-xs font-semibold ${movementTone(index.changePercent)}`}>{percent(index.changePercent)}</span>
              </button>
            ))}
          </div>
        ) : null}

        <div className="mt-5 grid min-w-0 gap-5 xl:grid-cols-[minmax(0,1.55fr)_minmax(18rem,0.8fr)]">
          <section className="min-w-0" aria-label={`${MARKET_LABELS[activeSection.market][language]} ${en ? 'market-wide rankings' : '全市场榜单'}`}>
            <div className="flex min-w-0 flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
              <div className="min-w-0">
                <h3 className="font-semibold text-foreground">{en ? 'Market-wide public rankings' : '全市场公开榜单'}</h3>
                <p className="mt-0.5 text-xs leading-5 text-secondary-text">
                  {en ? 'Public market sorting with liquidity filters; no fixed watchlist and no AI quota.' : '来自公开市场排序并过滤低流动性样本，不使用固定股票池，不消耗 AI 额度。'}
                </p>
              </div>
              <div className="flex shrink-0 flex-wrap items-center gap-1.5 text-[11px] text-secondary-text">
                <span className="rounded-md border border-border px-2 py-1">{dataModeLabel(activeSection.displayMode, language)}</span>
                <span className="rounded-md border border-border px-2 py-1">
                  {rankingCache.hit
                    ? (en ? `Cache ${rankingCache.ageSeconds}s` : `缓存 ${rankingCache.ageSeconds}秒`)
                    : (en ? 'Latest fetch' : '最新抓取')}
                </span>
              </div>
            </div>

            <div className="mt-3 grid grid-cols-3 border-y border-border/70" aria-label={en ? 'Ranking groups' : '榜单类型'}>
              {(Object.keys(RANKING_LABELS) as RankingKey[]).map((key) => {
                const Icon = rankingIcons[key];
                const selected = rankingKey === key;
                return (
                  <button
                    key={key}
                    type="button"
                    aria-pressed={selected}
                    onClick={() => {
                      setRankingKey(key);
                      setExpandedSymbol('');
                    }}
                    className={`inline-flex min-h-10 items-center justify-center gap-1.5 border-r border-border/70 px-2 text-sm last:border-r-0 ${selected ? 'bg-primary/10 font-semibold text-primary' : 'text-secondary-text hover:bg-hover/50 hover:text-foreground'}`}
                  >
                    <Icon className="h-4 w-4" aria-hidden="true" />
                    {RANKING_LABELS[key][language]}
                  </button>
                );
              })}
            </div>

            <div className="mt-3 overflow-hidden border-y border-border/70" role="table">
              <div className="grid grid-cols-[minmax(0,1fr)_minmax(4.5rem,.65fr)_minmax(3.5rem,.5fr)_auto] gap-2 bg-background/35 px-2 py-2 text-[11px] text-secondary-text lg:grid-cols-[minmax(0,1.15fr)_minmax(5rem,.55fr)_minmax(4rem,.5fr)_minmax(5rem,.55fr)_minmax(8rem,.8fr)_auto]" role="row">
                <span>{en ? 'Stock' : '股票'}</span>
                <span className="text-right">{en ? 'Price' : '价格'}</span>
                <span className="text-right">{en ? 'Change' : '涨跌'}</span>
                <span className="hidden text-right lg:block">{en ? 'Turnover' : '成交额'}</span>
                <span className="hidden lg:block">{en ? 'Source' : '来源'}</span>
                <span className="sr-only">{en ? 'Actions' : '操作'}</span>
              </div>
              <div className="divide-y divide-border/60">
                {activeItems.length ? activeItems.map((item) => {
                  const name = securityName(item, language);
                  const sessionLabel = item.tradingSession ? SESSION_LABELS[item.tradingSession]?.[language] : null;
                  return (
                    <div
                      key={item.symbol}
                      className="grid min-h-14 grid-cols-[minmax(0,1fr)_minmax(4.5rem,.65fr)_minmax(3.5rem,.5fr)_auto] items-center gap-2 px-2 py-2 hover:bg-hover/45 lg:grid-cols-[minmax(0,1.15fr)_minmax(5rem,.55fr)_minmax(4rem,.5fr)_minmax(5rem,.55fr)_minmax(8rem,.8fr)_auto]"
                      role="row"
                    >
                      <button type="button" aria-label={en ? `View ${name}` : `查看 ${name}`} onClick={() => onOpenSymbol(item.symbol)} className="min-w-0 text-left">
                        <span className="block truncate text-sm font-medium text-foreground hover:text-primary">{name}</span>
                        <span className="flex min-w-0 items-center gap-1.5 truncate text-[11px] text-secondary-text">
                          <span className="truncate">{item.symbol} · {item.currency ?? '-'}</span>
                          {sessionLabel ? <span className="shrink-0 rounded border border-border px-1">{sessionLabel}</span> : null}
                        </span>
                      </button>
                      <span className="text-right text-sm font-semibold text-foreground">{formatMarketNumber(item.currentPrice, language)}</span>
                      <span className={`text-right text-xs font-semibold ${movementTone(item.changePercent)}`}>{percent(item.changePercent)}</span>
                      <span className="hidden text-right text-xs text-secondary-text lg:block">{formatTurnover(item.turnover, language)}</span>
                      <span className="hidden min-w-0 lg:block">
                        <span className="block truncate text-xs text-secondary-text">{formatSourceLabel(item.sourceState.source, language)}</span>
                        <span className="block truncate text-[11px] text-secondary-text">{formatSourceStatus(item.sourceState.status, language)} · {formatMarketTimestamp(item.sourceState.observedAt ?? item.sourceState.fetchedAt, language)}</span>
                      </span>
                      <button
                        type="button"
                        aria-label={en ? `Set price alert for ${name}` : `为 ${name} 设置到价提醒`}
                        title={en ? 'Price alert' : '到价提醒'}
                        onClick={() => setExpandedSymbol((value) => value === item.symbol ? '' : item.symbol)}
                        className="inline-flex h-8 w-8 items-center justify-center rounded-md border border-border text-secondary-text hover:border-primary/60 hover:text-primary"
                      >
                        <BellRing className="h-4 w-4" aria-hidden="true" />
                      </button>
                    </div>
                  );
                }) : (
                  <p className="py-10 text-center text-sm text-secondary-text">
                    {en ? 'This ranking is temporarily unavailable; no fixed stocks are substituted.' : '该榜单数据暂不可用，未使用固定股票代替。'}
                  </p>
                )}
              </div>
            </div>

            <section className="mt-4 border-y border-border/70 py-3" aria-label={en ? 'Sector highlights' : '行业热点'}>
              <div className="flex items-center justify-between gap-3">
                <h4 className="text-sm font-semibold text-foreground">{en ? 'Sector highlights' : '行业热点'}</h4>
                <span className="text-[11px] text-secondary-text">{en ? 'Public sector data' : '公开行业数据'}</span>
              </div>
              {sectorHighlights.length ? (
                <div className="mt-2 grid divide-y divide-border/60 sm:grid-cols-2 sm:divide-x sm:divide-y-0 xl:grid-cols-3">
                  {sectorHighlights.slice(0, 6).map((sector) => (
                    <div key={sector.name} className="min-w-0 px-2 py-2 first:pl-0">
                      <div className="flex items-center justify-between gap-2">
                        <span className="truncate text-sm font-medium text-foreground">{sector.name}</span>
                        <span className={`shrink-0 text-xs font-semibold ${movementTone(sector.changePercent)}`}>{percent(sector.changePercent)}</span>
                      </div>
                      {sector.leadingSymbol ? (
                        <button type="button" onClick={() => onOpenSymbol(sector.leadingSymbol!)} className="mt-1 max-w-full truncate text-left text-xs text-secondary-text hover:text-primary">
                          {en ? 'Leader' : '领涨'} {sector.leadingName || sector.leadingSymbol} {percent(sector.leadingChangePercent)}
                        </button>
                      ) : null}
                    </div>
                  ))}
                </div>
              ) : (
                <p className="mt-2 text-xs leading-5 text-secondary-text">
                  {en ? 'A reliable public sector source is not available for this market yet.' : '该市场暂未接入可靠的公开行业热点源。'}
                </p>
              )}
            </section>

            {selectedAlertItem ? (
              <div className="mt-3 border-t border-border/70 pt-3">
                <PriceAlertFormV116
                  language={language}
                  stockCode={selectedAlertItem.symbol}
                  stockName={securityName(selectedAlertItem, language)}
                  currentPrice={selectedAlertItem.currentPrice}
                  currency={selectedAlertItem.currency}
                  onSave={onCreateAlert}
                />
              </div>
            ) : null}
          </section>

          <MarketFeed
            language={language}
            headlines={activeSection.headlines ?? []}
            items={activeItems}
          />
        </div>

        <p className="mt-4 border-t border-border/60 pt-3 text-xs text-secondary-text">
          {en
            ? 'Information, objective data and user-defined alerts only. No investment advice.'
            : '仅提供资讯、客观数据和用户自定义提醒，不构成投资建议。'}
        </p>
      </div>
    </section>
  );
}
