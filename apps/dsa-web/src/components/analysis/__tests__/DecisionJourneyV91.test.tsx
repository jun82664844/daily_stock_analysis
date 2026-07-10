import { fireEvent, render, screen, within } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import { DecisionJourneyV91 } from '../DecisionJourneyV91';
import type { DecisionJourneyModel } from '../decisionJourneyModel';

const model: DecisionJourneyModel = {
  language: 'zh',
  labels: {
    eyebrow: 'V91 专业免费研判',
    title: '用户决策闭环',
    subtitle: '先看结论，再核对证据、风险和更强数据能改变什么。',
    conclusion: '结论',
    opportunity: '价位地图',
    risk: '风险边界',
    evidence: '关键证据',
    evidenceLibrary: '证据库',
    free: '免费版包含',
    premium: '高级版增强',
    sourceTrust: '来源可信度',
    noAi: '未用 AI，不扣额度',
  },
  summary: {
    conclusion: '趋势偏强，但仍需等待确认。',
    score: 72,
    opportunity: '支撑 129.5；压力 140。',
    risk: '避免在行情过期时追涨。',
    evidence: '最新价 139，MA20 129.5，RSI14 63.5。',
  },
  technical: {
    ma5: 137,
    ma10: 134.5,
    ma20: 129.5,
    ma60: null,
    rsi14: 63.5,
    macd: 2.35,
    trendState: '偏强',
    volumeState: '量能中性',
  },
  chart: {
    label: '收盘价趋势',
    points: [
      { label: '07-01', value: 128 },
      { label: '07-02', value: 132 },
      { label: '07-03', value: 131 },
      { label: '07-04', value: 139 },
    ],
    min: 128,
    max: 139,
  },
  marketFocus: {
    label: '美股重点',
    benchmark: 'SPY / QQQ / 所属行业',
    items: ['财报与 SEC 文件', '估值及盈利预期', '指数与同业对比'],
  },
  trust: {
    quoteSource: 'free_web_chart',
    historySource: 'free_history',
    profileSource: 'free_profile',
    freshness: '新鲜',
    updatedAt: '2026-07-10T09:30:00+08:00',
    routeLane: 'us_free_lane',
    elapsed: '35 ms',
  },
  tabs: [
    {
      key: 'price',
      label: '行情量价',
      summary: '当前价格结构及成交量确认。',
      items: [{ label: '最新价 / 涨跌', value: '139 / +1.09%', detail: '开盘 137，最高 140，最低 136。' }],
    },
    {
      key: 'technical',
      label: '技术证据',
      summary: '使用历史行情在本地计算趋势与动量证据。',
      items: [{ label: 'RSI14 / MACD', value: '63.5 / 2.35', detail: '动量指标用于确认背景。' }],
    },
    {
      key: 'events',
      label: '资讯事件',
      summary: '针对当前市场的重大事件核对清单。',
      items: [{ label: '财报与 SEC 文件', value: '财报核对', detail: '核对原始披露。' }],
    },
    {
      key: 'fundamentals',
      label: '基本面',
      summary: '公司资料与估值背景。',
      items: [{ label: '市值 / 市盈率', value: '4.5T / 31.2', detail: '与历史和同业比较。' }],
    },
    {
      key: 'sources',
      label: '来源可信度',
      summary: '解读前先核对来源和新鲜度。',
      items: [{ label: '行情来源', value: 'free_web_chart', detail: '新鲜' }],
    },
  ],
  comparison: {
    free: ['完整决策结构', '行情与本地技术计算', '分市场核对清单', '来源和新鲜度披露'],
    premium: ['实时 API 新鲜度', '资讯和公告原文链接', '更长历史与模型验证', '自选股持续提醒'],
  },
  boundary: {
    aiUsed: false,
    disclaimer: '仅作信息分析，不构成投资建议。',
  },
};

describe('DecisionJourneyV91', () => {
  it('shows a focused first screen, a useful evidence library, and truthful upgrade differences', () => {
    const onJump = vi.fn();
    render(
      <MemoryRouter>
        <DecisionJourneyV91 model={model} onJump={onJump} />
      </MemoryRouter>,
    );

    const journey = screen.getByTestId('basic-query-decision-journey-v91');
    expect(journey).toHaveTextContent('用户决策闭环');
    expect(journey).toHaveTextContent('趋势偏强，但仍需等待确认');
    expect(journey).toHaveTextContent('支撑 129.5；压力 140');
    expect(journey).toHaveTextContent('避免在行情过期时追涨');
    expect(journey).toHaveTextContent('美股重点');
    expect(journey).toHaveTextContent('财报与 SEC 文件');
    expect(journey).toHaveTextContent('未用 AI，不扣额度');
    expect(journey).toHaveTextContent('仅作信息分析，不构成投资建议');
    expect(screen.getByTestId('decision-journey-price-chart')).toHaveAttribute('aria-label', '收盘价趋势');

    const library = screen.getByTestId('decision-journey-evidence-library');
    expect(library).toHaveTextContent('行情量价');
    expect(library).toHaveTextContent('139 / +1.09%');
    fireEvent.click(within(library).getByRole('tab', { name: '技术证据' }));
    expect(library).toHaveTextContent('RSI14 / MACD');
    expect(library).not.toHaveTextContent('139 / +1.09%');
    fireEvent.click(within(library).getByRole('tab', { name: '来源可信度' }));
    expect(library).toHaveTextContent('free_web_chart');
    expect(library).toHaveTextContent('us_free_lane');

    expect(journey).toHaveTextContent('完整决策结构');
    expect(journey).toHaveTextContent('实时 API 新鲜度');
    fireEvent.click(within(journey).getByRole('button', { name: '查看资讯事件' }));
    fireEvent.click(within(journey).getByRole('button', { name: '查看K线情景' }));
    fireEvent.click(within(journey).getByRole('button', { name: '查看升级差异' }));
    expect(onJump).toHaveBeenNthCalledWith(1, 'events');
    expect(onJump).toHaveBeenNthCalledWith(2, 'kline');
    expect(onJump).toHaveBeenNthCalledWith(3, 'upgrade');
  });

  it('renders English copy when the supplied model is English', () => {
    const englishModel: DecisionJourneyModel = {
      ...model,
      language: 'en',
      labels: {
        ...model.labels,
        eyebrow: 'V91 professional free view',
        title: 'Professional decision journey',
        subtitle: 'Conclusion first, then evidence, risks, and what better data changes.',
        evidenceLibrary: 'Evidence library',
        free: 'Free includes',
        premium: 'Premium improves',
        noAi: 'No AI, no quota',
      },
      marketFocus: { ...model.marketFocus, label: 'US market focus' },
      boundary: { ...model.boundary, disclaimer: 'Information analysis only, not investment advice.' },
    };

    render(
      <MemoryRouter>
        <DecisionJourneyV91 model={englishModel} onJump={() => undefined} />
      </MemoryRouter>,
    );

    expect(screen.getByTestId('basic-query-decision-journey-v91')).toHaveTextContent('Professional decision journey');
    expect(screen.getAllByText('US market focus')).toHaveLength(2);
    expect(screen.getByText('Information analysis only, not investment advice.')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'View news & events' })).toBeInTheDocument();
  });
});
