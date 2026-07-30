import { fireEvent, render, screen, within } from '@testing-library/react';
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
    expect(within(panel).getByText('+2.00%')).toBeInTheDocument();
    expect(within(panel).getAllByText('+1.00%')).toHaveLength(2);
    expect(within(panel).getAllByRole('link', { name: '查看来源' })[0]).toHaveAttribute(
      'href',
      'https://finance.yahoo.com/quote/AAPL',
    );
    expect(within(panel).getByText('同期变化不代表事件导致价格变化。本功能只提供资讯和客观数据，不构成投资建议。')).toBeInTheDocument();
    expect(within(panel).queryByText(/买入|卖出|目标价|收益预测/)).not.toBeInTheDocument();

    fireEvent.click(within(panel).getByRole('button', { name: '3个交易日' }));
    expect(within(panel).getByText('+4.00%')).toBeInTheDocument();
    expect(within(panel).getByText('+3.00%')).toBeInTheDocument();

    fireEvent.click(within(panel).getByRole('button', { name: '分红除息' }));
    expect(within(panel).getByText('Apple Inc.（AAPL）分红除息')).toBeInTheDocument();
    expect(within(panel).queryByText('Apple Inc.（AAPL）财报披露')).not.toBeInTheDocument();
  });

  it('reloads a bounded 24-month archive and renders English text', async () => {
    render(<SymbolEventArchiveV139 language="en" symbol="AAPL" />);
    const panel = await screen.findByTestId('symbol-event-archive-v139');
    expect(within(panel).getByText('Symbol event archive')).toBeInTheDocument();
    expect(within(panel).getByText('Apple earnings release')).toBeInTheDocument();
    expect(within(panel).getByText(/Same-period changes do not establish/)).toBeInTheDocument();

    fireEvent.click(within(panel).getByRole('button', { name: '24 months' }));
    expect(marketWorkspaceApi.getSymbolEventArchive).toHaveBeenLastCalledWith('AAPL', 24);
  });

  it('degrades without blocking the surrounding symbol workspace', async () => {
    vi.mocked(marketWorkspaceApi.getSymbolEventArchive).mockRejectedValue(
      new Error('offline'),
    );
    render(<SymbolEventArchiveV139 language="zh" symbol="AAPL" />);

    expect(await screen.findByText('公开事件档案暂不可用，个股行情工作区仍可继续使用。')).toBeInTheDocument();
  });
});
