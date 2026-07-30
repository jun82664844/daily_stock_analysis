import { BarChart3, CalendarRange, Database } from 'lucide-react';
import type {
  PublicSymbolEventArchiveItem,
  PublicSymbolEventComparisonSummary,
  SymbolArchiveEventType,
} from '../../api/marketWorkspace';
import {
  formatMarketTimestamp,
  formatSourceStatus,
} from './marketWorkspaceFormat';

type Props = {
  language: 'zh' | 'en';
  events: PublicSymbolEventArchiveItem[];
  summaries: PublicSymbolEventComparisonSummary[];
  windowDays: 1 | 3 | 5 | 20;
  selectedEventId: string;
  onSelectEvent: (eventId: string) => void;
};

const EVENT_LABELS: Record<SymbolArchiveEventType, { zh: string; en: string }> = {
  earnings: { zh: '财报披露', en: 'Earnings' },
  dividend: { zh: '分红除息', en: 'Dividends' },
  split: { zh: '拆股', en: 'Splits' },
  buyback: { zh: '股份回购', en: 'Buybacks' },
  announcement: { zh: '重要公告', en: 'Announcements' },
};

const percent = (value?: number | null): string => {
  if (value == null || !Number.isFinite(value)) return '—';
  return `${value > 0 ? '+' : ''}${value.toFixed(2)}%`;
};

export default function SymbolEventComparisonV141({
  language,
  events,
  summaries,
  windowDays,
  selectedEventId,
  onSelectEvent,
}: Props) {
  const en = language === 'en';
  const activeEvent = (
    events.find((item) => item.eventId === selectedEventId)
    ?? events[0]
    ?? null
  );
  const activeType = activeEvent?.eventType ?? summaries[0]?.eventType ?? null;
  const summary = summaries.find((item) => item.eventType === activeType) ?? null;
  const windowSummary = summary?.windows.find(
    (item) => item.tradingDays === windowDays,
  ) ?? null;
  const sameTypeEvents = activeType
    ? events.filter((item) => item.eventType === activeType).slice(0, 12)
    : [];
  const limitedSample = (
    windowSummary != null
    && windowSummary.sampleSize > 0
    && windowSummary.sampleSize < 3
  );

  return (
    <section
      className="mt-5 border-t border-primary/30 pt-5"
      data-testid="symbol-event-comparison-v141"
      aria-label={en ? 'Same-type event comparison' : '同类事件历史对比'}
    >
      <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
        <div>
          <span className="text-xs font-medium uppercase text-primary">
            DSA V141 · No AI
          </span>
          <h4 className="mt-1 flex items-center gap-2 text-lg font-semibold text-foreground">
            <BarChart3 className="h-5 w-5" />
            {en ? 'Same-type event comparison' : '同类事件历史对比'}
          </h4>
        </div>
        {summary ? (
          <div className="flex flex-wrap gap-2 text-xs">
            <span className="rounded-full border border-border px-3 py-1 text-foreground">
              {EVENT_LABELS[summary.eventType][language]}
            </span>
            <span className="rounded-full border border-border px-3 py-1 text-secondary-text">
              {en ? `${summary.eventCount} events` : `${summary.eventCount}次事件`}
            </span>
            <span className="rounded-full border border-border px-3 py-1 text-secondary-text">
              {en
                ? `Observed events ${summary.observedEventCount}/${summary.eventCount}`
                : `有效事件 ${summary.observedEventCount}/${summary.eventCount}`}
            </span>
          </div>
        ) : null}
      </div>

      {!summary || !windowSummary || windowSummary.sampleSize === 0 ? (
        <p className="mt-4 border-y border-border py-5 text-sm text-secondary-text">
          {en
            ? 'No historical observations are available for this window.'
            : '当前窗口暂无可用历史样本。'}
        </p>
      ) : (
        <>
          <div className="mt-4 flex flex-wrap items-center gap-2 text-xs text-secondary-text">
            <span>
              {en
                ? `${windowDays} ${windowDays === 1 ? 'session' : 'sessions'} after event`
                : `事件后${windowDays}个交易日`}
            </span>
            <span>·</span>
            <span>
              {en
                ? `Samples ${windowSummary.sampleSize}/${summary.eventCount}`
                : `样本 ${windowSummary.sampleSize}/${summary.eventCount}`}
            </span>
            {limitedSample ? (
              <span className="rounded-full border border-amber-500/50 px-2 py-0.5 text-amber-300">
                {en ? 'Limited sample' : '样本有限'}
              </span>
            ) : null}
          </div>
          <dl className="mt-3 grid border-y border-border sm:grid-cols-2 lg:grid-cols-5 lg:divide-x lg:divide-border">
            <div className="px-3 py-4">
              <dt className="text-xs text-secondary-text">{en ? 'Median stock change' : '个股变化中位数'}</dt>
              <dd className="mt-1 text-lg font-semibold text-foreground">{percent(windowSummary.symbolMedianReturnPercent)}</dd>
            </div>
            <div className="px-3 py-4">
              <dt className="text-xs text-secondary-text">{en ? 'Observed range' : '历史区间'}</dt>
              <dd className="mt-1 text-sm font-medium text-foreground">
                {percent(windowSummary.symbolMinReturnPercent)}
                {' '}
                {en ? 'to' : '至'}
                {' '}
                {percent(windowSummary.symbolMaxReturnPercent)}
              </dd>
            </div>
            <div className="px-3 py-4">
              <dt className="text-xs text-secondary-text">{en ? 'Positive / negative / flat' : '正负样本'}</dt>
              <dd className="mt-1 text-sm font-medium text-foreground">
                {en
                  ? `${windowSummary.positiveCount} positive / ${windowSummary.negativeCount} negative / ${windowSummary.flatCount} flat`
                  : `正 ${windowSummary.positiveCount} / 负 ${windowSummary.negativeCount} / 平 ${windowSummary.flatCount}`}
              </dd>
            </div>
            <div className="px-3 py-4">
              <dt className="text-xs text-secondary-text">{en ? 'Median relative change' : '相对基准中位数'}</dt>
              <dd className="mt-1 text-lg font-semibold text-foreground">{percent(windowSummary.relativeMedianReturnPercent)}</dd>
              <span className="mt-1 block text-xs text-secondary-text">
                {en
                  ? `${windowSummary.relativeSampleSize} relative samples`
                  : `相对样本 ${windowSummary.relativeSampleSize}`}
              </span>
            </div>
            <div className="px-3 py-4">
              <dt className="text-xs text-secondary-text">{en ? 'Data completeness' : '数据完整度'}</dt>
              <dd className="mt-1 text-lg font-semibold text-foreground">
                {Math.round(windowSummary.completenessPercent)}%
              </dd>
              <span className="mt-1 block text-xs text-secondary-text">
                {en
                  ? `${windowSummary.benchmarkSampleSize} benchmark samples`
                  : `基准样本 ${windowSummary.benchmarkSampleSize}`}
              </span>
            </div>
          </dl>
        </>
      )}

      <div className="mt-4">
        <p className="flex items-center gap-2 text-sm font-medium text-foreground">
          <CalendarRange className="h-4 w-4" />
          {en ? 'Historical samples' : '历史样本'}
        </p>
        <div className="mt-2 flex max-h-32 flex-wrap gap-2 overflow-y-auto">
          {sameTypeEvents.length ? sameTypeEvents.map((item) => {
            const observation = item.windows.find(
              (window) => window.tradingDays === windowDays,
            );
            const label = EVENT_LABELS[item.eventType][language];
            const date = formatMarketTimestamp(item.eventTime, language);
            const active = item.eventId === activeEvent?.eventId;
            return (
              <button
                type="button"
                key={item.eventId}
                className={active ? 'btn-primary' : 'btn-secondary'}
                aria-pressed={active}
                aria-label={`${date} ${label}`}
                onClick={() => onSelectEvent(item.eventId)}
              >
                <span>{date} · {label}</span>
                <span className="ml-2 opacity-80">
                  {observation?.status === 'available'
                    ? percent(observation.symbolReturnPercent)
                    : '—'}
                </span>
              </button>
            );
          }) : (
            <span className="text-sm text-secondary-text">
              {en ? 'No same-type events are available.' : '暂无同类事件。'}
            </span>
          )}
        </div>
      </div>

      <div className="mt-4 flex items-start gap-2 border-t border-border pt-3 text-xs text-secondary-text">
        <Database className="mt-0.5 h-3.5 w-3.5 shrink-0" />
        <span>
          {activeEvent
            ? `${en ? 'Event source: ' : '事件来源：'}${formatSourceStatus(activeEvent.eventSourceState.status, language)}. `
            : ''}
          {en
            ? 'This historical distribution does not predict future performance or establish causality. Information and historical data only. Not investment advice.'
            : '历史分布不代表未来表现，相关变化不表示因果关系。本功能只提供资讯和历史数据，不构成投资建议。'}
        </span>
      </div>
    </section>
  );
}
