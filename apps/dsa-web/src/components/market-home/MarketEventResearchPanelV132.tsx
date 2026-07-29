import { Database, ListChecks, Search, X } from 'lucide-react';
import type { MarketSecurityItem, PublicMarketEvent } from '../../api/marketWorkspace';
import {
  formatMarketNumber,
  formatMarketTimestamp,
  formatSourceLabel,
  formatSourceStatus,
} from '../market-workspace/marketWorkspaceFormat';

type Props = {
  language: 'zh' | 'en';
  event: PublicMarketEvent;
  marketItem?: MarketSecurityItem;
  onOpenSymbol: (symbol: string) => void;
  onClose: () => void;
};

function compactNumber(value: number | null | undefined, language: 'zh' | 'en'): string {
  if (value == null || !Number.isFinite(value)) return language === 'en' ? 'Unavailable' : '暂不可用';
  const abs = Math.abs(value);
  if (language === 'zh') {
    if (abs >= 100_000_000) return `${(value / 100_000_000).toLocaleString('zh-CN', { maximumFractionDigits: 2 })}亿`;
    if (abs >= 10_000) return `${(value / 10_000).toLocaleString('zh-CN', { maximumFractionDigits: 1 })}万`;
    return value.toLocaleString('zh-CN', { maximumFractionDigits: 2 });
  }
  if (abs >= 1_000_000_000) return `${(value / 1_000_000_000).toLocaleString('en-US', { maximumFractionDigits: 2 })}B`;
  if (abs >= 1_000_000) return `${(value / 1_000_000).toLocaleString('en-US', { maximumFractionDigits: 1 })}M`;
  return value.toLocaleString('en-US', { maximumFractionDigits: 2 });
}

function percent(value: number | null | undefined, language: 'zh' | 'en'): string {
  if (value == null || !Number.isFinite(value)) return language === 'en' ? 'Unavailable' : '暂不可用';
  return `${value > 0 ? '+' : ''}${value.toLocaleString(language === 'en' ? 'en-US' : 'zh-CN', { maximumFractionDigits: 2 })}%`;
}

export default function MarketEventResearchPanelV132({
  language,
  event,
  marketItem,
  onOpenSymbol,
  onClose,
}: Props) {
  const en = language === 'en';
  const symbol = event.symbol ?? '';
  const observedAt = marketItem?.sourceState.observedAt ?? marketItem?.sourceState.fetchedAt;

  return (
    <section
      data-testid="market-event-research-panel-v132"
      className="border-y border-cyan-400/30 bg-cyan-400/[0.04] px-4 py-4"
      aria-label={en ? `Research event linked to ${symbol}` : `研究 ${symbol} 关联事件`}
    >
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0">
          <p className="text-xs font-semibold text-cyan-300">{en ? 'Event research card · No AI used' : '事件研究卡 · 未使用 AI'}</p>
          <h4 className="mt-1 text-base font-semibold text-slate-100">{en ? 'Event research card' : '事件研究卡'}</h4>
          <p className="mt-1 text-sm leading-6 text-slate-300">{event.title}</p>
        </div>
        <button
          type="button"
          onClick={onClose}
          aria-label={en ? 'Close event research card' : '关闭事件研究卡'}
          className="inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-md border border-white/10 text-slate-400 hover:border-cyan-400/40 hover:text-cyan-300"
        >
          <X className="h-4 w-4" aria-hidden="true" />
        </button>
      </div>

      <div className="mt-4 grid gap-px overflow-hidden border-y border-white/10 bg-white/10 sm:grid-cols-3">
        <div className="min-w-0 bg-[#0a101b] px-3 py-3">
          <span className="block text-xs text-slate-500">{en ? 'Linked security' : '关联证券'}</span>
          <strong className="mt-1 block truncate text-sm text-slate-100">{symbol} · {event.name || marketItem?.name || symbol}</strong>
        </div>
        <div className="min-w-0 bg-[#0a101b] px-3 py-3">
          <span className="block text-xs text-slate-500">{en ? 'Event source records' : '事件来源记录'}</span>
          <strong className="mt-1 block text-sm text-slate-100">{event.sourceCount}</strong>
        </div>
        <div className="min-w-0 bg-[#0a101b] px-3 py-3">
          <span className="block text-xs text-slate-500">{en ? 'Event time' : '事件时间'}</span>
          <strong className="mt-1 block text-sm text-slate-100">{formatMarketTimestamp(event.eventTime, language)}</strong>
        </div>
      </div>

      {marketItem ? (
        <div className="mt-4" data-testid="market-event-public-quote-v132">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h5 className="text-sm font-semibold text-slate-200">{en ? 'Latest public market context' : '最新公开行情背景'}</h5>
            <span className="inline-flex items-center gap-1.5 text-xs text-slate-500">
              <Database className="h-3.5 w-3.5" aria-hidden="true" />
              {formatSourceLabel(marketItem.sourceState.source, language)} · {formatSourceStatus(marketItem.sourceState.status, language)}
            </span>
          </div>
          <div className="mt-2 grid gap-px overflow-hidden border-y border-white/10 bg-white/10 grid-cols-2 lg:grid-cols-4">
            {[
              [en ? 'Latest' : '最新价', formatMarketNumber(marketItem.currentPrice, language)],
              [en ? 'Change' : '涨跌幅', percent(marketItem.changePercent, language)],
              [en ? 'Volume' : '成交量', compactNumber(marketItem.volume, language)],
              [en ? 'Turnover' : '成交额', compactNumber(marketItem.turnover, language)],
            ].map(([label, value]) => (
              <div key={label} className="min-w-0 bg-[#0a101b] px-3 py-3">
                <span className="block text-xs text-slate-500">{label}</span>
                <strong className="mt-1 block truncate text-sm text-slate-100">{value}</strong>
              </div>
            ))}
          </div>
          <p className="mt-2 text-xs text-slate-500">
            {en ? 'Market observation' : '行情时间'}: {formatMarketTimestamp(observedAt, language)}
          </p>
        </div>
      ) : (
        <div className="mt-4 border-y border-amber-400/20 bg-amber-400/[0.04] px-3 py-3" data-testid="market-event-quote-unavailable-v132">
          <p className="text-sm text-amber-200">
            {en
              ? 'This security is not present in the loaded public rankings. Open the stock page to request the latest available data.'
              : '当前公开榜单未包含此关联证券的行情快照，可进入个股页查询最新数据。'}
          </p>
        </div>
      )}

      <div className="mt-4 border-t border-white/10 pt-3">
        <h5 className="flex items-center gap-2 text-sm font-semibold text-slate-200">
          <ListChecks className="h-4 w-4 text-cyan-300" aria-hidden="true" />
          {en ? 'Research checklist' : '资料核验清单'}
        </h5>
        <ul className="mt-2 grid gap-2 text-xs text-slate-400 sm:grid-cols-3">
          <li>{en ? 'Check the original source and event time' : '核对原文与事件时间'}</li>
          <li>{en ? 'Verify quote source and freshness' : '检查行情来源和新鲜度'}</li>
          <li>{en ? 'Compare later price and volume changes' : '比较后续价格和成交量变化'}</li>
        </ul>
      </div>

      <div className="mt-4 flex flex-col gap-3 border-t border-white/10 pt-3 sm:flex-row sm:items-end sm:justify-between">
        <div className="max-w-3xl text-xs leading-5 text-slate-500">
          <p>{en ? 'Price changes and the event are shown together; this does not mean the event caused the move.' : '价格变化与事件同时呈现，不代表事件导致涨跌。'}</p>
          <p>{en ? 'Public information and data only. Not investment advice.' : '仅提供公开资讯和数据，不构成投资建议。'}</p>
        </div>
        <button
          type="button"
          onClick={() => onOpenSymbol(symbol)}
          aria-label={en ? `Query linked security ${symbol}` : `查询关联证券 ${symbol}`}
          className="inline-flex min-h-10 shrink-0 items-center justify-center gap-2 rounded-lg border border-cyan-400/30 px-3 text-sm text-cyan-300 hover:bg-cyan-400/10"
        >
          <Search className="h-4 w-4" aria-hidden="true" />
          {en ? 'Query linked security' : '查询关联证券'}
        </button>
      </div>
    </section>
  );
}
