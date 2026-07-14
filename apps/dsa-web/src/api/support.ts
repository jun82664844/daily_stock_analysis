import apiClient from './index';
import { toCamelCase } from './utils';

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

interface SupportTicketEnvelope {
  ticket: SupportTicketDetail;
}

function ticketFromEnvelope(data: unknown): SupportTicketDetail {
  return toCamelCase<SupportTicketEnvelope>(data).ticket;
}

export const supportApi = {
  async listTickets(): Promise<SupportTicketList> {
    const response = await apiClient.get('/api/v1/support/tickets');
    return toCamelCase<SupportTicketList>(response.data);
  },

  async getTicket(ticketId: number): Promise<SupportTicketDetail> {
    const response = await apiClient.get(`/api/v1/support/tickets/${ticketId}`);
    return ticketFromEnvelope(response.data);
  },

  async createTicket(input: SupportTicketCreateInput): Promise<SupportTicketDetail> {
    const response = await apiClient.post('/api/v1/support/tickets', input);
    return ticketFromEnvelope(response.data);
  },

  async addMessage(ticketId: number, message: string): Promise<SupportTicketDetail> {
    const response = await apiClient.post(`/api/v1/support/tickets/${ticketId}/messages`, { message });
    return ticketFromEnvelope(response.data);
  },

  async closeTicket(ticketId: number): Promise<SupportTicketDetail> {
    const response = await apiClient.post(`/api/v1/support/tickets/${ticketId}/close`);
    return ticketFromEnvelope(response.data);
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
    return ticketFromEnvelope(response.data);
  },

  async adminAddMessage(ticketId: number, message: string): Promise<SupportTicketDetail> {
    const response = await apiClient.post(`/api/v1/support/admin/tickets/${ticketId}/messages`, { message });
    return ticketFromEnvelope(response.data);
  },

  async adminUpdateStatus(ticketId: number, status: SupportStatus): Promise<SupportTicketDetail> {
    const response = await apiClient.patch(`/api/v1/support/admin/tickets/${ticketId}/status`, { status });
    return ticketFromEnvelope(response.data);
  },
};
