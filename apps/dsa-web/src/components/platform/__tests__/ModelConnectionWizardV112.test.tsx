import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import ModelConnectionWizardV112 from '../ModelConnectionWizardV112';

describe('ModelConnectionWizardV112', () => {
  it('connects a provider with provider, key and one action', async () => {
    const onConnect = vi.fn().mockResolvedValue(undefined);
    render(<ModelConnectionWizardV112 language="zh" onConnect={onConnect} />);
    fireEvent.click(screen.getByRole('button', { name: 'DeepSeek' }));
    fireEvent.change(screen.getByLabelText('API Key'), { target: { value: 'sk-test-value' } });
    fireEvent.click(screen.getByRole('button', { name: '连接并测试' }));
    await waitFor(() => expect(onConnect).toHaveBeenCalledWith({ provider: 'deepseek', apiKey: 'sk-test-value' }));
    expect((screen.getByLabelText('API Key') as HTMLInputElement).value).toBe('');
  });

  it('never exposes base URL or internal model inputs', () => {
    render(<ModelConnectionWizardV112 language="zh" onConnect={vi.fn()} />);
    expect(screen.queryByLabelText(/Base URL/i)).not.toBeInTheDocument();
    expect(screen.queryByLabelText(/模型/i)).not.toBeInTheDocument();
  });

  it('offers explicit operating systems and a time-limited pairing code', async () => {
    const onCreatePairing = vi.fn().mockResolvedValue({
      code: '123456',
      expiresAt: new Date(Date.now() + 5 * 60 * 1000).toISOString(),
    });
    render(
      <ModelConnectionWizardV112
        language="zh"
        onConnect={vi.fn()}
        onCreatePairing={onCreatePairing}
      />,
    );

    expect(screen.getByRole('link', { name: '下载 Windows x64 开发包' })).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'macOS' }));
    expect(screen.getByRole('link', { name: 'Apple Silicon' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Intel' })).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: '生成配对码' }));
    expect(await screen.findByText('123456')).toBeInTheDocument();
    expect(await screen.findByText(/剩余 5:00|剩余 4:59/)).toBeInTheDocument();
  });
});
