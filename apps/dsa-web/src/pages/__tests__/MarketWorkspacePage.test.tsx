import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { UiLanguageProvider } from '../../contexts/UiLanguageContext';
import { UI_LANGUAGE_STORAGE_KEY } from '../../utils/uiLanguage';
import MarketWorkspacePage from '../MarketWorkspacePage';

const { getOverview, search, getSymbol, getSymbolEventArchive, getDailyBrief, addWatchlistItem, saveWatchlistAlertRule } = vi.hoisted(() => ({
  getOverview: vi.fn(),
  search: vi.fn(),
  getSymbol: vi.fn(),
  getSymbolEventArchive: vi.fn(),
  getDailyBrief: vi.fn(),
  addWatchlistItem: vi.fn(),
  saveWatchlistAlertRule: vi.fn(),
}));

vi.mock('../../api/marketWorkspace', () => ({
  marketWorkspaceApi: {
    getOverview: (market: string) => getOverview(market),
    search: (query: string, markets?: string[]) => search(query, markets),
    getSymbol: (symbol: string) => getSymbol(symbol),
    getSymbolEventArchive: (symbol: string, months: number) => getSymbolEventArchive(symbol, months),
    getDailyBrief: () => getDailyBrief(),
  },
}));

vi.mock('../../api/platform', () => ({
  platformApi: {
    addWatchlistItem: (symbol: string) => addWatchlistItem(symbol),
    saveWatchlistAlertRule: (payload: unknown) => saveWatchlistAlertRule(payload),
  },
}));

const overview = (market: 'cn' | 'hk' | 'us') => ({
  market,
  asOf: '2026-07-12T09:30:00Z',
  sessionState: 'open',
  indices: [],
  breadth: { advancers: 3, decliners: 1, unchanged: 1, unavailable: false },
  movers: [{
    symbol: market === 'us' ? 'AAPL' : market === 'hk' ? '0700.HK' : '600519.SH',
    name: market === 'us' ? 'Apple Inc.' : market === 'hk' ? '腾讯控股' : '贵州茅台',
    market,
    currency: market === 'us' ? 'USD' : market === 'hk' ? 'HKD' : 'CNY',
    currentPrice: 100,
    changePercent: 1.25,
    sector: 'Technology',
    sourceState: { source: `${market}_quote`, status: 'fresh' },
  }],
  heatmap: [],
  headlines: [],
  sources: [{ source: `${market}_market_snapshot`, status: 'fresh' }],
  warnings: [],
  cache: { hit: false, ageSeconds: 0, ttlSeconds: 60 },
  aiUsed: false,
  informationalOnly: true,
});

describe('MarketWorkspacePage', () => {
  beforeEach(() => {
    window.localStorage.clear();
    window.localStorage.setItem(UI_LANGUAGE_STORAGE_KEY, 'zh');
    getOverview.mockReset();
    search.mockReset();
    getSymbol.mockReset();
    getSymbolEventArchive.mockReset();
    getDailyBrief.mockReset();
    addWatchlistItem.mockReset();
    saveWatchlistAlertRule.mockReset();
    getOverview.mockImplementation(async (market: 'cn' | 'hk' | 'us') => overview(market));
    getDailyBrief.mockRejectedValue(new Error('login required'));
    addWatchlistItem.mockResolvedValue({ userId: 7, items: [], total: 1, aiUsed: false });
    saveWatchlistAlertRule.mockResolvedValue({ userId: 7, items: [], total: 1, aiUsed: false });
    search.mockResolvedValue({
      query: 'AAPL',
      markets: ['cn', 'hk', 'us'],
      items: [{
        symbol: 'AAPL',
        name: 'Apple Inc.',
        market: 'us',
        exchange: 'NASDAQ',
        currency: 'USD',
        matchType: 'exact_symbol',
        sourceState: { source: 'dsa_symbol_catalog', status: 'cached' },
      }],
      aiUsed: false,
    });
    getSymbol.mockResolvedValue({
      symbol: 'AAPL',
      name: 'Apple Inc.',
      market: 'us',
      currency: 'USD',
      asOf: '2026-07-12T09:30:00Z',
      quote: { currentPrice: 100, changePercent: 1.25, freshness: 'fresh' },
      history: [{ date: '2026-07-11', close: 99, volume: 1000 }],
      indicators: { ma5: 98, ma20: 95 },
      profile: { sector: 'Technology', industry: 'Consumer Electronics' },
      headlines: [],
      sources: [{ source: 'us_quote', status: 'fresh' }],
      warnings: [],
      personalization: null,
      aiUsed: false,
      informationalOnly: true,
    });
    getSymbolEventArchive.mockResolvedValue({
      symbol: 'AAPL',
      name: 'Apple Inc.',
      market: 'us',
      months: 12,
      asOf: '2026-07-30T00:00:00Z',
      items: [],
      comparisonSummaries: [],
      availableEventTypes: [],
      chart: {
        status: 'unavailable',
        symbol: 'AAPL',
        name: 'Apple Inc.',
        market: 'us',
        benchmarkSymbol: '^GSPC',
        benchmarkName: 'S&P 500',
        periodDays: 366,
        points: [],
        symbolSourceState: {
          source: 'yahoo_chart_public',
          status: 'unavailable',
        },
        benchmarkSourceState: {
          source: 'yahoo_chart_public',
          status: 'unavailable',
        },
        warningCodes: ['symbol_history_unavailable'],
      },
      warnings: [],
      aiUsed: false,
      informationalOnly: true,
      causalityDisclaimer: true,
    });
  });

  it('shows market state, time, breadth and sources before movers and switches markets', async () => {
    render(
      <MemoryRouter>
        <UiLanguageProvider><MarketWorkspacePage /></UiLanguageProvider>
      </MemoryRouter>,
    );

    expect(await screen.findByRole('heading', { name: '市场工作台' })).toBeInTheDocument();
    expect(screen.getByText('市场状态')).toBeInTheDocument();
    expect(screen.getByText('数据时间')).toBeInTheDocument();
    expect(screen.getByText('涨跌分布')).toBeInTheDocument();
    expect(screen.getByText('数据来源')).toBeInTheDocument();
    expect(screen.getByText('贵州茅台')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: '美股' }));

    await waitFor(() => expect(getOverview).toHaveBeenLastCalledWith('us'));
    expect(await screen.findByText('Apple Inc.')).toBeInTheDocument();
    expect(screen.queryByText('贵州茅台')).not.toBeInTheDocument();
  });

  it('opens a no-AI symbol workspace from global search', async () => {
    render(
      <MemoryRouter>
        <UiLanguageProvider><MarketWorkspacePage /></UiLanguageProvider>
      </MemoryRouter>,
    );

    const input = await screen.findByRole('searchbox', { name: '搜索股票代码或公司名称' });
    fireEvent.change(input, { target: { value: 'AAPL' } });
    fireEvent.click(screen.getByRole('button', { name: '搜索' }));
    fireEvent.click(await screen.findByRole('button', { name: /AAPL.*Apple Inc\./ }));

    expect(await screen.findByRole('heading', { name: 'Apple Inc.' })).toBeInTheDocument();
    expect(screen.getByText('未使用 AI')).toBeInTheDocument();
    expect(screen.getByText('MA20')).toBeInTheDocument();
    expect(screen.getByText('95')).toBeInTheDocument();
    expect(getSymbol).toHaveBeenCalledWith('AAPL');
    expect(getSymbolEventArchive).toHaveBeenCalledWith('AAPL', 12);
  });

  it('renders the market workspace in English mode', async () => {
    window.localStorage.setItem(UI_LANGUAGE_STORAGE_KEY, 'en');
    render(
      <MemoryRouter>
        <UiLanguageProvider><MarketWorkspacePage /></UiLanguageProvider>
      </MemoryRouter>,
    );

    expect(await screen.findByRole('heading', { name: 'Market workspace' })).toBeInTheDocument();
    expect(screen.getByText('Market status')).toBeInTheDocument();
    expect(screen.getByText('Data time')).toBeInTheDocument();
    expect(screen.getByText(/Information and data only\. No investment advice\./)).toBeInTheDocument();
  });

  it('lets a signed-in user save a watchlist item and an objective condition alert', async () => {
    render(
      <MemoryRouter>
        <UiLanguageProvider><MarketWorkspacePage /></UiLanguageProvider>
      </MemoryRouter>,
    );
    const input = await screen.findByRole('searchbox', { name: '搜索股票代码或公司名称' });
    fireEvent.change(input, { target: { value: 'AAPL' } });
    fireEvent.click(screen.getByRole('button', { name: '搜索' }));
    fireEvent.click(await screen.findByRole('button', { name: /AAPL.*Apple Inc\./ }));
    await screen.findByRole('heading', { name: 'Apple Inc.' });

    fireEvent.click(screen.getByRole('button', { name: '加入自选' }));
    fireEvent.change(screen.getByLabelText('到价阈值'), { target: { value: '105' } });
    fireEvent.click(screen.getByRole('button', { name: '保存到价提醒' }));

    await waitFor(() => expect(addWatchlistItem).toHaveBeenCalledWith('AAPL'));
    expect(saveWatchlistAlertRule).toHaveBeenCalledWith({
      stockCode: 'AAPL', ruleType: 'price_above', threshold: 105, enabled: true,
    });
  });

  it('shows an invalid-rule error instead of a login prompt', async () => {
    saveWatchlistAlertRule.mockRejectedValue({ parsedError: { status: 400, message: 'invalid_alert_rule' } });
    render(<MemoryRouter initialEntries={['/market?symbol=AAPL']}><UiLanguageProvider><MarketWorkspacePage /></UiLanguageProvider></MemoryRouter>);

    await screen.findByRole('heading', { name: 'Apple Inc.' });
    fireEvent.change(screen.getByLabelText('到价阈值'), { target: { value: '105' } });
    fireEvent.click(screen.getByRole('button', { name: '保存到价提醒' }));

    expect(await screen.findByText('提醒保存失败，请检查价格后重试。')).toBeInTheDocument();
    expect(screen.queryByText('登录后可保存到价提醒。')).not.toBeInTheDocument();
  });

  it('opens a safe symbol query once and ignores unsafe values', async () => {
    const { unmount } = render(<MemoryRouter initialEntries={['/market?symbol=AAPL']}><UiLanguageProvider><MarketWorkspacePage /></UiLanguageProvider></MemoryRouter>);
    await screen.findByRole('heading', { name: 'Apple Inc.' });
    expect(getSymbol).toHaveBeenCalledTimes(1);
    unmount();

    getSymbol.mockClear();
    render(<MemoryRouter initialEntries={['/market?symbol=%3Cscript%3E']}><UiLanguageProvider><MarketWorkspacePage /></UiLanguageProvider></MemoryRouter>);
    await screen.findByRole('heading', { name: '市场工作台' });
    expect(getSymbol).not.toHaveBeenCalled();
  });

  it('synchronizes the selected market for a direct symbol link and localizes source status', async () => {
    getSymbol.mockResolvedValueOnce({
      symbol: 'AAPL',
      name: 'Apple Inc.',
      market: 'us',
      currency: 'USD',
      asOf: '2026-07-12T09:30:00Z',
      quote: { currentPrice: 315.32000732421875, changePercent: 2.1676, freshness: 'fresh' },
      history: [],
      indicators: {},
      profile: {},
      headlines: [],
      sources: [{ source: 'yahoo_chart_reference', status: 'cached' }],
      warnings: [],
      personalization: null,
      aiUsed: false,
      informationalOnly: true,
    });

    render(<MemoryRouter initialEntries={['/market?symbol=AAPL']}><UiLanguageProvider><MarketWorkspacePage /></UiLanguageProvider></MemoryRouter>);

    expect(await screen.findByRole('heading', { name: 'Apple Inc.' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '美股' })).toHaveAttribute('aria-pressed', 'true');
    expect(screen.getByText('315.32')).toBeInTheDocument();
    expect(screen.getByText(/Yahoo 图表 · 缓存/)).toBeInTheDocument();
    expect(screen.queryByText('cached')).not.toBeInTheDocument();
  });

  it('keeps the direct-link market overview when an older request finishes later', async () => {
    window.localStorage.setItem(UI_LANGUAGE_STORAGE_KEY, 'en');
    let resolveCnOverview: ((value: ReturnType<typeof overview>) => void) | undefined;
    getOverview.mockImplementation((nextMarket: 'cn' | 'hk' | 'us') => {
      if (nextMarket === 'cn') {
        return new Promise((resolve) => { resolveCnOverview = resolve; });
      }
      return Promise.resolve({
        ...overview(nextMarket),
        movers: [{
          ...overview(nextMarket).movers[0],
          name: nextMarket === 'hk' ? 'Tencent Holdings' : 'Apple Inc.',
        }],
      });
    });
    getSymbol.mockResolvedValueOnce({
      symbol: '0700.HK',
      name: 'Tencent Holdings',
      market: 'hk',
      currency: 'HKD',
      asOf: '2026-07-12T09:30:00Z',
      quote: { currentPrice: 457.6, changePercent: 1.5, freshness: 'fresh' },
      history: [],
      indicators: {},
      profile: {},
      headlines: [],
      sources: [{ source: 'yahoo_chart_reference', status: 'fresh' }],
      warnings: [],
      personalization: null,
      aiUsed: false,
      informationalOnly: true,
    });

    render(<MemoryRouter initialEntries={['/market?symbol=0700.HK']}><UiLanguageProvider><MarketWorkspacePage /></UiLanguageProvider></MemoryRouter>);

    expect(await screen.findByRole('heading', { name: 'Tencent Holdings' })).toBeInTheDocument();
    await waitFor(() => expect(getOverview).toHaveBeenCalledWith('hk'));
    expect(screen.getByRole('button', { name: 'Hong Kong' })).toHaveAttribute('aria-pressed', 'true');
    await waitFor(() => expect(screen.getAllByText('Tencent Holdings')).toHaveLength(2));

    resolveCnOverview?.({
      ...overview('cn'),
      movers: [{ ...overview('cn').movers[0], name: 'Late A-share result' }],
    });

    await waitFor(() => expect(screen.queryByText('Late A-share result')).not.toBeInTheDocument());
    expect(screen.getAllByText('Tencent Holdings')).toHaveLength(2);
  });

  it('localizes degraded source warning codes', async () => {
    getOverview.mockResolvedValueOnce({
      ...overview('cn'),
      warnings: ['market_news_unavailable', 'market_quotes_unavailable', 'market_symbol_timeout:600519.SH'],
    });

    render(<MemoryRouter><UiLanguageProvider><MarketWorkspacePage /></UiLanguageProvider></MemoryRouter>);

    expect(await screen.findByText(/\u6388\u6743\u8d44\u8baf\u6e90\u6682\u4e0d\u53ef\u7528/)).toBeInTheDocument();
    expect(screen.getByText(/\u884c\u60c5\u6570\u636e\u6682\u4e0d\u53ef\u7528/)).toBeInTheDocument();
    expect(screen.getByText(/600519\.SH \u884c\u60c5\u8bf7\u6c42\u8d85\u65f6/)).toBeInTheDocument();
    expect(screen.queryByText(/market_news_unavailable/)).not.toBeInTheDocument();
  });
});
