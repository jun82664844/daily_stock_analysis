export type ScreeningLanguage = 'zh' | 'en';

export const MAX_SCREENING_COMPARE = 5;

const ADVISORY_PATTERNS = [
  /建议(?:买入|卖出|加仓|减仓|持有)/i,
  /(?:买入|卖出|加仓|减仓|止损|止盈)信号/i,
  /(?:必涨|抄底|逃顶|目标价|上涨空间|预期收益)/i,
  /(?:recommend(?:ed|ation)?|should)\s+(?:buy|sell|hold)/i,
  /(?:buy|sell)\s+(?:signal|now)/i,
  /target\s+price/i,
  /expected\s+return/i,
  /(?:入场|操作|交易)机会/i,
  /(?:启动|买卖)信号/i,
];

type StrategyPresentation = {
  name: string;
  description: string;
  category: string;
};

const STRATEGY_PRESENTATIONS: Record<string, { zh: StrategyPresentation; en: StrategyPresentation }> = {
  balanced_alpha: {
    zh: { name: '多因子数据筛选', description: '综合估值、资金活跃度、动量与稳定性指标，返回符合条件的数据记录。', category: '综合指标' },
    en: { name: 'Multi-factor data filter', description: 'Filters records using valuation, capital activity, momentum and stability metrics.', category: 'Multi-factor' },
  },
  capital_heat: {
    zh: { name: '资金活跃度筛选', description: '按成交额、换手率、量价变化等资金活跃度指标筛选数据记录。', category: '资金数据' },
    en: { name: 'Capital activity filter', description: 'Filters records by turnover, trading value and price-volume activity metrics.', category: 'Capital data' },
  },
  dual_low: {
    zh: { name: '低估值数据筛选', description: '按估值、流动性、当日活跃度和价格形态指标筛选数据记录。', category: '估值数据' },
    en: { name: 'Low-valuation data filter', description: 'Filters records by valuation, liquidity, daily activity and price-pattern metrics.', category: 'Valuation data' },
  },
  momentum_quality: {
    zh: { name: '趋势质量筛选', description: '按价格趋势、质量与稳定性指标筛选数据记录。', category: '趋势数据' },
    en: { name: 'Trend quality filter', description: 'Filters records by price-trend, quality and stability metrics.', category: 'Trend data' },
  },
  oversold_reversal: {
    zh: { name: '价格回撤筛选', description: '按阶段跌幅、流动性和价格修复指标筛选数据记录。', category: '价格数据' },
    en: { name: 'Price pullback filter', description: 'Filters records by period decline, liquidity and price-recovery metrics.', category: 'Price data' },
  },
  quality_value: {
    zh: { name: '估值质量筛选', description: '按估值、流动性、波动与活跃度指标筛选数据记录。', category: '估值数据' },
    en: { name: 'Valuation quality filter', description: 'Filters records by valuation, liquidity, volatility and activity metrics.', category: 'Valuation data' },
  },
  shrink_pullback: {
    zh: { name: '量价回落筛选', description: '按价格趋势、均线位置和成交量收缩指标筛选数据记录。', category: '量价数据' },
    en: { name: 'Volume pullback filter', description: 'Filters records by price trend, moving-average position and contracting volume.', category: 'Price-volume data' },
  },
  volume_breakout: {
    zh: { name: '量价突破筛选', description: '按价格区间、阻力位和成交量放大指标筛选数据记录。', category: '量价数据' },
    en: { name: 'Price-volume breakout filter', description: 'Filters records by price range, resistance level and expanding volume metrics.', category: 'Price-volume data' },
  },
};

export function toggleComparedCodes(current: string[], code: string): string[] {
  const normalized = code.trim().toUpperCase();
  if (!normalized) return current;
  if (current.includes(normalized)) return current.filter((item) => item !== normalized);
  if (current.length >= MAX_SCREENING_COMPARE) return current;
  return [...current, normalized];
}

export function containsAdvisoryLanguage(value: string): boolean {
  return ADVISORY_PATTERNS.some((pattern) => pattern.test(value));
}

export function strategyPresentation(
  id: string,
  language: ScreeningLanguage,
  fallback?: Partial<StrategyPresentation>,
): StrategyPresentation {
  const known = STRATEGY_PRESENTATIONS[id]?.[language];
  if (known) return known;
  const description = fallback?.description?.trim() || '';
  return {
    name: fallback?.name?.trim() || (language === 'en' ? 'Custom filter' : '自定义筛选'),
    description: description && !containsAdvisoryLanguage(description)
      ? description
      : language === 'en'
        ? 'Uses configured factual market-data conditions.'
        : '按已配置的事实型市场数据条件进行筛选。',
    category: fallback?.category?.trim() || (language === 'en' ? 'Custom filter' : '自定义筛选'),
  };
}

export function dataFreshnessLabel(value: string, language: ScreeningLanguage): string {
  const labels: Record<string, [string, string]> = {
    fresh: ['数据新鲜', 'Fresh data'],
    cached: ['缓存数据', 'Cached data'],
    stale: ['数据过期', 'Stale data'],
    unavailable: ['数据不可用', 'Data unavailable'],
  };
  const pair = labels[value] ?? [value || '-', value || '-'];
  return language === 'en' ? pair[1] : pair[0];
}

export function dataCompletenessLabel(value: number, language: ScreeningLanguage): string {
  if (value >= 75) return language === 'en' ? 'High data coverage' : '数据完整度高';
  if (value >= 40) return language === 'en' ? 'Partial data coverage' : '数据部分完整';
  return language === 'en' ? 'Limited data coverage' : '数据覆盖有限';
}

export function metricLabel(code: string, language: ScreeningLanguage): string {
  const key = code.startsWith('factor:') ? code.slice(7) : code;
  const labels: Record<string, [string, string]> = {
    screen_score: ['条件匹配度', 'Filter match'],
    score: ['指标汇总值', 'Metric aggregate'],
    change_pct: ['涨跌幅', 'Price change'],
    quote_price: ['最新价格', 'Latest price'],
    quality: ['质量因子', 'Quality factor'],
    value: ['估值因子', 'Valuation factor'],
    growth: ['成长因子', 'Growth factor'],
    momentum: ['动量因子', 'Momentum factor'],
  };
  const pair = labels[key] ?? [key, key];
  return language === 'en' ? pair[1] : pair[0];
}

export function informationFlagLabel(code: string, language: ScreeningLanguage): string {
  const labels: Record<string, [string, string]> = {
    data_stale: ['数据已过期', 'Data is stale'],
    data_unavailable: ['数据不可用', 'Data is unavailable'],
    data_warning: ['数据需要核对', 'Data needs review'],
    data_partial: ['数据部分缺失', 'Some data is missing'],
    news_unavailable: ['资讯数据暂不可用', 'News data is temporarily unavailable'],
    quote_stale: ['行情数据需要刷新核对', 'Quote data needs refresh verification'],
    valuation_data_high: ['估值指标处于较高区间', 'Valuation metric is in a higher range'],
  };
  const pair = labels[code] ?? [code, code];
  return language === 'en' ? pair[1] : pair[0];
}

export function observationLabel(code: string, language: ScreeningLanguage): string {
  const labels: Record<string, [string, string]> = {
    refresh_data: ['刷新并核对数据来源', 'Refresh and verify the data source'],
    monitor_factor_values: ['继续记录相关指标变化', 'Continue recording metric changes'],
    complete_factor_data: ['补充缺失的指标数据', 'Complete the missing metric data'],
    verify_data_freshness: ['核对数据时间与来源状态', 'Verify data timestamp and source state'],
  };
  const pair = labels[code] ?? [code, code];
  return language === 'en' ? pair[1] : pair[0];
}

export function conditionExitLabel(code: string, language: ScreeningLanguage): string {
  const labels: Record<string, [string, string]> = {
    factor_condition_changed: ['相关指标不再满足当前筛选条件', 'A metric no longer matches the current filter'],
    data_unavailable: ['数据不可用，无法继续核对筛选条件', 'Data is unavailable for filter verification'],
    data_freshness_degraded: ['数据新鲜度下降时重新核对条件', 'Recheck the filter when data freshness degrades'],
  };
  const pair = labels[code] ?? [code, code];
  return language === 'en' ? pair[1] : pair[0];
}
