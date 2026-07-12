import type { MarketSecurityItem } from '../../api/marketWorkspace';

type Props = { language: 'zh' | 'en'; items: MarketSecurityItem[]; onSelect: (symbol: string) => void };

export default function MarketMoversV113({ language, items, onSelect }: Props) {
  const en = language === 'en';
  return <section className="border-y border-border/70 py-5"><h2 className="text-lg font-semibold text-foreground">{en ? 'Observed movers' : '涨跌变化列表'}</h2><p className="mt-1 text-sm text-secondary-text">{en ? 'Sorted only by observed change, not investment value.' : '仅按已观测涨跌排序，不代表投资价值。'}</p><div className="mt-4 overflow-x-auto"><table className="w-full min-w-[620px] text-sm"><thead className="text-left text-secondary-text"><tr><th className="pb-3">{en ? 'Symbol' : '证券'}</th><th>{en ? 'Price' : '价格'}</th><th>{en ? 'Change' : '涨跌'}</th><th>{en ? 'Sector' : '板块'}</th><th>{en ? 'Freshness' : '新鲜度'}</th></tr></thead><tbody>{items.map((item) => <tr key={item.symbol} className="border-t border-border/50"><td className="py-3"><button type="button" onClick={() => onSelect(item.symbol)} className="text-left text-primary hover:underline"><strong className="block">{item.name}</strong><span className="text-xs text-secondary-text">{item.symbol}</span></button></td><td>{item.currentPrice ?? '-'}</td><td className={Number(item.changePercent) >= 0 ? 'text-emerald-400' : 'text-rose-400'}>{item.changePercent == null ? '-' : `${item.changePercent >= 0 ? '+' : ''}${item.changePercent.toFixed(2)}%`}</td><td>{item.sector ?? '-'}</td><td>{item.sourceState.status}</td></tr>)}</tbody></table></div></section>;
}
