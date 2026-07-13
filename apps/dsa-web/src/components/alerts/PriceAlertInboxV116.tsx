import { Bell, Check, CheckCheck, RefreshCw } from 'lucide-react';
import { useCallback, useEffect, useRef, useState } from 'react';
import {
  PLATFORM_SESSION_CHANGED_EVENT,
  platformApi,
  type PlatformWatchlistAlertEventsResponse,
} from '../../api/platform';

type Props = { language: 'zh' | 'en' };

export default function PriceAlertInboxV116({ language }: Props) {
  const en = language === 'en';
  const [userId, setUserId] = useState<number | null>(null);
  const [feed, setFeed] = useState<PlatformWatchlistAlertEventsResponse | null>(null);
  const [open, setOpen] = useState(false);
  const [failed, setFailed] = useState(false);
  const requestId = useRef(0);

  const refresh = useCallback(async () => {
    const id = ++requestId.current;
    try {
      const auth = await platformApi.current();
      if (id !== requestId.current) return;
      const nextUserId = auth?.user?.id ?? null;
      setUserId(nextUserId);
      if (nextUserId == null) {
        setFeed(null);
        setOpen(false);
        setFailed(false);
        return;
      }
      const nextFeed = await platformApi.alertEvents(false, 20);
      if (id !== requestId.current || nextFeed.userId !== nextUserId) return;
      setFeed(nextFeed);
      setFailed(false);
    } catch {
      if (id === requestId.current) setFailed(true);
    }
  }, []);

  useEffect(() => {
    const initialRefresh = window.setTimeout(() => void refresh(), 0);
    const interval = window.setInterval(() => void refresh(), 60_000);
    const onSessionChanged = () => void refresh();
    window.addEventListener(PLATFORM_SESSION_CHANGED_EVENT, onSessionChanged);
    return () => {
      requestId.current += 1;
      window.clearTimeout(initialRefresh);
      window.clearInterval(interval);
      window.removeEventListener(PLATFORM_SESSION_CHANGED_EVENT, onSessionChanged);
    };
  }, [refresh]);

  const apply = (next: PlatformWatchlistAlertEventsResponse) => {
    if (next.userId === userId) setFeed(next);
  };

  if (userId == null) return null;
  const unread = feed?.unread ?? 0;
  const label = unread
    ? (en ? `Price alert inbox, ${unread} unread` : `到价提醒收件箱，${unread} 条未读`)
    : (en ? 'Price alert inbox' : '到价提醒收件箱');

  return (
    <div className="relative">
      <button
        type="button"
        className="relative inline-flex h-10 w-10 items-center justify-center rounded-xl border border-border/70 bg-card/70 text-secondary-text hover:bg-hover hover:text-foreground"
        aria-label={label}
        aria-expanded={open}
        onClick={() => setOpen((value) => !value)}
      >
        <Bell className="h-5 w-5" />
        {unread > 0 ? <span className="absolute -right-1 -top-1 min-w-5 rounded-full bg-primary px-1 text-center text-[10px] font-semibold text-primary-foreground">{unread > 99 ? '99+' : unread}</span> : null}
      </button>
      {open ? (
        <section className="absolute right-0 top-12 z-50 w-[min(22rem,calc(100vw-2rem))] rounded-lg border border-border bg-card p-3 shadow-2xl" aria-label={en ? 'Price alert events' : '到价提醒事件'}>
          <div className="flex items-center justify-between gap-2 border-b border-border/70 pb-2">
            <div><h2 className="text-sm font-semibold text-foreground">{en ? 'Price alerts' : '到价提醒'}</h2><p className="text-xs text-secondary-text">{en ? 'Your private threshold events' : '您的私有价格阈值事件'}</p></div>
            <div className="flex gap-1">
              <button type="button" className="icon-btn" aria-label={en ? 'Refresh price alerts' : '刷新到价提醒'} onClick={() => void refresh()}><RefreshCw className="h-4 w-4" /></button>
              {unread ? <button type="button" className="icon-btn" aria-label={en ? 'Mark all price alerts read' : '全部标记为已读'} onClick={() => void platformApi.markAllAlertEventsRead().then(apply)}><CheckCheck className="h-4 w-4" /></button> : null}
            </div>
          </div>
          {failed ? <p role="status" className="mt-2 text-xs text-amber-300">{en ? 'Refresh failed; previous events are retained.' : '刷新失败，已保留上次事件。'}</p> : null}
          <div className="mt-2 max-h-80 space-y-2 overflow-y-auto">
            {feed?.items?.length ? feed.items.map((item) => (
              <article key={item.id} className="rounded-lg border border-border/70 p-3">
                <div className="flex items-start justify-between gap-2">
                  <div><strong className="text-sm text-foreground">{item.stockCode}</strong><p className="text-xs text-secondary-text">{item.direction === 'below' ? (en ? 'At or below' : '达到或低于') : (en ? 'At or above' : '达到或高于')} {item.threshold ?? '-'}</p></div>
                  {!item.readAt ? <button type="button" className="icon-btn" aria-label={en ? `Mark ${item.stockCode} alert read` : `标记 ${item.stockCode} 提醒为已读`} onClick={() => void platformApi.markAlertEventRead(item.id).then(apply)}><Check className="h-4 w-4" /></button> : null}
                </div>
                <p className="mt-2 text-xs text-secondary-text">{en ? 'Observed' : '触发价格'} {item.value ?? '-'} · {item.source ?? '-'}</p>
                <p className="mt-1 text-[11px] text-secondary-text">{item.observedAt ?? item.createdAt ?? '-'}</p>
              </article>
            )) : <p className="py-5 text-center text-sm text-secondary-text">{en ? 'No price alert events yet.' : '暂无到价提醒事件。'}</p>}
          </div>
          <p className="mt-2 border-t border-border/70 pt-2 text-[11px] text-secondary-text">{en ? 'Information and user-defined reminders only. No investment advice.' : '仅提供资讯和用户自定义提醒，不构成投资建议。'}</p>
        </section>
      ) : null}
    </div>
  );
}
