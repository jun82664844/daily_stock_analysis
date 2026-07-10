import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { FreeApiTrialPanelV93 } from '../FreeApiTrialPanelV93';

describe('FreeApiTrialPanelV93', () => {
  it('keeps guest lookup free while offering login for five API trials', () => {
    const onAction = vi.fn();
    render(
      <FreeApiTrialPanelV93
        language="zh"
        signedIn={false}
        plan="free"
        weeklyLimit={5}
        remaining={5}
        busy={false}
        onAction={onAction}
      />,
    );

    expect(screen.getByTestId('free-platform-api-trial')).toHaveTextContent('不登录仍可继续免费查询');
    fireEvent.click(screen.getByTestId('free-platform-api-trial-action'));
    expect(onAction).toHaveBeenCalledOnce();
  });

  it('shows free remaining quota and keeps no-AI research available after exhaustion', () => {
    render(
      <FreeApiTrialPanelV93
        language="zh"
        signedIn
        plan="free"
        weeklyLimit={5}
        remaining={3}
        busy={false}
        onAction={() => undefined}
      />,
    );

    expect(screen.getByTestId('free-platform-api-trial-action')).toHaveTextContent('剩余 3/5');
    expect(screen.getByTestId('free-platform-api-trial')).toHaveTextContent('免费网络研判仍可继续使用');
  });

  it('explains that premium supports both platform API and BYOK', () => {
    render(
      <FreeApiTrialPanelV93
        language="zh"
        signedIn
        plan="pro"
        weeklyLimit={100}
        remaining={88}
        busy={false}
        onAction={() => undefined}
      />,
    );

    expect(screen.getByTestId('free-platform-api-trial')).toHaveTextContent('高级会员可使用平台 API、自己的 API Key');
    expect(screen.getByTestId('free-platform-api-trial-action')).toHaveTextContent('剩余 88/100');
  });

  it('renders submission feedback without hiding the free snapshot', () => {
    render(
      <FreeApiTrialPanelV93
        language="zh"
        signedIn
        plan="free"
        weeklyLimit={5}
        remaining={4}
        busy={false}
        status="平台 API 试用已提交；任务完成后可在运行任务或历史报告中查看。"
        onAction={() => undefined}
      />,
    );

    expect(screen.getByTestId('free-platform-api-trial-status')).toHaveAttribute('role', 'status');
    expect(screen.getByTestId('free-platform-api-trial-status')).toHaveTextContent('平台 API 试用已提交');
  });
});
