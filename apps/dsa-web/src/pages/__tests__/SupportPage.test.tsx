import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { supportApi, type SupportTicketDetail, type SupportTicketSummary } from '../../api/support';
import { platformApi } from '../../api/platform';
import SupportPage from '../SupportPage';

vi.mock('../../api/support', () => ({
  supportApi: {
    listTickets: vi.fn(),
    getTicket: vi.fn(),
    createTicket: vi.fn(),
    addMessage: vi.fn(),
    closeTicket: vi.fn(),
  },
}));

vi.mock('../../api/platform', () => ({
  platformApi: { current: vi.fn() },
}));

const summary: SupportTicketSummary = {
  id: 12,
  userId: 7,
  requesterEmail: 'user@example.com',
  category: 'market_data',
  subject: 'Quote freshness question',
  status: 'open',
  unreadByUser: true,
  unreadByAdmin: false,
  messageCount: 2,
  createdAt: '2026-07-14T08:00:00',
  updatedAt: '2026-07-14T08:10:00',
  closedAt: null,
};

const detail: SupportTicketDetail = {
  ...summary,
  messages: [
    { id: 1, ticketId: 12, authorRole: 'user', body: 'The quote timestamp appears old.', createdAt: '2026-07-14T08:00:00' },
    { id: 2, ticketId: 12, authorRole: 'admin', body: 'We are checking the public source.', createdAt: '2026-07-14T08:10:00' },
  ],
};

function renderPage() {
  return render(<MemoryRouter><SupportPage /></MemoryRouter>);
}

describe('SupportPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(platformApi.current).mockResolvedValue({
      user: { id: 7, email: 'user@example.com', role: 'user', plan: 'free', status: 'active' },
      quota: { userId: 7, plan: 'free', weeklyLimit: 5, used: 0, remaining: 5, periodStart: '2026-07-13' },
    });
    vi.mocked(supportApi.listTickets).mockResolvedValue({ tickets: [summary], total: 1 });
    vi.mocked(supportApi.getTicket).mockResolvedValue(detail);
    vi.mocked(supportApi.createTicket).mockResolvedValue(detail);
    vi.mocked(supportApi.addMessage).mockResolvedValue({ ...detail, messageCount: 3, messages: [...detail.messages, { id: 3, ticketId: 12, authorRole: 'user', body: 'Still reproducible.', createdAt: '2026-07-14T08:20:00' }] });
    vi.mocked(supportApi.closeTicket).mockResolvedValue({ ...detail, status: 'closed', closedAt: '2026-07-14T08:30:00' });
  });

  it('shows a login boundary when no platform user is signed in', async () => {
    vi.mocked(platformApi.current).mockResolvedValue(null);
    renderPage();

    expect(await screen.findByRole('heading', { name: '登录后联系客服' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: '前往登录' })).toHaveAttribute('href', '/');
    expect(supportApi.listTickets).not.toHaveBeenCalled();
  });

  it('creates a categorized support ticket', async () => {
    vi.mocked(supportApi.listTickets).mockResolvedValueOnce({ tickets: [], total: 0 });
    renderPage();
    await screen.findByRole('heading', { name: '客服中心' });

    fireEvent.change(screen.getByLabelText('问题分类'), { target: { value: 'bug' } });
    fireEvent.change(screen.getByLabelText('问题主题'), { target: { value: 'Browser page did not load' } });
    fireEvent.change(screen.getByLabelText('问题描述'), { target: { value: 'The page stayed blank after refresh.' } });
    fireEvent.click(screen.getByRole('button', { name: '提交工单' }));

    await waitFor(() => expect(supportApi.createTicket).toHaveBeenCalledWith({
      category: 'bug',
      subject: 'Browser page did not load',
      message: 'The page stayed blank after refresh.',
    }));
  });

  it('opens the thread, replies, and closes the ticket', async () => {
    renderPage();

    fireEvent.click(await screen.findByRole('button', { name: /Quote freshness question/ }));
    expect(await screen.findByText('We are checking the public source.')).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText('追加消息'), { target: { value: 'Still reproducible.' } });
    fireEvent.click(screen.getByRole('button', { name: '发送消息' }));
    await waitFor(() => expect(supportApi.addMessage).toHaveBeenCalledWith(12, 'Still reproducible.'));

    fireEvent.click(screen.getByRole('button', { name: '关闭工单' }));
    await waitFor(() => expect(supportApi.closeTicket).toHaveBeenCalledWith(12));
  });
});
