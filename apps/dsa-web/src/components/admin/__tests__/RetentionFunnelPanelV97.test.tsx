import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import type { PlatformRetentionFunnelResponse } from '../../../api/platform';
import { RetentionFunnelPanelV97 } from '../RetentionFunnelPanelV97';

const summary: PlatformRetentionFunnelResponse = {
  mode: 'local_only',
  windowDays: 30,
  generatedAt: '2026-07-10T10:00:00',
  totalSessions: 3,
  aiUsed: false,
  stages: [
    { event: 'free_query_completed', uniqueSessions: 3, reachedFromStart: 3, droppedFromPrevious: 0, conversionFromPreviousPct: 100, conversionFromStartPct: 100 },
    { event: 'registration_completed', uniqueSessions: 2, reachedFromStart: 2, droppedFromPrevious: 1, conversionFromPreviousPct: 66.7, conversionFromStartPct: 66.7 },
    { event: 'api_trial_submitted', uniqueSessions: 2, reachedFromStart: 2, droppedFromPrevious: 0, conversionFromPreviousPct: 100, conversionFromStartPct: 66.7 },
    { event: 'trial_report_opened', uniqueSessions: 1, reachedFromStart: 1, droppedFromPrevious: 1, conversionFromPreviousPct: 50, conversionFromStartPct: 33.3 },
    { event: 'premium_options_viewed', uniqueSessions: 1, reachedFromStart: 1, droppedFromPrevious: 0, conversionFromPreviousPct: 100, conversionFromStartPct: 33.3 },
  ],
};

describe('RetentionFunnelPanelV97', () => {
  it('renders the five-stage English conversion funnel without identifiers', () => {
    render(<RetentionFunnelPanelV97 language="en" summary={summary} />);

    expect(screen.getByRole('heading', { name: 'Free conversion funnel' })).toBeInTheDocument();
    expect(screen.getByText('30-day local window')).toBeInTheDocument();
    expect(screen.getByTestId('retention-stage-free_query_completed')).toHaveTextContent('Query completed');
    expect(screen.getByTestId('retention-stage-registration_completed')).toHaveTextContent('Registered');
    expect(screen.getByTestId('retention-stage-api_trial_submitted')).toHaveTextContent('API trial');
    expect(screen.getByTestId('retention-stage-trial_report_opened')).toHaveTextContent('Report opened');
    expect(screen.getByTestId('retention-stage-premium_options_viewed')).toHaveTextContent('Premium viewed');
    expect(screen.getByTestId('retention-stage-registration_completed')).toHaveTextContent('2');
    expect(screen.getByTestId('retention-stage-registration_completed')).toHaveTextContent('66.7%');
    expect(screen.getByText('Local aggregate only · No AI used')).toBeInTheDocument();
    expect(screen.queryByText('session-all-1')).not.toBeInTheDocument();
  });

  it('renders complete Chinese labels', () => {
    render(<RetentionFunnelPanelV97 language="zh" summary={summary} />);

    expect(screen.getByRole('heading', { name: '免费用户转化漏斗' })).toBeInTheDocument();
    expect(screen.getByText('近 30 天本地窗口')).toBeInTheDocument();
    expect(screen.getByTestId('retention-stage-free_query_completed')).toHaveTextContent('完成免费查询');
    expect(screen.getByTestId('retention-stage-registration_completed')).toHaveTextContent('完成注册');
    expect(screen.getByTestId('retention-stage-api_trial_submitted')).toHaveTextContent('提交 API 试用');
    expect(screen.getByTestId('retention-stage-trial_report_opened')).toHaveTextContent('打开试用报告');
    expect(screen.getByTestId('retention-stage-premium_options_viewed')).toHaveTextContent('查看高级功能');
    expect(screen.getByText('仅本地汇总 · 未使用 AI')).toBeInTheDocument();
  });
});
