import { Clock3, Database, Radio } from 'lucide-react';
import type { MarketWorkspaceOverview } from '../../api/marketWorkspace';
import { formatSourceLabel } from './marketWorkspaceFormat';

type Props = { language: 'zh' | 'en'; overview: MarketWorkspaceOverview };

const statusText = (status: string, en: boolean) => {
  const map: Record<string, [string, string]> = {
    open: ['交易中', 'Open'], closed: ['已休市', 'Closed'], unknown: ['状态未知', 'Unknown'],
    fresh: ['新鲜', 'Fresh'], cached: ['缓存', 'Cached'], stale: ['过期', 'Stale'], unavailable: ['不可用', 'Unavailable'],
  };
  return map[status]?.[en ? 1 : 0] ?? status;
};

export default function MarketPulseV113({ language, overview }: Props) {
  const en = language === 'en';
  return (
    <section className="grid gap-3 border-b border-border/70 py-5 md:grid-cols-4" aria-label={en ? 'Market pulse' : '市场脉搏'}>
      <div><span className="flex items-center gap-2 text-sm text-secondary-text"><Radio className="h-4 w-4" />{en ? 'Market status' : '市场状态'}</span><strong className="mt-2 block text-lg text-foreground">{statusText(overview.sessionState, en)}</strong></div>
      <div><span className="flex items-center gap-2 text-sm text-secondary-text"><Clock3 className="h-4 w-4" />{en ? 'Data time' : '数据时间'}</span><strong className="mt-2 block text-sm text-foreground">{new Date(overview.asOf).toLocaleString(en ? 'en-US' : 'zh-CN')}</strong></div>
      <div><span className="text-sm text-secondary-text">{en ? 'Market breadth' : '涨跌分布'}</span><strong className="mt-2 block text-lg text-foreground"><span className="text-emerald-400">{overview.breadth.advancers}</span> / <span className="text-rose-400">{overview.breadth.decliners}</span> / {overview.breadth.unchanged}</strong></div>
      <div><span className="flex items-center gap-2 text-sm text-secondary-text"><Database className="h-4 w-4" />{en ? 'Data sources' : '数据来源'}</span><div className="mt-2 flex flex-wrap gap-2">{overview.sources.map((source) => <span key={source.source} className="rounded-full border border-border px-2 py-1 text-xs text-secondary-text">{formatSourceLabel(source.source, language)} · {statusText(source.status, en)}</span>)}</div></div>
    </section>
  );
}
