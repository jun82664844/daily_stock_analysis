import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { supportApi, type SupportTicketDetail, type SupportTicketSummary } from '../../../api/support';
import SupportWorkbenchV120 from '../SupportWorkbenchV120';

vi.mock('../../../api/support', () => ({
  supportApi: {
    adminListTickets: vi.fn(),
    adminGetTicket: vi.fn(),
    adminAddMessage: vi.fn(),
    adminUpdateStatus: vi.fn(),
  },
}));

const summary: SupportTicketSummary = {
  id: 12,
  userId: 7,
  requesterEmail: 'user@example.com',
  category: 'market_data',
  subject: 'Quote freshness question',
  status: 'open',
  unreadByUser: false,
  unreadByAdmin: true,
  messageCount: 1,
  createdAt: '2026-07-14T08:00:00',
  updatedAt: '2026-07-14T08:00:00',
  closedAt: null,
};

const detail: SupportTicketDetail = {
  ...summary,
  messages: [{ id: 1, ticketId: 12, authorRole: 'user', body: 'The quote timestamp appears old.', createdAt: '2026-07-14T08:00:00' }],
};

describe('SupportWorkbenchV120', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(supportApi.adminListTickets).mockResolvedValue({ tickets: [summary], total: 1 });
    vi.mocked(supportApi.adminGetTicket).mockResolvedValue(detail);
    vi.mocked(supportApi.adminAddMessage).mockResolvedValue({ ...detail, status: 'in_progress', messages: [...detail.messages, { id: 2, ticketId: 12, authorRole: 'admin', body: 'We are checking the source.', createdAt: '2026-07-14T08:10:00' }] });
    vi.mocked(supportApi.adminUpdateStatus).mockResolvedValue({ ...detail, status: 'closed', closedAt: '2026-07-14T08:20:00' });
  });

  it('loads the queue and lets an administrator reply and close a ticket', async () => {
    render(<SupportWorkbenchV120 />);

    expect(await screen.findByRole('heading', { name: '客服工单' })).toBeInTheDocument();
    expect(screen.getByText('user@example.com')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /Quote freshness question/ }));
    expect(await screen.findByText('The quote timestamp appears old.')).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText('管理员回复'), { target: { value: 'We are checking the source.' } });
    fireEvent.click(screen.getByRole('button', { name: '发送回复' }));
    await waitFor(() => expect(supportApi.adminAddMessage).toHaveBeenCalledWith(12, 'We are checking the source.'));

    fireEvent.click(screen.getByRole('button', { name: '标记已关闭' }));
    await waitFor(() => expect(supportApi.adminUpdateStatus).toHaveBeenCalledWith(12, 'closed'));
  });

  it('filters the queue by status', async () => {
    render(<SupportWorkbenchV120 />);
    await screen.findByRole('heading', { name: '客服工单' });

    fireEvent.change(screen.getByLabelText('工单状态'), { target: { value: 'in_progress' } });

    await waitFor(() => expect(supportApi.adminListTickets).toHaveBeenLastCalledWith('in_progress'));
  });
});
