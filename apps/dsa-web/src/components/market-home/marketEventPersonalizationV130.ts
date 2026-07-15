import type { MarketCode, PublicMarketEvent, PublicMarketHomeSection } from '../../api/marketWorkspace';

export type MarketEventMatch = 'watchlist' | 'sector' | 'market' | null;

export type PersonalizedMarketEvent = {
  event: PublicMarketEvent;
  match: MarketEventMatch;
};

export function normalizeMarketEventSymbol(value: string): string {
  const upper = String(value ?? '').trim().toUpperCase();
  const hk = upper.match(/^(?:HK)?0*(\d{1,5})(?:\.HK)?$/);
  if (hk && (upper.startsWith('HK') || upper.endsWith('.HK') || upper.length <= 5)) {
    return `HK:${Number(hk[1])}`;
  }
  const cn = upper.match(/^(?:(?:SH|SZ|BJ))?(\d{6})(?:\.(?:SH|SZ|SS|BJ))?$/);
  if (cn) return `CN:${cn[1]}`;
  return upper.replace(/\.US$/, '');
}

export function marketForWatchlistSymbol(value: string): MarketCode | null {
  const raw = String(value ?? '').trim().toUpperCase();
  if (/^[A-Z0-9]{2,12}-(?:USD|USDT|USDC|BTC|ETH)$/.test(raw)) return null;
  const normalized = normalizeMarketEventSymbol(value);
  if (normalized.startsWith('CN:')) return 'cn';
  if (normalized.startsWith('HK:')) return 'hk';
  return /^[A-Z][A-Z0-9.-]{0,9}$/.test(normalized) ? 'us' : null;
}

function normalizeSector(value?: string | null): string {
  return String(value ?? '').trim().toLocaleLowerCase();
}

function eventTimeValue(event: PublicMarketEvent): number {
  const value = new Date(event.eventTime).getTime();
  return Number.isFinite(value) ? value : 0;
}

export function personalizeMarketEvents(
  events: PublicMarketEvent[],
  watchlistSymbols: string[],
  watchlistSectors: string[],
  personalized: boolean,
): PersonalizedMarketEvent[] {
  const symbols = new Set(watchlistSymbols.map(normalizeMarketEventSymbol).filter(Boolean));
  const sectors = new Set(watchlistSectors.map(normalizeSector).filter(Boolean));
  const markets = new Set(watchlistSymbols.map(marketForWatchlistSymbol).filter((market): market is MarketCode => Boolean(market)));
  const priority: Record<Exclude<MarketEventMatch, null>, number> = { watchlist: 3, sector: 2, market: 1 };

  return events
    .map((event, index) => {
      const symbolMatch = Boolean(event.symbol && symbols.has(normalizeMarketEventSymbol(event.symbol)));
      const sectorMatch = Boolean(normalizeSector(event.sector) && sectors.has(normalizeSector(event.sector)));
      const marketMatch = markets.has(event.market);
      const match: MarketEventMatch = symbolMatch ? 'watchlist' : sectorMatch ? 'sector' : marketMatch ? 'market' : null;
      return { event, match, index };
    })
    .sort((left, right) => {
      if (personalized) {
        const priorityDifference = (right.match ? priority[right.match] : 0) - (left.match ? priority[left.match] : 0);
        if (priorityDifference !== 0) return priorityDifference;
      }
      if (left.event.relevanceScore !== right.event.relevanceScore) {
        return right.event.relevanceScore - left.event.relevanceScore;
      }
      const timeDifference = eventTimeValue(right.event) - eventTimeValue(left.event);
      if (timeDifference !== 0) return timeDifference;
      return left.index - right.index;
    })
    .map(({ event, match }) => ({ event, match }));
}

export function deriveWatchlistSectors(
  markets: PublicMarketHomeSection[],
  watchlistSymbols: string[],
): string[] {
  const symbols = new Set(watchlistSymbols.map(normalizeMarketEventSymbol).filter(Boolean));
  const sectors = new Set<string>();
  for (const market of markets) {
    const items = [
      ...(market.attention ?? []),
      ...(market.mostActive ?? []),
      ...(market.gainers ?? []),
      ...(market.losers ?? []),
    ];
    for (const item of items) {
      if (symbols.has(normalizeMarketEventSymbol(item.symbol)) && item.sector?.trim()) {
        sectors.add(item.sector.trim());
      }
    }
  }
  return Array.from(sectors);
}
