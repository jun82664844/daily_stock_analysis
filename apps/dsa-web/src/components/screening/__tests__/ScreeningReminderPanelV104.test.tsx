import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import ScreeningReminderPanelV104 from '../ScreeningReminderPanelV104';

describe('ScreeningReminderPanelV104', () => {
  it('saves a user-confirmed factual threshold rule', () => {
    const onSave = vi.fn();
    render(
      <ScreeningReminderPanelV104
        stockCode="AAPL"
        language="zh"
        state="idle"
        onClose={vi.fn()}
        onSave={onSave}
      />
    );

    fireEvent.change(screen.getByLabelText('提醒类型'), { target: { value: 'price_move' } });
    fireEvent.change(screen.getByLabelText('用户设置阈值'), { target: { value: '3.5' } });
    fireEvent.click(screen.getByTestId('screening-reminder-save'));

    expect(onSave).toHaveBeenCalledWith({ stockCode: 'AAPL', ruleType: 'price_move', threshold: 3.5 });
    expect(screen.getByTestId('screening-reminder-panel-v104')).not.toHaveTextContent(/建议买入|建议卖出|买点/);
  });

  it('supports source and data-state reminders without a numeric threshold', () => {
    const onSave = vi.fn();
    render(
      <ScreeningReminderPanelV104
        stockCode="600519"
        language="en"
        state="idle"
        onClose={vi.fn()}
        onSave={onSave}
      />
    );

    fireEvent.change(screen.getByLabelText('Alert type'), { target: { value: 'source_update' } });
    fireEvent.click(screen.getByTestId('screening-reminder-save'));

    expect(onSave).toHaveBeenCalledWith({ stockCode: '600519', ruleType: 'source_update', threshold: null });
    expect(screen.getByTestId('screening-reminder-panel-v104')).toHaveTextContent('user-defined condition');
  });
});
