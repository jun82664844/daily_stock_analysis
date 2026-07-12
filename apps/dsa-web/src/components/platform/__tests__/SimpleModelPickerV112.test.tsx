import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import SimpleModelPickerV112 from '../SimpleModelPickerV112';

const options = [
  { optionId: 'platform_recommended', label: '平台推荐', source: 'platform' as const, providerLabel: 'DSA', speed: 'fast' as const, purpose: '快速资讯分析', quotaType: 'flash' as const, costUnits: 1, recommended: true },
  { optionId: 'byok:2:recommended', label: '我的 DeepSeek', source: 'byok' as const, providerLabel: 'DeepSeek', speed: 'balanced' as const, purpose: '使用我的 API', quotaType: null, costUnits: 0, recommended: false },
];

describe('SimpleModelPickerV112', () => {
  it('defaults to platform recommended and hides technical fields', () => {
    render(<SimpleModelPickerV112 options={options} value="platform_recommended" onChange={vi.fn()} language="zh" />);
    expect(screen.getByText('平台推荐')).toBeInTheDocument();
    expect(screen.queryByLabelText(/Base URL/i)).not.toBeInTheDocument();
    expect(screen.queryByLabelText(/模型内部名称/i)).not.toBeInTheDocument();
  });

  it('emits one opaque option id', () => {
    const onChange = vi.fn();
    render(<SimpleModelPickerV112 options={options} value="platform_recommended" onChange={onChange} language="zh" />);
    fireEvent.click(screen.getByRole('button', { name: /我的 DeepSeek/ }));
    expect(onChange).toHaveBeenCalledWith('byok:2:recommended');
  });
});
