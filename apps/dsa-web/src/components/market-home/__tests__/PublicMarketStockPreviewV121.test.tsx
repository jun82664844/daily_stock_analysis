import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import type { MarketSecurityItem, SymbolWorkspaceResponse } from '../../../api/marketWorkspace';
import PublicMarketStockPreviewV121 from '../PublicMarketStockPreviewV121';

const item: MarketSecurityItem = {
  symbol: 'AAPL',
  name: 'Apple Inc.',
  market: 'us',
  currency: 'USD',
  currentPrice: 317.31,
  changePercent: 1.49,
  sourceState: { source: 'yahoo_public_us_screener', status: 'fresh' },
};

const detail: SymbolWorkspaceResponse = {
  symbol: 'AAPL',
  name: 'Apple Inc.',
  market: 'us',
  currency: 'USD',
  asOf: '2026-07-14T08:00:00Z',
  quote: {
    currentPrice: 317.31,
    changePercent: 1.49,
    open: 312,
    high: 319,
    low: 311,
    prevClose: 312.65,
    volume: 48_000_000,
    amount: 15_200_000_000,
    freshness: 'fresh',
    source: 'yahoo_chart_reference',
  },
  indicators: {
    ma5: 310,
    ma10: 305,
    ma20: 298,
    priceChange5d: 2.4,
    priceChange20d: 6.8,
    volumeChangeVsMa5: 12.5,
  },
  history: [
    { date: '2026-07-10', close: 310 },
    { date: '2026-07-11', close: 317.31 },
  ],
  profile: {
    sector: 'Technology',
    industry: 'Consumer Electronics',
    marketCap: 4_700_000_000_000,
  },
  headlines: [],
  sources: [{ source: 'yahoo_chart_reference', status: 'fresh', observedAt: '2026-07-14T08:00:00Z' }],
  warnings: [],
  aiUsed: false,
  informationalOnly: true,
};

describe('PublicMarketStockPreviewV121', () => {
  it('shows ranking data immediately while richer public detail is loading', () => {
    render(
      <PublicMarketStockPreviewV121
        language="zh"
        item={{ ...item, turnover: 12_345_678_900 }}
        detail={null}
        loading
        error=""
        onRetry={vi.fn()}
        onClose={vi.fn()}
        onOpenFull={vi.fn()}
      />,
    );

    expect(screen.getByRole('status')).toHaveTextContent('正在补充均线、历史曲线和公司资料');
    expect(screen.getByText('317.31')).toBeInTheDocument();
    expect(screen.getByText('+1.49%')).toBeInTheDocument();
    expect(screen.getByText('123.46亿')).toBeInTheDocument();
    expect(screen.getByText('未使用 AI')).toBeInTheDocument();
  });

  it('renders useful public quote, trend, profile and source data without AI', () => {
    render(
      <PublicMarketStockPreviewV121
        language="zh"
        item={item}
        detail={detail}
        loading={false}
        error=""
        onRetry={vi.fn()}
        onClose={vi.fn()}
        onOpenFull={vi.fn()}
      />,
    );

    expect(screen.getByRole('heading', { name: 'Apple Inc. 数据详情' })).toBeInTheDocument();
    expect(screen.getByText('开盘')).toBeInTheDocument();
    expect(screen.getAllByText('312').length).toBeGreaterThan(0);
    expect(screen.getByText('MA20')).toBeInTheDocument();
    expect(screen.getByText('298')).toBeInTheDocument();
    expect(screen.getByText('5日变化')).toBeInTheDocument();
    expect(screen.getByText('+2.4%')).toBeInTheDocument();
    expect(screen.getByText('Technology / Consumer Electronics')).toBeInTheDocument();
    expect(screen.getByText(/Yahoo 图表/)).toBeInTheDocument();
    expect(screen.getByText('未使用 AI')).toBeInTheDocument();
    expect(screen.getByText(/仅提供资讯和数据/)).toBeInTheDocument();
    expect(screen.getByLabelText('AAPL 近期收盘曲线')).toBeInTheDocument();
  });

  it('keeps the selected ranking quote as the preview headline when detail data differs', () => {
    render(
      <PublicMarketStockPreviewV121
        language="zh"
        item={item}
        detail={{ ...detail, quote: { ...detail.quote, currentPrice: 300, changePercent: -5 } }}
        loading={false}
        error=""
        onRetry={vi.fn()}
        onClose={vi.fn()}
        onOpenFull={vi.fn()}
      />,
    );

    expect(screen.getByText('317.31')).toBeInTheDocument();
    expect(screen.getByText('+1.49%')).toBeInTheDocument();
    expect(screen.queryByText('-5%')).not.toBeInTheDocument();
  });

  it('keeps missing values unavailable and exposes retry on failure', () => {
    const retry = vi.fn();
    const fallbackItem: MarketSecurityItem = {
      ...item,
      turnover: 12_345_678_900,
      sourceState: { source: 'yahoo_public_us_screener', status: 'fresh', observedAt: '2026-07-14T08:01:00Z' },
    };
    const sparse: SymbolWorkspaceResponse = {
      ...detail,
      quote: {},
      indicators: {},
      profile: {},
      history: [],
      sources: [{ source: 'us_quote', status: 'unavailable' }],
    };
    const { rerender } = render(
      <PublicMarketStockPreviewV121
        language="zh"
        item={fallbackItem}
        detail={sparse}
        loading={false}
        error=""
        onRetry={retry}
        onClose={vi.fn()}
        onOpenFull={vi.fn()}
      />,
    );
    expect(screen.getAllByText('暂不可用').length).toBeGreaterThan(0);
    expect(screen.queryByText('0')).not.toBeInTheDocument();
    expect(screen.getByText('123.46亿')).toBeInTheDocument();
    expect(screen.getByText(/榜单来源/)).toBeInTheDocument();
    expect(screen.getByText(/Yahoo 美股公开榜单/)).toBeInTheDocument();

    rerender(
      <PublicMarketStockPreviewV121
        language="zh"
        item={fallbackItem}
        detail={null}
        loading={false}
        error="request_failed"
        onRetry={retry}
        onClose={vi.fn()}
        onOpenFull={vi.fn()}
      />,
    );
    fireEvent.click(screen.getByRole('button', { name: '重新加载数据详情' }));
    expect(retry).toHaveBeenCalledTimes(1);
  });

  it('keeps the complete-query command and English copy consistent', () => {
    const open = vi.fn();
    render(
      <PublicMarketStockPreviewV121
        language="en"
        item={item}
        detail={detail}
        loading={false}
        error=""
        onRetry={vi.fn()}
        onClose={vi.fn()}
        onOpenFull={open}
      />,
    );
    expect(screen.getByText('No AI used')).toBeInTheDocument();
    expect(screen.getByText(/Information and data only/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Open full query' }));
    expect(open).toHaveBeenCalledWith('AAPL');
  });
});
