import { BellPlus, BookmarkPlus, ExternalLink, GitCompareArrows } from 'lucide-react';

import type { AlphaSiftCandidate } from '../../api/alphasift';
import {
  conditionExitLabel,
  dataCompletenessLabel,
  dataFreshnessLabel,
  informationFlagLabel,
  formatScreeningMetric,
  metricLabel,
  observationLabel,
  type ScreeningLanguage,
} from './screeningModelV104';

export type ScreeningWatchlistState = 'idle' | 'saving' | 'saved' | 'login-required' | 'error';

type Props = {
  candidate: AlphaSiftCandidate;
  language: ScreeningLanguage;
  selected: boolean;
  compareDisabled: boolean;
  watchlistState: ScreeningWatchlistState;
  onToggleCompare: (code: string) => void;
  onAddWatchlist: (code: string) => void;
  onOpenData: (code: string) => void;
  onOpenReminder: (code: string) => void;
};

export default function MarketScreeningCardV104({
  candidate,
  language,
  selected,
  compareDisabled,
  watchlistState,
  onToggleCompare,
  onAddWatchlist,
  onOpenData,
  onOpenReminder,
}: Props) {
  const en = language === 'en';
  const brief = candidate.screeningBrief;
  const metrics = brief?.observedMetrics.slice(0, 6) ?? [];
  const watchlistLabel = {
    idle: en ? 'Add to watchlist' : '加入自选',
    saving: en ? 'Saving' : '保存中',
    saved: en ? 'Saved' : '已保存',
    'login-required': en ? 'Login required' : '需要登录',
    error: en ? 'Try again' : '重试保存',
  }[watchlistState];

  return (
    <article
      data-testid={`market-screening-card-${candidate.code}`}
      className="min-w-0 rounded-lg border border-border bg-card p-4 shadow-soft-card"
    >
      <div className="flex min-w-0 items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <strong className="font-mono text-base text-foreground">{candidate.code}</strong>
            <span className="truncate text-sm text-secondary-text">{candidate.name || '-'}</span>
          </div>
          <p className="mt-1 text-xs text-secondary-text">
            {candidate.industry || (en ? 'Industry unavailable' : '行业数据缺失')}
          </p>
        </div>
        <span className="shrink-0 rounded-lg border border-border bg-surface px-2 py-1 text-xs text-secondary-text">
          {brief ? dataFreshnessLabel(brief.dataFreshness, language) : en ? 'Data unavailable' : '数据不可用'}
        </span>
      </div>

      <div className="mt-4 grid gap-2 sm:grid-cols-2 xl:grid-cols-3">
        {metrics.length ? (
          metrics.map((metric) => (
            <div key={metric.code} className="min-w-0 rounded-lg border border-border bg-surface px-3 py-2">
              <span className="block truncate text-xs text-secondary-text">{metricLabel(metric.code, language)}</span>
              <strong className="mt-1 block text-sm text-foreground">{formatScreeningMetric(metric.code, metric.value, language)}</strong>
              <span className="mt-1 block truncate text-[11px] text-secondary-text">{metric.source || '-'}</span>
            </div>
          ))
        ) : (
          <div className="rounded-lg border border-border bg-surface px-3 py-2 text-sm text-secondary-text">
            {en ? 'No observable metrics' : '暂无可用观测指标'}
          </div>
        )}
      </div>

      <div className="mt-4 grid gap-3 sm:grid-cols-2">
        <section>
          <h3 className="text-xs font-semibold text-secondary-text">{en ? 'Filter match details' : '条件匹配说明'}</h3>
          <div className="mt-2 flex flex-wrap gap-2">
            {(brief?.matchedConditionCodes ?? []).map((code) => (
              <span key={code} className="rounded-lg border border-primary/30 bg-primary/10 px-2 py-1 text-xs text-cyan">
                {metricLabel(code, language)}
              </span>
            ))}
            {!brief?.matchedConditionCodes.length ? <span className="text-sm text-secondary-text">-</span> : null}
          </div>
        </section>
        <section>
          <h3 className="text-xs font-semibold text-secondary-text">{en ? 'Data coverage' : '数据覆盖'}</h3>
          <p className="mt-2 text-sm text-foreground">
            {brief ? `${dataCompletenessLabel(brief.dataCompleteness, language)} · ${brief.dataCompleteness}/100` : '-'}
          </p>
          <p className="mt-1 text-xs text-secondary-text">
            {brief?.aiUsed ? (en ? 'AI summary source marked' : '已标记 AI 摘要来源') : en ? 'No AI used' : '未使用 AI'}
          </p>
        </section>
        <section>
          <h3 className="text-xs font-semibold text-secondary-text">{en ? 'Information notes' : '信息提示'}</h3>
          <ul className="mt-2 space-y-1 text-sm text-foreground">
            {(brief?.informationFlags ?? []).map((code) => <li key={code}>{informationFlagLabel(code, language)}</li>)}
            {!brief?.informationFlags.length ? <li>{en ? 'No additional notes' : '暂无附加提示'}</li> : null}
          </ul>
        </section>
        <section>
          <h3 className="text-xs font-semibold text-secondary-text">{en ? 'Further data observations' : '后续数据观察项'}</h3>
          <ul className="mt-2 space-y-1 text-sm text-foreground">
            {(brief?.observationCodes ?? []).map((code) => <li key={code}>{observationLabel(code, language)}</li>)}
          </ul>
        </section>
      </div>

      <section className="mt-3 rounded-lg border border-border bg-surface px-3 py-2">
        <h3 className="text-xs font-semibold text-secondary-text">
          {en ? 'When the filter condition no longer matches' : '筛选条件不再满足的情形'}
        </h3>
        <ul className="mt-1 space-y-1 text-sm text-foreground">
          {(brief?.conditionExitCodes ?? []).map((code) => <li key={code}>{conditionExitLabel(code, language)}</li>)}
        </ul>
      </section>

      <div className="mt-4 grid grid-cols-2 gap-2 sm:grid-cols-4">
        <button
          data-testid={`screening-compare-${candidate.code}`}
          className="inline-flex min-h-10 items-center justify-center gap-2 rounded-lg border border-border px-3 text-sm text-foreground disabled:cursor-not-allowed disabled:opacity-45"
          type="button"
          disabled={compareDisabled && !selected}
          onClick={() => onToggleCompare(candidate.code)}
        >
          <GitCompareArrows className="h-4 w-4" />
          {selected ? (en ? 'Remove' : '移出比较') : en ? 'Compare' : '加入比较'}
        </button>
        <button
          data-testid={`screening-watchlist-${candidate.code}`}
          className="inline-flex min-h-10 items-center justify-center gap-2 rounded-lg border border-border px-3 text-sm text-foreground disabled:cursor-not-allowed disabled:opacity-45"
          type="button"
          disabled={watchlistState === 'saving' || watchlistState === 'saved'}
          onClick={() => onAddWatchlist(candidate.code)}
        >
          <BookmarkPlus className="h-4 w-4" />
          {watchlistLabel}
        </button>
        <button
          data-testid={`screening-reminder-${candidate.code}`}
          className="inline-flex min-h-10 items-center justify-center gap-2 rounded-lg border border-border px-3 text-sm text-foreground"
          type="button"
          onClick={() => onOpenReminder(candidate.code)}
        >
          <BellPlus className="h-4 w-4" />
          {en ? 'Set alert' : '设置提醒'}
        </button>
        <button
          data-testid={`screening-open-data-${candidate.code}`}
          className="inline-flex min-h-10 items-center justify-center gap-2 rounded-lg border border-primary/50 bg-primary/10 px-3 text-sm font-semibold text-cyan"
          type="button"
          onClick={() => onOpenData(candidate.code)}
        >
          <ExternalLink className="h-4 w-4" />
          {en ? 'Open data' : '打开数据'}
        </button>
      </div>
    </article>
  );
}
