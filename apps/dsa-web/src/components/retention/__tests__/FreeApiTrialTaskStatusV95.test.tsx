import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { FreeApiTrialTaskStatusV95 } from '../FreeApiTrialTaskStatusV95';

describe('FreeApiTrialTaskStatusV95', () => {
  it('shows progress while a free API trial is running', () => {
    render(
      <FreeApiTrialTaskStatusV95
        language="zh"
        taskId="trial-task-1"
        status="processing"
        progress={42}
      />,
    );

    expect(screen.getByTestId('free-api-trial-task-status')).toHaveTextContent('试用报告生成中');
    expect(screen.getByTestId('free-api-trial-task-progress')).toHaveTextContent('42%');
  });

  it('shows a completed state that points the user to refreshed history', () => {
    render(
      <FreeApiTrialTaskStatusV95
        language="zh"
        taskId="trial-task-1"
        status="completed"
        progress={100}
      />,
    );

    expect(screen.getByTestId('free-api-trial-task-status')).toHaveTextContent('报告已完成');
    expect(screen.getByTestId('free-api-trial-task-status')).toHaveTextContent('历史报告已刷新');
  });

  it('shows an actionable failure state in English', () => {
    render(
      <FreeApiTrialTaskStatusV95
        language="en"
        taskId="trial-task-1"
        status="failed"
        progress={0}
      />,
    );

    expect(screen.getByTestId('free-api-trial-task-status')).toHaveTextContent('Trial report failed');
    expect(screen.getByTestId('free-api-trial-task-status')).toHaveTextContent('try again');
  });
});
