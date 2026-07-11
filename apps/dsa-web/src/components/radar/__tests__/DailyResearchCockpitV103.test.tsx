import { fireEvent, render, screen, within } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import type { PlatformWatchlistRadarResponse } from '../../../api/platform';
import { DailyResearchCockpitV103 } from '../DailyResearchCockpitV103';

const digestItem = (
  stockCode: string,
  state: string,
  dataConfidence: string,
  priorityScore: number,
) => ({
  stockCode,
  stockName: `${stockCode} name`,
  market: 'us',
  state,
  priorityScore,
  changePercent: state === 'risk_review' ? -3.2 : 2.4,
  signalScore: state === 'risk_review' ? 42 : 78,
  dataConfidence,
});

const radar = {
  userId: 103,
  plan: 'free',
  visibleLimit: 10,
  totalWatchlist: 3,
  processed: 3,
  hiddenCount: 0,
  degraded: 1,
  summary: { eventCount: 4, riskCount: 1, sourceEventCount: 1 },
  dailyDigest: {
    strongConfirmation: [digestItem('AAPL', 'strong_confirmation', 'high', 92)],
    riskReview: [digestItem('MU', 'risk_review', 'low', 88)],
    waitForConfirmation: [digestItem('600519', 'wait_for_confirmation', 'medium', 60)],
    dataHealth: { fresh: 1, cached: 1, stale: 1, unavailable: 0 },
    upgradeBoundary: 'same_research_flow_better_sources_and_automation',
    aiUsed: false,
  },
  items: [],
  events: [],
  generatedAt: '2026-07-11T10:00:00Z',
  aiUsed: false,
  analysisBoundary: 'information_only_not_investment_advice',
} as unknown as PlatformWatchlistRadarResponse;

describe('DailyResearchCockpitV103', () => {
  it('renders the Chinese daily workflow, confidence, freshness and API trial boundary', () => {
    render(
      <DailyResearchCockpitV103
        language="zh"
        radar={radar}
        trialRemaining={5}
        trialLimit={5}
        onSelectSymbol={() => undefined}
      />,
    );

    const panel = screen.getByTestId('daily-research-cockpit-v103');
    expect(panel).toHaveTextContent('今日研究驾驶舱');
    expect(panel).toHaveTextContent('重点确认');
    expect(panel).toHaveTextContent('风险复核');
    expect(panel).toHaveTextContent('等待确认');
    expect(panel).toHaveTextContent('数据可信度：高');
    expect(panel).toHaveTextContent('数据可信度：低');
    expect(panel).toHaveTextContent('新鲜 1');
    expect(panel).toHaveTextContent('过期 1');
    expect(panel).toHaveTextContent('平台 API 试用剩余 5/5');
    expect(panel).toHaveTextContent('不会自动消耗额度');
    expect(panel).toHaveTextContent('不构成投资建议');
  });

  it('renders equivalent English labels', () => {
    render(
      <DailyResearchCockpitV103
        language="en"
        radar={radar}
        trialRemaining={4}
        trialLimit={5}
        onSelectSymbol={() => undefined}
      />,
    );

    const panel = screen.getByTestId('daily-research-cockpit-v103');
    expect(panel).toHaveTextContent('Daily research cockpit');
    expect(panel).toHaveTextContent('Strong confirmation');
    expect(panel).toHaveTextContent('Risk review');
    expect(panel).toHaveTextContent('Wait for confirmation');
    expect(panel).toHaveTextContent('Data confidence: High');
    expect(panel).toHaveTextContent('Platform API trial 4/5 remaining');
    expect(panel).toHaveTextContent('does not consume quota automatically');
  });

  it('opens the selected symbol without consuming a trial automatically', () => {
    const onSelectSymbol = vi.fn();
    render(
      <DailyResearchCockpitV103
        language="zh"
        radar={radar}
        trialRemaining={5}
        trialLimit={5}
        onSelectSymbol={onSelectSymbol}
      />,
    );

    const strongGroup = screen.getByTestId('daily-research-group-strong_confirmation');
    fireEvent.click(within(strongGroup).getByRole('button', { name: /AAPL/ }));
    expect(onSelectSymbol).toHaveBeenCalledWith('AAPL');
  });
});
