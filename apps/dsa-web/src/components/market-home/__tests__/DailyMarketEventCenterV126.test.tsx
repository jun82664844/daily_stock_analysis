import { fireEvent, render, screen, within } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { MarketSecurityItem, PublicMarketEvent } from '../../../api/marketWorkspace';
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
    sourceRecords: [
      { publisher: 'Unit News', source: 'unit_news', url: 'https://example.com/aapl', eventTime: '2026-07-14T02:00:00Z', timeKind: 'published' },
      { publisher: 'Official Feed', source: 'official_feed', url: 'https://official.example/aapl', eventTime: '2026-07-14T02:05:00Z', timeKind: 'published' },
    ],
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
    sourceRecords: [
      { publisher: '测试资讯源', source: 'unit_news', url: null, eventTime: '2026-07-14T01:00:00Z', timeKind: 'published' },
    ],
  },
];

const marketItems: MarketSecurityItem[] = [{
  symbol: 'AAPL',
  name: 'Apple Inc.',
  market: 'us',
  currency: 'USD',
  currentPrice: 212.45,
  changePercent: 1.25,
  volume: 45_600_000,
  turnover: 9_680_000_000,
  sourceState: {
    source: 'public_us_ranking',
    status: 'fresh',
    observedAt: '2026-07-14T02:10:00Z',
  },
}];

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
    expect(screen.getByText('自选相关')).toBeInTheDocument();
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
    expect(screen.getByText('Watchlist match')).toBeInTheDocument();
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

  it('defaults to explainable personalized priority and can return to relevance order', () => {
    const personalizedEvents: Array<PublicMarketEvent & { sector?: string | null }> = [
      { ...events[1], eventId: 'general-cn', relevanceScore: 99 },
      {
        ...events[0],
        eventId: 'sector-us',
        title: 'NVDA announces a new accelerator platform',
        symbol: 'NVDA',
        name: 'NVIDIA',
        sector: 'Technology',
        relevanceScore: 80,
      },
      {
        ...events[0],
        eventId: 'market-us',
        title: 'US stock market closes higher',
        symbol: null,
        name: null,
        sector: null,
        relevanceScore: 70,
      },
      { ...events[0], eventId: 'watchlist-us', relevanceScore: 20 },
    ];
    render(
      <DailyMarketEventCenterV126
        language="en"
        events={personalizedEvents}
        watchlistSymbols={['AAPL']}
        watchlistSectors={['Technology']}
        onOpenSymbol={vi.fn()}
      />,
    );

    expect(screen.getByRole('button', { name: 'For me first' })).toHaveAttribute('aria-pressed', 'true');
    expect(screen.getByText('Watchlist match')).toBeInTheDocument();
    expect(screen.getByText('Related industry')).toBeInTheDocument();
    expect(screen.getByText('Followed market')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'China' }));
    expect(screen.getByTestId('market-event-personalization-summary-v130')).toHaveTextContent(
      'Prioritized from 1 watchlist symbols, 1 related industries and 1 followed markets.',
    );
    fireEvent.click(screen.getByRole('button', { name: 'All markets' }));
    let articles = screen.getAllByRole('article');
    expect(within(articles[0]).getByText('AAPL earnings results published')).toBeInTheDocument();
    expect(within(articles[1]).getByText('NVDA announces a new accelerator platform')).toBeInTheDocument();
    expect(within(articles[2]).getByText('US stock market closes higher')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'All events' }));
    articles = screen.getAllByRole('article');
    expect(within(articles[0]).getByText(events[1].title)).toBeInTheDocument();
  });

  it('keeps the public event feed unpersonalized for visitors without a watchlist', () => {
    render(
      <DailyMarketEventCenterV126
        language="en"
        events={events}
        watchlistSymbols={[]}
        watchlistSectors={[]}
        onOpenSymbol={vi.fn()}
      />,
    );

    expect(screen.queryByRole('button', { name: 'For me first' })).not.toBeInTheDocument();
    expect(screen.queryByText('Watchlist match')).not.toBeInTheDocument();
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

  it('lets returning visitors read only new events without changing read state', () => {
    localStorage.setItem(MARKET_EVENT_SEEN_STORAGE_KEY, JSON.stringify(['event-2']));
    const { rerender } = render(
      <DailyMarketEventCenterV126
        language="zh"
        events={events}
        watchlistSymbols={[]}
        onOpenSymbol={vi.fn()}
      />,
    );

    expect(screen.getByTestId('market-event-inbox-summary-v131')).toHaveTextContent(
      '共 2 条 · 新增 1 · 重点 1',
    );
    fireEvent.click(screen.getByRole('button', { name: '只看新增' }));
    expect(screen.getByText('AAPL earnings results published')).toBeInTheDocument();
    expect(screen.queryByText('央行公布最新利率信息')).not.toBeInTheDocument();
    expect(JSON.parse(localStorage.getItem(MARKET_EVENT_SEEN_STORAGE_KEY) || '[]')).toEqual(['event-2']);

    rerender(
      <DailyMarketEventCenterV126
        language="en"
        events={events}
        watchlistSymbols={[]}
        onOpenSymbol={vi.fn()}
      />,
    );
    expect(screen.getByRole('button', { name: 'New only' })).toHaveAttribute('aria-pressed', 'true');
    expect(screen.getByTestId('market-event-inbox-summary-v131')).toHaveTextContent(
      '2 total · 1 new · 1 priority',
    );
  });

  it('keeps new-only results inside the selected market without changing inbox totals', () => {
    localStorage.setItem(MARKET_EVENT_SEEN_STORAGE_KEY, JSON.stringify(['event-2']));
    render(
      <DailyMarketEventCenterV126
        language="zh"
        events={events}
        watchlistSymbols={[]}
        onOpenSymbol={vi.fn()}
      />,
    );

    fireEvent.click(screen.getByRole('button', { name: '只看新增' }));
    fireEvent.click(screen.getByRole('button', { name: 'A股' }));
    expect(screen.getByText('当前没有新增市场事件')).toBeInTheDocument();
    expect(screen.queryByText('AAPL earnings results published')).not.toBeInTheDocument();
    expect(screen.getByTestId('market-event-inbox-summary-v131')).toHaveTextContent(
      '共 2 条 · 新增 1 · 重点 1',
    );
  });

  it('shows an honest new-event empty state and can return to all events', () => {
    localStorage.setItem(MARKET_EVENT_SEEN_STORAGE_KEY, JSON.stringify(['event-2']));
    render(
      <DailyMarketEventCenterV126
        language="zh"
        events={events}
        watchlistSymbols={[]}
        onOpenSymbol={vi.fn()}
      />,
    );

    fireEvent.click(screen.getByRole('button', { name: '只看新增' }));
    fireEvent.click(screen.getByRole('button', { name: '全部标为已读' }));
    expect(screen.getByText('当前没有新增市场事件')).toBeInTheDocument();
    expect(screen.getByText('公开事件仍完整保留，可返回全部事件继续浏览。')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: '查看全部事件' }));
    expect(screen.getByText('AAPL earnings results published')).toBeInTheDocument();
    expect(screen.getByText('央行公布最新利率信息')).toBeInTheDocument();
  });

  it('expands source evidence on demand with bilingual safe links', () => {
    const { rerender } = render(
      <DailyMarketEventCenterV126
        language="zh"
        events={events}
        watchlistSymbols={[]}
        onOpenSymbol={vi.fn()}
      />,
    );

    expect(screen.queryByText('已显示 2 / 共 2 条公开来源记录')).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: '查看 AAPL earnings results published 的来源' }));
    expect(screen.getByText('已显示 2 / 共 2 条公开来源记录')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: '打开 Unit News 原文' })).toHaveAttribute('href', 'https://example.com/aapl');
    expect(screen.getByRole('link', { name: '打开 Official Feed 原文' })).toHaveAttribute('href', 'https://official.example/aapl');

    rerender(
      <DailyMarketEventCenterV126
        language="en"
        events={events}
        watchlistSymbols={[]}
        onOpenSymbol={vi.fn()}
      />,
    );
    expect(screen.getByText('Showing 2 of 2 public source records')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Hide sources for AAPL earnings results published' }));
    expect(screen.queryByText('Showing 2 of 2 public source records')).not.toBeInTheDocument();
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
      sourceRecords: [{
        publisher: 'Unit News',
        source: 'unit_news',
        url: null,
        eventTime: '2026-07-14T03:00:00Z',
        timeKind: 'published',
      }],
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

  it('opens a no-AI event research card with linked public market context', () => {
    const open = vi.fn();
    render(
      <DailyMarketEventCenterV126
        language="zh"
        events={events}
        marketItems={marketItems}
        watchlistSymbols={[]}
        onOpenSymbol={open}
      />,
    );

    fireEvent.click(screen.getByRole('button', { name: '研究 AAPL 关联事件' }));
    const panel = screen.getByTestId('market-event-research-panel-v132');
    expect(within(panel).getByText('事件研究卡')).toBeInTheDocument();
    expect(within(panel).getByText('AAPL · Apple Inc.')).toBeInTheDocument();
    expect(within(panel).getByText('212.45')).toBeInTheDocument();
    expect(within(panel).getByText('+1.25%')).toBeInTheDocument();
    expect(within(panel).getByText('4,560万')).toBeInTheDocument();
    expect(within(panel).getByText('96.8亿')).toBeInTheDocument();
    expect(within(panel).getByText('价格变化与事件同时呈现，不代表事件导致涨跌。')).toBeInTheDocument();
    expect(within(panel).getByText('仅提供公开资讯和数据，不构成投资建议。')).toBeInTheDocument();

    fireEvent.click(within(panel).getByRole('button', { name: '查询关联证券 AAPL' }));
    expect(open).toHaveBeenCalledWith('AAPL');
    fireEvent.click(within(panel).getByRole('button', { name: '关闭事件研究卡' }));
    expect(screen.queryByTestId('market-event-research-panel-v132')).not.toBeInTheDocument();
  });

  it('degrades honestly when linked quote context is unavailable and shows a research checklist', () => {
    render(
      <DailyMarketEventCenterV126
        language="en"
        events={events}
        marketItems={[]}
        watchlistSymbols={[]}
        onOpenSymbol={vi.fn()}
      />,
    );

    fireEvent.click(screen.getByRole('button', { name: 'Research event linked to AAPL' }));
    const panel = screen.getByTestId('market-event-research-panel-v132');
    expect(within(panel).getByText('This security is not present in the loaded public rankings. Open the stock page to request the latest available data.')).toBeInTheDocument();
    expect(within(panel).queryByTestId('market-event-public-quote-v132')).not.toBeInTheDocument();
    expect(within(panel).getByText('Research checklist')).toBeInTheDocument();
    expect(within(panel).getByText('Check the original source and event time')).toBeInTheDocument();
    expect(within(panel).getByText('Verify quote source and freshness')).toBeInTheDocument();
    expect(within(panel).getByText('Compare later price and volume changes')).toBeInTheDocument();
  });
});
