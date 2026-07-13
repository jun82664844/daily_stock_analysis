import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it, vi } from 'vitest';
import { UiLanguageProvider } from '../../../contexts/UiLanguageContext';
import { ShellHeader } from '../ShellHeader';
import { UI_LANGUAGE_STORAGE_KEY } from '../../../utils/uiLanguage';

vi.mock('../../alerts/PriceAlertInboxV116', () => ({
  default: ({ language }: { language: string }) => <div data-testid="price-alert-inbox">{language}</div>,
}));
vi.mock('../../theme/ThemeToggle', () => ({ ThemeToggle: () => <div data-testid="theme-toggle" /> }));

describe('ShellHeader', () => {
  it('keeps the private price-alert inbox in the global header', () => {
    window.localStorage.setItem(UI_LANGUAGE_STORAGE_KEY, 'zh');
    render(
      <MemoryRouter initialEntries={['/market']}>
        <UiLanguageProvider>
          <ShellHeader collapsed={false} onToggleSidebar={vi.fn()} onOpenMobileNav={vi.fn()} />
        </UiLanguageProvider>
      </MemoryRouter>,
    );
    expect(screen.getByTestId('price-alert-inbox')).toHaveTextContent('zh');
    expect(screen.getByText('市场')).toBeInTheDocument();
  });
});
