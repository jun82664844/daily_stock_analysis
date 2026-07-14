import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import type { PublicMarketHomeResponse } from '../../../api/marketWorkspace';
import PublicMarketHomeV116 from '../PublicMarketHomeV116';

const data: PublicMarketHomeResponse = {
  asOf: '2026-07-13T01:30:00Z', aiUsed: false, informationalOnly: true,
  markets: [
    { market: 'cn', sessionState: 'unknown', displayMode: 'latest_available', rankingScope: 'configured_universe', selectionBasis: 'turnover_then_absolute_change', indices: [{ symbol: '000001.SH', name: '上证指数', market: 'cn', currentPrice: 3250.12, changePercent: 0.62, sourceState: { source: 'cn_index', status: 'fresh', observedAt: '2026-07-13T01:29:00Z' } }], sources: [], warnings: [], headlines: [{ title: '沪深市场成交活跃度回升', summary: '公开市场资讯摘要。', publisher: '测试资讯源', publishedAt: '2026-07-13T01:25:00Z', url: 'https://example.com/cn-market', sourceState: { source: 'unit_news', status: 'fresh', observedAt: '2026-07-13T01:25:00Z' } }], attention: [{ symbol: '600519.SH', name: '贵州茅台', market: 'cn', currency: 'CNY', currentPrice: 1188.8, changePercent: -1.5, sourceState: { source: 'cn_quote', status: 'fresh', observedAt: '2026-07-13T01:29:00Z' } }] },
    { market: 'hk', sessionState: 'unknown', displayMode: 'delayed', rankingScope: 'configured_universe', selectionBasis: 'turnover_then_absolute_change', indices: [], sources: [], warnings: [], headlines: [], attention: [{ symbol: '0700.HK', name: '腾讯控股', market: 'hk', currency: 'HKD', currentPrice: 500, changePercent: 1.25, sourceState: { source: 'hk_quote', status: 'cached' } }] },
    { market: 'us', sessionState: 'unknown', displayMode: 'latest_available', rankingScope: 'configured_universe', selectionBasis: 'turnover_then_absolute_change', indices: [], sources: [], warnings: ['market_home_unavailable'], headlines: [], attention: [] },
  ],
};

describe('PublicMarketHomeV116', () => {
  it('labels the retrieval time when a public source omits publication time', () => {
    const withoutPublishedTime: PublicMarketHomeResponse = {
      ...data,
      markets: data.markets.map((market) => market.market !== 'cn' ? market : {
        ...market,
        headlines: (market.headlines ?? []).map((headline) => ({
          ...headline,
          publisher: '\u8d22\u8054\u793e',
          publishedAt: undefined,
          sourceState: {
            ...headline.sourceState,
            observedAt: undefined,
            fetchedAt: '2026-07-13T01:30:00Z',
          },
        })),
      }),
    };

    render(<PublicMarketHomeV116 language="en" data={withoutPublishedTime} loading={false} onOpenSymbol={vi.fn()} onCreateAlert={vi.fn()} />);
    expect(screen.getByText(/Retrieved/)).toBeInTheDocument();
    expect(screen.getByTestId('public-home-index-strip')).toHaveTextContent('SSE Composite');
    expect(screen.getByText('CLS')).toBeInTheDocument();
  });

  it('shows a compact three-market dashboard with a real information feed and partial degradation', () => {
    render(<PublicMarketHomeV116 language="zh" data={data} loading={false} onOpenSymbol={vi.fn()} onCreateAlert={vi.fn()} />);
    expect(screen.getByTestId('public-home-market-dashboard-v118')).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: '市场焦点' })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: /A股/ })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: /港股/ })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: /美股/ })).toBeInTheDocument();
    expect(screen.queryByText('DSA V116')).not.toBeInTheDocument();
    expect(screen.queryByText('全市场热门')).not.toBeInTheDocument();
    expect(screen.queryByText('实时股价')).not.toBeInTheDocument();
    expect(screen.getByTestId('public-home-index-strip')).toHaveTextContent('上证指数');
    expect(screen.getByTestId('public-home-index-strip')).toHaveTextContent('3,250.12');
    expect(screen.getAllByText('贵州茅台').length).toBeGreaterThan(0);
    expect(screen.getByRole('heading', { name: '市场快讯' })).toBeInTheDocument();
    expect(screen.getByText('沪深市场成交活跃度回升')).toBeInTheDocument();
    expect(screen.getByText('测试资讯源')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('tab', { name: /港股/ }));
    expect(screen.getAllByText('腾讯控股').length).toBeGreaterThan(0);
    expect(screen.getByRole('heading', { name: '行情动态' })).toBeInTheDocument();
    expect(screen.getByText(/最新可用价 500/)).toBeInTheDocument();

    fireEvent.click(screen.getByRole('tab', { name: /美股/ }));
    expect(screen.getAllByText('该市场暂时不可用')).toHaveLength(2);
  });

  it('opens a stock and creates a validated price-alert draft', () => {
    const open = vi.fn();
    const alert = vi.fn();
    render(<PublicMarketHomeV116 language="zh" data={data} loading={false} onOpenSymbol={open} onCreateAlert={alert} />);
    fireEvent.click(screen.getByRole('button', { name: '查看 贵州茅台' }));
    expect(open).toHaveBeenCalledWith('600519.SH');
    fireEvent.click(screen.getByRole('button', { name: '为 贵州茅台 设置到价提醒' }));
    fireEvent.change(screen.getByRole('spinbutton', { name: '到价阈值' }), { target: { value: '1200' } });
    fireEvent.click(screen.getByRole('button', { name: '保存到价提醒' }));
    expect(alert).toHaveBeenCalledWith(expect.objectContaining({ stockCode: '600519.SH', threshold: 1200 }));
  });
});
