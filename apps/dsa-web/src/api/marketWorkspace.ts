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
  sourceState: DataSourceState;
};

export type MarketHeadline = {
  title: string;
  summary?: string | null;
  publisher?: string | null;
  publishedAt?: string | null;
  url?: string | null;
  sourceState: DataSourceState;
};

export type MarketWorkspaceOverview = {
  market: MarketCode;
  asOf: string;
  sessionState: 'open' | 'closed' | 'unknown';
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
  displayMode: 'latest_available' | 'delayed' | 'realtime';
  rankingScope: 'configured_universe' | 'market_wide';
  selectionBasis: string;
  indices: MarketSecurityItem[];
  attention: MarketSecurityItem[];
  headlines?: MarketHeadline[];
  sources: DataSourceState[];
  warnings: string[];
};

export type PublicMarketHomeResponse = {
  asOf: string;
  markets: PublicMarketHomeSection[];
  aiUsed: boolean;
  informationalOnly: boolean;
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

export const marketWorkspaceApi = {
  async getHome(): Promise<PublicMarketHomeResponse> {
    const response = await apiClient.get('/api/v1/market-workspace/home');
    const body = toCamelCase<PublicMarketHomeResponse>(response.data);
    return {
      ...body,
      markets: Array.isArray(body.markets) ? body.markets.map((market) => ({
        ...market,
        indices: Array.isArray(market.indices) ? market.indices : [],
        attention: Array.isArray(market.attention) ? market.attention : [],
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
      breadth: body.breadth ?? { advancers: 0, decliners: 0, unchanged: 0, unavailable: true },
      indices: Array.isArray(body.indices) ? body.indices : [],
      movers: Array.isArray(body.movers) ? body.movers : [],
      heatmap: Array.isArray(body.heatmap) ? body.heatmap : [],
      headlines: Array.isArray(body.headlines) ? body.headlines : [],
      sources: Array.isArray(body.sources) ? body.sources : [],
      warnings: Array.isArray(body.warnings) ? body.warnings : [],
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
