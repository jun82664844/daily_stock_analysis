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
  indicators: Record<string, unknown>;
  route?: {
    inputCode?: string | null;
    normalizedCode: string;
    market: string;
    channel: string;
    dataSourceLane: string;
    quoteSources?: string[];
    historySources?: string[];
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
    const query = options?.refresh ? '?refresh=true' : '';
    const response = await apiClient.get<Record<string, unknown>>(
      `/api/v1/stocks/${encodeURIComponent(code)}/snapshot${query}`,
    );
    return toCamelCase<BasicStockSnapshot>(response.data);
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
