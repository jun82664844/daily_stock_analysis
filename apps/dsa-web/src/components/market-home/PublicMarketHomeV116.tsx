import { BellRing, Clock3, ExternalLink, RefreshCw } from 'lucide-react';
import { useState } from 'react';
import type { MarketCode, MarketSecurityItem, PublicMarketHomeResponse } from '../../api/marketWorkspace';
import PriceAlertFormV116, { type PriceAlertDraft } from '../alerts/PriceAlertFormV116';
import {
  formatMarketNumber,
  formatMarketTimestamp,
  formatSourceLabel,
  formatSourceStatus,
} from '../market-workspace/marketWorkspaceFormat';

type Props = {
  language: 'zh' | 'en';
  data: PublicMarketHomeResponse | null;
  loading: boolean;
  onOpenSymbol: (symbol: string) => void;
  onCreateAlert: (draft: PriceAlertDraft) => void | Promise<void>;
};

const MARKET_LABELS: Record<MarketCode, { zh: string; en: string }> = {
  cn: { zh: 'A股', en: 'A-shares' }, hk: { zh: '港股', en: 'Hong Kong' }, us: { zh: '美股', en: 'US stocks' },
};

const percent = (value: number | null | undefined) => value == null
  ? '-'
  : `${value > 0 ? '+' : ''}${value.toLocaleString(undefined, { maximumFractionDigits: 2 })}%`;

function SecurityCard({
  item, language, onOpen, onAlert, expanded, onToggle,
}: {
  item: MarketSecurityItem; language: 'zh' | 'en'; onOpen: () => void;
  onAlert: (draft: PriceAlertDraft) => void | Promise<void>; expanded: boolean; onToggle: () => void;
}) {
  const en = language === 'en';
  return (
    <article className="min-w-0 rounded-lg border border-border/70 bg-background/35 p-3">
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0"><h4 className="truncate font-semibold text-foreground">{item.name}</h4><p className="text-xs text-secondary-text">{item.symbol} · {item.currency ?? '-'}</p></div>
        <strong className={item.changePercent != null && item.changePercent < 0 ? 'text-danger' : 'text-success'}>{percent(item.changePercent)}</strong>
      </div>
      <div className="mt-3 flex items-end justify-between gap-3"><div><span className="text-xs text-secondary-text">{en ? 'Latest available price' : '最新可用价格'}</span><p className="text-xl font-semibold text-foreground">{formatMarketNumber(item.currentPrice, language)}</p></div><span className="rounded-full border border-border px-2 py-1 text-[11px] text-secondary-text">{formatSourceStatus(item.sourceState.status, language)}</span></div>
      <p className="mt-2 truncate text-[11px] text-secondary-text"><Clock3 className="mr-1 inline h-3 w-3" />{formatMarketTimestamp(item.sourceState.observedAt ?? item.sourceState.fetchedAt, language)} · {formatSourceLabel(item.sourceState.source, language)}</p>
      <div className="mt-3 flex flex-wrap gap-2">
        <button type="button" className="btn-secondary" aria-label={en ? `View ${item.name}` : `查看 ${item.name}`} onClick={onOpen}><ExternalLink className="h-4 w-4" />{en ? 'View stock' : '查看股票'}</button>
        <button type="button" className="btn-secondary" aria-label={en ? `Set price alert for ${item.name}` : `为 ${item.name} 设置到价提醒`} onClick={onToggle}><BellRing className="h-4 w-4" />{en ? 'Price alert' : '到价提醒'}</button>
      </div>
      {expanded ? <div className="mt-3 border-t border-border/70 pt-3"><PriceAlertFormV116 language={language} stockCode={item.symbol} stockName={item.name} currentPrice={item.currentPrice} currency={item.currency} onSave={async (draft) => { await onAlert(draft); }} /></div> : null}
    </article>
  );
}

export default function PublicMarketHomeV116({ language, data, loading, onOpenSymbol, onCreateAlert }: Props) {
  const en = language === 'en';
  const [activeMarket, setActiveMarket] = useState<MarketCode>('cn');
  const [expandedSymbol, setExpandedSymbol] = useState('');
  if (loading && !data) return <section className="mb-5 border-y border-border/70 py-6"><p className="flex items-center justify-center gap-2 text-secondary-text"><RefreshCw className="h-4 w-4 animate-spin" />{en ? 'Loading market overview...' : '正在加载市场速览...'}</p></section>;
  if (!data) return null;
  return (
    <section className="mb-5 border-y border-primary/30 bg-primary/5 py-5" data-testid="public-market-home-v116">
      <div className="px-4"><span className="text-xs font-medium text-primary">DSA V116</span><h2 className="mt-1 text-2xl font-semibold text-foreground">{en ? 'Three-market overview' : '三地市场速览'}</h2><p className="mt-1 text-sm text-secondary-text">{en ? 'Objective market attention across A-shares, Hong Kong and US stocks. No AI required.' : '无需 AI，查看 A股、港股和美股的客观市场关注变化。'}</p></div>
      <div className="mt-4 flex gap-2 overflow-x-auto px-4 md:hidden">{data.markets.map((section) => <button type="button" key={section.market} className={activeMarket === section.market ? 'btn-primary' : 'btn-secondary'} onClick={() => setActiveMarket(section.market)}>{MARKET_LABELS[section.market][language]}</button>)}</div>
      <div className="mt-4 grid min-w-0 gap-4 px-4 md:grid-cols-3">
        {data.markets.map((section) => (
          <section key={section.market} className={`${activeMarket === section.market ? 'block' : 'hidden'} min-w-0 md:block`} aria-label={MARKET_LABELS[section.market][language]}>
            <div className="mb-3 flex items-center justify-between gap-2"><div><h3 className="font-semibold text-foreground">{MARKET_LABELS[section.market][language]}</h3><p className="text-xs text-secondary-text">{section.rankingScope === 'configured_universe' ? (en ? 'Market attention' : '市场关注') : (en ? 'Active changes' : '活跃变化')}</p></div><span className="rounded-full border border-border px-2 py-1 text-[11px] text-secondary-text">{section.displayMode === 'delayed' ? (en ? 'Delayed data' : '延迟行情') : (en ? 'Latest available' : '最新可用')}</span></div>
            <div className="space-y-3">{section.attention.length ? section.attention.map((item) => <SecurityCard key={item.symbol} item={item} language={language} onOpen={() => onOpenSymbol(item.symbol)} onAlert={onCreateAlert} expanded={expandedSymbol === item.symbol} onToggle={() => setExpandedSymbol((value) => value === item.symbol ? '' : item.symbol)} />) : <div className="rounded-lg border border-dashed border-border p-5 text-center text-sm text-secondary-text">{en ? 'This market is temporarily unavailable' : '该市场暂时不可用'}</div>}</div>
          </section>
        ))}
      </div>
      <p className="mt-4 px-4 text-xs text-secondary-text">{en ? 'Information, objective data and user-defined alerts only. No investment advice.' : '仅提供市场资讯、客观数据和用户自定义提醒，不构成投资建议。'}</p>
    </section>
  );
}
