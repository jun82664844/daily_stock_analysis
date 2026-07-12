import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import BoostPackCardV112 from '../BoostPackCardV112';

describe('BoostPackCardV112', () => {
  it('shows fixed price, quotas and expiry before purchase', () => {
    const onPurchase = vi.fn();
    render(<BoostPackCardV112 language="zh" product={{ productCode: 'api_boost_168_28', priceHkd: 28, flash: 168, pro: 28, balance: { flash: 10, pro: 2 }, expiresAt: '2026-08-12T10:00:00', canPurchase: true }} onPurchase={onPurchase} />);
    expect(screen.getByText('HK$28')).toBeInTheDocument();
    expect(screen.getByText(/168 Flash \+ 28 Pro/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: '购买加油包' }));
    expect(onPurchase).toHaveBeenCalled();
  });
});
