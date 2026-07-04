import apiClient from './index';
import { toCamelCase } from './utils';
import type {
  HistoryListResponse,
  HistoryItem,
  HistoryFilters,
  AnalysisReport,
  NewsIntelResponse,
  NewsIntelItem,
  RunDiagnosticSummary,
  StockBarResponse,
  HistoryExportFormat,
  HistoryExportResponse,
  HistoryStateUpdatePayload,
  HistoryStateUpdateResponse,
  HistoryBatchStateResponse,
} from '../types/analysis';
import type { RunFlowSnapshot } from '../types/runFlow';

// ============ API 接口 ============

export interface GetHistoryListParams extends HistoryFilters {
  page?: number;
  limit?: number;
}

export interface MarkCurrentQuoteRefreshedPayload {
  stockCode?: string;
  routeLane?: string | null;
  quoteSource?: string | null;
  freshness?: string | null;
  aiUsed?: boolean;
  metadata?: Record<string, unknown>;
}

export interface MarkCurrentQuoteRefreshedResponse {
  recordId: number;
  stockCode: string;
  currentQuoteRefreshed: boolean;
  currentQuoteRefreshedAt?: string | null;
  aiUsed: boolean;
  routeLane?: string | null;
  quoteSource?: string | null;
  freshness?: string | null;
}

export const historyApi = {
  /**
   * 获取历史分析列表
   * @param params 筛选和分页参数
   */
  getList: async (params: GetHistoryListParams = {}): Promise<HistoryListResponse> => {
    const {
      stockCode,
      noteSearch,
      reportType,
      startDate,
      endDate,
      market,
      refreshStatus,
      state,
      sort,
      page = 1,
      limit = 20,
    } = params;

    const queryParams: Record<string, string | number> = { page, limit };
    if (stockCode) queryParams.stock_code = stockCode;
    if (noteSearch) queryParams.note_search = noteSearch;
    if (reportType) queryParams.report_type = reportType;
    if (startDate) queryParams.start_date = startDate;
    if (endDate) queryParams.end_date = endDate;
    if (market) queryParams.market = market;
    if (refreshStatus) queryParams.refresh_status = refreshStatus;
    if (state) queryParams.state = state;
    if (sort) queryParams.sort = sort;

    const response = await apiClient.get<Record<string, unknown>>('/api/v1/history', {
      params: queryParams,
    });

    const data = toCamelCase<{ total: number; page: number; limit: number; items: HistoryItem[] }>(response.data);
    return {
      total: data.total,
      page: data.page,
      limit: data.limit,
      items: data.items.map(item => toCamelCase<HistoryItem>(item)),
    };
  },

  markCurrentQuoteRefreshed: async (
    recordId: number,
    payload: MarkCurrentQuoteRefreshedPayload,
  ): Promise<MarkCurrentQuoteRefreshedResponse> => {
    const response = await apiClient.post<Record<string, unknown>>(`/api/v1/history/${recordId}/refresh-marker`, {
      stock_code: payload.stockCode,
      route_lane: payload.routeLane ?? undefined,
      quote_source: payload.quoteSource ?? undefined,
      freshness: payload.freshness ?? undefined,
      ai_used: payload.aiUsed ?? false,
      metadata: payload.metadata ?? {},
    });
    return toCamelCase<MarkCurrentQuoteRefreshedResponse>(response.data);
  },

  /**
   * 获取历史报告详情
   * @param recordId 分析历史记录主键 ID（使用 ID 而非 query_id，因为 query_id 在批量分析时可能重复）
   */
  getDetail: async (recordId: number): Promise<AnalysisReport> => {
    const response = await apiClient.get<Record<string, unknown>>(`/api/v1/history/${recordId}`);
    return toCamelCase<AnalysisReport>(response.data);
  },

  /**
   * 获取历史报告关联新闻
   * @param recordId 分析历史记录主键 ID
   * @param limit 返回数量限制
   */
  getNews: async (recordId: number, limit = 20): Promise<NewsIntelResponse> => {
    const response = await apiClient.get<Record<string, unknown>>(`/api/v1/history/${recordId}/news`, {
      params: { limit },
    });

    const data = toCamelCase<NewsIntelResponse>(response.data);
    return {
      total: data.total,
      items: (data.items || []).map(item => toCamelCase<NewsIntelItem>(item)),
    };
  },

  /**
   * 获取历史报告的 Markdown 格式内容
   * @param recordId 分析历史记录主键 ID
   * @returns Markdown 格式的完整报告内容
   */
  getMarkdown: async (recordId: number): Promise<string> => {
    const response = await apiClient.get<{ content: string }>(`/api/v1/history/${recordId}/markdown`);
    return response.data.content;
  },

  exportReports: async (
    recordIds: number[],
    format: HistoryExportFormat = 'markdown',
  ): Promise<HistoryExportResponse> => {
    const response = await apiClient.post<Record<string, unknown>>('/api/v1/history/export', {
      record_ids: recordIds,
      format,
    });
    return toCamelCase<HistoryExportResponse>(response.data);
  },

  updateState: async (
    recordId: number,
    payload: HistoryStateUpdatePayload,
  ): Promise<HistoryStateUpdateResponse> => {
    const response = await apiClient.patch<Record<string, unknown>>(`/api/v1/history/${recordId}/state`, {
      favorite: payload.favorite,
      important: payload.important,
      archived: payload.archived,
      read: payload.read,
      note: payload.note,
      ai_used: false,
    });
    return toCamelCase<HistoryStateUpdateResponse>(response.data);
  },

  batchUpdateState: async (
    recordIds: number[],
    payload: Omit<HistoryStateUpdatePayload, 'note'>,
  ): Promise<HistoryBatchStateResponse> => {
    const response = await apiClient.patch<Record<string, unknown>>('/api/v1/history/state', {
      record_ids: recordIds,
      favorite: payload.favorite,
      important: payload.important,
      archived: payload.archived,
      read: payload.read,
      ai_used: false,
    });
    return toCamelCase<HistoryBatchStateResponse>(response.data);
  },

  /**
   * 获取历史报告运行诊断摘要
   * @param recordId 分析历史记录主键 ID
   */
  getDiagnostics: async (recordId: number): Promise<RunDiagnosticSummary> => {
    const response = await apiClient.get<Record<string, unknown>>(`/api/v1/history/${recordId}/diagnostics`);
    return toCamelCase<RunDiagnosticSummary>(response.data);
  },

  /**
   * 获取历史报告运行流快照
   * @param recordId 分析历史记录主键 ID
   */
  getRecordFlow: async (recordId: number): Promise<RunFlowSnapshot> => {
    const response = await apiClient.get<Record<string, unknown>>(`/api/v1/history/${recordId}/flow`);
    return toCamelCase<RunFlowSnapshot>(response.data);
  },

  /**
   * 批量删除历史记录
   * @param recordIds 分析历史记录主键 ID 列表
   */
  deleteRecords: async (recordIds: number[]): Promise<{ deleted: number }> => {
    const response = await apiClient.delete<Record<string, unknown>>('/api/v1/history', {
      data: { record_ids: recordIds },
    });

    return toCamelCase<{ deleted: number }>(response.data);
  },

  /**
   * 按股票代码删除所有历史记录
   * @param stockCode 股票代码
   */
  deleteByCode: async (stockCode: string): Promise<{ deleted: number }> => {
    const response = await apiClient.delete<Record<string, unknown>>(`/api/v1/history/by-code/${encodeURIComponent(stockCode)}`);
    return toCamelCase<{ deleted: number }>(response.data);
  },

  /**
   * 获取个股栏列表（不重复个股，不包含大盘复盘）
   */
  getStockBarList: async (params: {
    startDate?: string;
    endDate?: string;
    limit?: number;
  } = {}): Promise<StockBarResponse> => {
    const queryParams: Record<string, string | number> = {};
    if (params.startDate) queryParams.start_date = params.startDate;
    if (params.endDate) queryParams.end_date = params.endDate;
    if (params.limit) queryParams.limit = params.limit;

    const response = await apiClient.get<Record<string, unknown>>('/api/v1/history/stocks', {
      params: queryParams,
    });

    const data = toCamelCase<{ total: number; items: unknown[] }>(response.data);
    return {
      total: data.total,
      items: data.items.map(item => toCamelCase<Record<string, unknown>>(item) as unknown as typeof data.items[0]),
    } as StockBarResponse;
  },
};
