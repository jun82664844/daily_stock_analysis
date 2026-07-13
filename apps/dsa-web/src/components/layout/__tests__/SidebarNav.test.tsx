import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { SidebarNav } from '../SidebarNav';

const mockLogout = vi.fn().mockResolvedValue(undefined);
const mockGetAlphaSiftStatus = vi.fn().mockResolvedValue({ enabled: false, available: false, installSpecIsDefault: false });
const mockPlatformCurrent = vi.fn().mockResolvedValue(null);
const mockThemeToggle = vi.fn(({ collapsed }: { collapsed?: boolean }) => (
  <button type="button">{collapsed ? '切换主题(折叠)' : '切换主题'}</button>
));

const authState = { authEnabled: true, loggedIn: false };
const completionBadgeState = { value: true };

vi.mock('../../../contexts/AuthContext', () => ({
  useAuth: () => ({
    authEnabled: authState.authEnabled,
    loggedIn: authState.loggedIn,
    logout: mockLogout,
  }),
}));

vi.mock('../../../stores/agentChatStore', () => ({
  useAgentChatStore: (selector: (state: { completionBadge: boolean }) => unknown) =>
    selector({ completionBadge: completionBadgeState.value }),
}));

vi.mock('../../../api/alphasift', () => ({
  ALPHASIFT_CONFIG_CHANGED_EVENT: 'alphasift-config-changed',
  SYSTEM_CONFIG_CHANGED_EVENT: 'dsa-system-config-changed',
  alphasiftApi: {
    getStatus: () => mockGetAlphaSiftStatus(),
  },
}));

vi.mock('../../../api/platform', () => ({
  PLATFORM_SESSION_CHANGED_EVENT: 'dsa-platform-session-changed',
  platformApi: {
    current: () => mockPlatformCurrent(),
  },
}));

vi.mock('../../theme/ThemeToggle', () => ({
  ThemeToggle: (props: { collapsed?: boolean }) => mockThemeToggle(props),
}));

describe('SidebarNav', () => {
  beforeEach(() => {
    mockPlatformCurrent.mockResolvedValue(null);
    completionBadgeState.value = true;
    authState.authEnabled = true;
    authState.loggedIn = false;
  });

  it('keeps market screening navigation visible while AlphaSift is disabled', async () => {
    mockGetAlphaSiftStatus.mockResolvedValueOnce({ enabled: false, available: false, installSpecIsDefault: false });

    render(
      <MemoryRouter initialEntries={['/']}>
        <SidebarNav />
      </MemoryRouter>,
    );

    expect(await screen.findByRole('link', { name: '市场筛选' })).toHaveAttribute('href', '/screening');
  });

  it('shows the screening navigation item when AlphaSift is enabled', async () => {
    mockGetAlphaSiftStatus.mockResolvedValueOnce({ enabled: true, available: false, installSpecIsDefault: false });

    render(
      <MemoryRouter initialEntries={['/']}>
        <SidebarNav />
      </MemoryRouter>,
    );

    expect(await screen.findByRole('link', { name: '市场筛选' })).toHaveAttribute('href', '/screening');
  });

  it('places screening after the public market workspace when AlphaSift is enabled', async () => {
    mockGetAlphaSiftStatus.mockResolvedValueOnce({ enabled: true, available: false, installSpecIsDefault: false });

    render(
      <MemoryRouter initialEntries={['/']}>
        <SidebarNav />
      </MemoryRouter>,
    );

    await screen.findByRole('link', { name: '市场筛选' });
    const hrefs = screen.getAllByRole('link').map((link) => link.getAttribute('href'));
    expect(hrefs.slice(0, 6)).toEqual(['/', '/chat', '/market', '/screening', '/research', '/portfolio']);
  });

  it('does not hide market screening navigation after a config save event', async () => {
    mockGetAlphaSiftStatus
      .mockResolvedValueOnce({ enabled: false, available: false, installSpecIsDefault: false })
      .mockResolvedValueOnce({ enabled: true, available: false, installSpecIsDefault: false });

    render(
      <MemoryRouter initialEntries={['/']}>
        <SidebarNav />
      </MemoryRouter>,
    );

    expect(await screen.findByRole('link', { name: '市场筛选' })).toHaveAttribute('href', '/screening');
    window.dispatchEvent(new Event('dsa-system-config-changed'));

    expect(screen.getByRole('link', { name: '市场筛选' })).toHaveAttribute('href', '/screening');
  });

  it('shows the shared completion badge only when chat completion is pending', () => {
    completionBadgeState.value = true;

    const { rerender } = render(
      <MemoryRouter initialEntries={['/chat']}>
        <SidebarNav />
      </MemoryRouter>,
    );

    expect(screen.getByTestId('chat-completion-badge')).toBeInTheDocument();
    expect(screen.getByLabelText('问股有新消息')).toBeInTheDocument();

    completionBadgeState.value = false;
    rerender(
      <MemoryRouter initialEntries={['/chat']}>
        <SidebarNav />
      </MemoryRouter>,
    );

    expect(screen.queryByTestId('chat-completion-badge')).not.toBeInTheDocument();
  });

  it('renders the collapsed theme toggle variant when the sidebar is collapsed', () => {
    render(
      <MemoryRouter initialEntries={['/']}>
        <SidebarNav collapsed />
      </MemoryRouter>,
    );

    expect(mockThemeToggle).toHaveBeenCalledWith(
      expect.objectContaining({ variant: 'nav', collapsed: true }),
    );
    expect(screen.getByRole('button', { name: '切换主题(折叠)' })).toBeInTheDocument();
  });

  it('renders the alerts navigation item and marks it active', () => {
    render(
      <MemoryRouter initialEntries={['/alerts']}>
        <SidebarNav />
      </MemoryRouter>,
    );

    const alertsLink = screen.getByRole('link', { name: '告警' });
    expect(alertsLink).toHaveAttribute('href', '/alerts');
    expect(alertsLink).toHaveClass('font-medium');
  });

  it('renders the admin operations navigation item', async () => {
    authState.loggedIn = true;

    render(
      <MemoryRouter initialEntries={['/admin']}>
        <SidebarNav />
      </MemoryRouter>,
    );

    await waitFor(() => {
      const hrefs = screen.getAllByRole('link').map((link) => link.getAttribute('href'));
      expect(hrefs).toContain('/admin');
    });
  });

  it('shows the public research center directly after market screening', async () => {
    render(
      <MemoryRouter initialEntries={['/research']}>
        <SidebarNav />
      </MemoryRouter>,
    );

    const researchLink = await screen.findByRole('link', { name: '研究中心' });
    expect(researchLink).toHaveAttribute('href', '/research');
    expect(researchLink).toHaveClass('font-medium');
    const hrefs = screen.getAllByRole('link').map((link) => link.getAttribute('href'));
    expect(hrefs.slice(0, 5)).toEqual(['/', '/chat', '/market', '/screening', '/research']);
  });

  it('hides admin-only navigation and logout for public unauthenticated users', async () => {
    render(
      <MemoryRouter initialEntries={['/']}>
        <SidebarNav />
      </MemoryRouter>,
    );

    await waitFor(() => expect(mockPlatformCurrent).toHaveBeenCalled());
    const hrefs = screen.getAllByRole('link').map((link) => link.getAttribute('href'));
    expect(hrefs).not.toContain('/admin');
    expect(hrefs).not.toContain('/settings');
    expect(screen.queryByRole('button', { name: '閫€鍑?' })).not.toBeInTheDocument();
  });

  it('hides the admin operations navigation item for ordinary platform users', async () => {
    mockPlatformCurrent.mockResolvedValueOnce({
      user: { id: 2, email: 'user@example.com', role: 'user', plan: 'free', status: 'active' },
      quota: { userId: 2, plan: 'free', weeklyLimit: 5, used: 0, remaining: 5, periodStart: '2026-06-29' },
    });

    render(
      <MemoryRouter initialEntries={['/account']}>
        <SidebarNav />
      </MemoryRouter>,
    );

    await waitFor(() => {
      const hrefs = screen.getAllByRole('link').map((link) => link.getAttribute('href'));
      expect(hrefs).not.toContain('/admin');
    });
  });

  it('refreshes platform role after a platform session change event', async () => {
    authState.loggedIn = true;
    mockPlatformCurrent
      .mockResolvedValueOnce(null)
      .mockResolvedValueOnce({
        user: { id: 2, email: 'user@example.com', role: 'user', plan: 'free', status: 'active' },
        quota: { userId: 2, plan: 'free', weeklyLimit: 5, used: 0, remaining: 5, periodStart: '2026-06-29' },
      });

    render(
      <MemoryRouter initialEntries={['/account']}>
        <SidebarNav />
      </MemoryRouter>,
    );

    await waitFor(() => {
      const hrefs = screen.getAllByRole('link').map((link) => link.getAttribute('href'));
      expect(hrefs).toContain('/admin');
    });

    window.dispatchEvent(new Event('dsa-platform-session-changed'));

    await waitFor(() => {
      const hrefs = screen.getAllByRole('link').map((link) => link.getAttribute('href'));
      expect(hrefs).not.toContain('/admin');
    });
  });

  it('renders the AI signals navigation item and marks it active', () => {
    render(
      <MemoryRouter initialEntries={['/decision-signals']}>
        <SidebarNav />
      </MemoryRouter>,
    );

    const signalsLink = screen.getByRole('link', { name: 'AI 建议' });
    expect(signalsLink).toHaveAttribute('href', '/decision-signals');
    expect(signalsLink).toHaveClass('font-medium');
  });

  it('opens the logout confirmation and confirms logout', async () => {
    authState.loggedIn = true;

    render(
      <MemoryRouter initialEntries={['/chat']}>
        <SidebarNav />
      </MemoryRouter>,
    );

    fireEvent.click(screen.getByRole('button', { name: '退出' }));

    expect(await screen.findByRole('heading', { name: '退出登录' })).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: '确认退出' }));
    expect(mockLogout).toHaveBeenCalled();
  });
});
