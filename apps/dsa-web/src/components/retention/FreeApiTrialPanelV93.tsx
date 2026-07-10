import type React from 'react';
import { LogIn, Sparkles } from 'lucide-react';
import { Button } from '../common';

type FreeApiTrialPanelV93Props = {
  language: string;
  signedIn: boolean;
  plan: string;
  weeklyLimit: number | null;
  remaining: number | null;
  busy: boolean;
  status?: string;
  error?: string;
  onAction: () => void;
};

export const FreeApiTrialPanelV93: React.FC<FreeApiTrialPanelV93Props> = ({
  language,
  signedIn,
  plan,
  weeklyLimit,
  remaining,
  busy,
  status = '',
  error = '',
  onAction,
}) => {
  const en = language === 'en';
  const paid = !['', 'free'].includes((plan || '').toLowerCase());
  const exhausted = signedIn && remaining !== null && remaining <= 0;
  const quotaText = remaining === null
    ? (en ? 'unlimited' : '不限量')
    : weeklyLimit === null
      ? `${remaining}`
      : `${remaining}/${weeklyLimit}`;

  const actionText = !signedIn
    ? (en ? 'Sign in for 5 weekly API trials' : '登录领取每周 5 次 API 试用')
    : paid
      ? (en ? `Run platform API analysis · ${quotaText} left` : `运行平台 API 分析 · 剩余 ${quotaText}`)
      : exhausted
        ? (en ? 'This week’s API trial is used up' : '本周 API 试用已用完')
        : (en ? `Use platform API trial · ${quotaText} left` : `使用平台 API 试用 · 剩余 ${quotaText}`);

  return (
    <section
      data-testid="free-platform-api-trial"
      className="mb-4 border-y border-primary/30 bg-primary/5 py-3"
    >
      <div className="flex min-w-0 flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-sm font-semibold text-foreground">
              {paid ? (en ? 'Platform API analysis' : '平台 API 分析') : (en ? 'Free AI trial analysis' : '免费 AI 试用分析')}
            </span>
            <span className="rounded-md border border-primary/40 bg-primary/10 px-2 py-1 text-[11px] font-medium text-primary">
              {en ? 'Separate from no-AI quick research' : '与未用 AI 快速研判分开计费'}
            </span>
          </div>
          <p className="mt-1 max-w-3xl text-xs leading-relaxed text-secondary-text">
            {!signedIn
              ? (en ? 'Free lookup remains available without login. Sign in only when you want to test an API-backed AI report.' : '不登录仍可继续免费查询；只有需要体验 API 驱动的 AI 报告时才登录。')
              : paid
                ? (en ? 'Premium members can use the platform API, their own API key, or an approved local model.' : '高级会员可使用平台 API、自己的 API Key，或已批准的本地模型。')
                : (en ? 'Free members receive 5 platform-API quick trials each week. When they are used up, free web research still remains available.' : '免费会员每周可体验 5 次平台 API 快速分析；额度用完后，免费网络研判仍可继续使用。')}
          </p>
        </div>
        <Button
          type="button"
          variant="secondary"
          size="sm"
          className="shrink-0"
          data-testid="free-platform-api-trial-action"
          isLoading={busy}
          disabled={busy || exhausted}
          onClick={onAction}
        >
          {signedIn ? <Sparkles className="h-4 w-4" aria-hidden="true" /> : <LogIn className="h-4 w-4" aria-hidden="true" />}
          {actionText}
        </Button>
      </div>
      {status || error ? (
        <div
          data-testid="free-platform-api-trial-status"
          role={error ? 'alert' : 'status'}
          className={`mt-2 rounded-md border px-3 py-2 text-xs ${error
            ? 'border-danger/50 bg-danger/10 text-danger'
            : 'border-success/45 bg-success/10 text-success'}`}
        >
          {error || status}
        </div>
      ) : null}
    </section>
  );
};
