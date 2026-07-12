import type { MarketDailyBriefResponse } from '../../api/marketWorkspace';

type Props = { language: 'zh' | 'en'; brief: MarketDailyBriefResponse | null; loginRequired: boolean };

export default function WatchlistBriefV113({ language, brief, loginRequired }: Props) {
  const en = language === 'en';
  return <section className="border-t border-border/70 py-5"><h2 className="text-lg font-semibold text-foreground">{en ? 'My watchlist brief' : '我的自选简报'}</h2>{loginRequired ? <p className="mt-2 text-sm text-secondary-text">{en ? 'Sign in to save a watchlist, condition alerts and a private no-AI brief. Market data remains public.' : '登录后可保存自选、条件提醒和私人未用 AI 简报；市场数据仍可公开查看。'}</p> : brief?.items?.length ? <div className="mt-3 flex flex-wrap gap-2">{brief.items.map((item) => <span key={item.symbol} className="rounded-lg border border-border px-3 py-2 text-sm text-foreground">{item.symbol} · {item.changePercent == null ? '-' : `${item.changePercent.toFixed(2)}%`}</span>)}</div> : <p className="mt-2 text-sm text-secondary-text">{en ? 'Your watchlist is empty.' : '自选股为空，可从股票工作台添加。'}</p>}</section>;
}
