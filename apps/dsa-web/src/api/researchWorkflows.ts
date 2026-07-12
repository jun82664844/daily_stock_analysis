import apiClient from './index';
import { toCamelCase } from './utils';

export type FinancialResearchFact = {
  code: string;
  labelZh: string;
  labelEn: string;
  value: unknown;
  detail?: string | null;
  unit: string;
  currency?: string | null;
  source: string;
  freshness: string;
  asOf?: string | null;
};

export type FinancialResearchWorkflow = {
  id: string;
  titleZh: string;
  titleEn: string;
  purposeZh: string;
  purposeEn: string;
  status: 'available' | 'partial';
  sourceReference: string;
  facts: FinancialResearchFact[];
  missingData: string[];
  aiUsed: boolean;
  publicSearchUsed: boolean;
};

export type FinancialResearchSource = {
  installed: boolean;
  sourceName: string;
  sourceRootName: string;
  license: string;
  commit?: string | null;
  acceptedCommit: string;
  commitVerified: boolean;
  externalCodeExecuted: boolean;
  connectorsEnabled: boolean;
  workflows: Array<{
    id: string;
    sourceReference: string;
    available: boolean;
  }>;
};

export type FinancialResearchWorkflowResponse = {
  stockCode: string;
  stockName?: string | null;
  market: string;
  generatedAt?: string | null;
  mode: string;
  aiUsed: boolean;
  publicSearchUsed: boolean;
  source: FinancialResearchSource;
  workflows: FinancialResearchWorkflow[];
  boundaryZh: string;
  boundaryEn: string;
};

export const researchWorkflowsApi = {
  async get(code: string, options?: { refresh?: boolean }): Promise<FinancialResearchWorkflowResponse> {
    const suffix = options?.refresh ? '?refresh=true' : '';
    const response = await apiClient.get<Record<string, unknown>>(
      `/api/v1/stocks/${encodeURIComponent(code)}/research-workflows${suffix}`,
    );
    return toCamelCase<FinancialResearchWorkflowResponse>(response.data);
  },
};
