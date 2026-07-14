import apiClient from './index';
import { toCamelCase } from './utils';

export const SUPPORT_INBOX_CHANGED_EVENT = 'dsa-support-inbox-changed';

export type SupportCategory = 'account' | 'market_data' | 'model' | 'report' | 'alerts' | 'subscription' | 'bug' | 'other';
export type SupportStatus = 'open' | 'in_progress' | 'closed';

export interface SupportMessage {
  id: number;
  ticketId: number;
  authorRole: 'user' | 'admin';
  body: string;
  createdAt: string | null;
}

export interface SupportTicketSummary {
  id: number;
  userId: number;
  requesterEmail: string | null;
  category: SupportCategory;
  subject: string;
  status: SupportStatus;
  unreadByUser: boolean;
  unreadByAdmin: boolean;
  messageCount: number;
  createdAt: string | null;
  updatedAt: string | null;
  closedAt: string | null;
}

export interface SupportTicketDetail extends SupportTicketSummary {
  messages: SupportMessage[];
}

export interface SupportTicketList {
  tickets: SupportTicketSummary[];
  total: number;
}

export interface SupportTicketCreateInput {
  category: SupportCategory;
  subject: string;
  message: string;
}

export interface SupportUserSummary {
  unreadCount: number;
  activeCount: number;
}

export interface SupportAdminSummary {
  unreadCount: number;
  pendingCount: number;
  oldestPendingAt: string | null;
}

interface SupportTicketEnvelope {
  ticket: SupportTicketDetail;
}

function ticketFromEnvelope(data: unknown): SupportTicketDetail {
  return toCamelCase<SupportTicketEnvelope>(data).ticket;
}

function emitSupportInboxChanged(): void {
  if (typeof window !== 'undefined') {
    window.dispatchEvent(new Event(SUPPORT_INBOX_CHANGED_EVENT));
  }
}

export const supportApi = {
  async listTickets(): Promise<SupportTicketList> {
    const response = await apiClient.get('/api/v1/support/tickets');
    return toCamelCase<SupportTicketList>(response.data);
  },

  async getTicket(ticketId: number): Promise<SupportTicketDetail> {
    const response = await apiClient.get(`/api/v1/support/tickets/${ticketId}`);
    const ticket = ticketFromEnvelope(response.data);
    emitSupportInboxChanged();
    return ticket;
  },

  async createTicket(input: SupportTicketCreateInput): Promise<SupportTicketDetail> {
    const response = await apiClient.post('/api/v1/support/tickets', input);
    const ticket = ticketFromEnvelope(response.data);
    emitSupportInboxChanged();
    return ticket;
  },

  async addMessage(ticketId: number, message: string): Promise<SupportTicketDetail> {
    const response = await apiClient.post(`/api/v1/support/tickets/${ticketId}/messages`, { message });
    const ticket = ticketFromEnvelope(response.data);
    emitSupportInboxChanged();
    return ticket;
  },

  async closeTicket(ticketId: number): Promise<SupportTicketDetail> {
    const response = await apiClient.post(`/api/v1/support/tickets/${ticketId}/close`);
    const ticket = ticketFromEnvelope(response.data);
    emitSupportInboxChanged();
    return ticket;
  },

  async getSummary(): Promise<SupportUserSummary> {
    const response = await apiClient.get('/api/v1/support/summary');
    return toCamelCase<SupportUserSummary>(response.data);
  },

  async adminListTickets(status?: SupportStatus | 'all'): Promise<SupportTicketList> {
    const params = status && status !== 'all' ? { status } : undefined;
    const response = params
      ? await apiClient.get('/api/v1/support/admin/tickets', { params })
      : await apiClient.get('/api/v1/support/admin/tickets');
    return toCamelCase<SupportTicketList>(response.data);
  },

  async adminGetTicket(ticketId: number): Promise<SupportTicketDetail> {
    const response = await apiClient.get(`/api/v1/support/admin/tickets/${ticketId}`);
    const ticket = ticketFromEnvelope(response.data);
    emitSupportInboxChanged();
    return ticket;
  },

  async adminAddMessage(ticketId: number, message: string): Promise<SupportTicketDetail> {
    const response = await apiClient.post(`/api/v1/support/admin/tickets/${ticketId}/messages`, { message });
    const ticket = ticketFromEnvelope(response.data);
    emitSupportInboxChanged();
    return ticket;
  },

  async adminUpdateStatus(ticketId: number, status: SupportStatus): Promise<SupportTicketDetail> {
    const response = await apiClient.patch(`/api/v1/support/admin/tickets/${ticketId}/status`, { status });
    const ticket = ticketFromEnvelope(response.data);
    emitSupportInboxChanged();
    return ticket;
  },

  async adminGetSummary(): Promise<SupportAdminSummary> {
    const response = await apiClient.get('/api/v1/support/admin/summary');
    return toCamelCase<SupportAdminSummary>(response.data);
  },
};
