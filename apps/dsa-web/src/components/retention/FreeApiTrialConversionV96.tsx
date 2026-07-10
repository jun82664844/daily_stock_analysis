import type React from 'react';
import { ArrowUpRight, Crown } from 'lucide-react';
import { Button } from '../common';

type FreeApiTrialConversionV96Props = {
  language: string;
  onExplorePremium: () => void;
};

export const FreeApiTrialConversionV96: React.FC<FreeApiTrialConversionV96Props> = ({
  language,
  onExplorePremium,
}) => {
  const en = language === 'en';

  return (
    <section
      data-testid="free-api-trial-conversion-v96"
      className="border-y border-primary/35 bg-primary/5 py-4"
    >
      <div className="flex min-w-0 flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
        <div className="min-w-0">
          <div className="flex min-w-0 flex-wrap items-center gap-2">
            <Crown className="h-4 w-4 shrink-0 text-primary" aria-hidden="true" />
            <h2 className="text-base font-semibold text-foreground">
              {en ? 'Free trial report opened' : '免费试用报告已打开'}
            </h2>
            <span className="rounded-md border border-success/40 bg-success/10 px-2 py-1 text-[11px] font-medium text-success">
              {en ? '1 trial used' : '已使用 1 次试用'}
            </span>
          </div>
          <p className="mt-2 max-w-3xl text-sm leading-relaxed text-secondary-text">
            {en
              ? 'This is the complete API-backed trial report. Premium keeps the same research workflow with higher quotas and a choice of Platform API, Your API, or Local model.'
              : '这是完整的 API 试用报告。高级版保持相同研究流程，并提供更高额度，可选择平台 API、我的 API 或本地模型。'}
          </p>
          <div className="mt-3 flex min-w-0 flex-wrap gap-2 text-xs text-secondary-text">
            <span className="rounded-md border border-subtle px-2 py-1">{en ? 'Platform API' : '平台 API'}</span>
            <span className="rounded-md border border-subtle px-2 py-1">{en ? 'Your API' : '我的 API'}</span>
            <span className="rounded-md border border-subtle px-2 py-1">{en ? 'Local model' : '本地模型'}</span>
          </div>
          <p className="mt-2 text-[11px] text-muted-text">
            {en
              ? 'Local development preview only; real payment remains disabled.'
              : '当前仅为本地开发预览，真实支付仍未启用。'}
          </p>
        </div>
        <Button
          type="button"
          variant="secondary"
          size="sm"
          className="shrink-0"
          data-testid="free-api-trial-upgrade"
          onClick={onExplorePremium}
        >
          {en ? 'Explore premium options' : '查看高级功能'}
          <ArrowUpRight className="h-4 w-4" aria-hidden="true" />
        </Button>
      </div>
    </section>
  );
};
