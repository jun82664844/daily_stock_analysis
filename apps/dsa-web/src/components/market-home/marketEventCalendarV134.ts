import type {
  MarketCode,
  PublicMarketEvent,
  SourceStatus,
} from '../../api/marketWorkspace';
import { normalizeMarketEventSymbol } from './marketEventPersonalizationV130';
import {
  buildFollowUpCheckpoints,
  type FollowedMarketEventV133,
} from './marketEventFollowUpV133';

export const MARKET_EVENT_CALENDAR_STORAGE_PREFIX = 'dsa.marketEvents.calendar.v134';
export const MARKET_EVENT_CALENDAR_CHANGED_EVENT = 'dsa:market-event-calendar-v134';
export const CALENDAR_PAST_DAYS = 7;
export const CALENDAR_FUTURE_DAYS = 30;
export const MAX_MARKET_CALENDAR_ENTRIES = 48;
export const MAX_CALENDAR_ACKNOWLEDGEMENTS = 128;

const DAY_MILLISECONDS = 24 * 60 * 60 * 1000;
const ENGLISH_MONTHS: Record<string, number> = {
  january: 1,
  jan: 1,
  february: 2,
  feb: 2,
  march: 3,
  mar: 3,
  april: 4,
  apr: 4,
  may: 5,
  june: 6,
  jun: 6,
  july: 7,
  jul: 7,
  august: 8,
  aug: 8,
  september: 9,
  sep: 9,
  sept: 9,
  october: 10,
  oct: 10,
  november: 11,
  nov: 11,
  december: 12,
  dec: 12,
};

export type MarketEventCalendarEntryV134 = {
  id: string;
  kind: 'public_event' | 'follow_up';
  dateBasis: 'explicit_schedule' | 'published' | 'follow_up_checkpoint';
  state: 'recent' | 'today' | 'upcoming' | 'due' | 'completed';
  scheduledAt: string;
  market: MarketCode;
  symbol: string | null;
  title: string;
  name: string | null;
  personalized: boolean;
  sourceStatus: SourceStatus;
  publisher: string;
  scheduleType?: 'earnings_release' | 'ex_dividend' | 'macro_policy';
  checkpointDays?: 1 | 3 | 5 | 20;
};

function normalizedScope(scope: string): string {
  const candidate = String(scope ?? '').trim();
  return /^user-\d+$/.test(candidate) ? candidate : 'guest';
}

export function marketEventCalendarStorageKey(scope: string): string {
  return `${MARKET_EVENT_CALENDAR_STORAGE_PREFIX}.${normalizedScope(scope)}`;
}

function localStore(): Storage | null {
  try {
    return typeof window === 'undefined' ? null : window.localStorage;
  } catch {
    return null;
  }
}

function validUtcDate(year: number, month: number, day: number): string | null {
  if (
    !Number.isInteger(year)
    || !Number.isInteger(month)
    || !Number.isInteger(day)
    || year < 2000
    || year > 2100
    || month < 1
    || month > 12
    || day < 1
    || day > 31
  ) {
    return null;
  }
  const candidate = new Date(Date.UTC(year, month - 1, day));
  if (
    candidate.getUTCFullYear() !== year
    || candidate.getUTCMonth() !== month - 1
    || candidate.getUTCDate() !== day
  ) {
    return null;
  }
  return candidate.toISOString();
}

function inferredYearDate(month: number, day: number, reference: Date): string | null {
  const referenceValue = reference.getTime();
  let year = reference.getUTCFullYear();
  let result = validUtcDate(year, month, day);
  if (!result) return null;
  if (new Date(result).getTime() < referenceValue - 120 * DAY_MILLISECONDS) {
    year += 1;
    result = validUtcDate(year, month, day);
  }
  return result;
}

export function extractExplicitScheduleAt(
  event: PublicMarketEvent,
  reference: Date = new Date(event.eventTime),
): string | null {
  const text = `${event.title}\n${event.summary ?? ''}`;
  const iso = text.match(/\b(20\d{2})[-/.](\d{1,2})[-/.](\d{1,2})\b/);
  if (iso) {
    return validUtcDate(Number(iso[1]), Number(iso[2]), Number(iso[3]));
  }

  const chinese = text.match(/(?<!\d)(\d{1,2})月(\d{1,2})日/);
  if (chinese) {
    return inferredYearDate(Number(chinese[1]), Number(chinese[2]), reference);
  }

  const english = text.match(
    /\b(January|Jan|February|Feb|March|Mar|April|Apr|May|June|Jun|July|Jul|August|Aug|September|Sept|Sep|October|Oct|November|Nov|December|Dec)\s+(\d{1,2})(?:,\s*(20\d{2}))?\b/i,
  );
  if (!english) return null;
  const month = ENGLISH_MONTHS[english[1].toLowerCase()];
  const year = english[3] ? Number(english[3]) : null;
  return year
    ? validUtcDate(year, month, Number(english[2]))
    : inferredYearDate(month, Number(english[2]), reference);
}

function sameUtcDay(left: number, right: number): boolean {
  return new Date(left).toISOString().slice(0, 10) === new Date(right).toISOString().slice(0, 10);
}

function publicEventState(scheduledAt: number, now: number): MarketEventCalendarEntryV134['state'] {
  if (sameUtcDay(scheduledAt, now)) return 'today';
  return scheduledAt > now ? 'upcoming' : 'recent';
}

function calendarSymbolKey(value: string): string {
  const raw = String(value ?? '').trim().toUpperCase();
  const cn = raw.match(/^(?:(SH|SZ|BJ))?(\d{6})(?:\.(SH|SZ|SS|BJ))?$/);
  if (cn) {
    const exchange = (cn[1] || cn[3] || 'UNKNOWN').replace('SS', 'SH');
    return `CN:${cn[2]}:${exchange}`;
  }
  return normalizeMarketEventSymbol(raw);
}

function publicEventEntry(
  event: PublicMarketEvent,
  watchlist: Set<string>,
  now: Date,
): MarketEventCalendarEntryV134 {
  const providerSchedule = event.timeKind === 'scheduled' ? event.eventTime : null;
  const explicitSchedule = providerSchedule
    ?? extractExplicitScheduleAt(event, new Date(event.eventTime));
  const scheduledAt = explicitSchedule ?? event.eventTime;
  const normalizedSymbol = calendarSymbolKey(event.symbol ?? '');
  return {
    id: `event:${event.eventId}`,
    kind: 'public_event',
    dateBasis: explicitSchedule ? 'explicit_schedule' : 'published',
    state: publicEventState(new Date(scheduledAt).getTime(), now.getTime()),
    scheduledAt,
    market: event.market,
    symbol: event.symbol?.trim() || null,
    title: event.title,
    name: event.name?.trim() || null,
    personalized: Boolean(normalizedSymbol && watchlist.has(normalizedSymbol)),
    sourceStatus: event.sourceState.status,
    publisher: event.publisher?.trim() || event.sourceState.source,
    scheduleType: event.scheduleType ?? undefined,
  };
}

function followUpEntries(
  followed: FollowedMarketEventV133,
  now: Date,
): MarketEventCalendarEntryV134[] {
  return buildFollowUpCheckpoints(followed, now).map((checkpoint) => ({
    id: `checkpoint:${followed.eventId}:${checkpoint.days}`,
    kind: 'follow_up' as const,
    dateBasis: 'follow_up_checkpoint' as const,
    state: checkpoint.state === 'observed'
      ? 'completed' as const
      : checkpoint.state === 'unavailable'
        ? 'due' as const
        : sameUtcDay(new Date(checkpoint.targetAt).getTime(), now.getTime())
          ? 'today' as const
          : 'upcoming' as const,
    scheduledAt: checkpoint.targetAt,
    market: followed.market,
    symbol: followed.symbol,
    title: followed.title,
    name: followed.name,
    personalized: true,
    sourceStatus: checkpoint.observation?.status ?? followed.baseline?.status ?? 'unavailable',
    publisher: followed.publisher,
    checkpointDays: checkpoint.days,
  }));
}

const STATE_ORDER: Record<MarketEventCalendarEntryV134['state'], number> = {
  due: 0,
  today: 1,
  upcoming: 2,
  recent: 3,
  completed: 4,
};

export function buildMarketEventCalendarV134(
  events: PublicMarketEvent[],
  followedEvents: FollowedMarketEventV133[],
  watchlistSymbols: string[],
  now: Date = new Date(),
): MarketEventCalendarEntryV134[] {
  const nowValue = now.getTime();
  const earliest = nowValue - CALENDAR_PAST_DAYS * DAY_MILLISECONDS;
  const latest = nowValue + CALENDAR_FUTURE_DAYS * DAY_MILLISECONDS;
  const watchlist = new Set(
    watchlistSymbols
      .map(calendarSymbolKey)
      .filter(Boolean),
  );
  const entries = [
    ...events.map((event) => publicEventEntry(event, watchlist, now)),
    ...followedEvents.flatMap((followed) => followUpEntries(followed, now)),
  ].filter((entry) => {
    const value = new Date(entry.scheduledAt).getTime();
    return Number.isFinite(value) && value >= earliest && value <= latest;
  });

  entries.sort((left, right) => {
    const stateDifference = STATE_ORDER[left.state] - STATE_ORDER[right.state];
    if (stateDifference !== 0) return stateDifference;
    if (left.personalized !== right.personalized) return left.personalized ? -1 : 1;
    return new Date(left.scheduledAt).getTime() - new Date(right.scheduledAt).getTime();
  });
  return entries.slice(0, MAX_MARKET_CALENDAR_ENTRIES);
}

export function loadCalendarAcknowledgements(scope: string): string[] {
  const store = localStore();
  if (!store) return [];
  try {
    const parsed = JSON.parse(store.getItem(marketEventCalendarStorageKey(scope)) ?? '[]');
    if (!Array.isArray(parsed)) return [];
    return Array.from(new Set(
      parsed
        .filter((item): item is string => typeof item === 'string' && item.length > 0)
        .slice(-MAX_CALENDAR_ACKNOWLEDGEMENTS),
    ));
  } catch {
    return [];
  }
}

function saveCalendarAcknowledgements(scope: string, entryIds: string[]): string[] {
  const normalized = Array.from(new Set(
    entryIds.filter((entryId) => typeof entryId === 'string' && entryId.length > 0),
  )).slice(-MAX_CALENDAR_ACKNOWLEDGEMENTS);
  try {
    localStore()?.setItem(marketEventCalendarStorageKey(scope), JSON.stringify(normalized));
  } catch {
    return normalized;
  }
  if (typeof window !== 'undefined') {
    window.dispatchEvent(new CustomEvent(MARKET_EVENT_CALENDAR_CHANGED_EVENT, {
      detail: { scope: normalizedScope(scope) },
    }));
  }
  return normalized;
}

export function acknowledgeCalendarEntries(scope: string, entryIds: string[]): string[] {
  return saveCalendarAcknowledgements(scope, [
    ...loadCalendarAcknowledgements(scope),
    ...entryIds,
  ]);
}

export function adoptGuestCalendarAcknowledgements(scope: string): string[] {
  const targetScope = normalizedScope(scope);
  if (targetScope === 'guest') return loadCalendarAcknowledgements('guest');
  const adopted = saveCalendarAcknowledgements(targetScope, [
    ...loadCalendarAcknowledgements(targetScope),
    ...loadCalendarAcknowledgements('guest'),
  ]);
  try {
    localStore()?.removeItem(marketEventCalendarStorageKey('guest'));
  } catch {
    return adopted;
  }
  if (typeof window !== 'undefined') {
    window.dispatchEvent(new CustomEvent(MARKET_EVENT_CALENDAR_CHANGED_EVENT, {
      detail: { scope: 'guest' },
    }));
  }
  return adopted;
}

export function unseenDueCalendarEntryIds(
  entries: MarketEventCalendarEntryV134[],
  acknowledgedEntryIds: string[],
): string[] {
  const acknowledged = new Set(acknowledgedEntryIds);
  return entries
    .filter((entry) => entry.state === 'due' && !acknowledged.has(entry.id))
    .map((entry) => entry.id);
}
