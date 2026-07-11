import { describe, expect, it } from 'vitest';

import {
  MAX_SCREENING_COMPARE,
  containsAdvisoryLanguage,
  dataCompletenessLabel,
  dataFreshnessLabel,
  metricLabel,
  strategyPresentation,
  toggleComparedCodes,
} from '../screeningModelV104';

describe('screeningModelV104', () => {
  it('toggles comparison codes and keeps the five-symbol limit', () => {
    expect(toggleComparedCodes([], 'AAPL')).toEqual(['AAPL']);
    expect(toggleComparedCodes(['AAPL'], 'AAPL')).toEqual([]);
    expect(toggleComparedCodes(['A', 'B', 'C', 'D', 'E'], 'F')).toEqual(['A', 'B', 'C', 'D', 'E']);
    expect(MAX_SCREENING_COMPARE).toBe(5);
  });

  it('uses neutral data-state labels in Chinese and English', () => {
    expect(dataFreshnessLabel('stale', 'zh')).toBe('数据过期');
    expect(dataFreshnessLabel('stale', 'en')).toBe('Stale data');
    expect(dataCompletenessLabel(82, 'zh')).toBe('数据完整度高');
    expect(dataCompletenessLabel(52, 'en')).toBe('Partial data coverage');
  });

  it('maps observable metrics without investment language', () => {
    expect(metricLabel('factor:quality', 'zh')).toBe('质量因子');
    expect(metricLabel('screen_score', 'en')).toBe('Filter match');
    expect(metricLabel('quote_price', 'zh')).toBe('最新价格');
  });

  it('detects DSA-owned advisory language but permits factual alerts', () => {
    expect(containsAdvisoryLanguage('建议买入并设置目标价')).toBe(true);
    expect(containsAdvisoryLanguage('AAPL 当前价格达到您设置的 315.00 提醒条件')).toBe(false);
    expect(containsAdvisoryLanguage('Price crossed the user-defined threshold')).toBe(false);
  });

  it('presents built-in screening strategies as neutral data filters in both languages', () => {
    const zh = strategyPresentation('shrink_pullback', 'zh');
    const en = strategyPresentation('shrink_pullback', 'en');

    expect(zh.name).toBe('量价回落筛选');
    expect(zh.description).toContain('成交量');
    expect(containsAdvisoryLanguage(zh.description)).toBe(false);
    expect(en.name).toBe('Volume pullback filter');
    expect(en.description).toContain('volume');
    expect(containsAdvisoryLanguage(en.description)).toBe(false);
  });
});
