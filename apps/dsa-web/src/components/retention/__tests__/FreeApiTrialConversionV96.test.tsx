import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { FreeApiTrialConversionV96 } from '../FreeApiTrialConversionV96';

describe('FreeApiTrialConversionV96', () => {
  it('explains the premium API choices after the free report opens', () => {
    render(<FreeApiTrialConversionV96 language="en" onExplorePremium={() => undefined} />);

    expect(screen.getByTestId('free-api-trial-conversion-v96')).toHaveTextContent('Free trial report opened');
    expect(screen.getByTestId('free-api-trial-conversion-v96')).toHaveTextContent('Platform API');
    expect(screen.getByTestId('free-api-trial-conversion-v96')).toHaveTextContent('Your API');
    expect(screen.getByTestId('free-api-trial-conversion-v96')).toHaveTextContent('Local model');
    expect(screen.getByTestId('free-api-trial-conversion-v96')).toHaveTextContent('real payment remains disabled');
  });

  it('opens the premium account entry', () => {
    const onExplorePremium = vi.fn();
    render(<FreeApiTrialConversionV96 language="zh" onExplorePremium={onExplorePremium} />);

    fireEvent.click(screen.getByTestId('free-api-trial-upgrade'));
    expect(onExplorePremium).toHaveBeenCalledOnce();
    expect(screen.getByTestId('free-api-trial-upgrade')).toHaveTextContent('查看高级功能');
  });
});
