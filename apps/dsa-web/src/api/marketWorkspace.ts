import apiClient from './index';
import { toCamelCase } from './utils';

export type MarketCode = 'cn' | 'hk' | 'us';
export type SourceStatus = 'fresh' | 'cached' | 'stale' | 'unavailable';

export type DataSourceState = {
  source: string;
  status: SourceStatus;
  observedAt?: string | null;
  fetchedAt?: string | null;
  delaySeconds?: number | null;
  warningCode?: string | null;
};

export type MarketSecurityItem = {
  symbol: string;
  name: string;
  market: MarketCode;
  currency?: string | null;
  currentPrice?: number | null;
  changePercent?: number | null;
  volume?: number | null;
  turnover?: number | null;
  marketCap?: number | null;
  sector?: string | null;
  tradingSession?: 'pre' | 'regular' | 'post' | 'closed' | 'unknown' | null;
  sourceState: DataSourceState;
};

export type MarketSectorItem = {
  name: string;
  market: MarketCode;
  changePercent?: number | null;
  leadingSymbol?: string | null;
  leadingName?: string | null;
  leadingChangePercent?: number | null;
  sourceState: DataSourceState;
};

export type MarketCacheState = {
  hit: boolean;
  ageSeconds: number;
  ttlSeconds: number;
};

export type MarketHeadline = {
  title: string;
  summary?: string | null;
  publisher?: string | null;
  publishedAt?: string | null;
  url?: string | null;
  sourceState: DataSourceState;
};

export type MarketEventCategory =
  | 'earnings'
  | 'announcement'
  | 'dividend'
  | 'trading_status'
  | 'macro'
  | 'corporate'
  | 'market';

export type PublicMarketEventSourceRecord = {
  publisher: string;
  source: string;
  url?: string | null;
  eventTime: string;
  timeKind: 'published' | 'observed' | 'retrieved' | 'scheduled' | 'unknown';
};

export type PublicMarketEvent = {
  eventId: string;
  market: MarketCode;
  category: MarketEventCategory;
  title: string;
  summary?: string | null;
  symbol?: string | null;
  name?: string | null;
  sector?: string | null;
  eventTime: string;
  timeKind: 'published' | 'observed' | 'retrieved' | 'scheduled' | 'unknown';
  publisher?: string | null;
  url?: string | null;
  sourceState: DataSourceState;
  classificationSource:
    | 'keyword_rules'
    | 'provider_schedule'
    | 'provider_event_history';
  scheduleType?:
    | 'earnings_release'
    | 'ex_dividend'
    | 'stock_split'
    | 'macro_policy'
    | null;
  relevanceScore: number;
  importance: 'high' | 'medium' | 'low';
  relevanceReasons: string[];
  sourceCount: number;
  sourcePublishers: string[];
  sourceRecords: PublicMarketEventSourceRecord[];
};

export type MarketWorkspaceOverview = {
  market: MarketCode;
  asOf: string;
  sessionState: 'open' | 'closed' | 'unknown';
  sessionPhase?: MarketSessionPhase;
  marketLocalTime?: string | null;
  minutesToOpen?: number | null;
  minutesToClose?: number | null;
  sessionSource?: 'exchange_calendar' | 'unavailable';
  sessionWarningCodes?: string[];
  indices: MarketSecurityItem[];
  breadth: { advancers: number; decliners: number; unchanged: number; unavailable: boolean };
  movers: MarketSecurityItem[];
  heatmap: MarketSecurityItem[];
  headlines: MarketHeadline[];
  sources: DataSourceState[];
  warnings: string[];
  cache: { hit: boolean; ageSeconds: number; ttlSeconds: number };
  aiUsed: boolean;
  informationalOnly: boolean;
};

export type PublicMarketHomeSection = {
  market: MarketCode;
  sessionState: 'open' | 'closed' | 'unknown';
  sessionPhase?: MarketSessionPhase;
  marketLocalTime?: string | null;
  minutesToOpen?: number | null;
  minutesToClose?: number | null;
  sessionSource?: 'exchange_calendar' | 'unavailable';
  sessionWarningCodes?: string[];
  displayMode: 'latest_available' | 'delayed' | 'realtime';
  rankingScope: 'configured_universe' | 'market_wide' | 'unavailable';
  selectionBasis: string;
  indices: MarketSecurityItem[];
  attention: MarketSecurityItem[];
  mostActive?: MarketSecurityItem[];
  gainers?: MarketSecurityItem[];
  losers?: MarketSecurityItem[];
  sectorHighlights?: MarketSectorItem[];
  rankingCache?: MarketCacheState;
  headlines?: MarketHeadline[];
  sources: DataSourceState[];
  warnings: string[];
};

export type MarketSessionPhase =
  | 'premarket'
  | 'intraday'
  | 'lunch_break'
  | 'closing_auction'
  | 'postmarket'
  | 'non_trading'
  | 'unknown';

export type PublicMarketHomeResponse = {
  asOf: string;
  markets: PublicMarketHomeSection[];
  events: PublicMarketEvent[];
  aiUsed: boolean;
  informationalOnly: boolean;
};

export type MarketEventReactionWindow = {
  tradingDays: 1 | 3 | 5 | 20;
  status: 'available' | 'pending' | 'insufficient_data';
  observedDate?: string | null;
  symbolReturnPercent?: number | null;
  benchmarkReturnPercent?: number | null;
  relativeReturnPercent?: number | null;
  volumeRatio?: number | null;
};

export type EventReactionMarketSource = {
  market: MarketCode;
  status: SourceStatus;
  eventCount: number;
  observedAt?: string | null;
  fetchedAt?: string | null;
  warningCode?: string | null;
};

export type EventReactionCacheState = MarketCacheState & {
  storage: 'none' | 'memory' | 'disk';
  refreshing: boolean;
};

export type PublicMarketEventReaction = {
  eventId: string;
  market: MarketCode;
  title: string;
  symbol: string;
  name: string;
  subjectType: 'security' | 'market_benchmark';
  eventTime: string;
  eventTimeKind?: 'scheduled' | 'observed';
  classificationSource?: 'provider_schedule' | 'provider_event_history';
  scheduleType?:
    | 'earnings_release'
    | 'ex_dividend'
    | 'stock_split'
    | 'macro_policy'
    | null;
  historySymbol: string;
  baselineDate?: string | null;
  benchmarkSymbol?: string | null;
  benchmarkName?: string | null;
  status: 'available' | 'partial' | 'pending' | 'unavailable';
  windows: MarketEventReactionWindow[];
  sourceState: DataSourceState;
  benchmarkSourceState?: DataSourceState | null;
  warningCodes: string[];
};

export type PublicMarketEventReactionResponse = {
  asOf: string;
  items: PublicMarketEventReaction[];
  marketSources: EventReactionMarketSource[];
  warnings: string[];
  cache: EventReactionCacheState;
  aiUsed: boolean;
  informationalOnly: boolean;
};

export type SymbolArchiveEventType =
  | 'earnings'
  | 'dividend'
  | 'split'
  | 'buyback'
  | 'announcement';

export type PublicSymbolEventArchiveItem = PublicMarketEventReaction & {
  eventType: SymbolArchiveEventType;
  summary?: string | null;
  publisher: string;
  sourceUrl?: string | null;
  eventSourceState: DataSourceState;
};

export type PublicSymbolEventArchiveResponse = {
  symbol: string;
  name: string;
  market: MarketCode;
  months: 6 | 12 | 24;
  asOf: string;
  items: PublicSymbolEventArchiveItem[];
  availableEventTypes: SymbolArchiveEventType[];
  warnings: string[];
  aiUsed: boolean;
  informationalOnly: boolean;
  causalityDisclaimer: boolean;
};

export type MarketSearchItem = {
  symbol: string;
  name: string;
  market: MarketCode;
  exchange?: string | null;
  currency?: string | null;
  matchType: 'exact_symbol' | 'symbol_prefix' | 'name_prefix' | 'name_contains';
  sourceState: DataSourceState;
};

export type MarketSearchResponse = {
  query: string;
  markets: MarketCode[];
  items: MarketSearchItem[];
  aiUsed: boolean;
};

export type SymbolWorkspaceResponse = {
  symbol: string;
  name: string;
  market: MarketCode;
  currency?: string | null;
  asOf?: string | null;
  quote: Record<string, unknown>;
  history: Array<Record<string, unknown>>;
  indicators: Record<string, unknown>;
  profile: Record<string, unknown>;
  headlines: MarketHeadline[];
  sources: DataSourceState[];
  warnings: string[];
  personalization?: { watchlisted?: boolean; alertCount?: number } | null;
  aiUsed: boolean;
  informationalOnly: boolean;
};

export type MarketDailyBriefResponse = {
  userId: number;
  asOf: string;
  items: Array<{
    symbol: string;
    name: string;
    market: string;
    currentPrice?: number | null;
    changePercent?: number | null;
    freshness: SourceStatus;
    status: string;
    warningCodes: string[];
  }>;
  emptyAction?: string | null;
  warnings: string[];
  aiUsed: boolean;
  informationalOnly: boolean;
};

function safeHttpUrl(value: unknown): string | null {
  const url = String(value ?? '').trim();
  if (!url) return null;
  try {
    const parsed = new URL(url);
    return parsed.protocol === 'http:' || parsed.protocol === 'https:' ? url : null;
  } catch {
    return null;
  }
}

function normalizeEventSourceRecords(event: PublicMarketEvent): PublicMarketEventSourceRecord[] {
  const rawRecords = Array.isArray(event.sourceRecords) && event.sourceRecords.length > 0
    ? event.sourceRecords
    : [{
        publisher: event.publisher ?? event.sourceState?.source ?? 'public_market_news',
        source: event.sourceState?.source ?? 'public_market_news',
        url: event.url,
        eventTime: event.eventTime,
        timeKind: event.timeKind,
      }];
  const seen = new Set<string>();
  const records: PublicMarketEventSourceRecord[] = [];
  for (const record of rawRecords) {
    const source = String(record?.source ?? 'public_market_news').trim() || 'public_market_news';
    const publisher = String(record?.publisher ?? source).trim() || source;
    const url = safeHttpUrl(record?.url);
    const eventTime = String(record?.eventTime ?? event.eventTime ?? '').trim();
    const timeKind = ['published', 'observed', 'retrieved'].includes(record?.timeKind)
      ? record.timeKind
      : 'unknown';
    const key = url
      ? `url:${url.toLowerCase()}`
      : `source:${publisher.toLowerCase()}|${source.toLowerCase()}|${eventTime}|${timeKind}`;
    if (seen.has(key)) continue;
    seen.add(key);
    records.push({ publisher, source, url, eventTime, timeKind });
    if (records.length >= 8) break;
  }
  return records;
}

export const marketWorkspaceApi = {
  async getHome(): Promise<PublicMarketHomeResponse> {
    const response = await apiClient.get('/api/v1/market-workspace/home');
    const body = toCamelCase<PublicMarketHomeResponse>(response.data);
    return {
      ...body,
      events: Array.isArray(body.events) ? body.events.map((event) => ({
        ...event,
        sector: String(event.sector ?? '').trim() || null,
        url: safeHttpUrl(event.url),
        relevanceScore: Number.isFinite(event.relevanceScore) ? event.relevanceScore : 0,
        importance: event.importance ?? 'low',
        relevanceReasons: Array.isArray(event.relevanceReasons) ? event.relevanceReasons : [],
        sourceCount: Number.isFinite(event.sourceCount) && event.sourceCount >= 1
          ? Math.min(20, Math.floor(event.sourceCount))
          : 1,
        sourcePublishers: Array.from(new Set(
          (Array.isArray(event.sourcePublishers) ? event.sourcePublishers : [event.publisher])
            .map((publisher) => String(publisher ?? '').trim())
            .filter(Boolean),
        )).slice(0, 8),
        sourceRecords: normalizeEventSourceRecords(event),
      })) : [],
      markets: Array.isArray(body.markets) ? body.markets.map((market) => ({
        ...market,
        sessionPhase: market.sessionPhase ?? 'unknown',
        sessionSource: market.sessionSource ?? 'unavailable',
        sessionWarningCodes: Array.isArray(market.sessionWarningCodes) ? market.sessionWarningCodes : [],
        indices: Array.isArray(market.indices) ? market.indices : [],
        attention: Array.isArray(market.attention) ? market.attention : [],
        mostActive: Array.isArray(market.mostActive) ? market.mostActive : (Array.isArray(market.attention) ? market.attention : []),
        gainers: Array.isArray(market.gainers) ? market.gainers : [],
        losers: Array.isArray(market.losers) ? market.losers : [],
        sectorHighlights: Array.isArray(market.sectorHighlights) ? market.sectorHighlights : [],
        rankingCache: market.rankingCache ?? { hit: false, ageSeconds: 0, ttlSeconds: 120 },
        headlines: Array.isArray(market.headlines) ? market.headlines : [],
        sources: Array.isArray(market.sources) ? market.sources : [],
        warnings: Array.isArray(market.warnings) ? market.warnings : [],
      })) : [],
    };
  },
  async getOverview(market: MarketCode): Promise<MarketWorkspaceOverview> {
    const response = await apiClient.get('/api/v1/market-workspace/overview', { params: { market } });
    const body = toCamelCase<MarketWorkspaceOverview>(response.data);
    return {
      ...body,
      sessionPhase: body.sessionPhase ?? 'unknown',
      sessionSource: body.sessionSource ?? 'unavailable',
      sessionWarningCodes: Array.isArray(body.sessionWarningCodes) ? body.sessionWarningCodes : [],
      breadth: body.breadth ?? { advancers: 0, decliners: 0, unchanged: 0, unavailable: true },
      indices: Array.isArray(body.indices) ? body.indices : [],
      movers: Array.isArray(body.movers) ? body.movers : [],
      heatmap: Array.isArray(body.heatmap) ? body.heatmap : [],
      headlines: Array.isArray(body.headlines) ? body.headlines : [],
      sources: Array.isArray(body.sources) ? body.sources : [],
      warnings: Array.isArray(body.warnings) ? body.warnings : [],
    };
  },
  async getEventReactions(): Promise<PublicMarketEventReactionResponse> {
    const response = await apiClient.get(
      '/api/v1/market-workspace/event-reactions',
      { withCredentials: false },
    );
    const body = toCamelCase<PublicMarketEventReactionResponse>(response.data);
    return {
      ...body,
      items: Array.isArray(body.items) ? body.items.map((item) => ({
        ...item,
        windows: Array.isArray(item.windows) ? item.windows : [],
        warningCodes: Array.isArray(item.warningCodes) ? item.warningCodes : [],
      })) : [],
      marketSources: Array.isArray(body.marketSources) ? body.marketSources : [],
      warnings: Array.isArray(body.warnings) ? body.warnings : [],
      cache: {
        hit: Boolean(body.cache?.hit),
        ageSeconds: Number.isFinite(body.cache?.ageSeconds) ? body.cache.ageSeconds : 0,
        ttlSeconds: Number.isFinite(body.cache?.ttlSeconds) ? body.cache.ttlSeconds : 900,
        storage: body.cache?.storage === 'memory'
          || body.cache?.storage === 'disk'
          || body.cache?.storage === 'none'
          ? body.cache.storage
          : 'none',
        refreshing: Boolean(body.cache?.refreshing),
      },
      aiUsed: Boolean(body.aiUsed),
      informationalOnly: body.informationalOnly !== false,
    };
  },
  async search(query: string, markets: MarketCode[] = ['cn', 'hk', 'us'], limit = 8): Promise<MarketSearchResponse> {
    const response = await apiClient.get('/api/v1/market-workspace/search', {
      params: { q: query, markets: markets.join(','), limit },
    });
    return toCamelCase<MarketSearchResponse>(response.data);
  },
  async getSymbol(symbol: string): Promise<SymbolWorkspaceResponse> {
    const response = await apiClient.get(`/api/v1/market-workspace/symbol/${encodeURIComponent(symbol)}`);
    return toCamelCase<SymbolWorkspaceResponse>(response.data);
  },
  async getSymbolEventArchive(
    symbol: string,
    months: 6 | 12 | 24 = 12,
  ): Promise<PublicSymbolEventArchiveResponse> {
    const response = await apiClient.get(
      `/api/v1/market-workspace/symbol/${encodeURIComponent(symbol)}/event-archive`,
      { params: { months }, withCredentials: false },
    );
    const body = toCamelCase<PublicSymbolEventArchiveResponse>(response.data);
    return {
      ...body,
      items: Array.isArray(body.items) ? body.items.map((item) => ({
        ...item,
        sourceUrl: safeHttpUrl(item.sourceUrl),
        windows: Array.isArray(item.windows) ? item.windows : [],
        warningCodes: Array.isArray(item.warningCodes) ? item.warningCodes : [],
      })) : [],
      availableEventTypes: Array.isArray(body.availableEventTypes)
        ? body.availableEventTypes
        : [],
      warnings: Array.isArray(body.warnings) ? body.warnings : [],
      aiUsed: Boolean(body.aiUsed),
      informationalOnly: body.informationalOnly !== false,
      causalityDisclaimer: body.causalityDisclaimer !== false,
    };
  },
  async getDailyBrief(): Promise<MarketDailyBriefResponse> {
    const response = await apiClient.get('/api/v1/market-workspace/daily-brief');
    const body = toCamelCase<MarketDailyBriefResponse>(response.data);
    return {
      ...body,
      items: Array.isArray(body.items) ? body.items : [],
      warnings: Array.isArray(body.warnings) ? body.warnings : [],
    };
  },
};
