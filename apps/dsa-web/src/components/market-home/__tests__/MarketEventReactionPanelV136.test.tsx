import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { marketWorkspaceApi, type PublicMarketEventReactionResponse } from '../../../api/marketWorkspace';
import MarketEventReactionPanelV136 from '../MarketEventReactionPanelV136';

vi.mock('../../../api/marketWorkspace', async (importOriginal) => {
  const original = await importOriginal<typeof import('../../../api/marketWorkspace')>();
  return {
    ...original,
    marketWorkspaceApi: {
      ...original.marketWorkspaceApi,
      getEventReactions: vi.fn(),
    },
  };
});

const response: PublicMarketEventReactionResponse = {
  asOf: '2026-07-30T01:00:00Z',
  items: [{
    eventId: 'event-aapl',
    market: 'us',
    title: 'Apple earnings release',
    symbol: 'AAPL',
    name: 'Apple Inc.',
    subjectType: 'security',
    eventTime: '2026-07-20T00:00:00Z',
    scheduleType: 'earnings_release',
    historySymbol: 'AAPL',
    baselineDate: '2026-07-20',
    benchmarkSymbol: '^GSPC',
    benchmarkName: '标普500指数',
    status: 'partial',
    windows: [{
      tradingDays: 1,
      status: 'available',
      observedDate: '2026-07-21',
      symbolReturnPercent: 2,
      benchmarkReturnPercent: 1,
      relativeReturnPercent: 1,
      volumeRatio: 1.5,
    }, {
      tradingDays: 3,
      status: 'pending',
      observedDate: null,
      symbolReturnPercent: null,
      benchmarkReturnPercent: null,
      relativeReturnPercent: null,
      volumeRatio: null,
    }, {
      tradingDays: 5,
      status: 'insufficient_data',
      observedDate: null,
      symbolReturnPercent: null,
      benchmarkReturnPercent: null,
      relativeReturnPercent: null,
      volumeRatio: null,
    }, {
      tradingDays: 20,
      status: 'pending',
      observedDate: null,
      symbolReturnPercent: null,
      benchmarkReturnPercent: null,
      relativeReturnPercent: null,
      volumeRatio: null,
    }],
    sourceState: { source: 'yahoo_chart_public', status: 'fresh' },
    benchmarkSourceState: { source: 'yahoo_chart_public', status: 'fresh' },
    warningCodes: ['observation_window_incomplete'],
  }],
  warnings: [],
  cache: { hit: false, ageSeconds: 0, ttlSeconds: 900 },
  aiUsed: false,
  informationalOnly: true,
};

describe('MarketEventReactionPanelV136', () => {
  beforeEach(() => {
    vi.mocked(marketWorkspaceApi.getEventReactions).mockReset();
    vi.mocked(marketWorkspaceApi.getEventReactions).mockResolvedValue(response);
  });

  it('shows objective one-day observations and a Chinese non-causality boundary', async () => {
    const onOpenSymbol = vi.fn();
    render(
      <MarketEventReactionPanelV136
        language="zh"
        onOpenSymbol={onOpenSymbol}
      />,
    );

    const panel = await screen.findByTestId('market-event-reactions-v136');
    expect(within(panel).getByText('事件后市场观察')).toBeInTheDocument();
    expect(within(panel).getByText('+2.00%')).toBeInTheDocument();
    expect(within(panel).getAllByText('+1.00%')).toHaveLength(2);
    expect(within(panel).getByText('1.50 倍')).toBeInTheDocument();
    expect(within(panel).getByText(/事件日期 2026\/07\/20/)).toBeInTheDocument();
    expect(within(panel).getByText(/市场基准 标普500指数/)).toBeInTheDocument();
    expect(within(panel).getByText('Apple earnings release')).toBeInTheDocument();
    expect(within(panel).getByText(/来源: Yahoo 公开图表/)).toBeInTheDocument();
    expect(within(panel).getByText('同期表现不代表事件导致行情变化。仅提供资讯和数据，不构成投资建议。')).toBeInTheDocument();
    expect(within(panel).queryByText(/买入|卖出|目标价|利好|利空/)).not.toBeInTheDocument();

    fireEvent.click(within(panel).getByRole('button', { name: '查询 AAPL' }));
    expect(onOpenSymbol).toHaveBeenCalledWith('AAPL');
  });

  it('switches observation windows and localizes pending states in English', async () => {
    render(
      <MarketEventReactionPanelV136
        language="en"
        onOpenSymbol={vi.fn()}
      />,
    );

    const panel = await screen.findByTestId('market-event-reactions-v136');
    expect(within(panel).getByText('Post-event market observations')).toBeInTheDocument();
    fireEvent.click(within(panel).getByRole('button', { name: '3 trading days' }));
    expect(within(panel).getByText('Awaiting enough trading sessions')).toBeInTheDocument();
    expect(within(panel).getByText('Same-period performance does not establish that the event caused a market move. Information and data only. Not investment advice.')).toBeInTheDocument();
  });

  it('degrades honestly when the public endpoint is unavailable', async () => {
    vi.mocked(marketWorkspaceApi.getEventReactions).mockRejectedValue(new Error('offline'));
    render(
      <MarketEventReactionPanelV136
        language="zh"
        onOpenSymbol={vi.fn()}
      />,
    );

    await waitFor(() => {
      expect(screen.getByText('事件窗口行情暂时不可用，其他市场资讯仍可继续浏览。')).toBeInTheDocument();
    });
  });

  it('shows the remaining wait when the public endpoint is rate limited', async () => {
    const error = Object.assign(new Error('rate limited'), {
      response: {
        status: 429,
        data: {
          error: 'rate_limited',
          message: 'Too many requests',
          retry_after_seconds: 18,
        },
      },
    });
    vi.mocked(marketWorkspaceApi.getEventReactions).mockRejectedValue(error);
    render(
      <MarketEventReactionPanelV136
        language="zh"
        onOpenSymbol={vi.fn()}
      />,
    );

    expect(await screen.findByText('请求过于频繁，请等待 18 秒后重新加载。')).toBeInTheDocument();
  });

  it('shows source failure instead of presenting it as a real empty result', async () => {
    vi.mocked(marketWorkspaceApi.getEventReactions).mockResolvedValue({
      ...response,
      items: [],
      warnings: ['event_reaction_events_unavailable'],
    });
    render(
      <MarketEventReactionPanelV136
        language="zh"
        onOpenSymbol={vi.fn()}
      />,
    );

    expect(await screen.findByText('事件窗口行情暂时不可用，其他市场资讯仍可继续浏览。')).toBeInTheDocument();
    expect(screen.queryByText('暂未取得可计算的历史计划事件')).not.toBeInTheDocument();
  });

  it('keeps successful observations visible when another source is unavailable', async () => {
    vi.mocked(marketWorkspaceApi.getEventReactions).mockResolvedValue({
      ...response,
      warnings: ['event_reaction_source_unavailable'],
    });
    render(
      <MarketEventReactionPanelV136
        language="zh"
        onOpenSymbol={vi.fn()}
      />,
    );

    const panel = await screen.findByTestId('market-event-reactions-v136');
    expect(within(panel).getByRole('heading', { level: 4, name: /Apple Inc\./ })).toBeInTheDocument();
    expect(within(panel).getByText('+2.00%')).toBeInTheDocument();
  });

  it('does not claim no-AI output when the server reports AI use', async () => {
    vi.mocked(marketWorkspaceApi.getEventReactions).mockResolvedValue({
      ...response,
      aiUsed: true,
    });
    render(
      <MarketEventReactionPanelV136
        language="zh"
        onOpenSymbol={vi.fn()}
      />,
    );

    const panel = await screen.findByTestId('market-event-reactions-v136');
    expect(within(panel).getByText('响应未满足免 AI 数据边界，暂不展示该批数据。')).toBeInTheDocument();
    expect(within(panel).queryByText(/未使用 AI/)).not.toBeInTheDocument();
    expect(within(panel).queryByText('Apple Inc.')).not.toBeInTheDocument();
  });

  it('stays hidden when the V136 feature switch is disabled', async () => {
    vi.mocked(marketWorkspaceApi.getEventReactions).mockRejectedValue(
      Object.assign(new Error('disabled'), {
        response: {
          status: 404,
          data: { error: 'public_event_reactions_disabled' },
        },
      }),
    );
    render(
      <MarketEventReactionPanelV136
        language="zh"
        onOpenSymbol={vi.fn()}
      />,
    );

    await waitFor(() => {
      expect(screen.queryByTestId('market-event-reactions-v136')).not.toBeInTheDocument();
    });
  });
});
