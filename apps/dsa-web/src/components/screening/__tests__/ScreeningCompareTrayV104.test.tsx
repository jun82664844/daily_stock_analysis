import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import type { AlphaSiftCandidate } from '../../../api/alphasift';
import ScreeningCompareTrayV104 from '../ScreeningCompareTrayV104';

const makeCandidate = (code: string, price: number | null): AlphaSiftCandidate => ({
  rank: 1,
  code,
  name: code === '600519' ? '贵州茅台' : '平安银行',
  industry: '测试行业',
  price,
  changePct: code === '600519' ? 1.2 : null,
  reason: '',
  raw: {},
  screeningBrief: {
    matchedConditionCodes: ['factor:quality'],
    observedMetrics: [{ code: 'factor:quality', value: 80, source: 'alphasift' }],
    informationFlags: [],
    observationCodes: ['monitor_factor_values'],
    conditionExitCodes: ['factor_condition_changed'],
    dataFreshness: code === '600519' ? 'fresh' : 'stale',
    dataCompleteness: code === '600519' ? 80 : 45,
    sourceStatus: 'partial',
    aiUsed: false,
  },
});

describe('ScreeningCompareTrayV104', () => {
  it('compares two securities and keeps missing values neutral', () => {
    render(
      <ScreeningCompareTrayV104
        candidates={[makeCandidate('600519', 1688), makeCandidate('000001', null)]}
        selectedCodes={['600519', '000001']}
        language="zh"
        onRemove={vi.fn()}
        onClear={vi.fn()}
        onOpenData={vi.fn()}
      />
    );

    const tray = screen.getByTestId('screening-compare-tray-v104');
    expect(tray).toHaveTextContent('数据横向比较');
    expect(tray).toHaveTextContent('600519');
    expect(tray).toHaveTextContent('000001');
    expect(tray).toHaveTextContent('1,688');
    expect(screen.getByTestId('screening-compare-price-000001')).toHaveTextContent('-');
    expect(screen.getByTestId('screening-compare-price-000001')).not.toHaveTextContent('0');
  });

  it('removes and clears selected securities', () => {
    const onRemove = vi.fn();
    const onClear = vi.fn();
    render(
      <ScreeningCompareTrayV104
        candidates={[makeCandidate('600519', 1688), makeCandidate('000001', 10)]}
        selectedCodes={['600519', '000001']}
        language="zh"
        onRemove={onRemove}
        onClear={onClear}
        onOpenData={vi.fn()}
      />
    );

    fireEvent.click(screen.getByTestId('screening-compare-remove-600519'));
    fireEvent.click(screen.getByTestId('screening-compare-clear'));
    expect(onRemove).toHaveBeenCalledWith('600519');
    expect(onClear).toHaveBeenCalledTimes(1);
  });
});
