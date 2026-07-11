import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { WatchlistAlertLoopV100 } from '../WatchlistAlertLoopV100';

const history = {
  userId: 7,
  total: 2,
  aiUsed: false,
  items: [
    {
      id: 2,
      plan: 'free',
      processed: 4,
      eventCount: 7,
      riskCount: 2,
      sourceEventCount: 1,
      triggeredCount: 1,
      strongest: { stockCode: 'AAPL', stockName: 'Apple Inc.', changePercent: 4.2 },
      weakest: { stockCode: 'HK00700', stockName: 'Tencent', changePercent: -2.1 },
      createdAt: '2026-07-11T10:00:00Z',
    },
    {
      id: 1,
      plan: 'free',
      processed: 4,
      eventCount: 5,
      riskCount: 1,
      sourceEventCount: 0,
      triggeredCount: 0,
      strongest: { stockCode: 'BTC-USD', changePercent: 2.0 },
      weakest: { stockCode: 'AAPL', changePercent: -1.0 },
      createdAt: '2026-07-10T10:00:00Z',
    },
  ],
};

const rules = {
  userId: 7,
  plan: 'free',
  limit: 3,
  total: 1,
  remaining: 2,
  aiUsed: false,
  items: [{
    id: 11,
    stockCode: 'AAPL',
    ruleType: 'ma20_cross',
    threshold: null,
    referenceValue: 200,
    enabled: true,
    createdAt: '2026-07-11T09:00:00Z',
    updatedAt: '2026-07-11T09:00:00Z',
  }],
};

const triggered = [{
  ruleId: 11,
  stockCode: 'AAPL',
  ruleType: 'ma20_cross',
  direction: 'above',
  value: 210,
  threshold: null,
  referenceValue: 200,
  aiUsed: false,
}];

describe('WatchlistAlertLoopV100', () => {
  it('renders Chinese private rules, triggers, and daily history', () => {
    const onDeleteRule = vi.fn();
    render(
      <WatchlistAlertLoopV100
        language="zh"
        history={history}
        rules={rules}
        triggeredAlerts={triggered}
        busy={false}
        onDeleteRule={onDeleteRule}
      />,
    );

    const panel = screen.getByTestId('watchlist-alert-loop-v100');
    expect(panel).toHaveTextContent('连续跟踪与每日复盘');
    expect(panel).toHaveTextContent('免费版提醒 1/3');
    expect(panel).toHaveTextContent('AAPL 上穿 MA20 200');
    expect(panel).toHaveTextContent('本次触发 1 条');
    expect(panel).toHaveTextContent('最近复盘 2 次');
    expect(panel).toHaveTextContent('处理 4 只');
    fireEvent.click(screen.getByTestId('watchlist-alert-rule-delete-11'));
    expect(onDeleteRule).toHaveBeenCalledWith(11);
  });

  it('renders the same workflow in English', () => {
    render(
      <WatchlistAlertLoopV100
        language="en"
        history={history}
        rules={rules}
        triggeredAlerts={triggered}
        busy={false}
        onDeleteRule={() => undefined}
      />,
    );

    const panel = screen.getByTestId('watchlist-alert-loop-v100');
    expect(panel).toHaveTextContent('Continuous tracking and daily reviews');
    expect(panel).toHaveTextContent('AAPL crossed above MA20 200');
    expect(panel).not.toHaveTextContent('连续跟踪与每日复盘');
  });

  it('shows an honest baseline empty state', () => {
    render(
      <WatchlistAlertLoopV100
        language="zh"
        history={{ ...history, total: 0, items: [] }}
        rules={{ ...rules, total: 0, remaining: 3, items: [] }}
        triggeredAlerts={[]}
        busy={false}
        onDeleteRule={() => undefined}
      />,
    );

    expect(screen.getByTestId('watchlist-alert-loop-v100')).toHaveTextContent('首次运行会建立比较基线');
  });
});
