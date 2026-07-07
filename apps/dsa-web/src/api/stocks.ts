import apiClient from './index';
import { toCamelCase } from './utils';

export type ExtractItem = {
  code?: string | null;
  name?: string | null;
  confidence: string;
};

export type ExtractFromImageResponse = {
  codes: string[];
  items?: ExtractItem[];
  rawText?: string;
};

export type BasicStockSnapshot = {
  stockCode: string;
  stockName?: string | null;
  market: string;
  quote: {
    currentPrice?: number | null;
    change?: number | null;
    changePercent?: number | null;
    open?: number | null;
    high?: number | null;
    low?: number | null;
    prevClose?: number | null;
    volume?: number | null;
    amount?: number | null;
    updateTime?: string | null;
    source: string;
    freshness: string;
  };
  profile?: {
    companyName?: string | null;
    sector?: string | null;
    industry?: string | null;
    exchange?: string | null;
    currency?: string | null;
    country?: string | null;
    website?: string | null;
    marketCap?: number | null;
    peRatio?: number | null;
    pbRatio?: number | null;
    dividendYield?: number | null;
    revenue?: number | null;
    netProfit?: number | null;
    revenueGrowth?: number | null;
    earningsGrowth?: number | null;
    source: string;
    freshness: string;
  } | null;
  indicators: Record<string, unknown>;
  trend?: {
    window: number;
    source: string;
    points: Array<{
      date?: string | null;
      close: number;
      volume?: number | null;
    }>;
    minClose?: number | null;
    maxClose?: number | null;
    changePercent?: number | null;
  } | null;
  intelligence?: {
    mode: string;
    aiUsed: boolean;
    boundary?: string | null;
    marketBrief?: {
      market: string;
      title: string;
      summary: string;
      lane: string;
      focusPoints: string[];
      deepUnlock: string;
    } | null;
    freeInsights?: Array<{
      category: string;
      title: string;
      summary: string;
      tone: string;
      bullets: string[];
      source: string;
    }>;
    peerComparison?: {
      title: string;
      summary: string;
      rows: Array<{
        symbol: string;
        label: string;
        role: string;
        reason: string;
        currentSignal: string;
        compareNext: string;
        source: string;
      }>;
    } | null;
    signalScore?: {
      score: number;
      label: string;
      summary: string;
      components: Array<{
        key: string;
        label: string;
        score: number;
        status: string;
        detail: string;
      }>;
      source: string;
      aiUsed?: boolean;
    } | null;
    retentionBrief?: {
      headline: string;
      whyItMatters: string;
      supportResistance: string;
      nextSteps: string[];
      upgradeHint: string;
      boundary: string;
      source: string;
    } | null;
    newsCenter?: {
      title: string;
      summary: string;
      items: Array<{
        category: string;
        title: string;
        summary: string;
        status: string;
        source: string;
        action: string;
        updatedAt?: string | null;
      }>;
      source: string;
      aiUsed: boolean;
      publicSearchUsed: boolean;
      premiumUnlock: string;
      boundary: string;
    } | null;
    aShareEnrichment?: {
      title: string;
      summary: string;
      status: string;
      source: string;
      sourceMode?: string;
      skill?: Record<string, unknown>;
      diagnostics?: Record<string, unknown>;
      updatedAt?: string | null;
      aiUsed: boolean;
      publicSearchUsed: boolean;
      channels: Array<{
        category: string;
        title: string;
        summary: string;
        status: string;
        source: string;
        action: string;
        updatedAt?: string | null;
      }>;
      premiumUnlock: string;
      boundary: string;
    } | null;
    klineForecast?: {
      title: string;
      horizon: string;
      direction: string;
      confidence: number;
      support?: number | null;
      resistance?: number | null;
      scenarios: Array<{
        label: string;
        direction: string;
        probability: number;
        trigger: string;
        detail: string;
      }>;
      adapterStatus: string;
      source: string;
      aiUsed: boolean;
      kronosModelUsed: boolean;
      premiumUnlock: string;
      boundary: string;
    } | null;
    items: Array<{
      category: string;
      title: string;
      summary: string;
      status: string;
      source: string;
      updatedAt?: string | null;
    }>;
    watchPoints?: Array<{
      category: string;
      title: string;
      detail: string;
      priority: string;
      source: string;
    }>;
    comparisonTargets?: Array<{
      label: string;
      symbol: string;
      reason: string;
      status: string;
      source: string;
    }>;
  } | null;
  route?: {
    inputCode?: string | null;
    normalizedCode: string;
    market: string;
    channel: string;
    dataSourceLane: string;
    quoteSources?: string[];
    historySources?: string[];
    profileSources?: string[];
    aiRequired: boolean;
  } | null;
  warnings?: Array<{
    code: string;
    severity: string;
    message: string;
  }>;
  degradation?: {
    status: string;
    severity: string;
    message: string;
  } | null;
  diagnostics?: {
    elapsedMs: number;
    quoteElapsedMs: number;
    historyElapsedMs: number;
    profileElapsedMs?: number;
    cache: Record<string, string>;
    sources: Record<string, string>;
    freshness: Record<string, string>;
    timeouts?: Record<string, boolean>;
    errors?: Record<string, string | null>;
    fallback?: Record<string, string>;
    sourceHealth?: Record<string, {
      source?: string | null;
      status?: string | null;
      consecutiveFailures?: number;
      lastError?: string | null;
      lastLatencyMs?: number | null;
      cooldownRemainingSec?: number;
    }>;
    persistentCache?: Record<string, string | number | boolean | null>;
    refresh?: Record<string, string | number | boolean | null>;
    routeLane?: string | null;
    performance: Record<string, unknown>;
  } | null;
  aiUsed: boolean;
};

export type BasicSnapshotOptions = {
  refresh?: boolean;
  aShareSourceMode?: 'poc' | 'a_stock_data' | 'off';
};

export type KronosForecastResponse = {
  stockCode: string;
  stockName?: string | null;
  market: string;
  mode: string;
  status: 'model_ready' | 'model_unavailable' | 'model_disabled' | 'model_error' | 'premium_required';
  provider: string;
  source: string;
  horizon: string;
  lookback: number;
  direction: string;
  confidence: number;
  support?: number | null;
  resistance?: number | null;
  adapterStatus: string;
  enabled: boolean;
  kronosModelUsed: boolean;
  modelId: string;
  tokenizerId: string;
  device: string;
  dependencyStatus: Record<string, boolean>;
  missingDependencies: string[];
  scenarios: Array<{
    label: string;
    direction: string;
    probability: number;
    trigger: string;
    detail: string;
  }>;
  forecastPoints: Array<{
    timestamp: string;
    open?: number | null;
    high?: number | null;
    low?: number | null;
    close?: number | null;
    volume?: number | null;
    amount?: number | null;
  }>;
  backtestSummary: {
    records: number;
    evaluated: number;
    hits: number;
    hitRate?: number | null;
    lastEvaluatedAt?: string | null;
  };
  warnings: string[];
  elapsedMs: number;
  cacheHit: boolean;
  recordId: string;
  aiUsed: boolean;
  publicSearchUsed: boolean;
  boundary: string;
};

export type KronosForecastOptions = {
  lookback?: number;
  horizon?: number;
  requireModel?: boolean;
};

export type BasicPrewarmResponse = {
  requested: number;
  warmed: number;
  degraded: number;
  symbols: string[];
  results: Record<string, unknown>;
  elapsedMs: number;
  aiUsed: boolean;
};

export type MarketSourceHealthItem = {
  source: string;
  priorityRank: number;
  status: string;
  consecutiveFailures: number;
  lastError?: string | null;
  lastLatencyMs?: number | null;
  cooldownRemainingSec: number;
};

export type MarketSourceHealthLane = {
  market: string;
  channel: string;
  routeLane: string;
  quoteSources: MarketSourceHealthItem[];
  historySources: MarketSourceHealthItem[];
};

export type MarketSourceHealthResponse = {
  mode: string;
  aiUsed: boolean;
  generatedAt?: string | null;
  cache: Record<string, string | number | boolean | null>;
  summary?: Record<string, string | number | boolean | null>;
  lanes: MarketSourceHealthLane[];
};

export type MarketSourceRecoveryRequest = {
  market?: string | null;
  sources?: string[];
  symbols?: string[];
  prewarm?: boolean;
};

export type MarketSourceRecoveryResponse = {
  mode: string;
  action: string;
  market: string;
  resetSources: string[];
  resetCount: number;
  prewarm: BasicPrewarmResponse;
  health: MarketSourceHealthResponse;
  aiUsed: boolean;
};

export const stocksApi = {
  async snapshot(code: string, options?: BasicSnapshotOptions): Promise<BasicStockSnapshot> {
    const params = new URLSearchParams();
    if (options?.refresh) params.set('refresh', 'true');
    if (options?.aShareSourceMode && options.aShareSourceMode !== 'poc') {
      params.set('a_share_source_mode', options.aShareSourceMode);
    }
    const query = params.toString() ? `?${params.toString()}` : '';
    const response = await apiClient.get<Record<string, unknown>>(
      `/api/v1/stocks/${encodeURIComponent(code)}/snapshot${query}`,
    );
    return toCamelCase<BasicStockSnapshot>(response.data);
  },

  async kronosForecast(code: string, options?: KronosForecastOptions): Promise<KronosForecastResponse> {
    const params = new URLSearchParams();
    if (options?.lookback) params.set('lookback', String(options.lookback));
    if (options?.horizon) params.set('horizon', String(options.horizon));
    if (options?.requireModel) params.set('require_model', 'true');
    const query = params.toString() ? `?${params.toString()}` : '';
    const response = await apiClient.get<Record<string, unknown>>(
      `/api/v1/stocks/${encodeURIComponent(code)}/kronos-forecast${query}`,
    );
    return toCamelCase<KronosForecastResponse>(response.data);
  },

  async prewarm(symbols: string[]): Promise<BasicPrewarmResponse> {
    const response = await apiClient.post<Record<string, unknown>>('/api/v1/stocks/prewarm', { symbols });
    return toCamelCase<BasicPrewarmResponse>(response.data);
  },

  async marketSourceHealth(): Promise<MarketSourceHealthResponse> {
    const response = await apiClient.get<Record<string, unknown>>('/api/v1/stocks/sources/health');
    return toCamelCase<MarketSourceHealthResponse>(response.data);
  },

  async recoverMarketSources(payload: MarketSourceRecoveryRequest): Promise<MarketSourceRecoveryResponse> {
    const response = await apiClient.post<Record<string, unknown>>('/api/v1/stocks/sources/recovery', payload);
    return toCamelCase<MarketSourceRecoveryResponse>(response.data);
  },

  async extractFromImage(file: File): Promise<ExtractFromImageResponse> {
    const formData = new FormData();
    formData.append('file', file);

    const headers: { [key: string]: string | undefined } = { 'Content-Type': undefined };
    const response = await apiClient.post(
      '/api/v1/stocks/extract-from-image',
      formData,
      {
        headers,
        timeout: 60000, // Vision API can be slow; 60s
      },
    );

    const data = response.data as { codes?: string[]; items?: ExtractItem[]; raw_text?: string };
    return {
      codes: data.codes ?? [],
      items: data.items,
      rawText: data.raw_text,
    };
  },

  async parseImport(file?: File, text?: string): Promise<ExtractFromImageResponse> {
    if (file) {
      const formData = new FormData();
      formData.append('file', file);
      const headers: { [key: string]: string | undefined } = { 'Content-Type': undefined };
      const response = await apiClient.post('/api/v1/stocks/parse-import', formData, { headers });
      const data = response.data as { codes?: string[]; items?: ExtractItem[] };
      return { codes: data.codes ?? [], items: data.items };
    }
    if (text) {
      const response = await apiClient.post('/api/v1/stocks/parse-import', { text });
      const data = response.data as { codes?: string[]; items?: ExtractItem[] };
      return { codes: data.codes ?? [], items: data.items };
    }
    throw new Error('请提供文件或粘贴文本');
  },
};
