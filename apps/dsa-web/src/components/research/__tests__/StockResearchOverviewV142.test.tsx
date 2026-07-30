import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { stocksApi, type BasicStockSnapshot } from '../../../api/stocks';
import { StockResearchOverviewV142 } from '../StockResearchOverviewV142';

vi.mock('../../../api/stocks', () => ({
  stocksApi: { researchOverview: vi.fn() },
}));

const snapshot: BasicStockSnapshot = {
  stockCode: 'AAPL',
  stockName: 'Apple Inc.',
  market: 'us',
  quote: {
    currentPrice: 208,
    change: 3,
    changePercent: 1.46,
    open: 205,
    high: 210,
    low: 204,
    prevClose: 205,
    volume: 50_000_000,
    amount: 10_400_000_000,
    updateTime: '2026-07-30T12:00:00',
    source: 'us_realtime',
    freshness: 'fresh',
  },
  profile: {
    companyName: 'Apple Inc.',
    sector: 'Technology',
    industry: 'Consumer Electronics',
    currency: 'USD',
    marketCap: 3_100_000_000_000,
    peRatio: 31.2,
    pbRatio: 42.1,
    revenue: 410_000_000_000,
    netProfit: 102_000_000_000,
    source: 'yfinance_profile',
    freshness: 'fresh',
  },
  indicators: {
    ma5: 204,
    ma20: 198,
    priceChange5D: 2.4,
    priceChange20D: 6.8,
    volumeChangeVsMa5: 12,
  },
  trend: {
    window: 5,
    source: 'yahoo_chart_history',
    points: [
      { date: '2026-07-24', close: 197, volume: 42_000_000 },
      { date: '2026-07-25', close: 199, volume: 44_000_000 },
      { date: '2026-07-28', close: 202, volume: 46_000_000 },
      { date: '2026-07-29', close: 205, volume: 48_000_000 },
      { date: '2026-07-30', close: 208, volume: 50_000_000 },
    ],
    minClose: 197,
    maxClose: 208,
    changePercent: 5.58,
  },
  intelligence: {
    mode: 'no_ai_low_cost',
    aiUsed: false,
    boundary: 'Information and data only; not investment advice.',
    peerComparison: {
      title: 'Peer comparison',
      summary: 'Compare with technology references.',
      rows: [
        {
          symbol: 'QQQ',
          label: 'Nasdaq 100 ETF',
          role: 'Broad market',
          reason: 'Technology benchmark',
          currentSignal: 'Reference quote available.',
          compareNext: 'Compare relative movement.',
          source: 'no_ai_route_rules',
          referenceQuote: {
            stockName: 'Invesco QQQ',
            currentPrice: 610,
            changePercent: 0.8,
            freshness: 'fresh',
            source: 'yahoo_chart',
            status: 'available',
          },
        },
        {
          symbol: '^IXIC',
          label: 'Nasdaq Composite',
          role: 'Index lens',
          reason: 'Index reference',
          currentSignal: 'Reference quote available.',
          compareNext: 'Compare relative movement.',
          source: 'yahoo_chart_reference',
          referenceQuote: {
            stockName: 'Nasdaq Composite',
            currentPrice: 26_000,
            changePercent: -0.4,
            freshness: 'cached',
            source: 'yahoo_chart_reference',
            status: 'available',
          },
        },
      ],
    },
    newsCenter: {
      title: 'News center',
      summary: 'Public information lanes.',
      items: [
        {
          category: 'news',
          title: 'Quarterly results published',
          summary: 'Revenue and earnings facts are available.',
          status: 'available',
          source: 'company_release',
          action: 'Open source.',
          updatedAt: '2026-07-29T18:00:00',
          url: 'https://example.com/aapl-results',
        },
        {
          category: 'financials',
          title: 'Financial snapshot lane',
          summary: 'Market cap 3.1T; PE 31.2; PB 42.1; dividend yield 0.4%; revenue 410B; net profit 102B.',
          status: 'available',
          source: 'yfinance_profile',
          action: 'Review public financial facts.',
          updatedAt: '2026-07-29T18:00:00',
        },
      ],
      source: 'public_news',
      aiUsed: false,
      publicSearchUsed: false,
      premiumUnlock: 'API mode can improve freshness.',
      boundary: 'Information only.',
    },
    items: [],
    comparisonTargets: [],
  },
  route: {
    normalizedCode: 'AAPL',
    market: 'us',
    channel: 'us_equity',
    dataSourceLane: 'us_market_data',
    quoteSources: ['yahoo_chart'],
    historySources: ['yahoo_chart_history'],
    profileSources: ['yfinance_profile'],
    aiRequired: false,
  },
  warnings: [],
  degradation: { status: 'ok', severity: 'info', message: 'Market data ready' },
  canonicalData: {
    contractVersion: 'v1',
    symbol: 'AAPL',
    market: 'us',
    policy: {},
    selectedSources: {
      quote: { source: 'yahoo_chart', freshness: 'fresh', observedAt: '2026-07-30T12:00:00' },
    },
    fieldProvenance: { current_price: 'yahoo_chart' },
    conflicts: [],
    deduplication: { inputCount: 1, outputCount: 1, removedCount: 0 },
    informationalOnly: true,
    aiUsed: false,
  },
  aiUsed: false,
};

const researchPayload = {
  stockCode: 'AAPL',
  publicSymbol: 'AAPL',
  status: 'available' as const,
  source: 'yfinance_public_financials',
  sourceUrl: 'https://finance.yahoo.com/quote/AAPL/financials/',
  updatedAt: '2026-07-30T12:00:00',
  cacheStatus: 'miss',
  financialYears: [
    { fiscalYear: 2021, periodEnd: '2021-09-30', revenue: 365_000_000_000, netIncome: 94_000_000_000, dilutedEps: 5.61, observedPe: 25.3 },
    { fiscalYear: 2022, periodEnd: '2022-09-30', revenue: 394_000_000_000, revenueGrowth: 7.95, netIncome: 99_000_000_000, netIncomeGrowth: 5.32, dilutedEps: 6.11, observedPe: 22.8 },
    { fiscalYear: 2023, periodEnd: '2023-09-30', revenue: 383_000_000_000, revenueGrowth: -2.79, netIncome: 97_000_000_000, netIncomeGrowth: -2.02, dilutedEps: 6.13, observedPe: 27.9 },
    { fiscalYear: 2024, periodEnd: '2024-09-30', revenue: 391_000_000_000, revenueGrowth: 2.09, netIncome: 93_000_000_000, netIncomeGrowth: -4.12, dilutedEps: 6.08, observedPe: 38.2 },
    { fiscalYear: 2025, periodEnd: '2025-09-30', revenue: 410_000_000_000, revenueGrowth: 4.86, netIncome: 102_000_000_000, netIncomeGrowth: 9.68, dilutedEps: 6.62, observedPe: 34.1 },
  ],
  valuationPosition: {
    metric: 'observed_pe',
    method: 'fiscal_year_end_price_divided_by_diluted_eps',
    currentValue: 34.1,
    minimum: 22.8,
    median: 27.9,
    maximum: 38.2,
    percentile: 80,
    observationCount: 5,
    position: 'upper_range' as const,
  },
  warnings: [],
  aiUsed: false,
  publicSearchUsed: false,
  boundaryZh: '仅提供资讯和数据，不构成投资建议或交易指令。',
  boundaryEn: 'Information and data only; not investment advice or a trading instruction.',
};

describe('StockResearchOverviewV142', () => {
  beforeEach(() => {
    vi.mocked(stocksApi.researchOverview).mockReset();
    vi.mocked(stocksApi.researchOverview).mockResolvedValue(researchPayload);
  });

  it('renders a compact Chinese research overview and lazy-loads financial facts', async () => {
    render(
      <StockResearchOverviewV142
        snapshot={snapshot}
        language="zh"
        detailsExpanded={false}
        onToggleDetails={vi.fn()}
      />,
    );

    const panel = screen.getByTestId('basic-query-research-overview-v142');
    expect(panel).toHaveTextContent('个股研究总览');
    expect(screen.getByRole('tab', { name: '研究总览' })).toHaveAttribute('aria-selected', 'true');
    expect(screen.getByRole('tab', { name: '财务趋势' })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: '同业对比' })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: '资讯事件' })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: 'K线样本' })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: '来源与边界' })).toBeInTheDocument();
    expect(stocksApi.researchOverview).not.toHaveBeenCalled();
    expect(panel).not.toHaveTextContent('买入');
    expect(panel).not.toHaveTextContent('目标价');
    expect(panel).not.toHaveTextContent('us_realtime');
    expect(panel).not.toHaveTextContent('Market data ready');
    expect(panel).toHaveTextContent('美股公开行情');
    expect(panel).toHaveTextContent('当前市场数据已就绪');

    fireEvent.click(screen.getByRole('tab', { name: '财务趋势' }));

    await waitFor(() => expect(stocksApi.researchOverview).toHaveBeenCalledWith('AAPL'));
    expect(await screen.findByText('五年财务趋势')).toBeInTheDocument();
    expect(screen.getByText('历史市盈率位置')).toBeInTheDocument();
    expect(screen.getByText('2025')).toBeInTheDocument();
    expect(screen.getByText('80%')).toBeInTheDocument();
    expect(panel).toHaveTextContent('财年末价格 / 当年摊薄每股收益');
  });

  it('renders missing financial values as unavailable instead of zero', async () => {
    vi.mocked(stocksApi.researchOverview).mockResolvedValueOnce({
      ...researchPayload,
      financialYears: [
        {
          fiscalYear: 2021,
          periodEnd: '2021-09-30',
          revenue: null,
          revenueGrowth: null,
          netIncome: null,
          netIncomeGrowth: null,
          dilutedEps: null,
          operatingCashFlow: null,
          observedPe: null,
        },
      ],
      valuationPosition: null,
      warnings: ['公开源仅返回 1 个财年，五年趋势并不完整。'],
    });
    render(
      <StockResearchOverviewV142
        snapshot={snapshot}
        language="zh"
        detailsExpanded={false}
        onToggleDetails={vi.fn()}
      />,
    );

    fireEvent.click(screen.getByRole('tab', { name: '财务趋势' }));

    const row = await screen.findByRole('row', { name: /2021/ });
    const cells = within(row).getAllByRole('cell');
    expect(cells[0]).toHaveTextContent('2021');
    cells.slice(1).forEach((cell) => expect(cell).toHaveTextContent(/^-$|^—$/));
    expect(screen.getByText('公开源仅返回 1 个财年，五年趋势并不完整。')).toBeInTheDocument();
  });

  it('shows actual peer quotes, event provenance, K-line samples, and source conflicts', () => {
    render(
      <StockResearchOverviewV142
        snapshot={snapshot}
        language="zh"
        detailsExpanded={false}
        onToggleDetails={vi.fn()}
      />,
    );

    fireEvent.click(screen.getByRole('tab', { name: '同业对比' }));
    const peers = screen.getByTestId('research-overview-peer-table-v142');
    expect(within(peers).getByText('QQQ')).toBeInTheDocument();
    expect(peers).toHaveTextContent('610');
    expect(peers).toHaveTextContent('+0.80%');
    expect(peers).toHaveTextContent('大盘');
    expect(peers).toHaveTextContent('指数参照');
    expect(peers).toHaveTextContent('Yahoo 参照行情');
    expect(peers).not.toHaveTextContent('Broad market');
    expect(peers).not.toHaveTextContent('Index lens');
    expect(peers).not.toHaveTextContent('yahoo_chart_reference');

    fireEvent.click(screen.getByRole('tab', { name: '资讯事件' }));
    expect(screen.getByText('Quarterly results published')).toBeInTheDocument();
    expect(screen.getByText('公司公告')).toBeInTheDocument();
    expect(screen.queryByText('company_release')).not.toBeInTheDocument();
    expect(screen.getByText('财务快照通道')).toBeInTheDocument();
    expect(screen.getByText(/总市值 3.1T/)).toBeInTheDocument();
    expect(screen.queryByText('Financial snapshot lane')).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole('tab', { name: 'K线样本' }));
    expect(screen.getByTestId('research-overview-kline-v142')).toHaveTextContent('5 个收盘样本');
    expect(screen.getByTestId('research-overview-kline-v142')).toHaveTextContent('+5.58%');

    fireEvent.click(screen.getByRole('tab', { name: '来源与边界' }));
    expect(screen.getByTestId('research-overview-sources-v142')).toHaveTextContent('Yahoo');
    expect(screen.getByTestId('research-overview-sources-v142')).toHaveTextContent('未发现来源冲突');
    expect(screen.getByTestId('research-overview-sources-v142')).toHaveTextContent('不构成投资建议');
  });

  it('uses English copy and reports financial source failures without raw errors', async () => {
    vi.mocked(stocksApi.researchOverview).mockRejectedValueOnce(new Error('secret provider stack'));
    render(
      <StockResearchOverviewV142
        snapshot={snapshot}
        language="en"
        detailsExpanded={false}
        onToggleDetails={vi.fn()}
      />,
    );

    expect(screen.getByText('Stock research overview')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('tab', { name: 'Financial trends' }));
    expect(await screen.findByText('Public financial data is temporarily unavailable.')).toBeInTheDocument();
    expect(screen.queryByText(/secret provider stack/i)).not.toBeInTheDocument();
  });

  it('lets the parent expand the preserved detailed modules', () => {
    const onToggleDetails = vi.fn();
    const { rerender } = render(
      <StockResearchOverviewV142
        snapshot={snapshot}
        language="zh"
        detailsExpanded={false}
        onToggleDetails={onToggleDetails}
      />,
    );

    fireEvent.click(screen.getByRole('button', { name: '展开全部详细模块' }));
    expect(onToggleDetails).toHaveBeenCalledTimes(1);

    rerender(
      <StockResearchOverviewV142
        snapshot={snapshot}
        language="zh"
        detailsExpanded
        onToggleDetails={onToggleDetails}
      />,
    );
    expect(screen.getByRole('button', { name: '收起详细模块' })).toBeInTheDocument();
  });
});
