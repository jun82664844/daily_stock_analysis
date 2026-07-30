import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { PublicMarketEvent } from '../../../api/marketWorkspace';
import type { FollowedMarketEventV133 } from '../marketEventFollowUpV133';
import {
  acknowledgeCalendarEntries,
  adoptGuestCalendarAcknowledgements,
  buildMarketEventCalendarV134,
  extractExplicitScheduleAt,
  loadCalendarAcknowledgements,
  marketEventCalendarStorageKey,
  unseenDueCalendarEntryIds,
} from '../marketEventCalendarV134';

const baseEvent: PublicMarketEvent = {
  eventId: 'event-aapl',
  market: 'us',
  category: 'earnings',
  title: 'Apple publishes an operating update',
  summary: 'Public company information.',
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
  baseline: {
    observedAt: '2026-07-29T00:00:00.000Z',
    price: 100,
    changePercent: 0,
    volume: 1_000,
    turnover: 100_000,
    source: 'unit_quote',
    status: 'fresh',
    sourceObservedAt: '2026-07-29T00:00:00.000Z',
  },
  observations: [],
};

describe('marketEventCalendarV134', () => {
  beforeEach(() => {
    localStorage.clear();
    vi.restoreAllMocks();
  });

  it('extracts only explicit ISO, Chinese, or English schedule dates', () => {
    const reference = new Date('2026-07-30T12:00:00.000Z');

    expect(extractExplicitScheduleAt(
      { ...baseEvent, title: 'Apple plans earnings on 2026-08-02' },
      reference,
    )).toBe('2026-08-02T00:00:00.000Z');
    expect(extractExplicitScheduleAt(
      { ...baseEvent, title: '贵州茅台将于8月3日披露半年报' },
      reference,
    )).toBe('2026-08-03T00:00:00.000Z');
    expect(extractExplicitScheduleAt(
      { ...baseEvent, title: 'Apple reports August 4, 2026' },
      reference,
    )).toBe('2026-08-04T00:00:00.000Z');
    expect(extractExplicitScheduleAt(
      { ...baseEvent, title: 'Apple price reaches 1188 with volume rising' },
      reference,
    )).toBeNull();
    expect(extractExplicitScheduleAt(
      { ...baseEvent, title: 'Apple reports on 2026-02-30' },
      reference,
    )).toBeNull();
  });

  it('builds three-market public entries and 1/3/5/20 day follow-up checkpoints', () => {
    const events: PublicMarketEvent[] = [
      { ...baseEvent, eventId: 'us-scheduled', title: 'Apple reports on 2026-08-02' },
      {
        ...baseEvent,
        eventId: 'cn-published',
        market: 'cn',
        symbol: '600519.SH',
        name: '贵州茅台',
        title: '贵州茅台发布公告',
      },
      {
        ...baseEvent,
        eventId: 'hk-published',
        market: 'hk',
        symbol: '0700.HK',
        name: '腾讯控股',
        title: '腾讯控股发布公告',
      },
    ];

    const entries = buildMarketEventCalendarV134(
      events,
      [followedEvent],
      ['AAPL'],
      new Date('2026-07-30T12:00:00.000Z'),
    );

    expect(new Set(entries.map((entry) => entry.market))).toEqual(new Set(['cn', 'hk', 'us']));
    expect(entries).toEqual(expect.arrayContaining([
      expect.objectContaining({
        id: 'event:us-scheduled',
        dateBasis: 'explicit_schedule',
        state: 'upcoming',
        personalized: true,
      }),
      expect.objectContaining({
        id: 'event:cn-published',
        dateBasis: 'published',
        state: 'today',
      }),
      expect.objectContaining({
        id: 'checkpoint:follow-aapl:1',
        dateBasis: 'follow_up_checkpoint',
        state: 'due',
        checkpointDays: 1,
      }),
      expect.objectContaining({
        id: 'checkpoint:follow-aapl:3',
        state: 'upcoming',
        checkpointDays: 3,
      }),
    ]));
  });

  it('keeps only the seven-day history and thirty-day future window', () => {
    const entries = buildMarketEventCalendarV134(
      [
        { ...baseEvent, eventId: 'too-old', eventTime: '2026-07-20T08:00:00.000Z' },
        { ...baseEvent, eventId: 'recent', eventTime: '2026-07-29T08:00:00.000Z' },
        { ...baseEvent, eventId: 'too-far', title: 'Apple reports on 2026-09-15' },
      ],
      [],
      [],
      new Date('2026-07-30T12:00:00.000Z'),
    );

    expect(entries.map((entry) => entry.id)).toEqual(['event:recent']);
  });

  it('matches personalized symbols exactly instead of using substrings or cross-exchange codes', () => {
    const entries = buildMarketEventCalendarV134(
      [
        { ...baseEvent, eventId: 'aapl', symbol: 'AAPL' },
        { ...baseEvent, eventId: 'aap', symbol: 'AAP' },
        { ...baseEvent, eventId: 'sz-index', market: 'cn', symbol: '000001.SH' },
        { ...baseEvent, eventId: 'sz-stock', market: 'cn', symbol: '000001.SZ' },
      ],
      [],
      ['AAPL', '000001.SZ'],
      new Date('2026-07-30T12:00:00.000Z'),
    );

    const personalized = entries.filter((entry) => entry.personalized).map((entry) => entry.id);
    expect(personalized).toEqual(expect.arrayContaining(['event:aapl', 'event:sz-stock']));
    expect(personalized).not.toContain('event:aap');
    expect(personalized).not.toContain('event:sz-index');
  });

  it('tracks unseen due reminders and caps acknowledgement storage', () => {
    const entries = buildMarketEventCalendarV134(
      [],
      [followedEvent],
      [],
      new Date('2026-07-30T12:00:00.000Z'),
    );
    const dueId = 'checkpoint:follow-aapl:1';

    expect(unseenDueCalendarEntryIds(entries, [])).toEqual([dueId]);
    expect(acknowledgeCalendarEntries('guest', [dueId])).toContain(dueId);
    expect(unseenDueCalendarEntryIds(entries, loadCalendarAcknowledgements('guest'))).toEqual([]);

    acknowledgeCalendarEntries(
      'guest',
      Array.from({ length: 140 }, (_, index) => `entry-${index}`),
    );
    expect(loadCalendarAcknowledgements('guest')).toHaveLength(128);
  });

  it('moves guest acknowledgement state only into a numeric signed-in scope', () => {
    acknowledgeCalendarEntries('guest', ['checkpoint:follow-aapl:1']);

    expect(adoptGuestCalendarAcknowledgements('user-72')).toContain('checkpoint:follow-aapl:1');
    expect(loadCalendarAcknowledgements('guest')).toEqual([]);
    expect(loadCalendarAcknowledgements('user-72')).toContain('checkpoint:follow-aapl:1');
    expect(loadCalendarAcknowledgements('user-73')).toEqual([]);
    expect(marketEventCalendarStorageKey('panjun@example.com')).toBe(
      marketEventCalendarStorageKey('guest'),
    );
  });

  it('survives corrupted local acknowledgement data', () => {
    localStorage.setItem(marketEventCalendarStorageKey('guest'), '{broken-json');
    expect(loadCalendarAcknowledgements('guest')).toEqual([]);
  });
});
