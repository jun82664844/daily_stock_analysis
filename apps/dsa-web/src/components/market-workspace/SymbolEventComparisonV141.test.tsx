import { fireEvent, render, screen, within } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import type { PublicSymbolEventArchiveItem } from '../../api/marketWorkspace';
import SymbolEventComparisonV141 from './SymbolEventComparisonV141';

const sourceState = {
  source: 'yahoo_chart_public',
  status: 'fresh' as const,
  observedAt: '2026-07-30T00:00:00Z',
  fetchedAt: '2026-07-30T00:00:00Z',
};

const event = (
  eventId: string,
  eventType: 'earnings' | 'dividend',
  eventTime: string,
  symbolReturnPercent: number | null,
): PublicSymbolEventArchiveItem => ({
  eventId,
  eventType,
  market: 'us',
  title: eventType === 'earnings' ? 'Apple earnings release' : 'Apple ex-dividend',
  summary: 'Traceable public event.',
  publisher: 'Yahoo Finance',
  sourceUrl: 'https://finance.yahoo.com/quote/AAPL',
  eventSourceState: sourceState,
  symbol: 'AAPL',
  name: 'Apple Inc.',
  subjectType: 'security',
  eventTime,
  eventTimeKind: 'observed',
  classificationSource: 'provider_event_history',
  scheduleType: eventType === 'earnings' ? 'earnings_release' : 'ex_dividend',
  historySymbol: 'AAPL',
  baselineDate: eventTime.slice(0, 10),
  benchmarkSymbol: '^GSPC',
  benchmarkName: 'S&P 500',
  status: symbolReturnPercent == null ? 'unavailable' : 'available',
  windows: symbolReturnPercent == null ? [] : [{
    tradingDays: 5,
    status: 'available',
    observedDate: '2026-07-29',
    symbolReturnPercent,
    benchmarkReturnPercent: 1,
    relativeReturnPercent: symbolReturnPercent - 1,
    volumeRatio: 1.2,
  }],
  sourceState,
  benchmarkSourceState: sourceState,
  warningCodes: [],
});

const events = [
  event('earnings-1', 'earnings', '2026-07-20T00:00:00Z', 6),
  event('earnings-2', 'earnings', '2026-04-20T00:00:00Z', -1),
  event('dividend-1', 'dividend', '2026-02-01T00:00:00Z', null),
];

const summaries = [{
  eventType: 'earnings' as const,
  eventCount: 4,
  observedEventCount: 3,
  windows: [{
    tradingDays: 1 as const,
    sampleSize: 3,
    benchmarkSampleSize: 3,
    relativeSampleSize: 3,
    positiveCount: 2,
    negativeCount: 1,
    flatCount: 0,
    symbolMedianReturnPercent: 1,
    symbolMinReturnPercent: -2,
    symbolMaxReturnPercent: 5,
    benchmarkMedianReturnPercent: 0.5,
    relativeMedianReturnPercent: 0.5,
    completenessPercent: 75,
  }, {
    tradingDays: 3 as const,
    sampleSize: 3,
    benchmarkSampleSize: 3,
    relativeSampleSize: 3,
    positiveCount: 2,
    negativeCount: 1,
    flatCount: 0,
    symbolMedianReturnPercent: 2,
    symbolMinReturnPercent: -1,
    symbolMaxReturnPercent: 5,
    benchmarkMedianReturnPercent: 0.8,
    relativeMedianReturnPercent: 1.2,
    completenessPercent: 75,
  }, {
    tradingDays: 5 as const,
    sampleSize: 3,
    benchmarkSampleSize: 3,
    relativeSampleSize: 3,
    positiveCount: 2,
    negativeCount: 1,
    flatCount: 0,
    symbolMedianReturnPercent: 2.5,
    symbolMinReturnPercent: -1,
    symbolMaxReturnPercent: 6,
    benchmarkMedianReturnPercent: 1.3,
    relativeMedianReturnPercent: 1.2,
    completenessPercent: 75,
  }, {
    tradingDays: 20 as const,
    sampleSize: 1,
    benchmarkSampleSize: 1,
    relativeSampleSize: 1,
    positiveCount: 1,
    negativeCount: 0,
    flatCount: 0,
    symbolMedianReturnPercent: 8,
    symbolMinReturnPercent: 8,
    symbolMaxReturnPercent: 8,
    benchmarkMedianReturnPercent: 3,
    relativeMedianReturnPercent: 5,
    completenessPercent: 25,
  }],
}];

describe('SymbolEventComparisonV141', () => {
  it('renders a Chinese same-type distribution for the selected window', () => {
    render(
      <SymbolEventComparisonV141
        language="zh"
        events={events}
        summaries={summaries}
        windowDays={5}
        selectedEventId="earnings-1"
        onSelectEvent={() => undefined}
      />,
    );

    const panel = screen.getByRole('region', { name: '同类事件历史对比' });
    expect(within(panel).getByText('财报披露')).toBeInTheDocument();
    expect(within(panel).getByText('4次事件')).toBeInTheDocument();
    expect(within(panel).getByText('有效事件 3/4')).toBeInTheDocument();
    expect(within(panel).getByText('+2.50%')).toBeInTheDocument();
    expect(within(panel).getByText('-1.00% 至 +6.00%')).toBeInTheDocument();
    expect(within(panel).getByText('正 2 / 负 1 / 平 0')).toBeInTheDocument();
    expect(within(panel).getByText('+1.20%')).toBeInTheDocument();
    expect(within(panel).getByText('75%')).toBeInTheDocument();
    expect(within(panel).queryByText(/买入|卖出|目标价|收益预测|胜率/)).not.toBeInTheDocument();
  });

  it('selects a historical sample and marks limited data honestly', () => {
    const onSelectEvent = vi.fn();
    render(
      <SymbolEventComparisonV141
        language="zh"
        events={events}
        summaries={summaries}
        windowDays={20}
        selectedEventId="earnings-1"
        onSelectEvent={onSelectEvent}
      />,
    );

    const panel = screen.getByRole('region', { name: '同类事件历史对比' });
    expect(within(panel).getByText('样本有限')).toBeInTheDocument();
    fireEvent.click(within(panel).getByRole('button', { name: /04\/20.*财报披露/ }));
    expect(onSelectEvent).toHaveBeenCalledWith('earnings-2');
  });

  it('keeps missing observations unavailable instead of rendering zero', () => {
    render(
      <SymbolEventComparisonV141
        language="zh"
        events={events}
        summaries={[{
          eventType: 'dividend',
          eventCount: 1,
          observedEventCount: 0,
          windows: summaries[0].windows.map((window) => ({
            ...window,
            sampleSize: 0,
            benchmarkSampleSize: 0,
            relativeSampleSize: 0,
            positiveCount: 0,
            negativeCount: 0,
            flatCount: 0,
            symbolMedianReturnPercent: null,
            symbolMinReturnPercent: null,
            symbolMaxReturnPercent: null,
            benchmarkMedianReturnPercent: null,
            relativeMedianReturnPercent: null,
            completenessPercent: 0,
          })),
        }]}
        windowDays={5}
        selectedEventId="dividend-1"
        onSelectEvent={() => undefined}
      />,
    );

    const panel = screen.getByRole('region', { name: '同类事件历史对比' });
    expect(within(panel).getByText('当前窗口暂无可用历史样本。')).toBeInTheDocument();
    expect(within(panel).queryByText('0.00%')).not.toBeInTheDocument();
  });

  it('renders complete English copy without Chinese platform labels', () => {
    render(
      <SymbolEventComparisonV141
        language="en"
        events={events}
        summaries={summaries}
        windowDays={5}
        selectedEventId="earnings-1"
        onSelectEvent={() => undefined}
      />,
    );

    const panel = screen.getByRole('region', { name: 'Same-type event comparison' });
    expect(within(panel).getByText('4 events')).toBeInTheDocument();
    expect(within(panel).getByText('Observed events 3/4')).toBeInTheDocument();
    expect(within(panel).getByText(/historical distribution does not predict future performance/)).toBeInTheDocument();
    expect(within(panel).queryByText(/同类|事件|样本|不构成投资建议/)).not.toBeInTheDocument();
  });
});
