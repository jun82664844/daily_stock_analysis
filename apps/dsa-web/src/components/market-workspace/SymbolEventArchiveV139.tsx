import { CalendarDays, ExternalLink, RefreshCw } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import {
  marketWorkspaceApi,
  type PublicSymbolEventArchiveItem,
  type PublicSymbolEventArchiveResponse,
  type SymbolArchiveEventType,
} from '../../api/marketWorkspace';
import {
  formatMarketTimestamp,
  formatSourceLabel,
  formatSourceStatus,
} from './marketWorkspaceFormat';
import SymbolEventComparisonV141 from './SymbolEventComparisonV141';
import SymbolEventTimelineV140 from './SymbolEventTimelineV140';

type Props = {
  language: 'zh' | 'en';
  symbol: string;
};

type Months = 6 | 12 | 24;
type WindowDays = 1 | 3 | 5 | 20;
type EventFilter = 'all' | SymbolArchiveEventType;
type ArchiveRequestState = {
  key: string;
  data: PublicSymbolEventArchiveResponse | null;
  error: boolean;
};

const MONTHS: Months[] = [6, 12, 24];
const WINDOWS: WindowDays[] = [1, 3, 5, 20];
const EVENT_FILTERS: EventFilter[] = [
  'all',
  'earnings',
  'dividend',
  'split',
  'buyback',
  'announcement',
];

const EVENT_LABELS: Record<EventFilter, { zh: string; en: string }> = {
  all: { zh: '全部事件', en: 'All events' },
  earnings: { zh: '财报披露', en: 'Earnings' },
  dividend: { zh: '分红除息', en: 'Dividends' },
  split: { zh: '拆股', en: 'Splits' },
  buyback: { zh: '股份回购', en: 'Buybacks' },
  announcement: { zh: '重要公告', en: 'Announcements' },
};

const eventTitle = (
  item: PublicSymbolEventArchiveItem,
  language: 'zh' | 'en',
): string => {
  if (language === 'en') return item.title;
  return `${item.name}（${item.symbol}）${EVENT_LABELS[item.eventType].zh}`;
};

const eventDescription = (
  item: PublicSymbolEventArchiveItem,
  language: 'zh' | 'en',
): string => {
  if (language === 'en') {
    return item.summary || 'Event recorded by the identified public source.';
  }
  const descriptions: Record<SymbolArchiveEventType, string> = {
    earnings: '公开来源记录的定期报告或业绩披露日期。',
    dividend: '公开来源记录的分红或除息事件日期。',
    split: '公开来源记录的拆股事件日期。',
    buyback: '公开来源记录的股份回购事件日期。',
    announcement: '公开来源记录的重要公告日期。',
  };
  return descriptions[item.eventType];
};

const percent = (value?: number | null): string => {
  if (value == null || !Number.isFinite(value)) return '—';
  return `${value > 0 ? '+' : ''}${value.toFixed(2)}%`;
};

export default function SymbolEventArchiveV139({ language, symbol }: Props) {
  const en = language === 'en';
  const [months, setMonths] = useState<Months>(12);
  const [windowDays, setWindowDays] = useState<WindowDays>(1);
  const [eventFilter, setEventFilter] = useState<EventFilter>('all');
  const [selectedEventId, setSelectedEventId] = useState('');
  const requestKey = `${symbol}:${months}`;
  const [requestState, setRequestState] = useState<ArchiveRequestState>({
    key: '',
    data: null,
    error: false,
  });
  const loading = requestState.key !== requestKey;
  const data = loading ? null : requestState.data;
  const error = !loading && requestState.error;

  useEffect(() => {
    let active = true;
    marketWorkspaceApi.getSymbolEventArchive(symbol, months)
      .then((payload) => {
        if (active) {
          setRequestState({ key: requestKey, data: payload, error: false });
        }
      })
      .catch(() => {
        if (active) {
          setRequestState({ key: requestKey, data: null, error: true });
        }
      });
    return () => { active = false; };
  }, [months, requestKey, symbol]);

  const filtered = useMemo(
    () => (data?.items ?? []).filter(
      (item) => eventFilter === 'all' || item.eventType === eventFilter,
    ),
    [data?.items, eventFilter],
  );
  const effectiveSelectedEventId = (
    filtered.some((item) => item.eventId === selectedEventId)
      ? selectedEventId
      : filtered[0]?.eventId ?? ''
  );

  return (
    <section
      className="border-b border-primary/30 bg-primary/5 px-4 py-6"
      data-testid="symbol-event-archive-v139"
      aria-label={en ? 'Symbol event archive' : '个股事件档案'}
    >
      <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <span className="text-xs font-medium uppercase text-primary">DSA V139 · No AI</span>
          <h3 className="mt-1 flex items-center gap-2 text-xl font-semibold text-foreground">
            <CalendarDays className="h-5 w-5" />
            {en ? 'Symbol event archive' : '个股事件档案'}
          </h3>
          <p className="mt-2 max-w-3xl text-sm text-secondary-text">
            {en
              ? 'Traceable public events with objective 1/3/5/20-session price observations.'
              : '汇集可追溯的公开事件，并展示事件后 1/3/5/20 个交易日的客观行情观察。'}
          </p>
        </div>
        <div className="flex flex-wrap gap-2" role="group" aria-label={en ? 'Archive range' : '档案时间范围'}>
          {MONTHS.map((value) => (
            <button
              type="button"
              key={value}
              className={months === value ? 'btn-primary' : 'btn-secondary'}
              aria-pressed={months === value}
              onClick={() => setMonths(value)}
            >
              {en ? `${value} months` : `${value}个月`}
            </button>
          ))}
        </div>
      </div>

      <div className="mt-5 flex flex-col gap-3 border-y border-border/70 py-4">
        <div className="flex flex-wrap gap-2" role="group" aria-label={en ? 'Event type' : '事件类型'}>
          {EVENT_FILTERS.map((value) => (
            <button
              type="button"
              key={value}
              className={eventFilter === value ? 'btn-primary' : 'btn-secondary'}
              aria-pressed={eventFilter === value}
              onClick={() => setEventFilter(value)}
            >
              {EVENT_LABELS[value][language]}
            </button>
          ))}
        </div>
        <div className="flex flex-wrap items-center gap-2" role="group" aria-label={en ? 'Observation window' : '行情观察窗口'}>
          <span className="mr-1 text-sm text-secondary-text">{en ? 'Observation:' : '观察窗口：'}</span>
          {WINDOWS.map((value) => (
            <button
              type="button"
              key={value}
              className={windowDays === value ? 'btn-primary' : 'btn-secondary'}
              aria-pressed={windowDays === value}
              onClick={() => setWindowDays(value)}
            >
              {en ? `${value} sessions` : `${value}个交易日`}
            </button>
          ))}
        </div>
      </div>

      {loading ? (
        <p className="flex items-center justify-center gap-2 py-10 text-sm text-secondary-text">
          <RefreshCw className="h-4 w-4 animate-spin" />
          {en ? 'Loading public event records...' : '正在加载公开事件记录...'}
        </p>
      ) : error ? (
        <p className="py-8 text-sm text-amber-300">
          {en
            ? 'The public event archive is temporarily unavailable. The quote workspace remains usable.'
            : '公开事件档案暂不可用，个股行情工作区仍可继续使用。'}
        </p>
      ) : (
        <>
          {data ? (
            <SymbolEventTimelineV140
              language={language}
              chart={data.chart}
              events={filtered}
              windowDays={windowDays}
              selectedEventId={effectiveSelectedEventId}
              onSelectEvent={setSelectedEventId}
            />
          ) : null}
          {data ? (
            <SymbolEventComparisonV141
              language={language}
              events={filtered}
              summaries={data.comparisonSummaries}
              windowDays={windowDays}
              selectedEventId={effectiveSelectedEventId}
              onSelectEvent={setSelectedEventId}
            />
          ) : null}
          {filtered.length ? (
            <div className="mt-5 grid gap-3 lg:grid-cols-2">
          {filtered.map((item) => {
            const observation = item.windows.find(
              (window) => window.tradingDays === windowDays,
            );
            const observationAvailable = observation?.status === 'available';
            return (
              <article
                key={item.eventId}
                className="min-w-0 rounded-lg border border-border bg-background/35 p-4"
              >
                <div className="flex flex-wrap items-start justify-between gap-2">
                  <div className="min-w-0">
                    <span className="text-xs text-primary">{EVENT_LABELS[item.eventType][language]}</span>
                    <h4 className="mt-1 break-words font-semibold text-foreground">
                      {eventTitle(item, language)}
                    </h4>
                  </div>
                  <span className="rounded-full border border-border px-2 py-1 text-xs text-secondary-text">
                    {formatSourceStatus(item.eventSourceState.status, language)}
                  </span>
                </div>
                <p className="mt-2 text-sm text-secondary-text">{eventDescription(item, language)}</p>
                <dl className="mt-4 grid grid-cols-2 gap-x-4 gap-y-3 text-sm sm:grid-cols-4">
                  <div><dt className="text-secondary-text">{en ? 'Event date' : '事件日期'}</dt><dd className="mt-1 text-foreground">{formatMarketTimestamp(item.eventTime, language)}</dd></div>
                  <div><dt className="text-secondary-text">{en ? 'Stock change' : '个股变化'}</dt><dd className="mt-1 text-foreground">{observationAvailable ? percent(observation?.symbolReturnPercent) : '—'}</dd></div>
                  <div><dt className="text-secondary-text">{en ? 'Benchmark' : '市场基准'}</dt><dd className="mt-1 text-foreground">{observationAvailable ? percent(observation?.benchmarkReturnPercent) : '—'}</dd></div>
                  <div><dt className="text-secondary-text">{en ? 'Relative change' : '相对变化'}</dt><dd className="mt-1 text-foreground">{observationAvailable ? percent(observation?.relativeReturnPercent) : '—'}</dd></div>
                </dl>
                {!observationAvailable ? (
                  <p className="mt-3 text-xs text-secondary-text">
                    {observation?.status === 'pending'
                      ? (en ? 'Awaiting enough trading sessions.' : '尚待足够交易日形成观察数据。')
                      : (en ? 'Price observation is unavailable for this window.' : '该窗口的行情观察数据不可用。')}
                  </p>
                ) : null}
                <div className="mt-4 flex flex-wrap items-center gap-3 border-t border-border/70 pt-3 text-xs text-secondary-text">
                  <span>{en ? 'Event source:' : '事件来源：'}{item.publisher}</span>
                  <span>{en ? 'Price source:' : '行情来源：'}{formatSourceLabel(item.sourceState.source, language)}</span>
                  {item.sourceUrl ? (
                    <a
                      href={item.sourceUrl}
                      target="_blank"
                      rel="noreferrer"
                      className="inline-flex items-center gap-1 text-primary hover:underline"
                    >
                      {en ? 'Open source' : '查看来源'}
                      <ExternalLink className="h-3.5 w-3.5" />
                    </a>
                  ) : null}
                </div>
              </article>
            );
          })}
            </div>
          ) : (
            <p className="py-8 text-sm text-secondary-text">
              {en
                ? 'No matching public events are available for this symbol and range.'
                : '当前证券在所选时间和类型下暂无可用公开事件。'}
            </p>
          )}
        </>
      )}

      <p className="mt-5 border-t border-border/70 pt-4 text-sm text-secondary-text">
        {en
          ? 'Same-period changes do not establish that an event caused a price move. Information and data only. Not investment advice.'
          : '同期变化不代表事件导致价格变化。本功能只提供资讯和客观数据，不构成投资建议。'}
      </p>
    </section>
  );
}
