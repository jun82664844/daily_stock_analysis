import { beforeEach, describe, expect, it } from 'vitest';
import {
  MARKET_EVENT_SEEN_STORAGE_KEY,
  getUnseenMarketEventIds,
  loadSeenMarketEventIds,
  mergeSeenMarketEventIds,
  saveSeenMarketEventIds,
} from '../marketEventReadState';

describe('marketEventReadState', () => {
  beforeEach(() => localStorage.clear());

  it('returns null when the visitor has no baseline yet', () => {
    expect(loadSeenMarketEventIds()).toBeNull();
    expect(getUnseenMarketEventIds(['event-1'], null)).toEqual([]);
  });

  it('treats damaged storage as a missing baseline', () => {
    localStorage.setItem(MARKET_EVENT_SEEN_STORAGE_KEY, '{not-json');

    expect(loadSeenMarketEventIds()).toBeNull();
  });

  it('deduplicates ids and keeps at most 200 recent values', () => {
    const ids = Array.from({ length: 205 }, (_, index) => `event-${index}`);

    const saved = saveSeenMarketEventIds(['event-0', ...ids, '  ', 'event-2']);

    expect(saved).toHaveLength(200);
    expect(new Set(saved).size).toBe(200);
    expect(loadSeenMarketEventIds()).toEqual(saved);
  });

  it('merges current ids first and reports only unseen events', () => {
    const merged = mergeSeenMarketEventIds(['old-1', 'old-2'], ['new-1', 'old-2']);

    expect(merged.slice(0, 3)).toEqual(['new-1', 'old-2', 'old-1']);
    expect(getUnseenMarketEventIds(['new-1', 'old-2'], ['old-1', 'old-2'])).toEqual(['new-1']);
  });
});
