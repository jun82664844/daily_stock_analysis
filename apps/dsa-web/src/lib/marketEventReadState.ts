export const MARKET_EVENT_SEEN_STORAGE_KEY = 'dsa.marketEvents.seen.v1';

const MAX_SEEN_EVENT_IDS = 200;

type EventStorage = Pick<Storage, 'getItem' | 'setItem'>;

function resolveStorage(storage?: EventStorage | null): EventStorage | null {
  if (storage !== undefined) return storage;
  try {
    return typeof window === 'undefined' ? null : window.localStorage;
  } catch {
    return null;
  }
}

function normalizeEventIds(values: unknown[]): string[] {
  const result: string[] = [];
  const seen = new Set<string>();
  for (const value of values) {
    const eventId = typeof value === 'string' ? value.trim() : '';
    if (!eventId || seen.has(eventId)) continue;
    seen.add(eventId);
    result.push(eventId);
    if (result.length >= MAX_SEEN_EVENT_IDS) break;
  }
  return result;
}

export function loadSeenMarketEventIds(storage?: EventStorage | null): string[] | null {
  const target = resolveStorage(storage);
  if (!target) return null;
  try {
    const raw = target.getItem(MARKET_EVENT_SEEN_STORAGE_KEY);
    if (raw === null) return null;
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? normalizeEventIds(parsed) : null;
  } catch {
    return null;
  }
}

export function saveSeenMarketEventIds(
  eventIds: string[],
  storage?: EventStorage | null,
): string[] {
  const normalized = normalizeEventIds(eventIds);
  const target = resolveStorage(storage);
  if (!target) return normalized;
  try {
    target.setItem(MARKET_EVENT_SEEN_STORAGE_KEY, JSON.stringify(normalized));
  } catch {
    // Browser privacy modes may deny storage; the event center remains usable.
  }
  return normalized;
}

export function mergeSeenMarketEventIds(seenEventIds: string[], currentEventIds: string[]): string[] {
  return normalizeEventIds([...currentEventIds, ...seenEventIds]);
}

export function getUnseenMarketEventIds(
  currentEventIds: string[],
  seenEventIds: string[] | null,
): string[] {
  if (seenEventIds === null) return [];
  const seen = new Set(seenEventIds);
  return normalizeEventIds(currentEventIds).filter((eventId) => !seen.has(eventId));
}
