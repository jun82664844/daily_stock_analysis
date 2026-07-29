import { BookmarkX, CalendarClock, Search } from 'lucide-react';
import type { PublicMarketEvent } from '../../api/marketWorkspace';
import { formatMarketTimestamp } from '../market-workspace/marketWorkspaceFormat';
import {
  buildFollowUpCheckpoints,
  latestFollowUpEvents,
  type FollowedMarketEventV133,
  type MarketEventQuoteObservationV133,
} from './marketEventFollowUpV133';

type Props = {
  language: 'zh' | 'en';
  followedEvents: FollowedMarketEventV133[];
  publicEvents: PublicMarketEvent[];
  now?: Date;
  onOpenSymbol: (symbol: string) => void;
  onRemove: (eventId: string) => void;
};

function price(value: number | null | undefined, language: 'zh' | 'en'): string {
  if (value == null || !Number.isFinite(value)) return language === 'en' ? 'Unavailable' : '暂无';
  return value.toLocaleString(language === 'en' ? 'en-US' : 'zh-CN', {
    maximumFractionDigits: 4,
  });
}

function changeFromBaseline(
  baseline: MarketEventQuoteObservationV133 | null,
  latest: MarketEventQuoteObservationV133 | undefined,
  language: 'zh' | 'en',
): string {
  if (
    baseline?.price == null
    || latest?.price == null
    || !Number.isFinite(baseline.price)
    || !Number.isFinite(latest.price)
    || baseline.price === 0
  ) {
    return language === 'en' ? 'Unavailable' : '暂无';
  }
  const value = ((latest.price - baseline.price) / baseline.price) * 100;
  return `${value > 0 ? '+' : ''}${value.toLocaleString(language === 'en' ? 'en-US' : 'zh-CN', {
    maximumFractionDigits: 2,
  })}%`;
}

export default function MarketEventFollowUpPanelV133({
  language,
  followedEvents,
  publicEvents,
  now = new Date(),
  onOpenSymbol,
  onRemove,
}: Props) {
  if (followedEvents.length === 0) return null;
  const en = language === 'en';

  return (
    <section
      data-testid="market-event-follow-up-panel-v133"
      className="border-y border-cyan-400/25 bg-cyan-400/[0.035] px-4 py-4"
      aria-label={en ? 'Event follow-up' : '事件后续追踪'}
    >
      <div className="flex flex-col gap-2 border-b border-white/10 pb-3 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p className="text-xs font-semibold text-cyan-300">
            {en ? 'Local follow-up record · No AI used' : '本地追踪记录 · 未使用 AI'}
          </p>
          <h3 className="mt-1 text-lg font-semibold text-slate-100">
            {en ? 'Event follow-up' : '事件后续追踪'}
          </h3>
          <p className="mt-1 text-sm text-slate-400">
            {en
              ? 'Revisit public events with later market observations and source updates.'
              : '用后续公开行情观察和来源更新，持续复盘已关注的市场事件。'}
          </p>
        </div>
        <span className="text-xs text-slate-500">
          {en ? `${followedEvents.length} followed` : `已关注 ${followedEvents.length} 条`}
        </span>
      </div>

      <div className="mt-4 grid gap-3">
        {followedEvents.map((followed) => {
          const latest = followed.observations.at(-1);
          const checkpoints = buildFollowUpCheckpoints(followed, now);
          const laterEvents = latestFollowUpEvents(followed, publicEvents);
          const relativeChange = changeFromBaseline(followed.baseline, latest, language);
          const relativePositive = relativeChange.startsWith('+');
          const relativeNegative = relativeChange.startsWith('-');

          return (
            <article
              key={followed.eventId}
              className="border border-white/10 bg-[#0a101b] p-4"
              data-testid={`market-event-follow-up-${followed.eventId}`}
            >
              <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2 text-xs text-slate-500">
                    <span className="font-semibold text-cyan-300">{followed.symbol}</span>
                    <span>{followed.name}</span>
                    <span>{followed.publisher}</span>
                  </div>
                  <h4 className="mt-1 text-base font-semibold text-slate-100">{followed.title}</h4>
                  <p className="mt-1 text-xs text-slate-500">
                    {en ? 'Followed' : '关注时间'} {formatMarketTimestamp(followed.followedAt, language)}
                  </p>
                </div>
                <div className="flex shrink-0 gap-2">
                  <button
                    type="button"
                    onClick={() => onOpenSymbol(followed.symbol)}
                    aria-label={en ? `Query ${followed.symbol}` : `查询 ${followed.symbol}`}
                    className="inline-flex min-h-10 items-center justify-center gap-2 rounded-md border border-cyan-400/30 px-3 text-sm text-cyan-300 hover:bg-cyan-400/10"
                  >
                    <Search className="h-4 w-4" aria-hidden="true" />
                    {en ? 'Query' : '查询'}
                  </button>
                  <button
                    type="button"
                    onClick={() => onRemove(followed.eventId)}
                    aria-label={en ? `Stop following ${followed.symbol}` : `取消关注 ${followed.symbol}`}
                    className="inline-flex h-10 w-10 items-center justify-center rounded-md border border-white/10 text-slate-400 hover:border-rose-400/30 hover:text-rose-300"
                  >
                    <BookmarkX className="h-4 w-4" aria-hidden="true" />
                  </button>
                </div>
              </div>

              <div className="mt-4 grid gap-px overflow-hidden border-y border-white/10 bg-white/10 sm:grid-cols-3">
                <div className="bg-[#080e18] px-3 py-3">
                  <span className="text-xs text-slate-500">{en ? 'Follow-time baseline' : '关注时基准'}</span>
                  <strong className="mt-1 block text-sm text-slate-100">{price(followed.baseline?.price, language)}</strong>
                </div>
                <div className="bg-[#080e18] px-3 py-3">
                  <span className="text-xs text-slate-500">{en ? 'Latest observation' : '最新观察'}</span>
                  <strong className="mt-1 block text-sm text-slate-100">{price(latest?.price, language)}</strong>
                </div>
                <div className="bg-[#080e18] px-3 py-3">
                  <span className="text-xs text-slate-500">{en ? 'Since followed' : '较关注时'}</span>
                  <strong
                    className={`mt-1 block text-sm ${
                      relativePositive ? 'text-emerald-300' : relativeNegative ? 'text-rose-300' : 'text-slate-100'
                    }`}
                  >
                    {relativeChange}
                  </strong>
                </div>
              </div>

              <div className="mt-4">
                <h5 className="flex items-center gap-2 text-sm font-semibold text-slate-200">
                  <CalendarClock className="h-4 w-4 text-cyan-300" aria-hidden="true" />
                  {en ? 'Observation checkpoints' : '观察节点'}
                </h5>
                <div className="mt-2 grid grid-cols-2 gap-2 sm:grid-cols-4">
                  {checkpoints.map((checkpoint) => {
                    const stateLabel = checkpoint.state === 'observed'
                      ? (en ? 'Observed' : '已观察')
                      : checkpoint.state === 'pending'
                        ? (en ? 'Pending' : '待观察')
                        : (en ? 'Unavailable' : '暂无记录');
                    return (
                      <div key={checkpoint.days} className="border border-white/10 px-3 py-2">
                        <span className="text-xs font-semibold text-slate-200">
                          {en ? `${checkpoint.days}D` : `${checkpoint.days}日`}
                        </span>
                        <span className="mt-1 block text-xs text-slate-500">{stateLabel}</span>
                        {checkpoint.observation ? (
                          <strong className="mt-1 block text-sm text-slate-100">
                            {price(checkpoint.observation.price, language)}
                          </strong>
                        ) : null}
                      </div>
                    );
                  })}
                </div>
              </div>

              {laterEvents.length > 0 ? (
                <div className="mt-4 border-t border-white/10 pt-3">
                  <h5 className="text-sm font-semibold text-slate-200">
                    {en ? 'Later public events' : '后续公开事件'}
                  </h5>
                  <ul className="mt-2 grid gap-2">
                    {laterEvents.map((event) => (
                      <li key={event.eventId} className="flex flex-col gap-1 text-xs sm:flex-row sm:items-center sm:justify-between">
                        <span className="min-w-0 text-slate-300">{event.title}</span>
                        <span className="shrink-0 text-slate-500">
                          {formatMarketTimestamp(event.eventTime, language)}
                        </span>
                      </li>
                    ))}
                  </ul>
                </div>
              ) : null}
            </article>
          );
        })}
      </div>

      <div className="mt-4 border-t border-white/10 pt-3 text-xs leading-5 text-slate-500">
        <p>
          {en
            ? 'This record places public events and later market observations together; it does not mean the event caused the market change.'
            : '本记录仅并列展示公开事件与后续行情观察，不代表事件导致行情变化。'}
        </p>
        <p>
          {en
            ? 'Public information and data only. Not investment advice.'
            : '仅提供公开资讯和数据，不构成投资建议。'}
        </p>
      </div>
    </section>
  );
}
