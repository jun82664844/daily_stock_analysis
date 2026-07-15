import { describe, expect, it } from 'vitest';
import type { PublicMarketEvent, PublicMarketHomeSection } from '../../../api/marketWorkspace';
import {
  deriveWatchlistSectors,
  marketForWatchlistSymbol,
  normalizeMarketEventSymbol,
  personalizeMarketEvents,
} from '../marketEventPersonalizationV130';

const sourceState = { source: 'unit_public', status: 'fresh' as const };

function event(eventId: string, market: 'cn' | 'hk' | 'us', relevanceScore: number, extras: Partial<PublicMarketEvent> = {}): PublicMarketEvent {
  return {
    eventId,
    market,
    category: 'market',
    title: eventId,
    eventTime: '2026-07-15T01:00:00Z',
    timeKind: 'published',
    sourceState,
    classificationSource: 'keyword_rules',
    relevanceScore,
    importance: 'medium',
    relevanceReasons: ['market_signal'],
    sourceCount: 1,
    sourcePublishers: ['Unit'],
    sourceRecords: [],
    ...extras,
  };
}

describe('marketEventPersonalizationV130', () => {
  it('normalizes three equity markets but does not treat crypto as US equity', () => {
    expect(normalizeMarketEventSymbol('SH600519')).toBe('CN:600519');
    expect(normalizeMarketEventSymbol('HK00700')).toBe('HK:700');
    expect(normalizeMarketEventSymbol('AAPL.US')).toBe('AAPL');
    expect(marketForWatchlistSymbol('600519.SH')).toBe('cn');
    expect(marketForWatchlistSymbol('0700.HK')).toBe('hk');
    expect(marketForWatchlistSymbol('AAPL')).toBe('us');
    expect(marketForWatchlistSymbol('BTC-USD')).toBeNull();
  });

  it('uses watchlist, sector and market matches before general relevance', () => {
    const ranked = personalizeMarketEvents([
      event('general', 'cn', 99),
      event('market', 'us', 80),
      event('sector', 'us', 70, { sector: 'Technology' }),
      event('watchlist', 'us', 10, { symbol: 'AAPL' }),
    ], ['AAPL'], ['Technology'], true);

    expect(ranked.map((item) => [item.event.eventId, item.match])).toEqual([
      ['watchlist', 'watchlist'],
      ['sector', 'sector'],
      ['market', 'market'],
      ['general', null],
    ]);
  });

  it('derives watchlist sectors only from already loaded public market items', () => {
    const markets = [{
      market: 'us',
      sessionState: 'open',
      displayMode: 'latest_available',
      rankingScope: 'market_wide',
      selectionBasis: 'public',
      indices: [],
      attention: [{ symbol: 'AAPL', name: 'Apple', market: 'us', sector: 'Technology', sourceState }],
      mostActive: [],
      gainers: [],
      losers: [],
      sources: [],
      warnings: [],
    }] as PublicMarketHomeSection[];

    expect(deriveWatchlistSectors(markets, ['AAPL'])).toEqual(['Technology']);
    expect(deriveWatchlistSectors(markets, ['MSFT'])).toEqual([]);
  });
});
