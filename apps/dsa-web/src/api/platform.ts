import apiClient from './index';
import { toCamelCase } from './utils';

export const PLATFORM_SESSION_CHANGED_EVENT = 'dsa-platform-session-changed';

function emitPlatformSessionChanged(): void {
  if (typeof window !== 'undefined') {
    window.dispatchEvent(new Event(PLATFORM_SESSION_CHANGED_EVENT));
  }
}

export type PlatformPlan = 'free' | 'pro' | 'premium' | 'enterprise';

export interface PlatformUser {
  id: number;
  email: string;
  role: 'user' | 'admin' | string;
  plan: PlatformPlan | string;
  status: 'active' | string;
}

export interface PlatformQuota {
  userId: number;
  plan: PlatformPlan | string;
  weeklyLimit: number | null;
  used: number;
  remaining: number | null;
  periodStart: string;
}

export interface PlatformAuthPayload {
  user: PlatformUser;
  quota: PlatformQuota;
}

export interface PlatformAdminUsersResponse {
  users: PlatformUser[];
}

export interface PlatformUsageBucket {
  userId: number;
  email: string;
  plan: PlatformPlan | string;
  quotaBucket: string;
  used: number;
  weeklyLimit: number | null;
  remaining: number | null;
  periodStart: string;
}

export interface PlatformAuditEvent {
  id?: number | null;
  userId?: number | null;
  action: string;
  metadata?: Record<string, unknown> | null;
  createdAt?: string | null;
}

export interface PlatformAdminUsageResponse {
  usage: PlatformUsageBucket[];
  auditEvents: PlatformAuditEvent[];
}

export interface PlatformApiKeyItem {
  id?: number | null;
  provider: string;
  model?: string | null;
  maskedKey: string;
  enabled: boolean;
  createdAt?: string | null;
  updatedAt?: string | null;
}

export interface PlatformQuotaBucket extends PlatformQuota {
  quotaBucket: string;
}

export interface PlatformAccountSummary extends PlatformAuthPayload {
  quotaBuckets: PlatformQuotaBucket[];
  apiKeys: PlatformApiKeyItem[];
  recommendedQueryMode: 'platform' | 'user' | 'local' | string;
}

export interface BillingCheckoutSession {
  id?: number | null;
  userId?: number | null;
  checkoutUrl: string;
  providerSessionId: string;
  provider: 'sandbox' | string;
  plan: PlatformPlan | string;
  status?: string | null;
  mode?: string | null;
  createdAt?: string | null;
  updatedAt?: string | null;
}

export interface PlatformBillingSubscription {
  userId: number;
  provider: 'sandbox' | string;
  providerSubscriptionId?: string | null;
  plan: PlatformPlan | string;
  status: string;
  createdAt?: string | null;
  updatedAt?: string | null;
}

export interface PlatformBillingEvent {
  id?: number | null;
  userId?: number | null;
  email?: string | null;
  provider: 'sandbox' | string;
  providerEventId: string;
  providerSessionId?: string | null;
  eventType: string;
  plan?: PlatformPlan | string | null;
  processingStatus?: string | null;
  metadata?: Record<string, unknown> | null;
  createdAt?: string | null;
  updatedAt?: string | null;
}

export interface PlatformBillingAccountResponse {
  billingEnabled: boolean;
  provider: 'sandbox' | string;
  mode: string;
  copy: string;
  subscription: PlatformBillingSubscription;
  checkoutSessions: BillingCheckoutSession[];
  recentEvents: PlatformBillingEvent[];
}

export interface PlatformAdminBillingEventsResponse {
  events: PlatformBillingEvent[];
}

export interface PlatformLocalStatusResponse {
  mode: string;
  aiUsed: boolean;
  generatedAt?: string | null;
  service: {
    webui: string;
    host: string;
    port: number;
  };
  auth: {
    platformUserAuthEnabled: boolean;
    adminAuthEnabled: boolean;
    csrfEnabled?: boolean;
  };
  billing: {
    enabled: boolean;
    provider: string;
    mode: string;
  };
  ai: {
    defaultModel?: string | null;
    agentModel?: string | null;
    localModelEnabled: boolean;
    localModelMaxConcurrent?: number | null;
    byokSupported: boolean;
    publicSearchEnabled: boolean;
  };
  market: {
    summary: {
      laneCount?: number;
      sourceCount?: number;
      degradedSourceCount?: number;
      [key: string]: unknown;
    };
    cache: Record<string, string | number | boolean | null>;
    lanes: unknown[];
  };
  safety: {
    noAiStatus: boolean;
    secretsRedacted: boolean;
    realPaymentEnabled: boolean;
    localOnly?: boolean;
  };
}

export interface PlatformWatchlistItem {
  id?: number | null;
  stockCode: string;
  inputCode?: string | null;
  market: string;
  createdAt?: string | null;
  updatedAt?: string | null;
}

export interface PlatformWatchlistResponse {
  userId: number;
  items: PlatformWatchlistItem[];
  total: number;
  aiUsed: boolean;
}

export interface PlatformWatchlistRefreshItem {
  stockCode: string;
  stockName?: string | null;
  market: string;
  routeLane?: string | null;
  currentPrice?: number | null;
  changePercent?: number | null;
  freshness: string;
  degradationStatus: string;
  warningCodes: string[];
  aiUsed: boolean;
  status: string;
}

export interface PlatformWatchlistRefreshResponse {
  userId: number;
  requested: number;
  refreshed: number;
  degraded: number;
  items: PlatformWatchlistRefreshItem[];
  aiUsed: boolean;
}

export const platformApi = {
  status: async (): Promise<{ platformAuthEnabled: boolean }> => {
    const response = await apiClient.get<Record<string, unknown>>('/api/v1/platform/status');
    return toCamelCase<{ platformAuthEnabled: boolean }>(response.data);
  },

  register: async (email: string, password: string): Promise<PlatformAuthPayload> => {
    const response = await apiClient.post<Record<string, unknown>>('/api/v1/platform/register', {
      email,
      password,
    });
    emitPlatformSessionChanged();
    return toCamelCase<PlatformAuthPayload>(response.data);
  },

  login: async (email: string, password: string): Promise<PlatformAuthPayload> => {
    const response = await apiClient.post<Record<string, unknown>>('/api/v1/platform/login', {
      email,
      password,
    });
    emitPlatformSessionChanged();
    return toCamelCase<PlatformAuthPayload>(response.data);
  },

  logout: async (): Promise<void> => {
    await apiClient.post('/api/v1/platform/logout');
    emitPlatformSessionChanged();
  },

  me: async (): Promise<PlatformAuthPayload> => {
    const response = await apiClient.get<Record<string, unknown>>('/api/v1/platform/me');
    return toCamelCase<PlatformAuthPayload>(response.data);
  },

  current: async (): Promise<PlatformAuthPayload | null> => {
    const response = await apiClient.get<Record<string, unknown>>('/api/v1/platform/me', {
      validateStatus: (status) => status === 200 || status === 401,
    });
    if (response.status === 401) {
      return null;
    }
    return toCamelCase<PlatformAuthPayload>(response.data);
  },

  quota: async (): Promise<PlatformQuota> => {
    const response = await apiClient.get<Record<string, unknown>>('/api/v1/platform/quota');
    return toCamelCase<PlatformQuota>(response.data);
  },

  account: async (): Promise<PlatformAccountSummary> => {
    const response = await apiClient.get<Record<string, unknown>>('/api/v1/platform/account');
    return toCamelCase<PlatformAccountSummary>(response.data);
  },

  watchlist: async (): Promise<PlatformWatchlistResponse> => {
    const response = await apiClient.get<Record<string, unknown>>('/api/v1/platform/watchlist');
    return toCamelCase<PlatformWatchlistResponse>(response.data);
  },

  addWatchlistItem: async (stockCode: string): Promise<PlatformWatchlistResponse> => {
    const response = await apiClient.post<Record<string, unknown>>('/api/v1/platform/watchlist', { stockCode });
    return toCamelCase<PlatformWatchlistResponse>(response.data);
  },

  removeWatchlistItem: async (stockCode: string): Promise<PlatformWatchlistResponse> => {
    const response = await apiClient.delete<Record<string, unknown>>(
      `/api/v1/platform/watchlist/${encodeURIComponent(stockCode)}`,
    );
    return toCamelCase<PlatformWatchlistResponse>(response.data);
  },

  refreshWatchlist: async (): Promise<PlatformWatchlistRefreshResponse> => {
    const response = await apiClient.post<Record<string, unknown>>('/api/v1/platform/watchlist/refresh');
    return toCamelCase<PlatformWatchlistRefreshResponse>(response.data);
  },

  listApiKeys: async (): Promise<PlatformApiKeyItem[]> => {
    const response = await apiClient.get<Record<string, unknown>[]>('/api/v1/platform/api-keys');
    return toCamelCase<PlatformApiKeyItem[]>(response.data);
  },

  saveApiKey: async (data: { provider: string; apiKey: string; model?: string | null }): Promise<PlatformApiKeyItem> => {
    const response = await apiClient.post<Record<string, unknown>>('/api/v1/platform/api-keys', data);
    return toCamelCase<PlatformApiKeyItem>(response.data);
  },

  createSandboxCheckout: async (plan: PlatformPlan): Promise<BillingCheckoutSession> => {
    const response = await apiClient.post<Record<string, unknown>>('/api/v1/billing/checkout', { plan });
    return toCamelCase<BillingCheckoutSession>(response.data);
  },

  billingAccount: async (): Promise<PlatformBillingAccountResponse> => {
    const response = await apiClient.get<Record<string, unknown>>('/api/v1/billing/account');
    return toCamelCase<PlatformBillingAccountResponse>(response.data);
  },

  adminUsers: async (): Promise<PlatformAdminUsersResponse> => {
    const response = await apiClient.get<Record<string, unknown>>('/api/v1/platform/admin/users');
    return toCamelCase<PlatformAdminUsersResponse>(response.data);
  },

  adminUsage: async (): Promise<PlatformAdminUsageResponse> => {
    const response = await apiClient.get<Record<string, unknown>>('/api/v1/platform/admin/usage');
    return toCamelCase<PlatformAdminUsageResponse>(response.data);
  },
  adminBillingEvents: async (): Promise<PlatformAdminBillingEventsResponse> => {
    const response = await apiClient.get<Record<string, unknown>>('/api/v1/billing/admin/events');
    return toCamelCase<PlatformAdminBillingEventsResponse>(response.data);
  },
  adminLocalStatus: async (): Promise<PlatformLocalStatusResponse> => {
    const response = await apiClient.get<Record<string, unknown>>('/api/v1/platform/admin/local-status');
    return toCamelCase<PlatformLocalStatusResponse>(response.data);
  },
  updateUserPlan: async (userId: number, plan: PlatformPlan): Promise<PlatformAuthPayload> => {
    const response = await apiClient.patch<Record<string, unknown>>(
      `/api/v1/platform/admin/users/${encodeURIComponent(userId)}/plan`,
      { plan },
    );
    return toCamelCase<PlatformAuthPayload>(response.data);
  },
};
