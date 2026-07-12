import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { UiLanguageProvider } from '../../contexts/UiLanguageContext';
import { UI_LANGUAGE_STORAGE_KEY } from '../../utils/uiLanguage';
import MarketWorkspacePage from '../MarketWorkspacePage';

const { getOverview, search, getSymbol, getDailyBrief, addWatchlistItem, saveWatchlistAlertRule } = vi.hoisted(() => ({
  getOverview: vi.fn(),
  search: vi.fn(),
  getSymbol: vi.fn(),
  getDailyBrief: vi.fn(),
  addWatchlistItem: vi.fn(),
  saveWatchlistAlertRule: vi.fn(),
}));

vi.mock('../../api/marketWorkspace', () => ({
  marketWorkspaceApi: {
    getOverview: (market: string) => getOverview(market),
    search: (query: string, markets?: string[]) => search(query, markets),
    getSymbol: (symbol: string) => getSymbol(symbol),
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
    fireEvent.change(screen.getByLabelText('条件阈值'), { target: { value: '105' } });
    fireEvent.click(screen.getByRole('button', { name: '保存条件提醒' }));

    await waitFor(() => expect(addWatchlistItem).toHaveBeenCalledWith('AAPL'));
    expect(saveWatchlistAlertRule).toHaveBeenCalledWith({
      stockCode: 'AAPL', ruleType: 'price_above', threshold: 105, enabled: true,
    });
  });
});
