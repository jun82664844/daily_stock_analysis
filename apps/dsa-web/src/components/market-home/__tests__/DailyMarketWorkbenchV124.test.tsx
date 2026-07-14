import { fireEvent, render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { PublicMarketHomeResponse } from '../../../api/marketWorkspace';
import DailyMarketWorkbenchV124 from '../DailyMarketWorkbenchV124';
import { rememberRecentMarketSymbol } from '../marketRecentV124';

const data: PublicMarketHomeResponse = {
  asOf: '2026-07-14T01:30:00Z',
  aiUsed: false,
  informationalOnly: true,
  markets: [
    {
      market: 'cn', sessionState: 'open', displayMode: 'latest_available', rankingScope: 'market_wide', selectionBasis: 'public',
      indices: [{ symbol: '000001.SH', name: '上证指数', market: 'cn', currentPrice: 3250.12, changePercent: 0.62, sourceState: { source: 'cn_index', status: 'fresh' } }],
      attention: [{ symbol: '300308.SZ', name: '中际旭创', market: 'cn', currentPrice: 1131.53, changePercent: 2.12, sourceState: { source: 'cn_rank', status: 'fresh' } }],
      headlines: [{ title: 'A股成交活跃度回升', publisher: '测试财经', publishedAt: '2026-07-14T01:25:00Z', url: 'https://example.com/cn', sourceState: { source: 'cn_news', status: 'fresh' } }],
      sources: [], warnings: [],
    },
    {
      market: 'hk', sessionState: 'closed', displayMode: 'delayed', rankingScope: 'market_wide', selectionBasis: 'public',
      indices: [{ symbol: '^HSI', name: 'Hang Seng Index', market: 'hk', currentPrice: 24100, changePercent: -0.2, sourceState: { source: 'hk_index', status: 'cached' } }],
      attention: [{ symbol: '0700.HK', name: 'Tencent', market: 'hk', currentPrice: 500, changePercent: 1.25, sourceState: { source: 'hk_rank', status: 'cached' } }],
      headlines: [{ title: '港股收市数据更新', publisher: '测试港股源', publishedAt: '2026-07-14T01:20:00Z', sourceState: { source: 'hk_news', status: 'cached' } }],
      sources: [], warnings: [],
    },
    {
      market: 'us', sessionState: 'unknown', displayMode: 'delayed', rankingScope: 'market_wide', selectionBasis: 'public',
      indices: [], attention: [{ symbol: 'AAPL', name: 'Apple Inc.', market: 'us', currentPrice: 210, changePercent: 0.8, sourceState: { source: 'us_rank', status: 'fresh' } }],
      headlines: [{ title: '美股盘前关注科技股', publisher: '测试美股源', sourceState: { source: 'us_news', status: 'fresh', fetchedAt: '2026-07-14T01:15:00Z' } }],
      sources: [], warnings: ['us_index_unavailable'],
    },
  ],
};

describe('DailyMarketWorkbenchV124', () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  it('shows three market clocks, a source-linked timeline, and the information-only boundary in Chinese', () => {
    render(<DailyMarketWorkbenchV124 language="zh" data={data} onOpenSymbol={vi.fn()} />);

    expect(screen.getByRole('heading', { name: '今日市场工作台' })).toBeInTheDocument();
    expect(screen.getByText('A股交易中')).toBeInTheDocument();
    expect(screen.getByText('港股已收市')).toBeInTheDocument();
    expect(screen.getByText('美股时段待确认')).toBeInTheDocument();
    expect(screen.getByText('上证指数')).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: '跨市场今日时间线' })).toBeInTheDocument();
    expect(screen.getByText('A股成交活跃度回升')).toBeInTheDocument();
    expect(screen.getByText('美股盘前关注科技股')).toBeInTheDocument();
    expect(screen.getByText(/抓取时间/)).toBeInTheDocument();
    expect(screen.getByText('仅提供资讯和数据，不构成投资建议。')).toBeInTheDocument();
  });

  it('keeps the English surface fully English', () => {
    render(<DailyMarketWorkbenchV124 language="en" data={data} onOpenSymbol={vi.fn()} />);

    expect(screen.getByRole('heading', { name: 'Daily market workbench' })).toBeInTheDocument();
    expect(screen.getByText('A-shares open')).toBeInTheDocument();
    expect(screen.getByText('Hong Kong closed')).toBeInTheDocument();
    expect(screen.getByText('US session unconfirmed')).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Cross-market timeline' })).toBeInTheDocument();
    expect(screen.getByText('Information and data only; not investment advice.')).toBeInTheDocument();
  });

  it('keeps every available market represented when one market has the newest headlines', () => {
    const crowdedData: PublicMarketHomeResponse = {
      ...data,
      markets: data.markets.map((section) => section.market === 'cn' ? {
        ...section,
        headlines: Array.from({ length: 6 }, (_, index) => ({
          title: `A-share headline ${index + 1}`,
          publisher: 'CN source',
          publishedAt: `2026-07-14T01:2${9 - index}:00Z`,
          sourceState: { source: 'cn_news', status: 'fresh' as const },
        })),
      } : section),
    };

    render(<DailyMarketWorkbenchV124 language="en" data={crowdedData} onOpenSymbol={vi.fn()} />);

    expect(screen.getByText('港股收市数据更新')).toBeInTheDocument();
    expect(screen.getByText('美股盘前关注科技股')).toBeInTheDocument();
  });

  it('opens and clears browser-local recent research without touching other storage', () => {
    rememberRecentMarketSymbol(
      { symbol: 'AAPL', name: 'Apple Inc.', market: 'us' },
      () => '2026-07-14T01:00:00Z',
    );
    window.localStorage.setItem('unrelated-setting', 'keep');
    const open = vi.fn();

    render(<DailyMarketWorkbenchV124 language="zh" data={data} onOpenSymbol={open} />);

    fireEvent.click(screen.getByRole('button', { name: '继续查看 Apple Inc. AAPL' }));
    expect(open).toHaveBeenCalledWith('AAPL');
    fireEvent.click(screen.getByRole('button', { name: '清空最近查看' }));
    expect(screen.getByText('浏览市场榜单后，可从这里继续研究。')).toBeInTheDocument();
    expect(window.localStorage.getItem('unrelated-setting')).toBe('keep');
  });
});
