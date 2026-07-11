import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { FreeKlineResearchV101 } from '../FreeKlineResearchV101';
import { stocksApi } from '../../../api/stocks';

vi.mock('../../../api/stocks', () => ({
  stocksApi: { history: vi.fn() },
}));

const bars = Array.from({ length: 30 }, (_, index) => ({
  date: `2026-06-${String(index + 1).padStart(2, '0')}`,
  open: 100 + index,
  high: 103 + index,
  low: 98 + index,
  close: 101 + index,
  volume: 1_000_000 + index * 20_000,
  amount: null,
  changePercent: index === 0 ? 0 : 0.8,
}));

describe('FreeKlineResearchV101', () => {
  beforeEach(() => {
    vi.mocked(stocksApi.history).mockReset();
    vi.mocked(stocksApi.history).mockResolvedValue({
      stockCode: 'AAPL',
      stockName: 'Apple Inc.',
      period: 'daily',
      source: 'yahoo_chart_history',
      data: bars,
    });
  });

  it('renders a Chinese no-AI evidence chart and reloads a selected range', async () => {
    render(<FreeKlineResearchV101 stockCode="AAPL" language="zh" />);

    const panel = await screen.findByTestId('free-kline-research-v101');
    expect(panel).toHaveTextContent('免费历史走势研究台');
    expect(panel).toHaveTextContent('未使用 AI');
    expect(panel).toHaveTextContent('区间涨跌');
    expect(panel).toHaveTextContent('最大回撤');
    expect(panel).toHaveTextContent('MA20');
    expect(panel).toHaveTextContent('Yahoo 公共历史行情');
    expect(stocksApi.history).toHaveBeenCalledWith('AAPL', 90);

    fireEvent.click(screen.getByRole('button', { name: '30日' }));
    await waitFor(() => expect(stocksApi.history).toHaveBeenLastCalledWith('AAPL', 30));
  });

  it('shows an English degraded state without exposing raw provider errors', async () => {
    vi.mocked(stocksApi.history).mockRejectedValueOnce(new Error('secret provider stack'));
    render(<FreeKlineResearchV101 stockCode="AAPL" language="en" />);

    expect(await screen.findByTestId('free-kline-research-error')).toHaveTextContent('Historical chart is temporarily unavailable');
    expect(screen.queryByText(/secret provider stack/i)).not.toBeInTheDocument();
  });

  it('uses the stock code instead of a localized company name in English copy', async () => {
    vi.mocked(stocksApi.history).mockResolvedValueOnce({
      stockCode: 'AAPL',
      stockName: '苹果',
      period: 'daily',
      source: 'yahoo_chart_history',
      data: bars,
    });

    render(<FreeKlineResearchV101 stockCode="AAPL" stockName="苹果" language="en" />);

    const panel = await screen.findByTestId('free-kline-research-v101');
    expect(panel).toHaveTextContent('AAPL actual daily history');
    expect(panel).not.toHaveTextContent('苹果');
  });

  it('limits the evidence model to the selected number of latest bars', async () => {
    const extendedBars = Array.from({ length: 45 }, (_, index) => ({
      ...bars[index % bars.length],
      date: `2026-05-${String(index + 1).padStart(2, '0')}`,
      close: 100 + index,
    }));
    vi.mocked(stocksApi.history).mockResolvedValue({
      stockCode: 'AAPL',
      stockName: 'Apple Inc.',
      period: 'daily',
      source: 'yahoo_chart_history',
      data: extendedBars,
    });

    render(<FreeKlineResearchV101 stockCode="AAPL" language="en" />);
    const panel = await screen.findByTestId('free-kline-research-v101');
    fireEvent.click(screen.getByRole('button', { name: '30D' }));

    await waitFor(() => expect(stocksApi.history).toHaveBeenLastCalledWith('AAPL', 30));
    expect(panel).toHaveTextContent('30 bars');
    expect(panel).not.toHaveTextContent('45 bars');
  });

  it('renders snapshot close history immediately while the full range is pending', async () => {
    vi.mocked(stocksApi.history).mockImplementation(() => new Promise(() => {}));
    render(
      <FreeKlineResearchV101
        stockCode="AAPL"
        stockName="Apple Inc."
        language="zh"
        initialTrend={{
          window: 20,
          source: 'snapshot_history',
          points: bars.slice(0, 20).map((item) => ({ date: item.date, close: item.close, volume: item.volume })),
        }}
      />,
    );

    expect(await screen.findByTestId('free-kline-research-v101')).toHaveTextContent('快速快照收盘线');
    expect(screen.getByTestId('free-kline-research-v101')).toHaveTextContent('完整历史更新中');
  });

  it('shows a clear empty state when no usable bars exist', async () => {
    vi.mocked(stocksApi.history).mockResolvedValueOnce({
      stockCode: 'AAPL',
      stockName: 'Apple Inc.',
      period: 'daily',
      source: 'history_empty',
      data: [],
    });
    render(<FreeKlineResearchV101 stockCode="AAPL" language="zh" />);

    expect(await screen.findByTestId('free-kline-research-empty')).toHaveTextContent('历史 K 线数据暂不足');
  });
});
