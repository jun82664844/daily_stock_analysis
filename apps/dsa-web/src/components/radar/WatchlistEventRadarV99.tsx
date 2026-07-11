import type React from 'react';
import {
  Activity,
  BellRing,
  Check,
  Database,
  ExternalLink,
  Newspaper,
  Plus,
  Radar,
  Search,
  TrendingDown,
  TrendingUp,
  TriangleAlert,
} from 'lucide-react';
import type {
  PlatformWatchlistRadarAlertSuggestion,
  PlatformWatchlistRadarEvent,
  PlatformWatchlistRadarResponse,
} from '../../api/platform';

type Props = {
  language: string;
  radar: PlatformWatchlistRadarResponse;
  onSelectSymbol: (stockCode: string) => void;
  onSaveAlert?: (alert: PlatformWatchlistRadarAlertSuggestion) => void;
  savedRuleKeys?: Set<string>;
  alertBusy?: boolean;
};

const numberText = (value: number | null | undefined, maximumFractionDigits = 2): string => (
  typeof value === 'number' && Number.isFinite(value)
    ? value.toLocaleString(undefined, { maximumFractionDigits })
    : '-'
);

const percentText = (value: number | null | undefined): string => {
  if (typeof value !== 'number' || !Number.isFinite(value)) return '-';
  return `${value > 0 ? '+' : ''}${numberText(value)}%`;
};

const eventText = (event: PlatformWatchlistRadarEvent, en: boolean): string => {
  if (event.type === 'price_move') {
    const direction = event.direction === 'up'
      ? (en ? 'rose' : '上涨')
      : (en ? 'fell' : '下跌');
    return en
      ? `Price ${direction} materially by ${numberText(Math.abs(event.value ?? 0))}%`
      : `价格显著${direction} ${numberText(Math.abs(event.value ?? 0))}%`;
  }
  if (event.type === 'trend_position') {
    const direction = event.direction === 'above'
      ? (en ? 'above' : '站上')
      : (en ? 'below' : '跌破');
    return en
      ? `Price is ${direction} MA20 ${numberText(event.referenceValue)}`
      : `${direction} MA20 ${numberText(event.referenceValue)}`;
  }
  if (event.type === 'volume_change') {
    const direction = event.direction === 'expanded'
      ? (en ? 'expanded' : '放大')
      : (en ? 'contracted' : '收缩');
    return en
      ? `Volume ${direction} ${numberText(Math.abs(event.value ?? 0))}% versus MA5`
      : `成交量较 5 日均量${direction} ${numberText(Math.abs(event.value ?? 0))}%`;
  }
  if (event.type === 'data_quality') {
    return en ? 'Market data needs a freshness check' : '行情数据需要检查新鲜度';
  }
  return event.title || (en ? 'Traceable source update' : '可追溯来源更新');
};

const alertText = (alert: PlatformWatchlistRadarAlertSuggestion, en: boolean): string => {
  if (alert.type === 'price_move') {
    return en
      ? `Price move reaches ${numberText(alert.threshold)}%`
      : `价格涨跌达到 ${numberText(alert.threshold)}%`;
  }
  if (alert.type === 'ma20_cross') {
    return en
      ? `Price crosses MA20 at ${numberText(alert.referenceValue)}`
      : `价格穿越 MA20 ${numberText(alert.referenceValue)}`;
  }
  return en
    ? `Volume changes ${numberText(alert.threshold)}% versus MA5`
    : `成交量较 5 日均量变化 ${numberText(alert.threshold)}%`;
};

const severityClasses = (severity: string): string => {
  if (severity === 'critical') return 'border-danger/45 bg-danger/10 text-danger';
  if (severity === 'warning') return 'border-warning/45 bg-warning/10 text-warning';
  return 'border-primary/35 bg-primary/5 text-primary';
};

export const WatchlistEventRadarV99: React.FC<Props> = ({
  language,
  radar,
  onSelectSymbol,
  onSaveAlert,
  savedRuleKeys = new Set(),
  alertBusy = false,
}) => {
  const en = language === 'en';

  if (radar.items.length === 0) {
    return (
      <section
        data-testid="watchlist-event-radar-v99"
        className="border-y border-primary/25 py-5"
      >
        <div className="flex items-center gap-2 text-base font-semibold text-foreground">
          <Radar className="h-5 w-5 text-primary" aria-hidden="true" />
          {en ? 'Today’s watchlist event radar' : '今日自选事件雷达'}
        </div>
        <div
          data-testid="watchlist-event-radar-empty"
          className="mt-3 border-l-2 border-primary pl-4 text-sm text-secondary-text"
        >
          {en
            ? 'Add symbols to your watchlist first. The radar will compare price, MA20, volume, freshness, and traceable source updates without using AI.'
            : '先加入自选股。雷达会在不使用 AI 的前提下，对比价格、MA20、量能、数据新鲜度和可追溯来源更新。'}
        </div>
      </section>
    );
  }

  const strongest = radar.summary.strongest;
  const weakest = radar.summary.weakest;

  return (
    <section
      data-testid="watchlist-event-radar-v99"
      className="border-y border-primary/25 py-5"
    >
      <div className="flex min-w-0 flex-col gap-3 xl:flex-row xl:items-end xl:justify-between">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <Radar className="h-5 w-5 text-primary" aria-hidden="true" />
            <h3 className="text-base font-semibold text-foreground">
              {en ? 'Today’s watchlist event radar' : '今日自选事件雷达'}
            </h3>
            <span className="rounded-md border border-primary/40 bg-primary/10 px-2 py-1 text-[11px] font-medium text-primary">
              {en ? 'No AI used' : '未使用 AI'}
            </span>
          </div>
          <p className="mt-1 max-w-3xl text-xs leading-relaxed text-secondary-text">
            {en
              ? 'Start with what changed, why it matters, and what to watch next. Source updates appear only when a traceable stored link exists.'
              : '先看发生了什么、为什么值得关注、下一步观察什么。只有存在可追溯的已入库链接时，才显示来源事件。'}
          </p>
        </div>
        <div className="grid min-w-0 grid-cols-2 gap-x-5 gap-y-2 text-xs sm:grid-cols-4">
          <div><span className="text-secondary-text">{en ? 'Strongest' : '最强'}</span><strong className="ml-1 text-foreground">{strongest?.stockCode ?? '-'} {percentText(strongest?.changePercent)}</strong></div>
          <div><span className="text-secondary-text">{en ? 'Weakest' : '最弱'}</span><strong className="ml-1 text-foreground">{weakest?.stockCode ?? '-'} {percentText(weakest?.changePercent)}</strong></div>
          <div><span className="text-secondary-text">{en ? 'Risk flags' : '风险标记'}</span><strong className="ml-1 text-foreground">{radar.summary.riskCount}</strong></div>
          <div><span className="text-secondary-text">{en ? 'Source updates' : '来源更新'}</span><strong className="ml-1 text-foreground">{radar.summary.sourceEventCount}</strong></div>
        </div>
      </div>

      {radar.hiddenCount > 0 ? (
        <div className="mt-4 flex items-start gap-2 border-l-2 border-warning pl-3 text-xs text-secondary-text">
          <TriangleAlert className="mt-0.5 h-4 w-4 shrink-0 text-warning" aria-hidden="true" />
          <span>
            {en
              ? `${radar.hiddenCount} more watchlist symbols were not included in this review. Free keeps the same radar structure; premium increases review capacity and automation.`
              : `还有 ${radar.hiddenCount} 只自选未纳入本次复盘。免费版保留相同雷达结构；高级版增加复盘容量和自动化能力。`}
          </span>
        </div>
      ) : null}

      <div className="mt-5 grid min-w-0 gap-3 xl:grid-cols-2">
        {radar.items.map((item) => {
          const primaryEvents = item.events.slice(0, 4);
          return (
            <article key={item.stockCode} className="min-w-0 rounded-lg border border-subtle bg-surface/60 p-4">
              <div className="flex min-w-0 items-start justify-between gap-3">
                <div className="min-w-0">
                  <button
                    type="button"
                    data-testid={`watchlist-radar-symbol-${item.stockCode}`}
                    onClick={() => onSelectSymbol(item.stockCode)}
                    className="inline-flex min-w-0 items-center gap-2 text-left text-sm font-semibold text-foreground hover:text-primary"
                  >
                    <Search className="h-4 w-4 shrink-0" aria-hidden="true" />
                    <span className="truncate">{item.stockCode}</span>
                  </button>
                  <div className="mt-0.5 truncate text-xs text-secondary-text">{item.stockName || item.market.toUpperCase()}</div>
                </div>
                <div className="shrink-0 text-right">
                  <div className="text-base font-semibold text-foreground">{numberText(item.currentPrice, 4)}</div>
                  <div className={item.changePercent !== undefined && item.changePercent !== null && item.changePercent < 0 ? 'text-danger' : 'text-success'}>
                    {percentText(item.changePercent)}
                  </div>
                </div>
              </div>

              <div className="mt-3 grid grid-cols-3 gap-2 border-y border-subtle py-2 text-xs">
                <div><span className="block text-secondary-text">MA20</span><strong className="text-foreground">{numberText(item.ma20, 4)}</strong></div>
                <div><span className="block text-secondary-text">{en ? 'Volume vs MA5' : '量能较 5 日'}</span><strong className="text-foreground">{percentText(item.volumeChangePercent)}</strong></div>
                <div><span className="block text-secondary-text">{en ? 'Signal' : '信号分'}</span><strong className="text-foreground">{item.signalScore ?? '-'}</strong></div>
              </div>

              <div className="mt-3 space-y-2">
                {primaryEvents.length > 0 ? primaryEvents.map((event, index) => (
                  <div key={`${item.stockCode}-${event.type}-${index}`} className="flex min-w-0 items-start gap-2 text-xs">
                    {event.type === 'source_update'
                      ? <Newspaper className="mt-0.5 h-4 w-4 shrink-0 text-primary" aria-hidden="true" />
                      : event.direction === 'up' || event.direction === 'above'
                        ? <TrendingUp className="mt-0.5 h-4 w-4 shrink-0 text-success" aria-hidden="true" />
                        : event.direction === 'down' || event.direction === 'below'
                          ? <TrendingDown className="mt-0.5 h-4 w-4 shrink-0 text-danger" aria-hidden="true" />
                          : <Activity className="mt-0.5 h-4 w-4 shrink-0 text-warning" aria-hidden="true" />}
                    <div className="min-w-0 flex-1">
                      {event.type === 'source_update' && event.sourceUrl ? (
                        <a
                          href={event.sourceUrl}
                          target="_blank"
                          rel="noreferrer"
                          className="inline-flex min-w-0 items-center gap-1 font-medium text-foreground hover:text-primary"
                        >
                          <span className="truncate">{eventText(event, en)}</span>
                          <ExternalLink className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />
                        </a>
                      ) : (
                        <span className="font-medium text-foreground">{eventText(event, en)}</span>
                      )}
                      {event.summary ? <p className="mt-0.5 line-clamp-2 text-secondary-text">{event.summary}</p> : null}
                    </div>
                    <span className={`shrink-0 rounded-md border px-1.5 py-0.5 text-[10px] ${severityClasses(event.severity)}`}>
                      {event.severity === 'critical'
                        ? (en ? 'Priority' : '优先')
                        : event.severity === 'warning'
                          ? (en ? 'Watch' : '关注')
                          : (en ? 'Info' : '信息')}
                    </span>
                  </div>
                )) : (
                  <div className="text-xs text-secondary-text">{en ? 'No material change in this refresh.' : '本次刷新暂无显著变化。'}</div>
                )}
              </div>

              <div className="mt-3 flex min-w-0 flex-wrap items-center gap-1.5 border-t border-subtle pt-3 text-[11px] text-secondary-text">
                <BellRing className="h-3.5 w-3.5 text-primary" aria-hidden="true" />
                <span className="font-medium text-foreground">{en ? 'Suggested alerts' : '建议提醒'}</span>
                {item.suggestedAlerts.slice(0, 3).map((alert) => {
                  const ruleKey = `${item.stockCode}:${alert.type}`;
                  const saved = savedRuleKeys.has(ruleKey);
                  return onSaveAlert ? (
                    <button
                      key={ruleKey}
                      type="button"
                      data-testid={`watchlist-alert-save-${item.stockCode}-${alert.type}`}
                      disabled={alertBusy || saved}
                      onClick={() => onSaveAlert(alert)}
                      className="inline-flex min-h-8 items-center gap-1 rounded-md border border-subtle px-2 py-1 text-left hover:border-primary/45 hover:text-foreground disabled:cursor-default disabled:opacity-70"
                    >
                      {saved
                        ? <Check className="h-3.5 w-3.5 text-success" aria-hidden="true" />
                        : <Plus className="h-3.5 w-3.5 text-primary" aria-hidden="true" />}
                      <span>{saved ? (en ? 'Saved' : '已保存') : alertText(alert, en)}</span>
                    </button>
                  ) : (
                    <span key={ruleKey} className="rounded-md border border-subtle px-2 py-1">
                      {alertText(alert, en)}
                    </span>
                  );
                })}
              </div>
            </article>
          );
        })}
      </div>

      <div className="mt-4 flex flex-wrap items-center gap-2 text-[11px] text-secondary-text">
        <Database className="h-3.5 w-3.5" aria-hidden="true" />
        <span>{en ? `Processed ${radar.processed}/${radar.totalWatchlist}` : `已处理 ${radar.processed}/${radar.totalWatchlist}`}</span>
        <span>·</span>
        <span>{en ? 'Information analysis only; not investment advice.' : '仅供信息分析，不构成投资建议。'}</span>
      </div>
    </section>
  );
};
