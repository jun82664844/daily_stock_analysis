import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { LocalModelStatusV107 } from '../LocalModelStatusV107';


const readyStatus = {
  enabled: true,
  reachable: true,
  ready: true,
  quickReady: true,
  deepReady: true,
  reason: 'ready',
  runtime: 'ollama',
  quickModel: 'quick-model',
  deepModel: 'deep-model',
  quickModelAvailable: true,
  deepModelAvailable: true,
  maxConcurrent: 1,
};

describe('LocalModelStatusV107', () => {
  it('explains the free local quota and both model lanes in Chinese', () => {
    const onRunQuick = vi.fn();
    render(
      <LocalModelStatusV107
        language="zh"
        plan="free"
        quotaText="本周剩余 50/50"
        status={readyStatus}
        onRunQuick={onRunQuick}
      />,
    );

    const panel = screen.getByTestId('local-model-status-v107');
    expect(screen.getByText('本地 AI 试用已就绪')).toBeInTheDocument();
    expect(panel).toHaveTextContent('快速分析：quick-model');
    expect(panel).toHaveTextContent('深度分析：deep-model');
    expect(screen.getByText(/本周剩余 50\/50/)).toBeInTheDocument();
    expect(screen.getByText(/只提供资讯和数据/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: '使用本地 AI 详细解读' }));
    expect(onRunQuick).toHaveBeenCalledTimes(1);
  });

  it('shows a useful English fallback when Ollama is unreachable', () => {
    render(
      <LocalModelStatusV107
        language="en"
        plan="pro"
        quotaText="100 remaining"
        status={{ ...readyStatus, reachable: false, ready: false, quickReady: false, deepReady: false, reason: 'local_model_unreachable' }}
      />,
    );

    expect(screen.getByText('Local AI is offline')).toBeInTheDocument();
    expect(screen.getByText(/Start Ollama and retry/)).toBeInTheDocument();
    expect(screen.getByText(/Information and data only/)).toBeInTheDocument();
  });
});
