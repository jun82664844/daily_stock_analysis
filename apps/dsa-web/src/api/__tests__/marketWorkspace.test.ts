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
      events: [{ event_id: 'event-1', market: 'us', category: 'earnings', title: 'AAPL earnings results', summary: 'Public information.', symbol: 'AAPL', name: 'Apple Inc.', sector: 'Technology', event_time: '2026-07-13T01:25:00Z', time_kind: 'published', publisher: 'Unit News', url: 'https://example.com/event', source_state: { source: 'unit_news', status: 'fresh', observed_at: '2026-07-13T01:25:00Z' }, classification_source: 'keyword_rules', relevance_score: 95, importance: 'high', relevance_reasons: ['linked_security', 'earnings_event'], source_count: 2, source_publishers: ['Unit News', 'Official Feed'], source_records: [{ publisher: 'Unit News', source: 'unit_news', url: 'https://example.com/event', event_time: '2026-07-13T01:25:00Z', time_kind: 'published' }, { publisher: 'Official Feed', source: 'official_feed', url: 'https://official.example/event', event_time: '2026-07-13T01:26:00Z', time_kind: 'published' }] }],
    } });
    const body = await marketWorkspaceApi.getHome();
    expect(apiClient.get).toHaveBeenCalledWith('/api/v1/market-workspace/home');
    expect(body.asOf).toBe('2026-07-13T01:30:00Z');
    expect(body.markets[0].displayMode).toBe('latest_available');
    expect(body.markets[0].sessionPhase).toBe('intraday');
    expect(body.markets[0].minutesToClose).toBe(330);
    expect(body.events[0].eventId).toBe('event-1');
    expect(body.events[0].eventTime).toBe('2026-07-13T01:25:00Z');
    expect(body.events[0].sector).toBe('Technology');
    expect(body.events[0].sourceState.observedAt).toBe('2026-07-13T01:25:00Z');
    expect(body.events[0].relevanceScore).toBe(95);
    expect(body.events[0].importance).toBe('high');
    expect(body.events[0].relevanceReasons).toEqual(['linked_security', 'earnings_event']);
    expect(body.events[0].sourceCount).toBe(2);
    expect(body.events[0].sourcePublishers).toEqual(['Unit News', 'Official Feed']);
    expect(body.events[0].sourceRecords).toEqual([
      { publisher: 'Unit News', source: 'unit_news', url: 'https://example.com/event', eventTime: '2026-07-13T01:25:00Z', timeKind: 'published' },
      { publisher: 'Official Feed', source: 'official_feed', url: 'https://official.example/event', eventTime: '2026-07-13T01:26:00Z', timeKind: 'published' },
    ]);
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

  it('loads the public observed event-window contract without AI', async () => {
    vi.mocked(apiClient.get).mockResolvedValue({ data: {
      as_of: '2026-07-30T01:00:00Z',
      items: [{
        event_id: 'event-aapl',
        market: 'us',
        title: 'Apple earnings release',
        symbol: 'AAPL',
        name: 'Apple Inc.',
        subject_type: 'security',
        event_time: '2026-07-20T00:00:00Z',
        schedule_type: 'earnings_release',
        history_symbol: 'AAPL',
        baseline_date: '2026-07-17',
        benchmark_symbol: '^GSPC',
        benchmark_name: '标普500指数',
        status: 'partial',
        windows: [{
          trading_days: 1,
          status: 'available',
          observed_date: '2026-07-20',
          symbol_return_percent: 2,
          benchmark_return_percent: 1,
          relative_return_percent: 1,
          volume_ratio: 1.5,
        }],
        source_state: { source: 'yahoo_chart_public', status: 'fresh' },
        benchmark_source_state: { source: 'yahoo_chart_public', status: 'fresh' },
        warning_codes: ['observation_window_incomplete'],
      }],
      warnings: [],
      cache: { hit: false, age_seconds: 0, ttl_seconds: 900 },
      ai_used: false,
      informational_only: true,
    } });

    const body = await marketWorkspaceApi.getEventReactions();

    expect(apiClient.get).toHaveBeenCalledWith(
      '/api/v1/market-workspace/event-reactions',
      { withCredentials: false },
    );
    expect(body.items[0].eventId).toBe('event-aapl');
    expect(body.items[0].windows[0].tradingDays).toBe(1);
    expect(body.items[0].windows[0].relativeReturnPercent).toBe(1);
    expect(body.aiUsed).toBe(false);
  });

  it('does not mask a server-side V136 AI boundary regression', async () => {
    vi.mocked(apiClient.get).mockResolvedValue({ data: {
      as_of: '2026-07-30T00:00:00Z',
      items: [],
      warnings: [],
      cache: { hit: false, age_seconds: 0, ttl_seconds: 900 },
      ai_used: true,
      informational_only: true,
    } });

    const body = await marketWorkspaceApi.getEventReactions();

    expect(body.aiUsed).toBe(true);
  });

  it('defaults V127 relevance fields for an older event payload', async () => {
    vi.mocked(apiClient.get).mockResolvedValue({ data: {
      as_of: '2026-07-13T01:30:00Z',
      markets: [],
      events: [{
        event_id: 'legacy-event', market: 'cn', category: 'market', title: '市场成交保持活跃',
        event_time: '2026-07-13T01:25:00Z', time_kind: 'published',
        publisher: 'Legacy Publisher',
        url: 'javascript:alert(document.domain)',
        source_state: { source: 'unit_news', status: 'fresh' }, classification_source: 'keyword_rules',
      }],
      ai_used: false,
      informational_only: true,
    } });

    const body = await marketWorkspaceApi.getHome();

    expect(body.events[0].relevanceScore).toBe(0);
    expect(body.events[0].importance).toBe('low');
    expect(body.events[0].relevanceReasons).toEqual([]);
    expect(body.events[0].sourceCount).toBe(1);
    expect(body.events[0].sourcePublishers).toEqual(['Legacy Publisher']);
    expect(body.events[0].sector).toBeNull();
    expect(body.events[0].url).toBeNull();
    expect(body.events[0].sourceRecords).toEqual([{
      publisher: 'Legacy Publisher',
      source: 'unit_news',
      url: null,
      eventTime: '2026-07-13T01:25:00Z',
      timeKind: 'published',
    }]);
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
