import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { marketWorkspaceApi, type PublicMarketHomeResponse, type SymbolWorkspaceResponse } from '../../../api/marketWorkspace';
import PublicMarketHomeV116 from '../PublicMarketHomeV116';
import { readRecentMarketSymbols } from '../marketRecentV124';

afterEach(() => {
  vi.restoreAllMocks();
});

const data: PublicMarketHomeResponse = {
  asOf: '2026-07-13T01:30:00Z', aiUsed: false, informationalOnly: true,
  events: [{ eventId: 'event-aapl', market: 'us', category: 'earnings', title: 'AAPL earnings results published', symbol: 'AAPL', name: 'Apple Inc.', eventTime: '2026-07-13T01:25:00Z', timeKind: 'published', publisher: 'Unit News', sourceState: { source: 'unit_news', status: 'fresh' }, classificationSource: 'keyword_rules' }],
  markets: [
    {
      market: 'cn', sessionState: 'open', displayMode: 'latest_available', rankingScope: 'market_wide', selectionBasis: 'market_wide_public_rankings_with_liquidity_filter',
      indices: [{ symbol: '000001.SH', name: '上证指数', market: 'cn', currentPrice: 3250.12, changePercent: 0.62, sourceState: { source: 'cn_index', status: 'fresh', observedAt: '2026-07-13T01:29:00Z' } }],
      sources: [{ source: 'sina_public_cn_ranking', status: 'fresh', fetchedAt: '2026-07-13T01:30:00Z' }], warnings: [], rankingCache: { hit: false, ageSeconds: 0, ttlSeconds: 120 },
      headlines: [{ title: '沪深市场成交活跃度回升', summary: '公开市场资讯摘要。', publisher: '测试资讯源', publishedAt: '2026-07-13T01:25:00Z', url: 'https://example.com/cn-market', sourceState: { source: 'unit_news', status: 'fresh', observedAt: '2026-07-13T01:25:00Z' } }],
      attention: [{ symbol: '300308.SZ', name: '中际旭创', market: 'cn', currency: 'CNY', currentPrice: 1131.53, changePercent: 2.12, turnover: 9496897654, tradingSession: 'regular', sourceState: { source: 'sina_public_cn_ranking', status: 'fresh', observedAt: '2026-07-14T10:01:30+08:00' } }],
      mostActive: [{ symbol: '300308.SZ', name: '中际旭创', market: 'cn', currency: 'CNY', currentPrice: 1131.53, changePercent: 2.12, turnover: 9496897654, tradingSession: 'regular', sourceState: { source: 'sina_public_cn_ranking', status: 'fresh', observedAt: '2026-07-14T10:01:30+08:00' } }],
      gainers: [{ symbol: '300001.SZ', name: '特锐德', market: 'cn', currency: 'CNY', currentPrice: 20, changePercent: 9.5, turnover: 300000000, sourceState: { source: 'sina_public_cn_ranking', status: 'fresh' } }],
      losers: [{ symbol: '600010.SH', name: '包钢股份', market: 'cn', currency: 'CNY', currentPrice: 2.1, changePercent: -7.2, turnover: 500000000, sourceState: { source: 'sina_public_cn_ranking', status: 'fresh' } }],
      sectorHighlights: [{ name: '家具行业', market: 'cn', changePercent: 3.7, leadingSymbol: '600001.SH', leadingName: '领涨公司', leadingChangePercent: 8.2, sourceState: { source: 'sina_public_cn_sector', status: 'fresh' } }],
    },
    {
      market: 'hk', sessionState: 'open', displayMode: 'delayed', rankingScope: 'market_wide', selectionBasis: 'market_wide_public_rankings_with_liquidity_filter', indices: [],
      sources: [], warnings: ['hk_sector_highlights_unavailable'], rankingCache: { hit: true, ageSeconds: 30, ttlSeconds: 120 }, headlines: [],
      attention: [{ symbol: '0700.HK', name: '腾讯控股', market: 'hk', currency: 'HKD', currentPrice: 500, changePercent: 1.25, sourceState: { source: 'sina_public_hk_ranking', status: 'cached' } }],
      mostActive: [{ symbol: '0700.HK', name: '腾讯控股', market: 'hk', currency: 'HKD', currentPrice: 500, changePercent: 1.25, sourceState: { source: 'sina_public_hk_ranking', status: 'cached' } }], gainers: [], losers: [], sectorHighlights: [],
    },
    {
      market: 'us', sessionState: 'closed', displayMode: 'delayed', rankingScope: 'market_wide', selectionBasis: 'market_wide_public_rankings_with_liquidity_filter', indices: [],
      sources: [], warnings: ['us_sector_highlights_unavailable'], rankingCache: { hit: false, ageSeconds: 0, ttlSeconds: 120 }, headlines: [],
      attention: [{ symbol: 'AAPL', name: 'Apple Inc.', market: 'us', currency: 'USD', currentPrice: 210, changePercent: 0.8, tradingSession: 'pre', sourceState: { source: 'yahoo_public_us_screener', status: 'fresh' } }],
      mostActive: [{ symbol: 'AAPL', name: 'Apple Inc.', market: 'us', currency: 'USD', currentPrice: 210, changePercent: 0.8, tradingSession: 'pre', sourceState: { source: 'yahoo_public_us_screener', status: 'fresh' } }], gainers: [], losers: [], sectorHighlights: [],
    },
  ],
};

const previewDetail: SymbolWorkspaceResponse = {
  symbol: '300308.SZ',
  name: '中际旭创',
  market: 'cn',
  currency: 'CNY',
  asOf: '2026-07-14T10:01:30+08:00',
  quote: {
    currentPrice: 1131.53,
    changePercent: 2.12,
    open: 1100,
    high: 1140,
    low: 1098,
    prevClose: 1108,
    volume: 18_000_000,
    amount: 9_496_897_654,
    freshness: 'fresh',
    source: 'a_share_realtime',
  },
  history: [{ date: '2026-07-11', close: 1108 }, { date: '2026-07-14', close: 1131.53 }],
  indicators: { ma5: 1090, ma10: 1070, ma20: 1050, priceChange5d: 4.2, priceChange20d: 9.1, volumeChangeVsMa5: 15 },
  profile: { sector: '信息技术', industry: '通信设备', marketCap: 1_200_000_000_000 },
  headlines: [],
  sources: [{ source: 'a_share_realtime', status: 'fresh', observedAt: '2026-07-14T10:01:30+08:00' }],
  warnings: [],
  aiUsed: false,
  informationalOnly: true,
};

describe('PublicMarketHomeV116', () => {
  it('lazy-loads the V126 event center and forwards watchlist context', async () => {
    render(
      <PublicMarketHomeV116
        language="zh"
        data={data}
        loading={false}
        watchlistSymbols={['AAPL']}
        onOpenSymbol={vi.fn()}
        onCreateAlert={vi.fn()}
      />,
    );

    expect(await screen.findByTestId('daily-market-event-center-v126')).toBeInTheDocument();
    expect(screen.getByText('自选关注')).toBeInTheDocument();
  });

  it('mounts the V124 workbench and remembers a ranking stock before opening the free query', () => {
    window.localStorage.clear();
    const open = vi.fn();
    render(<PublicMarketHomeV116 language="zh" data={data} loading={false} onOpenSymbol={open} onCreateAlert={vi.fn()} />);

    expect(screen.getByTestId('daily-market-workbench-v124')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: '查看 中际旭创' }));

    expect(open).toHaveBeenCalledWith('300308.SZ');
    expect(readRecentMarketSymbols()[0]).toMatchObject({
      symbol: '300308.SZ',
      name: '中际旭创',
      market: 'cn',
    });
    expect(screen.getByRole('button', { name: '继续查看 中际旭创 300308.SZ' })).toBeInTheDocument();
  });

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
    expect(screen.getAllByText(/Retrieved/).length).toBeGreaterThan(0);
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
    expect(screen.getByText('全市场公开榜单')).toBeInTheDocument();
    expect(screen.queryByText('实时股价')).not.toBeInTheDocument();
    expect(screen.getByTestId('public-home-index-strip')).toHaveTextContent('上证指数');
    expect(screen.getByTestId('public-home-index-strip')).toHaveTextContent('3,250.12');
    expect(screen.getAllByText('中际旭创').length).toBeGreaterThan(0);
    expect(screen.queryByText('贵州茅台')).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: '涨幅榜' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '跌幅榜' })).toBeInTheDocument();
    expect(screen.getByText('家具行业')).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: '市场快讯' })).toBeInTheDocument();
    expect(screen.getAllByText('沪深市场成交活跃度回升').length).toBeGreaterThan(0);
    expect(screen.getAllByText('测试资讯源').length).toBeGreaterThan(0);

    fireEvent.click(screen.getByRole('tab', { name: /港股/ }));
    expect(screen.getAllByText('腾讯控股').length).toBeGreaterThan(0);
    expect(screen.getByRole('heading', { name: '行情动态' })).toBeInTheDocument();
    expect(screen.getByText(/最新可用价 500/)).toBeInTheDocument();

    fireEvent.click(screen.getByRole('tab', { name: /美股/ }));
    expect(screen.getAllByText('苹果').length).toBeGreaterThan(0);
    expect(screen.getByText('盘前')).toBeInTheDocument();
  });

  it('opens a stock and creates a validated price-alert draft', () => {
    const open = vi.fn();
    const alert = vi.fn();
    render(<PublicMarketHomeV116 language="zh" data={data} loading={false} onOpenSymbol={open} onCreateAlert={alert} />);
    fireEvent.click(screen.getByRole('button', { name: '查看 中际旭创' }));
    expect(open).toHaveBeenCalledWith('300308.SZ');
    fireEvent.click(screen.getByRole('button', { name: '为 中际旭创 设置到价提醒' }));
    fireEvent.change(screen.getByRole('spinbutton', { name: '到价阈值' }), { target: { value: '1200' } });
    fireEvent.click(screen.getByRole('button', { name: '保存到价提醒' }));
    expect(alert).toHaveBeenCalledWith(expect.objectContaining({ stockCode: '300308.SZ', threshold: 1200 }));
  });

  it('switches market-wide ranking groups and labels the US extended session', () => {
    render(<PublicMarketHomeV116 language="zh" data={data} loading={false} onOpenSymbol={vi.fn()} onCreateAlert={vi.fn()} />);
    fireEvent.click(screen.getByRole('button', { name: '涨幅榜' }));
    expect(screen.getByText('特锐德')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('tab', { name: /美股/ }));
    expect(screen.getByText('盘前')).toBeInTheDocument();
  });

  it('loads public stock details only after an explicit preview click and keeps full query available', async () => {
    const getSymbol = vi.spyOn(marketWorkspaceApi, 'getSymbol').mockResolvedValue(previewDetail);
    const open = vi.fn();
    render(<PublicMarketHomeV116 language="zh" data={data} loading={false} onOpenSymbol={open} onCreateAlert={vi.fn()} />);

    expect(getSymbol).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole('button', { name: '查看 中际旭创 数据详情' }));
    expect(screen.getByRole('status')).toHaveTextContent('正在补充均线、历史曲线和公司资料');
    expect(await screen.findByRole('heading', { name: '中际旭创 数据详情' })).toBeInTheDocument();
    expect(getSymbol).toHaveBeenCalledTimes(1);
    expect(getSymbol).toHaveBeenCalledWith('300308.SZ');

    fireEvent.click(screen.getByRole('button', { name: '进入完整查询' }));
    expect(open).toHaveBeenCalledWith('300308.SZ');

    fireEvent.click(screen.getByRole('tab', { name: /港股/ }));
    await waitFor(() => expect(screen.queryByTestId('public-market-stock-preview-v121')).not.toBeInTheDocument());
  });

  it('keeps the ranking usable when detail loading fails and supports retry', async () => {
    const getSymbol = vi.spyOn(marketWorkspaceApi, 'getSymbol')
      .mockRejectedValueOnce(new Error('network'))
      .mockResolvedValueOnce(previewDetail);
    render(<PublicMarketHomeV116 language="zh" data={data} loading={false} onOpenSymbol={vi.fn()} onCreateAlert={vi.fn()} />);

    fireEvent.click(screen.getByRole('button', { name: '查看 中际旭创 数据详情' }));
    expect(await screen.findByRole('heading', { name: '公开数据暂时不可用' })).toBeInTheDocument();
    expect(screen.getAllByText('中际旭创').length).toBeGreaterThan(0);
    fireEvent.click(screen.getByRole('button', { name: '重新加载数据详情' }));
    expect(await screen.findByRole('heading', { name: '中际旭创 数据详情' })).toBeInTheDocument();
    expect(getSymbol).toHaveBeenCalledTimes(2);
  });
});
