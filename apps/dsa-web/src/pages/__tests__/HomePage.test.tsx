import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { analysisApi, DuplicateTaskError } from '../../api/analysis';
import { agentApi } from '../../api/agent';
import { historyApi } from '../../api/history';
import { platformApi } from '../../api/platform';
import { stocksApi } from '../../api/stocks';
import { systemConfigApi } from '../../api/systemConfig';
import { UiLanguageProvider } from '../../contexts/UiLanguageContext';
import { useStockPoolStore } from '../../stores';
import type { RunFlowSnapshot } from '../../types/runFlow';
import { getReportText, normalizeReportLanguage } from '../../utils/reportLanguage';
import { UI_LANGUAGE_STORAGE_KEY } from '../../utils/uiLanguage';
import HomePage from '../HomePage';

const navigateMock = vi.fn();

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom');
  return {
    ...actual,
    useNavigate: () => navigateMock,
  };
});

vi.mock('../../api/history', () => ({
  historyApi: {
    getList: vi.fn(),
    getDetail: vi.fn(),
    getNews: vi.fn().mockResolvedValue({ total: 0, items: [] }),
    getMarkdown: vi.fn().mockResolvedValue('# report'),
    getDiagnostics: vi.fn(),
    getRecordFlow: vi.fn(),
    getStockBarList: vi.fn().mockResolvedValue({ total: 0, items: [] }),
    markCurrentQuoteRefreshed: vi.fn(),
    exportReports: vi.fn(),
    updateState: vi.fn(),
    batchUpdateState: vi.fn(),
    deleteByCode: vi.fn(),
  },
}));

vi.mock('../../api/analysis', async () => {
  const actual = await vi.importActual<typeof import('../../api/analysis')>('../../api/analysis');
  return {
    ...actual,
    analysisApi: {
      analyzeAsync: vi.fn(),
      triggerMarketReview: vi.fn(),
      getStatus: vi.fn(),
      getTasks: vi.fn(),
      getTaskFlow: vi.fn(),
    },
  };
});

vi.mock('../../api/systemConfig', () => ({
  systemConfigApi: {
    getSetupStatus: vi.fn(),
    getWatchlist: vi.fn().mockResolvedValue([]),
  },
}));

vi.mock('../../api/stocks', () => ({
  stocksApi: {
    extractFromImage: vi.fn(),
    parseImport: vi.fn(),
    prewarm: vi.fn(),
    snapshot: vi.fn(),
  },
}));

vi.mock('../../api/agent', () => ({
  agentApi: {
    getSkills: vi.fn(),
  },
}));

vi.mock('../../api/platform', () => ({
  PLATFORM_SESSION_CHANGED_EVENT: 'dsa-platform-session-changed',
  platformApi: {
    status: vi.fn(),
    current: vi.fn(),
    account: vi.fn(),
    listApiKeys: vi.fn(),
    register: vi.fn(),
    login: vi.fn(),
    logout: vi.fn(),
    saveApiKey: vi.fn(),
    watchlist: vi.fn(),
    addWatchlistItem: vi.fn(),
    removeWatchlistItem: vi.fn(),
    refreshWatchlist: vi.fn(),
  },
}));

vi.mock('../../hooks/useTaskStream', () => ({
  useTaskStream: vi.fn(),
}));

const historyItem = {
  id: 1,
  queryId: 'q-1',
  stockCode: '600519',
  stockName: '贵州茅台',
  sentimentScore: 82,
  operationAdvice: '买入',
  createdAt: '2026-03-18T08:00:00Z',
};

const historyReport = {
  meta: {
    id: 1,
    queryId: 'q-1',
    stockCode: '600519',
    stockName: '贵州茅台',
    reportType: 'detailed' as const,
    reportLanguage: 'zh' as const,
    createdAt: '2026-03-18T08:00:00Z',
  },
  summary: {
    analysisSummary: '趋势维持强势',
    operationAdvice: '继续观察买点',
    trendPrediction: '短线震荡偏强',
    sentimentScore: 78,
  },
};

const marketReviewHistoryItem = {
  id: 2,
  queryId: 'market-review-q-1',
  stockCode: 'MARKET',
  stockName: '大盘复盘',
  reportType: 'market_review' as const,
  createdAt: '2026-03-18T08:00:00Z',
};

const marketReviewHistoryReport = {
  meta: {
    id: 2,
    queryId: 'market-review-q-1',
    stockCode: 'MARKET',
    stockName: '大盘复盘',
    reportType: 'market_review' as const,
    reportLanguage: 'zh' as const,
    createdAt: '2026-03-18T08:00:00Z',
  },
  summary: {
    analysisSummary: '大盘复盘摘要',
    operationAdvice: '查看复盘',
    trendPrediction: '大盘复盘',
    sentimentScore: 50,
  },
};

const runFlowSnapshot: RunFlowSnapshot = {
  taskId: 'task-1',
  traceId: 'trace-1',
  stockCode: '600519',
  stockName: '贵州茅台',
  status: 'running',
  generatedAt: '2026-06-08T08:00:00Z',
  summary: {
    elapsedMs: 1200,
    failedAttempts: 0,
    fallbackCount: 0,
    dataSourceCount: 1,
    eventCount: 1,
  },
  lanes: [
    { id: 'entry', label: '入口', order: 1 },
    { id: 'analysis', label: '分析引擎', order: 2 },
  ],
  nodes: [
    {
      id: 'request',
      lane: 'entry',
      kind: 'entry',
      label: '用户请求',
      status: 'success',
    },
    {
      id: 'analysis',
      lane: 'analysis',
      kind: 'analysis',
      label: '分析流程',
      status: 'running',
    },
  ],
  edges: [
    {
      id: 'request-analysis',
      from: 'request',
      to: 'analysis',
      kind: 'control',
      status: 'running',
      label: '调度',
    },
  ],
  events: [
    {
      id: 'evt-1',
      timestamp: '2026-06-08T08:00:00Z',
      severity: 'info',
      type: 'task_started',
      nodeId: 'analysis',
      title: '任务开始',
    },
  ],
};

describe('HomePage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    navigateMock.mockReset();
    window.localStorage.clear();
    useStockPoolStore.getState().resetDashboardState();
    vi.mocked(analysisApi.getTasks).mockResolvedValue({
      total: 0,
      pending: 0,
      processing: 0,
      tasks: [],
    });
    vi.mocked(agentApi.getSkills).mockResolvedValue({ skills: [], default_skill_id: '' });
    vi.mocked(platformApi.status).mockResolvedValue({ platformAuthEnabled: false });
    vi.mocked(platformApi.current).mockResolvedValue(null);
    vi.mocked(platformApi.account).mockRejectedValue(new Error('not signed in'));
    vi.mocked(platformApi.listApiKeys).mockResolvedValue([]);
    vi.mocked(platformApi.logout).mockResolvedValue(undefined);
    vi.mocked(platformApi.saveApiKey).mockResolvedValue({
      provider: 'deepseek',
      model: 'deepseek/deepseek-v4-flash',
      maskedKey: 'sk-...test',
      enabled: true,
    });
    vi.mocked(platformApi.watchlist).mockResolvedValue({ userId: 0, items: [], total: 0, aiUsed: false });
    vi.mocked(platformApi.addWatchlistItem).mockResolvedValue({ userId: 0, items: [], total: 0, aiUsed: false });
    vi.mocked(platformApi.removeWatchlistItem).mockResolvedValue({ userId: 0, items: [], total: 0, aiUsed: false });
    vi.mocked(platformApi.refreshWatchlist).mockResolvedValue({
      userId: 0,
      requested: 0,
      refreshed: 0,
      degraded: 0,
      items: [],
      aiUsed: false,
    });
    vi.mocked(historyApi.getDiagnostics).mockResolvedValue({
      status: 'unknown',
      statusLabel: '未知',
      reason: '旧报告或诊断证据不足，无法判断本次运行状态',
      components: {},
      copyText: 'data_status: unknown',
    });
    vi.mocked(historyApi.getRecordFlow).mockResolvedValue(runFlowSnapshot);
    vi.mocked(historyApi.markCurrentQuoteRefreshed).mockResolvedValue({
      recordId: 0,
      stockCode: 'AAPL',
      currentQuoteRefreshed: true,
      currentQuoteRefreshedAt: '2026-07-03T09:30:00',
      aiUsed: false,
      routeLane: 'us_market_data',
      quoteSource: 'yahoo_chart',
      freshness: 'fresh',
    });
    vi.mocked(historyApi.exportReports).mockResolvedValue({
      format: 'markdown',
      filename: 'dsa-history-export-test.md',
      content: '# DSA History Export\n\nAAPL informational report',
      recordCount: 1,
      recordIds: [1],
      aiUsed: false,
    });
    vi.mocked(historyApi.updateState).mockResolvedValue({
      recordId: 1,
      favorite: true,
      important: false,
      archived: false,
      read: false,
      note: 'local note',
      noteUpdatedAt: '2026-07-04T08:00:00Z',
      aiUsed: false,
    });
    vi.mocked(historyApi.batchUpdateState).mockResolvedValue({
      updated: 1,
      recordIds: [1],
      aiUsed: false,
    });
    vi.mocked(analysisApi.getTaskFlow).mockResolvedValue(runFlowSnapshot);
    vi.mocked(stocksApi.prewarm).mockResolvedValue({
      requested: 4,
      warmed: 0,
      degraded: 4,
      symbols: ['600519', 'AAPL', 'HK00700', 'BTC-USD'],
      results: {},
      elapsedMs: 1,
      aiUsed: false,
    });
    vi.mocked(systemConfigApi.getSetupStatus).mockResolvedValue({
      isComplete: true,
      readyForSmoke: true,
      requiredMissingKeys: [],
      nextStepKey: null,
      checks: [],
    });
  });

  it('renders the dashboard workspace and auto-loads the first report', async () => {
    vi.mocked(historyApi.getList).mockResolvedValue({
      total: 1,
      page: 1,
      limit: 20,
      items: [historyItem],
    });
    vi.mocked(historyApi.getDetail).mockResolvedValue(historyReport);
    vi.mocked(analysisApi.analyzeAsync).mockResolvedValue({
      taskId: 'task-1',
      status: 'pending',
    });

    render(
      <MemoryRouter>
        <HomePage />
      </MemoryRouter>,
    );

    const dashboard = await screen.findByTestId('home-dashboard');
    expect(dashboard).toBeInTheDocument();
    expect(dashboard.className).toContain('h-[calc(100vh-5rem)]');
    expect(dashboard.className).toContain('lg:h-[calc(100vh-2rem)]');
    expect(dashboard.firstElementChild?.className).toContain('min-h-0');
    expect(dashboard.querySelector('.flex-1.flex.min-h-0.overflow-hidden')).toBeTruthy();
    expect(screen.getByTestId('home-dashboard-scroll')).toBeInTheDocument();
    expect(screen.getByPlaceholderText('输入股票代码或名称，如 600519、贵州茅台、AAPL')).toBeInTheDocument();
    expect(await screen.findByText('趋势维持强势')).toBeInTheDocument();
    expect(
      screen.getByRole('button', {
        name: getReportText(normalizeReportLanguage(historyReport.meta.reportLanguage)).fullReport,
      }),
    ).toBeInTheDocument();
    expect(historyApi.getMarkdown).not.toHaveBeenCalled();
  });

  it('loads markdown only after opening the full report drawer', async () => {
    vi.mocked(historyApi.getList).mockResolvedValue({
      total: 1,
      page: 1,
      limit: 20,
      items: [historyItem],
    });
    vi.mocked(historyApi.getDetail).mockResolvedValue(historyReport);
    vi.mocked(historyApi.getMarkdown).mockResolvedValue('# Full Markdown Report');

    render(
      <MemoryRouter>
        <HomePage />
      </MemoryRouter>,
    );

    const fullReportButton = await screen.findByRole('button', {
      name: getReportText(normalizeReportLanguage(historyReport.meta.reportLanguage)).fullReport,
    });
    expect(historyApi.getMarkdown).not.toHaveBeenCalled();

    fireEvent.click(fullReportButton);

    await waitFor(() => {
      expect(historyApi.getMarkdown).toHaveBeenCalledWith(historyReport.meta.id);
    });
    expect(await screen.findByRole('heading', { name: 'Full Markdown Report' })).toBeInTheDocument();
  });

  it('marks historical reports as separate from current quotes and refreshes a no-AI snapshot', async () => {
    vi.mocked(historyApi.getList).mockResolvedValue({
      total: 1,
      page: 1,
      limit: 20,
      items: [historyItem],
    });
    vi.mocked(historyApi.getDetail).mockResolvedValue(historyReport);
    vi.mocked(stocksApi.snapshot).mockResolvedValue({
      stockCode: '600519',
      stockName: '贵州茅台',
      market: 'cn',
      quote: {
        currentPrice: 1688,
        changePercent: 0.8,
        source: 'a_share_realtime',
        freshness: 'fresh',
      },
      indicators: { ma5: 1650, ma20: 1600 },
      diagnostics: {
        elapsedMs: 25,
        quoteElapsedMs: 10,
        historyElapsedMs: 15,
        cache: { quote: 'refresh', history: 'refresh' },
        sources: { quote: 'a_share_realtime', history: 'a_share_history' },
        freshness: { quote: 'fresh', history: 'fresh' },
        fallback: { quote: 'live', history: 'live' },
        persistentCache: { quote: 'none', history: 'none', mode: 'local_json' },
        refresh: { mode: 'force_refresh', requested: true, quote: true, history: true },
        routeLane: 'a_share_market_data',
        performance: { status: 'ok', slowThresholdMs: 3000 },
      },
      aiUsed: false,
    });
    vi.mocked(analysisApi.analyzeAsync).mockRejectedValue(new Error('AI should not run when refreshing current quote from history'));

    render(
      <MemoryRouter>
        <HomePage />
      </MemoryRouter>,
    );

    const boundary = await screen.findByTestId('history-report-freshness-boundary');
    expect(boundary).toHaveTextContent('Historical AI report');
    expect(boundary).toHaveTextContent('not current quote');
    expect(screen.queryByTestId('basic-query-snapshot')).not.toBeInTheDocument();

    fireEvent.click(screen.getByTestId('history-report-refresh-current'));

    await waitFor(() => {
      expect(stocksApi.snapshot).toHaveBeenCalledWith('600519', { refresh: true });
    });
    expect(analysisApi.analyzeAsync).not.toHaveBeenCalled();
    expect(await screen.findByTestId('basic-query-snapshot')).toHaveTextContent('1,688');
    expect(screen.getByTestId('basic-query-diagnostics')).toHaveTextContent('force_refresh');
    expect(screen.queryByTestId('history-report-freshness-boundary')).not.toBeInTheDocument();
  });

  it('filters the history center and marks reports refreshed after a current quote refresh', async () => {
    const aaplHistoryItem = {
      ...historyItem,
      id: 3,
      queryId: 'q-aapl',
      stockCode: 'AAPL',
      stockName: 'Apple',
      reportType: 'simple' as const,
      createdAt: '2026-07-03T08:00:00Z',
    };
    const btcHistoryItem = {
      ...historyItem,
      id: 4,
      queryId: 'q-btc',
      stockCode: 'BTC-USD',
      stockName: 'Bitcoin',
      reportType: 'brief' as const,
      createdAt: '2026-07-02T08:00:00Z',
    };
    const hkHistoryItem = {
      ...historyItem,
      id: 5,
      queryId: 'q-hk',
      stockCode: 'HK00700',
      stockName: 'Tencent',
      reportType: 'full' as const,
      createdAt: '2026-07-01T08:00:00Z',
    };
    const aaplReport = {
      ...historyReport,
      meta: {
        ...historyReport.meta,
        id: 3,
        queryId: 'q-aapl',
        stockCode: 'AAPL',
        stockName: 'Apple',
        reportType: 'simple' as const,
        createdAt: '2026-07-03T08:00:00Z',
      },
      summary: {
        ...historyReport.summary,
        analysisSummary: 'Apple historical report',
      },
    };

    vi.mocked(historyApi.getList).mockImplementation((params: {
      reportType?: string;
      market?: string;
      stockCode?: string;
      refreshStatus?: string;
    } = {}) => {
      if (params.reportType === 'market_review') {
        return Promise.resolve({
          total: 0,
          page: 1,
          limit: 10,
          items: [],
        });
      }
      let items = [
        { ...historyItem, reportType: 'detailed' as const, createdAt: '2026-07-03T09:00:00Z' },
        aaplHistoryItem,
        btcHistoryItem,
        hkHistoryItem,
      ];
      if (params.market === 'us') {
        items = items.filter((item) => item.stockCode === 'AAPL');
      }
      if (params.stockCode) {
        const needle = params.stockCode.toUpperCase();
        items = items.filter((item) => `${item.stockCode} ${item.stockName ?? ''}`.toUpperCase().includes(needle));
      }
      if (params.refreshStatus === 'refreshed') {
        items = items.filter((item) => item.id === 3);
      }
      if (params.refreshStatus === 'not_refreshed') {
        items = items.filter((item) => item.id !== 3);
      }
      return Promise.resolve({
        total: items.length,
        page: 1,
        limit: 20,
        items,
      });
    });
    vi.mocked(historyApi.getDetail).mockImplementation((recordId: number) => (
      Promise.resolve(recordId === 3 ? aaplReport : historyReport)
    ));
    vi.mocked(stocksApi.snapshot).mockResolvedValue({
      stockCode: 'AAPL',
      stockName: 'Apple',
      market: 'us',
      quote: {
        currentPrice: 211.34,
        changePercent: 1.2,
        source: 'yahoo_chart',
        freshness: 'fresh',
      },
      indicators: { ma5: 205, ma20: 198 },
      diagnostics: {
        elapsedMs: 20,
        quoteElapsedMs: 10,
        historyElapsedMs: 10,
        cache: { quote: 'refresh', history: 'refresh' },
        sources: { quote: 'yahoo_chart', history: 'yahoo_chart' },
        freshness: { quote: 'fresh', history: 'fresh' },
        fallback: { quote: 'live', history: 'live' },
        persistentCache: { quote: 'none', history: 'none', mode: 'local_json' },
        refresh: { mode: 'force_refresh', requested: true, quote: true, history: true },
        routeLane: 'us_market_data',
        performance: { status: 'ok', slowThresholdMs: 3000 },
      },
      aiUsed: false,
    });

    render(
      <MemoryRouter>
        <HomePage />
      </MemoryRouter>,
    );

    expect(await screen.findByTestId('history-center-filters')).toBeInTheDocument();
    expect(await screen.findByTestId('history-center-item-3')).toHaveTextContent('AAPL');
    expect(screen.getByTestId('history-center-item-4')).toHaveTextContent('BTC-USD');
    expect(screen.getByTestId('history-card-refresh-status-3')).toHaveTextContent('Not refreshed');

    fireEvent.change(screen.getByTestId('history-center-market-filter'), { target: { value: 'us' } });

    await waitFor(() => {
      expect(historyApi.getList).toHaveBeenCalledWith(expect.objectContaining({
        market: 'us',
        sort: 'newest',
      }));
    });
    await waitFor(() => {
      expect(screen.getByTestId('history-center-item-3')).toBeInTheDocument();
      expect(screen.queryByTestId('history-center-item-1')).not.toBeInTheDocument();
      expect(screen.queryByTestId('history-center-item-4')).not.toBeInTheDocument();
    });

    fireEvent.change(screen.getByTestId('history-center-code-filter'), { target: { value: 'AAP' } });
    await waitFor(() => {
      expect(historyApi.getList).toHaveBeenCalledWith(expect.objectContaining({
        market: 'us',
        stockCode: 'AAP',
      }));
    });
    expect(screen.getByTestId('history-center-item-3')).toHaveTextContent('Apple');

    fireEvent.click(screen.getByTestId('history-center-item-3'));

    await waitFor(() => {
      expect(historyApi.getDetail).toHaveBeenCalledWith(3);
    });
    fireEvent.click(await screen.findByTestId('history-report-refresh-current'));

    await waitFor(() => {
      expect(stocksApi.snapshot).toHaveBeenCalledWith('AAPL', { refresh: true });
    });
    expect(historyApi.markCurrentQuoteRefreshed).toHaveBeenCalledWith(3, expect.objectContaining({
      stockCode: 'AAPL',
      routeLane: 'us_market_data',
      quoteSource: 'yahoo_chart',
      freshness: 'fresh',
      aiUsed: false,
    }));
    expect(analysisApi.analyzeAsync).not.toHaveBeenCalled();
    expect(screen.getByTestId('history-card-refresh-status-3')).toHaveTextContent('Current quote refreshed');

    fireEvent.change(screen.getByTestId('history-center-refresh-filter'), { target: { value: 'refreshed' } });
    await waitFor(() => {
      expect(historyApi.getList).toHaveBeenCalledWith(expect.objectContaining({
        market: 'us',
        stockCode: 'AAP',
        refreshStatus: 'refreshed',
      }));
    });
    expect(screen.getByTestId('history-center-item-3')).toBeInTheDocument();
    expect(screen.queryByTestId('history-center-item-1')).not.toBeInTheDocument();

    fireEvent.click(screen.getByTestId('history-center-reset-filters'));
    fireEvent.change(screen.getByTestId('history-center-refresh-filter'), { target: { value: 'not_refreshed' } });
    await waitFor(() => {
      expect(screen.queryByTestId('history-center-item-3')).not.toBeInTheDocument();
      expect(screen.getByTestId('history-center-item-1')).toBeInTheDocument();
    });
  });

  it('restores history center filters from local storage and displays the backend total', async () => {
    const aaplHistoryItem = {
      ...historyItem,
      id: 6,
      queryId: 'q-aapl-restored',
      stockCode: 'AAPL',
      stockName: 'Apple',
      reportType: 'simple' as const,
      createdAt: '2026-07-03T08:00:00Z',
    };
    const aaplReport = {
      ...historyReport,
      meta: {
        ...historyReport.meta,
        id: 6,
        queryId: 'q-aapl-restored',
        stockCode: 'AAPL',
        stockName: 'Apple',
        reportType: 'simple' as const,
        createdAt: '2026-07-03T08:00:00Z',
      },
    };

    window.localStorage.setItem('dsa-history-center-filters-v1', JSON.stringify({
      market: 'us',
      reportType: 'simple',
      refreshStatus: 'refreshed',
      range: '30d',
      sort: 'oldest',
      code: 'AAP',
    }));
    vi.mocked(historyApi.getList).mockImplementation((params: { reportType?: string } = {}) => {
      if (params.reportType === 'market_review') {
        return Promise.resolve({
          total: 0,
          page: 1,
          limit: 10,
          items: [],
        });
      }
      return Promise.resolve({
        total: 12,
        page: 1,
        limit: 20,
        items: [aaplHistoryItem],
      });
    });
    vi.mocked(historyApi.getDetail).mockResolvedValue(aaplReport);

    render(
      <MemoryRouter>
        <HomePage />
      </MemoryRouter>,
    );

    expect(await screen.findByTestId('history-center-filters')).toBeInTheDocument();
    expect(screen.getByTestId('history-center-market-filter')).toHaveValue('us');
    expect(screen.getByTestId('history-center-report-type-filter')).toHaveValue('simple');
    expect(screen.getByTestId('history-center-refresh-filter')).toHaveValue('refreshed');
    expect(screen.getByTestId('history-center-range-filter')).toHaveValue('30d');
    expect(screen.getByTestId('history-center-time-filter')).toHaveValue('oldest');
    expect(screen.getByTestId('history-center-code-filter')).toHaveValue('AAP');

    await waitFor(() => {
      expect(historyApi.getList).toHaveBeenCalledWith(expect.objectContaining({
        market: 'us',
        reportType: 'simple',
        refreshStatus: 'refreshed',
        stockCode: 'AAP',
        sort: 'oldest',
        startDate: expect.any(String),
        endDate: expect.any(String),
      }));
    });
    expect(await screen.findByTestId('history-center-item-6')).toHaveTextContent('AAPL');
    expect(screen.getByTestId('history-total-count')).toHaveTextContent('12');
  });

  it('exports selected history reports as a local no-AI markdown bundle', async () => {
    const createObjectURL = vi.fn(() => 'blob:dsa-history-export-v27');
    const revokeObjectURL = vi.fn();
    const clickSpy = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => undefined);
    Object.defineProperty(URL, 'createObjectURL', {
      configurable: true,
      value: createObjectURL,
    });
    Object.defineProperty(URL, 'revokeObjectURL', {
      configurable: true,
      value: revokeObjectURL,
    });

    const aaplHistoryItem = {
      ...historyItem,
      id: 7,
      queryId: 'q-aapl-export',
      stockCode: 'AAPL',
      stockName: 'Apple',
      reportType: 'simple' as const,
      createdAt: '2026-07-03T08:00:00Z',
    };

    vi.mocked(historyApi.getList).mockImplementation((params: { reportType?: string } = {}) => {
      if (params.reportType === 'market_review') {
        return Promise.resolve({
          total: 0,
          page: 1,
          limit: 10,
          items: [],
        });
      }
      return Promise.resolve({
        total: 1,
        page: 1,
        limit: 20,
        items: [aaplHistoryItem],
      });
    });
    vi.mocked(historyApi.exportReports).mockResolvedValue({
      format: 'markdown',
      filename: 'dsa-history-export-v27.md',
      content: '# DSA History Export\n\nAAPL informational report',
      recordCount: 1,
      recordIds: [7],
      aiUsed: false,
    });

    render(
      <MemoryRouter>
        <HomePage />
      </MemoryRouter>,
    );

    expect(await screen.findByTestId('history-center-item-7')).toHaveTextContent('AAPL');
    fireEvent.click(await screen.findByRole('checkbox', { name: /全选当前已加载历史记录|Select all loaded history records/i }));
    fireEvent.click(await screen.findByTestId('history-center-export-selected'));

    await waitFor(() => {
      expect(historyApi.exportReports).toHaveBeenCalledWith([7], 'markdown');
    });
    expect(createObjectURL).toHaveBeenCalled();
    expect(clickSpy).toHaveBeenCalled();
    expect(revokeObjectURL).toHaveBeenCalledWith('blob:dsa-history-export-v27');
    expect(screen.getByTestId('history-center-export-status')).toHaveTextContent('Exported 1 local reports');
    expect(analysisApi.analyzeAsync).not.toHaveBeenCalled();
    clickSpy.mockRestore();
  });

  it('manages local history state with filters, batch archive, favorite and notes without AI', async () => {
    const aaplHistoryItem = {
      ...historyItem,
      id: 8,
      queryId: 'q-aapl-state',
      stockCode: 'AAPL',
      stockName: 'Apple',
      reportType: 'simple' as const,
      favorite: false,
      important: false,
      archived: false,
      read: false,
      note: '',
      createdAt: '2026-07-04T08:00:00Z',
    };
    const aaplReport = {
      ...historyReport,
      meta: {
        ...historyReport.meta,
        id: 8,
        queryId: 'q-aapl-state',
        stockCode: 'AAPL',
        stockName: 'Apple',
        reportType: 'simple' as const,
        createdAt: '2026-07-04T08:00:00Z',
      },
      summary: {
        ...historyReport.summary,
        analysisSummary: 'Apple state management report',
      },
    };

    vi.mocked(historyApi.getList).mockImplementation((params: { reportType?: string; state?: string } = {}) => {
      if (params.reportType === 'market_review') {
        return Promise.resolve({
          total: 0,
          page: 1,
          limit: 10,
          items: [],
        });
      }
      const item = params.state === 'favorite'
        ? { ...aaplHistoryItem, favorite: true, note: 'Watch after earnings' }
        : aaplHistoryItem;
      return Promise.resolve({
        total: 1,
        page: 1,
        limit: 20,
        items: [item],
      });
    });
    vi.mocked(historyApi.getDetail).mockResolvedValue(aaplReport);
    vi.mocked(historyApi.batchUpdateState).mockResolvedValue({
      updated: 1,
      recordIds: [8],
      aiUsed: false,
    });
    vi.mocked(historyApi.updateState).mockResolvedValue({
      recordId: 8,
      favorite: true,
      important: false,
      archived: false,
      read: false,
      note: 'Watch after earnings',
      noteUpdatedAt: '2026-07-04T08:30:00Z',
      aiUsed: false,
    });

    render(
      <MemoryRouter>
        <HomePage />
      </MemoryRouter>,
    );

    expect(await screen.findByTestId('history-center-item-8')).toHaveTextContent('AAPL');

    fireEvent.change(screen.getByTestId('history-center-state-filter'), { target: { value: 'favorite' } });
    await waitFor(() => {
      expect(historyApi.getList).toHaveBeenCalledWith(expect.objectContaining({
        state: 'favorite',
      }));
    });

    fireEvent.click(await screen.findByTestId('history-select-all-visible'));
    fireEvent.click(screen.getByTestId('history-center-archive-selected'));
    await waitFor(() => {
      expect(historyApi.batchUpdateState).toHaveBeenCalledWith([8], { archived: true });
    });
    expect(screen.getByTestId('history-center-state-status')).toHaveTextContent('Archived 1 local reports');

    fireEvent.click(screen.getByTestId('history-center-item-8'));
    await waitFor(() => {
      expect(historyApi.getDetail).toHaveBeenCalledWith(8);
    });

    fireEvent.click(await screen.findByTestId('history-state-favorite'));
    await waitFor(() => {
      expect(historyApi.updateState).toHaveBeenCalledWith(8, { favorite: false });
    });

    fireEvent.change(screen.getByTestId('history-state-note-input'), {
      target: { value: 'Watch after earnings' },
    });
    fireEvent.click(screen.getByTestId('history-state-note-save'));
    await waitFor(() => {
      expect(historyApi.updateState).toHaveBeenCalledWith(8, { note: 'Watch after earnings' });
    });
    expect(screen.getByTestId('history-state-status')).toHaveTextContent('Saved local history state');
    expect(analysisApi.analyzeAsync).not.toHaveBeenCalled();
  });

  it('enhances history center with active default, note search, date groups and batch flags without AI', async () => {
    const aaplHistoryItem = {
      ...historyItem,
      id: 10,
      queryId: 'q-aapl-v29',
      stockCode: 'AAPL',
      stockName: 'Apple',
      reportType: 'simple' as const,
      important: false,
      archived: false,
      read: false,
      note: 'Apple earnings gap monitor',
      createdAt: '2026-07-04T08:00:00Z',
    };
    const hkHistoryItem = {
      ...historyItem,
      id: 11,
      queryId: 'q-hk-v29',
      stockCode: 'HK00700',
      stockName: 'Tencent',
      reportType: 'full' as const,
      important: false,
      archived: false,
      read: false,
      note: 'Dividend watch',
      createdAt: '2026-07-03T08:00:00Z',
    };

    vi.mocked(historyApi.getList).mockImplementation((params: {
      reportType?: string;
      state?: string;
      noteSearch?: string;
    } = {}) => {
      if (params.reportType === 'market_review') {
        return Promise.resolve({
          total: 0,
          page: 1,
          limit: 10,
          items: [],
        });
      }
      let items = [aaplHistoryItem, hkHistoryItem];
      if (params.noteSearch) {
        const needle = params.noteSearch.toLowerCase();
        items = items.filter((item) => (item.note || '').toLowerCase().includes(needle));
      }
      return Promise.resolve({
        total: items.length,
        page: 1,
        limit: 20,
        items,
      });
    });
    vi.mocked(historyApi.batchUpdateState).mockResolvedValue({
      updated: 1,
      recordIds: [10],
      aiUsed: false,
    });

    render(
      <MemoryRouter>
        <HomePage />
      </MemoryRouter>,
    );

    expect(await screen.findByTestId('history-center-item-10')).toHaveTextContent('AAPL');
    expect(screen.getByTestId('history-center-state-filter')).toHaveValue('active');
    await waitFor(() => {
      expect(historyApi.getList).toHaveBeenCalledWith(expect.objectContaining({
        state: 'active',
      }));
    });
    expect(screen.getByTestId('history-group-2026-07-04')).toHaveTextContent('2026-07-04');
    expect(screen.getByTestId('history-group-2026-07-03')).toHaveTextContent('2026-07-03');

    fireEvent.change(screen.getByTestId('history-center-note-filter'), { target: { value: 'earnings' } });
    await waitFor(() => {
      expect(historyApi.getList).toHaveBeenCalledWith(expect.objectContaining({
        state: 'active',
        noteSearch: 'earnings',
      }));
    });
    expect(screen.getByTestId('history-center-item-10')).toBeInTheDocument();
    expect(screen.queryByTestId('history-center-item-11')).not.toBeInTheDocument();

    fireEvent.click(screen.getByTestId('history-select-all-visible'));
    fireEvent.click(screen.getByTestId('history-center-important-selected'));
    await waitFor(() => {
      expect(historyApi.batchUpdateState).toHaveBeenCalledWith([10], { important: true });
    });
    expect(screen.getByTestId('history-center-state-status')).toHaveTextContent('Marked important 1 local reports');

    fireEvent.click(screen.getByTestId('history-center-read-selected'));
    await waitFor(() => {
      expect(historyApi.batchUpdateState).toHaveBeenCalledWith([10], { read: true });
    });
    expect(analysisApi.analyzeAsync).not.toHaveBeenCalled();
  });

  it('adds no-AI report detail search, section jumps and same-stock timeline', async () => {
    const currentItem = {
      ...historyItem,
      id: 30,
      queryId: 'q-v30-current',
      stockCode: 'AAPL',
      stockName: 'Apple',
      reportType: 'detailed' as const,
      createdAt: '2026-07-04T08:00:00Z',
    };
    const previousItem = {
      ...historyItem,
      id: 31,
      queryId: 'q-v30-previous',
      stockCode: 'AAPL',
      stockName: 'Apple',
      reportType: 'simple' as const,
      createdAt: '2026-07-01T08:00:00Z',
    };
    const otherItem = {
      ...historyItem,
      id: 32,
      queryId: 'q-v30-other',
      stockCode: 'MSFT',
      stockName: 'Microsoft',
      reportType: 'simple' as const,
      createdAt: '2026-07-03T08:00:00Z',
    };
    const currentReport = {
      ...historyReport,
      meta: {
        ...historyReport.meta,
        id: 30,
        queryId: 'q-v30-current',
        stockCode: 'AAPL',
        stockName: 'Apple',
        reportType: 'detailed' as const,
        createdAt: '2026-07-04T08:00:00Z',
      },
      summary: {
        ...historyReport.summary,
        analysisSummary: 'Apple margin expansion remains visible',
        operationAdvice: 'Review valuation risk before adding',
        trendPrediction: 'Momentum holds',
      },
      strategy: {
        idealBuy: 'Wait for valuation reset near support',
        secondaryBuy: 'Add only after volume confirms',
        stopLoss: 'Break below support',
        takeProfit: 'Scale out near resistance',
      },
      details: {
        newsContent: 'Supply chain update mentions valuation discipline.',
      },
    };
    const previousReport = {
      ...currentReport,
      meta: {
        ...currentReport.meta,
        id: 31,
        queryId: 'q-v30-previous',
        createdAt: '2026-07-01T08:00:00Z',
      },
      summary: {
        ...currentReport.summary,
        analysisSummary: 'Previous Apple history report',
      },
    };

    vi.mocked(historyApi.getList).mockImplementation((params: { reportType?: string } = {}) => {
      if (params.reportType === 'market_review') {
        return Promise.resolve({ total: 0, page: 1, limit: 10, items: [] });
      }
      return Promise.resolve({
        total: 3,
        page: 1,
        limit: 20,
        items: [currentItem, previousItem, otherItem],
      });
    });
    vi.mocked(historyApi.getDetail).mockImplementation((recordId: number) => (
      Promise.resolve(recordId === 31 ? previousReport : currentReport)
    ));
    vi.mocked(analysisApi.analyzeAsync).mockRejectedValue(new Error('AI should not run for local report detail tools'));

    render(
      <MemoryRouter>
        <HomePage />
      </MemoryRouter>,
    );

    expect(await screen.findByText('Apple margin expansion remains visible')).toBeInTheDocument();
    expect(screen.getByTestId('history-report-tools')).toBeInTheDocument();
    expect(screen.getByTestId('history-report-stock-timeline')).toHaveTextContent('AAPL');
    expect(screen.getByTestId('history-report-timeline-30')).toHaveTextContent('Current');
    expect(screen.getByTestId('history-report-timeline-31')).toHaveTextContent('2026-07-01');
    expect(screen.queryByTestId('history-report-timeline-32')).not.toBeInTheDocument();

    fireEvent.change(screen.getByTestId('history-report-search'), { target: { value: 'valuation' } });
    expect(screen.getByTestId('history-report-search-count')).toHaveTextContent('1/3');
    expect(screen.getByTestId('history-report-search-hit')).toHaveTextContent('valuation risk');
    fireEvent.click(screen.getByTestId('history-report-search-next'));
    expect(screen.getByTestId('history-report-search-count')).toHaveTextContent('2/3');

    fireEvent.click(screen.getByTestId('history-report-jump-strategy'));
    expect(screen.getByTestId('history-report-section-status')).toHaveTextContent('Strategy');

    fireEvent.click(screen.getByTestId('history-report-timeline-31'));
    await waitFor(() => {
      expect(historyApi.getDetail).toHaveBeenCalledWith(31);
    });
    expect(await screen.findByText('Previous Apple history report')).toBeInTheDocument();
    expect(analysisApi.analyzeAsync).not.toHaveBeenCalled();
  });

  it('shows the empty report workspace when history is empty', async () => {
    vi.mocked(historyApi.getList).mockResolvedValue({
      total: 0,
      page: 1,
      limit: 20,
      items: [],
    });

    render(
      <MemoryRouter>
        <HomePage />
      </MemoryRouter>,
    );

    expect(await screen.findByText('开始分析')).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: '开始分析', level: 3 })).toBeInTheDocument();
    expect(screen.getByText('输入股票代码进行分析，或从左侧选择历史报告查看。')).toBeInTheDocument();
    expect(screen.getByText('暂无个股记录')).toBeInTheDocument();
  });

  it('opens the run-flow drawer from an active task in TaskPanel', async () => {
    vi.mocked(historyApi.getList).mockResolvedValue({
      total: 0,
      page: 1,
      limit: 20,
      items: [],
    });
    vi.mocked(analysisApi.getTasks).mockResolvedValue({
      total: 1,
      pending: 0,
      processing: 1,
      tasks: [
        {
          taskId: 'task-1',
          traceId: 'trace-1',
          stockCode: '600519',
          stockName: '贵州茅台',
          status: 'processing',
          progress: 35,
          message: '分析中',
          reportType: 'detailed',
          createdAt: '2026-06-08T08:00:00Z',
        },
      ],
    });

    render(
      <MemoryRouter>
        <HomePage />
      </MemoryRouter>,
    );

    fireEvent.click(await screen.findByRole('button', { name: '查看 贵州茅台 运行流' }));

    await waitFor(() => {
      expect(analysisApi.getTaskFlow).toHaveBeenCalledWith('task-1');
    });
    expect(await screen.findByTestId('run-flow-panel')).toBeInTheDocument();
    expect(screen.getByText('贵州茅台 运行流')).toBeInTheDocument();
  });

  it('opens the run-flow drawer from completed report diagnostics', async () => {
    vi.mocked(historyApi.getList).mockResolvedValue({
      total: 1,
      page: 1,
      limit: 20,
      items: [historyItem],
    });
    vi.mocked(historyApi.getDetail).mockResolvedValue(historyReport);

    render(
      <MemoryRouter>
        <HomePage />
      </MemoryRouter>,
    );

    fireEvent.click(await screen.findByText('运行状态'));
    fireEvent.click(screen.getByRole('button', { name: '查看历史记录 1 运行流' }));

    await waitFor(() => {
      expect(historyApi.getRecordFlow).toHaveBeenCalledWith(1);
    });
    expect(await screen.findByTestId('run-flow-panel')).toBeInTheDocument();
    expect(screen.getByText('贵州茅台 历史运行流')).toBeInTheDocument();
  });

  it('shows market review history in the stock bar', async () => {
    vi.mocked(historyApi.getStockBarList).mockResolvedValue({
      total: 1,
      items: [{
        id: 11,
        stockCode: 'AAPL',
        stockName: 'Apple',
        reportType: 'detailed',
        sentimentScore: 72,
        operationAdvice: '观察',
        analysisCount: 2,
        lastAnalysisTime: '2026-03-19T08:00:00Z',
      }],
    });
    vi.mocked(historyApi.getList).mockImplementation((params: { reportType?: string } = {}) => {
      if (params.reportType === 'market_review') {
        return Promise.resolve({
          total: 1,
          page: 1,
          limit: 10,
          items: [marketReviewHistoryItem],
        });
      }
      return Promise.resolve({
        total: 0,
        page: 1,
        limit: 20,
        items: [],
      });
    });
    vi.mocked(historyApi.getDetail).mockResolvedValue(marketReviewHistoryReport);

    render(
      <MemoryRouter>
        <HomePage />
      </MemoryRouter>,
    );

    expect(await screen.findByRole('button', { name: /MARKET/ })).toBeInTheDocument();
    const newerStockButton = await screen.findByRole('button', { name: /AAPL/ });
    const marketButton = await screen.findByRole('button', { name: /MARKET/ });
    expect(newerStockButton.compareDocumentPosition(marketButton) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(screen.queryByText('大盘复盘历史')).not.toBeInTheDocument();
    expect(historyApi.getList).toHaveBeenCalledWith({
      stockCode: 'MARKET',
      reportType: 'market_review',
      page: 1,
      limit: 10,
    });

    fireEvent.click(await screen.findByRole('button', { name: /MARKET/ }));

    expect(await screen.findByText('大盘复盘摘要')).toBeInTheDocument();
  });

  it('removes the MARKET stock bar item after deleting market review history', async () => {
    let isMarketReviewDeleted = false;
    vi.mocked(historyApi.getStockBarList).mockResolvedValue({
      total: 0,
      items: [],
    });
    vi.mocked(historyApi.getList).mockImplementation((params: { reportType?: string } = {}) => {
      if (params.reportType === 'market_review') {
        return Promise.resolve({
          total: isMarketReviewDeleted ? 0 : 1,
          page: 1,
          limit: 10,
          items: isMarketReviewDeleted ? [] : [marketReviewHistoryItem],
        });
      }
      return Promise.resolve({
        total: 0,
        page: 1,
        limit: 20,
        items: [],
      });
    });
    vi.mocked(historyApi.deleteByCode).mockImplementation(async () => {
      isMarketReviewDeleted = true;
      return { deleted: 1 };
    });

    render(
      <MemoryRouter>
        <HomePage />
      </MemoryRouter>,
    );

    expect(await screen.findByRole('button', { name: /MARKET/ })).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: '删除 大盘复盘 历史记录' }));

    await waitFor(() => {
      expect(screen.queryByRole('button', { name: /MARKET/ })).not.toBeInTheDocument();
    });
    expect(historyApi.deleteByCode).toHaveBeenCalledWith('MARKET');
  });

  it('surfaces duplicate task warnings from dashboard submission', async () => {
    vi.mocked(historyApi.getList).mockResolvedValue({
      total: 0,
      page: 1,
      limit: 20,
      items: [],
    });
    vi.mocked(analysisApi.analyzeAsync).mockRejectedValue(
      new DuplicateTaskError('600519', 'task-1', '股票 600519 正在分析中'),
    );

    render(
      <MemoryRouter>
        <HomePage />
      </MemoryRouter>,
    );

    const input = await screen.findByPlaceholderText('输入股票代码或名称，如 600519、贵州茅台、AAPL');
    fireEvent.change(input, { target: { value: '600519' } });
    fireEvent.click(screen.getByRole('button', { name: '快速分析' }));

    await waitFor(() => {
      expect(screen.getByText(/股票 600519 正在分析中/)).toBeInTheDocument();
    });
    expect(screen.getByText(/股票 600519 正在分析中/).closest('[role="alert"]')).toBeInTheDocument();
  });

  it('runs basic query without submitting AI analysis', async () => {
    vi.mocked(historyApi.getList).mockResolvedValue({
      total: 0,
      page: 1,
      limit: 20,
      items: [],
    });
    vi.mocked(stocksApi.snapshot).mockResolvedValue({
      stockCode: 'AAPL',
      stockName: 'Apple Inc.',
      market: 'us',
      quote: {
        currentPrice: 200,
        change: 3,
        changePercent: 1.5,
        open: 198,
        high: 205,
        low: 197,
        prevClose: 197,
        volume: 75352800,
        amount: 15070560000,
        source: 'yahoo_chart',
        freshness: 'fresh',
      },
      indicators: {
        ma5: 198,
        ma10: 196,
        ma20: 190,
        priceChange5D: 4.2,
        priceChange20D: -1.6,
        volumeChangeVsMa5: 12.5,
        volumePriceSignal: 'price_volume_confirmed',
      },
      profile: {
        companyName: 'Apple Inc.',
        sector: 'Technology',
        industry: 'Consumer Electronics',
        exchange: 'NASDAQ',
        currency: 'USD',
        country: 'United States',
        marketCap: 4500000000000,
        peRatio: 31.2,
        dividendYield: 0.5,
        source: 'unit_profile',
        freshness: 'fresh',
      },
      trend: {
        window: 6,
        source: 'unit_history',
        changePercent: 6.383,
        minClose: 188,
        maxClose: 200,
        points: [
          { date: '2026-06-25', close: 188, volume: 70000000 },
          { date: '2026-06-26', close: 190, volume: 71000000 },
          { date: '2026-06-29', close: 193, volume: 73000000 },
          { date: '2026-06-30', close: 196, volume: 74000000 },
          { date: '2026-07-01', close: 198, volume: 75000000 },
          { date: '2026-07-02', close: 200, volume: 75352800 },
        ],
      },
      intelligence: {
        mode: 'no_ai_low_cost',
        aiUsed: false,
        boundary: 'Information analysis only; not investment advice.',
        items: [
          {
            category: 'news',
            title: 'News',
            summary: 'No realtime news source is enabled in free no-AI mode.',
            status: 'degraded',
            source: 'no_ai_quick_snapshot',
          },
          {
            category: 'announcements',
            title: 'Announcements',
            summary: 'No filing or announcement source is enabled in free no-AI mode.',
            status: 'degraded',
            source: 'no_ai_quick_snapshot',
          },
          {
            category: 'financials',
            title: 'Financial snapshot',
            summary: 'Market cap 4.5T; PE 31.2; dividend yield 0.5%.',
            status: 'available',
            source: 'unit_profile',
          },
        ],
        watchPoints: [
          {
            category: 'trend',
            title: 'Trend confirmation',
            detail: 'Watch whether price can hold above MA20.',
            priority: 'high',
            source: 'no_ai_rules',
          },
          {
            category: 'volume',
            title: 'Volume confirmation',
            detail: 'Volume expansion would improve confirmation quality.',
            priority: 'medium',
            source: 'no_ai_rules',
          },
          {
            category: 'risk',
            title: 'Risk boundary',
            detail: 'Keep the analysis informational and not investment advice.',
            priority: 'medium',
            source: 'no_ai_rules',
          },
        ],
        comparisonTargets: [
          {
            label: 'QQQ',
            symbol: 'QQQ',
            reason: 'US large-cap technology benchmark.',
            status: 'reference_only',
            source: 'no_ai_route_rules',
          },
          {
            label: 'Technology sector ETF',
            symbol: 'XLK',
            reason: 'Sector context for Technology names.',
            status: 'reference_only',
            source: 'no_ai_route_rules',
          },
        ],
      },
      diagnostics: {
        elapsedMs: 18,
        quoteElapsedMs: 8,
        historyElapsedMs: 10,
        cache: { quote: 'miss', history: 'miss' },
        sources: { quote: 'yahoo_chart', history: 'yfinance' },
        freshness: { quote: 'fresh', history: 'fresh' },
        timeouts: { quote: false, history: false },
        errors: { quote: null, history: null },
        fallback: { quote: 'live', history: 'live' },
        sourceHealth: {
          quote: { source: 'unit_quote', status: 'ok', consecutiveFailures: 0 },
          history: { source: 'unit_history', status: 'ok', consecutiveFailures: 0 },
        },
        persistentCache: { quote: 'memory', history: 'memory', mode: 'local_json' },
        routeLane: 'us_market_data',
        performance: { status: 'ok', slowThresholdMs: 3000 },
      },
      aiUsed: false,
    });
    vi.mocked(analysisApi.analyzeAsync).mockRejectedValue(new Error('AI should not run for basic query'));

    render(
      <MemoryRouter>
        <HomePage />
      </MemoryRouter>,
    );

    const input = await screen.findByRole('textbox');
    fireEvent.change(input, { target: { value: 'AAPL' } });
    fireEvent.click(screen.getByRole('button', { name: '查询' }));

    await waitFor(() => {
      expect(stocksApi.snapshot).toHaveBeenCalledWith('AAPL');
    });
    expect(analysisApi.analyzeAsync).not.toHaveBeenCalled();
    expect(await screen.findByText('Apple Inc.')).toBeInTheDocument();
    expect(screen.getAllByText('200').length).toBeGreaterThan(0);
    const primarySummary = screen.getByTestId('basic-query-primary-summary');
    expect(primarySummary).toHaveTextContent('Apple Inc.');
    expect(primarySummary).toHaveTextContent('200');
    expect(primarySummary).toHaveTextContent('Technology');
    expect(primarySummary).toHaveTextContent('Consumer Electronics');
    expect(primarySummary).toHaveTextContent('4.5T');
    expect(primarySummary).toHaveTextContent('31.2');
    const freeReport = screen.getByTestId('basic-query-free-report');
    expect(freeReport).toHaveTextContent('No AI');
    expect(freeReport).toHaveTextContent('Technology');
    expect(freeReport).toHaveTextContent('Consumer Electronics');
    expect(freeReport).toHaveTextContent('MA5');
    expect(freeReport).toHaveTextContent('MA20');
    expect(freeReport).toHaveTextContent('4.5T');
    expect(freeReport).toHaveTextContent('31.2');
    const productBrief = screen.getByTestId('basic-query-product-brief');
    expect(productBrief).toHaveTextContent('关键结论');
    expect(productBrief).toHaveTextContent('支撑');
    expect(productBrief).toHaveTextContent('压力');
    expect(productBrief).toHaveTextContent('短线');
    expect(productBrief).toHaveTextContent('中线');
    expect(productBrief).toHaveTextContent('风险边界');
    expect(productBrief).toHaveTextContent('继续深度分析');
    expect(productBrief).toHaveTextContent('No AI');
    const miniChart = screen.getByTestId('basic-query-mini-chart');
    expect(miniChart).toHaveTextContent('6日趋势');
    expect(miniChart).toHaveTextContent('+6.38%');
    expect(miniChart.querySelector('svg')).toBeInTheDocument();
    const intelligencePanel = screen.getByTestId('basic-query-intelligence-panel');
    expect(intelligencePanel).toHaveTextContent('资讯摘要');
    expect(intelligencePanel).toHaveTextContent('新闻');
    expect(intelligencePanel).toHaveTextContent('公告');
    expect(intelligencePanel).toHaveTextContent('财报');
    expect(intelligencePanel).toHaveTextContent('No realtime news source');
    expect(intelligencePanel).toHaveTextContent('No AI');
    expect(intelligencePanel).toHaveTextContent('not investment advice');
    const watchPoints = screen.getByTestId('basic-query-watch-points');
    expect(watchPoints).toHaveTextContent('下一步观察');
    expect(watchPoints).toHaveTextContent('Trend confirmation');
    expect(watchPoints).toHaveTextContent('MA20');
    expect(watchPoints).toHaveTextContent('Volume confirmation');
    expect(watchPoints).toHaveTextContent('QQQ');
    expect(watchPoints).toHaveTextContent('XLK');
    expect(
      primarySummary.compareDocumentPosition(screen.getByTestId('basic-query-user-guardrails'))
      & Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
    expect(
      primarySummary.compareDocumentPosition(screen.getByTestId('basic-query-workspace-lanes'))
      & Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
    expect(screen.getByTestId('basic-query-quote-details')).toHaveTextContent('开盘');
    expect(screen.getByTestId('basic-query-quote-details')).toHaveTextContent('198');
    expect(screen.getByTestId('basic-query-quote-details')).toHaveTextContent('最高');
    expect(screen.getByTestId('basic-query-quote-details')).toHaveTextContent('205');
    expect(screen.getByTestId('basic-query-quote-details')).toHaveTextContent('最低');
    expect(screen.getByTestId('basic-query-quote-details')).toHaveTextContent('197');
    expect(screen.getByTestId('basic-query-quote-details')).toHaveTextContent('昨收');
    expect(screen.getByTestId('basic-query-quote-details')).toHaveTextContent('涨跌额');
    expect(screen.getByTestId('basic-query-quote-details')).toHaveTextContent('3');
    expect(screen.getByTestId('basic-query-quote-details')).toHaveTextContent('成交量');
    expect(screen.getByTestId('basic-query-quote-details')).toHaveTextContent('75.35M');
    expect(screen.getByTestId('basic-query-technical-details')).toHaveTextContent('MA10');
    expect(screen.getByTestId('basic-query-technical-details')).toHaveTextContent('196');
    expect(screen.getByTestId('basic-query-technical-details')).toHaveTextContent('5日涨跌');
    expect(screen.getByTestId('basic-query-technical-details')).toHaveTextContent('4.2%');
    expect(screen.getByTestId('basic-query-technical-details')).toHaveTextContent('20日涨跌');
    expect(screen.getByTestId('basic-query-technical-details')).toHaveTextContent('-1.6%');
    expect(screen.getByTestId('basic-query-technical-details')).toHaveTextContent('量能变化');
    expect(screen.getByTestId('basic-query-technical-details')).toHaveTextContent('12.5%');
    expect(screen.getByTestId('basic-query-technical-details')).toHaveTextContent('价量确认');
    expect(screen.getByTestId('basic-query-company-profile')).toHaveTextContent('Technology');
    expect(screen.getByTestId('basic-query-company-profile')).toHaveTextContent('Consumer Electronics');
    expect(screen.getByTestId('basic-query-company-profile')).toHaveTextContent('NASDAQ');
    expect(screen.getByTestId('basic-query-company-profile')).toHaveTextContent('USD');
    expect(screen.getByTestId('basic-query-company-profile')).toHaveTextContent('4.5T');
    expect(screen.getByTestId('basic-query-company-profile')).toHaveTextContent('31.2');
    expect(screen.getByTestId('basic-query-company-profile')).toHaveTextContent('unit_profile');
    expect(screen.getByTestId('basic-query-snapshot')).toHaveTextContent('No AI');
    expect(screen.getByTestId('basic-query-diagnostics')).toHaveTextContent('18ms');
    expect(screen.getByTestId('basic-query-diagnostics')).toHaveTextContent('Q miss / H miss');
    expect(screen.getByTestId('basic-query-diagnostics')).toHaveTextContent('Q live / H live');
    expect(screen.getByTestId('basic-query-diagnostics')).toHaveTextContent('Q ok / H ok');
    expect(screen.getByTestId('basic-query-diagnostics')).toHaveTextContent('Q memory / H memory');
  });

  it('force-refreshes the current no-AI snapshot without submitting AI analysis', async () => {
    vi.mocked(historyApi.getList).mockResolvedValue({
      total: 0,
      page: 1,
      limit: 20,
      items: [],
    });
    vi.mocked(stocksApi.snapshot)
      .mockResolvedValueOnce({
        stockCode: 'AAPL',
        stockName: 'Apple Inc.',
        market: 'us',
        quote: {
          currentPrice: 200,
          changePercent: 1.5,
          source: 'yahoo_chart',
          freshness: 'cached',
        },
        indicators: { ma5: 198, ma20: 190 },
        diagnostics: {
          elapsedMs: 18,
          quoteElapsedMs: 8,
          historyElapsedMs: 10,
          cache: { quote: 'hit', history: 'hit' },
          sources: { quote: 'yahoo_chart', history: 'yfinance' },
          freshness: { quote: 'cached', history: 'cached' },
          fallback: { quote: 'cache', history: 'cache' },
          persistentCache: { quote: 'memory', history: 'memory', mode: 'local_json' },
          refresh: { mode: 'cache_first', requested: false },
          routeLane: 'us_market_data',
          performance: { status: 'ok', slowThresholdMs: 3000 },
        },
        aiUsed: false,
      })
      .mockResolvedValueOnce({
        stockCode: 'AAPL',
        stockName: 'Apple Inc.',
        market: 'us',
        quote: {
          currentPrice: 210,
          changePercent: 2.0,
          source: 'yahoo_chart',
          freshness: 'fresh',
        },
        indicators: { ma5: 202, ma20: 191 },
        diagnostics: {
          elapsedMs: 31,
          quoteElapsedMs: 13,
          historyElapsedMs: 18,
          cache: { quote: 'refresh', history: 'refresh' },
          sources: { quote: 'yahoo_chart', history: 'yfinance' },
          freshness: { quote: 'fresh', history: 'fresh' },
          fallback: { quote: 'live', history: 'live' },
          persistentCache: { quote: 'none', history: 'none', mode: 'local_json' },
          refresh: { mode: 'force_refresh', requested: true, quote: true, history: true },
          routeLane: 'us_market_data',
          performance: { status: 'ok', slowThresholdMs: 3000 },
        },
        aiUsed: false,
      });
    vi.mocked(analysisApi.analyzeAsync).mockRejectedValue(new Error('AI should not run for snapshot refresh'));

    render(
      <MemoryRouter>
        <HomePage />
      </MemoryRouter>,
    );

    const input = await screen.findByRole('textbox');
    fireEvent.change(input, { target: { value: 'AAPL' } });
    fireEvent.click(screen.getByRole('button', { name: '查询' }));

    expect(await screen.findByTestId('basic-query-snapshot')).toHaveTextContent('200');
    fireEvent.click(screen.getByTestId('basic-query-refresh-market'));

    await waitFor(() => {
      expect(stocksApi.snapshot).toHaveBeenLastCalledWith('AAPL', { refresh: true });
    });
    expect(analysisApi.analyzeAsync).not.toHaveBeenCalled();
    expect(screen.getByTestId('basic-query-snapshot')).toHaveTextContent('210');
    expect(screen.getByTestId('basic-query-diagnostics')).toHaveTextContent('force_refresh');
    expect(screen.getByTestId('basic-query-diagnostics')).toHaveTextContent('Q refresh / H refresh');
  });

  it('shows quick query route and degradation warnings without submitting AI analysis', async () => {
    vi.mocked(historyApi.getList).mockResolvedValue({
      total: 0,
      page: 1,
      limit: 20,
      items: [],
    });
    vi.mocked(stocksApi.snapshot).mockResolvedValue({
      stockCode: 'BTC-USD',
      stockName: 'Bitcoin',
      market: 'crypto',
      quote: {
        source: 'crypto_yahoo_chart',
        freshness: 'stale',
      },
      indicators: { ma5: 101, ma20: 99, volumePriceSignal: 'neutral' },
      route: {
        inputCode: 'BTC-USD',
        normalizedCode: 'BTC-USD',
        market: 'crypto',
        channel: 'crypto_spot',
        dataSourceLane: 'crypto_market_data',
        quoteSources: ['crypto_yahoo_chart'],
        historySources: ['crypto_yahoo_chart'],
        aiRequired: false,
      },
      warnings: [
        { code: 'stale_quote', severity: 'warning', message: 'Quote is stale; using cached data.' },
      ],
      degradation: {
        status: 'degraded',
        severity: 'warning',
        message: 'Quote is stale; using cached data.',
      },
      diagnostics: {
        elapsedMs: 7,
        quoteElapsedMs: 2,
        historyElapsedMs: 5,
        cache: { quote: 'hit', history: 'hit' },
        sources: { quote: 'crypto_yahoo_chart', history: 'crypto_yahoo_chart' },
        freshness: { quote: 'stale', history: 'cached' },
        timeouts: { quote: false, history: false },
        errors: { quote: null, history: null },
        fallback: { quote: 'stale_cache', history: 'cache' },
        sourceHealth: {
          quote: { source: 'crypto_yahoo_chart', status: 'ok', consecutiveFailures: 0 },
          history: { source: 'crypto_yahoo_chart', status: 'ok', consecutiveFailures: 0 },
        },
        persistentCache: { quote: 'disk', history: 'disk', mode: 'local_json' },
        routeLane: 'crypto_market_data',
        performance: { status: 'ok', slowThresholdMs: 3000 },
      },
      aiUsed: false,
    });
    vi.mocked(analysisApi.analyzeAsync).mockRejectedValue(new Error('AI should not run for degraded quick query'));

    render(
      <MemoryRouter>
        <HomePage />
      </MemoryRouter>,
    );

    const input = await screen.findByRole('textbox');
    fireEvent.change(input, { target: { value: 'BTC-USD' } });
    fireEvent.click(screen.getByRole('button', { name: '查询' }));

    expect(await screen.findByTestId('basic-query-route')).toHaveTextContent('crypto_market_data');
    expect(screen.getByTestId('basic-query-diagnostics')).toHaveTextContent('Q hit / H hit');
    expect(screen.getByTestId('basic-query-diagnostics')).toHaveTextContent('Q stale_cache / H cache');
    expect(screen.getByTestId('basic-query-degradation')).toHaveTextContent('stale_quote');
    expect(analysisApi.analyzeAsync).not.toHaveBeenCalled();
  });

  it('shows ordinary-user account guardrails for no-AI quick queries and AI quota cost', async () => {
    window.localStorage.setItem(UI_LANGUAGE_STORAGE_KEY, 'en');
    vi.mocked(platformApi.status).mockResolvedValue({ platformAuthEnabled: true });
    vi.mocked(platformApi.current).mockResolvedValue({
      user: {
        id: 15,
        email: 'v15-user@example.com',
        role: 'user',
        plan: 'free',
        status: 'active',
      },
      quota: {
        userId: 15,
        plan: 'free',
        weeklyLimit: 5,
        used: 4,
        remaining: 1,
        periodStart: '2026-07-01',
      },
    });
    vi.mocked(platformApi.account).mockResolvedValue({
      user: {
        id: 15,
        email: 'v15-user@example.com',
        role: 'user',
        plan: 'free',
        status: 'active',
      },
      quota: {
        userId: 15,
        plan: 'free',
        weeklyLimit: 5,
        used: 4,
        remaining: 1,
        periodStart: '2026-07-01',
      },
      quotaBuckets: [
        {
          userId: 15,
          plan: 'free',
          weeklyLimit: 10,
          used: 1,
          remaining: 9,
          periodStart: '2026-07-01',
          quotaBucket: 'basic_query',
        },
        {
          userId: 15,
          plan: 'free',
          weeklyLimit: 3,
          used: 1,
          remaining: 2,
          periodStart: '2026-07-01',
          quotaBucket: 'ai_deep_user_key',
        },
      ],
      apiKeys: [
        {
          provider: 'deepseek',
          model: 'deepseek/deepseek-v4-flash',
          maskedKey: 'sk-...live',
          enabled: true,
        },
      ],
      recommendedQueryMode: 'user',
    });
    vi.mocked(platformApi.listApiKeys).mockResolvedValue([
      {
        provider: 'deepseek',
        model: 'deepseek/deepseek-v4-flash',
        maskedKey: 'sk-...live',
        enabled: true,
      },
    ]);
    vi.mocked(platformApi.watchlist).mockResolvedValue({
      userId: 15,
      total: 4,
      aiUsed: false,
      items: [
        { id: 1, stockCode: '600519', market: 'cn' },
        { id: 2, stockCode: 'AAPL', market: 'us' },
        { id: 3, stockCode: 'HK00700', market: 'hk' },
        { id: 4, stockCode: 'BTC-USD', market: 'crypto' },
      ],
    });
    vi.mocked(platformApi.refreshWatchlist).mockResolvedValue({
      userId: 15,
      requested: 4,
      refreshed: 4,
      degraded: 1,
      aiUsed: false,
      items: [
        { stockCode: '600519', stockName: 'Kweichow Moutai', market: 'cn', routeLane: 'a_share_market_data', freshness: 'fresh', degradationStatus: 'ok', warningCodes: [], aiUsed: false, status: 'ok' },
        { stockCode: 'AAPL', stockName: 'Apple Inc.', market: 'us', routeLane: 'us_market_data', freshness: 'fresh', degradationStatus: 'ok', warningCodes: [], aiUsed: false, status: 'ok' },
        { stockCode: 'HK00700', stockName: 'Tencent Holdings', market: 'hk', routeLane: 'hk_market_data', freshness: 'fresh', degradationStatus: 'degraded', warningCodes: ['missing_history'], aiUsed: false, status: 'degraded' },
        { stockCode: 'BTC-USD', stockName: 'Bitcoin', market: 'crypto', routeLane: 'crypto_market_data', freshness: 'fresh', degradationStatus: 'ok', warningCodes: [], aiUsed: false, status: 'ok' },
      ],
    });
    vi.mocked(historyApi.getList).mockResolvedValue({
      total: 0,
      page: 1,
      limit: 20,
      items: [],
    });
    vi.mocked(stocksApi.snapshot).mockResolvedValue({
      stockCode: 'HK00700',
      stockName: 'Tencent Holdings',
      market: 'hk',
      quote: {
        currentPrice: 390.2,
        changePercent: 0.8,
        source: 'yahoo_chart',
        freshness: 'fresh',
      },
      indicators: { ma5: 388, ma20: 376 },
      route: {
        inputCode: 'HK00700',
        normalizedCode: '0700.HK',
        market: 'hk',
        channel: 'hk_equity',
        dataSourceLane: 'hk_market_data',
        quoteSources: ['yahoo_chart'],
        historySources: ['yfinance'],
        aiRequired: false,
      },
      diagnostics: {
        elapsedMs: 21,
        quoteElapsedMs: 9,
        historyElapsedMs: 12,
        cache: { quote: 'hit', history: 'miss' },
        sources: { quote: 'yahoo_chart', history: 'yfinance' },
        freshness: { quote: 'fresh', history: 'fresh' },
        timeouts: { quote: false, history: false },
        errors: { quote: null, history: null },
        fallback: { quote: 'live', history: 'live' },
        sourceHealth: {
          quote: { source: 'yahoo_chart', status: 'ok', consecutiveFailures: 0 },
          history: { source: 'yfinance', status: 'ok', consecutiveFailures: 0 },
        },
        persistentCache: { quote: 'disk', history: 'disk', mode: 'local_json' },
        routeLane: 'hk_market_data',
        performance: { status: 'ok', slowThresholdMs: 3000 },
      },
      aiUsed: false,
    });
    vi.mocked(analysisApi.analyzeAsync).mockRejectedValue(new Error('AI should not run for no-AI quick query'));

    render(
      <UiLanguageProvider>
        <MemoryRouter>
          <HomePage />
        </MemoryRouter>
      </UiLanguageProvider>,
    );

    const platformStatus = await screen.findByTestId('platform-query-status');
    expect(platformStatus).toHaveTextContent('Signed in v15-user@example.com');
    expect(platformStatus).toHaveTextContent('Plan free');
    expect(platformStatus).toHaveTextContent('Weekly free 1/5 left');
    expect(platformStatus).toHaveTextContent('No-AI quick 9/10 left');
    expect(platformStatus).toHaveTextContent('BYOK ready sk-...live');
    expect(platformStatus).toHaveTextContent('Recommended BYOK');
    expect(platformStatus).not.toHaveTextContent('sk-live-secret');
    expect(screen.getByTestId('platform-ai-cost-warning')).toHaveTextContent('Quick snapshot stays no-AI');
    expect(screen.getByTestId('platform-ai-cost-warning')).toHaveTextContent('Quick/Deep AI uses selected quota');
    expect(await screen.findByTestId('platform-watchlist-panel')).toHaveTextContent('Watchlist 4');
    expect(screen.getByTestId('platform-watchlist-panel')).toHaveTextContent('600519');
    expect(screen.getByTestId('platform-watchlist-panel')).toHaveTextContent('BTC-USD');

    fireEvent.click(screen.getByTestId('platform-watchlist-refresh'));
    expect(await screen.findByTestId('platform-watchlist-refresh-summary')).toHaveTextContent('No AI used');
    expect(screen.getByTestId('platform-watchlist-refresh-summary')).toHaveTextContent('refreshed 4/4');
    expect(screen.getByTestId('platform-watchlist-refresh-summary')).toHaveTextContent('degraded 1');
    expect(screen.getByTestId('platform-watchlist-refresh-summary')).toHaveTextContent('hk_market_data');

    fireEvent.change(screen.getByPlaceholderText('Enter a stock code or name, e.g. 600519, Kweichow Moutai, AAPL'), {
      target: { value: 'HK00700' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Query' }));

    expect(await screen.findByTestId('basic-query-user-guardrails')).toHaveTextContent('Current quick snapshot');
    expect(screen.queryByTestId('platform-query-status')).not.toBeInTheDocument();
    expect(screen.getByTestId('basic-query-user-guardrails')).toHaveTextContent('No AI used');
    expect(screen.getByTestId('basic-query-user-guardrails')).toHaveTextContent('HK market data');
    expect(screen.getByTestId('basic-query-user-guardrails')).toHaveTextContent('Historical reports stay separate');
    expect(screen.getByTestId('basic-query-user-guardrails')).toHaveTextContent('Cache local_json');
    expect(screen.getByTestId('basic-query-route')).toHaveTextContent('hk_market_data');
    const workspace = screen.getByTestId('basic-query-workspace-lanes');
    expect(workspace).toHaveTextContent('Current Snapshot');
    expect(workspace).toHaveTextContent('No AI');
    expect(workspace).toHaveTextContent('HK market data');
    expect(workspace).toHaveTextContent('Watchlist');
    expect(workspace).toHaveTextContent('4 symbols');
    expect(workspace).toHaveTextContent('History Reports');
    expect(workspace).toHaveTextContent('0 reports');
    expect(workspace).toHaveTextContent('separate');
    expect(workspace).toHaveTextContent('AI Analysis');
    expect(workspace).toHaveTextContent('Selected Platform API');
    expect(workspace).toHaveTextContent('BYOK ready');
    expect(analysisApi.analyzeAsync).not.toHaveBeenCalled();
  });

  it('renders refreshed watchlist board rows and runs no-AI quick query from a row', async () => {
    window.localStorage.setItem(UI_LANGUAGE_STORAGE_KEY, 'en');
    vi.mocked(platformApi.status).mockResolvedValue({ platformAuthEnabled: true });
    vi.mocked(platformApi.current).mockResolvedValue({
      user: {
        id: 18,
        email: 'v18-user@example.com',
        role: 'user',
        plan: 'free',
        status: 'active',
      },
      quota: {
        userId: 18,
        plan: 'free',
        weeklyLimit: 5,
        used: 0,
        remaining: 5,
        periodStart: '2026-07-01',
      },
    });
    vi.mocked(platformApi.account).mockResolvedValue({
      user: {
        id: 18,
        email: 'v18-user@example.com',
        role: 'user',
        plan: 'free',
        status: 'active',
      },
      quota: {
        userId: 18,
        plan: 'free',
        weeklyLimit: 5,
        used: 0,
        remaining: 5,
        periodStart: '2026-07-01',
      },
      quotaBuckets: [],
      apiKeys: [],
      recommendedQueryMode: 'platform',
    });
    vi.mocked(platformApi.watchlist).mockResolvedValue({
      userId: 18,
      total: 4,
      aiUsed: false,
      items: [
        { id: 1, stockCode: '600519', market: 'cn' },
        { id: 2, stockCode: 'AAPL', market: 'us' },
        { id: 3, stockCode: 'HK00700', market: 'hk' },
        { id: 4, stockCode: 'BTC-USD', market: 'crypto' },
      ],
    });
    vi.mocked(platformApi.refreshWatchlist).mockResolvedValue({
      userId: 18,
      requested: 4,
      refreshed: 4,
      degraded: 1,
      aiUsed: false,
      items: [
        {
          stockCode: '600519',
          stockName: 'Kweichow Moutai',
          market: 'cn',
          routeLane: 'a_share_market_data',
          currentPrice: 1512.34,
          changePercent: 1.23,
          freshness: 'fresh',
          degradationStatus: 'ok',
          warningCodes: [],
          aiUsed: false,
          status: 'ok',
        },
        {
          stockCode: 'AAPL',
          stockName: 'Apple Inc.',
          market: 'us',
          routeLane: 'us_market_data',
          currentPrice: 211.88,
          changePercent: -0.42,
          freshness: 'fresh',
          degradationStatus: 'ok',
          warningCodes: [],
          aiUsed: false,
          status: 'ok',
        },
        {
          stockCode: 'HK00700',
          stockName: 'Tencent Holdings',
          market: 'hk',
          routeLane: 'hk_market_data',
          currentPrice: 390.2,
          changePercent: 0.8,
          freshness: 'fresh',
          degradationStatus: 'degraded',
          warningCodes: ['missing_history'],
          aiUsed: false,
          status: 'degraded',
        },
        {
          stockCode: 'BTC-USD',
          stockName: 'Bitcoin',
          market: 'crypto',
          routeLane: 'crypto_market_data',
          currentPrice: 61888.12,
          changePercent: 2.5,
          freshness: 'fresh',
          degradationStatus: 'ok',
          warningCodes: [],
          aiUsed: false,
          status: 'ok',
        },
      ],
    });
    vi.mocked(stocksApi.snapshot).mockResolvedValue({
      stockCode: 'HK00700',
      stockName: 'Tencent Holdings',
      market: 'hk',
      quote: {
        currentPrice: 390.2,
        changePercent: 0.8,
        source: 'yahoo_chart',
        freshness: 'fresh',
      },
      indicators: { ma5: 388, ma20: 376 },
      route: {
        inputCode: 'HK00700',
        normalizedCode: '0700.HK',
        market: 'hk',
        channel: 'hk_equity',
        dataSourceLane: 'hk_market_data',
        quoteSources: ['yahoo_chart'],
        historySources: ['yfinance'],
        aiRequired: false,
      },
      diagnostics: {
        elapsedMs: 21,
        quoteElapsedMs: 9,
        historyElapsedMs: 12,
        cache: { quote: 'hit', history: 'miss' },
        sources: { quote: 'yahoo_chart', history: 'yfinance' },
        freshness: { quote: 'fresh', history: 'fresh' },
        timeouts: { quote: false, history: false },
        errors: { quote: null, history: null },
        fallback: { quote: 'live', history: 'live' },
        sourceHealth: {
          quote: { source: 'yahoo_chart', status: 'ok', consecutiveFailures: 0 },
          history: { source: 'yfinance', status: 'ok', consecutiveFailures: 0 },
        },
        persistentCache: { quote: 'disk', history: 'disk', mode: 'local_json' },
        routeLane: 'hk_market_data',
        performance: { status: 'ok', slowThresholdMs: 3000 },
      },
      aiUsed: false,
    });
    vi.mocked(historyApi.getList).mockResolvedValue({
      total: 0,
      page: 1,
      limit: 20,
      items: [],
    });
    vi.mocked(analysisApi.analyzeAsync).mockRejectedValue(new Error('AI should not run from watchlist board quick query'));

    render(
      <UiLanguageProvider>
        <MemoryRouter>
          <HomePage />
        </MemoryRouter>
      </UiLanguageProvider>,
    );

    await screen.findByTestId('platform-watchlist-panel');
    fireEvent.click(screen.getByTestId('platform-watchlist-refresh'));

    const board = await screen.findByTestId('platform-watchlist-board');
    expect(board).toHaveTextContent('Tencent Holdings');
    expect(board).toHaveTextContent('HK00700');
    expect(board).toHaveTextContent('390.2');
    expect(board).toHaveTextContent('0.8%');
    expect(board).toHaveTextContent('hk_market_data');
    expect(board).toHaveTextContent('degraded');
    expect(board).toHaveTextContent('missing_history');
    expect(board).toHaveTextContent('Apple Inc.');
    expect(board).toHaveTextContent('AAPL');
    expect(board).toHaveTextContent('us_market_data');
    expect(board).toHaveTextContent('fresh');
    expect(board).toHaveTextContent('No AI');

    fireEvent.click(screen.getByTestId('platform-watchlist-board-query-HK00700'));

    await waitFor(() => {
      expect(stocksApi.snapshot).toHaveBeenCalledWith('HK00700');
    });
    expect(await screen.findByTestId('basic-query-route')).toHaveTextContent('hk_market_data');
    expect(analysisApi.analyzeAsync).not.toHaveBeenCalled();
  });

  it('submits market review from the home toolbar', async () => {
    vi.mocked(historyApi.getList).mockResolvedValue({
      total: 0,
      page: 1,
      limit: 20,
      items: [],
    });
    vi.mocked(analysisApi.triggerMarketReview).mockResolvedValue({
      status: 'accepted',
      sendNotification: true,
      message: '大盘复盘任务已提交',
      taskId: 'task-1',
    });
    vi.mocked(analysisApi.getStatus).mockResolvedValue({
      taskId: 'task-1',
      status: 'completed',
      marketReviewReport: '市场复盘报告示例文本',
    });

    render(
      <MemoryRouter>
        <HomePage />
      </MemoryRouter>,
    );

    fireEvent.click(await screen.findByRole('button', { name: '大盘复盘' }));

    await waitFor(() => {
      expect(analysisApi.triggerMarketReview).toHaveBeenCalledWith({ sendNotification: true });
    });
    expect(await screen.findByText('大盘复盘已完成')).toBeInTheDocument();
    expect(await screen.findByText('市场复盘报告示例文本')).toBeInTheDocument();
    expect(analysisApi.getStatus).toHaveBeenCalledWith('task-1');
  });

  it('keeps report language unset when only the UI language is English', async () => {
    window.localStorage.setItem(UI_LANGUAGE_STORAGE_KEY, 'en');
    vi.mocked(historyApi.getList).mockResolvedValue({
      total: 0,
      page: 1,
      limit: 20,
      items: [],
    });
    vi.mocked(analysisApi.analyzeAsync).mockResolvedValue({
      taskId: 'task-1',
      status: 'pending',
    });
    vi.mocked(analysisApi.triggerMarketReview).mockResolvedValue({
      status: 'accepted',
      sendNotification: true,
      message: 'Market review task submitted',
      taskId: 'market-task-1',
    });
    vi.mocked(analysisApi.getStatus).mockResolvedValue({
      taskId: 'market-task-1',
      status: 'completed',
      marketReviewReport: 'Market review report',
      marketReviewPayload: {
        kind: 'market_review',
        language: 'en',
        title: 'Market review',
        sections: [],
      },
    });

    render(
      <UiLanguageProvider>
        <MemoryRouter>
          <HomePage />
        </MemoryRouter>
      </UiLanguageProvider>,
    );

    fireEvent.change(await screen.findByPlaceholderText('Enter a stock code or name, e.g. 600519, Kweichow Moutai, AAPL'), {
      target: { value: 'AAPL' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Quick AI' }));
    fireEvent.click(screen.getByRole('button', { name: 'Market review' }));

    await waitFor(() => {
      expect(analysisApi.analyzeAsync).toHaveBeenCalled();
      expect(analysisApi.triggerMarketReview).toHaveBeenCalledWith({ sendNotification: true });
    });
    expect(vi.mocked(analysisApi.analyzeAsync).mock.calls[0]?.[0]).not.toHaveProperty('reportLanguage');
  });

  it('uses the payload language for live market review controls', async () => {
    vi.mocked(historyApi.getList).mockResolvedValue({
      total: 0,
      page: 1,
      limit: 20,
      items: [],
    });
    vi.mocked(analysisApi.triggerMarketReview).mockResolvedValue({
      status: 'accepted',
      sendNotification: true,
      message: 'Market review task submitted',
      taskId: 'task-1',
    });
    vi.mocked(analysisApi.getStatus).mockResolvedValue({
      taskId: 'task-1',
      status: 'completed',
      marketReviewReport: '# US Market Recap\n\n## Summary\n\nUS market review body',
      marketReviewPayload: {
        kind: 'market_review',
        region: 'us',
        language: 'en',
        title: 'US Market Recap',
        sections: [
          {
            key: 'summary',
            title: 'Summary',
            markdown: 'US market review body',
          },
        ],
      },
    });

    render(
      <MemoryRouter>
        <HomePage />
      </MemoryRouter>,
    );

    fireEvent.click(await screen.findByRole('button', { name: '大盘复盘' }));

    expect(await screen.findByRole('button', { name: 'Copy Markdown Source' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Copy Plain Text' })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: '复制 Markdown 源码' })).not.toBeInTheDocument();
  });

  it('scrolls the dashboard to market review feedback after toolbar clicks', async () => {
    vi.mocked(historyApi.getList).mockResolvedValue({
      total: 1,
      page: 1,
      limit: 20,
      items: [historyItem],
    });
    vi.mocked(historyApi.getDetail).mockResolvedValue(historyReport);
    vi.mocked(analysisApi.triggerMarketReview).mockResolvedValue({
      status: 'accepted',
      sendNotification: true,
      message: '大盘复盘任务已提交',
      taskId: 'task-1',
    });
    vi.mocked(analysisApi.getStatus).mockResolvedValue({
      taskId: 'task-1',
      status: 'completed',
      marketReviewReport: '市场复盘报告示例文本',
    });

    render(
      <MemoryRouter>
        <HomePage />
      </MemoryRouter>,
    );

    await screen.findByText('趋势维持强势');
    const dashboardScroll = screen.getByTestId('home-dashboard-scroll');
    const scrollToMock = vi.fn(function scrollTo(this: HTMLElement, options?: ScrollToOptions) {
      if (typeof options?.top === 'number') {
        this.scrollTop = options.top;
      }
    });
    Object.defineProperty(dashboardScroll, 'scrollTo', {
      configurable: true,
      value: scrollToMock,
    });
    dashboardScroll.scrollTop = 480;

    fireEvent.click(screen.getByRole('button', { name: '大盘复盘' }));

    await waitFor(() => {
      expect(scrollToMock).toHaveBeenCalledWith({ top: 0, behavior: 'smooth' });
    });
    expect(dashboardScroll.scrollTop).toBe(0);
    expect(await screen.findByText('大盘复盘已完成')).toBeInTheDocument();
  });

  it('keeps market review results in the main dashboard scroll area', async () => {
    vi.mocked(historyApi.getList).mockResolvedValue({
      total: 0,
      page: 1,
      limit: 20,
      items: [],
    });
    vi.mocked(analysisApi.triggerMarketReview).mockResolvedValue({
      status: 'accepted',
      sendNotification: true,
      message: '大盘复盘任务已提交',
      taskId: 'task-1',
    });
    vi.mocked(analysisApi.getStatus).mockResolvedValue({
      taskId: 'task-1',
      status: 'completed',
      marketReviewReport: [
        '# A股市场复盘',
        '',
        '> 市场情绪修复',
        '',
        '## 指数概览',
        '',
        '| 指数 | 表现 |',
        '| --- | --- |',
        '| 上证指数 | 震荡走强 |',
        '',
        '## 风险提示',
        '',
        '- 资金回流核心资产',
      ].join('\n'),
      marketReviewPayload: {
        kind: 'market_review',
        region: 'cn',
        title: 'A股市场复盘',
        breadth: {
          upCount: 3200,
          downCount: 1700,
          limitUpCount: 60,
          limitDownCount: 8,
          totalAmount: 9800,
          turnoverUnit: '亿',
        },
        indices: [
          {
            code: '000001',
            name: '上证指数',
            current: 3150.2,
            changePct: 0.62,
            high: 3168.4,
            low: 3120.8,
          },
        ],
        sections: [
          {
            key: 'index_overview',
            title: '指数概览',
            markdown: '| 指数 | 表现 |\n| --- | --- |\n| 上证指数 | 震荡走强 |',
          },
          {
            key: 'risk',
            title: '风险提示',
            markdown: '- 资金回流核心资产',
          },
        ],
      },
    });

    render(
      <MemoryRouter>
        <HomePage />
      </MemoryRouter>,
    );

    fireEvent.click(await screen.findByRole('button', { name: '大盘复盘' }));

    const dashboardScroll = screen.getByTestId('home-dashboard-scroll');
    const marketReviewReport = await screen.findByTestId('market-review-report');
    expect(dashboardScroll).toContainElement(marketReviewReport);
    expect(marketReviewReport.className).not.toContain('max-h-64');
    expect(marketReviewReport.className).not.toContain('overflow-y-auto');
    expect(screen.getByRole('heading', { name: '结构化大盘数据' })).toBeInTheDocument();
    expect(screen.getByText('3200')).toBeInTheDocument();
    expect(screen.getByText('3150.2')).toBeInTheDocument();
    expect(marketReviewReport.querySelector('h2, h3')?.textContent).not.toBe('A股市场复盘');
    expect(screen.getByRole('heading', { name: '指数概览' })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: '风险提示' })).toBeInTheDocument();
    expect(screen.getAllByRole('table').length).toBeGreaterThanOrEqual(2);
    expect(screen.queryByText('# A股市场复盘')).not.toBeInTheDocument();
    expect(screen.queryByText('开始分析')).not.toBeInTheDocument();
  });

  it('shows first-run setup gaps and links to settings', async () => {
    vi.mocked(historyApi.getList).mockResolvedValue({
      total: 0,
      page: 1,
      limit: 20,
      items: [],
    });
    vi.mocked(systemConfigApi.getSetupStatus).mockResolvedValue({
      isComplete: false,
      readyForSmoke: false,
      requiredMissingKeys: ['llm_primary', 'stock_list'],
      nextStepKey: 'llm_primary',
      checks: [
        {
          key: 'llm_primary',
          title: 'LLM 主渠道',
          category: 'ai_model',
          required: true,
          status: 'needs_action',
          message: '缺少主模型配置',
        },
        {
          key: 'stock_list',
          title: '自选股',
          category: 'base',
          required: true,
          status: 'needs_action',
          message: '缺少自选股',
        },
      ],
    });

    render(
      <MemoryRouter>
        <HomePage />
      </MemoryRouter>,
    );

    expect(await screen.findByText('基础配置未完成')).toBeInTheDocument();
    expect(screen.getByText(/LLM 主渠道、自选股/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: '去配置' }));
    expect(navigateMock).toHaveBeenCalledWith('/settings');
  });

  it('navigates to chat with report context when asking a follow-up question', async () => {
    vi.mocked(historyApi.getList).mockResolvedValue({
      total: 1,
      page: 1,
      limit: 20,
      items: [historyItem],
    });
    vi.mocked(historyApi.getDetail).mockResolvedValue(historyReport);

    render(
      <MemoryRouter>
        <HomePage />
      </MemoryRouter>,
    );

    const followUpButton = await screen.findByRole('button', { name: '追问 AI' });
    fireEvent.click(followUpButton);

    expect(navigateMock).toHaveBeenCalledWith(
      '/chat?stock=600519&name=%E8%B4%B5%E5%B7%9E%E8%8C%85%E5%8F%B0&recordId=1',
    );
  });

  it('opens and closes the mobile history drawer without changing dashboard styles', async () => {
    vi.mocked(historyApi.getList).mockResolvedValue({
      total: 0,
      page: 1,
      limit: 20,
      items: [],
    });

    const { container } = render(
      <MemoryRouter>
        <HomePage />
      </MemoryRouter>,
    );

    const trigger = await screen.findByRole('button', { name: '历史记录' });
    fireEvent.click(trigger);

    expect(container.querySelector('.page-drawer-overlay')).toBeTruthy();
    expect(container.querySelector('.dashboard-card')).toBeTruthy();

    fireEvent.click(container.querySelector('.fixed.inset-0.z-40') as HTMLElement);

    await waitFor(() => {
      expect(container.querySelector('.page-drawer-overlay')).toBeFalsy();
    });
  });

  it('keeps same-stock history range controls in empty result state and allows switching back', async () => {
    const staleReport = {
      ...historyReport,
      meta: {
        ...historyReport.meta,
        createdAt: '2020-01-01T08:00:00Z',
      },
    };

    vi.mocked(historyApi.getStockBarList).mockResolvedValue({
      total: 1,
      items: [
        {
          id: 1,
          stockCode: '600519',
          stockName: '贵州茅台',
          reportType: 'detailed',
          sentimentScore: 58,
          operationAdvice: '继续观察买点',
          analysisCount: 2,
          lastAnalysisTime: '2026-03-21T08:00:00Z',
        },
      ],
    });

    vi.mocked(historyApi.getList).mockImplementation((params: { stockCode?: string; startDate?: string } = {}) => {
      if (!Object.prototype.hasOwnProperty.call(params, 'stockCode')) {
        return Promise.resolve({
          total: 1,
          page: 1,
          limit: 20,
          items: [historyItem],
        });
      }

      return Promise.resolve({
        total: 0,
        page: 1,
        limit: 20,
        items: [],
      });
    });
    vi.mocked(historyApi.getDetail).mockResolvedValue(staleReport);

    render(
      <MemoryRouter>
        <HomePage />
      </MemoryRouter>,
    );

    const historyTrendButton = await screen.findByRole('button', { name: '历史趋势' });
    fireEvent.click(historyTrendButton);

    const range30Button = await screen.findByRole('button', { name: '近30天' });
    fireEvent.click(range30Button);

    await waitFor(() => {
      expect(screen.getByText('暂无更多同股历史分析')).toBeInTheDocument();
      expect(screen.getByRole('button', { name: '全部历史' })).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('button', { name: '全部历史' }));

    await waitFor(() => {
      expect(screen.queryByText('暂无更多同股历史分析')).not.toBeInTheDocument();
    });
    expect(screen.getAllByRole('button', { name: /贵州茅台/ }).length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText(/2次/)).toBeInTheDocument();

    const historyCalls = vi.mocked(historyApi.getList).mock.calls.filter((call) => call[0]?.stockCode === '600519');
    expect(historyCalls).toHaveLength(3);
    expect(historyCalls[1][0]).toHaveProperty('startDate');
    expect(historyCalls[2][0]).not.toHaveProperty('startDate');
  });

  it('renders active task panel content from dashboard state', async () => {
    const activeTask = {
      taskId: 'task-1',
      stockCode: '600519',
      stockName: '贵州茅台',
      status: 'processing' as const,
      progress: 45,
      message: '正在抓取最新行情',
      reportType: 'detailed',
      createdAt: '2026-03-18T08:00:00Z',
    };
    vi.mocked(historyApi.getList).mockResolvedValue({
      total: 0,
      page: 1,
      limit: 20,
      items: [],
    });
    vi.mocked(analysisApi.getTasks).mockResolvedValue({
      total: 1,
      pending: 0,
      processing: 1,
      tasks: [activeTask],
    });

    useStockPoolStore.setState({
      activeTasks: [activeTask],
    });

    render(
      <MemoryRouter>
        <HomePage />
      </MemoryRouter>,
    );

    expect(await screen.findByText('分析任务')).toBeInTheDocument();
    expect(screen.getByText('正在抓取最新行情')).toBeInTheDocument();
  });

  it('triggers reanalyze for the current report even if the search input has other text', async () => {
    vi.mocked(historyApi.getList).mockResolvedValue({
      total: 1,
      page: 1,
      limit: 20,
      items: [historyItem],
    });
    vi.mocked(historyApi.getDetail).mockResolvedValue(historyReport);
    vi.mocked(analysisApi.analyzeAsync).mockResolvedValue({
      taskId: 'task-re-1',
      status: 'pending',
    });

    render(
      <MemoryRouter>
        <HomePage />
      </MemoryRouter>,
    );

    // Wait for the report to load
    await screen.findByText('趋势维持强势');

    // Type something else in the search box
    const input = screen.getByPlaceholderText('输入股票代码或名称，如 600519、贵州茅台、AAPL');
    fireEvent.change(input, { target: { value: 'AAPL' } });

    // Click "Reanalyze"
    const reanalyzeButton = screen.getByRole('button', { name: '重新分析' });
    fireEvent.click(reanalyzeButton);

    // Verify that analyzeAsync is called with the report's stock code, not the search box text
    expect(analysisApi.analyzeAsync).toHaveBeenCalledWith(expect.objectContaining({
      stockCode: '600519',
      originalQuery: '600519',
      forceRefresh: true,
    }));
    expect(vi.mocked(analysisApi.analyzeAsync).mock.calls[0]?.[0]).not.toHaveProperty('reportLanguage');
  });

  it('passes the selected strategy when submitting stock analysis', async () => {
    vi.mocked(agentApi.getSkills).mockResolvedValue({
      default_skill_id: 'bull_trend',
      skills: [
        { id: 'bull_trend', name: '默认多头趋势', description: '趋势分析' },
        { id: 'growth_quality', name: '成长质量', description: '成长股分析' },
      ],
    });
    vi.mocked(historyApi.getList).mockResolvedValue({
      total: 0,
      page: 1,
      limit: 20,
      items: [],
    });
    vi.mocked(analysisApi.analyzeAsync).mockResolvedValue({
      taskId: 'task-strategy-1',
      status: 'pending',
    });

    render(
      <MemoryRouter>
        <HomePage />
      </MemoryRouter>,
    );

    fireEvent.click(await screen.findByRole('button', { name: '策略' }));
    fireEvent.click(screen.getByRole('menuitemradio', { name: /成长质量/ }));

    const input = screen.getByPlaceholderText('输入股票代码或名称，如 600519、贵州茅台、AAPL');
    fireEvent.change(input, { target: { value: '600519' } });
    fireEvent.click(screen.getByRole('button', { name: '快速分析' }));

    await waitFor(() => {
      expect(analysisApi.analyzeAsync).toHaveBeenCalledWith(expect.objectContaining({
        stockCode: '600519',
        skills: ['growth_quality'],
      }));
    });
  });

  it('submits deep analysis from the manual deep action', async () => {
    vi.mocked(historyApi.getList).mockResolvedValue({
      total: 0,
      page: 1,
      limit: 20,
      items: [],
    });
    vi.mocked(analysisApi.analyzeAsync).mockResolvedValue({
      taskId: 'task-deep-1',
      status: 'pending',
    });

    render(
      <MemoryRouter>
        <HomePage />
      </MemoryRouter>,
    );

    const input = screen.getByRole('textbox');
    fireEvent.change(input, { target: { value: '600519' } });
    fireEvent.click(await screen.findByRole('button', { name: '深度分析' }));

    await waitFor(() => {
      expect(analysisApi.analyzeAsync).toHaveBeenCalledWith(expect.objectContaining({
        stockCode: '600519',
        reportType: 'detailed',
        analysisDepth: 'deep',
      }));
    });
  });

  it('supports keyboard navigation in the strategy menu', async () => {
    vi.mocked(agentApi.getSkills).mockResolvedValue({
      default_skill_id: 'bull_trend',
      skills: [
        { id: 'bull_trend', name: '默认多头趋势', description: '趋势分析' },
        { id: 'growth_quality', name: '成长质量', description: '成长股分析' },
      ],
    });
    vi.mocked(historyApi.getList).mockResolvedValue({
      total: 0,
      page: 1,
      limit: 20,
      items: [],
    });

    render(
      <MemoryRouter>
        <HomePage />
      </MemoryRouter>,
    );

    const trigger = await screen.findByRole('button', { name: '策略' });
    fireEvent.keyDown(trigger, { key: 'ArrowDown' });

    const defaultOption = await screen.findByRole('menuitemradio', { name: /默认策略/ });
    await waitFor(() => {
      expect(defaultOption).toHaveFocus();
    });

    const menu = screen.getByRole('menu');
    fireEvent.keyDown(menu, { key: 'ArrowDown' });
    expect(screen.getByRole('menuitemradio', { name: /默认多头趋势/ })).toHaveFocus();

    fireEvent.keyDown(menu, { key: 'End' });
    expect(screen.getByRole('menuitemradio', { name: /成长质量/ })).toHaveFocus();

    fireEvent.keyDown(menu, { key: 'Escape' });
    await waitFor(() => {
      expect(screen.queryByRole('menu')).not.toBeInTheDocument();
    });
    expect(trigger).toHaveFocus();
  });

  it('renders market review history reports with a dedicated markdown view', async () => {
    vi.mocked(historyApi.getList).mockResolvedValue({
      total: 1,
      page: 1,
      limit: 20,
      items: [marketReviewHistoryItem],
    });
    vi.mocked(historyApi.getDetail).mockResolvedValue(marketReviewHistoryReport);
    vi.mocked(historyApi.getMarkdown).mockResolvedValue([
      '# 大盘复盘详情',
      '',
      '## 市场情绪与赚钱效应',
      '',
      '**赚钱效应** 改善',
      '',
      '## 行业/主题轮动',
      '',
      '| 方向 | 状态 |',
      '| --- | --- |',
      '| 半导体 | 轮动增强 |',
    ].join('\n'));

    render(
      <MemoryRouter>
        <HomePage />
      </MemoryRouter>,
    );

    await screen.findByText('大盘复盘摘要');
    expect(screen.queryByRole('heading', { name: '大盘复盘详情' })).not.toBeInTheDocument();
    expect(await screen.findByRole('heading', { name: '市场情绪与赚钱效应' })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: '行业/主题轮动' })).toBeInTheDocument();
    expect(screen.getByText('赚钱效应')).toBeInTheDocument();
    expect(screen.getByRole('table')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: '重新分析' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: '追问 AI' })).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: '重新复盘' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '历史趋势' })).toBeInTheDocument();
    expect(historyApi.getMarkdown).toHaveBeenCalledWith(marketReviewHistoryReport.meta.id);

    expect(analysisApi.analyzeAsync).not.toHaveBeenCalled();
    expect(navigateMock).not.toHaveBeenCalled();
  });

  it('clears live market review output when switching to a history report', async () => {
    vi.mocked(historyApi.getList).mockImplementation((params: { reportType?: string } = {}) => {
      if (params.reportType === 'market_review') {
        return Promise.resolve({
          total: 1,
          page: 1,
          limit: 10,
          items: [marketReviewHistoryItem],
        });
      }
      return Promise.resolve({
        total: 1,
        page: 1,
        limit: 20,
        items: [historyItem],
      });
    });
    vi.mocked(historyApi.getStockBarList).mockResolvedValue({
      total: 1,
      items: [
        {
          id: 1,
          stockCode: '600519',
          stockName: '贵州茅台',
          sentimentScore: 82,
          operationAdvice: '买入',
          analysisCount: 1,
          lastAnalysisTime: '2026-03-18T08:00:00Z',
          reportType: 'detailed',
        },
      ],
    });
    vi.mocked(historyApi.getDetail).mockImplementation((recordId: number) => {
      if (recordId === 2) {
        return Promise.resolve(marketReviewHistoryReport);
      }
      return Promise.resolve(historyReport);
    });
    vi.mocked(historyApi.getMarkdown).mockResolvedValue([
      '# 大盘复盘详情',
      '',
      '## 市场情绪与赚钱效应',
      '',
      '**赚钱效应** 改善',
      '',
      '## 行业/主题轮动',
      '',
      '| 方向 | 状态 |',
      '| --- | --- |',
      '| 半导体 | 轮动增强 |',
    ].join('\n'));
    vi.mocked(analysisApi.triggerMarketReview).mockResolvedValue({
      status: 'accepted',
      sendNotification: true,
      message: '大盘复盘任务已提交',
      taskId: 'task-1',
    });
    vi.mocked(analysisApi.getStatus).mockResolvedValue({
      taskId: 'task-1',
      status: 'completed',
      marketReviewReport: '市场复盘报告示例文本',
    });

    render(
      <MemoryRouter>
        <HomePage />
      </MemoryRouter>,
    );

    await screen.findByText('趋势维持强势');

    fireEvent.click(screen.getByRole('button', { name: '大盘复盘' }));

    await waitFor(() => {
      expect(screen.getByText('大盘复盘已完成')).toBeInTheDocument();
      expect(screen.getByText('市场复盘报告示例文本')).toBeInTheDocument();
    });

    const marketHistoryButton = await screen.findByRole('button', { name: /MARKET/ });
    fireEvent.click(marketHistoryButton);

    await waitFor(() => {
      expect(screen.queryByText('市场复盘报告示例文本')).not.toBeInTheDocument();
      expect(screen.queryByText('大盘复盘已完成')).not.toBeInTheDocument();
    });
    expect(await screen.findByText('大盘复盘摘要')).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: '市场情绪与赚钱效应' })).toBeInTheDocument();
    expect(vi.mocked(historyApi.getDetail)).toHaveBeenCalledWith(2);
  });
});
