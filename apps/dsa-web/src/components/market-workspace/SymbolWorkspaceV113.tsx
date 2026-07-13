import { Activity, BookmarkPlus, Building2, Clock3, Database } from 'lucide-react';
import { Line, LineChart, Tooltip, XAxis, YAxis } from 'recharts';
import type { SymbolWorkspaceResponse } from '../../api/marketWorkspace';
import PriceAlertFormV116, { type PriceAlertDraft } from '../alerts/PriceAlertFormV116';
import {
  formatMarketNumber,
  formatMarketTimestamp,
  formatSourceLabel,
  formatSourceStatus,
} from './marketWorkspaceFormat';

type Props = {
  language: 'zh' | 'en';
  data: SymbolWorkspaceResponse;
  onAddWatchlist?: () => Promise<void>;
  onSaveAlert?: (draft: PriceAlertDraft) => Promise<void>;
  actionNotice?: string;
};

const optionalNumber = (value: unknown): number | null => {
  if (value == null || value === '') return null;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
};

export default function SymbolWorkspaceV113({
  language,
  data,
  onAddWatchlist,
  onSaveAlert,
  actionNotice,
}: Props) {
  const en = language === 'en';
  const quote = data.quote ?? {};
  const indicators = data.indicators ?? {};
  const chartData = (data.history ?? []).map((point) => ({
    date: String(point.date ?? ''),
    close: Number(point.close ?? 0),
  }));

  return (
    <section className="border-y border-primary/30 bg-primary/5 py-6" aria-label={en ? 'Symbol workspace' : '股票工作台'}>
      <div className="flex flex-col gap-3 px-4 md:flex-row md:items-end md:justify-between">
        <div>
          <span className="text-xs uppercase text-primary">{data.market} · {data.currency ?? '-'}</span>
          <h2 className="mt-1 text-2xl font-semibold text-foreground">{data.name}</h2>
          <p className="text-secondary-text">{data.symbol}</p>
        </div>
        <div className="flex flex-wrap gap-2 text-xs">
          <span className="rounded-full border border-primary/40 px-3 py-1 text-primary">{en ? 'No AI used' : '未使用 AI'}</span>
          <span className="rounded-full border border-border px-3 py-1 text-secondary-text">{formatSourceLabel(data.sources?.[0]?.source, language)} · {formatSourceStatus(data.sources?.[0]?.status, language)}</span>
        </div>
      </div>

      <div className="mt-5 grid gap-3 px-4 sm:grid-cols-2 lg:grid-cols-4">
        <div><span className="text-sm text-secondary-text">{en ? 'Latest price' : '最新价'}</span><strong className="mt-1 block text-xl text-foreground">{formatMarketNumber(quote.currentPrice, language)}</strong></div>
        <div><span className="text-sm text-secondary-text">{en ? 'Change' : '涨跌幅'}</span><strong className="mt-1 block text-xl text-foreground">{formatMarketNumber(quote.changePercent, language)}%</strong></div>
        <div><span className="text-sm text-secondary-text">MA5</span><strong className="mt-1 block text-xl text-foreground">{formatMarketNumber(indicators.ma5, language)}</strong></div>
        <div><span className="text-sm text-secondary-text">MA20</span><strong className="mt-1 block text-xl text-foreground">{formatMarketNumber(indicators.ma20, language)}</strong></div>
      </div>

      <div className="mt-5 flex flex-col gap-3 border-y border-border/70 px-4 py-4 lg:flex-row lg:items-end">
        <button type="button" className="btn-secondary" onClick={() => void onAddWatchlist?.()}>
          <BookmarkPlus className="h-4 w-4" />{en ? 'Add to watchlist' : '加入自选'}
        </button>
        <PriceAlertFormV116
          language={language}
          stockCode={data.symbol}
          stockName={data.name}
          currentPrice={optionalNumber(quote.currentPrice)}
          currency={data.currency}
          onSave={async (draft) => { if (onSaveAlert) await onSaveAlert(draft); }}
          notice={actionNotice}
        />
      </div>

      <div className="mt-6 grid min-w-0 gap-6 px-4 lg:grid-cols-[1.5fr_1fr]">
        <div className="min-w-0">
          <h3 className="flex items-center gap-2 font-medium text-foreground"><Activity className="h-4 w-4" />{en ? 'Daily close history' : '日线收盘历史'}</h3>
          <div className="mt-3 h-56 min-h-0 min-w-0 w-full" aria-label={en ? 'Daily close chart' : '日线收盘图'}>
            {chartData.length ? <LineChart responsive data={chartData} style={{ width: '100%', height: '100%' }}><XAxis dataKey="date" hide /><YAxis domain={['auto', 'auto']} width={55} /><Tooltip /><Line type="monotone" dataKey="close" stroke="hsl(var(--primary))" strokeWidth={2} dot={false} /></LineChart> : <p className="text-sm text-secondary-text">{en ? 'History unavailable.' : '历史数据不可用。'}</p>}
          </div>
        </div>
        <div className="space-y-4">
          <div><h3 className="flex items-center gap-2 font-medium text-foreground"><Building2 className="h-4 w-4" />{en ? 'Company facts' : '公司资料'}</h3><p className="mt-2 text-sm text-secondary-text">{String(data.profile?.sector ?? '-')} / {String(data.profile?.industry ?? '-')}</p></div>
          <div><h3 className="flex items-center gap-2 font-medium text-foreground"><Clock3 className="h-4 w-4" />{en ? 'Observed at' : '数据时间'}</h3><p className="mt-2 text-sm text-secondary-text">{formatMarketTimestamp(data.asOf, language)}</p></div>
          <div><h3 className="flex items-center gap-2 font-medium text-foreground"><Database className="h-4 w-4" />{en ? 'Source boundary' : '来源边界'}</h3><p className="mt-2 text-sm text-secondary-text">{en ? 'Missing modules stay unavailable and never become zero values.' : '缺失模块保持不可用，不会伪装为零值。'}</p></div>
        </div>
      </div>
    </section>
  );
}
