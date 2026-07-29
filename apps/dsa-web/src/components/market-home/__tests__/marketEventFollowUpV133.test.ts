import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { MarketSecurityItem, PublicMarketEvent } from '../../../api/marketWorkspace';
import {
  FOLLOW_UP_HORIZON_DAYS,
  adoptGuestFollowedMarketEvents,
  buildFollowUpCheckpoints,
  followMarketEvent,
  latestFollowUpEvents,
  loadFollowedMarketEvents,
  marketEventFollowUpStorageKey,
  recordFollowedMarketEventObservations,
  unfollowMarketEvent,
} from '../marketEventFollowUpV133';

const event: PublicMarketEvent = {
  eventId: 'event-aapl-launch',
  market: 'us',
  category: 'corporate',
  title: 'Apple publishes a product update',
  summary: 'Public company update.',
  symbol: 'AAPL',
  name: 'Apple',
  sector: 'Technology',
  eventTime: '2026-07-20T09:00:00.000Z',
  timeKind: 'published',
  publisher: 'Unit News',
  url: 'https://example.com/aapl',
  sourceState: {
    source: 'unit_news',
    status: 'fresh',
    observedAt: '2026-07-20T09:01:00.000Z',
  },
  classificationSource: 'keyword_rules',
  relevanceScore: 80,
  importance: 'high',
  relevanceReasons: ['linked_security', 'corporate_event'],
  sourceCount: 1,
  sourcePublishers: ['Unit News'],
  sourceRecords: [],
};

const quote: MarketSecurityItem = {
  symbol: 'AAPL',
  name: 'Apple',
  market: 'us',
  currency: 'USD',
  currentPrice: 100,
  changePercent: 1.25,
  volume: 2_000,
  turnover: 200_000,
  sector: 'Technology',
  sourceState: {
    source: 'unit_quote',
    status: 'fresh',
    observedAt: '2026-07-20T10:00:00.000Z',
  },
};

describe('marketEventFollowUpV133', () => {
  beforeEach(() => {
    localStorage.clear();
    vi.restoreAllMocks();
  });

  it('persists a followed event with an honest follow-time quote baseline', () => {
    const result = followMarketEvent(
      event,
      quote,
      'guest',
      () => '2026-07-20T10:00:00.000Z',
    );

    expect(result).toHaveLength(1);
    expect(result[0]).toMatchObject({
      eventId: 'event-aapl-launch',
      symbol: 'AAPL',
      followedAt: '2026-07-20T10:00:00.000Z',
      publisher: 'Unit News',
    });
    expect(result[0].baseline).toMatchObject({
      observedAt: '2026-07-20T10:00:00.000Z',
      price: 100,
      volume: 2_000,
      source: 'unit_quote',
      status: 'fresh',
    });
    expect(loadFollowedMarketEvents('guest')).toEqual(result);
  });

  it('keeps storage scoped to guest or a numeric platform user id', () => {
    followMarketEvent(event, quote, 'user-72', () => '2026-07-20T10:00:00.000Z');

    expect(loadFollowedMarketEvents('guest')).toEqual([]);
    expect(loadFollowedMarketEvents('user-72')).toHaveLength(1);
    expect(marketEventFollowUpStorageKey('user-72')).toContain('user-72');
    expect(marketEventFollowUpStorageKey('panjun@example.com')).toBe(
      marketEventFollowUpStorageKey('guest'),
    );
    expect(localStorage.getItem(marketEventFollowUpStorageKey('user-72'))).not.toContain(
      'panjun@example.com',
    );
  });

  it('moves current guest follows into the signed-in user scope without leaking to another user', () => {
    followMarketEvent(event, quote, 'guest', () => '2026-07-20T10:00:00.000Z');

    const adopted = adoptGuestFollowedMarketEvents('user-72');

    expect(adopted).toHaveLength(1);
    expect(loadFollowedMarketEvents('guest')).toEqual([]);
    expect(loadFollowedMarketEvents('user-72')).toHaveLength(1);
    expect(loadFollowedMarketEvents('user-73')).toEqual([]);
  });

  it('records exact-symbol public quote observations and replaces the same UTC day', () => {
    followMarketEvent(event, quote, 'guest', () => '2026-07-20T10:00:00.000Z');
    const collision: MarketSecurityItem = {
      ...quote,
      symbol: 'AAP',
      currentPrice: 999,
    };

    recordFollowedMarketEventObservations(
      'guest',
      [{ ...quote, currentPrice: 102 }, collision],
      () => '2026-07-20T15:00:00.000Z',
    );
    const next = recordFollowedMarketEventObservations(
      'guest',
      [{ ...quote, currentPrice: 104 }],
      () => '2026-07-21T15:00:00.000Z',
    );

    expect(next[0].observations).toHaveLength(2);
    expect(next[0].observations.map((item) => item.price)).toEqual([102, 104]);
    expect(next[0].baseline?.price).toBe(100);
  });

  it('builds 1/3/5/20 day checkpoints without inventing missing observations', () => {
    const [followed] = followMarketEvent(
      event,
      quote,
      'guest',
      () => '2026-07-20T10:00:00.000Z',
    );
    followed.observations.push({
      ...followed.observations[0],
      observedAt: '2026-07-21T11:00:00.000Z',
      price: 103,
    });

    const checkpoints = buildFollowUpCheckpoints(
      followed,
      new Date('2026-07-24T10:00:00.000Z'),
    );

    expect(FOLLOW_UP_HORIZON_DAYS).toEqual([1, 3, 5, 20]);
    expect(checkpoints.map((item) => item.state)).toEqual([
      'observed',
      'unavailable',
      'pending',
      'pending',
    ]);
    expect(checkpoints[0].observation?.price).toBe(103);
    expect(checkpoints[1].observation).toBeUndefined();
  });

  it('finds only later public events for the exact followed security', () => {
    const [followed] = followMarketEvent(
      event,
      quote,
      'guest',
      () => '2026-07-20T10:00:00.000Z',
    );
    const publicEvents: PublicMarketEvent[] = [
      { ...event, eventId: 'later-2', title: 'Second follow-up', eventTime: '2026-07-22T09:00:00.000Z' },
      { ...event, eventId: 'later-1', title: 'First follow-up', eventTime: '2026-07-21T09:00:00.000Z' },
      { ...event, eventId: 'wrong-symbol', symbol: 'AAP', title: 'Wrong security', eventTime: '2026-07-23T09:00:00.000Z' },
      { ...event, eventId: 'older', title: 'Older update', eventTime: '2026-07-19T09:00:00.000Z' },
    ];

    expect(latestFollowUpEvents(followed, publicEvents).map((item) => item.eventId)).toEqual([
      'later-2',
      'later-1',
    ]);
  });

  it('removes one followed event and survives corrupted local data', () => {
    followMarketEvent(event, quote, 'guest', () => '2026-07-20T10:00:00.000Z');
    expect(unfollowMarketEvent('event-aapl-launch', 'guest')).toEqual([]);

    localStorage.setItem(marketEventFollowUpStorageKey('guest'), '{broken-json');
    expect(loadFollowedMarketEvents('guest')).toEqual([]);
  });
});
