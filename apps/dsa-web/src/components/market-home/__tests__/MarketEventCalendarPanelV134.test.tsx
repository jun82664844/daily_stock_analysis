import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import type { PublicMarketEvent } from '../../../api/marketWorkspace';
import type { FollowedMarketEventV133 } from '../marketEventFollowUpV133';
import MarketEventCalendarPanelV134 from '../MarketEventCalendarPanelV134';

const scheduledEvent: PublicMarketEvent = {
  eventId: 'event-aapl-scheduled',
  market: 'us',
  category: 'earnings',
  title: 'Apple reports earnings on 2026-08-02',
  summary: 'The source explicitly provides the event date.',
  symbol: 'AAPL',
  name: 'Apple',
  sector: 'Technology',
  eventTime: '2026-07-30T08:00:00.000Z',
  timeKind: 'published',
  publisher: 'Unit News',
  url: 'https://example.com/aapl',
  sourceState: {
    source: 'unit_news',
    status: 'fresh',
    observedAt: '2026-07-30T08:01:00.000Z',
  },
  classificationSource: 'keyword_rules',
  relevanceScore: 80,
  importance: 'high',
  relevanceReasons: ['linked_security', 'earnings_event'],
  sourceCount: 1,
  sourcePublishers: ['Unit News'],
  sourceRecords: [],
};

const publishedEvent: PublicMarketEvent = {
  ...scheduledEvent,
  eventId: 'event-cn-published',
  market: 'cn',
  category: 'announcement',
  title: '贵州茅台发布公告',
  summary: '公开公告。',
  symbol: '600519.SH',
  name: '贵州茅台',
  publisher: '公开资讯源',
};

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

describe('MarketEventCalendarPanelV134', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it('renders an honest Chinese calendar with schedule, publication, and follow-up time bases', () => {
    render(
      <MarketEventCalendarPanelV134
        language="zh"
        events={[scheduledEvent, publishedEvent]}
        followedEvents={[followedEvent]}
        watchlistSymbols={['AAPL']}
        scope="guest"
        now={new Date('2026-07-30T12:00:00.000Z')}
        onOpenSymbol={vi.fn()}
      />,
    );

    expect(screen.getByTestId('market-event-calendar-v134')).toBeInTheDocument();
    expect(screen.getByText('免费市场日历')).toBeInTheDocument();
    expect(screen.getByText('待复盘 1')).toBeInTheDocument();
    expect(screen.getByText('计划日期')).toBeInTheDocument();
    expect(screen.getByText('发布时间')).toBeInTheDocument();
    expect(screen.getByText('1日复盘节点')).toBeInTheDocument();
    expect(screen.getByText('来源明确给出日期时才标记为计划事件。')).toBeInTheDocument();
    expect(screen.getByText('事件与行情并列展示不代表因果关系。')).toBeInTheDocument();
    expect(screen.getByText('日历仅整理公开资讯和本地检查点，不构成投资建议。')).toBeInTheDocument();
  });

  it('filters due reviews and acknowledges them locally', () => {
    render(
      <MarketEventCalendarPanelV134
        language="zh"
        events={[scheduledEvent]}
        followedEvents={[followedEvent]}
        watchlistSymbols={[]}
        scope="guest"
        now={new Date('2026-07-30T12:00:00.000Z')}
        onOpenSymbol={vi.fn()}
      />,
    );

    fireEvent.click(screen.getByRole('button', { name: '待复盘' }));
    expect(screen.getByText('1日复盘节点')).toBeInTheDocument();
    expect(screen.queryByText('Apple reports earnings on 2026-08-02')).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: '全部标为已查看' }));
    expect(screen.getByText('待复盘 0')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: '全部标为已查看' })).not.toBeInTheDocument();
  });

  it('renders English copy and opens a linked security', () => {
    const onOpenSymbol = vi.fn();
    render(
      <MarketEventCalendarPanelV134
        language="en"
        events={[scheduledEvent]}
        followedEvents={[]}
        watchlistSymbols={['AAPL']}
        scope="user-72"
        now={new Date('2026-07-30T12:00:00.000Z')}
        onOpenSymbol={onOpenSymbol}
      />,
    );

    expect(screen.getByText('Free market calendar')).toBeInTheDocument();
    expect(screen.getByText('Scheduled date')).toBeInTheDocument();
    expect(screen.getByText('No AI used')).toBeInTheDocument();
    expect(screen.getByText('This calendar only organizes public information and local checkpoints. Not investment advice.')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Query AAPL' }));
    expect(onOpenSymbol).toHaveBeenCalledWith('AAPL');
  });

  it('keeps followed checkpoints visible when the public event stream fills the display limit', () => {
    const densePublicEvents = Array.from({ length: 14 }, (_, index) => ({
      ...publishedEvent,
      eventId: `dense-public-${index}`,
      title: `公开市场事件 ${index + 1}`,
      eventTime: `2026-07-30T${String(index).padStart(2, '0')}:00:00.000Z`,
    }));
    render(
      <MarketEventCalendarPanelV134
        language="zh"
        events={densePublicEvents}
        followedEvents={[{
          ...followedEvent,
          followedAt: '2026-07-30T12:00:00.000Z',
        }]}
        watchlistSymbols={[]}
        scope="guest"
        now={new Date('2026-07-30T12:00:00.000Z')}
        onOpenSymbol={vi.fn()}
      />,
    );

    expect(screen.getByText('1日复盘节点')).toBeInTheDocument();
    expect(screen.getByText('3日复盘节点')).toBeInTheDocument();
    expect(screen.getByText('5日复盘节点')).toBeInTheDocument();
    expect(screen.getByText('20日复盘节点')).toBeInTheDocument();
  });
});
