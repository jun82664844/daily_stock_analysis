import type React from 'react';
import { BellRing, CalendarClock, History, ShieldCheck, Trash2 } from 'lucide-react';
import type {
  PlatformWatchlistAlertRulesResponse,
  PlatformWatchlistRadarHistoryResponse,
  PlatformWatchlistTriggeredAlert,
} from '../../api/platform';

type Props = {
  language: string;
  history: PlatformWatchlistRadarHistoryResponse;
  rules: PlatformWatchlistAlertRulesResponse;
  triggeredAlerts: PlatformWatchlistTriggeredAlert[];
  busy: boolean;
  onDeleteRule: (ruleId: number) => void;
};

const numberText = (value: number | null | undefined): string => (
  typeof value === 'number' && Number.isFinite(value)
    ? value.toLocaleString(undefined, { maximumFractionDigits: 2 })
    : '-'
);

const ruleText = (
  stockCode: string,
  ruleType: string,
  threshold: number | null | undefined,
  referenceValue: number | null | undefined,
  en: boolean,
): string => {
  if (ruleType === 'price_move') return en ? `${stockCode} moves ${numberText(threshold)}%` : `${stockCode} 涨跌达到 ${numberText(threshold)}%`;
  if (ruleType === 'volume_change') return en ? `${stockCode} volume changes ${numberText(threshold)}%` : `${stockCode} 量能变化 ${numberText(threshold)}%`;
  if (ruleType === 'ma20_cross') return en ? `${stockCode} crosses MA20 ${numberText(referenceValue)}` : `${stockCode} 穿越 MA20 ${numberText(referenceValue)}`;
  if (ruleType === 'source_update') return en ? `${stockCode} gets a source update` : `${stockCode} 出现来源更新`;
  return en ? `${stockCode} data quality degrades` : `${stockCode} 数据质量下降`;
};

const triggerText = (item: PlatformWatchlistTriggeredAlert, en: boolean): string => {
  if (item.ruleType === 'ma20_cross') {
    if (en) return `${item.stockCode} crossed ${item.direction === 'above' ? 'above' : 'below'} MA20 ${numberText(item.referenceValue)}`;
    return `${item.stockCode} ${item.direction === 'above' ? '上穿' : '下穿'} MA20 ${numberText(item.referenceValue)}`;
  }
  if (item.ruleType === 'price_move') return en ? `${item.stockCode} price move reached ${numberText(item.value)}%` : `${item.stockCode} 涨跌达到 ${numberText(item.value)}%`;
  if (item.ruleType === 'volume_change') return en ? `${item.stockCode} volume changed ${numberText(item.value)}%` : `${item.stockCode} 量能变化 ${numberText(item.value)}%`;
  if (item.ruleType === 'source_update') return en ? `${item.stockCode} has a traceable source update` : `${item.stockCode} 出现可追溯来源更新`;
  return en ? `${item.stockCode} has a data-quality warning` : `${item.stockCode} 出现数据质量提醒`;
};

const dateText = (value: string | null | undefined, en: boolean): string => {
  if (!value) return '-';
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return parsed.toLocaleString(en ? 'en-US' : 'zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  });
};

export const WatchlistAlertLoopV100: React.FC<Props> = ({
  language,
  history,
  rules,
  triggeredAlerts,
  busy,
  onDeleteRule,
}) => {
  const en = language === 'en';
  return (
    <section data-testid="watchlist-alert-loop-v100" className="border-b border-primary/25 pb-5">
      <div className="flex min-w-0 flex-wrap items-center gap-2">
        <CalendarClock className="h-5 w-5 text-primary" aria-hidden="true" />
        <h3 className="text-base font-semibold text-foreground">
          {en ? 'Continuous tracking and daily reviews' : '连续跟踪与每日复盘'}
        </h3>
        <span className="rounded-md border border-primary/35 bg-primary/10 px-2 py-1 text-[11px] text-primary">
          {en ? `${rules.plan} alerts ${rules.total}/${rules.limit}` : `${rules.plan === 'free' ? '免费版' : '高级版'}提醒 ${rules.total}/${rules.limit}`}
        </span>
        <span className="rounded-md border border-subtle px-2 py-1 text-[11px] text-secondary-text">
          {en ? `Recent reviews ${history.total}` : `最近复盘 ${history.total} 次`}
        </span>
      </div>
      <p className="mt-1 text-xs leading-relaxed text-secondary-text">
        {history.total === 0
          ? (en ? 'The first run creates a comparison baseline. Cross alerts start from the next saved review.' : '首次运行会建立比较基线；穿越类提醒从下一次已保存复盘开始判断。')
          : (en ? 'Saved reviews compare today with the prior baseline without using AI.' : '已保存复盘会把今天与上一次基线对比，不使用 AI。')}
      </p>

      {triggeredAlerts.length > 0 ? (
        <div className="mt-4 border-l-2 border-warning pl-3">
          <div className="flex items-center gap-2 text-xs font-semibold text-foreground">
            <BellRing className="h-4 w-4 text-warning" aria-hidden="true" />
            {en ? `Triggered this run: ${triggeredAlerts.length}` : `本次触发 ${triggeredAlerts.length} 条`}
          </div>
          <div className="mt-2 flex flex-wrap gap-2">
            {triggeredAlerts.map((item) => (
              <span key={`${item.ruleId}-${item.stockCode}`} className="rounded-md border border-warning/40 bg-warning/10 px-2 py-1 text-xs text-warning">
                {triggerText(item, en)}
              </span>
            ))}
          </div>
        </div>
      ) : null}

      <div className="mt-4 grid min-w-0 gap-5 xl:grid-cols-2">
        <div className="min-w-0">
          <div className="flex items-center gap-2 text-xs font-semibold text-foreground">
            <ShieldCheck className="h-4 w-4 text-primary" aria-hidden="true" />
            {en ? 'Private alert rules' : '我的私有提醒'}
          </div>
          <div className="mt-2 divide-y divide-subtle border-y border-subtle">
            {rules.items.length > 0 ? rules.items.map((rule) => (
              <div key={rule.id} className="flex min-w-0 items-center justify-between gap-3 py-2 text-xs">
                <span className="min-w-0 truncate text-foreground">
                  {ruleText(rule.stockCode, rule.ruleType, rule.threshold, rule.referenceValue, en)}
                </span>
                <button
                  type="button"
                  data-testid={`watchlist-alert-rule-delete-${rule.id}`}
                  aria-label={en ? `Delete ${rule.stockCode} alert` : `删除 ${rule.stockCode} 提醒`}
                  disabled={busy}
                  onClick={() => onDeleteRule(rule.id)}
                  className="inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-md border border-subtle text-secondary-text hover:text-danger disabled:opacity-50"
                >
                  <Trash2 className="h-4 w-4" aria-hidden="true" />
                </button>
              </div>
            )) : (
              <div className="py-3 text-xs text-secondary-text">
                {en ? 'No saved alerts yet. Save one from the suggested alerts below.' : '暂无已保存提醒，可从下方建议提醒中直接保存。'}
              </div>
            )}
          </div>
        </div>

        <div className="min-w-0">
          <div className="flex items-center gap-2 text-xs font-semibold text-foreground">
            <History className="h-4 w-4 text-primary" aria-hidden="true" />
            {en ? 'Daily review timeline' : '每日复盘时间线'}
          </div>
          <div className="mt-2 divide-y divide-subtle border-y border-subtle">
            {history.items.length > 0 ? history.items.slice(0, 7).map((item) => (
              <div key={item.id} className="grid grid-cols-[minmax(0,1fr)_auto] gap-3 py-2 text-xs">
                <div className="min-w-0">
                  <div className="font-medium text-foreground">{dateText(item.createdAt, en)}</div>
                  <div className="mt-0.5 truncate text-secondary-text">
                    {en
                      ? `Strongest ${item.strongest?.stockCode ?? '-'} / weakest ${item.weakest?.stockCode ?? '-'}`
                      : `最强 ${item.strongest?.stockCode ?? '-'} / 最弱 ${item.weakest?.stockCode ?? '-'}`}
                  </div>
                </div>
                <div className="text-right text-secondary-text">
                  <div>{en ? `Processed ${item.processed}` : `处理 ${item.processed} 只`}</div>
                  <div>{en ? `Triggers ${item.triggeredCount}` : `触发 ${item.triggeredCount}`}</div>
                </div>
              </div>
            )) : (
              <div className="py-3 text-xs text-secondary-text">
                {en ? 'No saved daily review yet.' : '暂无已保存的每日复盘。'}
              </div>
            )}
          </div>
        </div>
      </div>
    </section>
  );
};
