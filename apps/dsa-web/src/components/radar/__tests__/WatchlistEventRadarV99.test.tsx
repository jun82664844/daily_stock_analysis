import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { WatchlistEventRadarV99 } from '../WatchlistEventRadarV99';

const radar = {
  userId: 7,
  plan: 'free',
  visibleLimit: 10,
  totalWatchlist: 12,
  processed: 10,
  hiddenCount: 2,
  degraded: 1,
  summary: {
    strongest: { stockCode: 'AAPL', stockName: 'Apple Inc.', changePercent: 5.2 },
    weakest: { stockCode: 'MU', stockName: 'Micron', changePercent: -3.4 },
    eventCount: 4,
    riskCount: 2,
    sourceEventCount: 1,
  },
  dailyDigest: {
    strongConfirmation: [{
      stockCode: 'AAPL',
      stockName: 'Apple Inc.',
      market: 'us',
      state: 'strong_confirmation',
      priorityScore: 96,
      changePercent: 5.2,
      signalScore: 78,
      dataConfidence: 'high',
    }],
    riskReview: [],
    waitForConfirmation: [],
    dataHealth: { fresh: 1, cached: 0, stale: 0, unavailable: 0 },
    upgradeBoundary: 'same_research_flow_better_sources_and_automation',
    aiUsed: false,
  },
  items: [
    {
      stockCode: 'AAPL',
      stockName: 'Apple Inc.',
      market: 'us',
      routeLane: 'us_market_data',
      currentPrice: 210,
      changePercent: 5.2,
      ma5: 205,
      ma20: 200,
      priceChange5d: 4,
      priceChange20d: 8,
      volumeChangePercent: 42,
      volumeSignal: 'price_volume_confirmed',
      signalScore: 78,
      updatedAt: '2026-07-11T09:30:00',
      freshness: 'fresh',
      degradationStatus: 'ok',
      warningCodes: [],
      aiUsed: false,
      status: 'ok',
      sourceStatus: 'available',
      researchBrief: {
        state: 'strong_confirmation',
        priorityScore: 96,
        dataConfidence: 'high',
        evidenceCodes: ['price_above_ma20', 'volume_expanded', 'usable_data'],
        nextWatch: { type: 'hold_above_ma20', value: 200 },
        invalidation: { type: 'lose_ma20', value: 200 },
        aiUsed: false,
      },
      events: [
        {
          stockCode: 'AAPL',
          type: 'price_move',
          severity: 'critical',
          direction: 'up',
          value: 5.2,
          referenceValue: null,
          title: null,
          summary: null,
          sourceName: null,
          sourceUrl: null,
          occurredAt: '2026-07-11T09:30:00',
          warningCodes: [],
          aiUsed: false,
        },
        {
          stockCode: 'AAPL',
          type: 'trend_position',
          severity: 'info',
          direction: 'above',
          value: 210,
          referenceValue: 200,
          title: null,
          summary: null,
          sourceName: null,
          sourceUrl: null,
          occurredAt: '2026-07-11T09:30:00',
          warningCodes: [],
          aiUsed: false,
        },
        {
          stockCode: 'AAPL',
          type: 'source_update',
          severity: 'info',
          direction: 'new',
          value: null,
          referenceValue: null,
          title: 'Apple files an official update',
          summary: 'Traceable filing summary',
          sourceName: 'SEC feed',
          sourceUrl: 'https://example.com/filing/1',
          occurredAt: '2026-07-11T08:30:00',
          warningCodes: [],
          aiUsed: false,
        },
      ],
      suggestedAlerts: [
        { stockCode: 'AAPL', type: 'price_move', threshold: 3, referenceValue: null, aiUsed: false },
        { stockCode: 'AAPL', type: 'ma20_cross', threshold: null, referenceValue: 200, aiUsed: false },
      ],
    },
  ],
  events: [],
  generatedAt: '2026-07-11T09:31:00Z',
  aiUsed: false,
  analysisBoundary: 'information_only_not_investment_advice',
};

describe('WatchlistEventRadarV99', () => {
  it('renders a complete Chinese daily review without leaking runtime tokens', () => {
    render(<WatchlistEventRadarV99 language="zh" radar={radar} onSelectSymbol={() => undefined} />);

    const panel = screen.getByTestId('watchlist-event-radar-v99');
    expect(panel).toHaveTextContent('今日自选事件雷达');
    expect(panel).toHaveTextContent(/最强\s*AAPL \+5\.2%/);
    expect(panel).toHaveTextContent('价格显著上涨 5.2%');
    expect(panel).toHaveTextContent('站上 MA20 200');
    expect(panel).toHaveTextContent('价格涨跌达到 3%');
    expect(panel).toHaveTextContent('还有 2 只自选未纳入本次复盘');
    expect(panel).not.toHaveTextContent('critical');
    expect(panel).not.toHaveTextContent('price_move');
  });

  it('renders the same information structure in English', () => {
    render(<WatchlistEventRadarV99 language="en" radar={radar} onSelectSymbol={() => undefined} />);

    const panel = screen.getByTestId('watchlist-event-radar-v99');
    expect(panel).toHaveTextContent('Today’s watchlist event radar');
    expect(panel).toHaveTextContent('Price rose materially by 5.2%');
    expect(panel).toHaveTextContent('Price crosses MA20 at 200');
    expect(panel).not.toHaveTextContent('今日自选事件雷达');
  });

  it('keeps traceable source links and opens a symbol from the workflow', () => {
    const onSelectSymbol = vi.fn();
    render(<WatchlistEventRadarV99 language="zh" radar={radar} onSelectSymbol={onSelectSymbol} />);

    expect(screen.getByRole('link', { name: /Apple files an official update/ })).toHaveAttribute(
      'href',
      'https://example.com/filing/1',
    );
    fireEvent.click(screen.getByTestId('watchlist-radar-symbol-AAPL'));
    expect(onSelectSymbol).toHaveBeenCalledWith('AAPL');
  });

  it('saves a suggested alert and shows its saved state', () => {
    const onSaveAlert = vi.fn();
    const { rerender } = render(
      <WatchlistEventRadarV99
        language="zh"
        radar={radar}
        onSelectSymbol={() => undefined}
        onSaveAlert={onSaveAlert}
        savedRuleKeys={new Set()}
        alertBusy={false}
      />,
    );

    fireEvent.click(screen.getByTestId('watchlist-alert-save-AAPL-price_move'));
    expect(onSaveAlert).toHaveBeenCalledWith(radar.items[0].suggestedAlerts[0]);

    rerender(
      <WatchlistEventRadarV99
        language="zh"
        radar={radar}
        onSelectSymbol={() => undefined}
        onSaveAlert={onSaveAlert}
        savedRuleKeys={new Set(['AAPL:price_move'])}
        alertBusy={false}
      />,
    );
    expect(screen.getByTestId('watchlist-alert-save-AAPL-price_move')).toHaveTextContent('已保存');
    expect(screen.getByTestId('watchlist-alert-save-AAPL-price_move')).toBeDisabled();
  });

  it('shows a useful empty state', () => {
    render(
      <WatchlistEventRadarV99
        language="zh"
        radar={{
          ...radar,
          totalWatchlist: 0,
          processed: 0,
          hiddenCount: 0,
          items: [],
          summary: { strongest: null, weakest: null, eventCount: 0, riskCount: 0, sourceEventCount: 0 },
        }}
        onSelectSymbol={() => undefined}
      />,
    );

    expect(screen.getByTestId('watchlist-event-radar-empty')).toHaveTextContent('先加入自选股');
  });
});
