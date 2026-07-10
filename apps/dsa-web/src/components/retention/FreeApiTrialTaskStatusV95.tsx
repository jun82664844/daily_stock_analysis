import type React from 'react';
import { AlertTriangle, CheckCircle2, Loader2 } from 'lucide-react';

type TrialTaskStatus = 'pending' | 'processing' | 'completed' | 'failed';

type FreeApiTrialTaskStatusV95Props = {
  language: string;
  taskId: string;
  status: TrialTaskStatus;
  progress: number;
};

export const FreeApiTrialTaskStatusV95: React.FC<FreeApiTrialTaskStatusV95Props> = ({
  language,
  taskId,
  status,
  progress,
}) => {
  const en = language === 'en';
  const boundedProgress = Math.max(0, Math.min(100, progress || 0));
  const isComplete = status === 'completed';
  const isFailed = status === 'failed';
  const title = isComplete
    ? (en ? 'Trial report completed' : '试用报告已完成')
    : isFailed
      ? (en ? 'Trial report failed' : '试用报告生成失败')
      : (en ? 'Trial report is generating' : '试用报告生成中');
  const detail = isComplete
    ? (en ? 'History has been refreshed. Open the latest report from the history center.' : '历史报告已刷新，可在历史报告中心打开最新报告。')
    : isFailed
      ? (en ? 'The report could not be generated. Check the error and try again later.' : '本次报告未能生成，请查看错误后稍后重试。')
      : (en ? 'This uses one platform API trial. You can keep using free no-AI research while it runs.' : '本次使用 1 次平台 API 试用，生成期间仍可继续使用免费未用 AI 研判。');

  return (
    <section
      data-testid="free-api-trial-task-status"
      role="status"
      aria-live="polite"
      className={`mb-4 border-y py-3 ${isFailed ? 'border-danger/40 bg-danger/5' : 'border-primary/30 bg-primary/5'}`}
    >
      <div className="flex min-w-0 items-start gap-2">
        {isComplete ? (
          <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-success" aria-hidden="true" />
        ) : isFailed ? (
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-danger" aria-hidden="true" />
        ) : (
          <Loader2 className="mt-0.5 h-4 w-4 shrink-0 animate-spin text-primary" aria-hidden="true" />
        )}
        <div className="min-w-0 flex-1">
          <div className="flex min-w-0 flex-wrap items-center justify-between gap-2">
            <h3 className="text-sm font-semibold text-foreground">{title}</h3>
            {!isComplete && !isFailed ? (
              <span data-testid="free-api-trial-task-progress" className="text-xs font-medium text-primary">
                {boundedProgress}%
              </span>
            ) : null}
          </div>
          <p className="mt-1 text-xs leading-relaxed text-secondary-text">{detail}</p>
          {!isComplete && !isFailed ? (
            <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-surface" aria-label={en ? 'Trial report progress' : '试用报告进度'}>
              <div className="h-full rounded-full bg-primary transition-[width]" style={{ width: `${boundedProgress}%` }} />
            </div>
          ) : null}
          <span className="sr-only">{taskId}</span>
        </div>
      </div>
    </section>
  );
};
