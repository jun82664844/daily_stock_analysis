import type { HistoryItem } from '../../types/analysis';
import { areStockCodesEquivalent } from '../../utils/stockCode';

export function findNewTrialHistoryItem(
  historyItems: HistoryItem[],
  stockCode: string,
  baselineIds: ReadonlySet<number>,
  notBeforeMs?: number,
): HistoryItem | null {
  return historyItems
    .filter((item) => !baselineIds.has(item.id))
    .filter((item) => areStockCodesEquivalent(item.stockCode, stockCode))
    .filter((item) => {
      if (notBeforeMs === undefined) {
        return true;
      }
      const createdAt = Date.parse(item.createdAt || '');
      return Number.isFinite(createdAt) && createdAt >= notBeforeMs - 5_000;
    })
    .reduce<HistoryItem | null>((latest, item) => {
      if (!latest) {
        return item;
      }
      return Date.parse(item.createdAt || '') > Date.parse(latest.createdAt || '')
        ? item
        : latest;
    }, null);
}
