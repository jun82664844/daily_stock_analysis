import type {
  MarketCode,
  MarketEventCategory,
  MarketSecurityItem,
  PublicMarketEvent,
  SourceStatus,
} from '../../api/marketWorkspace';
import { normalizeMarketEventSymbol } from './marketEventPersonalizationV130';

export const MARKET_EVENT_FOLLOW_UP_STORAGE_PREFIX = 'dsa.marketEvents.followUp.v133';
export const MARKET_EVENT_FOLLOW_UP_CHANGED_EVENT = 'dsa:market-event-follow-up-v133';
export const FOLLOW_UP_HORIZON_DAYS = [1, 3, 5, 20] as const;

const MAX_FOLLOWED_EVENTS = 12;
const MAX_OBSERVATIONS = 32;
const DAY_MILLISECONDS = 24 * 60 * 60 * 1000;

export type MarketEventQuoteObservationV133 = {
  observedAt: string;
  price: number | null;
  changePercent: number | null;
  volume: number | null;
  turnover: number | null;
  source: string;
  status: SourceStatus;
  sourceObservedAt?: string | null;
};

export type FollowedMarketEventV133 = {
  eventId: string;
  market: MarketCode;
  category: MarketEventCategory;
  title: string;
  symbol: string;
  name: string;
  eventTime: string;
  publisher: string;
  followedAt: string;
  baseline: MarketEventQuoteObservationV133 | null;
  observations: MarketEventQuoteObservationV133[];
};

export type FollowUpCheckpointV133 = {
  days: (typeof FOLLOW_UP_HORIZON_DAYS)[number];
  targetAt: string;
  state: 'pending' | 'observed' | 'unavailable';
  observation?: MarketEventQuoteObservationV133;
};

type Clock = () => string;

function normalizeScope(scope: string): string {
  const value = String(scope ?? '').trim();
  return /^user-\d+$/.test(value) ? value : 'guest';
}

export function marketEventFollowUpStorageKey(scope: string): string {
  return `${MARKET_EVENT_FOLLOW_UP_STORAGE_PREFIX}.${normalizeScope(scope)}`;
}

function storage(): Storage | null {
  try {
    return typeof window === 'undefined' ? null : window.localStorage;
  } catch {
    return null;
  }
}

function finiteNumber(value: unknown): number | null {
  return typeof value === 'number' && Number.isFinite(value) ? value : null;
}

function validDate(value: unknown): value is string {
  return typeof value === 'string' && Number.isFinite(new Date(value).getTime());
}

function sanitizeObservation(value: unknown): MarketEventQuoteObservationV133 | null {
  if (!value || typeof value !== 'object') return null;
  const candidate = value as Partial<MarketEventQuoteObservationV133>;
  if (!validDate(candidate.observedAt) || typeof candidate.source !== 'string') return null;
  if (!['fresh', 'cached', 'stale', 'unavailable'].includes(String(candidate.status))) return null;
  return {
    observedAt: candidate.observedAt,
    price: finiteNumber(candidate.price),
    changePercent: finiteNumber(candidate.changePercent),
    volume: finiteNumber(candidate.volume),
    turnover: finiteNumber(candidate.turnover),
    source: candidate.source,
    status: candidate.status as SourceStatus,
    sourceObservedAt: validDate(candidate.sourceObservedAt) ? candidate.sourceObservedAt : null,
  };
}

function sanitizeFollowedEvent(value: unknown): FollowedMarketEventV133 | null {
  if (!value || typeof value !== 'object') return null;
  const candidate = value as Partial<FollowedMarketEventV133>;
  if (
    typeof candidate.eventId !== 'string'
    || typeof candidate.symbol !== 'string'
    || typeof candidate.title !== 'string'
    || typeof candidate.name !== 'string'
    || typeof candidate.publisher !== 'string'
    || !validDate(candidate.eventTime)
    || !validDate(candidate.followedAt)
    || !['cn', 'hk', 'us'].includes(String(candidate.market))
    || !['earnings', 'announcement', 'dividend', 'trading_status', 'macro', 'corporate', 'market'].includes(
      String(candidate.category),
    )
  ) {
    return null;
  }
  const observations = Array.isArray(candidate.observations)
    ? candidate.observations
      .map(sanitizeObservation)
      .filter((item): item is MarketEventQuoteObservationV133 => Boolean(item))
      .sort((left, right) => new Date(left.observedAt).getTime() - new Date(right.observedAt).getTime())
      .slice(-MAX_OBSERVATIONS)
    : [];
  return {
    eventId: candidate.eventId,
    market: candidate.market as MarketCode,
    category: candidate.category as MarketEventCategory,
    title: candidate.title,
    symbol: candidate.symbol,
    name: candidate.name,
    eventTime: candidate.eventTime,
    publisher: candidate.publisher,
    followedAt: candidate.followedAt,
    baseline: sanitizeObservation(candidate.baseline),
    observations,
  };
}

export function loadFollowedMarketEvents(scope: string): FollowedMarketEventV133[] {
  const store = storage();
  if (!store) return [];
  try {
    const parsed = JSON.parse(store.getItem(marketEventFollowUpStorageKey(scope)) ?? '[]');
    if (!Array.isArray(parsed)) return [];
    return parsed
      .map(sanitizeFollowedEvent)
      .filter((item): item is FollowedMarketEventV133 => Boolean(item))
      .slice(0, MAX_FOLLOWED_EVENTS);
  } catch {
    return [];
  }
}

function notifyChanged(scope: string): void {
  if (typeof window === 'undefined') return;
  window.dispatchEvent(
    new CustomEvent(MARKET_EVENT_FOLLOW_UP_CHANGED_EVENT, {
      detail: { scope: normalizeScope(scope) },
    }),
  );
}

function saveFollowedMarketEvents(
  scope: string,
  events: FollowedMarketEventV133[],
): FollowedMarketEventV133[] {
  const next = events.slice(0, MAX_FOLLOWED_EVENTS);
  try {
    storage()?.setItem(marketEventFollowUpStorageKey(scope), JSON.stringify(next));
  } catch {
    return next;
  }
  notifyChanged(scope);
  return next;
}

function observationFromQuote(
  quote: MarketSecurityItem,
  observedAt: string,
): MarketEventQuoteObservationV133 {
  return {
    observedAt,
    price: finiteNumber(quote.currentPrice),
    changePercent: finiteNumber(quote.changePercent),
    volume: finiteNumber(quote.volume),
    turnover: finiteNumber(quote.turnover),
    source: quote.sourceState.source,
    status: quote.sourceState.status,
    sourceObservedAt: validDate(quote.sourceState.observedAt) ? quote.sourceState.observedAt : null,
  };
}

function quoteForSymbol(
  symbol: string,
  quotes: MarketSecurityItem[],
): MarketSecurityItem | null {
  const normalized = normalizeMarketEventSymbol(symbol);
  return quotes.find((quote) => normalizeMarketEventSymbol(quote.symbol) === normalized) ?? null;
}

export function followMarketEvent(
  event: PublicMarketEvent,
  quote: MarketSecurityItem | null | undefined,
  scope: string,
  clock: Clock = () => new Date().toISOString(),
): FollowedMarketEventV133[] {
  if (!event.symbol?.trim()) return loadFollowedMarketEvents(scope);
  const followedAt = clock();
  const current = loadFollowedMarketEvents(scope);
  const existing = current.find((item) => item.eventId === event.eventId);
  const baseline = quote ? observationFromQuote(quote, followedAt) : null;
  const followed: FollowedMarketEventV133 = {
    eventId: event.eventId,
    market: event.market,
    category: event.category,
    title: event.title,
    symbol: event.symbol,
    name: event.name?.trim() || event.symbol,
    eventTime: event.eventTime,
    publisher: event.publisher?.trim() || event.sourceState.source,
    followedAt: existing?.followedAt ?? followedAt,
    baseline: existing?.baseline ?? baseline,
    observations: existing?.observations ?? (baseline ? [baseline] : []),
  };
  return saveFollowedMarketEvents(scope, [
    followed,
    ...current.filter((item) => item.eventId !== event.eventId),
  ]);
}

export function unfollowMarketEvent(
  eventId: string,
  scope: string,
): FollowedMarketEventV133[] {
  return saveFollowedMarketEvents(
    scope,
    loadFollowedMarketEvents(scope).filter((item) => item.eventId !== eventId),
  );
}

function utcDateKey(value: string): string {
  return new Date(value).toISOString().slice(0, 10);
}

export function recordFollowedMarketEventObservations(
  scope: string,
  quotes: MarketSecurityItem[],
  clock: Clock = () => new Date().toISOString(),
): FollowedMarketEventV133[] {
  const observedAt = clock();
  const dayKey = utcDateKey(observedAt);
  const next = loadFollowedMarketEvents(scope).map((followed) => {
    const quote = quoteForSymbol(followed.symbol, quotes);
    if (!quote) return followed;
    const observation = observationFromQuote(quote, observedAt);
    const observations = [...followed.observations];
    const sameDayIndex = observations.findIndex((item) => utcDateKey(item.observedAt) === dayKey);
    if (sameDayIndex >= 0) {
      observations[sameDayIndex] = observation;
    } else {
      observations.push(observation);
    }
    observations.sort(
      (left, right) => new Date(left.observedAt).getTime() - new Date(right.observedAt).getTime(),
    );
    return { ...followed, observations: observations.slice(-MAX_OBSERVATIONS) };
  });
  return saveFollowedMarketEvents(scope, next);
}

export function adoptGuestFollowedMarketEvents(scope: string): FollowedMarketEventV133[] {
  const normalizedScope = normalizeScope(scope);
  if (normalizedScope === 'guest') return loadFollowedMarketEvents('guest');
  const current = loadFollowedMarketEvents(normalizedScope);
  const guest = loadFollowedMarketEvents('guest');
  const knownIds = new Set(current.map((item) => item.eventId));
  const adopted = [
    ...current,
    ...guest.filter((item) => !knownIds.has(item.eventId)),
  ].slice(0, MAX_FOLLOWED_EVENTS);
  saveFollowedMarketEvents(normalizedScope, adopted);
  try {
    storage()?.removeItem(marketEventFollowUpStorageKey('guest'));
  } catch {
    return adopted;
  }
  notifyChanged('guest');
  return adopted;
}

export function buildFollowUpCheckpoints(
  followed: FollowedMarketEventV133,
  now: Date = new Date(),
): FollowUpCheckpointV133[] {
  const followedAt = new Date(followed.followedAt).getTime();
  const nowValue = now.getTime();
  return FOLLOW_UP_HORIZON_DAYS.map((days) => {
    const targetValue = followedAt + days * DAY_MILLISECONDS;
    const observation = followed.observations.find(
      (item) => {
        const observationTime = new Date(item.observedAt).getTime();
        return observationTime >= targetValue && observationTime <= nowValue;
      },
    );
    return {
      days,
      targetAt: new Date(targetValue).toISOString(),
      state: observation ? 'observed' : nowValue < targetValue ? 'pending' : 'unavailable',
      ...(observation ? { observation } : {}),
    };
  });
}

export function latestFollowUpEvents(
  followed: FollowedMarketEventV133,
  events: PublicMarketEvent[],
  limit = 3,
): PublicMarketEvent[] {
  const symbol = normalizeMarketEventSymbol(followed.symbol);
  const originalEventTime = new Date(followed.eventTime).getTime();
  return events
    .filter(
      (event) =>
        event.eventId !== followed.eventId
        && Boolean(event.symbol)
        && normalizeMarketEventSymbol(event.symbol ?? '') === symbol
        && new Date(event.eventTime).getTime() > originalEventTime,
    )
    .sort((left, right) => new Date(right.eventTime).getTime() - new Date(left.eventTime).getTime())
    .slice(0, Math.max(0, limit));
}
