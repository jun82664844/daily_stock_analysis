import { describe, expect, it } from 'vitest';
import type { BasicStockSnapshot } from '../../../api/stocks';
import {
  buildQueryObservation,
  compareQueryObservations,
  readPriorQueryObservation,
  storeQueryObservation,
} from '../queryChangeTracker';

const snapshot = (overrides: Partial<BasicStockSnapshot> = {}): BasicStockSnapshot => ({
  stockCode: 'AAPL',
  stockName: 'Apple Inc.',
  market: 'us',
  quote: {
    currentPrice: 200,
    changePercent: 1.5,
    source: 'unit_quote',
    freshness: 'fresh',
    updateTime: '2026-07-10T09:30:00Z',
  },
  indicators: {
    ma5: 198,
    ma20: 190,
    volumePriceSignal: 'price_volume_confirmed',
  },
  intelligence: {
    mode: 'no_ai_low_cost',
    aiUsed: false,
    signalScore: {
      score: 64,
      label: 'positive',
      summary: 'unit',
      components: [],
      source: 'unit',
    },
    items: [],
  },
  warnings: [],
  aiUsed: false,
  ...overrides,
});

describe('queryChangeTracker', () => {
  it('creates a first-observation summary when no prior query exists', () => {
    const current = buildQueryObservation(snapshot(), '2026-07-10T10:00:00Z');
    expect(compareQueryObservations(null, current).kind).toBe('first');
  });

  it('reports unchanged when the same observation is queried again', () => {
    const current = buildQueryObservation(snapshot(), '2026-07-10T10:00:00Z');
    expect(compareQueryObservations(current, current).kind).toBe('unchanged');
  });

  it('detects useful price, score, freshness, and trend-position changes', () => {
    const previous = buildQueryObservation(snapshot(), '2026-07-10T10:00:00Z');
    const current = buildQueryObservation(snapshot({
      quote: {
        currentPrice: 205,
        changePercent: 2.4,
        source: 'unit_quote',
        freshness: 'stale',
        updateTime: '2026-07-10T11:00:00Z',
      },
      indicators: { ma5: 202, ma20: 206, volumePriceSignal: 'neutral' },
      intelligence: {
        mode: 'no_ai_low_cost',
        aiUsed: false,
        signalScore: { score: 51, label: 'neutral', summary: 'unit', components: [], source: 'unit' },
        items: [],
      },
      warnings: [{ code: 'quote_stale', severity: 'warning', message: 'stale' }],
    }), '2026-07-10T11:00:00Z');

    const result = compareQueryObservations(previous, current);
    expect(result.kind).toBe('changed');
    expect(result.priceDelta).toBe(5);
    expect(result.signalScoreDelta).toBe(-13);
    expect(result.freshnessChanged).toBe(true);
    expect(result.trendPositionChanged).toBe(true);
    expect(result.warningCountDelta).toBe(1);
  });

  it('keeps prior observations isolated by market and symbol', () => {
    const storage = window.localStorage;
    storage.clear();
    const aapl = buildQueryObservation(snapshot(), '2026-07-10T10:00:00Z');
    storeQueryObservation(storage, aapl);

    expect(readPriorQueryObservation(storage, 'us', 'AAPL')).toEqual(aapl);
    expect(readPriorQueryObservation(storage, 'hk', 'AAPL')).toBeNull();
    expect(readPriorQueryObservation(storage, 'us', 'MSFT')).toBeNull();
  });

  it('reports a storage failure instead of claiming the observation was saved', () => {
    const storage = {
      getItem: () => null,
      setItem: () => { throw new Error('storage blocked'); },
    } as unknown as Storage;
    const current = buildQueryObservation(snapshot());

    expect(storeQueryObservation(storage, current)).toBe(false);
  });
});
