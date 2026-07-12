import { ExternalLink } from 'lucide-react';
import type { MarketHeadline } from '../../api/marketWorkspace';

type Props = { language: 'zh' | 'en'; items: MarketHeadline[] };

export default function MarketNewsTimelineV113({ language, items }: Props) {
  const en = language === 'en';
  return <section className="py-5"><h2 className="text-lg font-semibold text-foreground">{en ? 'Information timeline' : '资讯时间线'}</h2><div className="mt-4 grid gap-3">{items.length ? items.map((item, index) => <article key={`${item.title}:${index}`} className="border-l-2 border-primary/50 pl-4"><div className="flex flex-wrap items-center gap-2 text-xs text-secondary-text"><span>{item.publisher ?? item.sourceState.source}</span><span>{item.publishedAt ? new Date(item.publishedAt).toLocaleString(en ? 'en-US' : 'zh-CN') : (en ? 'Time unavailable' : '时间不可用')}</span></div><h3 className="mt-1 font-medium text-foreground">{item.title}</h3>{item.summary ? <p className="mt-1 text-sm text-secondary-text">{item.summary}</p> : null}{item.url ? <a href={item.url} target="_blank" rel="noopener noreferrer" className="mt-2 inline-flex items-center gap-1 text-sm text-primary">{en ? 'Open source' : '打开来源'}<ExternalLink className="h-3.5 w-3.5" /></a> : null}</article>) : <p className="py-5 text-sm text-secondary-text">{en ? 'No authorized information source is currently available.' : '当前没有可用的授权资讯来源。'}</p>}</div></section>;
}
