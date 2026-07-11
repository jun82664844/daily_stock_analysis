import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import type { AlphaSiftCandidate } from '../../../api/alphasift';
import MarketScreeningCardV104 from '../MarketScreeningCardV104';

const candidate: AlphaSiftCandidate = {
  rank: 1,
  code: '600519',
  name: '贵州茅台',
  industry: '白酒',
  price: 1688,
  changePct: 1.8,
  reason: 'provider text is not rendered as advice',
  raw: {},
  screeningBrief: {
    matchedConditionCodes: ['screen_score', 'factor:quality'],
    observedMetrics: [
      { code: 'screen_score', value: 88, source: 'alphasift' },
      { code: 'factor:quality', value: 92, source: 'alphasift' },
    ],
    informationFlags: ['valuation_data_high'],
    observationCodes: ['monitor_factor_values'],
    conditionExitCodes: ['factor_condition_changed'],
    dataFreshness: 'cached',
    dataCompleteness: 82,
    sourceStatus: 'available',
    aiUsed: false,
  },
};

describe('MarketScreeningCardV104', () => {
  it('renders neutral data evidence without advisory language', () => {
    render(
      <MarketScreeningCardV104
        candidate={candidate}
        language="zh"
        selected={false}
        compareDisabled={false}
        watchlistState="idle"
        onToggleCompare={vi.fn()}
        onAddWatchlist={vi.fn()}
        onOpenData={vi.fn()}
        onOpenReminder={vi.fn()}
      />
    );

    const card = screen.getByTestId('market-screening-card-600519');
    expect(card).toHaveTextContent('条件匹配说明');
    expect(card).toHaveTextContent('数据完整度高');
    expect(card).toHaveTextContent('缓存数据');
    expect(card).toHaveTextContent('质量因子');
    expect(card).toHaveTextContent('估值指标处于较高区间');
    expect(card).toHaveTextContent('后续数据观察项');
    expect(card).toHaveTextContent('筛选条件不再满足的情形');
    expect(card).toHaveTextContent('未使用 AI');
    expect(card).not.toHaveTextContent(/建议买入|建议卖出|目标价|预期收益/);
  });

  it('routes compare, watchlist, reminder and data actions', () => {
    const onToggleCompare = vi.fn();
    const onAddWatchlist = vi.fn();
    const onOpenData = vi.fn();
    const onOpenReminder = vi.fn();
    render(
      <MarketScreeningCardV104
        candidate={candidate}
        language="zh"
        selected={false}
        compareDisabled={false}
        watchlistState="idle"
        onToggleCompare={onToggleCompare}
        onAddWatchlist={onAddWatchlist}
        onOpenData={onOpenData}
        onOpenReminder={onOpenReminder}
      />
    );

    fireEvent.click(screen.getByTestId('screening-compare-600519'));
    fireEvent.click(screen.getByTestId('screening-watchlist-600519'));
    fireEvent.click(screen.getByTestId('screening-reminder-600519'));
    fireEvent.click(screen.getByTestId('screening-open-data-600519'));

    expect(onToggleCompare).toHaveBeenCalledWith('600519');
    expect(onAddWatchlist).toHaveBeenCalledWith('600519');
    expect(onOpenReminder).toHaveBeenCalledWith('600519');
    expect(onOpenData).toHaveBeenCalledWith('600519');
  });
});
