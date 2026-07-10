import type React from 'react';
import { CheckCircle2, Crown, FileCheck2, Search, Sparkles, UserPlus } from 'lucide-react';
import type { PlatformRetentionEventName, PlatformRetentionFunnelResponse } from '../../api/platform';

type RetentionFunnelPanelV97Props = {
  language: string;
  summary: PlatformRetentionFunnelResponse;
};

const STAGE_ICONS: Record<PlatformRetentionEventName, React.ComponentType<{ className?: string }>> = {
  free_query_completed: Search,
  registration_completed: UserPlus,
  api_trial_submitted: Sparkles,
  trial_report_opened: FileCheck2,
  premium_options_viewed: Crown,
};

const STAGE_LABELS: Record<PlatformRetentionEventName, { en: string; zh: string }> = {
  free_query_completed: { en: 'Query completed', zh: '完成免费查询' },
  registration_completed: { en: 'Registered', zh: '完成注册' },
  api_trial_submitted: { en: 'API trial', zh: '提交 API 试用' },
  trial_report_opened: { en: 'Report opened', zh: '打开试用报告' },
  premium_options_viewed: { en: 'Premium viewed', zh: '查看高级功能' },
};

export const RetentionFunnelPanelV97: React.FC<RetentionFunnelPanelV97Props> = ({
  language,
  summary,
}) => {
  const en = language === 'en';

  return (
    <section data-testid="retention-funnel-v97" className="border-y border-subtle py-5">
      <div className="flex min-w-0 flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex items-center gap-2 text-primary">
            <CheckCircle2 className="h-4 w-4" aria-hidden="true" />
            <span className="text-xs font-semibold uppercase">V97</span>
          </div>
          <h2 className="mt-1 text-lg font-semibold text-foreground">
            {en ? 'Free conversion funnel' : '免费用户转化漏斗'}
          </h2>
          <p className="mt-1 text-sm text-secondary-text">
            {en
              ? `${summary.windowDays}-day local window`
              : `近 ${summary.windowDays} 天本地窗口`}
          </p>
        </div>
        <div className="text-right">
          <div className="text-2xl font-semibold text-foreground">{summary.totalSessions}</div>
          <div className="text-xs text-muted-text">{en ? 'observed sessions' : '已观察会话'}</div>
        </div>
      </div>

      <div className="mt-4 grid min-w-0 gap-2 sm:grid-cols-2 xl:grid-cols-5">
        {summary.stages.map((stage, index) => {
          const Icon = STAGE_ICONS[stage.event];
          const label = STAGE_LABELS[stage.event][en ? 'en' : 'zh'];
          return (
            <div
              key={stage.event}
              data-testid={`retention-stage-${stage.event}`}
              className="min-w-0 border-l-2 border-primary/35 px-3 py-2"
            >
              <div className="flex min-w-0 items-center gap-2 text-sm font-medium text-foreground">
                <Icon className="h-4 w-4 shrink-0 text-primary" aria-hidden="true" />
                <span className="min-w-0">{label}</span>
              </div>
              <div className="mt-2 flex items-end justify-between gap-2">
                <span className="text-xl font-semibold text-foreground">{stage.reachedFromStart}</span>
                <span className="text-xs font-medium text-primary">
                  {index === 0 ? '100%' : `${stage.conversionFromPreviousPct}%`}
                </span>
              </div>
              <p className="mt-1 text-[11px] text-muted-text">
                {en
                  ? `${stage.droppedFromPrevious} dropped · ${stage.conversionFromStartPct}% from start`
                  : `流失 ${stage.droppedFromPrevious} · 起点转化 ${stage.conversionFromStartPct}%`}
              </p>
            </div>
          );
        })}
      </div>

      <p className="mt-4 text-xs text-muted-text">
        {en ? 'Local aggregate only · No AI used' : '仅本地汇总 · 未使用 AI'}
      </p>
    </section>
  );
};
