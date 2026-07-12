import type React from 'react';
import { Sparkles } from 'lucide-react';
import type { PlatformLocalModelStatus } from '../../api/platform';


interface LocalModelStatusV107Props {
  language: string;
  plan: string;
  quotaText: string;
  status: PlatformLocalModelStatus | null;
  onRunQuick?: () => void;
  isRunning?: boolean;
  disabled?: boolean;
}

const reasonCopy = (reason: string, isEnglish: boolean): string => {
  const copy: Record<string, [string, string]> = {
    local_model_disabled: ['本地模型尚未启用。免费行情查询不受影响。', 'Local AI is disabled. Free quote lookup is unaffected.'],
    local_model_unreachable: ['请启动 Ollama 后重试。免费行情查询不受影响。', 'Start Ollama and retry. Free quote lookup is unaffected.'],
    local_model_missing_base_url: ['本地模型地址尚未配置。', 'The local model endpoint is not configured.'],
    local_model_unsafe_base_url: ['本地模型地址未通过本机安全检查。', 'The local model endpoint did not pass the local safety check.'],
    local_model_missing_quick_model: ['快速分析模型尚未安装或配置。', 'The quick-analysis model is not installed or configured.'],
    local_model_missing_deep_model: ['深度分析模型尚未安装或配置。', 'The deep-analysis model is not installed or configured.'],
    local_model_busy: ['本地模型正在处理其他任务，请稍后重试。', 'The local model is busy. Retry shortly.'],
  };
  const selected = copy[reason] || ['本地模型暂不可用，请稍后重试。', 'Local AI is temporarily unavailable. Retry shortly.'];
  return isEnglish ? selected[1] : selected[0];
};

export const LocalModelStatusV107: React.FC<LocalModelStatusV107Props> = ({
  language,
  plan,
  quotaText,
  status,
  onRunQuick,
  isRunning = false,
  disabled = false,
}) => {
  const isEnglish = language === 'en';
  const ready = Boolean(status?.quickReady);
  const title = ready
    ? (isEnglish ? 'Local AI trial is ready' : '本地 AI 试用已就绪')
    : (isEnglish ? 'Local AI is offline' : '本地 AI 暂不可用');
  const planLabel = plan === 'free'
    ? (isEnglish ? 'Free trial' : '免费试用')
    : (isEnglish ? 'Member quota' : '会员额度');

  return (
    <section
      data-testid="local-model-status-v107"
      className={`mt-3 rounded-lg border p-3 ${ready ? 'border-primary/35 bg-primary/5' : 'border-warning/35 bg-warning/5'}`}
    >
      <div className="flex min-w-0 flex-wrap items-center justify-between gap-2">
        <div className="min-w-0">
          <div className="text-sm font-semibold text-foreground">{title}</div>
          <div className="mt-1 text-xs text-secondary-text">
            {ready
              ? (isEnglish ? 'Runs on this server through Ollama without using a paid cloud API.' : '通过本机 Ollama 运行，不消耗付费云端模型 API。')
              : reasonCopy(status?.reason || 'local_model_unavailable', isEnglish)}
          </div>
        </div>
        <span className="rounded-md border border-subtle px-2 py-1 text-xs text-secondary-text">
          {planLabel} · {quotaText}
        </span>
      </div>
      <div className="mt-3 grid min-w-0 gap-2 text-xs sm:grid-cols-2">
        <div className="min-w-0 rounded-md border border-subtle/80 bg-surface/40 px-3 py-2 text-secondary-text">
          <span className="font-medium text-foreground">{isEnglish ? 'Quick analysis' : '快速分析'}：</span>
          {status?.quickModel || '-'}
          <span className="ml-2">{status?.quickReady ? (isEnglish ? 'Ready' : '已就绪') : (isEnglish ? 'Unavailable' : '不可用')}</span>
        </div>
        <div className="min-w-0 rounded-md border border-subtle/80 bg-surface/40 px-3 py-2 text-secondary-text">
          <span className="font-medium text-foreground">{isEnglish ? 'Deep analysis' : '深度分析'}：</span>
          {status?.deepModel || '-'}
          <span className="ml-2">{status?.deepReady ? (isEnglish ? 'Ready' : '已就绪') : (isEnglish ? 'Unavailable' : '不可用')}</span>
        </div>
      </div>
      <div className="mt-3 flex min-w-0 flex-wrap items-center justify-between gap-2">
        <p className="min-w-0 flex-1 text-xs text-secondary-text">
          {isEnglish
            ? 'Information and data only. No investment advice, target price, position sizing or return promise.'
            : '只提供资讯和数据，不提供投资建议、目标价、仓位比例或收益承诺。'}
        </p>
        {onRunQuick ? (
          <button
            type="button"
            data-testid="local-model-run-quick-v107"
            disabled={!ready || disabled || isRunning}
            onClick={onRunQuick}
            className="inline-flex h-9 items-center gap-2 rounded-lg border border-primary/45 bg-primary/10 px-3 text-sm font-medium text-primary transition-colors hover:bg-primary/15 disabled:cursor-not-allowed disabled:opacity-50"
          >
            <Sparkles className="h-4 w-4" aria-hidden="true" />
            {isRunning
              ? (isEnglish ? 'Running local AI...' : '本地 AI 分析中...')
              : (isEnglish ? 'Run local AI detailed read' : '使用本地 AI 详细解读')}
          </button>
        ) : null}
      </div>
    </section>
  );
};

export default LocalModelStatusV107;
