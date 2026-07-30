import { fireEvent, render, screen, within } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import type {
  PublicSymbolEventArchiveItem,
  PublicSymbolEventChart,
} from '../../api/marketWorkspace';
import SymbolEventTimelineV140 from './SymbolEventTimelineV140';

const sourceState = {
  source: 'yahoo_chart_public',
  status: 'fresh' as const,
  observedAt: '2026-07-30T00:00:00Z',
  fetchedAt: '2026-07-30T00:00:00Z',
};

const chart: PublicSymbolEventChart = {
  status: 'available',
  historySymbol: 'AAPL',
  benchmarkSymbol: '^GSPC',
  benchmarkName: 'S&P 500',
  points: [{
    date: '2026-07-18',
    symbolClose: 100,
    benchmarkClose: 200,
    symbolChangePercent: 0,
    benchmarkChangePercent: 0,
    relativeChangePercent: 0,
    volume: 1_000,
  }, {
    date: '2026-07-20',
    symbolClose: 105,
    benchmarkClose: 202,
    symbolChangePercent: 5,
    benchmarkChangePercent: 1,
    relativeChangePercent: 4,
    volume: 1_200,
  }, {
    date: '2026-07-21',
    symbolClose: 110,
    benchmarkClose: 204,
    symbolChangePercent: 10,
    benchmarkChangePercent: 2,
    relativeChangePercent: 8,
    volume: 1_400,
  }],
  sourceState,
  benchmarkSourceState: sourceState,
  warningCodes: [],
};

const event = (
  eventId: string,
  eventType: 'earnings' | 'dividend',
  baselineDate: string | null,
): PublicSymbolEventArchiveItem => ({
  eventId,
  eventType,
  market: 'us',
  title: eventType === 'earnings' ? 'Apple earnings release' : 'Apple ex-dividend',
  summary: 'Public event.',
  publisher: 'Yahoo Finance',
  sourceUrl: 'https://finance.yahoo.com/quote/AAPL',
  eventSourceState: sourceState,
  symbol: 'AAPL',
  name: 'Apple Inc.',
  subjectType: 'security',
  eventTime: `${baselineDate ?? '2026-05-10'}T00:00:00Z`,
  eventTimeKind: 'observed',
  classificationSource: 'provider_event_history',
  scheduleType: eventType === 'earnings' ? 'earnings_release' : 'ex_dividend',
  historySymbol: 'AAPL',
  baselineDate,
  benchmarkSymbol: '^GSPC',
  benchmarkName: 'S&P 500',
  status: baselineDate ? 'partial' : 'unavailable',
  windows: baselineDate ? [{
    tradingDays: 1,
    status: 'available',
    observedDate: '2026-07-21',
    symbolReturnPercent: 4.7619,
    benchmarkReturnPercent: 0.9901,
    relativeReturnPercent: 3.7718,
    volumeRatio: 1.2,
  }] : [],
  sourceState,
  benchmarkSourceState: sourceState,
  warningCodes: baselineDate ? [] : ['event_price_observation_unavailable'],
});

const events = [
  event('earnings-aapl', 'earnings', '2026-07-20'),
  event('dividend-aapl', 'dividend', null),
];

describe('SymbolEventTimelineV140', () => {
  it('renders a Chinese normalized timeline and links the active event window', () => {
    render(
      <SymbolEventTimelineV140
        language="zh"
        chart={chart}
        events={events}
        windowDays={1}
      />,
    );

    const panel = screen.getByRole('region', { name: '事件与K线联动图' });
    expect(within(panel).getByText('相对走势（区间起点=0）')).toBeInTheDocument();
    expect(within(panel).getAllByText('Apple Inc.').length).toBeGreaterThanOrEqual(1);
    expect(within(panel).getAllByText('标普500指数').length).toBeGreaterThanOrEqual(1);
    expect(within(panel).getByText('事件后1个交易日')).toBeInTheDocument();
    expect(within(panel).getByText('+4.76%')).toBeInTheDocument();
    expect(within(panel).getByText(/同图展示不代表事件导致价格变化/)).toBeInTheDocument();
    expect(within(panel).queryByText(/建议买入|建议卖出|目标价|收益预测/)).not.toBeInTheDocument();

    fireEvent.click(within(panel).getByRole('button', { name: /分红除息/ }));
    expect(within(panel).getByText('该事件暂无可用的行情观察窗口。')).toBeInTheDocument();
  });

  it('renders complete English copy without Chinese platform labels', () => {
    render(
      <SymbolEventTimelineV140
        language="en"
        chart={{ ...chart, benchmarkName: '标普500指数' }}
        events={events.map((event) => ({ ...event, name: '腾讯控股' }))}
        windowDays={1}
      />,
    );

    const panel = screen.getByRole('region', { name: 'Event and price timeline' });
    expect(within(panel).getByText('Normalized performance (range start = 0)')).toBeInTheDocument();
    expect(within(panel).getAllByText('AAPL').length).toBeGreaterThanOrEqual(1);
    expect(within(panel).getAllByText('S&P 500 Index').length).toBeGreaterThanOrEqual(1);
    expect(within(panel).getByText('1 session after event')).toBeInTheDocument();
    expect(within(panel).getByText(/does not establish that an event caused/)).toBeInTheDocument();
    expect(within(panel).queryByText(/事件|交易日|不构成投资建议/)).not.toBeInTheDocument();
  });

  it('keeps the symbol series when benchmark data is unavailable', () => {
    render(
      <SymbolEventTimelineV140
        language="zh"
        chart={{
          ...chart,
          status: 'partial',
          points: chart.points.map((point) => ({
            ...point,
            benchmarkClose: null,
            benchmarkChangePercent: null,
            relativeChangePercent: null,
          })),
          benchmarkSourceState: {
            source: 'yahoo_chart_public',
            status: 'unavailable',
          },
          warningCodes: ['benchmark_history_unavailable'],
        }}
        events={events}
        windowDays={1}
      />,
    );

    const panel = screen.getByRole('region', { name: '事件与K线联动图' });
    expect(within(panel).getByText('市场基准历史暂不可用，个股曲线仍可查看。')).toBeInTheDocument();
    expect(within(panel).getAllByText('Apple Inc.').length).toBeGreaterThanOrEqual(1);
  });

  it('shows an honest empty state when price history is unavailable', () => {
    render(
      <SymbolEventTimelineV140
        language="zh"
        chart={{ ...chart, status: 'unavailable', points: [] }}
        events={events}
        windowDays={1}
      />,
    );

    expect(screen.getByText('历史行情暂不可用，事件档案仍可继续查看。')).toBeInTheDocument();
  });
});
