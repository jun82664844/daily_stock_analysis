import type { MarketCode, MarketSecurityItem } from '../../api/marketWorkspace';

const STORAGE_KEY = 'dsa.public-market.recent-symbols.v124';
const MAX_ITEMS = 6;

export const RECENT_MARKET_SYMBOLS_EVENT = 'dsa:recent-market-symbols-v124';

export type RecentMarketSymbolV124 = {
  symbol: string;
  name: string;
  market: MarketCode;
  viewedAt: string;
};

type RecentMarketSymbolInput = Pick<MarketSecurityItem, 'symbol' | 'name' | 'market'>;

function storageAvailable(): boolean {
  return typeof window !== 'undefined' && Boolean(window.localStorage);
}

function cleanItem(value: unknown): RecentMarketSymbolV124 | null {
  if (!value || typeof value !== 'object') return null;
  const item = value as Record<string, unknown>;
  const symbol = typeof item.symbol === 'string' ? item.symbol.trim().toUpperCase() : '';
  const name = typeof item.name === 'string' ? item.name.trim() : '';
  const market = item.market;
  const viewedAt = typeof item.viewedAt === 'string' ? item.viewedAt.trim() : '';
  if (!symbol || !name || !viewedAt || (market !== 'cn' && market !== 'hk' && market !== 'us')) return null;
  return { symbol, name, market, viewedAt };
}

export function readRecentMarketSymbols(): RecentMarketSymbolV124[] {
  if (!storageAvailable()) return [];
  try {
    const parsed = JSON.parse(window.localStorage.getItem(STORAGE_KEY) || '[]');
    if (!Array.isArray(parsed)) return [];
    return parsed.map(cleanItem).filter((item): item is RecentMarketSymbolV124 => Boolean(item)).slice(0, MAX_ITEMS);
  } catch {
    return [];
  }
}

export function rememberRecentMarketSymbol(
  input: RecentMarketSymbolInput,
  clock: () => string = () => new Date().toISOString(),
): RecentMarketSymbolV124[] {
  if (!storageAvailable()) return [];
  const symbol = input.symbol.trim().toUpperCase();
  const name = input.name.trim() || symbol;
  if (!symbol || (input.market !== 'cn' && input.market !== 'hk' && input.market !== 'us')) {
    return readRecentMarketSymbols();
  }
  const next = [
    { symbol, name, market: input.market, viewedAt: clock() },
    ...readRecentMarketSymbols().filter((item) => item.symbol !== symbol),
  ].slice(0, MAX_ITEMS);
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
  window.dispatchEvent(new CustomEvent(RECENT_MARKET_SYMBOLS_EVENT));
  return next;
}

export function clearRecentMarketSymbols(): void {
  if (!storageAvailable()) return;
  window.localStorage.removeItem(STORAGE_KEY);
  window.dispatchEvent(new CustomEvent(RECENT_MARKET_SYMBOLS_EVENT));
}
