import { describe, expect, it } from 'vitest';
import type { BasicStockSnapshot } from '../../../api/stocks';
import { buildDecisionJourneyModel } from '../decisionJourneyModel';

const buildSnapshot = (market: string, stockCode: string): BasicStockSnapshot => {
  const points = Array.from({ length: 40 }, (_, index) => ({
    date: `2026-06-${String(index + 1).padStart(2, '0')}`,
    close: 100 + index,
    volume: 1_000_000 + index * 25_000,
  }));

  return {
    stockCode,
    stockName: stockCode,
    market,
    quote: {
      currentPrice: 139,
      change: 1.5,
      changePercent: 1.09,
      open: 137,
      high: 140,
      low: 136,
      prevClose: 137.5,
      volume: 1_975_000,
      amount: 274_525_000,
      updateTime: '2026-07-10T09:30:00+08:00',
      source: 'free_web_chart',
      freshness: 'fresh',
    },
    profile: {
      companyName: stockCode,
      sector: 'Technology',
      industry: 'Consumer Electronics',
      marketCap: 4_500_000_000_000,
      peRatio: 31.2,
      source: 'free_profile',
      freshness: 'cached',
    },
    indicators: {
      ma5: 137,
      ma10: 134.5,
      ma20: 129.5,
      volumeChangeVsMa5: 18.2,
    },
    trend: {
      window: points.length,
      source: 'free_history',
      points,
      minClose: 100,
      maxClose: 139,
      changePercent: 39,
    },
    intelligence: {
      mode: 'no_ai',
      aiUsed: false,
      boundary: 'information_only',
      items: [],
      newsCenter: {
        title: 'News',
        summary: 'Latest public information channels.',
        items: [{
          category: 'news',
          title: 'Public information checkpoint',
          summary: 'Verify material events before interpreting price action.',
          status: 'available',
          source: 'free_news_rules',
          action: 'read_source',
          updatedAt: '2026-07-10T09:20:00+08:00',
        }],
        source: 'free_news_rules',
        aiUsed: false,
        publicSearchUsed: false,
        premiumUnlock: 'Realtime links',
        boundary: 'information_only',
      },
      comparisonTargets: [{
        label: 'Market benchmark',
        symbol: market === 'cn' ? '000300.SH' : 'SPY',
        reason: 'Broad-market reference.',
        status: 'reference_only',
        source: 'market_rules',
      }],
    },
    route: {
      normalizedCode: stockCode,
      market,
      channel: `${market}_market_data`,
      dataSourceLane: `${market}_free_lane`,
      aiRequired: false,
    },
    diagnostics: {
      elapsedMs: 35,
      quoteElapsedMs: 12,
      historyElapsedMs: 18,
      cache: { quote: 'miss' },
      sources: { quote: 'free_web_chart', history: 'free_history' },
      freshness: { quote: 'fresh', history: 'fresh' },
      performance: { status: 'ok' },
    },
    aiUsed: false,
  };
};

const buildModel = (market: string, stockCode: string, language: 'zh' | 'en' = 'zh') => (
  buildDecisionJourneyModel({
    snapshot: buildSnapshot(market, stockCode),
    language,
    conclusion: language === 'en' ? 'Trend is constructive.' : '趋势偏强，但仍需等待确认。',
    score: 72,
    risk: language === 'en' ? 'Avoid chasing a stale quote.' : '避免在行情过期时追涨。',
    support: '129.5',
    resistance: '140',
  })
);

describe('buildDecisionJourneyModel', () => {
  it.each([
    ['cn', '600519.SH', 'A股重点', '公告与监管披露'],
    ['us', 'AAPL', '美股重点', '财报与 SEC 文件'],
    ['hk', '00700.HK', '港股重点', '港交所公告与南向资金'],
    ['crypto', 'BTC-USD', '加密市场重点', '流动性与全天候波动'],
  ])('builds a localized market template for %s', (market, stockCode, focusLabel, focusItem) => {
    const model = buildModel(market, stockCode);

    expect(model.marketFocus.label).toBe(focusLabel);
    expect(model.marketFocus.items).toContain(focusItem);
    expect(model.summary.conclusion).toBe('趋势偏强，但仍需等待确认。');
    expect(model.summary.score).toBe(72);
    expect(model.boundary.aiUsed).toBe(false);
  });

  it('derives technical evidence and keeps source trust visible', () => {
    const model = buildModel('us', 'AAPL');

    expect(model.technical.ma5).toBeCloseTo(137, 5);
    expect(model.technical.ma20).toBeCloseTo(129.5, 5);
    expect(model.technical.rsi14).toBe(100);
    expect(model.technical.trendState).toBe('偏强');
    expect(model.chart.points).toHaveLength(40);
    expect(model.trust.quoteSource).toBe('免费网络行情');
    expect(model.trust.historySource).toBe('免费历史行情');
    expect(model.trust.profileSource).toBe('免费公司资料');
    expect(model.trust.freshness).toBe('新鲜');
    expect(model.trust.updatedAt).not.toContain('T09:30:00');
    expect(model.tabs.find((tab) => tab.key === 'sources')?.items[0]?.value).toBe('免费网络行情');
  });

  it('keeps the same reading structure while describing the paid source improvement', () => {
    const model = buildModel('us', 'AAPL', 'en');

    expect(model.labels.title).toBe('Decision journey');
    expect(model.marketFocus.label).toBe('US market focus');
    expect(model.comparison.free).toContain('Complete decision structure');
    expect(model.comparison.premium).toContain('Realtime API freshness');
    expect(model.boundary.disclaimer).toBe('Information analysis only, not investment advice.');
  });
});
