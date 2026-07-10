import type { BasicStockSnapshot } from '../../api/stocks';

export const QUERY_OBSERVATION_STORAGE_KEY = 'dsa-free-query-observations-v1';
const MAX_OBSERVATIONS = 40;

export type QueryTrendPosition = 'above_ma20' | 'below_ma20' | 'at_ma20' | 'unknown';

export type QueryObservation = {
  version: 1;
  stockCode: string;
  market: string;
  observedAt: string;
  sourceUpdatedAt: string | null;
  price: number | null;
  changePercent: number | null;
  ma5: number | null;
  ma20: number | null;
  trendPosition: QueryTrendPosition;
  volumeSignal: string;
  signalScore: number | null;
  freshness: string;
  warningCount: number;
};

export type QueryChangeSummary = {
  kind: 'first' | 'unchanged' | 'changed' | 'unavailable';
  previous: QueryObservation | null;
  current: QueryObservation;
  priceDelta: number | null;
  changePercentDelta: number | null;
  signalScoreDelta: number | null;
  warningCountDelta: number;
  freshnessChanged: boolean;
  trendPositionChanged: boolean;
  volumeSignalChanged: boolean;
};

type StoredObservations = Record<string, QueryObservation>;

const finiteNumber = (value: unknown): number | null => (
  typeof value === 'number' && Number.isFinite(value) ? value : null
);

const pickNumber = (values: Record<string, unknown>, ...keys: string[]): number | null => {
  for (const key of keys) {
    const value = finiteNumber(values[key]);
    if (value !== null) return value;
  }
  return null;
};

const pickString = (values: Record<string, unknown>, ...keys: string[]): string => {
  for (const key of keys) {
    const value = values[key];
    if (typeof value === 'string' && value.trim()) return value.trim();
  }
  return '';
};

const observationKey = (market: string, stockCode: string): string => (
  `${(market || 'unknown').trim().toLowerCase()}:${(stockCode || '').trim().toUpperCase()}`
);

const trendPosition = (price: number | null, ma20: number | null): QueryTrendPosition => {
  if (price === null || ma20 === null) return 'unknown';
  if (Math.abs(price - ma20) < 0.000001) return 'at_ma20';
  return price > ma20 ? 'above_ma20' : 'below_ma20';
};

const safeDelta = (previous: number | null, current: number | null): number | null => (
  previous === null || current === null ? null : Number((current - previous).toFixed(6))
);

const hasNumericChange = (value: number | null): boolean => value !== null && Math.abs(value) > 0.000001;

const readStore = (storage: Storage): StoredObservations => {
  try {
    const parsed = JSON.parse(storage.getItem(QUERY_OBSERVATION_STORAGE_KEY) || '{}');
    return parsed && typeof parsed === 'object' && !Array.isArray(parsed) ? parsed as StoredObservations : {};
  } catch {
    return {};
  }
};

export const buildQueryObservation = (
  snapshot: BasicStockSnapshot,
  observedAt = new Date().toISOString(),
): QueryObservation => {
  const indicators = snapshot.indicators || {};
  const price = finiteNumber(snapshot.quote.currentPrice);
  const ma20 = pickNumber(indicators, 'ma20', 'MA20');
  return {
    version: 1,
    stockCode: snapshot.stockCode.trim().toUpperCase(),
    market: (snapshot.market || 'unknown').trim().toLowerCase(),
    observedAt,
    sourceUpdatedAt: snapshot.quote.updateTime || null,
    price,
    changePercent: finiteNumber(snapshot.quote.changePercent),
    ma5: pickNumber(indicators, 'ma5', 'MA5'),
    ma20,
    trendPosition: trendPosition(price, ma20),
    volumeSignal: pickString(indicators, 'volumePriceSignal', 'volume_price_signal') || 'unknown',
    signalScore: finiteNumber(snapshot.intelligence?.signalScore?.score),
    freshness: snapshot.quote.freshness || 'unknown',
    warningCount: (snapshot.warnings || []).filter((warning) => warning.severity !== 'info').length,
  };
};

export const readPriorQueryObservation = (
  storage: Storage,
  market: string,
  stockCode: string,
): QueryObservation | null => readStore(storage)[observationKey(market, stockCode)] || null;

export const storeQueryObservation = (storage: Storage, observation: QueryObservation): boolean => {
  const current = readStore(storage);
  current[observationKey(observation.market, observation.stockCode)] = observation;
  const bounded = Object.fromEntries(
    Object.entries(current)
      .sort(([, left], [, right]) => String(right.observedAt).localeCompare(String(left.observedAt)))
      .slice(0, MAX_OBSERVATIONS),
  );
  try {
    storage.setItem(QUERY_OBSERVATION_STORAGE_KEY, JSON.stringify(bounded));
    return true;
  } catch {
    // Browser storage can be unavailable in private or restricted contexts.
    return false;
  }
};

export const compareQueryObservations = (
  previous: QueryObservation | null,
  current: QueryObservation,
): QueryChangeSummary => {
  if (!previous) {
    return {
      kind: 'first',
      previous: null,
      current,
      priceDelta: null,
      changePercentDelta: null,
      signalScoreDelta: null,
      warningCountDelta: 0,
      freshnessChanged: false,
      trendPositionChanged: false,
      volumeSignalChanged: false,
    };
  }

  const priceDelta = safeDelta(previous.price, current.price);
  const changePercentDelta = safeDelta(previous.changePercent, current.changePercent);
  const signalScoreDelta = safeDelta(previous.signalScore, current.signalScore);
  const warningCountDelta = current.warningCount - previous.warningCount;
  const freshnessChanged = previous.freshness !== current.freshness;
  const trendPositionChanged = previous.trendPosition !== current.trendPosition;
  const volumeSignalChanged = previous.volumeSignal !== current.volumeSignal;
  const changed = hasNumericChange(priceDelta)
    || hasNumericChange(changePercentDelta)
    || hasNumericChange(signalScoreDelta)
    || warningCountDelta !== 0
    || freshnessChanged
    || trendPositionChanged
    || volumeSignalChanged;

  return {
    kind: changed ? 'changed' : 'unchanged',
    previous,
    current,
    priceDelta,
    changePercentDelta,
    signalScoreDelta,
    warningCountDelta,
    freshnessChanged,
    trendPositionChanged,
    volumeSignalChanged,
  };
};
