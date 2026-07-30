import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import {
  marketWorkspaceApi,
  type PublicSymbolEventArchiveResponse,
} from '../../api/marketWorkspace';
import SymbolEventArchiveV139 from './SymbolEventArchiveV139';

vi.mock('../../api/marketWorkspace', async (importOriginal) => {
  const original = await importOriginal<typeof import('../../api/marketWorkspace')>();
  return {
    ...original,
    marketWorkspaceApi: {
      ...original.marketWorkspaceApi,
      getSymbolEventArchive: vi.fn(),
    },
  };
});

const response: PublicSymbolEventArchiveResponse = {
  symbol: 'AAPL',
  name: 'Apple Inc.',
  market: 'us',
  months: 12,
  asOf: '2026-07-30T00:00:00Z',
  chart: {
    status: 'available',
    historySymbol: 'AAPL',
    benchmarkSymbol: '^GSPC',
    benchmarkName: 'S&P 500',
    points: [{
      date: '2026-07-20',
      symbolClose: 100,
      benchmarkClose: 200,
      symbolChangePercent: 0,
      benchmarkChangePercent: 0,
      relativeChangePercent: 0,
      volume: 1_000,
    }, {
      date: '2026-07-21',
      symbolClose: 102,
      benchmarkClose: 202,
      symbolChangePercent: 2,
      benchmarkChangePercent: 1,
      relativeChangePercent: 1,
      volume: 1_200,
    }],
    sourceState: { source: 'yahoo_chart_public', status: 'fresh' },
    benchmarkSourceState: { source: 'yahoo_chart_public', status: 'fresh' },
    warningCodes: [],
  },
  items: [{
    eventId: 'earnings-aapl',
    eventType: 'earnings',
    market: 'us',
    title: 'Apple earnings release',
    summary: 'Public calendar date supplied by Yahoo Finance.',
    publisher: 'Yahoo Finance',
    sourceUrl: 'https://finance.yahoo.com/quote/AAPL',
    eventSourceState: { source: 'yfinance_public_calendar', status: 'fresh' },
    symbol: 'AAPL',
    name: 'Apple Inc.',
    subjectType: 'security',
    eventTime: '2026-07-20T00:00:00Z',
    eventTimeKind: 'observed',
    classificationSource: 'provider_event_history',
    scheduleType: 'earnings_release',
    historySymbol: 'AAPL',
    baselineDate: '2026-07-20',
    benchmarkSymbol: '^GSPC',
    benchmarkName: 'S&P 500',
    status: 'partial',
    windows: [{
      tradingDays: 1,
      status: 'available',
      observedDate: '2026-07-21',
      symbolReturnPercent: 2,
      benchmarkReturnPercent: 1,
      relativeReturnPercent: 1,
      volumeRatio: 1.5,
    }, {
      tradingDays: 3,
      status: 'available',
      observedDate: '2026-07-23',
      symbolReturnPercent: 4,
      benchmarkReturnPercent: 1,
      relativeReturnPercent: 3,
      volumeRatio: 1.2,
    }],
    sourceState: { source: 'yahoo_chart_public', status: 'fresh' },
    benchmarkSourceState: { source: 'yahoo_chart_public', status: 'fresh' },
    warningCodes: [],
  }, {
    eventId: 'dividend-aapl',
    eventType: 'dividend',
    market: 'us',
    title: 'Apple ex-dividend',
    summary: 'Historical ex-dividend event.',
    publisher: 'Yahoo Finance',
    sourceUrl: 'https://finance.yahoo.com/quote/AAPL',
    eventSourceState: { source: 'yahoo_chart_corporate_actions', status: 'cached' },
    symbol: 'AAPL',
    name: 'Apple Inc.',
    subjectType: 'security',
    eventTime: '2026-05-10T00:00:00Z',
    eventTimeKind: 'observed',
    classificationSource: 'provider_event_history',
    scheduleType: 'ex_dividend',
    historySymbol: 'AAPL',
    baselineDate: null,
    benchmarkSymbol: '^GSPC',
    benchmarkName: 'S&P 500',
    status: 'unavailable',
    windows: [],
    sourceState: { source: 'yahoo_chart_public', status: 'unavailable' },
    benchmarkSourceState: null,
    warningCodes: ['event_price_observation_unavailable'],
  }],
  comparisonSummaries: [{
    eventType: 'earnings',
    eventCount: 1,
    observedEventCount: 1,
    windows: [{
      tradingDays: 1,
      sampleSize: 1,
      benchmarkSampleSize: 1,
      relativeSampleSize: 1,
      positiveCount: 1,
      negativeCount: 0,
      flatCount: 0,
      symbolMedianReturnPercent: 2,
      symbolMinReturnPercent: 2,
      symbolMaxReturnPercent: 2,
      benchmarkMedianReturnPercent: 1,
      relativeMedianReturnPercent: 1,
      completenessPercent: 100,
    }],
  }, {
    eventType: 'dividend',
    eventCount: 1,
    observedEventCount: 0,
    windows: [],
  }],
  availableEventTypes: ['earnings', 'dividend'],
  warnings: [],
  aiUsed: false,
  informationalOnly: true,
  causalityDisclaimer: true,
};

describe('SymbolEventArchiveV139', () => {
  beforeEach(() => {
    vi.mocked(marketWorkspaceApi.getSymbolEventArchive).mockReset();
    vi.mocked(marketWorkspaceApi.getSymbolEventArchive).mockResolvedValue(response);
  });

  it('renders a Chinese traceable archive and switches observation windows', async () => {
    render(<SymbolEventArchiveV139 language="zh" symbol="AAPL" />);

    const panel = await screen.findByTestId('symbol-event-archive-v139');
    expect(within(panel).getByText('个股事件档案')).toBeInTheDocument();
    expect(within(panel).getByText('Apple Inc.（AAPL）财报披露')).toBeInTheDocument();
    expect(within(panel).getAllByText('+2.00%').length).toBeGreaterThanOrEqual(1);
    expect(within(panel).getAllByText('+1.00%').length).toBeGreaterThanOrEqual(2);
    expect(within(panel).getAllByRole('link', { name: '查看来源' })[0]).toHaveAttribute(
      'href',
      'https://finance.yahoo.com/quote/AAPL',
    );
    expect(within(panel).getByText('同期变化不代表事件导致价格变化。本功能只提供资讯和客观数据，不构成投资建议。')).toBeInTheDocument();
    expect(within(panel).queryByText(/买入|卖出|目标价|收益预测/)).not.toBeInTheDocument();

    fireEvent.click(within(panel).getByRole('button', { name: '3个交易日' }));
    expect(within(panel).getAllByText('+4.00%').length).toBeGreaterThanOrEqual(1);
    expect(within(panel).getAllByText('+3.00%').length).toBeGreaterThanOrEqual(1);

    fireEvent.click(within(panel).getByRole('button', { name: '分红除息' }));
    expect(within(panel).getByText('Apple Inc.（AAPL）分红除息')).toBeInTheDocument();
    expect(within(panel).queryByText('Apple Inc.（AAPL）财报披露')).not.toBeInTheDocument();
  });

  it('links a V141 historical sample selection back to the V140 timeline', async () => {
    const olderEarnings = {
      ...response.items[0],
      eventId: 'earnings-aapl-older',
      eventTime: '2026-06-20T00:00:00Z',
      baselineDate: '2026-06-20',
      windows: [{
        ...response.items[0].windows[0],
        observedDate: '2026-06-21',
        symbolReturnPercent: 7,
        benchmarkReturnPercent: 2,
        relativeReturnPercent: 5,
      }],
    };
    vi.mocked(marketWorkspaceApi.getSymbolEventArchive).mockResolvedValueOnce({
      ...response,
      items: [response.items[0], olderEarnings, response.items[1]],
      comparisonSummaries: [{
        ...response.comparisonSummaries[0],
        eventCount: 2,
        observedEventCount: 2,
        windows: [{
          ...response.comparisonSummaries[0].windows[0],
          sampleSize: 2,
          benchmarkSampleSize: 2,
          relativeSampleSize: 2,
          positiveCount: 2,
          symbolMedianReturnPercent: 4.5,
          symbolMinReturnPercent: 2,
          symbolMaxReturnPercent: 7,
          benchmarkMedianReturnPercent: 1.5,
          relativeMedianReturnPercent: 3,
          completenessPercent: 100,
        }],
      }, response.comparisonSummaries[1]],
    });

    render(<SymbolEventArchiveV139 language="zh" symbol="AAPL" />);

    const comparison = await screen.findByRole('region', { name: '同类事件历史对比' });
    fireEvent.click(
      within(comparison).getByRole('button', { name: /06\/20.*财报披露/ }),
    );

    const timeline = screen.getByRole('region', { name: '事件与K线联动图' });
    expect(within(timeline).getByText('+7.00%')).toBeInTheDocument();
    expect(
      within(timeline).getByRole('button', { name: /06\/20.*财报披露/ }),
    ).toHaveAttribute('aria-pressed', 'true');
  });

  it('reloads a bounded 24-month archive and renders English text', async () => {
    render(<SymbolEventArchiveV139 language="en" symbol="AAPL" />);
    const panel = await screen.findByTestId('symbol-event-archive-v139');
    expect(within(panel).getByText('Symbol event archive')).toBeInTheDocument();
    expect(within(panel).getByText('Apple earnings release')).toBeInTheDocument();
    expect(within(panel).getByText(/Same-period changes do not establish/)).toBeInTheDocument();

    fireEvent.click(within(panel).getByRole('button', { name: '24 months' }));
    await waitFor(() => {
      expect(marketWorkspaceApi.getSymbolEventArchive).toHaveBeenLastCalledWith('AAPL', 24);
    });
  });

  it('degrades without blocking the surrounding symbol workspace', async () => {
    vi.mocked(marketWorkspaceApi.getSymbolEventArchive).mockRejectedValue(
      new Error('offline'),
    );
    render(<SymbolEventArchiveV139 language="zh" symbol="AAPL" />);

    expect(await screen.findByText('公开事件档案暂不可用，个股行情工作区仍可继续使用。')).toBeInTheDocument();
  });
});
