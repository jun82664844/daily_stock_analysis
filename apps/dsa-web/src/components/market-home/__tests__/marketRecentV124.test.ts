import { beforeEach, describe, expect, it } from 'vitest';
import {
  clearRecentMarketSymbols,
  readRecentMarketSymbols,
  rememberRecentMarketSymbol,
} from '../marketRecentV124';

describe('marketRecentV124', () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  it('starts empty and ignores damaged local data', () => {
    expect(readRecentMarketSymbols()).toEqual([]);
    window.localStorage.setItem('dsa.public-market.recent-symbols.v124', '{broken');
    expect(readRecentMarketSymbols()).toEqual([]);
  });

  it('deduplicates by symbol, moves the latest item first, and keeps six items', () => {
    const items = [
      ['AAPL', 'Apple', 'us'],
      ['0700.HK', 'Tencent', 'hk'],
      ['600519.SH', '贵州茅台', 'cn'],
      ['MSFT', 'Microsoft', 'us'],
      ['000001.SZ', '平安银行', 'cn'],
      ['9988.HK', 'Alibaba', 'hk'],
      ['NVDA', 'NVIDIA', 'us'],
    ] as const;

    items.forEach(([symbol, name, market], index) => {
      rememberRecentMarketSymbol({ symbol, name, market }, () => `2026-07-14T00:00:0${index}Z`);
    });
    rememberRecentMarketSymbol(
      { symbol: 'AAPL', name: 'Apple Inc.', market: 'us' },
      () => '2026-07-14T00:00:09Z',
    );

    const recent = readRecentMarketSymbols();
    expect(recent).toHaveLength(6);
    expect(recent[0]).toEqual({
      symbol: 'AAPL',
      name: 'Apple Inc.',
      market: 'us',
      viewedAt: '2026-07-14T00:00:09Z',
    });
    expect(recent.filter((item) => item.symbol === 'AAPL')).toHaveLength(1);
    expect(JSON.stringify(recent)).not.toMatch(/api.?key|email|user.?id/i);
  });

  it('clears only the recent-symbol collection', () => {
    window.localStorage.setItem('unrelated-setting', 'keep');
    rememberRecentMarketSymbol(
      { symbol: 'AAPL', name: 'Apple', market: 'us' },
      () => '2026-07-14T00:00:00Z',
    );

    clearRecentMarketSymbols();

    expect(readRecentMarketSymbols()).toEqual([]);
    expect(window.localStorage.getItem('unrelated-setting')).toBe('keep');
  });
});
