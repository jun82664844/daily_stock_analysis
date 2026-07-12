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
    expect(body.cache.ttlSeconds).toBe(60);
    expect(apiClient.get).toHaveBeenCalledWith('/api/v1/market-workspace/overview', { params: { market: 'us' } });
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
