import { beforeEach, describe, expect, it, vi } from 'vitest';
import apiClient from '../index';
import { supportApi } from '../support';

vi.mock('../index', () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
    patch: vi.fn(),
  },
}));

const ticketPayload = {
  id: 12,
  user_id: 7,
  requester_email: 'user@example.com',
  category: 'market_data',
  subject: 'Quote freshness question',
  status: 'open',
  unread_by_user: false,
  unread_by_admin: true,
  message_count: 1,
  created_at: '2026-07-14T08:00:00',
  updated_at: '2026-07-14T08:00:00',
  closed_at: null,
  messages: [{
    id: 1,
    ticket_id: 12,
    author_role: 'user',
    body: 'The quote timestamp appears old.',
    created_at: '2026-07-14T08:00:00',
  }],
};

describe('supportApi', () => {
  beforeEach(() => vi.clearAllMocks());

  it('maps user ticket responses to camelCase', async () => {
    vi.mocked(apiClient.get).mockResolvedValue({ data: { tickets: [ticketPayload], total: 1 } });

    const response = await supportApi.listTickets();

    expect(apiClient.get).toHaveBeenCalledWith('/api/v1/support/tickets');
    expect(response.tickets[0].userId).toBe(7);
    expect(response.tickets[0].unreadByAdmin).toBe(true);
    expect(response.tickets[0].messageCount).toBe(1);
  });

  it('creates, replies to, and closes a user ticket', async () => {
    vi.mocked(apiClient.post).mockResolvedValue({ data: { ticket: ticketPayload } });

    await supportApi.createTicket({ category: 'market_data', subject: 'Quote freshness question', message: 'The quote timestamp appears old.' });
    await supportApi.addMessage(12, 'Still reproducible.');
    const closed = await supportApi.closeTicket(12);

    expect(apiClient.post).toHaveBeenNthCalledWith(1, '/api/v1/support/tickets', {
      category: 'market_data',
      subject: 'Quote freshness question',
      message: 'The quote timestamp appears old.',
    });
    expect(apiClient.post).toHaveBeenNthCalledWith(2, '/api/v1/support/tickets/12/messages', { message: 'Still reproducible.' });
    expect(apiClient.post).toHaveBeenNthCalledWith(3, '/api/v1/support/tickets/12/close');
    expect(closed.userId).toBe(7);
  });

  it('loads and updates the administrator queue', async () => {
    vi.mocked(apiClient.get).mockResolvedValue({ data: { tickets: [ticketPayload], total: 1 } });
    vi.mocked(apiClient.post).mockResolvedValue({ data: { ticket: ticketPayload } });
    vi.mocked(apiClient.patch).mockResolvedValue({ data: { ticket: { ...ticketPayload, status: 'closed' } } });

    const queue = await supportApi.adminListTickets('open');
    await supportApi.adminAddMessage(12, 'We are checking the source.');
    const updated = await supportApi.adminUpdateStatus(12, 'closed');

    expect(apiClient.get).toHaveBeenCalledWith('/api/v1/support/admin/tickets', { params: { status: 'open' } });
    expect(apiClient.post).toHaveBeenCalledWith('/api/v1/support/admin/tickets/12/messages', { message: 'We are checking the source.' });
    expect(apiClient.patch).toHaveBeenCalledWith('/api/v1/support/admin/tickets/12/status', { status: 'closed' });
    expect(queue.tickets[0].requesterEmail).toBe('user@example.com');
    expect(updated.status).toBe('closed');
  });
});
