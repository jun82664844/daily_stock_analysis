import { fireEvent, render, screen, within } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { PublicMarketEvent } from '../../../api/marketWorkspace';
import { MARKET_EVENT_SEEN_STORAGE_KEY } from '../../../lib/marketEventReadState';
import DailyMarketEventCenterV126 from '../DailyMarketEventCenterV126';

const events: PublicMarketEvent[] = [
  {
    eventId: 'event-1',
    market: 'us',
    category: 'earnings',
    title: 'AAPL earnings results published',
    summary: 'Public earnings information.',
    symbol: 'AAPL',
    name: 'Apple Inc.',
    eventTime: '2026-07-14T02:00:00Z',
    timeKind: 'published',
    publisher: 'Unit News',
    url: 'https://example.com/aapl',
    sourceState: { source: 'unit_news', status: 'fresh' },
    classificationSource: 'keyword_rules',
    relevanceScore: 72,
    importance: 'high',
    relevanceReasons: ['linked_security', 'earnings_event', 'fresh_source'],
    sourceCount: 2,
    sourcePublishers: ['Unit News', 'Official Feed'],
  },
  {
    eventId: 'event-2',
    market: 'cn',
    category: 'macro',
    title: '央行公布最新利率信息',
    summary: '公开宏观信息。',
    eventTime: '2026-07-14T01:00:00Z',
    timeKind: 'published',
    publisher: '测试资讯源',
    sourceState: { source: 'unit_news', status: 'cached' },
    classificationSource: 'keyword_rules',
    relevanceScore: 50,
    importance: 'medium',
    relevanceReasons: ['macro_event', 'cached_source'],
    sourceCount: 1,
    sourcePublishers: ['测试资讯源'],
  },
];

describe('DailyMarketEventCenterV126', () => {
  beforeEach(() => localStorage.clear());

  it('shows bilingual structured events and highlights watchlist symbols', () => {
    const open = vi.fn();
    const { rerender } = render(
      <DailyMarketEventCenterV126
        language="zh"
        events={events}
        watchlistSymbols={['AAPL']}
        onOpenSymbol={open}
      />,
    );

    expect(screen.getByRole('heading', { name: '今日市场事件' })).toBeInTheDocument();
    expect(screen.getByText('重点事件 1')).toBeInTheDocument();
    expect(screen.getByText('自选关注')).toBeInTheDocument();
    expect(screen.getAllByText('财报业绩')).toHaveLength(2);
    expect(screen.getByText('宏观数据')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: '查询 AAPL' }));
    expect(open).toHaveBeenCalledWith('AAPL');

    rerender(
      <DailyMarketEventCenterV126
        language="en"
        events={events}
        watchlistSymbols={['AAPL']}
        onOpenSymbol={open}
      />,
    );
    expect(screen.getByRole('heading', { name: 'Daily market events' })).toBeInTheDocument();
    expect(screen.getByText('Watchlist')).toBeInTheDocument();
  });

  it('filters categories without hiding truthful source state', () => {
    render(
      <DailyMarketEventCenterV126
        language="zh"
        events={events}
        watchlistSymbols={[]}
        onOpenSymbol={vi.fn()}
      />,
    );

    fireEvent.click(screen.getByRole('button', { name: '宏观' }));
    expect(screen.getByText('央行公布最新利率信息')).toBeInTheDocument();
    expect(screen.queryByText('AAPL earnings results published')).not.toBeInTheDocument();
    expect(screen.getByText('缓存')).toBeInTheDocument();
    expect(screen.getByText('仅提供公开资讯和数据，不构成投资建议。')).toBeInTheDocument();
  });

  it('filters by market and explains why retained events matter', () => {
    const { rerender } = render(
      <DailyMarketEventCenterV126
        language="zh"
        events={events}
        watchlistSymbols={[]}
        onOpenSymbol={vi.fn()}
      />,
    );

    fireEvent.click(screen.getByRole('button', { name: 'A股' }));
    expect(screen.getByText('央行公布最新利率信息')).toBeInTheDocument();
    expect(screen.queryByText('AAPL earnings results published')).not.toBeInTheDocument();
    expect(screen.getByText('中重要度')).toBeInTheDocument();
    expect(screen.getByText('宏观事件')).toBeInTheDocument();
    expect(screen.getByText('缓存来源')).toBeInTheDocument();

    rerender(
      <DailyMarketEventCenterV126
        language="en"
        events={events}
        watchlistSymbols={[]}
        onOpenSymbol={vi.fn()}
      />,
    );
    expect(screen.getByText('Medium importance')).toBeInTheDocument();
    expect(screen.getByText('Cached source')).toBeInTheDocument();
  });

  it('puts watchlist-linked events before higher-scored general events', () => {
    render(
      <DailyMarketEventCenterV126
        language="en"
        events={[events[1], { ...events[0], relevanceScore: 20, importance: 'low' }]}
        watchlistSymbols={['AAPL']}
        onOpenSymbol={vi.fn()}
      />,
    );

    const articles = screen.getAllByRole('article');
    expect(within(articles[0]).getByText('AAPL earnings results published')).toBeInTheDocument();
  });

  it('shows multi-source transparency and locally marks new events as read', () => {
    localStorage.setItem(MARKET_EVENT_SEEN_STORAGE_KEY, JSON.stringify(['event-2']));
    const { rerender } = render(
      <DailyMarketEventCenterV126
        language="zh"
        events={events}
        watchlistSymbols={[]}
        onOpenSymbol={vi.fn()}
      />,
    );

    expect(screen.getByText('新增 1')).toBeInTheDocument();
    expect(screen.getByText('新事件')).toBeInTheDocument();
    expect(screen.getByText('2 条公开来源记录')).toBeInTheDocument();
    expect(screen.getByText('Official Feed')).toBeInTheDocument();

    rerender(
      <DailyMarketEventCenterV126
        language="en"
        events={events}
        watchlistSymbols={[]}
        onOpenSymbol={vi.fn()}
      />,
    );
    expect(screen.getByText('1 new')).toBeInTheDocument();
    expect(screen.getByText('2 public source records')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Mark all as read' }));
    expect(screen.queryByText('1 new')).not.toBeInTheDocument();
    expect(JSON.parse(localStorage.getItem(MARKET_EVENT_SEEN_STORAGE_KEY) || '[]')).toEqual([
      'event-1',
      'event-2',
    ]);
  });

  it('offers a market-update filter and labels unlinked markets as source channels', () => {
    const marketEvent: PublicMarketEvent = {
      eventId: 'event-market',
      market: 'us',
      category: 'market',
      title: 'Broad market bulletin',
      eventTime: '2026-07-14T03:00:00Z',
      timeKind: 'published',
      publisher: 'Unit News',
      sourceState: { source: 'unit_news', status: 'fresh' },
      classificationSource: 'keyword_rules',
      relevanceScore: 40,
      importance: 'medium',
      relevanceReasons: ['market_signal', 'fresh_source'],
      sourceCount: 1,
      sourcePublishers: ['Unit News'],
    };
    render(
      <DailyMarketEventCenterV126
        language="en"
        events={[...events, marketEvent]}
        watchlistSymbols={[]}
        onOpenSymbol={vi.fn()}
      />,
    );

    expect(screen.getByText('China source')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Market' }));
    expect(screen.getByText('Broad market bulletin')).toBeInTheDocument();
    expect(screen.getByText('US source')).toBeInTheDocument();
    expect(screen.queryByText('AAPL earnings results published')).not.toBeInTheDocument();
  });

  it('renders a useful empty state without inventing events', () => {
    render(
      <DailyMarketEventCenterV126
        language="zh"
        events={[]}
        watchlistSymbols={[]}
        onOpenSymbol={vi.fn()}
      />,
    );

    expect(screen.getByText('暂未取得可展示的公开市场事件')).toBeInTheDocument();
  });
});
