import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { analysisApi, DuplicateTaskError } from '../../api/analysis';
import { agentApi } from '../../api/agent';
import { historyApi } from '../../api/history';
import { marketWorkspaceApi } from '../../api/marketWorkspace';
import { platformApi, type PlatformWatchlistRadarItem, type PlatformWatchlistRadarResponse } from '../../api/platform';
import { stocksApi } from '../../api/stocks';
import type { BasicStockSnapshot } from '../../api/stocks';
import { systemConfigApi } from '../../api/systemConfig';
import { UiLanguageProvider } from '../../contexts/UiLanguageContext';
import { useStockPoolStore } from '../../stores';
import type { RunFlowSnapshot } from '../../types/runFlow';
import { getReportText, normalizeReportLanguage } from '../../utils/reportLanguage';
import { UI_LANGUAGE_STORAGE_KEY } from '../../utils/uiLanguage';
import HomePage, { localizeGeneratedText } from '../HomePage';

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

vi.mock('../../api/marketWorkspace', () => ({
  marketWorkspaceApi: { getHome: vi.fn() },
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
    kronosForecast: vi.fn(),
    history: vi.fn(),
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
    localModelStatus: vi.fn(),
    current: vi.fn(),
    account: vi.fn(),
    listApiKeys: vi.fn(),
    requestRegistrationCode: vi.fn(),
    register: vi.fn(),
    login: vi.fn(),
    logout: vi.fn(),
    saveApiKey: vi.fn(),
    watchlist: vi.fn(),
    addWatchlistItem: vi.fn(),
    removeWatchlistItem: vi.fn(),
    refreshWatchlist: vi.fn(),
    watchlistRadar: vi.fn(),
    runWatchlistRadar: vi.fn(),
    watchlistRadarHistory: vi.fn(),
    watchlistAlertRules: vi.fn(),
    saveWatchlistAlertRule: vi.fn(),
    deleteWatchlistAlertRule: vi.fn(),
    saveSnapshotToHistory: vi.fn(),
  },
}));

const makeRadarItem = (overrides: Partial<PlatformWatchlistRadarItem>): PlatformWatchlistRadarItem => ({
  stockCode: 'AAPL',
  stockName: 'Apple Inc.',
  market: 'us',
  routeLane: 'us_market_data',
  currentPrice: 210,
  changePercent: 0,
  ma20: 205,
  volumeChangePercent: 0,
  signalScore: 60,
  freshness: 'fresh',
  degradationStatus: 'ok',
  warningCodes: [],
  aiUsed: false,
  status: 'ok',
  sourceStatus: 'no_traceable_source',
  researchBrief: {
    state: 'wait_for_confirmation',
    priorityScore: 60,
    dataConfidence: 'high',
    evidenceCodes: ['usable_data'],
    nextWatch: { type: 'hold_above_ma20', value: 205 },
    invalidation: { type: 'lose_ma20', value: 205 },
    aiUsed: false,
  },
  events: [],
  suggestedAlerts: [],
  ...overrides,
});

const makeRadarResponse = (
  userId: number,
  items: PlatformWatchlistRadarItem[],
  degraded = 0,
): PlatformWatchlistRadarResponse => {
  const ranked = items
    .filter((item) => typeof item.changePercent === 'number')
    .slice()
    .sort((left, right) => (right.changePercent ?? 0) - (left.changePercent ?? 0));
  const digestItem = (item: PlatformWatchlistRadarItem) => ({
    stockCode: item.stockCode,
    stockName: item.stockName,
    market: item.market,
    state: item.researchBrief.state,
    priorityScore: item.researchBrief.priorityScore,
    changePercent: item.changePercent,
    signalScore: item.signalScore,
    dataConfidence: item.researchBrief.dataConfidence,
  });
  return {
    userId,
    plan: 'free',
    visibleLimit: 10,
    totalWatchlist: items.length,
    processed: items.length,
    hiddenCount: 0,
    degraded,
    summary: {
      strongest: ranked[0] ? { stockCode: ranked[0].stockCode, stockName: ranked[0].stockName, changePercent: ranked[0].changePercent } : null,
      weakest: ranked.at(-1) ? { stockCode: ranked.at(-1)!.stockCode, stockName: ranked.at(-1)!.stockName, changePercent: ranked.at(-1)!.changePercent } : null,
      eventCount: items.reduce((total, item) => total + item.events.length, 0),
      riskCount: degraded,
      sourceEventCount: items.reduce((total, item) => total + item.events.filter((event) => event.type === 'source_update').length, 0),
    },
    dailyDigest: {
      strongConfirmation: items.filter((item) => item.researchBrief.state === 'strong_confirmation').map(digestItem).slice(0, 3),
      riskReview: items.filter((item) => item.researchBrief.state === 'risk_review').map(digestItem).slice(0, 3),
      waitForConfirmation: items.filter((item) => item.researchBrief.state === 'wait_for_confirmation').map(digestItem).slice(0, 3),
      dataHealth: {
        fresh: items.filter((item) => item.freshness === 'fresh' && item.status === 'ok').length,
        cached: items.filter((item) => item.freshness === 'cached' && item.status === 'ok').length,
        stale: items.filter((item) => item.freshness === 'stale' || item.warningCodes.length > 0).length,
        unavailable: items.filter((item) => item.freshness === 'unavailable').length,
      },
      upgradeBoundary: 'same_research_flow_better_sources_and_automation',
      aiUsed: false,
    },
    items,
    events: items.flatMap((item) => item.events),
    generatedAt: '2026-07-11T09:30:00Z',
    aiUsed: false,
    analysisBoundary: 'information_only_not_investment_advice',
  };
};

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

const openHistoryRecord = async (recordId: number) => {
  fireEvent.click(await screen.findByTestId(`history-center-item-${recordId}`));
};

const openQuickAnalysisFromCurrentSnapshot = async () => {
  await screen.findByTestId('basic-query-compact-overview');
  fireEvent.click(screen.getAllByRole('button', { name: /快速分析|Quick analysis|Open quick analysis/ })[0]);
  await screen.findByTestId('basic-query-mode-banner');
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
  it('localizes parameterized no-AI backend text in Chinese', () => {
    expect(
      localizeGeneratedText('Watch whether price can hold above MA20 190 after the next refresh.', 'zh'),
    ).toBe('观察价格能否在下次刷新后守住 MA20 190。');
    expect(
      localizeGeneratedText(
        'No-AI quick view for us_equity: quote freshness is cached; realtime news, filings, external search, and investment advice are not included.',
        'zh',
      ),
    ).toBe('未用 AI 的美股快速视图：行情新鲜度为缓存；不包含实时新闻、公告文件、外部搜索或投资建议。');
    expect(
      localizeGeneratedText(
        'No realtime news source is enabled in free no-AI mode for us_equity. No AI or public search was used.',
        'zh',
      ),
    ).toBe('免费未用 AI 模式暂未启用美股实时新闻源；未使用 AI 或公共搜索。');
    expect(
      localizeGeneratedText(
        'Premium can use configured API feeds for broader coverage and higher refresh limits; the visible module structure remains the same.',
        'zh',
      ),
    ).toBe('高级版可使用已配置的 API 数据源扩大覆盖范围并提高刷新额度；页面模块结构保持一致。');
    expect(
      localizeGeneratedText('Information and data only; not investment advice or a trading instruction.', 'zh'),
    ).toBe('仅提供资讯和数据，不构成投资建议或交易指令。');
    expect(localizeGeneratedText('range_watch', 'zh')).toBe('区间观察');
    expect(localizeGeneratedText('Range-watch preview', 'zh')).toBe('区间观察预览');
    expect(localizeGeneratedText('TencentFetcher', 'zh')).toBe('腾讯行情历史');
    expect(localizeGeneratedText('a_stock_data_skill_adapter', 'zh')).toBe('A股数据适配器');
  });

  beforeEach(() => {
    vi.clearAllMocks();
    navigateMock.mockReset();
    window.localStorage.clear();
    window.sessionStorage.clear();
    useStockPoolStore.getState().resetDashboardState();
    vi.mocked(analysisApi.getTasks).mockResolvedValue({
      total: 0,
      pending: 0,
      processing: 0,
      tasks: [],
    });
    vi.mocked(agentApi.getSkills).mockResolvedValue({ skills: [], default_skill_id: '' });
    vi.mocked(marketWorkspaceApi.getHome).mockRejectedValue(new Error('V116 disabled in legacy test'));
    vi.mocked(platformApi.status).mockResolvedValue({ platformAuthEnabled: false });
    vi.mocked(platformApi.localModelStatus).mockResolvedValue({
      enabled: true,
      reachable: true,
      ready: true,
      quickReady: true,
      deepReady: true,
      reason: 'ready',
      runtime: 'ollama',
      quickModel: 'quick-model',
      deepModel: 'deep-model',
      quickModelAvailable: true,
      deepModelAvailable: true,
      maxConcurrent: 1,
    });
    vi.mocked(platformApi.current).mockResolvedValue(null);
    vi.mocked(platformApi.account).mockRejectedValue(new Error('not signed in'));
    vi.mocked(platformApi.listApiKeys).mockResolvedValue([]);
    vi.mocked(platformApi.requestRegistrationCode).mockResolvedValue({
      email: 'user@example.com',
      sent: true,
      expiresInSeconds: 600,
      devCode: '123456',
      message: 'Local verification code generated',
    });
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
    vi.mocked(platformApi.watchlistRadar).mockResolvedValue(makeRadarResponse(0, []));
    vi.mocked(platformApi.runWatchlistRadar).mockResolvedValue({
      ...makeRadarResponse(0, []),
      runId: 1,
      triggeredAlerts: [],
    });
    vi.mocked(platformApi.watchlistRadarHistory).mockResolvedValue({ userId: 0, total: 0, items: [], aiUsed: false });
    vi.mocked(platformApi.watchlistAlertRules).mockResolvedValue({
      userId: 0,
      plan: 'free',
      limit: 3,
      total: 0,
      remaining: 3,
      items: [],
      aiUsed: false,
    });
    vi.mocked(platformApi.saveWatchlistAlertRule).mockResolvedValue({
      userId: 0,
      plan: 'free',
      limit: 3,
      total: 0,
      remaining: 3,
      items: [],
      aiUsed: false,
    });
    vi.mocked(platformApi.deleteWatchlistAlertRule).mockResolvedValue({
      userId: 0,
      plan: 'free',
      limit: 3,
      total: 0,
      remaining: 3,
      items: [],
      aiUsed: false,
    });
    vi.mocked(platformApi.saveSnapshotToHistory).mockResolvedValue({
      recordId: 0,
      stockCode: 'AAPL',
      reportType: 'basic_snapshot',
      savedToHistory: true,
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
    vi.mocked(stocksApi.history).mockResolvedValue({
      stockCode: 'AAPL',
      stockName: 'Apple Inc.',
      period: 'daily',
      source: 'yahoo_chart_history',
      data: Array.from({ length: 30 }, (_, index) => ({
        date: `2026-06-${String(index + 1).padStart(2, '0')}`,
        open: 100 + index,
        high: 103 + index,
        low: 98 + index,
        close: 101 + index,
        volume: 1_000_000 + index * 20_000,
        amount: null,
        changePercent: index === 0 ? 0 : 0.8,
      })),
    });
    vi.mocked(stocksApi.prewarm).mockResolvedValue({
      requested: 4,
      warmed: 0,
      degraded: 4,
      symbols: ['600519', 'AAPL', 'HK00700', 'BTC-USD'],
      results: {},
      elapsedMs: 1,
      aiUsed: false,
    });
    vi.mocked(stocksApi.kronosForecast).mockResolvedValue({
      stockCode: 'AAPL',
      stockName: 'Apple Inc.',
      market: 'us',
      mode: 'kronos_sandbox',
      status: 'model_unavailable',
      provider: 'kronos',
      source: 'local_kline_rules_kronos_unavailable',
      horizon: 'next_5_bars',
      lookback: 120,
      direction: 'upside_bias',
      confidence: 64,
      support: 190,
      resistance: 205,
      adapterStatus: 'Kronos adapter ready; model not invoked because dependencies are missing: torch, model.',
      enabled: true,
      kronosModelUsed: false,
      modelId: 'NeoQuasar/Kronos-small',
      tokenizerId: 'NeoQuasar/Kronos-Tokenizer-base',
      device: 'auto',
      dependencyStatus: { pandas: true, torch: false, einops: true, safetensors: true, huggingfaceHub: true, model: false },
      missingDependencies: ['torch', 'model'],
      runtimeMetrics: {
        resolvedDevice: 'not_run',
        modelCacheHit: false,
        modelLoadMs: 0,
        inferenceMs: 0,
        peakVramMb: 0,
        inputBars: 0,
        forecastBars: 0,
      },
      scenarios: [
        {
          label: 'Upside-biased preview',
          direction: 'upside_bias',
          probability: 64,
          trigger: 'Hold above support.',
          detail: 'Local fallback.',
        },
      ],
      forecastPoints: [
        { timestamp: '2026-07-07', close: 201 },
        { timestamp: '2026-07-08', close: 202 },
      ],
      backtestSummary: { records: 1, evaluated: 1, hits: 1, hitRate: 1, lastEvaluatedAt: '2026-07-06T09:00:00' },
      warnings: [
        'Kronos market data fetch timed out; local rules fallback used.',
        'KRONOS_ENABLED is false; local rules fallback only.',
        'K-line context is short; confidence is capped.',
        'Kronos model unavailable; missing dependencies: torch, model.',
      ],
      elapsedMs: 12,
      cacheHit: false,
      recordId: 'unit-kronos',
      aiUsed: false,
      publicSearchUsed: false,
      boundary: 'Experimental model preview; information analysis only; not investment advice.',
    });
    vi.mocked(systemConfigApi.getSetupStatus).mockResolvedValue({
      isComplete: true,
      readyForSmoke: true,
      requiredMissingKeys: [],
      nextStepKey: null,
      checks: [],
    });
  });

  it('shows V116 market data before query and preserves a guest price-alert draft for registration', async () => {
    window.localStorage.setItem(UI_LANGUAGE_STORAGE_KEY, 'zh');
    vi.mocked(platformApi.status).mockResolvedValue({ platformAuthEnabled: true });
    vi.mocked(platformApi.current).mockResolvedValue(null);
    vi.mocked(marketWorkspaceApi.getHome).mockResolvedValue({
      asOf: '2026-07-13T01:30:00Z', aiUsed: false, informationalOnly: true,
      markets: [
        { market: 'cn', sessionState: 'unknown', displayMode: 'latest_available', rankingScope: 'configured_universe', selectionBasis: 'turnover_then_absolute_change', indices: [], sources: [], warnings: [], attention: [{ symbol: '600519.SH', name: '贵州茅台', market: 'cn', currentPrice: 1188.8, changePercent: -1.5, sourceState: { source: 'cn_quote', status: 'fresh' } }] },
        { market: 'hk', sessionState: 'unknown', displayMode: 'latest_available', rankingScope: 'configured_universe', selectionBasis: 'turnover_then_absolute_change', indices: [], sources: [], warnings: [], attention: [] },
        { market: 'us', sessionState: 'unknown', displayMode: 'latest_available', rankingScope: 'configured_universe', selectionBasis: 'turnover_then_absolute_change', indices: [], sources: [], warnings: [], attention: [] },
      ],
    });

    render(<UiLanguageProvider><MemoryRouter><HomePage /></MemoryRouter></UiLanguageProvider>);
    expect(await screen.findByRole('heading', { name: '市场焦点' })).toBeInTheDocument();
    const queryToolbar = screen.getByTestId('home-query-toolbar');
    const marketHome = screen.getByTestId('public-market-home-v116');
    expect(queryToolbar.compareDocumentPosition(marketHome) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(screen.getByTestId('home-analysis-workspace')).toHaveClass('hidden');
    expect(screen.queryByTestId('guest-query-entry')).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: '为 贵州茅台 设置到价提醒' }));
    fireEvent.change(screen.getByRole('spinbutton', { name: '到价阈值' }), { target: { value: '1200' } });
    fireEvent.click(screen.getByRole('button', { name: '保存到价提醒' }));

    expect(await screen.findByText('注册后可保存这条私有到价提醒；登录后仍需再次确认。')).toBeInTheDocument();
    expect(screen.getByTestId('platform-auth-register-tab')).toHaveClass('bg-primary');
    expect(screen.getByTestId('platform-registration-benefit-v116')).toHaveTextContent('注册后每周赠送 5 次快速分析及 1 次深度分析');
    expect(window.sessionStorage.getItem('dsa_v116_pending_price_alert')).toContain('600519.SH');
  });

  it('does not restore a stale private account load after logout', async () => {
    let resolveAccount: ((value: Awaited<ReturnType<typeof platformApi.account>>) => void) | undefined;
    const pendingAccount = new Promise<Awaited<ReturnType<typeof platformApi.account>>>((resolve) => {
      resolveAccount = resolve;
    });
    const session = {
      user: { id: 71, email: 'race-a@example.com', role: 'user', plan: 'free', status: 'active' },
      quota: { userId: 71, plan: 'free', weeklyLimit: 5, used: 0, remaining: 5, periodStart: '2026-07-06' },
    };
    vi.mocked(platformApi.status).mockResolvedValue({ platformAuthEnabled: true });
    vi.mocked(platformApi.current).mockResolvedValue(session);
    vi.mocked(platformApi.account).mockReturnValue(pendingAccount);
    vi.mocked(platformApi.watchlist).mockResolvedValue({
      userId: 71,
      total: 1,
      items: [{ id: 1, stockCode: 'AAPL', market: 'us' }],
      aiUsed: false,
    });
    vi.mocked(platformApi.watchlistRadarHistory).mockResolvedValue({
      userId: 71,
      total: 1,
      items: [{ id: 1, plan: 'free', processed: 1, eventCount: 0, riskCount: 0, sourceEventCount: 0, triggeredCount: 0 }],
      aiUsed: false,
    });
    vi.mocked(platformApi.watchlistAlertRules).mockResolvedValue({
      userId: 71,
      plan: 'free',
      limit: 3,
      total: 1,
      remaining: 2,
      items: [{ id: 9, stockCode: 'AAPL', ruleType: 'price_move', threshold: 3, enabled: true }],
      aiUsed: false,
    });

    render(
      <UiLanguageProvider>
        <MemoryRouter>
          <HomePage />
        </MemoryRouter>
      </UiLanguageProvider>,
    );

    expect(await screen.findByTestId('platform-signed-in-panel')).toHaveTextContent('race-a@example.com');
    fireEvent.click(screen.getByTestId('platform-logout-button'));
    await waitFor(() => expect(screen.queryByTestId('platform-signed-in-panel')).not.toBeInTheDocument());

    resolveAccount?.({
      user: session.user,
      quota: session.quota,
      quotaBuckets: [],
      apiKeys: [],
      recommendedQueryMode: 'platform',
    });
    await new Promise((resolve) => window.setTimeout(resolve, 50));

    expect(screen.queryByText('race-a@example.com')).not.toBeInTheDocument();
    expect(screen.queryByText('AAPL 涨跌达到 3%')).not.toBeInTheDocument();
  });

  it('clears private state and reports a localized error when logout confirmation fails', async () => {
    window.localStorage.setItem(UI_LANGUAGE_STORAGE_KEY, 'zh');
    const session = {
      user: { id: 72, email: 'logout-failure@example.com', role: 'user', plan: 'free', status: 'active' },
      quota: { userId: 72, plan: 'free', weeklyLimit: 5, used: 0, remaining: 5, periodStart: '2026-07-06' },
    };
    vi.mocked(platformApi.status).mockResolvedValue({ platformAuthEnabled: true });
    vi.mocked(platformApi.current).mockResolvedValue(session);
    vi.mocked(platformApi.account).mockResolvedValue({
      user: session.user,
      quota: session.quota,
      quotaBuckets: [],
      apiKeys: [],
      recommendedQueryMode: 'platform',
    });
    vi.mocked(platformApi.watchlist).mockResolvedValue({ userId: 72, total: 0, items: [], aiUsed: false });
    vi.mocked(platformApi.watchlistRadarHistory).mockResolvedValue({ userId: 72, total: 0, items: [], aiUsed: false });
    vi.mocked(platformApi.watchlistAlertRules).mockResolvedValue({
      userId: 72,
      plan: 'free',
      limit: 3,
      total: 0,
      remaining: 3,
      items: [],
      aiUsed: false,
    });
    vi.mocked(platformApi.logout).mockRejectedValue(new Error('local logout unavailable'));

    render(
      <UiLanguageProvider>
        <MemoryRouter>
          <HomePage />
        </MemoryRouter>
      </UiLanguageProvider>,
    );

    expect(await screen.findByTestId('platform-signed-in-panel')).toHaveTextContent('logout-failure@example.com');
    fireEvent.click(screen.getByTestId('platform-logout-button'));

    await waitFor(() => expect(screen.queryByTestId('platform-signed-in-panel')).not.toBeInTheDocument());
    expect(screen.getByTestId('platform-auth-error')).toHaveTextContent('本地退出确认失败，请刷新页面检查登录状态');
  });

  it('rejects private watchlist payloads owned by a different session user', async () => {
    const session = {
      user: { id: 81, email: 'owner-a@example.com', role: 'user', plan: 'free', status: 'active' },
      quota: { userId: 81, plan: 'free', weeklyLimit: 5, used: 0, remaining: 5, periodStart: '2026-07-06' },
    };
    vi.mocked(platformApi.status).mockResolvedValue({ platformAuthEnabled: true });
    vi.mocked(platformApi.current).mockResolvedValue(session);
    vi.mocked(platformApi.account).mockResolvedValue({
      user: session.user,
      quota: session.quota,
      quotaBuckets: [],
      apiKeys: [],
      recommendedQueryMode: 'platform',
    });
    vi.mocked(platformApi.watchlist).mockResolvedValue({
      userId: 82,
      total: 1,
      items: [{ id: 1, stockCode: 'MSFT', market: 'us' }],
      aiUsed: false,
    });
    vi.mocked(platformApi.watchlistRadarHistory).mockResolvedValue({ userId: 82, total: 0, items: [], aiUsed: false });
    vi.mocked(platformApi.watchlistAlertRules).mockResolvedValue({
      userId: 82,
      plan: 'free',
      limit: 3,
      total: 0,
      remaining: 3,
      items: [],
      aiUsed: false,
    });

    render(
      <UiLanguageProvider>
        <MemoryRouter>
          <HomePage />
        </MemoryRouter>
      </UiLanguageProvider>,
    );

    expect(await screen.findByTestId('platform-signed-in-panel')).toHaveTextContent('owner-a@example.com');
    await new Promise((resolve) => window.setTimeout(resolve, 50));
    fireEvent.click(screen.getByTestId('platform-personal-workspace-toggle'));
    expect(screen.getByTestId('platform-watchlist-panel')).not.toHaveTextContent('MSFT');
  });

  it('shows a guest-first query entry before login', async () => {
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

    const entry = await screen.findByTestId('guest-query-entry');
    expect(entry).toHaveTextContent('无需登录');
    expect(entry).toHaveTextContent('AAPL');
    expect(entry).toHaveTextContent('600519');
    expect(entry).toHaveTextContent('00700.HK');
    expect(entry).toHaveTextContent('BTC-USD');
    expect(screen.getByTestId('guest-example-AAPL')).toBeInTheDocument();
    expect(screen.getByTestId('guest-example-600519')).toBeInTheDocument();
    expect(screen.getByTestId('guest-example-00700.HK')).toBeInTheDocument();
    expect(screen.getByTestId('guest-example-BTC-USD')).toBeInTheDocument();
    expect(screen.getByTestId('history-center-filters')).toBeInTheDocument();
  });

  it('keeps the guest-first query entry fully English in English mode', async () => {
    window.localStorage.setItem(UI_LANGUAGE_STORAGE_KEY, 'en');
    vi.mocked(historyApi.getList).mockResolvedValue({ total: 0, page: 1, limit: 20, items: [] });

    render(
      <UiLanguageProvider>
        <MemoryRouter>
          <HomePage />
        </MemoryRouter>
      </UiLanguageProvider>,
    );

    const entry = await screen.findByTestId('guest-query-entry');
    expect(entry).toHaveTextContent('Check one stock for free before deciding whether to sign in');
    expect(entry).toHaveTextContent('Enter a symbol to view quotes, moving averages, volume-price context, signal scores and watch points.');
    expect(entry).not.toHaveTextContent('先免费查一只标的');
    expect(entry).not.toHaveTextContent('输入代码即可查看行情');
  });

  it('submits the visible free platform API trial as fast platform analysis', async () => {
    const session = {
      user: { id: 93, email: 'v93-free@example.com', role: 'user', plan: 'free', status: 'active' },
      quota: { userId: 93, plan: 'free', weeklyLimit: 5, used: 0, remaining: 5, periodStart: '2026-07-06' },
    };
    vi.mocked(platformApi.status).mockResolvedValue({ platformAuthEnabled: true });
    vi.mocked(platformApi.current).mockResolvedValue(session);
    vi.mocked(platformApi.account).mockResolvedValue({
      ...session,
      quotaBuckets: [
        { ...session.quota, quotaBucket: 'basic_query', weeklyLimit: null, remaining: null },
        { ...session.quota, quotaBucket: 'ai_quick' },
        { ...session.quota, quotaBucket: 'ai_quick_user_key', weeklyLimit: 25, remaining: 25 },
        { ...session.quota, quotaBucket: 'ai_deep', weeklyLimit: 0, remaining: 0 },
        { ...session.quota, quotaBucket: 'ai_local', weeklyLimit: 50, remaining: 50 },
      ],
      apiKeys: [],
      recommendedQueryMode: 'platform',
    });
    vi.mocked(historyApi.getList).mockResolvedValue({ total: 0, page: 1, limit: 20, items: [] });
    vi.mocked(stocksApi.snapshot).mockResolvedValue({
      stockCode: 'AAPL',
      stockName: 'Apple Inc.',
      market: 'us',
      quote: { currentPrice: 200, changePercent: 1.5, source: 'unit_quote', freshness: 'fresh' },
      indicators: { ma5: 198, ma20: 190 },
      aiUsed: false,
    } as unknown as BasicStockSnapshot);
    vi.mocked(analysisApi.analyzeAsync).mockResolvedValue({ taskId: 'task-v93-trial', status: 'pending' });

    render(
      <MemoryRouter>
        <HomePage />
      </MemoryRouter>,
    );

    fireEvent.change(await screen.findByPlaceholderText('输入股票代码或名称，如 600519、贵州茅台、AAPL'), {
      target: { value: 'AAPL' },
    });
    fireEvent.click(screen.getByRole('button', { name: '查询' }));
    await screen.findByTestId('basic-query-snapshot');

    const trial = await screen.findByTestId('free-platform-api-trial-action');
    expect(trial).toHaveTextContent('5');
    fireEvent.click(trial);

    await waitFor(() => {
      expect(analysisApi.analyzeAsync).toHaveBeenCalledWith(expect.objectContaining({
        stockCode: 'AAPL',
        analysisDepth: 'fast',
        reportType: 'brief',
        apiKeyMode: 'platform',
      }));
    });
    expect(screen.getByTestId('free-platform-api-trial-status')).toHaveTextContent('平台 API 试用已提交');
  });

  it('shows useful same-symbol changes on the second free query', async () => {
    vi.mocked(historyApi.getList).mockResolvedValue({ total: 0, page: 1, limit: 20, items: [] });
    vi.mocked(stocksApi.snapshot)
      .mockResolvedValueOnce({
        stockCode: 'AAPL',
        stockName: 'Apple Inc.',
        market: 'us',
        quote: { currentPrice: 200, changePercent: 1.5, source: 'unit_quote', freshness: 'fresh' },
        indicators: { ma5: 198, ma20: 190, volumePriceSignal: 'price_volume_confirmed' },
        intelligence: {
          mode: 'no_ai_low_cost',
          aiUsed: false,
          signalScore: { score: 64, label: 'positive', summary: 'unit', components: [], source: 'unit' },
          items: [],
        },
        warnings: [],
        aiUsed: false,
      } as unknown as BasicStockSnapshot)
      .mockResolvedValueOnce({
        stockCode: 'AAPL',
        stockName: 'Apple Inc.',
        market: 'us',
        quote: { currentPrice: 205, changePercent: 2.4, source: 'unit_quote', freshness: 'stale' },
        indicators: { ma5: 202, ma20: 206, volumePriceSignal: 'neutral' },
        intelligence: {
          mode: 'no_ai_low_cost',
          aiUsed: false,
          signalScore: { score: 51, label: 'neutral', summary: 'unit', components: [], source: 'unit' },
          items: [],
        },
        warnings: [{ code: 'quote_stale', severity: 'warning', message: 'stale' }],
        aiUsed: false,
      } as unknown as BasicStockSnapshot);

    render(
      <MemoryRouter>
        <HomePage />
      </MemoryRouter>,
    );

    const input = await screen.findByPlaceholderText('输入股票代码或名称，如 600519、贵州茅台、AAPL');
    fireEvent.change(input, { target: { value: 'AAPL' } });
    fireEvent.click(screen.getByRole('button', { name: '查询' }));
    expect(await screen.findByTestId('same-symbol-query-change')).toHaveTextContent('已建立首次对比基线');

    fireEvent.click(screen.getByRole('button', { name: '查询' }));
    await waitFor(() => {
      const comparison = screen.getByTestId('same-symbol-query-change');
      expect(comparison).toHaveTextContent('相比上次查询发生了什么变化');
      expect(comparison).toHaveTextContent('价格 +5');
      expect(comparison).toHaveTextContent('信号评分 -13');
      expect(comparison).toHaveTextContent('MA20 上方 → MA20 下方');
      expect(comparison).toHaveTextContent('新鲜 → 过期');
      expect(comparison).toHaveTextContent('风险提醒 +1');
    });
  });

  it('lets guests query first and keeps only the top account entry for login and register', async () => {
    vi.mocked(platformApi.status).mockResolvedValue({ platformAuthEnabled: true });
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
        changePercent: 1.5,
        source: 'unit_quote',
        freshness: 'fresh',
      },
      indicators: { ma5: 198, ma20: 190 },
      intelligence: {
        mode: 'no_ai_low_cost',
        aiUsed: false,
        boundary: 'Information analysis only; not investment advice.',
        retentionBrief: {
          headline: 'AAPL quick read: +1.5%, above MA20 190.',
          whyItMatters: 'Free no-AI checklist.',
          supportResistance: 'support 190; resistance 200',
          nextSteps: ['Refresh once', 'Compare with QQQ', 'Use deep analysis for filings'],
          upgradeHint: 'Login to save history and watchlist.',
          boundary: 'Information analysis only; not investment advice.',
          source: 'no_ai_retention_rules',
        },
        items: [],
      },
      diagnostics: {
        elapsedMs: 5,
        quoteElapsedMs: 2,
        historyElapsedMs: 3,
        cache: { quote: 'miss', history: 'miss' },
        sources: { quote: 'unit_quote', history: 'unit_history' },
        freshness: { quote: 'fresh', history: 'fresh' },
        fallback: { quote: 'live', history: 'live' },
        routeLane: 'us_market_data',
        performance: { status: 'ok' },
      },
      aiUsed: false,
    });

    render(
      <MemoryRouter>
        <HomePage />
      </MemoryRouter>,
    );

    fireEvent.click(await screen.findByTestId('guest-example-AAPL'));

    await waitFor(() => {
      expect(stocksApi.snapshot).toHaveBeenCalledWith('AAPL');
    });
    expect(await screen.findByTestId('basic-query-snapshot')).toHaveTextContent('Apple Inc.');
    expect(screen.queryByTestId('guest-conversion-guide')).not.toBeInTheDocument();
    expect(screen.queryByTestId('guest-guide-login')).not.toBeInTheDocument();
    expect(screen.queryByTestId('guest-guide-register')).not.toBeInTheDocument();
    expect(screen.getByTestId('basic-query-snapshot')).toHaveTextContent('200');

    fireEvent.click(screen.getByTestId('platform-auth-register-tab'));

    expect(screen.getByTestId('platform-auth-register-tab')).toHaveClass('bg-primary');
    expect(screen.getByTestId('platform-auth-email')).toBeInTheDocument();
    expect(screen.getByTestId('platform-auth-password')).toBeInTheDocument();
    expect(screen.getByTestId('platform-auth-confirm-password')).toBeInTheDocument();
    expect(screen.getByTestId('platform-auth-verification-code')).toBeInTheDocument();
    expect(screen.getByTestId('platform-auth-send-code')).toHaveTextContent('发送验证码');
    expect(screen.getByTestId('platform-auth-submit')).toHaveTextContent('注册');
    expect(screen.getByTestId('platform-auth-submit')).toBeEnabled();
    expect(screen.getByTestId('platform-auth-email')).toHaveAttribute('autocomplete', 'off');
    expect(screen.getByTestId('platform-auth-password')).toHaveAttribute('autocomplete', 'new-password');
    expect(screen.getByTestId('platform-auth-confirm-password')).toHaveAttribute('autocomplete', 'new-password');
    expect(screen.getByTestId('platform-auth-password')).toHaveValue('');
    expect(screen.getByTestId('platform-auth-confirm-password')).toHaveValue('');
    fireEvent.change(screen.getByTestId('platform-auth-password'), { target: { value: 'password123' } });
    fireEvent.change(screen.getByTestId('platform-auth-confirm-password'), { target: { value: 'password123' } });
    fireEvent.click(screen.getByTestId('platform-auth-login-tab'));
    expect(screen.getByTestId('platform-auth-password')).toHaveValue('');
    expect(screen.queryByTestId('platform-auth-confirm-password')).not.toBeInTheDocument();
    fireEvent.click(screen.getByTestId('platform-auth-register-tab'));
    expect(screen.getByTestId('platform-auth-password')).toHaveValue('');
    expect(screen.getByTestId('platform-auth-confirm-password')).toHaveValue('');
    fireEvent.change(screen.getByTestId('platform-auth-password'), { target: { value: 'password123' } });
    fireEvent.click(screen.getByTestId('platform-auth-submit'));
    expect(screen.getByTestId('platform-auth-error')).toHaveTextContent('请先输入邮箱');
    expect(screen.getByTestId('basic-query-snapshot')).toHaveTextContent('Apple Inc.');
  });

  it('requires password confirmation and a local verification code before registration', async () => {
    vi.mocked(platformApi.status).mockResolvedValue({ platformAuthEnabled: true });
    vi.mocked(platformApi.register).mockResolvedValue({
      user: {
        id: 77,
        email: 'verified@example.com',
        role: 'user',
        plan: 'free',
        status: 'active',
      },
      quota: {
        userId: 77,
        plan: 'free',
        weeklyLimit: 5,
        used: 0,
        remaining: 5,
        periodStart: '2026-07-06',
      },
    });

    render(
      <MemoryRouter>
        <HomePage />
      </MemoryRouter>,
    );

    fireEvent.click(await screen.findByTestId('platform-auth-register-tab'));
    fireEvent.change(screen.getByTestId('platform-auth-email'), { target: { value: 'verified@example.com' } });
    fireEvent.change(screen.getByTestId('platform-auth-password'), { target: { value: 'password123' } });
    fireEvent.change(screen.getByTestId('platform-auth-confirm-password'), { target: { value: 'password456' } });
    fireEvent.click(screen.getByTestId('platform-auth-submit'));

    expect(screen.getByTestId('platform-auth-error')).toHaveTextContent('两次输入的密码不一致');
    expect(platformApi.register).not.toHaveBeenCalled();

    fireEvent.change(screen.getByTestId('platform-auth-confirm-password'), { target: { value: 'password123' } });
    fireEvent.click(screen.getByTestId('platform-auth-submit'));
    expect(screen.getByTestId('platform-auth-error')).toHaveTextContent('请先输入邮箱验证码');

    fireEvent.click(screen.getByTestId('platform-auth-send-code'));
    await waitFor(() => {
      expect(platformApi.requestRegistrationCode).toHaveBeenCalledWith('verified@example.com');
    });
    expect(screen.getByTestId('platform-auth-verification-status')).toHaveTextContent('123456');
    expect(screen.getByTestId('platform-auth-verification-code')).toHaveValue('123456');
    expect(screen.queryByTestId('platform-auth-error')).not.toBeInTheDocument();

    fireEvent.click(screen.getByTestId('platform-auth-submit'));

    await waitFor(() => {
      expect(platformApi.register).toHaveBeenCalledWith('verified@example.com', 'password123', '123456');
    });
  });

  it('localizes platform login errors when UI language is Chinese', async () => {
    vi.mocked(platformApi.status).mockResolvedValue({ platformAuthEnabled: true });
    vi.mocked(platformApi.login).mockRejectedValueOnce({
      response: {
        status: 401,
        data: { error: 'invalid_credentials', message: 'Invalid login' },
      },
    });

    render(
      <MemoryRouter>
        <HomePage />
      </MemoryRouter>,
    );

    fireEvent.click(await screen.findByTestId('platform-auth-login-tab'));
    fireEvent.change(await screen.findByTestId('platform-auth-email'), { target: { value: 'login@example.com' } });
    fireEvent.change(screen.getByTestId('platform-auth-password'), { target: { value: 'bad-password' } });
    fireEvent.click(screen.getByTestId('platform-auth-submit'));

    expect(await screen.findByTestId('platform-auth-error')).toHaveTextContent('邮箱或密码不正确，请检查后再登录');
  });

  it('localizes platform register errors when UI language is Chinese', async () => {
    vi.mocked(platformApi.status).mockResolvedValue({ platformAuthEnabled: true });
    vi.mocked(platformApi.register).mockRejectedValueOnce({
      response: {
        status: 409,
        data: { error: 'email_exists', message: 'Email already exists' },
      },
    });

    render(
      <MemoryRouter>
        <HomePage />
      </MemoryRouter>,
    );

    fireEvent.click(await screen.findByTestId('platform-auth-register-tab'));
    fireEvent.change(screen.getByTestId('platform-auth-email'), { target: { value: 'exists@example.com' } });
    fireEvent.change(screen.getByTestId('platform-auth-password'), { target: { value: 'password123' } });
    fireEvent.change(screen.getByTestId('platform-auth-confirm-password'), { target: { value: 'password123' } });
    fireEvent.change(screen.getByTestId('platform-auth-verification-code'), { target: { value: '123456' } });
    fireEvent.click(screen.getByTestId('platform-auth-submit'));

    expect(await screen.findByTestId('platform-auth-error')).toHaveTextContent('该邮箱已注册，请直接登录');
  });

  it('keeps platform auth errors in English when UI language is English', async () => {
    window.localStorage.setItem(UI_LANGUAGE_STORAGE_KEY, 'en');
    vi.mocked(platformApi.status).mockResolvedValue({ platformAuthEnabled: true });
    vi.mocked(platformApi.login).mockRejectedValueOnce({
      response: {
        status: 401,
        data: { error: 'invalid_credentials', message: 'Invalid login' },
      },
    });

    render(
      <UiLanguageProvider>
        <MemoryRouter>
          <HomePage />
        </MemoryRouter>
      </UiLanguageProvider>,
    );

    const loginTab = await screen.findByTestId('platform-auth-login-tab');
    expect(loginTab).toHaveTextContent('Login');
    expect(screen.getByTestId('platform-auth-register-tab')).toHaveTextContent('Register');
    fireEvent.click(loginTab);
    expect(screen.getByTestId('platform-auth-email')).toHaveAttribute('placeholder', 'Email');
    expect(screen.getByTestId('platform-auth-password')).toHaveAttribute('placeholder', 'Password');
    expect(screen.getByTestId('platform-auth-submit')).toHaveTextContent('Login');
    fireEvent.click(screen.getByTestId('platform-auth-register-tab'));
    expect(screen.getByTestId('platform-auth-confirm-password')).toHaveAttribute('placeholder', 'Confirm password');
    expect(screen.getByTestId('platform-auth-verification-code')).toHaveAttribute('placeholder', 'Verification code');
    expect(screen.getByTestId('platform-auth-send-code')).toHaveTextContent('Send code');
    expect(screen.getByTestId('platform-auth-submit')).toHaveTextContent('Register');
    fireEvent.click(screen.getByTestId('platform-auth-login-tab'));
    fireEvent.change(await screen.findByTestId('platform-auth-email'), { target: { value: 'login@example.com' } });
    fireEvent.change(screen.getByTestId('platform-auth-password'), { target: { value: 'bad-password' } });
    fireEvent.click(screen.getByTestId('platform-auth-submit'));

    expect(await screen.findByTestId('platform-auth-error')).toHaveTextContent('Invalid email or password.');
  });

  it('keeps signed-in model controls off the homepage and links to account settings', async () => {
    window.localStorage.setItem(UI_LANGUAGE_STORAGE_KEY, 'en');
    const session = {
      user: { id: 94, email: 'english-user@example.com', role: 'user', plan: 'pro', status: 'active' },
      quota: { userId: 94, plan: 'pro', weeklyLimit: 100, used: 0, remaining: 100, periodStart: '2026-07-06' },
    };
    vi.mocked(platformApi.status).mockResolvedValue({ platformAuthEnabled: true });
    vi.mocked(platformApi.current).mockResolvedValue(session);
    vi.mocked(platformApi.account).mockResolvedValue({
      ...session,
      quotaBuckets: [
        { ...session.quota, quotaBucket: 'basic_query', weeklyLimit: null, remaining: null },
        { ...session.quota, quotaBucket: 'ai_quick' },
        { ...session.quota, quotaBucket: 'ai_quick_user_key', weeklyLimit: 500, remaining: 500 },
        { ...session.quota, quotaBucket: 'ai_local', weeklyLimit: 100, remaining: 100 },
      ],
      apiKeys: [],
      recommendedQueryMode: 'platform',
    });
    vi.mocked(platformApi.listApiKeys).mockResolvedValue([]);
    vi.mocked(historyApi.getList).mockResolvedValue({ total: 0, page: 1, limit: 20, items: [] });

    render(
      <UiLanguageProvider>
        <MemoryRouter>
          <HomePage />
        </MemoryRouter>
      </UiLanguageProvider>,
    );

    const panel = await screen.findByTestId('platform-signed-in-panel');
    expect(panel).toHaveTextContent('english-user@example.com');
    expect(screen.getByRole('button', { name: 'Account and models' })).toBeInTheDocument();
    expect(screen.queryByTestId('platform-query-mode-panel')).not.toBeInTheDocument();
    expect(panel).not.toHaveTextContent('Choose analysis model');
  });

  it('localizes structured no-AI query content when UI language is Chinese', async () => {
    window.localStorage.setItem(UI_LANGUAGE_STORAGE_KEY, 'zh');
    vi.mocked(platformApi.status).mockResolvedValue({ platformAuthEnabled: true });
    vi.mocked(marketWorkspaceApi.getHome).mockResolvedValue({
      asOf: '2026-07-13T01:30:00Z', aiUsed: false, informationalOnly: true,
      markets: [
        { market: 'cn', sessionState: 'unknown', displayMode: 'latest_available', rankingScope: 'configured_universe', selectionBasis: 'turnover_then_absolute_change', indices: [], sources: [], warnings: [], attention: [{ symbol: '600519.SH', name: '贵州茅台', market: 'cn', currentPrice: 1188.8, changePercent: -1.5, sourceState: { source: 'cn_quote', status: 'fresh' } }] },
        { market: 'hk', sessionState: 'unknown', displayMode: 'latest_available', rankingScope: 'configured_universe', selectionBasis: 'turnover_then_absolute_change', indices: [], sources: [], warnings: [], attention: [] },
        { market: 'us', sessionState: 'unknown', displayMode: 'latest_available', rankingScope: 'configured_universe', selectionBasis: 'turnover_then_absolute_change', indices: [], sources: [], warnings: [], attention: [] },
      ],
    });
    vi.mocked(historyApi.getList).mockResolvedValue({
      total: 0,
      page: 1,
      limit: 20,
      items: [],
    });
    vi.mocked(stocksApi.snapshot).mockResolvedValue({
      stockCode: '600519',
      stockName: '贵州茅台',
      market: 'cn',
      quote: {
        currentPrice: 1181.28,
        changePercent: -1.1,
        source: 'a_share_realtime',
        freshness: 'stale',
      },
      indicators: { ma20: 1212.965, volumeChangeVsMa5: -75.1617, volumePriceSignal: 'neutral' },
      profile: { marketCap: 1476700000000, peRatio: 17.85, source: 'a_share_realtime', freshness: 'stale' },
      intelligence: {
        mode: 'no_ai_low_cost',
        aiUsed: false,
        boundary: 'Information and data only; not investment advice or a trading instruction.',
        signalScore: {
          score: 47,
          label: 'Weak quick signal',
          summary: '600519 signal is 47/100 from trend, volume, data freshness, and profile completeness. No AI or public search was used.',
          components: [
            { key: 'trend', label: 'Trend', score: 42, status: 'missing', detail: 'Trend score is limited because latest price or MA20 is unavailable.' },
            { key: 'volume', label: 'Volume', score: 50, status: 'neutral', detail: 'Volume-price behavior is neutral in the quick rules. Volume is -75.1617% versus MA5.' },
            { key: 'freshness', label: 'Data freshness', score: 90, status: 'warning', detail: 'Quote data is fresh for this quick snapshot. a_share historical source timed out; moving averages may be incomplete.' },
            { key: 'profile', label: 'Profile completeness', score: 76, status: 'positive', detail: 'Company profile has usable valuation or financial fields.' },
          ],
          source: 'no_ai_rules',
          aiUsed: false,
        },
        retentionBrief: {
          headline: '600519 quick read: -1.1%, with incomplete MA20 context.',
          whyItMatters: 'This free snapshot turns quote, moving averages, volume and a share context into a first-pass checklist without spending AI quota.',
          supportResistance: 'support 1181.28; resistance 1212.965',
          nextSteps: [
            'Resolve data warning first: a_share historical source timed out; moving averages may be incomplete.',
            'Refresh once before market action and confirm whether price stays with incomplete MA20 context.',
            'Compare this move with 000300.SH instead of reading it alone.',
            'Use deep analysis only when you need news, filings, fundamentals, or a longer AI-written report.',
          ],
          upgradeHint: 'Login to save history, build a watchlist, keep quota state, and unlock deeper analysis when needed.',
          boundary: 'Information analysis only; not investment advice.',
          source: 'no_ai_retention_rules',
        },
        newsCenter: {
          title: 'Local news center',
          summary: '600519 information lanes for a share: news, announcements, financials, sector context, and data quality. No AI or public search was used.',
          source: 'no_ai_news_center_rules',
          aiUsed: false,
          publicSearchUsed: false,
          premiumUnlock: 'Premium can add realtime news, filings, source links, sector comparison, and AI summaries.',
          boundary: 'Information analysis only; not investment advice.',
          items: [
            { category: 'news', title: 'Market-moving news lane', summary: 'Realtime public news/search is off in free local mode, so this lane is a checklist placeholder.', status: 'degraded', source: 'no_ai_news_center_rules', action: 'Use deep analysis or configured news feeds for realtime links.' },
            { category: 'financials', title: 'Financial snapshot lane', summary: 'Market cap 1.4767T; PE 17.85; PB 6.34.', status: 'available', source: 'a_share_realtime', action: 'Compare valuation and fundamentals before relying on price action alone.' },
          ],
        },
        aShareEnrichment: {
          title: 'A-share enrichment',
          summary: '贵州茅台 A-share enrichment for announcements, fund flow, sectors, research, and dragon-tiger data is available through the local POC lane. Context: 白酒 / 沪深300. Last price 1210, change -1.1%',
          status: 'available',
          source: 'a_stock_data_poc_adapter',
          updatedAt: '2026-07-07T09:30:00Z',
          aiUsed: false,
          publicSearchUsed: false,
          premiumUnlock: 'Premium can expand announcement source text, research PDFs, fund-flow history, sector linkage, and dragon-tiger seat details.',
          boundary: 'Information analysis only; not investment advice.',
          channels: [
            { category: 'announcements', title: 'Announcements channel', summary: '贵州茅台 keeps a reserved CNINFO / TDX F10 announcements lane; quick mode shows the checklist entry only.', status: 'degraded', source: 'a_stock_data_poc_local_rules', action: 'Later versions can enable cached announcement fetching without calling external sources on every query.', updatedAt: '2026-07-07T09:30:00Z' },
            { category: 'capital_flow', title: 'Fund-flow channel', summary: 'Main fund net inflow is 120M, ratio 8.5%.', status: 'available', source: 'a_stock_data_eastmoney_fund_flow', action: 'Check whether main fund inflow is continuous across several sessions, not only a single-day move.', updatedAt: '2026-07-07T09:30:00Z' },
            { category: 'sector', title: 'Sector channel', summary: '贵州茅台 current context: 白酒; 沪深300.', status: 'available', source: 'a_stock_data_eastmoney_concept_blocks', action: 'Compare move, valuation, and fund flow against the same sector.', updatedAt: '2026-07-07T09:30:00Z' },
            { category: 'research', title: 'Research channel', summary: 'Latest research: Earnings quality tracker; rating buy.', status: 'available', source: 'a_stock_data_eastmoney_reportapi', action: 'Premium can expand research lists, PDFs, and institution forecast fields.', updatedAt: '2026-07-07T09:30:00Z' },
            { category: 'dragon_tiger', title: 'Dragon-tiger channel', summary: '2026-07-06 Dragon-tiger list record exists, net buy 30M.', status: 'available', source: 'a_stock_data_eastmoney_datacenter', action: 'Focus on institution seats and brokerage buy/sell direction.', updatedAt: '2026-07-07T09:30:00Z' },
          ],
        },
        klineForecast: {
          title: 'K-line forecast lab',
          horizon: 'next_5_bars',
          direction: 'downside_risk',
          confidence: 82,
          support: 1181.28,
          resistance: 1212.965,
          adapterStatus: 'Kronos adapter ready; local rules preview only; Kronos model not installed or invoked.',
          source: 'local_kline_rules_kronos_ready',
          aiUsed: false,
          kronosModelUsed: false,
          premiumUnlock: 'Premium can run a configured Kronos or local-model forecast lane after model/data approval.',
          boundary: 'Experimental model preview; information analysis only; not investment advice.',
          scenarios: [
            { label: 'Downside-risk preview', direction: 'downside_risk', probability: 58, trigger: 'Hold above MA20 1212.965 and keep volume change near -75.1617%.', detail: 'Local rules read support near 1181.28 and resistance near 1212.965. This is not Kronos inference.' },
            { label: 'Breakout confirmation', direction: 'upside_bias', probability: 16, trigger: 'Price closes above resistance 1212.965 with expanding volume.', detail: 'Treat this as a checklist for the next refresh, not a trade instruction.' },
          ],
        },
        items: [],
      },
      diagnostics: {
        elapsedMs: 4,
        quoteElapsedMs: 2,
        historyElapsedMs: 2,
        cache: { quote: 'hit', history: 'hit' },
        sources: { quote: 'a_share_realtime', history: 'a_share_history' },
        freshness: { quote: 'stale', history: 'stale' },
        fallback: { quote: 'cache', history: 'cache' },
        routeLane: 'a_share_market_data',
        performance: { status: 'ok' },
      },
      aiUsed: false,
    } as unknown as BasicStockSnapshot);

    render(
      <MemoryRouter>
        <UiLanguageProvider>
          <HomePage />
        </UiLanguageProvider>
      </MemoryRouter>,
    );

    expect(await screen.findByTestId('public-market-home-v116')).toBeInTheDocument();
    expect(screen.getByTestId('platform-auth-panel')).toBeInTheDocument();

    expect(await screen.findByTestId('history-center-market-filter')).toHaveTextContent('全部市场');
    expect(screen.getByTestId('history-center-code-filter')).toHaveAttribute('placeholder', '代码或名称');
    expect(screen.getByTestId('history-center-filters')).not.toHaveTextContent('All markets');

    const input = await screen.findByPlaceholderText('输入股票代码或名称，如 600519、贵州茅台、AAPL');
    fireEvent.change(input, { target: { value: '600519.SH' } });
    fireEvent.click(screen.getByRole('button', { name: '查询' }));

    await waitFor(() => {
      expect(stocksApi.snapshot).toHaveBeenCalledWith('600519.SH', {
        aShareSourceMode: 'a_stock_data',
      });
    });
    await openQuickAnalysisFromCurrentSnapshot();

    expect(screen.getByTestId('public-market-home-collapsed')).toBeInTheDocument();
    expect(screen.queryByTestId('public-market-home-v116')).not.toBeInTheDocument();
    expect(screen.getByTestId('platform-auth-panel')).toBeInTheDocument();
    expect(screen.getByTestId('platform-auth-panel-collapsed')).toBeInTheDocument();
    expect(screen.queryByTestId('platform-auth-email')).not.toBeInTheDocument();

    fireEvent.click(screen.getByTestId('platform-auth-register-tab'));
    expect(screen.getByTestId('platform-auth-panel-expanded')).toBeInTheDocument();
    expect(screen.getByTestId('platform-auth-email')).toBeInTheDocument();

    fireEvent.click(screen.getByTestId('platform-auth-panel-toggle'));
    expect(screen.getByTestId('platform-auth-panel-collapsed')).toBeInTheDocument();
    expect(screen.queryByTestId('platform-auth-email')).not.toBeInTheDocument();

    fireEvent.click(screen.getByTestId('public-market-home-toggle'));
    expect(screen.getByTestId('public-market-home-expanded')).toBeInTheDocument();
    expect(screen.getByTestId('public-market-home-v116')).toBeInTheDocument();

    fireEvent.click(screen.getByTestId('public-market-home-toggle'));
    expect(screen.getByTestId('public-market-home-collapsed')).toBeInTheDocument();
    expect(screen.queryByTestId('public-market-home-v116')).not.toBeInTheDocument();

    const freeReport = await screen.findByTestId('basic-query-free-report');
    expect(freeReport).toHaveTextContent('未用 AI');
    expect(freeReport).not.toHaveTextContent('No AI');

    const guardrails = screen.getByTestId('basic-query-user-guardrails');
    expect(guardrails).toHaveTextContent('当前快速快照');
    expect(guardrails).toHaveTextContent('历史报告单独保留');
    expect(guardrails).toHaveTextContent('A股行情数据');
    expect(guardrails).not.toHaveTextContent('Current quick snapshot');

    const workspace = screen.getByTestId('basic-query-workspace-lanes');
    expect(workspace).toHaveTextContent('当前快照');
    expect(workspace).toHaveTextContent('自选');
    expect(workspace).toHaveTextContent('历史报告');
    expect(workspace).toHaveTextContent('AI 分析');
    expect(workspace).not.toHaveTextContent('Current Snapshot');

    const signalScore = await screen.findByTestId('basic-query-signal-score');
    expect(signalScore).toHaveTextContent('趋势');
    expect(signalScore).toHaveTextContent('量价');
    expect(signalScore).toHaveTextContent('数据新鲜度');
    expect(signalScore).toHaveTextContent('资料完整度');
    expect(signalScore).not.toHaveTextContent('Trend');
    expect(signalScore).not.toHaveTextContent('Data freshness');
    expect(signalScore).not.toHaveTextContent('Trend score is limited');
    expect(signalScore).not.toHaveTextContent('historical source timed out');

    const retentionBrief = screen.getByTestId('basic-query-retention-brief');
    expect(retentionBrief).not.toHaveTextContent('quick read:');
    expect(retentionBrief).not.toHaveTextContent('Resolve data warning first');
    expect(retentionBrief).not.toHaveTextContent('Refresh once before market action');
    expect(retentionBrief).not.toHaveTextContent('with incomplete MA20 context');

    const newsCenter = screen.getByTestId('basic-query-news-center');
    expect(newsCenter).toHaveTextContent('本地资讯中心');
    expect(newsCenter).toHaveTextContent('影响行情的资讯通道');
    expect(newsCenter).toHaveTextContent('未用公共搜索');
    expect(newsCenter).not.toHaveTextContent('News center');
    expect(newsCenter).not.toHaveTextContent('Market-moving news lane');

    const aShareEnrichment = screen.getByTestId('basic-query-a-share-enrichment');
    expect(aShareEnrichment).toHaveTextContent('A股增强数据');
    expect(aShareEnrichment).toHaveTextContent('A股数据扩展');
    expect(aShareEnrichment).toHaveTextContent('资金流通道');
    expect(aShareEnrichment).toHaveTextContent('研报通道');
    expect(aShareEnrichment).toHaveTextContent('龙虎榜通道');
    expect(aShareEnrichment).toHaveTextContent('主力资金净流入 120M');
    expect(aShareEnrichment).toHaveTextContent('高级版使用 API');
    expect(aShareEnrichment).toHaveTextContent('不构成投资建议');
    expect(aShareEnrichment).not.toHaveTextContent('Fund-flow channel');
    expect(aShareEnrichment).not.toHaveTextContent('Dragon-tiger channel');
    expect(aShareEnrichment).not.toHaveTextContent('2026-07-07T09:30:00Z');

    const klineForecast = screen.getByTestId('basic-query-kline-forecast-lab');
    expect(klineForecast).toHaveTextContent('K线预测实验室');
    expect(klineForecast).toHaveTextContent('方向');
    expect(klineForecast).toHaveTextContent('下行风险');
    expect(klineForecast).toHaveTextContent('运行 Kronos 模型');
    expect(klineForecast).not.toHaveTextContent('K-line forecast lab');
    expect(klineForecast).not.toHaveTextContent('Kronos model not installed');
  });

  it('localizes US news, filing, financial, and sector nouns in Chinese mode', async () => {
    window.localStorage.setItem(UI_LANGUAGE_STORAGE_KEY, 'zh');
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
        currentPrice: 308.63,
        changePercent: 4.75,
        source: 'us_realtime',
        freshness: 'stale',
      },
      indicators: { ma20: 294.8025, volumeChangeVsMa5: -31.5573, volumePriceSignal: 'neutral' },
      profile: {
        sector: 'Technology',
        industry: 'Consumer Electronics',
        marketCap: 4533000000000,
        peRatio: 37.3192,
        pbRatio: 42.511,
        dividendYield: 0.35,
        revenue: 451442000000,
        netProfit: 122575500000,
        source: 'yfinance_profile',
        freshness: 'stale',
      },
      intelligence: {
        mode: 'no_ai_low_cost',
        aiUsed: false,
        boundary: 'Information analysis only; not investment advice.',
        newsCenter: {
          title: 'Local news center',
          summary: 'AAPL information lanes for Technology / Consumer Electronics: news, announcements, financials, sector context, and data quality. No AI or public search was used.',
          source: 'no_ai_news_center_rules',
          aiUsed: false,
          publicSearchUsed: false,
          premiumUnlock: 'Premium can add realtime news, filings, source links, sector comparison, and AI summaries.',
          boundary: 'Information analysis only; not investment advice.',
          items: [
            {
              category: 'news',
              title: 'Market-moving news lane',
              summary: 'AAPL is at 308.63 with +4.75%. Realtime public news/search is off in free local mode, so this lane is a checklist placeholder.',
              status: 'degraded',
              source: 'no_ai_news_center_rules',
              action: 'Use deep analysis or configured news feeds for realtime links.',
            },
            {
              category: 'announcements',
              title: 'SEC filings lane',
              summary: 'SEC filings, earnings call notes, and source links are reserved for deep mode or configured feeds. Free mode avoids public search and AI cost.',
              status: 'degraded',
              source: 'no_ai_news_center_rules',
              action: 'Upgrade or configure a filings source when source links are required.',
            },
            {
              category: 'financials',
              title: 'Financial snapshot lane',
              summary: 'Market cap 4.533T; PE 37.3192; PB 42.511; dividend yield 0.35%; revenue 451.442B; net profit 122.5755B.',
              status: 'available',
              source: 'yfinance_profile',
              action: 'Compare valuation and fundamentals before relying on price action alone.',
            },
            {
              category: 'sector',
              title: 'Sector and peer lane',
              summary: 'Context is Technology / Consumer Electronics; current volume-price signal is price above trend volume soft. Compare against route-based peers before reading this symbol in isolation.',
              status: 'available',
              source: 'no_ai_news_center_rules',
              action: 'Open peer comparison or deep sector view for richer cross-asset context.',
            },
          ],
        },
      },
      diagnostics: {
        elapsedMs: 4,
        quoteElapsedMs: 2,
        historyElapsedMs: 2,
        cache: { quote: 'hit', history: 'hit' },
        sources: { quote: 'us_realtime', history: 'yfinance' },
        freshness: { quote: 'stale', history: 'stale' },
        fallback: { quote: 'cache', history: 'cache' },
        routeLane: 'us_market_data',
        performance: { status: 'ok' },
      },
      aiUsed: false,
    } as unknown as BasicStockSnapshot);

    render(
      <MemoryRouter>
        <UiLanguageProvider>
          <HomePage />
        </UiLanguageProvider>
      </MemoryRouter>,
    );

    const input = await screen.findByRole('textbox');
    fireEvent.change(input, { target: { value: 'AAPL' } });
    fireEvent.click(screen.getByRole('button', { name: '查询' }));
    await openQuickAnalysisFromCurrentSnapshot();

    const newsCenter = await screen.findByTestId('basic-query-news-center');
    expect(newsCenter).toHaveTextContent('科技 / 消费电子');
    expect(newsCenter).toHaveTextContent('SEC 文件、业绩电话会纪要和来源链接');
    expect(newsCenter).toHaveTextContent('股息率 0.35%');
    expect(newsCenter).toHaveTextContent('营收 451.442B');
    expect(newsCenter).toHaveTextContent('净利润 122.5755B');
    expect(newsCenter).toHaveTextContent('公司资料');
    expect(newsCenter).not.toHaveTextContent('Technology / Consumer Electronics');
    expect(newsCenter).not.toHaveTextContent('SEC filings');
    expect(newsCenter).not.toHaveTextContent('dividend yield');
    expect(newsCenter).not.toHaveTextContent('revenue');
    expect(newsCenter).not.toHaveTextContent('net profit');
    expect(newsCenter).not.toHaveTextContent('yfinance_profile');
  });

  it('localizes A-share quick reference fallback data in Chinese mode', async () => {
    window.localStorage.setItem(UI_LANGUAGE_STORAGE_KEY, 'zh');
    vi.mocked(historyApi.getList).mockResolvedValue({
      total: 0,
      page: 1,
      limit: 20,
      items: [],
    });
    vi.mocked(stocksApi.snapshot).mockResolvedValue({
      stockCode: '600519',
      stockName: '贵州茅台',
      market: 'cn',
      quote: {
        currentPrice: 1181.28,
        changePercent: -1.1,
        source: 'a_share_realtime',
        freshness: 'stale',
      },
      indicators: {
        ma5: 1195.782,
        ma10: 1191.91,
        ma20: 1212.965,
        lastClose: 1202.45,
        priceChange5d: 2.894,
        priceChange20d: -3.0267,
        volumeChangeVsMa5: -75.1617,
      },
      intelligence: {
        mode: 'no_ai_low_cost',
        aiUsed: false,
        aShareEnrichment: {
          title: 'A-share quick reference',
          summary: '贵州茅台 quick reference uses quote, moving-average, volume, valuation, and freshness data. External announcements, fund-flow, research, and dragon-tiger seats are not enabled in free quick mode.',
          status: 'available',
          source: 'basic_quote_snapshot',
          updatedAt: '2026-07-07T09:30:00Z',
          aiUsed: false,
          publicSearchUsed: false,
          premiumUnlock: 'Premium can add live announcements, fund-flow history, research PDFs, sector linkage, and dragon-tiger seat details.',
          boundary: 'Information analysis only; not investment advice.',
          channels: [
            { category: 'price_structure', title: 'Price structure', summary: 'Latest 1181.28, change -1.1%, open 1186, high 1190, low 1181.28; price is below MA20 1212.965.', status: 'available', source: 'basic_quote_snapshot', action: 'Use this as a first-pass structure check for 贵州茅台; refresh stale quotes before comparing intraday moves.', updatedAt: '2026-07-07T09:30:00Z' },
            { category: 'volume_activity', title: 'Volume activity', summary: 'Volume 174.7K, amount 207M; volume is -75.1617% versus MA5.', status: 'available', source: 'basic_indicator_snapshot', action: 'Use volume only as confirmation; price and source freshness come first.', updatedAt: '2026-07-07T09:30:00Z' },
            { category: 'valuation_snapshot', title: 'Valuation snapshot', summary: 'Market cap 1.4767T; PE 17.85; PB 6.34.', status: 'available', source: 'basic_profile_snapshot', action: 'Use valuation as context, not as a timing signal.', updatedAt: '2026-07-07T09:30:00Z' },
            { category: 'trend_windows', title: 'Trend windows', summary: '5-day change 2.894%; 20-day change -3.0267%; MA5 1195.782, MA10 1191.91, MA20 1212.965; last close 1202.45.', status: 'available', source: 'basic_indicator_snapshot', action: 'Compare short-window moves with MA20 before reading the trend as repaired.', updatedAt: '2026-07-07T09:30:00Z' },
            { category: 'data_quality', title: 'Data quality', summary: 'Quote freshness stale; profile freshness stale; quote source a_share_realtime.', status: 'available', source: 'basic_data_quality_snapshot', action: 'Treat stale or cached data as provisional and refresh before acting on changes.', updatedAt: '2026-07-07T09:30:00Z' },
          ],
        },
        items: [],
        boundary: 'Information analysis only; not investment advice.',
      },
      diagnostics: {
        elapsedMs: 4,
        quoteElapsedMs: 2,
        historyElapsedMs: 2,
        cache: { quote: 'hit', history: 'hit' },
        sources: { quote: 'a_share_realtime', history: 'a_share_history' },
        freshness: { quote: 'stale', history: 'stale' },
        fallback: { quote: 'cache', history: 'cache' },
        routeLane: 'a_share_market_data',
        performance: { status: 'ok' },
      },
      aiUsed: false,
    } as unknown as BasicStockSnapshot);

    render(
      <MemoryRouter>
        <UiLanguageProvider>
          <HomePage />
        </UiLanguageProvider>
      </MemoryRouter>,
    );

    const input = await screen.findByRole('textbox');
    fireEvent.change(input, { target: { value: '600519.SH' } });
    fireEvent.click(screen.getByRole('button', { name: '查询' }));

    await waitFor(() => {
      expect(stocksApi.snapshot).toHaveBeenCalledWith('600519.SH', {
        aShareSourceMode: 'a_stock_data',
      });
    });
    await openQuickAnalysisFromCurrentSnapshot();

    const aShareEnrichment = await screen.findByTestId('basic-query-a-share-enrichment');
    expect(aShareEnrichment).toHaveTextContent('A股快速参考数据');
    expect(aShareEnrichment).toHaveTextContent('价格结构');
    expect(aShareEnrichment).toHaveTextContent('量价活跃度');
    expect(aShareEnrichment).toHaveTextContent('估值快照');
    expect(aShareEnrichment).toHaveTextContent('周期趋势');
    expect(aShareEnrichment).toHaveTextContent('数据质量');
    expect(aShareEnrichment).toHaveTextContent('最新价 1181.28');
    expect(aShareEnrichment).toHaveTextContent('成交额 207M');
    expect(aShareEnrichment).toHaveTextContent('市值 1.4767T');
    expect(aShareEnrichment).toHaveTextContent('5日涨跌 2.894%');
    expect(aShareEnrichment).toHaveTextContent('未用公共搜索');
    expect(aShareEnrichment).toHaveTextContent('不构成投资建议');
    expect(aShareEnrichment).not.toHaveTextContent('A-share quick reference');
    expect(aShareEnrichment).not.toHaveTextContent('Price structure');
    expect(aShareEnrichment).not.toHaveTextContent('Data quality');
    expect(aShareEnrichment).not.toHaveTextContent('External announcements');
  });

  it('renders the V63 A-share reader summary in Chinese mode', async () => {
    window.localStorage.setItem(UI_LANGUAGE_STORAGE_KEY, 'zh');
    vi.mocked(historyApi.getList).mockResolvedValue({
      total: 0,
      page: 1,
      limit: 20,
      items: [],
    });
    vi.mocked(stocksApi.snapshot).mockResolvedValue({
      stockCode: '600519',
      stockName: '贵州茅台',
      market: 'cn',
      quote: {
        currentPrice: 1188.8,
        changePercent: -1.5,
        source: 'a_share_realtime',
        freshness: 'fresh',
      },
      indicators: {},
      intelligence: {
        mode: 'no_ai_low_cost',
        aiUsed: false,
        aShareEnrichment: {
          title: 'A-share enrichment',
          summary: '贵州茅台 A股增强数据：公告、资金流、板块、研报和龙虎榜已检查。',
          status: 'available',
          source: 'a_stock_data_skill_adapter',
          sourceMode: 'a_stock_data',
          updatedAt: '2026-07-08T09:30:00Z',
          aiUsed: false,
          publicSearchUsed: false,
          readerSummary: {
            headline: '贵州茅台 A股增强速读',
            whyRead: '为什么值得看：公告有新记录，板块背景可用，资金流和龙虎榜已查询但当前未命中。',
            boundary: '仅作信息分析，不构成投资建议。',
            keyFacts: [
              { label: '今日关键信息', value: '1188.8 / -1.5%', detail: '行情来自 A 股快速通道。' },
              { label: '已命中通道', value: '3/5', detail: '公告、板块、研报可读。' },
              { label: '数据成本', value: '未用 AI', detail: '未使用公共搜索。' },
            ],
            missExplanations: [
              {
                title: '资金流通道',
                explanation: '已查询，当前未返回分钟级主力净额。',
                nextStep: '盘中刷新后再复核。',
              },
            ],
            premiumFeatures: ['公告原文', '资金流历史', '研报 PDF', '板块联动', '龙虎榜席位明细'],
          },
          premiumUnlock: 'Premium can expand announcement source text, research PDFs, fund-flow history, sector linkage, and dragon-tiger seat details.',
          boundary: 'Information analysis only; not investment advice.',
          channels: [
            {
              category: 'announcements',
              title: '公告通道',
              summary: '2026-06-22 贵州茅台2025年年度权益分派实施公告',
              status: 'available',
              source: 'a_stock_data_cninfo_or_f10',
              action: '深度模式可展开公告原文。',
              updatedAt: '2026-07-08T09:30:00Z',
              details: [
                { label: '发布日期', value: '2026-06-22', detail: '公告披露日期' },
                { label: '公告标题', value: 'Dividend implementation announcement', detail: 'annual distribution' },
              ],
            },
          ],
        },
        items: [],
        boundary: 'Information analysis only; not investment advice.',
      },
      aiUsed: false,
    } as unknown as BasicStockSnapshot);

    render(
      <MemoryRouter>
        <UiLanguageProvider>
          <HomePage />
        </UiLanguageProvider>
      </MemoryRouter>,
    );

    const input = await screen.findByRole('textbox');
    fireEvent.change(input, { target: { value: '600519.SH' } });
    fireEvent.click(screen.getByRole('button', { name: '查询' }));
    await openQuickAnalysisFromCurrentSnapshot();

    const readerSummary = await screen.findByTestId('basic-query-a-share-reader-summary');
    expect(readerSummary).toHaveTextContent('今日关键信息');
    expect(readerSummary).toHaveTextContent('为什么值得看');
    expect(readerSummary).toHaveTextContent('未命中说明');
    expect(readerSummary).toHaveTextContent('版本差异');
    expect(readerSummary).toHaveTextContent('公告原文');
    expect(readerSummary).toHaveTextContent('资金流历史');
    expect(readerSummary).toHaveTextContent('仅作信息分析');
  });

  it('renders V64 structured A-share channel details in Chinese mode', async () => {
    window.localStorage.setItem(UI_LANGUAGE_STORAGE_KEY, 'zh');
    vi.mocked(historyApi.getList).mockResolvedValue({
      total: 0,
      page: 1,
      limit: 20,
      items: [],
    });
    vi.mocked(stocksApi.snapshot).mockResolvedValue({
      stockCode: '600519',
      stockName: '贵州茅台',
      market: 'cn',
      quote: {
        currentPrice: 1188.8,
        changePercent: -1.5,
        source: 'a_share_realtime',
        freshness: 'fresh',
      },
      indicators: {},
      intelligence: {
        mode: 'no_ai_low_cost',
        aiUsed: false,
        aShareEnrichment: {
          title: 'A股增强数据',
          summary: '贵州茅台 A股增强数据',
          status: 'available',
          source: 'a_stock_data_skill_adapter',
          sourceMode: 'a_stock_data',
          aiUsed: false,
          publicSearchUsed: false,
          channels: [
            {
              category: 'capital_flow',
              title: '资金流通道',
              summary: '主力资金净额 12.0M。',
              status: 'available',
              source: 'a_stock_data_eastmoney_fund_flow',
              action: '继续观察主力资金是否连续回流。',
              details: [
                { label: '主力净额', value: '12.0M', detail: '近几条分钟记录合计' },
                { label: '最新分钟', value: '12.0M', detail: '2026-07-08 09:31' },
              ],
            },
          ],
          premiumUnlock: '免费版保留同样入口；高级版使用 API 展开更多来源。',
          boundary: '仅作信息分析，不构成投资建议。',
        },
        items: [],
        boundary: 'Information analysis only; not investment advice.',
      },
      aiUsed: false,
    } as unknown as BasicStockSnapshot);

    render(
      <MemoryRouter>
        <UiLanguageProvider>
          <HomePage />
        </UiLanguageProvider>
      </MemoryRouter>,
    );

    const input = await screen.findByRole('textbox');
    fireEvent.change(input, { target: { value: '600519.SH' } });
    fireEvent.click(screen.getByRole('button', { name: '查询' }));
    await openQuickAnalysisFromCurrentSnapshot();

    const enrichment = await screen.findByTestId('basic-query-a-share-enrichment');
    expect(enrichment).toHaveTextContent('主力净额');
    expect(enrichment).toHaveTextContent('12.0M');
    expect(enrichment).toHaveTextContent('最新分钟');
    expect(enrichment).toHaveTextContent('近几条分钟记录合计');
  });

  it('lets users switch A-share enrichment source mode and run sample probes', async () => {
    window.localStorage.setItem(UI_LANGUAGE_STORAGE_KEY, 'en');
    vi.mocked(historyApi.getList).mockResolvedValue({
      total: 0,
      page: 1,
      limit: 20,
      items: [],
    });
    vi.mocked(stocksApi.snapshot).mockResolvedValue({
      stockCode: '600519',
      stockName: 'Kweichow Moutai',
      market: 'cn',
      quote: {
        currentPrice: 1188.8,
        source: 'a_share_realtime',
        freshness: 'fresh',
      },
      indicators: {},
      intelligence: {
        mode: 'no_ai_low_cost',
        aiUsed: false,
        aShareEnrichment: {
          title: 'A-share enrichment',
          summary: 'Adapter mode visible.',
          status: 'degraded',
          source: 'a_stock_data_skill_adapter',
          sourceMode: 'a_stock_data',
          skill: { installed: true, revision: 'bcda405' },
          diagnostics: {
            cache: { hits: 1, misses: 0, staleHits: 0 },
            rateLimitedChannels: [],
            errors: {},
          },
          updatedAt: '2026-07-07T09:30:00Z',
          aiUsed: false,
          publicSearchUsed: false,
          premiumUnlock: 'Premium can expand sources.',
          boundary: 'Information analysis only; not investment advice.',
          channels: [
            {
              category: 'announcements',
              title: 'Announcements channel',
              summary: 'Checklist placeholder.',
              status: 'degraded',
              source: 'a_stock_data_poc_local_rules',
              action: 'Enable cached source fetching after approval.',
              updatedAt: '2026-07-07T09:30:00Z',
            },
          ],
        },
        items: [],
        boundary: 'Information analysis only; not investment advice.',
      },
      aiUsed: false,
    } as unknown as BasicStockSnapshot);

    render(
      <MemoryRouter>
        <UiLanguageProvider>
          <HomePage />
        </UiLanguageProvider>
      </MemoryRouter>,
    );

    const input = await screen.findByRole('textbox');
    fireEvent.change(input, { target: { value: '600519' } });
    fireEvent.click(screen.getByRole('button', { name: 'Query' }));
    await openQuickAnalysisFromCurrentSnapshot();

    const sourcePanel = await screen.findByTestId('a-share-source-control');
    expect(sourcePanel).toHaveTextContent('A-share source');
    expect(sourcePanel).toHaveTextContent('cache H1 / M0 / S0');
    expect(sourcePanel).toHaveTextContent('repo bcda405');

    fireEvent.click(screen.getByTestId('a-share-source-mode-a_stock_data'));
    await waitFor(() => {
      expect(stocksApi.snapshot).toHaveBeenLastCalledWith('600519', {
        refresh: true,
        aShareSourceMode: 'a_stock_data',
      });
    });

    fireEvent.click(screen.getByTestId('a-share-source-probe-000001'));
    await waitFor(() => {
      expect(stocksApi.snapshot).toHaveBeenLastCalledWith('000001', {
        refresh: true,
        aShareSourceMode: 'a_stock_data',
      });
    });
  });

  it('keeps a guest AAPL snapshot through register and saves it to history and watchlist', async () => {
    window.localStorage.setItem(UI_LANGUAGE_STORAGE_KEY, 'en');
    vi.mocked(platformApi.status).mockResolvedValue({ platformAuthEnabled: true });
    vi.mocked(historyApi.getList).mockResolvedValue({
      total: 0,
      page: 1,
      limit: 20,
      items: [],
    });
    vi.mocked(platformApi.register).mockResolvedValue({
      user: {
        id: 56,
        email: 'v56-user@example.com',
        role: 'user',
        plan: 'free',
        status: 'active',
      },
      quota: {
        userId: 56,
        plan: 'free',
        weeklyLimit: 5,
        used: 0,
        remaining: 5,
        periodStart: '2026-07-06',
      },
    });
    vi.mocked(platformApi.account).mockResolvedValue({
      user: {
        id: 56,
        email: 'v56-user@example.com',
        role: 'user',
        plan: 'free',
        status: 'active',
      },
      quota: {
        userId: 56,
        plan: 'free',
        weeklyLimit: 5,
        used: 0,
        remaining: 5,
        periodStart: '2026-07-06',
      },
      quotaBuckets: [
        {
          userId: 56,
          plan: 'free',
          weeklyLimit: 10,
          used: 1,
          remaining: 9,
          periodStart: '2026-07-06',
          quotaBucket: 'basic_query',
        },
        {
          userId: 56,
          plan: 'free',
          weeklyLimit: 3,
          used: 0,
          remaining: 3,
          periodStart: '2026-07-06',
          quotaBucket: 'ai_quick',
        },
        {
          userId: 56,
          plan: 'free',
          weeklyLimit: 3,
          used: 0,
          remaining: 3,
          periodStart: '2026-07-06',
          quotaBucket: 'ai_quick_user_key',
        },
        {
          userId: 56,
          plan: 'free',
          weeklyLimit: 1,
          used: 0,
          remaining: 1,
          periodStart: '2026-07-06',
          quotaBucket: 'ai_local',
        },
      ],
      apiKeys: [
        {
          provider: 'deepseek',
          model: 'deepseek/deepseek-v4-flash',
          maskedKey: 'sk-...safe',
          enabled: true,
        },
      ],
      recommendedQueryMode: 'user',
    });
    vi.mocked(platformApi.watchlist).mockResolvedValue({
      userId: 56,
      total: 0,
      aiUsed: false,
      items: [],
    });
    vi.mocked(platformApi.addWatchlistItem).mockResolvedValue({
      userId: 56,
      total: 1,
      aiUsed: false,
      items: [{ id: 1, stockCode: 'AAPL', market: 'us' }],
    });
    vi.mocked(platformApi.saveSnapshotToHistory).mockResolvedValue({
      recordId: 5601,
      stockCode: 'AAPL',
      reportType: 'basic_snapshot',
      savedToHistory: true,
      aiUsed: false,
    });
    vi.mocked(stocksApi.snapshot).mockResolvedValue({
      stockCode: 'AAPL',
      stockName: 'Apple Inc.',
      market: 'us',
      quote: {
        currentPrice: 200,
        changePercent: 1.5,
        source: 'unit_quote',
        freshness: 'fresh',
      },
      indicators: { ma5: 198, ma20: 190 },
      intelligence: {
        mode: 'no_ai_low_cost',
        aiUsed: false,
        boundary: 'Information analysis only; not investment advice.',
        retentionBrief: {
          headline: 'AAPL quick read: +1.5%, above MA20 190.',
          whyItMatters: 'Free no-AI checklist.',
          supportResistance: 'support 190; resistance 200',
          nextSteps: ['Register, save history, and add to watchlist'],
          upgradeHint: 'Login to save history and watchlist.',
          boundary: 'Information analysis only; not investment advice.',
          source: 'no_ai_retention_rules',
        },
        items: [],
      },
      route: {
        inputCode: 'AAPL',
        normalizedCode: 'AAPL',
        market: 'us',
        channel: 'us_equity',
        dataSourceLane: 'us_market_data',
        quoteSources: ['unit_quote'],
        historySources: ['unit_history'],
        aiRequired: false,
      },
      diagnostics: {
        elapsedMs: 5,
        quoteElapsedMs: 2,
        historyElapsedMs: 3,
        cache: { quote: 'miss', history: 'miss' },
        sources: { quote: 'unit_quote', history: 'unit_history' },
        freshness: { quote: 'fresh', history: 'fresh' },
        fallback: { quote: 'live', history: 'live' },
        routeLane: 'us_market_data',
        performance: { status: 'ok' },
      },
      aiUsed: false,
    });

    render(
      <UiLanguageProvider>
        <MemoryRouter>
          <HomePage />
        </MemoryRouter>
      </UiLanguageProvider>,
    );

    fireEvent.click(await screen.findByTestId('guest-example-AAPL'));
    expect(await screen.findByTestId('basic-query-snapshot')).toHaveTextContent('Apple Inc.');

    fireEvent.click(screen.getByTestId('platform-auth-register-tab'));
    fireEvent.change(screen.getByTestId('platform-auth-email'), { target: { value: 'v56-user@example.com' } });
    fireEvent.change(screen.getByTestId('platform-auth-password'), { target: { value: 'password123' } });
    fireEvent.change(screen.getByTestId('platform-auth-confirm-password'), { target: { value: 'password123' } });
    fireEvent.click(screen.getByTestId('platform-auth-send-code'));
    await waitFor(() => {
      expect(platformApi.requestRegistrationCode).toHaveBeenCalledWith('v56-user@example.com');
    });
    fireEvent.change(screen.getByTestId('platform-auth-verification-code'), { target: { value: '123456' } });
    fireEvent.click(screen.getByTestId('platform-auth-submit'));

    await waitFor(() => {
      expect(platformApi.register).toHaveBeenCalledWith('v56-user@example.com', 'password123', '123456');
    });
    expect(screen.getByTestId('basic-query-snapshot')).toHaveTextContent('Apple Inc.');
    const modeGuide = await screen.findByTestId('basic-query-retention-mode-guide');
    expect(modeGuide).toHaveTextContent('Free no-AI');
    expect(modeGuide).toHaveTextContent('Platform API');
    expect(modeGuide).toHaveTextContent('BYOK');
    expect(modeGuide).toHaveTextContent('Local model');
    expect(modeGuide).toHaveTextContent('sk-...safe');
    expect(modeGuide).not.toHaveTextContent('sk-live');

    fireEvent.click(screen.getByTestId('basic-query-save-current-history'));
    await waitFor(() => {
      expect(platformApi.saveSnapshotToHistory).toHaveBeenCalledWith(expect.objectContaining({
        stockCode: 'AAPL',
        aiUsed: false,
      }));
    });
    expect(await screen.findByTestId('basic-query-retention-status')).toHaveTextContent('Saved to history');

    fireEvent.click(screen.getByTestId('basic-query-add-current-watchlist'));
    await waitFor(() => {
      expect(platformApi.addWatchlistItem).toHaveBeenCalledWith('AAPL');
    });
    expect(screen.getByTestId('basic-query-retention-status')).toHaveTextContent('Added to watchlist');
  });

  it('loads history without auto-opening an old report and opens it on explicit selection', async () => {
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
    expect(await screen.findByTestId('history-center-item-1')).toBeInTheDocument();
    expect(historyApi.getDetail).not.toHaveBeenCalled();
    expect(screen.queryByText('趋势维持强势')).not.toBeInTheDocument();

    await openHistoryRecord(1);
    expect(await screen.findByText('趋势维持强势', undefined, { timeout: 3000 })).toBeInTheDocument();
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

    await openHistoryRecord(1);
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

    await openHistoryRecord(1);
    const boundary = await screen.findByTestId('history-report-freshness-boundary');
    expect(boundary).toHaveTextContent('Historical AI report');
    expect(boundary).toHaveTextContent('not current quote');
    expect(screen.queryByTestId('basic-query-snapshot')).not.toBeInTheDocument();

    fireEvent.click(screen.getByTestId('history-report-refresh-current'));

    await waitFor(() => {
      expect(stocksApi.snapshot).toHaveBeenCalledWith('600519', {
        refresh: true,
        aShareSourceMode: 'a_stock_data',
      });
    });
    expect(analysisApi.analyzeAsync).not.toHaveBeenCalled();
    expect(await screen.findByTestId('basic-query-snapshot')).toHaveTextContent('1,688');
    expect(screen.getByTestId('basic-query-diagnostics')).toHaveTextContent('强制刷新');
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
    expect(screen.getByTestId('history-center-export-status')).toHaveTextContent('已导出 1 份本地报告');
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
    expect(screen.getByTestId('history-center-state-status')).toHaveTextContent('已归档 1 份本地报告');

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
    expect(screen.getByTestId('history-state-status')).toHaveTextContent('已保存本地历史状态');
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
    expect(screen.getByTestId('history-center-state-status')).toHaveTextContent('已标为重要 1 份本地报告');

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

    await openHistoryRecord(30);
    expect(await screen.findByText('Apple margin expansion remains visible')).toBeInTheDocument();
    expect(screen.getByTestId('history-report-tools')).toBeInTheDocument();
    expect(screen.getByTestId('history-report-stock-timeline')).toHaveTextContent('AAPL');
    expect(screen.getByTestId('history-report-timeline-30')).toHaveTextContent('当前');
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

    await openHistoryRecord(1);
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
    fireEvent.click(screen.getByRole('button', { name: '深度分析' }));

    await waitFor(() => {
      expect(screen.getByText(/股票 600519 正在分析中/)).toBeInTheDocument();
    });
    expect(screen.getByText(/股票 600519 正在分析中/).closest('[role="alert"]')).toBeInTheDocument();
  });

  it('routes guest quick analysis to the free no-AI snapshot when platform auth is enabled', async () => {
    vi.mocked(platformApi.status).mockResolvedValue({ platformAuthEnabled: true });
    vi.mocked(historyApi.getList).mockResolvedValue({
      total: 0,
      page: 1,
      limit: 20,
      items: [],
    });
    vi.mocked(stocksApi.snapshot).mockResolvedValue({
      stockCode: '600519',
      stockName: '贵州茅台',
      market: 'cn',
      quote: {
        currentPrice: 1188.8,
        changePercent: -1.5,
        source: 'unit_quote',
        freshness: 'fresh',
      },
      indicators: { ma5: 1190, ma20: 1202 },
      profile: { companyName: '贵州茅台', source: 'unit_profile', freshness: 'fresh' },
      intelligence: {
        mode: 'no_ai_low_cost',
        aiUsed: false,
        boundary: 'Information analysis only; not investment advice.',
      },
      aiUsed: false,
    } as unknown as BasicStockSnapshot);
    vi.mocked(analysisApi.analyzeAsync).mockRejectedValue(new Error('AI should not run for guest quick analysis'));

    render(
      <MemoryRouter>
        <HomePage />
      </MemoryRouter>,
    );

    const input = await screen.findByPlaceholderText('输入股票代码或名称，如 600519、贵州茅台、AAPL');
    fireEvent.change(input, { target: { value: '600519' } });
    fireEvent.click(screen.getByRole('button', { name: '快速分析' }));

    await waitFor(() => {
      expect(stocksApi.snapshot).toHaveBeenCalledWith('600519', { aShareSourceMode: 'a_stock_data' });
    });
    expect(analysisApi.analyzeAsync).not.toHaveBeenCalled();
    expect(await screen.findByTestId('basic-query-primary-summary')).toHaveTextContent('贵州茅台');
    expect(await screen.findByTestId('basic-query-mode-banner')).toHaveTextContent('快速分析模式');
    expect(screen.getByTestId('basic-query-mode-banner')).toHaveTextContent('未用 AI');
    expect(await screen.findByTestId('free-kline-research-v101')).toHaveTextContent('免费历史走势研究台');
    expect(stocksApi.history).toHaveBeenCalledWith('600519', 90);
    expect(screen.queryByText('Login required')).not.toBeInTheDocument();
  });

  it('routes quick analysis to the free no-AI snapshot before platform status finishes loading', async () => {
    vi.mocked(platformApi.status).mockImplementation(() => new Promise(() => {}));
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
        currentPrice: 310.66,
        changePercent: -0.24,
        source: 'unit_quote',
        freshness: 'fresh',
      },
      indicators: { ma5: 303.138, ma20: 295.04 },
      profile: { companyName: 'Apple Inc.', source: 'unit_profile', freshness: 'fresh' },
      intelligence: {
        mode: 'no_ai_low_cost',
        aiUsed: false,
        boundary: 'Information analysis only; not investment advice.',
      },
      aiUsed: false,
    } as unknown as BasicStockSnapshot);
    vi.mocked(analysisApi.analyzeAsync).mockRejectedValue(new Error('AI should not run while platform status is still loading'));

    render(
      <MemoryRouter>
        <HomePage />
      </MemoryRouter>,
    );

    const input = await screen.findByPlaceholderText('输入股票代码或名称，如 600519、贵州茅台、AAPL');
    fireEvent.change(input, { target: { value: 'AAPL' } });
    fireEvent.click(screen.getByRole('button', { name: '快速分析' }));

    await waitFor(() => {
      expect(stocksApi.snapshot).toHaveBeenCalledWith('AAPL');
    });
    expect(analysisApi.analyzeAsync).not.toHaveBeenCalled();
    expect(await screen.findByTestId('basic-query-primary-summary')).toHaveTextContent('Apple Inc.');
    expect(await screen.findByTestId('basic-query-mode-banner')).toHaveTextContent('快速分析模式');
    expect(screen.getByTestId('basic-query-mode-banner')).toHaveTextContent('未用 AI');
  });

  it('clears stale analysis connection errors after a successful no-AI query', async () => {
    vi.mocked(historyApi.getList).mockResolvedValue({
      total: 0,
      page: 1,
      limit: 20,
      items: [],
    });
    useStockPoolStore.setState({
      query: 'AAPL',
      error: {
        title: '无法连接到本地服务',
        message: '旧的本地连接错误',
        rawMessage: 'Failed to fetch',
        category: 'local_connection_failed',
      },
    });
    vi.mocked(stocksApi.snapshot).mockResolvedValue({
      stockCode: 'AAPL',
      stockName: 'Apple Inc.',
      market: 'us',
      quote: {
        currentPrice: 200,
        changePercent: 1.5,
        source: 'unit_quote',
        freshness: 'fresh',
      },
      indicators: { ma5: 198, ma20: 190 },
      profile: { companyName: 'Apple Inc.', source: 'unit_profile', freshness: 'fresh' },
      intelligence: {
        mode: 'no_ai_low_cost',
        aiUsed: false,
        boundary: 'Information analysis only; not investment advice.',
      },
      aiUsed: false,
    } as unknown as BasicStockSnapshot);

    render(
      <MemoryRouter>
        <HomePage />
      </MemoryRouter>,
    );

    expect(await screen.findByText('旧的本地连接错误')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: '查询' }));

    expect(await screen.findByTestId('basic-query-snapshot')).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.queryByText('旧的本地连接错误')).not.toBeInTheDocument();
    });
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
        pbRatio: 48.6,
        dividendYield: 0.5,
        revenue: 451442000000,
        netProfit: 122575500000,
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
        signalScore: {
          score: 82,
          label: 'Strong quick signal',
          summary: 'AAPL signal is 82/100 from trend, volume, data freshness, and profile completeness.',
          components: [
            {
              key: 'trend',
              label: 'Trend',
              score: 90,
              status: 'positive',
              detail: 'Price is above MA20 and short-term trend remains constructive.',
            },
            {
              key: 'volume',
              label: 'Volume',
              score: 70,
              status: 'neutral',
              detail: 'Volume is above recent average but still needs follow-through.',
            },
            {
              key: 'freshness',
              label: 'Data freshness',
              score: 100,
              status: 'positive',
              detail: 'Quote and history are fresh.',
            },
            {
              key: 'profile',
              label: 'Profile completeness',
              score: 80,
              status: 'positive',
              detail: 'Company sector, industry, and valuation fields are available.',
            },
          ],
          source: 'no_ai_rules',
          aiUsed: false,
        },
        retentionBrief: {
          headline: 'AAPL quick read: +1.5%, above MA20 190.',
          whyItMatters: 'This free snapshot turns quote, moving averages, volume and Technology / Consumer Electronics context into a first-pass checklist without spending AI quota.',
          supportResistance: 'support 190; resistance 205',
          nextSteps: [
            'Refresh once before market action and confirm whether price stays above MA20.',
            'Compare this move with QQQ instead of reading it alone.',
            'Use deep analysis only when you need filings or a longer AI-written report.',
          ],
          upgradeHint: 'Login to save history, build a watchlist, keep quota state, and unlock deeper analysis when needed.',
          boundary: 'Information analysis only; not investment advice.',
          source: 'no_ai_retention_rules',
        },
        newsCenter: {
          title: 'Local news center',
          summary: 'AAPL information lanes for Technology / Consumer Electronics: news, announcements, financials, sector context, and data quality. No AI or public search was used.',
          source: 'no_ai_news_center_rules',
          aiUsed: false,
          publicSearchUsed: false,
          premiumUnlock: 'Premium can add realtime news, filings, source links, sector comparison, and AI summaries.',
          boundary: 'Information analysis only; not investment advice.',
          items: [
            {
              category: 'news',
              title: 'Market-moving news lane',
              summary: 'Realtime public news/search is off in free local mode, so this lane is a checklist placeholder.',
              status: 'degraded',
              source: 'no_ai_news_center_rules',
              action: 'Use deep analysis or configured news feeds for realtime links.',
              updatedAt: '2026-07-02T16:00:00',
            },
            {
              category: 'announcements',
              title: 'SEC filings lane',
              summary: 'SEC filings, earnings call notes, and source links are reserved for deep mode or configured feeds.',
              status: 'degraded',
              source: 'no_ai_news_center_rules',
              action: 'Upgrade or configure a filings source when source links are required.',
            },
            {
              category: 'financials',
              title: 'Financial snapshot lane',
              summary: 'Market cap 4.5T; PE 31.2.',
              status: 'available',
              source: 'unit_profile',
              action: 'Compare valuation and fundamentals before relying on price action alone.',
            },
            {
              category: 'sector',
              title: 'Sector and peer lane',
              summary: 'Context is Technology / Consumer Electronics. Current volume-price signal is price volume confirmed.',
              status: 'available',
              source: 'no_ai_news_center_rules',
              action: 'Open peer comparison or deep sector view for richer cross-asset context.',
            },
          ],
        },
        klineForecast: {
          title: 'K-line forecast lab',
          horizon: 'next_5_bars',
          direction: 'upside_bias',
          confidence: 72,
          support: 190,
          resistance: 205,
          adapterStatus: 'Kronos adapter ready; local rules preview only; Kronos model not installed or invoked.',
          source: 'local_kline_rules_kronos_ready',
          aiUsed: false,
          kronosModelUsed: false,
          premiumUnlock: 'Premium can run a configured Kronos or local-model forecast lane after model/data approval.',
          boundary: 'Experimental model preview; information analysis only; not investment advice.',
          scenarios: [
            {
              label: 'Upside-biased preview',
              direction: 'upside_bias',
              probability: 70,
              trigger: 'Hold above MA20 190 and keep volume change near +12.5%.',
              detail: 'Local rules read support near 190 and resistance near 205. This is not Kronos inference.',
            },
            {
              label: 'Breakout confirmation',
              direction: 'upside_bias',
              probability: 78,
              trigger: 'Price closes above resistance 205 with expanding volume.',
              detail: 'Treat this as a checklist for the next refresh, not a trade instruction.',
            },
            {
              label: 'Pullback risk',
              direction: 'downside_risk',
              probability: 30,
              trigger: 'Price loses support 190 or data freshness degrades.',
              detail: 'Recheck source freshness and broad-market references before interpreting weakness.',
            },
          ],
        },
        marketBrief: {
          market: 'us',
          title: 'US equity quick view',
          summary: 'US equity lane uses quote, history, profile, Nasdaq and sector references without AI.',
          lane: 'us_market_data',
          focusPoints: ['Price versus MA20', 'Volume confirmation', 'Nasdaq and sector ETF context'],
          deepUnlock: 'Deep analysis can add news, filings, sector comparison, and AI report.',
        },
        freeInsights: [
          {
            category: 'movement',
            title: 'Move explanation',
            summary: 'Price is +1.5% and holds above MA20 with positive short-term confirmation.',
            tone: 'positive',
            bullets: ['Price versus MA20', 'Volume confirmation'],
            source: 'no_ai_rules',
          },
          {
            category: 'peer_context',
            title: 'Peer context',
            summary: 'Compare this move with QQQ and XLK before reading AAPL in isolation.',
            tone: 'info',
            bullets: ['QQQ', 'XLK'],
            source: 'no_ai_route_rules',
          },
          {
            category: 'risk',
            title: 'Key risks',
            summary: 'No-AI quick view does not include realtime news, filings, or external search.',
            tone: 'warning',
            bullets: ['No AI', 'not investment advice'],
            source: 'no_ai_rules',
          },
        ],
        peerComparison: {
          title: 'Peer and market comparison',
          summary: 'Compare AAPL against QQQ and XLK before reading it in isolation.',
          rows: [
            {
              symbol: 'QQQ',
              label: 'QQQ',
              role: 'Broad market',
              reason: 'US large-cap technology benchmark.',
              currentSignal: 'AAPL is above MA20 with positive change.',
              compareNext: 'Check whether AAPL confirms faster or weaker than QQQ on the next refresh.',
              source: 'no_ai_route_rules',
            },
            {
              symbol: '^IXIC',
              label: 'Nasdaq Composite',
              role: 'Index lens',
              reason: 'US market index context.',
              currentSignal: 'AAPL is above MA20 with positive change.',
              compareNext: 'Check whether AAPL confirms faster or weaker than ^IXIC on the next refresh.',
              source: 'no_ai_route_rules',
            },
            {
              symbol: 'XLK',
              label: 'Technology sector ETF',
              role: 'Sector lens',
              reason: 'Sector context for Technology names.',
              currentSignal: 'AAPL is above MA20 with positive change.',
              compareNext: 'Check whether AAPL confirms faster or weaker than XLK on the next refresh.',
              source: 'no_ai_route_rules',
            },
          ],
        },
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
      canonicalData: {
        contractVersion: 'v1',
        symbol: 'AAPL',
        market: 'us',
        policy: {
          strategy: 'freshness_then_priority_then_observed_at',
          noAveraging: true,
          factsAndModelsSeparated: true,
        },
        selectedSources: {
          quote: { source: 'yahoo_chart', freshness: 'fresh', priority: 0, cacheState: 'miss' },
          history: { source: 'yfinance', freshness: 'fresh', priority: 1, cacheState: 'miss' },
          profile: { source: 'unit_profile', freshness: 'fresh', priority: null, cacheState: 'miss' },
        },
        fieldProvenance: {
          'quote.current_price': 'yahoo_chart',
          'profile.market_cap': 'unit_profile',
        },
        conflicts: [],
        deduplication: { inputCount: 4, outputCount: 3, removedCount: 1 },
        informationalOnly: true,
        aiUsed: false,
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
    expect(primarySummary).toHaveTextContent('科技');
    expect(primarySummary).toHaveTextContent('消费电子');
    expect(primarySummary).toHaveTextContent('4.5T');
    expect(primarySummary).toHaveTextContent('31.2');
    const compactOverview = screen.getByTestId('basic-query-compact-overview');
    expect(compactOverview).toHaveTextContent('行情速查');
    expect(compactOverview).toHaveTextContent('点击快速分析查看完整免费研判');
    expect(screen.queryByTestId('basic-query-broker-cockpit')).not.toBeInTheDocument();
    expect(screen.queryByTestId('basic-query-commercial-journey')).not.toBeInTheDocument();
    expect(screen.queryByTestId('basic-query-kline-forecast-lab')).not.toBeInTheDocument();

    fireEvent.click(screen.getAllByRole('button', { name: '快速分析' })[0]);
    await waitFor(() => {
      expect(stocksApi.snapshot).toHaveBeenCalledTimes(2);
    });
    expect(await screen.findByTestId('basic-query-mode-banner')).toHaveTextContent('快速分析模式');
    const decisionJourney = screen.getByTestId('basic-query-decision-journey-v91');
    expect(
      screen.getByTestId('basic-query-mode-banner').compareDocumentPosition(decisionJourney)
      & Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
    expect(decisionJourney).toHaveTextContent('V91 专业免费研判');
    expect(decisionJourney).toHaveTextContent('用户决策闭环');
    expect(decisionJourney).toHaveTextContent('结论');
    expect(decisionJourney).toHaveTextContent('价位地图');
    expect(decisionJourney).toHaveTextContent('风险边界');
    expect(decisionJourney).toHaveTextContent('关键证据');
    expect(decisionJourney).toHaveTextContent('美股重点');
    expect(decisionJourney).toHaveTextContent('财报与 SEC 文件');
    expect(decisionJourney).toHaveTextContent('证据库');
    expect(decisionJourney).toHaveTextContent('免费版包含');
    expect(decisionJourney).toHaveTextContent('高级版增强');
    expect(decisionJourney).toHaveTextContent('未用 AI，不扣额度');
    expect(decisionJourney).toHaveTextContent('仅作信息分析，不构成投资建议');
    const evidenceLibrary = within(decisionJourney).getByTestId('decision-journey-evidence-library');
    expect(evidenceLibrary).toHaveTextContent('行情量价');
    expect(evidenceLibrary).toHaveTextContent('技术证据');
    expect(evidenceLibrary).toHaveTextContent('资讯事件');
    expect(evidenceLibrary).toHaveTextContent('基本面');
    expect(evidenceLibrary).toHaveTextContent('来源可信度');
    expect(within(decisionJourney).getByTestId('decision-journey-price-chart')).toBeInTheDocument();
    expect(analysisApi.analyzeAsync).not.toHaveBeenCalled();
    expect(screen.queryByTestId('basic-query-first-screen-focus-v90')).not.toBeInTheDocument();
    expect(screen.queryByTestId('basic-query-broker-decision-desk-v89')).not.toBeInTheDocument();
    const nextActions = screen.getByTestId('basic-query-next-actions-v85');
    expect(
      decisionJourney.compareDocumentPosition(nextActions)
      & Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
    expect(nextActions).toHaveTextContent('下一步工作流');
    expect(nextActions).toHaveTextContent('刷新行情');
    expect(nextActions).toHaveTextContent('看资讯');
    expect(nextActions).toHaveTextContent('看同业');
    expect(nextActions).toHaveTextContent('看K线');
    expect(nextActions).toHaveTextContent('保存自选');
    expect(nextActions).toHaveTextContent('未用 AI，不扣额度');
    fireEvent.click(within(nextActions).getByRole('button', { name: '保存自选' }));
    expect(nextActions).toHaveTextContent('注册或登录后可保存自选');
    fireEvent.click(within(nextActions).getByRole('button', { name: '看资讯' }));
    fireEvent.click(within(nextActions).getByRole('button', { name: '看同业' }));
    fireEvent.click(within(nextActions).getByRole('button', { name: '看K线' }));
    expect(analysisApi.analyzeAsync).not.toHaveBeenCalled();
    const freeAnalystWorkbench = screen.getByTestId('basic-query-free-analyst-workbench-v86');
    expect(freeAnalystWorkbench).toHaveTextContent('免费研判工作台');
    expect(freeAnalystWorkbench).toHaveTextContent('像经纪人一样先看结论、证据、风险和下一步');
    expect(freeAnalystWorkbench).toHaveTextContent('是否值得继续看');
    expect(freeAnalystWorkbench).toHaveTextContent('当前最大看点');
    expect(freeAnalystWorkbench).toHaveTextContent('最大风险');
    expect(freeAnalystWorkbench).toHaveTextContent('下一步路径');
    expect(freeAnalystWorkbench).toHaveTextContent('免费版已经开放');
    expect(freeAnalystWorkbench).toHaveTextContent('高级版增强');
    expect(freeAnalystWorkbench).toHaveTextContent('未用 AI，不扣额度');
    expect(freeAnalystWorkbench).toHaveAttribute('data-density', 'secondary');
    fireEvent.click(within(freeAnalystWorkbench).getByRole('button', { name: '看资讯' }));
    fireEvent.click(within(freeAnalystWorkbench).getByRole('button', { name: '看K线' }));
    expect(analysisApi.analyzeAsync).not.toHaveBeenCalled();
    const visualAnalystPage = screen.getByTestId('basic-query-visual-analyst-page-v87');
    expect(visualAnalystPage).toHaveTextContent('可视化研判页');
    expect(visualAnalystPage).toHaveTextContent('先看图，再读结论');
    expect(visualAnalystPage).toHaveTextContent('趋势轨道');
    expect(visualAnalystPage).toHaveTextContent('量价确认');
    expect(visualAnalystPage).toHaveTextContent('支撑压力');
    expect(visualAnalystPage).toHaveTextContent('经纪人下一步');
    expect(visualAnalystPage).toHaveTextContent('免费版可见');
    expect(visualAnalystPage).toHaveTextContent('高级版增强');
    expect(visualAnalystPage).toHaveTextContent('未用 AI，不扣额度');
    expect(visualAnalystPage).toHaveAttribute('data-density', 'secondary');
    fireEvent.click(within(visualAnalystPage).getByRole('button', { name: '看资讯' }));
    fireEvent.click(within(visualAnalystPage).getByRole('button', { name: '看K线' }));
    expect(analysisApi.analyzeAsync).not.toHaveBeenCalled();
    const readingRoadmap = screen.getByTestId('basic-query-reading-roadmap-v88');
    expect(readingRoadmap).toHaveTextContent('3分钟研判路线');
    expect(readingRoadmap).toHaveTextContent('第一步：看结论');
    expect(readingRoadmap).toHaveTextContent('第二步：看图形证据');
    expect(readingRoadmap).toHaveTextContent('第三步：核对资讯与同业');
    expect(readingRoadmap).toHaveTextContent('第四步：看K线情景');
    expect(readingRoadmap).toHaveTextContent('免费版可完整阅读');
    expect(readingRoadmap).toHaveTextContent('高级版补数据源');
    expect(readingRoadmap).toHaveTextContent('未用 AI，不扣额度');
    expect(readingRoadmap).toHaveAttribute('data-density', 'secondary');
    const scrollIntoViewSpy = vi.fn();
    HTMLElement.prototype.scrollIntoView = scrollIntoViewSpy;
    fireEvent.click(within(readingRoadmap).getByRole('button', { name: '看资讯' }));
    fireEvent.click(within(readingRoadmap).getByRole('button', { name: '看同业' }));
    fireEvent.click(within(readingRoadmap).getByRole('button', { name: '看K线' }));
    expect(scrollIntoViewSpy).toHaveBeenCalledTimes(3);
    expect(scrollIntoViewSpy).toHaveBeenCalledWith({ behavior: 'auto', block: 'center' });
    expect(analysisApi.analyzeAsync).not.toHaveBeenCalled();
    const todayBriefCard = screen.getByTestId('basic-query-today-brief-card');
    expect(todayBriefCard).toHaveTextContent('今日看点摘要');
    expect(todayBriefCard).toHaveTextContent('一句话看法');
    expect(todayBriefCard).toHaveTextContent('AAPL');
    expect(todayBriefCard).toHaveTextContent('200');
    expect(todayBriefCard).toHaveTextContent('+1.5%');
    expect(todayBriefCard).toHaveTextContent('数据可信度');
    expect(todayBriefCard).toHaveTextContent('实时行情可用');
    expect(todayBriefCard).toHaveTextContent('下一步动作');
    expect(todayBriefCard).toHaveTextContent('刷新实时行情');
    expect(todayBriefCard).toHaveTextContent('风险边界');
    expect(todayBriefCard).toHaveTextContent('免费版已给出');
    expect(todayBriefCard).toHaveTextContent('高级版补齐');
    expect(todayBriefCard).toHaveTextContent('实时资讯/API');
    expect(todayBriefCard).toHaveTextContent('不构成投资建议');
    const brokerThreeStep = within(todayBriefCard).getByTestId('basic-query-broker-three-step-card');
    expect(brokerThreeStep).toHaveTextContent('经纪人三段判断');
    expect(brokerThreeStep).toHaveTextContent('能不能看');
    expect(brokerThreeStep).toHaveTextContent('可以继续看');
    expect(brokerThreeStep).toHaveTextContent('为什么看');
    expect(brokerThreeStep).toHaveTextContent('信号完整度 82/100');
    expect(brokerThreeStep).toHaveTextContent('什么时候升级');
    expect(brokerThreeStep).toHaveTextContent('需要实时资讯/API、来源链接或模型验证时升级');
    expect(brokerThreeStep).toHaveTextContent('免费版先给判断框架');
    expect(brokerThreeStep).toHaveTextContent('高级版补齐验证深度');
    expect(within(todayBriefCard).queryByTestId('basic-query-premium-preview-panel')).not.toBeInTheDocument();
    fireEvent.click(within(todayBriefCard).getByRole('button', { name: '查看高级版会新增哪些内容' }));
    const premiumPreviewPanel = within(todayBriefCard).getByTestId('basic-query-premium-preview-panel');
    expect(premiumPreviewPanel).toHaveTextContent('高级版报告结构预览');
    expect(premiumPreviewPanel).toHaveTextContent('只展示结构，不消耗额度');
    expect(premiumPreviewPanel).toHaveTextContent('实时资讯/API');
    expect(premiumPreviewPanel).toHaveTextContent('来源链接');
    expect(premiumPreviewPanel).toHaveTextContent('Kronos/API 模型验证');
    expect(premiumPreviewPanel).toHaveTextContent('持续跟踪与历史');
    expect(premiumPreviewPanel).toHaveTextContent('不会发起 AI 分析，不扣额度');
    const premiumConversion = within(premiumPreviewPanel).getByTestId('basic-query-premium-conversion-v84');
    expect(premiumConversion).toHaveTextContent('升级价值预览');
    expect(premiumConversion).toHaveTextContent('免费版同样可看');
    expect(premiumConversion).toHaveTextContent('高级版换 API 数据源');
    expect(premiumConversion).toHaveTextContent('实时新闻原文');
    expect(premiumConversion).toHaveTextContent('公告/SEC 原文链接');
    expect(premiumConversion).toHaveTextContent('同业强弱 API');
    expect(premiumConversion).toHaveTextContent('Kronos/API 预测');
    expect(premiumConversion).toHaveTextContent('持续跟踪提醒');
    expect(premiumConversion).toHaveTextContent('本地预览，不接真实支付');
    expect(stocksApi.snapshot).toHaveBeenCalledTimes(2);
    expect(analysisApi.analyzeAsync).not.toHaveBeenCalled();
    fireEvent.click(within(todayBriefCard).getByRole('button', { name: '收起高级版预览' }));
    expect(within(todayBriefCard).queryByTestId('basic-query-premium-preview-panel')).not.toBeInTheDocument();
    const freeEventCenter = screen.getByTestId('basic-query-free-event-center-v82');
    expect(freeEventCenter).toHaveTextContent('免费资讯与事件中心');
    expect(freeEventCenter).toHaveTextContent('为什么今天值得看');
    expect(freeEventCenter).toHaveTextContent('未用 AI，不扣额度');
    expect(freeEventCenter).toHaveTextContent('价格异动');
    expect(freeEventCenter).toHaveTextContent('资讯/公告');
    expect(freeEventCenter).toHaveTextContent('基本面背景');
    expect(freeEventCenter).toHaveTextContent('同业参照');
    expect(freeEventCenter).toHaveTextContent('免费版可立即做');
    expect(freeEventCenter).toHaveTextContent('高级版补充验证');
    expect(freeEventCenter).toHaveTextContent('实时资讯/API');
    expect(freeEventCenter).toHaveTextContent('来源链接');
    expect(freeEventCenter).toHaveTextContent('Kronos/API 模型');
    expect(freeEventCenter).toHaveTextContent('不构成投资建议');
    const defaultEventDetail = within(freeEventCenter).getByTestId('basic-query-free-event-detail-v83');
    expect(defaultEventDetail).toHaveTextContent('事件详情');
    expect(defaultEventDetail).toHaveTextContent('价格异动');
    expect(defaultEventDetail).toHaveTextContent('来源状态');
    expect(defaultEventDetail).toHaveTextContent('免费版下一步');
    expect(defaultEventDetail).toHaveTextContent('高级版验证');
    fireEvent.click(within(freeEventCenter).getByRole('button', { name: /资讯\/公告/ }));
    const newsEventDetail = within(freeEventCenter).getByTestId('basic-query-free-event-detail-v83');
    expect(newsEventDetail).toHaveTextContent('资讯/公告');
    expect(newsEventDetail).toHaveTextContent('来源状态');
    expect(newsEventDetail).toHaveTextContent('查看来源状态与原文链接');
    expect(newsEventDetail).toHaveTextContent('免费版下一步');
    expect(newsEventDetail).toHaveTextContent('高级版验证');
    fireEvent.click(within(freeEventCenter).getByRole('button', { name: /同业参照/ }));
    const peerEventDetail = within(freeEventCenter).getByTestId('basic-query-free-event-detail-v83');
    expect(peerEventDetail).toHaveTextContent('同业参照');
    expect(peerEventDetail).toHaveTextContent('对照同业/指数强弱');
    expect(analysisApi.analyzeAsync).not.toHaveBeenCalled();
    const proDecisionCard = screen.getByTestId('basic-query-pro-decision-card');
    expect(
      todayBriefCard.compareDocumentPosition(proDecisionCard)
      & Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
    expect(proDecisionCard).toHaveTextContent('专业研判总览');
    expect(proDecisionCard).toHaveTextContent('继续研究优先级');
    expect(proDecisionCard).toHaveTextContent('82/100');
    expect(proDecisionCard).toHaveTextContent('一句话结论');
    expect(proDecisionCard).toHaveTextContent('关键证据');
    expect(proDecisionCard).toHaveTextContent('价格结构');
    expect(proDecisionCard).toHaveTextContent('同业参照');
    expect(proDecisionCard).toHaveTextContent('风险先看');
    expect(proDecisionCard).toHaveTextContent('升级后补齐');
    expect(proDecisionCard).toHaveTextContent('免费版已开放');
    expect(proDecisionCard).toHaveTextContent('行情、技术、资讯、K线、同业、风险');
    expect(proDecisionCard).toHaveTextContent('高级版增强');
    expect(proDecisionCard).toHaveTextContent('实时 API');
    expect(proDecisionCard).toHaveTextContent('原文链接');
    expect(proDecisionCard).toHaveTextContent('模型深度');
    expect(proDecisionCard).toHaveTextContent('不构成投资建议');
    expect(
      primarySummary.compareDocumentPosition(proDecisionCard)
      & Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
    const quoteTrustPanel = screen.getByTestId('basic-query-quote-trust-panel');
    expect(quoteTrustPanel).toHaveTextContent('行情可信度');
    expect(quoteTrustPanel).toHaveTextContent('实时行情可用');
    expect(quoteTrustPanel).toHaveTextContent('刷新动作');
    expect(quoteTrustPanel).toHaveTextContent('刷新实时行情');
    expect(quoteTrustPanel).toHaveTextContent('来源对照');
    expect(quoteTrustPanel).toHaveTextContent('Yahoo 图表数据');
    expect(quoteTrustPanel).toHaveTextContent('分析口吻');
    expect(quoteTrustPanel).toHaveTextContent('可正常解读');
    expect(quoteTrustPanel).toHaveTextContent('高级版补齐');
    expect(quoteTrustPanel).toHaveTextContent('多源 API 对照');
    fireEvent.click(within(quoteTrustPanel).getByRole('button', { name: '刷新实时行情' }));
    await waitFor(() => {
      expect(stocksApi.snapshot).toHaveBeenCalledTimes(3);
    });
    expect(stocksApi.snapshot).toHaveBeenLastCalledWith('AAPL', { refresh: true });
    fireEvent.click(within(screen.getByTestId('basic-query-next-actions-v85')).getByRole('button', { name: '刷新行情' }));
    await waitFor(() => {
      expect(stocksApi.snapshot).toHaveBeenCalledTimes(4);
    });
    expect(stocksApi.snapshot).toHaveBeenLastCalledWith('AAPL', { refresh: true });
    const verifiedDataBoard = screen.getByTestId('basic-query-verified-data-board');
    expect(verifiedDataBoard).toHaveTextContent('真实数据增强');
    expect(verifiedDataBoard).toHaveTextContent('数据可信度');
    expect(verifiedDataBoard).toHaveTextContent('行情源');
    expect(verifiedDataBoard).toHaveTextContent('Yahoo 图表');
    expect(verifiedDataBoard).toHaveTextContent('公司资料源');
    expect(verifiedDataBoard).toHaveTextContent('公司资料');
    expect(verifiedDataBoard).toHaveTextContent('缓存状态');
    expect(verifiedDataBoard).toHaveTextContent('实时获取');
    expect(verifiedDataBoard).toHaveTextContent('来源健康');
    expect(verifiedDataBoard).toHaveTextContent('统一事实快照');
    expect(verifiedDataBoard).toHaveTextContent('3 类来源 / 0 项已发现冲突');
    expect(verifiedDataBoard).toHaveTextContent('已去除 1 条重复记录');
    expect(verifiedDataBoard).toHaveTextContent('同业/板块实况');
    expect(verifiedDataBoard).toHaveTextContent('QQQ');
    expect(verifiedDataBoard).toHaveTextContent('XLK');
    expect(verifiedDataBoard).toHaveTextContent('财务基础');
    expect(verifiedDataBoard).toHaveTextContent('总市值');
    expect(verifiedDataBoard).toHaveTextContent('4.5T');
    expect(verifiedDataBoard).toHaveTextContent('市盈率');
    expect(verifiedDataBoard).toHaveTextContent('31.2');
    expect(verifiedDataBoard).toHaveTextContent('市净率');
    expect(verifiedDataBoard).toHaveTextContent('48.6');
    expect(verifiedDataBoard).toHaveTextContent('股息率');
    expect(verifiedDataBoard).toHaveTextContent('0.5%');
    expect(verifiedDataBoard).toHaveTextContent('资讯/公告状态');
    expect(verifiedDataBoard).toHaveTextContent('SEC 文件通道');
    expect(verifiedDataBoard).toHaveTextContent('财务快照通道');
    expect(verifiedDataBoard).toHaveTextContent('免费版使用公开/本地源');
    expect(verifiedDataBoard).toHaveTextContent('高级版使用 API 和原文链接');
    expect(verifiedDataBoard).toHaveTextContent('不构成投资建议');
    expect(verifiedDataBoard).toHaveTextContent('量价信号为 价量确认');
    expect(verifiedDataBoard).not.toHaveTextContent('price volume confirmed');
    const eventRadar = screen.getByTestId('basic-query-event-radar');
    expect(eventRadar).toHaveTextContent('事件雷达');
    expect(eventRadar).toHaveTextContent('为什么涨跌');
    expect(eventRadar).toHaveTextContent('AAPL 上涨 1.5%');
    expect(eventRadar).toHaveTextContent('价格站上 MA20 190');
    expect(eventRadar).toHaveTextContent('成交量较 MA5 增加 12.5%');
    expect(eventRadar).toHaveTextContent('关键事件');
    expect(eventRadar).toHaveTextContent('趋势事件');
    expect(eventRadar).toHaveTextContent('量能事件');
    expect(eventRadar).toHaveTextContent('数据事件');
    expect(eventRadar).toHaveTextContent('下一步观察');
    expect(eventRadar).toHaveTextContent('刷新一次行情');
    expect(eventRadar).toHaveTextContent('继续对比 QQQ / XLK');
    expect(eventRadar).toHaveTextContent('高级版补齐');
    expect(eventRadar).toHaveTextContent('实时新闻/API');
    expect(eventRadar).toHaveTextContent('公告原文链接');
    expect(eventRadar).toHaveTextContent('Kronos/API 模型');
    expect(eventRadar).toHaveTextContent('不构成投资建议');
    const commercialJourney = screen.getByTestId('basic-query-commercial-journey');
    expect(commercialJourney).toHaveTextContent('免费查询完整路径');
    expect(commercialJourney).toHaveTextContent('免费版已开放');
    expect(commercialJourney).toHaveTextContent('先看结论');
    expect(commercialJourney).toHaveTextContent('再看研究');
    expect(commercialJourney).toHaveTextContent('最后决定是否深度分析');
    expect(commercialJourney).toHaveTextContent('行情、技术、资讯、K线、同业、风险');
    expect(commercialJourney).toHaveTextContent('高级版只换数据源');
    expect(commercialJourney).toHaveTextContent('实时新闻 API');
    expect(commercialJourney).toHaveTextContent('公告/SEC API');
    expect(commercialJourney).toHaveTextContent('Kronos/API 模型');
    expect(commercialJourney).toHaveTextContent('我的 API');
    expect(commercialJourney).toHaveTextContent('不登录也能查');
    expect(commercialJourney).not.toHaveTextContent('Upgrade to unlock');
    const brokerCockpit = screen.getByTestId('basic-query-broker-cockpit');
    expect(brokerCockpit).toHaveTextContent('经纪人首屏研判');
    expect(brokerCockpit).toHaveTextContent('现在值不值得继续看');
    expect(brokerCockpit).toHaveTextContent('结论');
    expect(brokerCockpit).toHaveTextContent('证据链');
    expect(brokerCockpit).toHaveTextContent('风险边界');
    expect(brokerCockpit).toHaveTextContent('升级后解决什么');
    expect(brokerCockpit).toHaveTextContent('免费版先给完整研究结构');
    expect(brokerCockpit).toHaveTextContent('高级版换实时 API、来源链接和模型深度');
    expect(brokerCockpit).toHaveTextContent('不构成投资建议');
    expect(
      primarySummary.compareDocumentPosition(brokerCockpit)
      & Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
    expect(
      brokerCockpit.compareDocumentPosition(commercialJourney)
      & Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
    const dataDepthBoard = screen.getByTestId('basic-query-data-depth-board');
    expect(dataDepthBoard).toHaveTextContent('免费版真实数据面板');
    expect(dataDepthBoard).toHaveTextContent('美股重点数据');
    expect(dataDepthBoard).toHaveTextContent('核心数据');
    expect(dataDepthBoard).toHaveTextContent(/最新价\s*200/);
    expect(dataDepthBoard).toHaveTextContent(/涨跌幅\s*\+1.5%/);
    expect(dataDepthBoard).toHaveTextContent(/成交量\s*75.35M/);
    expect(dataDepthBoard).toHaveTextContent(/总市值\s*4.5T/);
    expect(dataDepthBoard).toHaveTextContent(/市盈率\s*31.2/);
    expect(dataDepthBoard).toHaveTextContent('技术结构');
    expect(dataDepthBoard).toHaveTextContent(/MA5\s*198/);
    expect(dataDepthBoard).toHaveTextContent(/MA20\s*190/);
    expect(dataDepthBoard).toHaveTextContent(/支撑\s*190/);
    expect(dataDepthBoard).toHaveTextContent(/压力\s*205/);
    expect(dataDepthBoard).toHaveTextContent('资讯与事件');
    expect(dataDepthBoard).toHaveTextContent('SEC 文件通道');
    expect(dataDepthBoard).toHaveTextContent('财务快照通道');
    expect(dataDepthBoard).toHaveTextContent('同业与风险');
    expect(dataDepthBoard).toHaveTextContent('QQQ');
    expect(dataDepthBoard).toHaveTextContent('XLK');
    expect(dataDepthBoard).toHaveTextContent('仅作信息分析，不构成投资建议');
    expect(dataDepthBoard).not.toHaveTextContent('Free data depth board');
    const coreDetail = screen.getByTestId('basic-query-data-detail-core');
    expect(coreDetail).toHaveTextContent('展开详情');
    expect(coreDetail).toHaveTextContent(/开盘\s*198/);
    expect(coreDetail).toHaveTextContent(/最高\s*205/);
    expect(coreDetail).toHaveTextContent(/最低\s*197/);
    expect(coreDetail).toHaveTextContent(/昨收\s*197/);
    expect(coreDetail).toHaveTextContent('NASDAQ');
    expect(coreDetail).toHaveTextContent('美国');
    const eventDetail = screen.getByTestId('basic-query-data-detail-events');
    expect(eventDetail).toHaveTextContent('事件清单');
    expect(eventDetail).toHaveTextContent('影响行情的资讯通道');
    expect(eventDetail).toHaveTextContent('状态：降级');
    expect(eventDetail).toHaveTextContent('下一步：使用深度分析或配置资讯源');
    const peerTable = screen.getByTestId('basic-query-peer-table');
    expect(peerTable).toHaveTextContent('同业对比表');
    expect(peerTable).toHaveTextContent('标的');
    expect(peerTable).toHaveTextContent('角色');
    expect(peerTable).toHaveTextContent('当前信号');
    expect(peerTable).toHaveTextContent('下次对比');
    expect(peerTable).toHaveTextContent('大盘');
    expect(peerTable).toHaveTextContent('纳斯达克综合指数');
    expect(peerTable).toHaveTextContent('科技行业 ETF');
    const klineTriggers = screen.getByTestId('basic-query-kline-triggers');
    expect(klineTriggers).toHaveTextContent('K线触发条件');
    expect(klineTriggers).toHaveTextContent('上行倾向预览');
    expect(klineTriggers).toHaveTextContent('突破确认');
    expect(klineTriggers).toHaveTextContent('回落风险');
    expect(klineTriggers).toHaveTextContent('守住 MA20 190');
    expect(klineTriggers).toHaveTextContent('价格放量收在压力位 205 上方');
    expect(klineTriggers).toHaveTextContent('价格跌破支撑 190');
    expect(
      primarySummary.compareDocumentPosition(commercialJourney)
      & Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
    const professionalOverview = screen.getByTestId('basic-query-professional-overview');
    expect(professionalOverview).toHaveTextContent('专业速览');
    expect(professionalOverview).toHaveTextContent('趋势评分');
    expect(professionalOverview).toHaveTextContent('82/100');
    expect(professionalOverview).toHaveTextContent('风险等级');
    expect(professionalOverview).toHaveTextContent('低');
    expect(professionalOverview).toHaveTextContent('数据通道');
    expect(professionalOverview).toHaveTextContent('免费网络源');
    expect(professionalOverview).toHaveTextContent('高级 API 源');
    expect(professionalOverview).toHaveTextContent('模块导航');
    expect(professionalOverview).toHaveTextContent('行情概览');
    expect(professionalOverview).toHaveTextContent('技术面');
    expect(professionalOverview).toHaveTextContent('资讯中心');
    expect(professionalOverview).toHaveTextContent('K线预测');
    expect(professionalOverview).not.toHaveTextContent('高级版解锁');
    const freeResearchBoard = screen.getByTestId('basic-query-free-research-board');
    expect(freeResearchBoard).toHaveTextContent('免费研究看板');
    expect(freeResearchBoard).toHaveTextContent('同样内容，高级版换用 API 数据源');
    expect(freeResearchBoard).toHaveTextContent('资讯雷达');
    expect(freeResearchBoard).toHaveTextContent('SEC 文件通道');
    expect(freeResearchBoard).toHaveTextContent('财务快照通道');
    expect(freeResearchBoard).toHaveTextContent('K线推演');
    expect(freeResearchBoard).toHaveTextContent('未来 5 根K线');
    expect(freeResearchBoard).toHaveTextContent('上行倾向');
    expect(freeResearchBoard).toHaveTextContent('支撑 190');
    expect(freeResearchBoard).toHaveTextContent('压力 205');
    expect(freeResearchBoard).toHaveTextContent('同业/板块');
    expect(freeResearchBoard).toHaveTextContent('QQQ');
    expect(freeResearchBoard).toHaveTextContent('XLK');
    expect(freeResearchBoard).toHaveTextContent('风险解释');
    expect(freeResearchBoard).toHaveTextContent('实时新闻');
    expect(freeResearchBoard).toHaveTextContent('不构成投资建议');
    expect(freeResearchBoard).not.toHaveTextContent('Research radar');
    const valueSummary = screen.getByTestId('basic-query-free-value-summary');
    expect(valueSummary).toHaveTextContent('免费版重点结论');
    expect(valueSummary).toHaveTextContent('当前看点');
    expect(valueSummary).toHaveTextContent('风险边界');
    expect(valueSummary).toHaveTextContent('数据通道差异');
    expect(valueSummary).toHaveTextContent('深度分析');
    const completeRead = screen.getByTestId('basic-query-free-complete-read');
    expect(valueSummary).toContainElement(completeRead);
    expect(completeRead).toHaveTextContent('免费版完整速读');
    expect(completeRead).toHaveTextContent('机会看点');
    expect(completeRead).toHaveTextContent('风险边界');
    expect(completeRead).toHaveTextContent('下一步观察');
    expect(completeRead).toHaveTextContent('数据来源');
    expect(completeRead).toHaveTextContent('版本差异');
    expect(completeRead).toHaveTextContent('免费版看同样模块');
    expect(completeRead).toHaveTextContent('高级版使用 API');
    expect(completeRead).not.toHaveTextContent('高级版可解锁');
    expect(completeRead).not.toHaveTextContent('Trend confirmation');
    expect(completeRead).not.toHaveTextContent('Volume confirmation');
    expect(completeRead).not.toHaveTextContent('fresh');
    expect(completeRead).not.toHaveTextContent('us_market_data');
    const featureEntry = screen.getByTestId('basic-query-free-feature-entry');
    expect(valueSummary).toContainElement(featureEntry);
    expect(valueSummary).toContainElement(screen.getByTestId('basic-query-feature-entry-news'));
    expect(valueSummary).toContainElement(screen.getByTestId('basic-query-feature-entry-kline'));
    expect(
      primarySummary.compareDocumentPosition(valueSummary)
      & Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
    const freeReport = screen.getByTestId('basic-query-free-report');
    expect(freeReport).toHaveTextContent('未用 AI');
    expect(freeReport).toHaveTextContent('科技');
    expect(freeReport).toHaveTextContent('消费电子');
    expect(freeReport).toHaveTextContent('MA5');
    expect(freeReport).toHaveTextContent('MA20');
    expect(freeReport).toHaveTextContent('4.5T');
    expect(freeReport).toHaveTextContent('31.2');
    const signalScore = screen.getByTestId('basic-query-signal-score');
    expect(signalScore).toHaveTextContent('82/100');
    expect(signalScore).toHaveTextContent('快速信号较强');
    expect(signalScore).toHaveTextContent('趋势');
    expect(signalScore).toHaveTextContent('量价');
    expect(signalScore).toHaveTextContent('数据新鲜度');
    expect(signalScore).toHaveTextContent('资料完整度');
    expect(signalScore).toHaveTextContent('未用 AI');
    expect(signalScore).not.toHaveTextContent('Constructive quick signal');
    expect(signalScore).not.toHaveTextContent('Price 200 is above MA5');
    expect(signalScore).not.toHaveTextContent('Price is above trend');
    const retentionBrief = screen.getByTestId('basic-query-retention-brief');
    expect(retentionBrief).toHaveTextContent('AAPL 快速解读');
    expect(retentionBrief).toHaveTextContent('科技 / 消费电子');
    expect(retentionBrief).toHaveTextContent('支撑 190；压力 205');
    expect(retentionBrief).toHaveTextContent('与 QQQ 对比');
    expect(retentionBrief).toHaveTextContent('登录后可保存历史');
    expect(retentionBrief).toHaveTextContent('不构成投资建议');
    const newsCenter = screen.getByTestId('basic-query-news-center');
    expect(newsCenter).toHaveTextContent('本地资讯中心');
    expect(newsCenter).toHaveTextContent('影响行情的资讯通道');
    expect(newsCenter).toHaveTextContent('SEC 文件通道');
    expect(newsCenter).toHaveTextContent('财务快照通道');
    expect(newsCenter).toHaveTextContent('板块与同业通道');
    expect(newsCenter).toHaveTextContent('未用 AI');
    expect(newsCenter).toHaveTextContent('未用公共搜索');
    expect(newsCenter).toHaveTextContent('高级版使用 API');
    const klineForecast = screen.getByTestId('basic-query-kline-forecast-lab');
    expect(klineForecast).toHaveTextContent('K线预测实验室');
    expect(klineForecast).toHaveTextContent('未来 5 根K线');
    expect(klineForecast).toHaveTextContent('72/100');
    expect(klineForecast).toHaveTextContent('Kronos 适配器已就绪');
    expect(klineForecast).toHaveTextContent('上行倾向预览');
    expect(klineForecast).toHaveTextContent('突破确认');
    expect(klineForecast).toHaveTextContent('回落风险');
    expect(klineForecast).toHaveTextContent('不构成投资建议');
    fireEvent.click(screen.getByTestId('basic-query-kronos-run'));
    await waitFor(() => {
      expect(stocksApi.kronosForecast).toHaveBeenCalledWith('AAPL', {
        lookback: 120,
        horizon: 5,
        requireModel: false,
      });
    });
    const kronosResult = await screen.findByTestId('basic-query-kronos-live-result');
    const kronosReadiness = screen.getByTestId('basic-query-kronos-readiness-summary');
    expect(kronosReadiness).toHaveTextContent('这不是运行失败');
    expect(kronosReadiness).toHaveTextContent('当前使用本地K线规则兜底');
    expect(kronosReadiness).toHaveTextContent('真实 Kronos 模型尚未启用');
    expect(kronosReadiness).toHaveTextContent('高级版可在模型或 API 通道确认后启用完整预测');
    expect(kronosResult).toHaveTextContent('模型不可用');
    expect(kronosResult).toHaveTextContent('本地规则兜底');
    expect(kronosResult).toHaveTextContent('Kronos 行情数据获取超时，已使用本地规则兜底。');
    expect(kronosResult).toHaveTextContent('KRONOS_ENABLED 未开启，当前仅使用本地规则兜底。');
    expect(kronosResult).toHaveTextContent('K线上下文不足，置信度已降低。');
    expect(kronosResult).not.toHaveTextContent('Kronos market data fetch timed out');
    expect(kronosResult).not.toHaveTextContent('KRONOS_ENABLED is false');
    expect(kronosResult).not.toHaveTextContent('K-line context is short');
    expect(kronosResult).toHaveTextContent('运行设备');
    expect(kronosResult).toHaveTextContent('模型未运行');
    expect(kronosResult).toHaveTextContent('模型加载 0ms');
    expect(kronosResult).toHaveTextContent('推理 0ms');
    expect(kronosResult).toHaveTextContent('峰值显存 0MB');
    expect(screen.getByTestId('basic-query-kronos-dependency-status')).toHaveTextContent('torch: 缺失');
    expect(screen.getByTestId('basic-query-kronos-backtest-summary')).toHaveTextContent('1 条记录');
    const premiumFeatureLadder = screen.getByTestId('basic-query-premium-feature-ladder');
    expect(premiumFeatureLadder).toHaveTextContent('同样功能');
    expect(premiumFeatureLadder).toHaveTextContent('免费网络源');
    expect(premiumFeatureLadder).toHaveTextContent('高级 API 源');
    expect(premiumFeatureLadder).toHaveTextContent('Kronos 已就绪');
    expect(premiumFeatureLadder).toHaveTextContent('我的 API 或本地模型');
    expect(premiumFeatureLadder).not.toHaveTextContent('高级资讯');
    const productBrief = screen.getByTestId('basic-query-product-brief');
    expect(productBrief).toHaveTextContent('关键结论');
    expect(productBrief).toHaveTextContent('支撑');
    expect(productBrief).toHaveTextContent('压力');
    expect(productBrief).toHaveTextContent('短线');
    expect(productBrief).toHaveTextContent('中线');
    expect(productBrief).toHaveTextContent('风险边界');
    expect(productBrief).toHaveTextContent('继续深度分析');
    expect(productBrief).toHaveTextContent('未用 AI');
    const miniChart = screen.getByTestId('basic-query-mini-chart');
    expect(miniChart).toHaveTextContent('6日趋势');
    expect(miniChart).toHaveTextContent('+6.38%');
    expect(miniChart.querySelector('svg')).toBeInTheDocument();
    const intelligencePanel = screen.getByTestId('basic-query-intelligence-panel');
    expect(intelligencePanel).toHaveTextContent('资讯摘要');
    expect(intelligencePanel).toHaveTextContent('新闻');
    expect(intelligencePanel).toHaveTextContent('公告');
    expect(intelligencePanel).toHaveTextContent('财报');
    expect(intelligencePanel).toHaveTextContent('免费未用 AI 模式未启用实时新闻源');
    expect(intelligencePanel).toHaveTextContent('未用 AI');
    expect(intelligencePanel).toHaveTextContent('不构成投资建议');
    const marketBrief = screen.getByTestId('basic-query-market-brief');
    expect(marketBrief).toHaveTextContent('市场通道');
    expect(marketBrief).toHaveTextContent('美股快速视图');
    expect(marketBrief).toHaveTextContent('美股行情数据');
    expect(marketBrief).toHaveTextContent('纳指与行业 ETF 背景');
    const freeInsights = screen.getByTestId('basic-query-free-insights');
    expect(freeInsights).not.toHaveTextContent('Technology / Consumer Electronics');
    expect(freeInsights).not.toHaveTextContent('quick profile context');
    expect(freeInsights).not.toHaveTextContent('holds above MA20');
    expect(freeInsights).not.toHaveTextContent('volume is');
    expect(freeInsights).toHaveTextContent('免费洞察');
    expect(freeInsights).toHaveTextContent('波动解释');
    expect(freeInsights).toHaveTextContent('同业背景');
    expect(freeInsights).toHaveTextContent('关键风险');
    expect(freeInsights).toHaveTextContent('QQQ');
    expect(freeInsights).toHaveTextContent('未用 AI 快速视图');
    const peerComparison = screen.getByTestId('basic-query-peer-comparison');
    expect(peerComparison).toHaveTextContent('同业/大盘对照');
    expect(peerComparison).toHaveTextContent('AAPL');
    expect(peerComparison).toHaveTextContent('QQQ');
    expect(peerComparison).toHaveTextContent('^IXIC');
    expect(peerComparison).toHaveTextContent('XLK');
    expect(peerComparison).toHaveTextContent('行业参照');
    expect(peerComparison).toHaveTextContent('AAPL 当前高于 MA20');
    const watchPoints = screen.getByTestId('basic-query-watch-points');
    expect(watchPoints).toHaveTextContent('下一步观察');
    expect(watchPoints).toHaveTextContent('趋势确认');
    expect(watchPoints).toHaveTextContent('MA20');
    expect(watchPoints).toHaveTextContent('量能确认');
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
    expect(screen.getByTestId('basic-query-company-profile')).toHaveTextContent('科技');
    expect(screen.getByTestId('basic-query-company-profile')).toHaveTextContent('消费电子');
    expect(screen.getByTestId('basic-query-company-profile')).toHaveTextContent('NASDAQ');
    expect(screen.getByTestId('basic-query-company-profile')).toHaveTextContent('USD');
    expect(screen.getByTestId('basic-query-company-profile')).toHaveTextContent('4.5T');
    expect(screen.getByTestId('basic-query-company-profile')).toHaveTextContent('31.2');
    expect(screen.getByTestId('basic-query-company-profile')).toHaveTextContent('公司资料');
    expect(screen.getByTestId('basic-query-snapshot')).toHaveTextContent('未用 AI');
    expect(screen.getByTestId('basic-query-diagnostics-details')).not.toHaveAttribute('open');
    expect(screen.getByTestId('basic-query-diagnostics')).toHaveTextContent('18ms');
    expect(screen.getByTestId('basic-query-diagnostics')).toHaveTextContent('Q 未命中 / H 未命中');
    expect(screen.getByTestId('basic-query-diagnostics')).toHaveTextContent('Q 实时 / H 实时');
    expect(screen.getByTestId('basic-query-diagnostics')).toHaveTextContent('Q 正常 / H 正常');
    expect(screen.getByTestId('basic-query-diagnostics')).toHaveTextContent('Q 内存 / H 内存');
  }, 15000);

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
    expect(screen.getByTestId('basic-query-diagnostics')).toHaveTextContent('强制刷新');
    expect(screen.getByTestId('basic-query-diagnostics')).toHaveTextContent('Q 刷新 / H 刷新');
  });

  it('explains stale data recovery and premium source gaps in quick mode', async () => {
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
        changePercent: 1.5,
        source: 'yahoo_chart',
        freshness: 'stale',
      },
      indicators: {
        ma5: 198,
        ma20: 190,
        volumeChangeVsMa5: 12.5,
      },
      profile: {
        companyName: 'Apple Inc.',
        sector: 'Technology',
        industry: 'Consumer Electronics',
        marketCap: 4500000000000,
        peRatio: 31.2,
        source: 'unit_profile',
        freshness: 'fresh',
      },
      trend: {
        window: 2,
        source: 'unit_history',
        minClose: 190,
        maxClose: 200,
        changePercent: 5.2,
        points: [
          { date: '2026-07-01', close: 190, volume: 70000000 },
          { date: '2026-07-02', close: 200, volume: 75352800 },
        ],
      },
      diagnostics: {
        elapsedMs: 18,
        quoteElapsedMs: 8,
        historyElapsedMs: 10,
        cache: { quote: 'hit', history: 'hit' },
        sources: { quote: 'yahoo_chart', history: 'yfinance' },
        freshness: { quote: 'stale', history: 'stale' },
        fallback: { quote: 'stale_disk_cache', history: 'stale_disk_cache' },
        persistentCache: { quote: 'memory', history: 'memory', mode: 'local_json' },
        refresh: { mode: 'cache_first', requested: false },
        sourceHealth: {
          quote: { source: 'unit_quote', status: 'ok', consecutiveFailures: 0 },
          history: { source: 'unit_history', status: 'cooling_down', consecutiveFailures: 2 },
        },
        routeLane: 'us_market_data',
        performance: { status: 'ok', slowThresholdMs: 3000 },
      },
      aiUsed: false,
    });
    vi.mocked(analysisApi.analyzeAsync).mockRejectedValue(new Error('AI should not run for source recovery'));

    render(
      <MemoryRouter>
        <HomePage />
      </MemoryRouter>,
    );

    const input = await screen.findByRole('textbox');
    fireEvent.change(input, { target: { value: 'AAPL' } });
    fireEvent.click(screen.getAllByRole('button', { name: '快速分析' })[0]);

    const recoveryPanel = await screen.findByTestId('basic-query-source-recovery-panel');
    expect(recoveryPanel).toHaveTextContent('数据源修复建议');
    expect(recoveryPanel).toHaveTextContent('为什么提示过期/缓存');
    expect(recoveryPanel).toHaveTextContent('免费版现在可做');
    expect(recoveryPanel).toHaveTextContent('先点刷新实时行情');
    expect(recoveryPanel).toHaveTextContent('网络或代理异常时稍后重试');
    expect(recoveryPanel).toHaveTextContent('高级版补齐');
    expect(recoveryPanel).toHaveTextContent('多源 API 对照');
    expect(recoveryPanel).toHaveTextContent('自动预热和恢复');
    expect(recoveryPanel).toHaveTextContent('过期磁盘缓存');
    expect(recoveryPanel).not.toHaveTextContent('stale_disk_cache');
    fireEvent.click(screen.getByTestId('basic-query-source-recovery-refresh'));
    await waitFor(() => {
      expect(stocksApi.snapshot).toHaveBeenLastCalledWith('AAPL', { refresh: true });
    });
    expect(analysisApi.analyzeAsync).not.toHaveBeenCalled();
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

    expect(await screen.findByTestId('basic-query-route')).toHaveTextContent('加密货币行情数据');
    expect(screen.getByTestId('basic-query-diagnostics')).toHaveTextContent('Q 命中 / H 命中');
    expect(screen.getByTestId('basic-query-diagnostics')).toHaveTextContent('Q 过期缓存 / H 缓存');
    expect(screen.getByTestId('basic-query-degradation')).toHaveTextContent('行情过期');
    expect(analysisApi.analyzeAsync).not.toHaveBeenCalled();
  });

  it('keeps the same free detail modules visible for all market routes with basic snapshots', async () => {
    const cases = [
      {
        query: '600519.SH',
        stockCode: '600519',
        stockName: '贵州茅台',
        market: 'cn',
        lane: 'a_share_market_data',
        channel: 'a_share_equity',
        source: 'a_share_realtime',
        marketTitle: 'A股重点数据',
        laneLabel: 'A股行情数据',
        peerLabel: '沪深300',
        price: 1188.8,
        ma5: 1195.78,
        ma20: 1212.96,
      },
      {
        query: 'AAPL',
        stockCode: 'AAPL',
        stockName: 'Apple Inc.',
        market: 'us',
        lane: 'us_market_data',
        channel: 'us_equity',
        source: 'yahoo_chart',
        marketTitle: '美股重点数据',
        laneLabel: '美股行情数据',
        peerLabel: '纳斯达克综合指数',
        price: 200,
        ma5: 198,
        ma20: 190,
      },
      {
        query: '00700.HK',
        stockCode: '00700.HK',
        stockName: '腾讯控股',
        market: 'hk',
        lane: 'hk_market_data',
        channel: 'hk_equity',
        source: 'yahoo_chart',
        marketTitle: '港股重点数据',
        laneLabel: '港股行情数据',
        peerLabel: '恒生指数',
        price: 390.2,
        ma5: 388,
        ma20: 376,
      },
      {
        query: 'BTC-USD',
        stockCode: 'BTC-USD',
        stockName: 'Bitcoin',
        market: 'crypto',
        lane: 'crypto_market_data',
        channel: 'crypto_spot',
        source: 'crypto_yahoo_chart',
        marketTitle: '加密货币重点数据',
        laneLabel: '加密货币行情数据',
        peerLabel: '以太坊',
        price: 108000,
        ma5: 106800,
        ma20: 102400,
      },
    ];

    for (const item of cases) {
      vi.clearAllMocks();
      vi.mocked(historyApi.getList).mockResolvedValue({
        total: 0,
        page: 1,
        limit: 20,
        items: [],
      });
      vi.mocked(stocksApi.snapshot).mockResolvedValue({
        stockCode: item.stockCode,
        stockName: item.stockName,
        market: item.market,
        quote: {
          currentPrice: item.price,
          change: item.price * 0.012,
          changePercent: 1.2,
          open: item.price * 0.99,
          high: item.price * 1.03,
          low: item.price * 0.98,
          prevClose: item.price * 0.988,
          volume: 1200000,
          amount: item.price * 1200000,
          source: item.source,
          freshness: 'fresh',
        },
        indicators: {
          ma5: item.ma5,
          ma20: item.ma20,
          volumeChangeVsMa5: 8.6,
          volumePriceSignal: 'price_volume_confirmed',
        },
        route: {
          inputCode: item.query,
          normalizedCode: item.stockCode,
          market: item.market,
          channel: item.channel,
          dataSourceLane: item.lane,
          quoteSources: [item.source],
          historySources: [item.source],
          aiRequired: false,
        },
        diagnostics: {
          elapsedMs: 9,
          quoteElapsedMs: 4,
          historyElapsedMs: 5,
          cache: { quote: 'miss', history: 'miss' },
          sources: { quote: item.source, history: item.source },
          freshness: { quote: 'fresh', history: 'fresh' },
          timeouts: { quote: false, history: false },
          errors: { quote: null, history: null },
          fallback: { quote: 'live', history: 'live' },
          sourceHealth: {
            quote: { source: item.source, status: 'ok', consecutiveFailures: 0 },
            history: { source: item.source, status: 'ok', consecutiveFailures: 0 },
          },
          persistentCache: { quote: 'memory', history: 'memory', mode: 'local_json' },
          routeLane: item.lane,
          performance: { status: 'ok', slowThresholdMs: 3000 },
        },
        aiUsed: false,
      });
      vi.mocked(analysisApi.analyzeAsync).mockRejectedValue(new Error('AI should not run for free basic route'));

      render(
        <MemoryRouter>
          <HomePage />
        </MemoryRouter>,
      );

      fireEvent.change(await screen.findByPlaceholderText('输入股票代码或名称，如 600519、贵州茅台、AAPL'), {
        target: { value: item.query },
      });
      fireEvent.click(screen.getByRole('button', { name: '查询' }));
      await openQuickAnalysisFromCurrentSnapshot();

      const board = await screen.findByTestId('basic-query-data-depth-board');
      if (item.market === 'cn') {
        expect(stocksApi.snapshot).toHaveBeenCalledWith(item.query, { aShareSourceMode: 'a_stock_data' });
      } else {
        expect(stocksApi.snapshot).toHaveBeenCalledWith(item.query);
      }
      expect(board).toHaveTextContent(item.marketTitle);
      expect(board).toHaveTextContent(item.laneLabel);
      expect(board).toHaveTextContent('核心数据');
      expect(board).toHaveTextContent('技术结构');
      expect(board).toHaveTextContent('资讯与事件');
      expect(board).toHaveTextContent('同业与风险');
      expect(screen.getByTestId('basic-query-data-detail-events')).toHaveTextContent('事件清单');
      expect(screen.getByTestId('basic-query-kline-triggers')).toHaveTextContent('K线触发条件');
      expect(screen.getByTestId('basic-query-kline-triggers')).toHaveTextContent('突破确认');
      const peerTable = screen.getByTestId('basic-query-peer-table');
      expect(peerTable).toHaveTextContent('同业对比表');
      expect(peerTable).toHaveTextContent(item.peerLabel);
      expect(analysisApi.analyzeAsync).not.toHaveBeenCalled();
      cleanup();
    }
  }, 15000);

  it('localizes backend comparison targets in the Chinese free detail view', async () => {
    const cases = [
      {
        query: '00700.HK',
        stockCode: 'HK00700',
        stockName: '腾讯控股',
        market: 'hk',
        lane: 'hk_market_data',
        label: 'Hang Seng Index',
        status: 'Index lens',
        reason: 'Hong Kong market reference.',
        expectedLabel: '恒生指数',
        expectedStatus: '指数参照',
        expectedReason: '香港市场参照',
      },
      {
        query: 'BTC-USD',
        stockCode: 'BTC-USD',
        stockName: 'Bitcoin',
        market: 'crypto',
        lane: 'crypto_market_data',
        label: 'Ethereum',
        status: 'Crypto beta',
        reason: 'Large-cap crypto rotation reference.',
        expectedLabel: '以太坊',
        expectedStatus: '加密参照',
        expectedReason: '大市值加密资产轮动参照',
      },
    ];

    for (const item of cases) {
      vi.clearAllMocks();
      vi.mocked(historyApi.getList).mockResolvedValue({
        total: 0,
        page: 1,
        limit: 20,
        items: [],
      });
      vi.mocked(stocksApi.snapshot).mockResolvedValue({
        stockCode: item.stockCode,
        stockName: item.stockName,
        market: item.market,
        quote: {
          currentPrice: item.market === 'hk' ? 431.2 : 63709.8,
          change: 1.2,
          changePercent: 0.3,
          open: 430,
          high: 445,
          low: 424,
          prevClose: 429,
          volume: 2400000,
          amount: 1030000000,
          source: 'local_test',
          freshness: 'fresh',
        },
        indicators: {
          ma5: 424.64,
          ma20: 440.6,
          volumeChangeVsMa5: -12.5,
          volumePriceSignal: 'neutral',
        },
        route: {
          inputCode: item.query,
          normalizedCode: item.stockCode,
          market: item.market,
          channel: item.market === 'crypto' ? 'crypto_spot' : 'hk_equity',
          dataSourceLane: item.lane,
          quoteSources: ['local_test'],
          historySources: ['local_test'],
          aiRequired: false,
        },
        diagnostics: {
          elapsedMs: 10,
          quoteElapsedMs: 5,
          historyElapsedMs: 5,
          cache: { quote: 'miss', history: 'miss' },
          sources: { quote: 'local_test', history: 'local_test' },
          freshness: { quote: 'fresh', history: 'fresh' },
          timeouts: { quote: false, history: false },
          errors: { quote: null, history: null },
          fallback: { quote: 'live', history: 'live' },
          sourceHealth: {
            quote: { source: 'local_test', status: 'ok', consecutiveFailures: 0 },
            history: { source: 'local_test', status: 'ok', consecutiveFailures: 0 },
          },
          persistentCache: { quote: 'memory', history: 'memory', mode: 'local_json' },
          routeLane: item.lane,
          performance: { status: 'ok', slowThresholdMs: 3000 },
        },
        intelligence: {
          mode: 'free_rules',
          aiUsed: false,
          items: [],
          comparisonTargets: [
            {
              symbol: item.market === 'hk' ? '^HSI' : 'ETH-USD',
              label: item.label,
              status: item.status,
              reason: item.reason,
              source: 'local_test',
            },
          ],
        },
        aiUsed: false,
      });

      render(
        <MemoryRouter>
          <HomePage />
        </MemoryRouter>,
      );

      fireEvent.change(await screen.findByPlaceholderText('输入股票代码或名称，如 600519、贵州茅台、AAPL'), {
        target: { value: item.query },
      });
      fireEvent.click(screen.getByRole('button', { name: '查询' }));
      await openQuickAnalysisFromCurrentSnapshot();

      const peerTable = await screen.findByTestId('basic-query-peer-table');
      expect(peerTable).toHaveTextContent(item.expectedLabel);
      expect(peerTable).toHaveTextContent(item.expectedStatus);
      expect(peerTable).toHaveTextContent(item.expectedReason);
      expect(peerTable).not.toHaveTextContent(item.label);
      expect(peerTable).not.toHaveTextContent(item.status);
      expect(peerTable).not.toHaveTextContent(item.reason);
      cleanup();
    }
  });

  it('shows free comparison reference quote values in Chinese mode', async () => {
    window.localStorage.setItem(UI_LANGUAGE_STORAGE_KEY, 'zh-CN');
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
        currentPrice: 308.63,
        changePercent: 4.75,
        source: 'unit_quote',
        freshness: 'fresh',
      },
      profile: {
        companyName: 'Apple Inc.',
        sector: 'Technology',
        industry: 'Consumer Electronics',
        marketCap: 4530000000000,
        peRatio: 37.3192,
        source: 'unit_profile',
        freshness: 'fresh',
      },
      indicators: { ma5: 291.578, ma20: 294.8025 },
      route: {
        inputCode: 'AAPL',
        normalizedCode: 'AAPL',
        market: 'us',
        channel: 'us_equity',
        dataSourceLane: 'us_market_data',
        quoteSources: ['unit_quote'],
        historySources: ['unit_history'],
        aiRequired: false,
      },
      diagnostics: {
        elapsedMs: 20,
        quoteElapsedMs: 10,
        historyElapsedMs: 10,
        profileElapsedMs: 1,
        cache: { quote: 'miss', history: 'miss', profile: 'miss' },
        sources: { quote: 'unit_quote', history: 'unit_history', profile: 'unit_profile' },
        freshness: { quote: 'fresh', history: 'fresh', profile: 'fresh' },
        timeouts: { quote: false, history: false, profile: false },
        errors: { quote: null, history: null, profile: null },
        fallback: { quote: 'live', history: 'live', profile: 'live' },
        persistentCache: { quote: 'none', history: 'none', profile: 'none', mode: 'local_json' },
        routeLane: 'us_market_data',
        performance: { status: 'ok', slowThresholdMs: 3000 },
      },
      intelligence: {
        mode: 'free_rules',
        aiUsed: false,
        items: [],
        peerComparison: {
          title: 'Peer and market comparison',
          summary: 'Compare AAPL against QQQ and ^IXIC before reading it in isolation.',
          rows: [
            {
              symbol: 'QQQ',
              label: 'QQQ',
              role: 'Market benchmark',
              reason: 'US growth and technology benchmark.',
              currentSignal: 'AAPL is above MA20 with +4.75%; volume signal is neutral.',
              compareNext: 'Check whether AAPL confirms faster or weaker than QQQ on the next refresh.',
              source: 'no_ai_route_rules',
              referenceQuote: {
                currentPrice: 512.34,
                price: 512.34,
                changePercent: 0.87,
                freshness: 'fresh',
                source: 'unit_reference_quote',
                status: 'available',
                updateTime: '2026-07-08T09:31:00',
              },
            },
          ],
        },
        comparisonTargets: [
          {
            symbol: 'QQQ',
            label: 'QQQ',
            status: 'reference_only',
            reason: 'US growth and technology benchmark.',
            source: 'no_ai_route_rules',
            referenceQuote: {
              currentPrice: 512.34,
              price: 512.34,
              changePercent: 0.87,
              freshness: 'fresh',
              source: 'unit_reference_quote',
              status: 'available',
              updateTime: '2026-07-08T09:31:00',
            },
          },
        ],
      },
      aiUsed: false,
    });

    render(
      <MemoryRouter>
        <HomePage />
      </MemoryRouter>,
    );

    fireEvent.change(await screen.findByPlaceholderText('输入股票代码或名称，如 600519、贵州茅台、AAPL'), {
      target: { value: 'AAPL' },
    });
    fireEvent.click(screen.getByRole('button', { name: '查询' }));
    await openQuickAnalysisFromCurrentSnapshot();

    const peerComparison = await screen.findByTestId('basic-query-peer-comparison');
    expect(peerComparison).toHaveTextContent('参照价');
    expect(peerComparison).toHaveTextContent('512.34');
    expect(peerComparison).toHaveTextContent('+0.87%');
    expect(peerComparison).toHaveTextContent('新鲜');

    const watchPoints = screen.getByTestId('basic-query-watch-points');
    expect(watchPoints).toHaveTextContent('参照行情');
    expect(watchPoints).toHaveTextContent('QQQ');
    expect(watchPoints).toHaveTextContent('512.34');
    expect(watchPoints).not.toHaveTextContent('实时对比数值留给后续深度视图');
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
    vi.mocked(platformApi.runWatchlistRadar).mockResolvedValue({
      ...makeRadarResponse(15, [
        makeRadarItem({ stockCode: '600519', stockName: 'Kweichow Moutai', market: 'cn', routeLane: 'a_share_market_data', currentPrice: 1512.34, changePercent: 1.23 }),
        makeRadarItem({ stockCode: 'AAPL', stockName: 'Apple Inc.', market: 'us', routeLane: 'us_market_data', currentPrice: 211.88, changePercent: -0.42 }),
        makeRadarItem({ stockCode: 'HK00700', stockName: 'Tencent Holdings', market: 'hk', routeLane: 'hk_market_data', currentPrice: 390.2, changePercent: 0.8, degradationStatus: 'degraded', warningCodes: ['missing_history'], status: 'degraded', sourceStatus: 'source_unavailable' }),
        makeRadarItem({ stockCode: 'BTC-USD', stockName: 'Bitcoin', market: 'crypto', routeLane: 'crypto_market_data', currentPrice: 61888.12, changePercent: 2.5 }),
      ], 1),
      runId: 99,
      triggeredAlerts: [],
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
    expect(screen.getByTestId('platform-signed-in-panel')).toHaveClass('w-full');
    expect(platformStatus).toHaveTextContent('Signed in v15-user@example.com');
    expect(platformStatus).toHaveTextContent('Plan free');
    expect(platformStatus).toHaveTextContent('Weekly free 1/5 left');
    expect(platformStatus).not.toHaveTextContent('No-AI quick 9/10 left');
    expect(platformStatus).not.toHaveTextContent('BYOK ready sk-...live');
    expect(platformStatus).not.toHaveTextContent('Recommended BYOK');
    expect(platformStatus).not.toHaveTextContent('sk-live-secret');
    expect(screen.getByTestId('platform-status-plan')).toHaveClass('whitespace-nowrap');
    expect(screen.getByTestId('platform-status-weekly')).toHaveClass('whitespace-nowrap');
    fireEvent.click(screen.getByTestId('platform-personal-workspace-toggle'));
    expect(screen.getByTestId('platform-ai-cost-warning')).toHaveTextContent('Quick snapshot stays no-AI');
    expect(screen.getByTestId('platform-ai-cost-warning')).toHaveTextContent('Quick/Deep AI uses selected quota');
    expect(await screen.findByTestId('platform-watchlist-panel')).toHaveTextContent('Watchlist 4');
    expect(screen.getByTestId('platform-watchlist-panel')).toHaveTextContent('600519');
    expect(screen.getByTestId('platform-watchlist-panel')).toHaveTextContent('BTC-USD');

    fireEvent.click(screen.getByTestId('platform-watchlist-refresh'));
    expect(await screen.findByTestId('platform-watchlist-refresh-summary')).toHaveTextContent('No AI');
    expect(screen.getByTestId('platform-watchlist-refresh-summary')).toHaveTextContent('refreshed 4/4');
    expect(screen.getByTestId('platform-watchlist-refresh-summary')).toHaveTextContent('degraded 1');
    expect(screen.getByTestId('platform-watchlist-refresh-summary')).toHaveTextContent('HK market data');

    fireEvent.change(screen.getByPlaceholderText('Enter a stock code or name, e.g. 600519, Kweichow Moutai, AAPL'), {
      target: { value: 'HK00700' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Query' }));

    expect(await screen.findByTestId('basic-query-user-guardrails')).toHaveTextContent('Current quick snapshot');
    expect(screen.queryByTestId('platform-query-status')).not.toBeInTheDocument();
    expect(screen.getByTestId('basic-query-user-guardrails')).toHaveTextContent('No AI');
    expect(screen.getByTestId('basic-query-user-guardrails')).toHaveTextContent('HK market data');
    expect(screen.getByTestId('basic-query-user-guardrails')).toHaveTextContent('Historical reports stay separate');
    expect(screen.getByTestId('basic-query-user-guardrails')).toHaveTextContent('Cache local_json');
    expect(screen.getByTestId('basic-query-route')).toHaveTextContent('HK market data');
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

  it('keeps the signed-in account panel compact and localized in Chinese', async () => {
    window.localStorage.setItem(UI_LANGUAGE_STORAGE_KEY, 'zh');
    vi.mocked(platformApi.status).mockResolvedValue({ platformAuthEnabled: true });
    vi.mocked(platformApi.current).mockResolvedValue({
      user: {
        id: 16,
        email: 'zh-user@example.com',
        role: 'user',
        plan: 'free',
        status: 'active',
      },
      quota: {
        userId: 16,
        plan: 'free',
        weeklyLimit: 5,
        used: 0,
        remaining: 5,
        periodStart: '2026-07-01',
      },
    });
    vi.mocked(platformApi.account).mockResolvedValue({
      user: {
        id: 16,
        email: 'zh-user@example.com',
        role: 'user',
        plan: 'free',
        status: 'active',
      },
      quota: {
        userId: 16,
        plan: 'free',
        weeklyLimit: 5,
        used: 0,
        remaining: 5,
        periodStart: '2026-07-01',
      },
      quotaBuckets: [
        {
          userId: 16,
          plan: 'free',
          weeklyLimit: null,
          used: 0,
          remaining: null,
          periodStart: '2026-07-01',
          quotaBucket: 'basic_query',
        },
      ],
      apiKeys: [],
      recommendedQueryMode: 'platform',
    });
    vi.mocked(platformApi.watchlist).mockResolvedValue({ userId: 16, total: 0, items: [], aiUsed: false });

    render(
      <UiLanguageProvider>
        <MemoryRouter>
          <HomePage />
        </MemoryRouter>
      </UiLanguageProvider>,
    );

    const panel = await screen.findByTestId('platform-signed-in-panel');
    const status = screen.getByTestId('platform-query-status');
    expect(status).toHaveTextContent('已登录 zh-user@example.com');
    expect(status).toHaveTextContent('套餐 免费版');
    expect(status).toHaveTextContent('每周免费 剩余 5/5');
    expect(status).not.toHaveTextContent('免费快照');
    expect(status).not.toHaveTextContent('我的 API');
    expect(status).not.toHaveTextContent('推荐 平台 API');
    expect(status).toHaveTextContent('退出');
    expect(screen.getByRole('button', { name: '账户与模型' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '展开个人工作台' })).toBeInTheDocument();
    expect(screen.queryByTestId('platform-ai-cost-warning')).not.toBeInTheDocument();
    expect(screen.queryByTestId('platform-query-mode-panel')).not.toBeInTheDocument();
    expect(screen.queryByTestId('platform-watchlist-panel')).not.toBeInTheDocument();
    expect(panel.textContent?.match(/zh-user@example\.com/g)?.length ?? 0).toBe(1);
    expect(panel).not.toHaveTextContent('Signed in');
    expect(panel).not.toHaveTextContent('Plan free');
    expect(panel).not.toHaveTextContent('Weekly free');
    expect(panel).not.toHaveTextContent('No-AI quick');
  });

  it('renders the V100 saved review loop, saves an alert, and runs a no-AI query from a row', async () => {
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
    const radarRun = {
      ...makeRadarResponse(18, [
      makeRadarItem({ stockCode: '600519', stockName: 'Kweichow Moutai', market: 'cn', routeLane: 'a_share_market_data', currentPrice: 1512.34, changePercent: 1.23, ma20: 1490 }),
      makeRadarItem({ stockCode: 'AAPL', stockName: 'Apple Inc.', market: 'us', routeLane: 'us_market_data', currentPrice: 211.88, changePercent: -0.42, ma20: 205 }),
      makeRadarItem({
        stockCode: 'HK00700',
        stockName: 'Tencent Holdings',
        market: 'hk',
        routeLane: 'hk_market_data',
        currentPrice: 390.2,
        changePercent: 0.8,
        ma20: 376,
        degradationStatus: 'degraded',
        warningCodes: ['missing_history'],
        status: 'degraded',
        sourceStatus: 'source_unavailable',
        events: [{ stockCode: 'HK00700', type: 'data_quality', severity: 'warning', direction: 'degraded', warningCodes: ['missing_history'], aiUsed: false }],
        suggestedAlerts: [{ stockCode: 'HK00700', type: 'ma20_cross', threshold: null, referenceValue: 376, aiUsed: false }],
      }),
      makeRadarItem({
        stockCode: 'BTC-USD',
        stockName: 'Bitcoin',
        market: 'crypto',
        routeLane: 'crypto_market_data',
        currentPrice: 61888.12,
        changePercent: 2.5,
        events: [{ stockCode: 'BTC-USD', type: 'price_move', severity: 'warning', direction: 'up', value: 2.5, warningCodes: [], aiUsed: false }],
      }),
      ], 1),
      runId: 100,
      triggeredAlerts: [],
    };
    vi.mocked(platformApi.runWatchlistRadar).mockResolvedValue(radarRun);
    vi.mocked(platformApi.watchlistRadarHistory).mockResolvedValue({
      userId: 18,
      total: 1,
      aiUsed: false,
      items: [{
        id: 100,
        plan: 'free',
        processed: 4,
        eventCount: 2,
        riskCount: 1,
        sourceEventCount: 0,
        triggeredCount: 0,
        strongest: { stockCode: 'BTC-USD', changePercent: 2.5 },
        weakest: { stockCode: 'AAPL', changePercent: -0.42 },
        createdAt: '2026-07-11T09:30:00Z',
      }],
    });
    vi.mocked(platformApi.watchlistAlertRules).mockResolvedValue({
      userId: 18,
      plan: 'free',
      limit: 3,
      total: 0,
      remaining: 3,
      items: [],
      aiUsed: false,
    });
    vi.mocked(platformApi.saveWatchlistAlertRule).mockResolvedValue({
      userId: 18,
      plan: 'free',
      limit: 3,
      total: 1,
      remaining: 2,
      aiUsed: false,
      items: [{
        id: 31,
        stockCode: 'HK00700',
        ruleType: 'ma20_cross',
        threshold: null,
        referenceValue: 376,
        enabled: true,
      }],
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

    await screen.findByTestId('platform-signed-in-panel');
    fireEvent.click(screen.getByTestId('platform-personal-workspace-toggle'));
    await screen.findByTestId('platform-watchlist-panel');
    fireEvent.click(screen.getByTestId('platform-watchlist-refresh'));

    const radarPanel = await screen.findByTestId('watchlist-event-radar-v99');
    const cockpit = await screen.findByTestId('daily-research-cockpit-v103');
    expect(cockpit).toHaveTextContent('Daily research cockpit');
    expect(cockpit).toHaveTextContent('Wait for confirmation');
    expect(cockpit).toHaveTextContent('Platform API trial 5/5 remaining');
    expect(cockpit).toHaveTextContent('does not consume quota automatically');
    expect(radarPanel).toHaveTextContent('Today’s watchlist event radar');
    expect(radarPanel).toHaveTextContent(/Strongest\s*BTC-USD \+2\.5%/);
    expect(radarPanel).toHaveTextContent(/Weakest\s*AAPL -0\.42%/);
    expect(radarPanel).toHaveTextContent('Risk flags1');
    expect(radarPanel).toHaveTextContent('No AI used');
    expect(radarPanel).toHaveTextContent('Tencent Holdings');
    expect(radarPanel).toHaveTextContent('HK00700');
    expect(radarPanel).toHaveTextContent('390.2');
    expect(radarPanel).toHaveTextContent('+0.8%');
    expect(radarPanel).toHaveTextContent('Market data needs a freshness check');
    expect(radarPanel).toHaveTextContent('Apple Inc.');
    expect(radarPanel).toHaveTextContent('AAPL');

    const alertLoop = await screen.findByTestId('watchlist-alert-loop-v100');
    expect(alertLoop).toHaveTextContent('Continuous tracking and daily reviews');
    expect(alertLoop).toHaveTextContent('Recent reviews 1');
    fireEvent.click(screen.getByTestId('watchlist-alert-save-HK00700-ma20_cross'));
    await waitFor(() => {
      expect(platformApi.saveWatchlistAlertRule).toHaveBeenCalledWith({
        stockCode: 'HK00700',
        ruleType: 'ma20_cross',
        threshold: null,
        referenceValue: 376,
        enabled: true,
      });
    });
    expect(await screen.findByTestId('watchlist-alert-save-HK00700-ma20_cross')).toHaveTextContent('Saved');

    fireEvent.click(screen.getByTestId('watchlist-radar-symbol-HK00700'));

    await waitFor(() => {
      expect(stocksApi.snapshot).toHaveBeenCalledWith('HK00700');
    });
    expect(await screen.findByTestId('basic-query-route')).toHaveTextContent('HK market data');
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
    fireEvent.click(screen.getByRole('button', { name: 'Deep analysis' }));
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

    await screen.findByTestId('history-center-item-1');
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

    await openHistoryRecord(1);
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

    await openHistoryRecord(1);
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

    await openHistoryRecord(1);
    // Wait for the explicitly selected report to load
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
    fireEvent.click(screen.getByRole('button', { name: '深度分析' }));

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

  it('shows a clear login and API mode guard when a guest clicks deep analysis', async () => {
    vi.mocked(platformApi.status).mockResolvedValue({ platformAuthEnabled: true });
    vi.mocked(platformApi.current).mockResolvedValue(null);
    vi.mocked(historyApi.getList).mockResolvedValue({
      total: 0,
      page: 1,
      limit: 20,
      items: [],
    });
    vi.mocked(analysisApi.analyzeAsync).mockResolvedValue({
      taskId: 'task-guest-deep',
      status: 'pending',
    });

    render(
      <MemoryRouter>
        <HomePage />
      </MemoryRouter>,
    );

    const input = await screen.findByPlaceholderText('输入股票代码或名称，如 600519、贵州茅台、AAPL');
    fireEvent.change(input, { target: { value: '600519' } });
    fireEvent.click(screen.getByRole('button', { name: '深度分析' }));

    const guard = await screen.findByTestId('deep-analysis-guard');
    expect(guard).toHaveTextContent('深度分析需要先登录');
    expect(guard).toHaveTextContent('平台 API、我的 API 或本地模型');
    expect(analysisApi.analyzeAsync).not.toHaveBeenCalled();
  });

  it('shows the deep-analysis guard next to the current snapshot when a guest clicks the snapshot deep action', async () => {
    vi.mocked(platformApi.status).mockResolvedValue({ platformAuthEnabled: true });
    vi.mocked(platformApi.current).mockResolvedValue(null);
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
      quote: { currentPrice: 200, changePercent: 1.5, source: 'unit_quote', freshness: 'fresh' },
      indicators: { ma5: 198, ma20: 190 },
      aiUsed: false,
    } as unknown as BasicStockSnapshot);
    vi.mocked(analysisApi.analyzeAsync).mockResolvedValue({
      taskId: 'task-guest-snapshot-deep',
      status: 'pending',
    });

    render(
      <MemoryRouter>
        <HomePage />
      </MemoryRouter>,
    );

    fireEvent.change(await screen.findByPlaceholderText('输入股票代码或名称，如 600519、贵州茅台、AAPL'), {
      target: { value: 'AAPL' },
    });
    fireEvent.click(screen.getByRole('button', { name: '查询' }));
    await screen.findByTestId('basic-query-compact-overview');

    const deepButtons = screen.getAllByRole('button', { name: '深度分析' });
    fireEvent.click(deepButtons[deepButtons.length - 1]);

    const inlineGuard = await screen.findByTestId('basic-query-deep-inline-guard');
    expect(inlineGuard).toHaveTextContent('深度分析需要先登录');
    expect(inlineGuard).toHaveTextContent('登录后可选择平台 API、我的 API 或本地模型');
    expect(inlineGuard).toHaveTextContent('当前免费查询和快速分析仍可继续使用');
    expect(analysisApi.analyzeAsync).not.toHaveBeenCalled();
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

    await openHistoryRecord(2);
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

    await screen.findByTestId('history-center-item-1');

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
