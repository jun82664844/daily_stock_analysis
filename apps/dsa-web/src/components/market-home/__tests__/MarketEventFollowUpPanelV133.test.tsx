import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import type { PublicMarketEvent } from '../../../api/marketWorkspace';
import type { FollowedMarketEventV133 } from '../marketEventFollowUpV133';
import MarketEventFollowUpPanelV133 from '../MarketEventFollowUpPanelV133';

const followed: FollowedMarketEventV133 = {
  eventId: 'event-aapl-launch',
  market: 'us',
  category: 'corporate',
  title: 'Apple publishes a product update',
  symbol: 'AAPL',
  name: 'Apple',
  eventTime: '2026-07-20T09:00:00.000Z',
  publisher: 'Unit News',
  followedAt: '2026-07-20T10:00:00.000Z',
  baseline: {
    observedAt: '2026-07-20T10:00:00.000Z',
    price: 100,
    changePercent: 1.2,
    volume: 2_000,
    turnover: 200_000,
    source: 'unit_quote',
    status: 'fresh',
  },
  observations: [
    {
      observedAt: '2026-07-20T10:00:00.000Z',
      price: 100,
      changePercent: 1.2,
      volume: 2_000,
      turnover: 200_000,
      source: 'unit_quote',
      status: 'fresh',
    },
    {
      observedAt: '2026-07-21T11:00:00.000Z',
      price: 103,
      changePercent: 2.1,
      volume: 3_000,
      turnover: 309_000,
      source: 'unit_quote',
      status: 'fresh',
    },
  ],
};

const laterEvent: PublicMarketEvent = {
  eventId: 'event-aapl-follow-up',
  market: 'us',
  category: 'corporate',
  title: 'Apple publishes a follow-up update',
  summary: 'Later public company update.',
  symbol: 'AAPL',
  name: 'Apple',
  sector: 'Technology',
  eventTime: '2026-07-22T09:00:00.000Z',
  timeKind: 'published',
  publisher: 'Unit News',
  url: 'https://example.com/aapl-follow-up',
  sourceState: {
    source: 'unit_news',
    status: 'fresh',
    observedAt: '2026-07-22T09:01:00.000Z',
  },
  classificationSource: 'keyword_rules',
  relevanceScore: 80,
  importance: 'high',
  relevanceReasons: ['linked_security', 'corporate_event'],
  sourceCount: 1,
  sourcePublishers: ['Unit News'],
  sourceRecords: [],
};

describe('MarketEventFollowUpPanelV133', () => {
  it('shows a Chinese follow-up record with checkpoints and explicit information-only boundaries', () => {
    render(
      <MarketEventFollowUpPanelV133
        language="zh"
        followedEvents={[followed]}
        publicEvents={[laterEvent]}
        now={new Date('2026-07-24T10:00:00.000Z')}
        onOpenSymbol={vi.fn()}
        onRemove={vi.fn()}
      />,
    );

    expect(screen.getByTestId('market-event-follow-up-panel-v133')).toBeInTheDocument();
    expect(screen.getByText('事件后续追踪')).toBeInTheDocument();
    expect(screen.getByText('关注时基准')).toBeInTheDocument();
    expect(screen.getByText('较关注时')).toBeInTheDocument();
    expect(screen.getByText('+3%')).toBeInTheDocument();
    expect(screen.getByText('1日')).toBeInTheDocument();
    expect(screen.getByText('已观察')).toBeInTheDocument();
    expect(screen.getByText('后续公开事件')).toBeInTheDocument();
    expect(screen.getByText('Apple publishes a follow-up update')).toBeInTheDocument();
    expect(screen.getByText(/不代表事件导致行情变化/)).toBeInTheDocument();
    expect(screen.getByText(/不构成投资建议/)).toBeInTheDocument();
  });

  it('uses English copy and exposes query and remove actions', () => {
    const onOpenSymbol = vi.fn();
    const onRemove = vi.fn();
    render(
      <MarketEventFollowUpPanelV133
        language="en"
        followedEvents={[followed]}
        publicEvents={[]}
        now={new Date('2026-07-20T12:00:00.000Z')}
        onOpenSymbol={onOpenSymbol}
        onRemove={onRemove}
      />,
    );

    expect(screen.getByText('Event follow-up')).toBeInTheDocument();
    expect(screen.getAllByText('Pending')).toHaveLength(4);
    fireEvent.click(screen.getByRole('button', { name: 'Query AAPL' }));
    fireEvent.click(screen.getByRole('button', { name: 'Stop following AAPL' }));

    expect(onOpenSymbol).toHaveBeenCalledWith('AAPL');
    expect(onRemove).toHaveBeenCalledWith('event-aapl-launch');
  });

  it('renders nothing when there are no followed events', () => {
    const { container } = render(
      <MarketEventFollowUpPanelV133
        language="zh"
        followedEvents={[]}
        publicEvents={[]}
        onOpenSymbol={vi.fn()}
        onRemove={vi.fn()}
      />,
    );

    expect(container).toBeEmptyDOMElement();
  });
});
