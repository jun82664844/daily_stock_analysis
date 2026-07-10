import { describe, expect, it } from 'vitest';
import type { HistoryItem } from '../../../types/analysis';
import { findNewTrialHistoryItem } from '../freeApiTrialReport';

const historyItem = (id: number, stockCode: string, createdAt: string): HistoryItem => ({
  id,
  queryId: `query-${id}`,
  stockCode,
  stockName: stockCode,
  reportType: 'brief',
  createdAt,
});

describe('findNewTrialHistoryItem', () => {
  it('returns the newest matching report that was not present before the trial', () => {
    const result = findNewTrialHistoryItem(
      [
        historyItem(8, '600519.SH', '2026-07-10T10:00:00Z'),
        historyItem(9, 'AAPL', '2026-07-10T11:00:00Z'),
        historyItem(10, 'AAPL', '2026-07-10T12:00:00Z'),
      ],
      'AAPL',
      new Set([9]),
    );

    expect(result?.id).toBe(10);
  });

  it('does not reopen an older matching report from the baseline', () => {
    const result = findNewTrialHistoryItem(
      [historyItem(9, 'AAPL', '2026-07-10T11:00:00Z')],
      'AAPL',
      new Set([9]),
    );

    expect(result).toBeNull();
  });

  it('ignores an old report that was outside the visible baseline', () => {
    const result = findNewTrialHistoryItem(
      [historyItem(11, 'AAPL', '2026-07-10T09:00:00Z')],
      'AAPL',
      new Set(),
      Date.parse('2026-07-10T10:00:00Z'),
    );

    expect(result).toBeNull();
  });
});
