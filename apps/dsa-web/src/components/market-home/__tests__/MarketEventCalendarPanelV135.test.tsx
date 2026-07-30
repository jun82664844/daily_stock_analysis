import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import type { PublicMarketEvent } from '../../../api/marketWorkspace';
import type { FollowedMarketEventV133 } from '../marketEventFollowUpV133';
import MarketEventCalendarPanelV135 from '../MarketEventCalendarPanelV135';

function scheduledEvent(
  eventId: string,
  market: 'cn' | 'hk' | 'us',
  symbol: string | null,
  name: string | null,
  eventTime: string,
  scheduleType: 'earnings_release' | 'ex_dividend' | 'macro_policy',
): PublicMarketEvent {
  return {
    eventId,
    market,
    category: scheduleType === 'ex_dividend'
      ? 'dividend'
      : scheduleType === 'macro_policy'
        ? 'macro'
        : 'earnings',
    title: `Source title ${eventId}`,
    summary: 'Public scheduled event.',
    symbol,
    name,
    sector: null,
    eventTime,
    timeKind: 'scheduled',
    publisher: scheduleType === 'macro_policy' ? 'Federal Reserve' : 'Public Calendar',
    url: 'https://example.com/calendar',
    sourceState: {
      source: 'unit_public_calendar',
      status: eventId === 'stale-event' ? 'stale' : 'fresh',
      observedAt: '2026-07-30T08:00:00.000Z',
    },
    classificationSource: 'provider_schedule',
    scheduleType,
    relevanceScore: 80,
    importance: 'high',
    relevanceReasons: ['scheduled_event'],
    sourceCount: 1,
    sourcePublishers: ['Public Calendar'],
    sourceRecords: [],
  };
}

const followedEvent: FollowedMarketEventV133 = {
  eventId: 'follow-aapl',
  market: 'us',
  category: 'corporate',
  title: 'Apple product event',
  symbol: 'AAPL',
  name: 'Apple',
  eventTime: '2026-07-28T08:00:00.000Z',
  publisher: 'Unit News',
  followedAt: '2026-07-29T00:00:00.000Z',
  baseline: null,
  observations: [],
};

const events: PublicMarketEvent[] = [
  scheduledEvent(
    'cn-today',
    'cn',
    '600519.SH',
    '贵州茅台',
    '2026-07-30T00:00:00.000Z',
    'earnings_release',
  ),
  scheduledEvent(
    'hk-week',
    'hk',
    '0700.HK',
    '腾讯控股',
    '2026-08-02T00:00:00.000Z',
    'earnings_release',
  ),
  scheduledEvent(
    'us-later',
    'us',
    'AAPL',
    'Apple Inc.',
    '2026-08-12T00:00:00.000Z',
    'ex_dividend',
  ),
  scheduledEvent(
    'fomc-week',
    'us',
    null,
    null,
    '2026-08-05T00:00:00.000Z',
    'macro_policy',
  ),
];

describe('MarketEventCalendarPanelV135', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it('defaults to this week and exposes today, mine, and due views in Chinese', () => {
    render(
      <MarketEventCalendarPanelV135
        language="zh"
        events={events}
        followedEvents={[followedEvent]}
        watchlistSymbols={['0700.HK']}
        scope="guest"
        now={new Date('2026-07-30T12:00:00.000Z')}
        onOpenSymbol={vi.fn()}
      />,
    );

    expect(screen.getByTestId('market-event-calendar-v135')).toBeInTheDocument();
    expect(screen.getByText('本周市场大事')).toBeInTheDocument();
    expect(screen.getByText('贵州茅台 财报披露')).toBeInTheDocument();
    expect(screen.getByText('腾讯控股 财报披露')).toBeInTheDocument();
    expect(screen.getByText('美联储 FOMC 会议')).toBeInTheDocument();
    expect(screen.queryByText('Apple Inc. 除息日')).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: '今日事件' }));
    expect(screen.getByText('贵州茅台 财报披露')).toBeInTheDocument();
    expect(screen.queryByText('腾讯控股 财报披露')).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: '我的日历' }));
    expect(screen.getByText('腾讯控股 财报披露')).toBeInTheDocument();
    expect(screen.getAllByText('Apple product event').length).toBeGreaterThan(0);
    expect(screen.queryByText('美联储 FOMC 会议')).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: '待复盘' }));
    expect(screen.getByText('1日复盘节点')).toBeInTheDocument();
  });

  it('renders localized English event labels, source status, and query action', () => {
    const onOpenSymbol = vi.fn();
    render(
      <MarketEventCalendarPanelV135
        language="en"
        events={events}
        followedEvents={[]}
        watchlistSymbols={['AAPL']}
        scope="user-72"
        now={new Date('2026-07-30T12:00:00.000Z')}
        onOpenSymbol={onOpenSymbol}
      />,
    );

    expect(screen.getByText('This week in markets')).toBeInTheDocument();
    expect(screen.getByText('贵州茅台 earnings release')).toBeInTheDocument();
    expect(screen.getByText('Federal Reserve FOMC meeting')).toBeInTheDocument();
    expect(screen.getAllByText('Scheduled date').length).toBeGreaterThan(0);
    expect(screen.getByText('Public data · No AI used')).toBeInTheDocument();
    expect(screen.getByText('Events and market prices shown together do not establish causality.')).toBeInTheDocument();
    expect(screen.getByText('Information and data only. Not investment advice.')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'My calendar' }));
    fireEvent.click(screen.getByRole('button', { name: 'Query AAPL' }));
    expect(onOpenSymbol).toHaveBeenCalledWith('AAPL');
  });

  it('truthfully displays stale source state and a bounded empty view', () => {
    const stale = scheduledEvent(
      'stale-event',
      'us',
      'MSFT',
      'Microsoft',
      '2026-08-01T00:00:00.000Z',
      'earnings_release',
    );
    const { rerender } = render(
      <MarketEventCalendarPanelV135
        language="zh"
        events={[stale]}
        followedEvents={[]}
        watchlistSymbols={[]}
        scope="guest"
        now={new Date('2026-07-30T12:00:00.000Z')}
        onOpenSymbol={vi.fn()}
      />,
    );

    expect(screen.getByText('陈旧缓存')).toBeInTheDocument();

    rerender(
      <MarketEventCalendarPanelV135
        language="zh"
        events={[]}
        followedEvents={[]}
        watchlistSymbols={[]}
        scope="guest"
        now={new Date('2026-07-30T12:00:00.000Z')}
        onOpenSymbol={vi.fn()}
      />,
    );
    expect(screen.getByText('本周暂无来源明确的计划事件')).toBeInTheDocument();
  });
});
