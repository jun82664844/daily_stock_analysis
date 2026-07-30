import { Activity, Database, MousePointerClick } from 'lucide-react';
import { useMemo, useState } from 'react';
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ReferenceArea,
  ReferenceLine,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import type {
  PublicSymbolEventArchiveItem,
  PublicSymbolEventChart,
  SymbolArchiveEventType,
} from '../../api/marketWorkspace';
import {
  formatMarketTimestamp,
  formatSourceLabel,
  formatSourceStatus,
} from './marketWorkspaceFormat';

type Props = {
  language: 'zh' | 'en';
  chart: PublicSymbolEventChart;
  events: PublicSymbolEventArchiveItem[];
  windowDays: 1 | 3 | 5 | 20;
  selectedEventId?: string;
  onSelectEvent?: (eventId: string) => void;
};

const EVENT_LABELS: Record<SymbolArchiveEventType, { zh: string; en: string }> = {
  earnings: { zh: '财报披露', en: 'Earnings' },
  dividend: { zh: '分红除息', en: 'Dividend' },
  split: { zh: '拆股', en: 'Split' },
  buyback: { zh: '股份回购', en: 'Buyback' },
  announcement: { zh: '重要公告', en: 'Announcement' },
};

const percent = (value?: number | null): string => {
  if (value == null || !Number.isFinite(value)) return '—';
  return `${value > 0 ? '+' : ''}${value.toFixed(2)}%`;
};

const containsCjk = (value: string): boolean => /[\u3400-\u9fff]/.test(value);

const benchmarkLabel = (
  symbol: string,
  fallback: string,
  language: 'zh' | 'en',
): string => {
  const labels: Record<string, { zh: string; en: string }> = {
    '000001.SS': { zh: '上证指数', en: 'SSE Composite Index' },
    '^HSI': { zh: '恒生指数', en: 'Hang Seng Index' },
    '^GSPC': { zh: '标普500指数', en: 'S&P 500 Index' },
  };
  return labels[symbol]?.[language] ?? fallback;
};

export default function SymbolEventTimelineV140({
  language,
  chart,
  events,
  windowDays,
  selectedEventId,
  onSelectEvent,
}: Props) {
  const en = language === 'en';
  const [localSelectedEventId, setLocalSelectedEventId] = useState<string>('');
  const effectiveSelectedEventId = selectedEventId ?? localSelectedEventId;
  const activeEvent = useMemo(
    () => (
      events.find((item) => item.eventId === effectiveSelectedEventId)
      ?? events[0]
      ?? null
    ),
    [effectiveSelectedEventId, events],
  );
  const activeObservation = activeEvent?.windows.find(
    (window) => window.tradingDays === windowDays,
  );
  const eventSymbolName = events[0]?.name || '';
  const symbolName = (
    en && containsCjk(eventSymbolName)
      ? chart.historySymbol
      : eventSymbolName || chart.historySymbol
  );
  const marketBenchmark = benchmarkLabel(
    chart.benchmarkSymbol,
    chart.benchmarkName,
    language,
  );
  const benchmarkAvailable = chart.points.some(
    (point) => point.benchmarkChangePercent != null,
  );
  const activeStart = activeEvent?.baselineDate ?? undefined;
  const activeEnd = (
    activeObservation?.status === 'available'
      ? activeObservation.observedDate ?? undefined
      : undefined
  );

  if (chart.status === 'unavailable' || !chart.points.length) {
    return (
      <section
        className="mt-5 rounded-lg border border-border bg-background/30 p-4"
        aria-label={en ? 'Event and price timeline' : '事件与K线联动图'}
      >
        <h4 className="flex items-center gap-2 font-semibold text-foreground">
          <Activity className="h-4 w-4" />
          {en ? 'Event and price timeline' : '事件与K线联动图'}
        </h4>
        <p className="mt-3 text-sm text-secondary-text">
          {en
            ? 'Historical prices are temporarily unavailable. The event archive remains available.'
            : '历史行情暂不可用，事件档案仍可继续查看。'}
        </p>
      </section>
    );
  }

  return (
    <section
      className="mt-5 rounded-lg border border-primary/30 bg-background/30 p-4"
      aria-label={en ? 'Event and price timeline' : '事件与K线联动图'}
      data-testid="symbol-event-timeline-v140"
    >
      <div className="flex flex-col gap-2 md:flex-row md:items-start md:justify-between">
        <div>
          <span className="text-xs font-medium uppercase text-primary">DSA V140 · No AI</span>
          <h4 className="mt-1 flex items-center gap-2 text-lg font-semibold text-foreground">
            <Activity className="h-5 w-5" />
            {en ? 'Event and price timeline' : '事件与K线联动图'}
          </h4>
          <p className="mt-1 text-sm text-secondary-text">
            {en
              ? 'Normalized performance (range start = 0)'
              : '相对走势（区间起点=0）'}
          </p>
        </div>
        <div className="flex flex-wrap gap-2 text-xs text-secondary-text">
          <span className="rounded-full border border-border px-2 py-1">
            {symbolName}
          </span>
          <span className="rounded-full border border-border px-2 py-1">
            {marketBenchmark}
          </span>
        </div>
      </div>

      {!benchmarkAvailable ? (
        <p className="mt-4 rounded-lg border border-amber-400/30 bg-amber-400/5 px-3 py-2 text-sm text-amber-200">
          {en
            ? 'Benchmark history is unavailable. The symbol series remains visible.'
            : '市场基准历史暂不可用，个股曲线仍可查看。'}
        </p>
      ) : null}

      <div
        className="mt-4 h-72 min-h-0 min-w-0 w-full"
        aria-label={en ? 'Normalized event price chart' : '标准化事件行情图'}
      >
        <LineChart responsive data={chart.points} style={{ width: '100%', height: '100%' }}>
          <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
          <XAxis
            dataKey="date"
            minTickGap={32}
            tickFormatter={(value) => String(value).slice(5)}
            stroke="hsl(var(--secondary-text))"
          />
          <YAxis
            width={52}
            tickFormatter={(value) => `${Number(value).toFixed(0)}%`}
            stroke="hsl(var(--secondary-text))"
          />
          <Tooltip
            labelFormatter={(value) => String(value)}
            formatter={(value, name) => [
              percent(typeof value === 'number' ? value : Number(value)),
              String(name),
            ]}
            contentStyle={{
              background: 'hsl(var(--background))',
              border: '1px solid hsl(var(--border))',
              borderRadius: 8,
            }}
          />
          <Legend />
          {activeStart && activeEnd ? (
            <ReferenceArea
              x1={activeStart}
              x2={activeEnd}
              fill="hsl(var(--primary))"
              fillOpacity={0.08}
              strokeOpacity={0}
            />
          ) : null}
          {events.map((item) => (
            item.baselineDate ? (
              <ReferenceLine
                key={item.eventId}
                x={item.baselineDate}
                stroke="hsl(var(--warning))"
                strokeDasharray="4 4"
              />
            ) : null
          ))}
          <Line
            type="monotone"
            dataKey="symbolChangePercent"
            name={symbolName}
            stroke="hsl(var(--primary))"
            strokeWidth={2}
            dot={false}
            connectNulls={false}
          />
          {benchmarkAvailable ? (
            <Line
              type="monotone"
              dataKey="benchmarkChangePercent"
              name={marketBenchmark}
              stroke="hsl(var(--success))"
              strokeWidth={2}
              dot={false}
              connectNulls={false}
            />
          ) : null}
        </LineChart>
      </div>

      <div className="mt-4 border-t border-border/70 pt-4">
        <p className="flex items-center gap-2 text-sm font-medium text-foreground">
          <MousePointerClick className="h-4 w-4" />
          {en ? 'Select an event' : '选择事件'}
        </p>
        <div className="mt-2 flex max-h-28 flex-wrap gap-2 overflow-y-auto">
          {events.length ? events.map((item) => {
            const label = EVENT_LABELS[item.eventType][language];
            const dateLabel = formatMarketTimestamp(item.eventTime, language);
            const active = item.eventId === activeEvent?.eventId;
            return (
              <button
                type="button"
                key={item.eventId}
                className={active ? 'btn-primary' : 'btn-secondary'}
                aria-pressed={active}
                aria-label={`${dateLabel} ${label}`}
                onClick={() => {
                  if (onSelectEvent) {
                    onSelectEvent(item.eventId);
                  } else {
                    setLocalSelectedEventId(item.eventId);
                  }
                }}
              >
                {dateLabel} · {label}
              </button>
            );
          }) : (
            <span className="text-sm text-secondary-text">
              {en ? 'No events in the selected filter.' : '当前筛选下暂无事件。'}
            </span>
          )}
        </div>
      </div>

      {activeEvent ? (
        <div className="mt-4 rounded-lg border border-border bg-background/35 p-3">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <strong className="text-sm text-foreground">
              {en
                ? `${windowDays} ${windowDays === 1 ? 'session' : 'sessions'} after event`
                : `事件后${windowDays}个交易日`}
            </strong>
            <span className="text-xs text-secondary-text">
              {EVENT_LABELS[activeEvent.eventType][language]}
            </span>
          </div>
          {activeObservation?.status === 'available' ? (
            <dl className="mt-3 grid gap-3 text-sm sm:grid-cols-3">
              <div><dt className="text-secondary-text">{en ? 'Stock change' : '个股变化'}</dt><dd className="mt-1 font-medium text-foreground">{percent(activeObservation.symbolReturnPercent)}</dd></div>
              <div><dt className="text-secondary-text">{en ? 'Benchmark' : '市场基准'}</dt><dd className="mt-1 font-medium text-foreground">{percent(activeObservation.benchmarkReturnPercent)}</dd></div>
              <div><dt className="text-secondary-text">{en ? 'Relative change' : '相对变化'}</dt><dd className="mt-1 font-medium text-foreground">{percent(activeObservation.relativeReturnPercent)}</dd></div>
            </dl>
          ) : (
            <p className="mt-3 text-sm text-secondary-text">
              {en
                ? 'No price observation is available for this event and window.'
                : '该事件暂无可用的行情观察窗口。'}
            </p>
          )}
        </div>
      ) : null}

      <div className="mt-4 flex flex-wrap items-center gap-3 border-t border-border/70 pt-3 text-xs text-secondary-text">
        <span className="inline-flex items-center gap-1">
          <Database className="h-3.5 w-3.5" />
          {formatSourceLabel(chart.sourceState.source, language)}
          {' · '}
          {formatSourceStatus(chart.sourceState.status, language)}
        </span>
        <span>
          {en ? 'Benchmark source: ' : '基准来源：'}
          {formatSourceStatus(chart.benchmarkSourceState.status, language)}
        </span>
      </div>
      <p className="mt-3 text-sm text-secondary-text">
        {en
          ? 'Showing an event and a price curve together does not establish that an event caused the price move. Information and historical data only. Not investment advice.'
          : '事件与价格曲线同图展示不代表事件导致价格变化。本功能只提供资讯和历史数据，不构成投资建议。'}
      </p>
    </section>
  );
}
