import { beforeEach, describe, expect, it, vi } from 'vitest';
import apiClient from '../index';
import { marketWorkspaceApi } from '../marketWorkspace';

vi.mock('../index', () => ({
  default: { get: vi.fn() },
}));

describe('marketWorkspaceApi', () => {
  beforeEach(() => vi.mocked(apiClient.get).mockReset());

  it('maps snake_case overview fields to camelCase', async () => {
    vi.mocked(apiClient.get).mockResolvedValue({
      data: {
        market: 'us',
        as_of: '2026-07-12T09:30:00Z',
        session_state: 'open',
        session_phase: 'intraday',
        market_local_time: '2026-07-12T05:30:00-04:00',
        minutes_to_open: null,
        minutes_to_close: 390,
        session_source: 'exchange_calendar',
        session_warning_codes: [],
        indices: [],
        breadth: { advancers: 1, decliners: 0, unchanged: 0, unavailable: false },
        movers: [],
        heatmap: [],
        headlines: [],
        sources: [],
        warnings: [],
        cache: { hit: false, age_seconds: 0, ttl_seconds: 60 },
        ai_used: false,
        informational_only: true,
      },
    });

    const body = await marketWorkspaceApi.getOverview('us');

    expect(body.asOf).toBe('2026-07-12T09:30:00Z');
    expect(body.sessionPhase).toBe('intraday');
    expect(body.marketLocalTime).toBe('2026-07-12T05:30:00-04:00');
    expect(body.minutesToClose).toBe(390);
    expect(body.sessionSource).toBe('exchange_calendar');
    expect(body.cache.ttlSeconds).toBe(60);
    expect(apiClient.get).toHaveBeenCalledWith('/api/v1/market-workspace/overview', { params: { market: 'us' } });
  });

  it('loads the public three-market home contract as camelCase', async () => {
    vi.mocked(apiClient.get).mockResolvedValue({ data: {
      as_of: '2026-07-13T01:30:00Z', ai_used: false, informational_only: true,
      markets: [{ market: 'us', session_state: 'open', session_phase: 'intraday', market_local_time: '2026-07-13T10:30:00-04:00', minutes_to_close: 330, session_source: 'exchange_calendar', session_warning_codes: [], display_mode: 'latest_available', ranking_scope: 'configured_universe', selection_basis: 'turnover_then_absolute_change', indices: [], attention: [], sources: [], warnings: [] }],
      events: [{ event_id: 'event-1', market: 'us', category: 'earnings', title: 'AAPL earnings results', summary: 'Public information.', symbol: 'AAPL', name: 'Apple Inc.', event_time: '2026-07-13T01:25:00Z', time_kind: 'published', publisher: 'Unit News', url: 'https://example.com/event', source_state: { source: 'unit_news', status: 'fresh', observed_at: '2026-07-13T01:25:00Z' }, classification_source: 'keyword_rules' }],
    } });
    const body = await marketWorkspaceApi.getHome();
    expect(apiClient.get).toHaveBeenCalledWith('/api/v1/market-workspace/home');
    expect(body.asOf).toBe('2026-07-13T01:30:00Z');
    expect(body.markets[0].displayMode).toBe('latest_available');
    expect(body.markets[0].sessionPhase).toBe('intraday');
    expect(body.markets[0].minutesToClose).toBe(330);
    expect(body.events[0].eventId).toBe('event-1');
    expect(body.events[0].eventTime).toBe('2026-07-13T01:25:00Z');
    expect(body.events[0].sourceState.observedAt).toBe('2026-07-13T01:25:00Z');
  });

  it('defaults events for an older public-home response', async () => {
    vi.mocked(apiClient.get).mockResolvedValue({ data: {
      as_of: '2026-07-13T01:30:00Z',
      markets: [],
      ai_used: false,
      informational_only: true,
    } });

    const body = await marketWorkspaceApi.getHome();

    expect(body.events).toEqual([]);
  });

  it('defaults overview collection fields when an older cached response omits them', async () => {
    vi.mocked(apiClient.get).mockResolvedValue({
      data: {
        market: 'cn',
        as_of: '2026-07-12T09:30:00Z',
        session_state: 'unknown',
        cache: { hit: true, age_seconds: 10, ttl_seconds: 60 },
        ai_used: false,
        informational_only: true,
      },
    });

    const body = await marketWorkspaceApi.getOverview('cn');

    expect(body.indices).toEqual([]);
    expect(body.movers).toEqual([]);
    expect(body.heatmap).toEqual([]);
    expect(body.headlines).toEqual([]);
    expect(body.sources).toEqual([]);
    expect(body.warnings).toEqual([]);
    expect(body.breadth).toEqual({ advancers: 0, decliners: 0, unchanged: 0, unavailable: true });
  });

  it('defaults daily brief collections for an older signed-in response', async () => {
    vi.mocked(apiClient.get).mockResolvedValue({
      data: {
        user_id: 7,
        as_of: '2026-07-12T09:30:00Z',
        ai_used: false,
        informational_only: true,
      },
    });

    const body = await marketWorkspaceApi.getDailyBrief();

    expect(body.items).toEqual([]);
    expect(body.warnings).toEqual([]);
  });
});
