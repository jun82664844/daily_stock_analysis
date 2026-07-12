import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import type { ReactNode } from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import ResearchWorkflowsPage from '../ResearchWorkflowsPage';
import { UiLanguageProvider, useUiLanguage } from '../../contexts/UiLanguageContext';
import { UI_LANGUAGE_STORAGE_KEY } from '../../utils/uiLanguage';

const getResearchWorkflows = vi.hoisted(() => vi.fn());

function LanguageToggleHarness({ children }: { children: ReactNode }) {
  const { language, setLanguage } = useUiLanguage();
  return <><button type="button" onClick={() => setLanguage(language === 'zh' ? 'en' : 'zh')}>toggle-test-language</button>{children}</>;
}

vi.mock('../../api/researchWorkflows', () => ({
  researchWorkflowsApi: {
    get: (...args: unknown[]) => getResearchWorkflows(...args),
  },
}));

const payload = {
  stockCode: 'AAPL',
  stockName: 'Apple Inc.',
  market: 'us',
  generatedAt: '2026-07-11T10:00:00Z',
  mode: 'deterministic_no_ai',
  aiUsed: false,
  publicSearchUsed: false,
  source: {
    installed: true,
    sourceName: 'anthropics/financial-services',
    sourceRootName: 'anthropic-financial-services',
    license: 'Apache-2.0',
    commit: '4aa51ed3d379731f',
    acceptedCommit: '4aa51ed3d379731f',
    commitVerified: true,
    externalCodeExecuted: false,
    connectorsEnabled: false,
    workflows: [],
  },
  workflows: [
    {
      id: 'company_snapshot',
      titleZh: '公司与估值概览',
      titleEn: 'Company and valuation snapshot',
      purposeZh: '汇总公开字段。',
      purposeEn: 'Summarize disclosed fields.',
      status: 'available',
      sourceReference: 'plugins/comps-analysis/SKILL.md',
      facts: [{ code: 'current_price', labelZh: '最新价格', labelEn: 'Latest price', value: 205, source: 'yahoo_chart', freshness: 'fresh', unit: 'currency', currency: 'USD', asOf: '2026-07-11T10:00:00Z' }],
      missingData: [],
      aiUsed: false,
      publicSearchUsed: false,
    },
    {
      id: 'earnings_review',
      titleZh: '经营数据复盘',
      titleEn: 'Operating data review',
      purposeZh: '整理经营字段。',
      purposeEn: 'Organize operating fields.',
      status: 'partial',
      sourceReference: 'plugins/earnings-analysis/SKILL.md',
      facts: [{ code: 'revenue_growth', labelZh: '收入增长率', labelEn: 'Revenue growth', value: 0.5, source: 'yfinance_profile', freshness: 'cached', unit: 'percent', currency: null, asOf: null }],
      missingData: ['revenue', 'net_profit'],
      aiUsed: false,
      publicSearchUsed: false,
    },
    {
      id: 'sector_overview',
      titleZh: '行业与板块概览',
      titleEn: 'Sector and industry overview',
      purposeZh: '展示行业。',
      purposeEn: 'Show industry.',
      status: 'available',
      sourceReference: 'plugins/sector-overview/SKILL.md',
      facts: [],
      missingData: [],
      aiUsed: false,
      publicSearchUsed: false,
    },
    {
      id: 'catalyst_calendar',
      titleZh: '公开事件日历',
      titleEn: 'Public event calendar',
      purposeZh: '展示公开事件。',
      purposeEn: 'Show public events.',
      status: 'partial',
      sourceReference: 'plugins/catalyst-calendar/SKILL.md',
      facts: [],
      missingData: ['events'],
      aiUsed: false,
      publicSearchUsed: false,
    },
  ],
  boundaryZh: '仅提供资讯和数据，不构成投资建议。',
  boundaryEn: 'Information and data only; not investment advice.',
};

describe('ResearchWorkflowsPage', () => {
  beforeEach(() => {
    getResearchWorkflows.mockReset();
    getResearchWorkflows.mockResolvedValue(payload);
    window.localStorage.setItem(UI_LANGUAGE_STORAGE_KEY, 'zh');
  });

  it('shows four anonymous no-AI research workflows with source provenance', async () => {
    render(<UiLanguageProvider><ResearchWorkflowsPage /></UiLanguageProvider>);

    expect(await screen.findByRole('heading', { name: '金融研究中心' })).toBeInTheDocument();
    expect(await screen.findByText('公司与估值概览')).toBeInTheDocument();
    expect(screen.getByText('经营数据复盘')).toBeInTheDocument();
    expect(screen.getByText('行业与板块概览')).toBeInTheDocument();
    expect(screen.getByText('公开事件日历')).toBeInTheDocument();
    expect(screen.getByText('Anthropic 金融工作流来源已安装')).toBeInTheDocument();
    expect(screen.getByText('外部连接器未启用')).toBeInTheDocument();
    expect(screen.getByText('仅提供资讯和数据，不构成投资建议。')).toBeInTheDocument();
    expect(screen.getByText('0.50%')).toBeInTheDocument();
    expect(screen.getByText('205 美元')).toBeInTheDocument();
    expect(screen.getByText('公司资料 · 缓存')).toBeInTheDocument();
    expect(screen.queryByText(/yfinance_profile|SKILL\.md|cached/)).not.toBeInTheDocument();
    expect(getResearchWorkflows).toHaveBeenCalledWith('AAPL', { refresh: false });
  });

  it('queries another symbol and offers an explicit refresh', async () => {
    render(<UiLanguageProvider><ResearchWorkflowsPage /></UiLanguageProvider>);
    await screen.findByText('公司与估值概览');

    fireEvent.change(screen.getByPlaceholderText('输入股票代码，如 600519.SH、AAPL'), { target: { value: '600519.SH' } });
    fireEvent.click(screen.getByLabelText('强制刷新现有行情数据'));
    fireEvent.click(screen.getByRole('button', { name: '生成研究清单' }));

    await waitFor(() => expect(getResearchWorkflows).toHaveBeenLastCalledWith('600519.SH', { refresh: true }));
  });

  it('renders the complete page in English mode', async () => {
    window.localStorage.setItem(UI_LANGUAGE_STORAGE_KEY, 'en');
    render(<UiLanguageProvider><ResearchWorkflowsPage /></UiLanguageProvider>);

    expect(await screen.findByRole('heading', { name: 'Financial research center' })).toBeInTheDocument();
    expect(screen.getByText('Company and valuation snapshot')).toBeInTheDocument();
    expect(screen.getByText('Operating data review')).toBeInTheDocument();
    expect(screen.getByText('Information and data only; not investment advice.')).toBeInTheDocument();
    expect(screen.queryByText('公司与估值概览')).not.toBeInTheDocument();
  });

  it('keeps the current symbol and does not refetch when the language changes', async () => {
    render(<UiLanguageProvider><LanguageToggleHarness><ResearchWorkflowsPage /></LanguageToggleHarness></UiLanguageProvider>);
    await screen.findByRole('heading', { name: '金融研究中心' });

    fireEvent.change(screen.getByRole('textbox', { name: '股票代码' }), { target: { value: '600519.SH' } });
    fireEvent.click(screen.getByRole('button', { name: '生成研究清单' }));
    await waitFor(() => expect(getResearchWorkflows).toHaveBeenCalledTimes(2));

    fireEvent.click(screen.getByRole('button', { name: 'toggle-test-language' }));
    await screen.findByRole('heading', { name: 'Financial research center' });
    expect(screen.getByRole('textbox', { name: 'Stock code' })).toHaveValue('600519.SH');
    expect(getResearchWorkflows).toHaveBeenCalledTimes(2);
  });
});
