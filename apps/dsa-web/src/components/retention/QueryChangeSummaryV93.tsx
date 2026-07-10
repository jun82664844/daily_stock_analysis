import type React from 'react';
import { ArrowRight, Clock3 } from 'lucide-react';
import type { QueryChangeSummary, QueryTrendPosition } from './queryChangeTracker';

type QueryChangeSummaryV93Props = {
  summary: QueryChangeSummary;
  language: string;
};

const signed = (value: number | null, suffix = ''): string => {
  if (value === null) return '-';
  const formatted = value.toLocaleString(undefined, { maximumFractionDigits: 2 });
  return `${value > 0 ? '+' : ''}${formatted}${suffix}`;
};

const trendLabel = (value: QueryTrendPosition, language: string): string => {
  const en = language === 'en';
  if (value === 'above_ma20') return en ? 'above MA20' : 'MA20 上方';
  if (value === 'below_ma20') return en ? 'below MA20' : 'MA20 下方';
  if (value === 'at_ma20') return en ? 'near MA20' : '贴近 MA20';
  return en ? 'unknown' : '未知';
};

const freshnessLabel = (value: string, language: string): string => {
  const en = language === 'en';
  if (value === 'fresh') return en ? 'fresh' : '新鲜';
  if (value === 'stale') return en ? 'stale' : '过期';
  if (value === 'cached') return en ? 'cached' : '缓存';
  return value || (en ? 'unknown' : '未知');
};

const observationTime = (value: string | undefined, language: string): string => {
  if (!value) return '-';
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return new Intl.DateTimeFormat(language === 'en' ? 'en-US' : 'zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  }).format(parsed);
};

export const QueryChangeSummaryV93: React.FC<QueryChangeSummaryV93Props> = ({ summary, language }) => {
  const en = language === 'en';
  const chips: string[] = [];
  if (summary.kind === 'changed') {
    if (summary.priceDelta !== null && Math.abs(summary.priceDelta) > 0.000001) {
      chips.push(`${en ? 'Price' : '价格'} ${signed(summary.priceDelta)}`);
    }
    if (summary.changePercentDelta !== null && Math.abs(summary.changePercentDelta) > 0.000001) {
      chips.push(`${en ? 'Daily move' : '日涨跌变化'} ${signed(summary.changePercentDelta, '%')}`);
    }
    if (summary.signalScoreDelta !== null && Math.abs(summary.signalScoreDelta) > 0.000001) {
      chips.push(`${en ? 'Signal score' : '信号评分'} ${signed(summary.signalScoreDelta)}`);
    }
    if (summary.trendPositionChanged && summary.previous) {
      chips.push(`${trendLabel(summary.previous.trendPosition, language)} → ${trendLabel(summary.current.trendPosition, language)}`);
    }
    if (summary.freshnessChanged && summary.previous) {
      chips.push(`${freshnessLabel(summary.previous.freshness, language)} → ${freshnessLabel(summary.current.freshness, language)}`);
    }
    if (summary.warningCountDelta !== 0) {
      chips.push(`${en ? 'Risk flags' : '风险提醒'} ${signed(summary.warningCountDelta)}`);
    }
    if (summary.volumeSignalChanged) {
      chips.push(en ? 'Volume signal changed' : '量价信号已变化');
    }
  }

  const title = summary.kind === 'unavailable'
    ? (en ? 'Browser comparison is unavailable' : '当前浏览器无法保存对比')
    : summary.kind === 'first'
      ? (en ? 'Comparison baseline created' : '已建立首次对比基线')
      : summary.kind === 'unchanged'
        ? (en ? 'No core change since the last query' : '相比上次查询，核心数据暂无变化')
        : (en ? 'What changed since the last query' : '相比上次查询发生了什么变化');

  return (
    <section
      data-testid="same-symbol-query-change"
      role="status"
      aria-live="polite"
      className="mb-4 border-y border-subtle bg-background/20 py-3"
    >
      <div className="flex min-w-0 flex-col gap-2 lg:flex-row lg:items-center lg:justify-between">
        <div className="min-w-0">
          <div className="flex items-center gap-2 text-sm font-semibold text-foreground">
            <Clock3 className="h-4 w-4 text-primary" aria-hidden="true" />
            {title}
          </div>
          <p className="mt-1 text-xs leading-relaxed text-secondary-text">
            {summary.kind === 'unavailable'
              ? (en ? 'Market data still works, but this browser blocks local comparison storage.' : '行情查询仍可使用，但当前浏览器禁止保存本地对比记录。')
              : summary.kind === 'first'
                ? (en ? 'Query this symbol again later to see price, trend, signal, and data-quality changes.' : '下次再查询同一标的时，这里会对比价格、趋势、信号和数据质量变化。')
                : `${en ? 'Previous observation' : '上次记录'} ${observationTime(summary.previous?.observedAt, language)}`}
          </p>
        </div>
        <div className="flex min-w-0 flex-wrap items-center gap-1.5 text-xs text-secondary-text">
          {chips.length > 0 ? chips.slice(0, 6).map((chip) => (
            <span key={chip} className="inline-flex max-w-full items-center gap-1 rounded-md border border-subtle px-2 py-1">
              <ArrowRight className="h-3 w-3 shrink-0 text-primary" aria-hidden="true" />
              <span className="truncate">{chip}</span>
            </span>
          )) : (
            <span className="rounded-md border border-subtle px-2 py-1">
              {summary.kind === 'unavailable'
                ? (en ? 'No AI used; browser storage unavailable' : '未用 AI；浏览器本地存储不可用')
                : (en ? 'No AI used; stored only in this browser' : '未用 AI；仅保存在当前浏览器')}
            </span>
          )}
        </div>
      </div>
    </section>
  );
};
