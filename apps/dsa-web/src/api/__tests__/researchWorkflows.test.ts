import { beforeEach, describe, expect, it, vi } from 'vitest';
import { researchWorkflowsApi } from '../researchWorkflows';

const get = vi.hoisted(() => vi.fn());

vi.mock('../index', () => ({
  default: { get },
}));

describe('researchWorkflowsApi', () => {
  beforeEach(() => {
    get.mockReset();
  });

  it('loads public no-AI workflows and converts fields to camelCase', async () => {
    get.mockResolvedValueOnce({
      data: {
        stock_code: 'AAPL',
        stock_name: 'Apple Inc.',
        market: 'us',
        mode: 'deterministic_no_ai',
        ai_used: false,
        public_search_used: false,
        source: {
          installed: true,
          source_name: 'anthropics/financial-services',
          source_root_name: 'anthropic-financial-services',
          license: 'Apache-2.0',
          commit: '4aa51ed3',
          accepted_commit: '4aa51ed3',
          commit_verified: true,
          external_code_executed: false,
          connectors_enabled: false,
          workflows: [],
        },
        workflows: [{
          id: 'company_snapshot',
          title_zh: '公司与估值概览',
          title_en: 'Company and valuation snapshot',
          purpose_zh: '事实数据',
          purpose_en: 'Observed facts',
          status: 'available',
          source_reference: 'plugins/example/SKILL.md',
          facts: [{
            code: 'current_price',
            label_zh: '最新价格',
            label_en: 'Latest price',
            value: 205,
            unit: 'currency',
            currency: 'USD',
            source: 'yahoo_chart',
            freshness: 'fresh',
            as_of: '2026-07-11T10:00:00Z',
          }],
          missing_data: [],
          ai_used: false,
          public_search_used: false,
        }],
        boundary_zh: '仅提供资讯和数据。',
        boundary_en: 'Information and data only.',
      },
    });

    const result = await researchWorkflowsApi.get('AAPL');

    expect(get).toHaveBeenCalledWith('/api/v1/stocks/AAPL/research-workflows');
    expect(result.stockCode).toBe('AAPL');
    expect(result.source.connectorsEnabled).toBe(false);
    expect(result.source.commitVerified).toBe(true);
    expect(result.workflows[0].sourceReference).toContain('SKILL.md');
    expect(result.workflows[0].facts[0].asOf).toBe('2026-07-11T10:00:00Z');
    expect(result.workflows[0].facts[0].currency).toBe('USD');
  });

  it('forwards an explicit source refresh', async () => {
    get.mockResolvedValueOnce({ data: { workflows: [], source: {} } });

    await researchWorkflowsApi.get('600519.SH', { refresh: true });

    expect(get).toHaveBeenCalledWith('/api/v1/stocks/600519.SH/research-workflows?refresh=true');
  });
});
