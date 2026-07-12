import { Activity, BellRing, BookmarkPlus, Building2, Clock3, Database } from 'lucide-react';
import { useState } from 'react';
import { Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import type { SymbolWorkspaceResponse } from '../../api/marketWorkspace';

type AlertRuleType = 'price_above' | 'price_below';
type Props = {
  language: 'zh' | 'en';
  data: SymbolWorkspaceResponse;
  onAddWatchlist?: () => Promise<void>;
  onSaveAlert?: (ruleType: AlertRuleType, threshold: number) => Promise<void>;
  actionNotice?: string;
};

const number = (value: unknown) => value == null || Number.isNaN(Number(value))
  ? '-'
  : Number(value).toLocaleString(undefined, { maximumFractionDigits: 4 });

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
  const [ruleType, setRuleType] = useState<AlertRuleType>('price_above');
  const [threshold, setThreshold] = useState(String(quote.currentPrice ?? ''));

  const thresholdNumber = Number(threshold);
  const canSaveAlert = Number.isFinite(thresholdNumber) && thresholdNumber > 0;

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
          <span className="rounded-full border border-border px-3 py-1 text-secondary-text">{data.sources?.[0]?.source ?? '-'} · {data.sources?.[0]?.status ?? '-'}</span>
        </div>
      </div>

      <div className="mt-5 grid gap-3 px-4 sm:grid-cols-2 lg:grid-cols-4">
        <div><span className="text-sm text-secondary-text">{en ? 'Latest price' : '最新价'}</span><strong className="mt-1 block text-xl text-foreground">{number(quote.currentPrice)}</strong></div>
        <div><span className="text-sm text-secondary-text">{en ? 'Change' : '涨跌幅'}</span><strong className="mt-1 block text-xl text-foreground">{number(quote.changePercent)}%</strong></div>
        <div><span className="text-sm text-secondary-text">MA5</span><strong className="mt-1 block text-xl text-foreground">{number(indicators.ma5)}</strong></div>
        <div><span className="text-sm text-secondary-text">MA20</span><strong className="mt-1 block text-xl text-foreground">{number(indicators.ma20)}</strong></div>
      </div>

      <div className="mt-5 flex flex-col gap-3 border-y border-border/70 px-4 py-4 lg:flex-row lg:items-end">
        <button type="button" className="btn-secondary" onClick={() => void onAddWatchlist?.()}>
          <BookmarkPlus className="h-4 w-4" />{en ? 'Add to watchlist' : '加入自选'}
        </button>
        <label className="flex min-w-0 flex-col gap-1 text-sm text-secondary-text">
          {en ? 'Condition direction' : '条件方向'}
          <select className="h-10 rounded-lg border border-border bg-surface px-3 text-foreground" value={ruleType} onChange={(event) => setRuleType(event.target.value as AlertRuleType)}>
            <option value="price_above">{en ? 'Price above' : '价格高于'}</option>
            <option value="price_below">{en ? 'Price below' : '价格低于'}</option>
          </select>
        </label>
        <label className="flex min-w-0 flex-col gap-1 text-sm text-secondary-text">
          {en ? 'Condition threshold' : '条件阈值'}
          <input aria-label={en ? 'Condition threshold' : '条件阈值'} type="number" min="0" step="any" className="h-10 rounded-lg border border-border bg-surface px-3 text-foreground" value={threshold} onChange={(event) => setThreshold(event.target.value)} />
        </label>
        <button type="button" className="btn-secondary" disabled={!canSaveAlert} onClick={() => void onSaveAlert?.(ruleType, thresholdNumber)}>
          <BellRing className="h-4 w-4" />{en ? 'Save condition alert' : '保存条件提醒'}
        </button>
        {actionNotice ? <p className="text-sm text-secondary-text" role="status">{actionNotice}</p> : null}
      </div>

      <div className="mt-6 grid min-w-0 gap-6 px-4 lg:grid-cols-[1.5fr_1fr]">
        <div className="min-w-0">
          <h3 className="flex items-center gap-2 font-medium text-foreground"><Activity className="h-4 w-4" />{en ? 'Daily close history' : '日线收盘历史'}</h3>
          <div className="mt-3 h-56 min-h-0 min-w-0 w-full" aria-label={en ? 'Daily close chart' : '日线收盘图'}>
            {chartData.length ? <ResponsiveContainer width="100%" height="100%" minWidth={1} minHeight={1}><LineChart data={chartData}><XAxis dataKey="date" hide /><YAxis domain={['auto', 'auto']} width={55} /><Tooltip /><Line type="monotone" dataKey="close" stroke="hsl(var(--primary))" strokeWidth={2} dot={false} /></LineChart></ResponsiveContainer> : <p className="text-sm text-secondary-text">{en ? 'History unavailable.' : '历史数据不可用。'}</p>}
          </div>
        </div>
        <div className="space-y-4">
          <div><h3 className="flex items-center gap-2 font-medium text-foreground"><Building2 className="h-4 w-4" />{en ? 'Company facts' : '公司资料'}</h3><p className="mt-2 text-sm text-secondary-text">{String(data.profile?.sector ?? '-')} / {String(data.profile?.industry ?? '-')}</p></div>
          <div><h3 className="flex items-center gap-2 font-medium text-foreground"><Clock3 className="h-4 w-4" />{en ? 'Observed at' : '数据时间'}</h3><p className="mt-2 text-sm text-secondary-text">{data.asOf ?? '-'}</p></div>
          <div><h3 className="flex items-center gap-2 font-medium text-foreground"><Database className="h-4 w-4" />{en ? 'Source boundary' : '来源边界'}</h3><p className="mt-2 text-sm text-secondary-text">{en ? 'Missing modules stay unavailable and never become zero values.' : '缺失模块保持不可用，不会伪装为零值。'}</p></div>
        </div>
      </div>
    </section>
  );
}
