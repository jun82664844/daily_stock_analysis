import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import PriceAlertFormV116 from '../PriceAlertFormV116';

describe('PriceAlertFormV116', () => {
  it('validates a positive finite threshold and saves an objective draft', async () => {
    const onSave = vi.fn().mockResolvedValue(undefined);
    render(
      <PriceAlertFormV116
        language="zh"
        stockCode="AAPL"
        stockName="Apple Inc."
        currentPrice={100}
        currency="USD"
        onSave={onSave}
      />,
    );

    const threshold = screen.getByRole('spinbutton', { name: '到价阈值' });
    fireEvent.change(threshold, { target: { value: '0' } });
    expect(screen.getByRole('button', { name: '保存到价提醒' })).toBeDisabled();
    fireEvent.change(threshold, { target: { value: '105' } });
    fireEvent.change(screen.getByRole('combobox', { name: '到价方向' }), { target: { value: 'price_below' } });
    fireEvent.click(screen.getByRole('button', { name: '保存到价提醒' }));

    await waitFor(() => expect(onSave).toHaveBeenCalledWith({
      stockCode: 'AAPL', stockName: 'Apple Inc.', ruleType: 'price_below', threshold: 105, currency: 'USD',
    }));
  });

  it('disables duplicate submissions while saving and renders English copy', async () => {
    let resolveSave: (() => void) | undefined;
    const onSave = vi.fn(() => new Promise<void>((resolve) => { resolveSave = resolve; }));
    render(
      <PriceAlertFormV116
        language="en"
        stockCode="AAPL"
        stockName="Apple Inc."
        currentPrice={100}
        onSave={onSave}
      />,
    );

    fireEvent.click(screen.getByRole('button', { name: 'Save price alert' }));
    expect(screen.getByRole('button', { name: 'Saving price alert' })).toBeDisabled();
    resolveSave?.();
    await waitFor(() => expect(screen.getByRole('button', { name: 'Save price alert' })).toBeEnabled());
  });
});
