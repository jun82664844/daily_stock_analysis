import type { MarketSecurityItem } from '../../api/marketWorkspace';

type Props = { language: 'zh' | 'en'; items: MarketSecurityItem[]; onSelect: (symbol: string) => void };

export default function MarketHeatmapV113({ language, items, onSelect }: Props) {
  const en = language === 'en';
  return (
    <section className="py-5" aria-labelledby="market-heatmap-title">
      <h2 id="market-heatmap-title" className="text-lg font-semibold text-foreground">{en ? 'Market change map' : '市场涨跌图'}</h2>
      <p className="mt-1 text-sm text-secondary-text">{en ? 'Color and value both show observed change; unavailable size fields use equal tiles.' : '颜色和数值共同表示已观测涨跌；规模字段缺失时使用等面积网格。'}</p>
      <div className="mt-4 grid grid-cols-2 gap-2 md:grid-cols-4 lg:grid-cols-5">
        {items.length ? items.map((item) => {
          const change = item.changePercent;
          const tone = change == null ? 'border-border bg-surface' : change > 0 ? 'border-emerald-500/40 bg-emerald-500/10' : change < 0 ? 'border-rose-500/40 bg-rose-500/10' : 'border-border bg-surface';
          return <button type="button" key={item.symbol} onClick={() => onSelect(item.symbol)} className={`min-h-24 rounded-lg border p-3 text-left ${tone}`}><strong className="block text-foreground">{item.symbol}</strong><span className="mt-1 block truncate text-sm text-secondary-text">{item.name}</span><span className="mt-3 block font-mono text-sm text-foreground">{change == null ? '-' : `${change >= 0 ? '+' : ''}${change.toFixed(2)}%`}</span></button>;
        }) : <p className="col-span-full py-6 text-sm text-secondary-text">{en ? 'Heatmap data is unavailable.' : '涨跌图数据暂不可用。'}</p>}
      </div>
    </section>
  );
}
