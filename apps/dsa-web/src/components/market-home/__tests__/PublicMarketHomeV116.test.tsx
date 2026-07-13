import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import type { PublicMarketHomeResponse } from '../../../api/marketWorkspace';
import PublicMarketHomeV116 from '../PublicMarketHomeV116';

const data: PublicMarketHomeResponse = {
  asOf: '2026-07-13T01:30:00Z', aiUsed: false, informationalOnly: true,
  markets: [
    { market: 'cn', sessionState: 'unknown', displayMode: 'latest_available', rankingScope: 'configured_universe', selectionBasis: 'turnover_then_absolute_change', indices: [], sources: [], warnings: [], attention: [{ symbol: '600519.SH', name: '贵州茅台', market: 'cn', currency: 'CNY', currentPrice: 1188.8, changePercent: -1.5, sourceState: { source: 'cn_quote', status: 'fresh', observedAt: '2026-07-13T01:29:00Z' } }] },
    { market: 'hk', sessionState: 'unknown', displayMode: 'delayed', rankingScope: 'configured_universe', selectionBasis: 'turnover_then_absolute_change', indices: [], sources: [], warnings: [], attention: [{ symbol: '0700.HK', name: '腾讯控股', market: 'hk', currency: 'HKD', currentPrice: 500, changePercent: 1.25, sourceState: { source: 'hk_quote', status: 'cached' } }] },
    { market: 'us', sessionState: 'unknown', displayMode: 'latest_available', rankingScope: 'configured_universe', selectionBasis: 'turnover_then_absolute_change', indices: [], sources: [], warnings: ['market_home_unavailable'], attention: [] },
  ],
};

describe('PublicMarketHomeV116', () => {
  it('shows three markets with latest-available wording and partial degradation', () => {
    render(<PublicMarketHomeV116 language="zh" data={data} loading={false} onOpenSymbol={vi.fn()} onCreateAlert={vi.fn()} />);
    expect(screen.getByRole('heading', { name: '三地市场速览' })).toBeInTheDocument();
    expect(screen.getAllByText('市场关注')).toHaveLength(3);
    expect(screen.queryByText('全市场热门')).not.toBeInTheDocument();
    expect(screen.queryByText('实时股价')).not.toBeInTheDocument();
    expect(screen.getByText('贵州茅台')).toBeInTheDocument();
    expect(screen.getByText('腾讯控股')).toBeInTheDocument();
    expect(screen.getByText('该市场暂时不可用')).toBeInTheDocument();
    expect(screen.getByText('缓存')).toBeInTheDocument();
    expect(screen.queryByText('cached')).not.toBeInTheDocument();
    expect(screen.getByText(/港股行情/)).toBeInTheDocument();
    expect(screen.queryByText(/hk_quote/)).not.toBeInTheDocument();
    expect(screen.queryByText(/yahoo_chart_reference/)).not.toBeInTheDocument();
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
