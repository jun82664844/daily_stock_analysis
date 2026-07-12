import { ExternalLink } from 'lucide-react';

import type { BasicStockSnapshot } from '../../api/stocks';


type GlobalEquityPayload = NonNullable<
  NonNullable<BasicStockSnapshot['intelligence']>['globalEquityEnrichment']
>;

type Props = {
  payload: GlobalEquityPayload;
  language: 'zh' | 'en';
};

const channelLabel = (category: string, fallback: string, language: 'zh' | 'en') => {
  if (language === 'en') return fallback;
  if (category === 'news') return '公司资讯';
  if (category === 'filings') return fallback.toUpperCase().includes('SEC') ? 'SEC 文件' : '港交所公告';
  if (category === 'fundamentals') return '公司资料';
  return fallback;
};

const statusLabel = (status: string, language: 'zh' | 'en') => {
  if (language === 'en') {
    if (status === 'available') return 'Available';
    if (status === 'unavailable') return 'Unavailable';
    return 'Degraded';
  }
  if (status === 'available') return '可用';
  if (status === 'unavailable') return '不可用';
  return '降级';
};

const sourceLabel = (source: string, language: 'zh' | 'en') => {
  if (language === 'en') return source;
  const labels: Record<string, string> = {
    global_equity_public_adapter: '港美股公开数据适配器',
    yahoo_finance_search_feed: 'Yahoo Finance 公开资讯源',
    sec_edgar_submissions: 'SEC EDGAR 官方文件源',
    hkexnews_official_search: '港交所披露易官方查询',
    yfinance_profile: 'Yahoo Finance 公司资料',
  };
  return labels[source] || source;
};

const displayValue = (value: unknown) => {
  if (value === null || value === undefined || value === '') return '-';
  if (typeof value === 'number') return new Intl.NumberFormat('en-US', { maximumFractionDigits: 4 }).format(value);
  return String(value);
};

export function GlobalEquityEnrichmentCard({ payload, language }: Props) {
  const isEnglish = language === 'en';

  return (
    <section
      data-testid="basic-query-global-equity-enrichment"
      className="mb-4 overflow-hidden rounded-lg border border-primary/45 bg-surface/55"
    >
      <div className="flex min-w-0 flex-col gap-3 border-b border-subtle/80 p-4 lg:flex-row lg:items-start lg:justify-between">
        <div className="min-w-0">
          <div className="text-xs font-semibold text-primary">
            {isEnglish ? 'US / HK public data' : '港美股公开数据'}
          </div>
          <h3 className="mt-1 text-lg font-semibold text-foreground">
            {isEnglish
              ? payload.title
              : payload.market === 'us'
                ? '美股公开资讯与 SEC 文件'
                : '港股公开资讯与公告状态'}
          </h3>
          <p className="mt-1 text-sm leading-relaxed text-secondary-text">
            {isEnglish
              ? payload.summary
              : '直接读取公开来源，展示真实标题、时间、来源链接和公告状态；缺失来源会明确标记降级。'}
          </p>
        </div>
        <div className="flex shrink-0 flex-wrap gap-2 text-xs">
          <span className="rounded-md border border-primary/40 bg-primary/10 px-2 py-1 font-semibold text-primary">
            {statusLabel(payload.status, language)}
          </span>
          <span className="rounded-md border border-subtle/80 px-2 py-1 text-secondary-text">
            {isEnglish ? 'No AI' : '未使用 AI'}
          </span>
          <span className="rounded-md border border-subtle/80 px-2 py-1 text-secondary-text">
            {sourceLabel(payload.source, language)}
          </span>
        </div>
      </div>

      <div className="divide-y divide-subtle/80">
        {payload.channels.map((channel) => (
          <div key={`${channel.category}-${channel.source}`} className="grid min-w-0 gap-3 p-4 lg:grid-cols-[minmax(13rem,0.34fr)_minmax(0,0.66fr)]">
            <div className="min-w-0">
              <div className="flex min-w-0 flex-wrap items-center gap-2">
                <h4 className="text-sm font-semibold text-foreground">
                  {channelLabel(channel.category, channel.title, language)}
                </h4>
                <span className="rounded-md border border-subtle/80 px-1.5 py-0.5 text-[11px] text-secondary-text">
                  {statusLabel(channel.status, language)}
                </span>
              </div>
              <p className="mt-1 text-xs leading-relaxed text-secondary-text">
                {isEnglish ? channel.summary : channel.status === 'available'
                  ? '公开来源数据已返回，可通过右侧原文核对。'
                  : '当前来源未返回可展示明细，系统未生成替代内容。'}
              </p>
              <div className="mt-2 text-[11px] text-secondary-text">
                {sourceLabel(channel.source, language)}
              </div>
              {channel.officialUrl ? (
                <a
                  className="mt-2 inline-flex items-center gap-1 text-xs font-medium text-primary hover:underline"
                  href={channel.officialUrl}
                  target="_blank"
                  rel="noreferrer"
                >
                  {isEnglish ? 'Open official search' : '打开官方查询'}
                  <ExternalLink className="h-3.5 w-3.5" aria-hidden="true" />
                </a>
              ) : null}
            </div>

            <div className="min-w-0 divide-y divide-subtle/70 border-l-0 lg:border-l lg:border-subtle/70 lg:pl-4">
              {channel.items.length > 0 ? channel.items.map((item, index) => {
                const title = item.title || item.label || `${channelLabel(channel.category, channel.title, language)} ${index + 1}`;
                return (
                  <div key={`${title}-${index}`} className="min-w-0 py-2 first:pt-0 last:pb-0">
                    {item.url ? (
                      <a
                        className="inline-flex max-w-full items-start gap-1 text-sm font-semibold leading-snug text-foreground hover:text-primary hover:underline"
                        href={item.url}
                        target="_blank"
                        rel="noreferrer"
                      >
                        <span className="min-w-0">{title}</span>
                        <ExternalLink className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden="true" />
                      </a>
                    ) : (
                      <div className="text-sm font-semibold text-foreground">{title}</div>
                    )}
                    {item.value !== undefined ? (
                      <div className="mt-1 text-sm text-foreground">{displayValue(item.value)}</div>
                    ) : null}
                    {item.summary ? (
                      <p className="mt-1 text-xs leading-relaxed text-secondary-text">{item.summary}</p>
                    ) : null}
                    <div className="mt-1 flex min-w-0 flex-wrap gap-2 text-[11px] text-secondary-text">
                      {item.documentType ? <span>{item.documentType}</span> : null}
                      {item.publisher ? <span>{item.publisher}</span> : null}
                      {item.publishedAt ? <time dateTime={item.publishedAt}>{item.publishedAt}</time> : null}
                    </div>
                  </div>
                );
              }) : (
                <div className="py-2 text-xs leading-relaxed text-secondary-text">
                  {isEnglish ? channel.action : '请通过官方来源核对；当前没有可展示的明细。'}
                </div>
              )}
            </div>
          </div>
        ))}
      </div>

      <div className="flex min-w-0 flex-col gap-2 border-t border-subtle/80 bg-primary/5 px-4 py-3 text-xs text-secondary-text lg:flex-row lg:items-center lg:justify-between">
        <span>{isEnglish ? payload.premiumUnlock : '高级版可接入更广的数据 API 和更高刷新额度，页面结构保持一致。'}</span>
        <span className="font-medium text-foreground">
          {isEnglish
            ? 'Information and data only; not investment advice or a trading instruction.'
            : '仅提供资讯和数据，不构成投资建议或交易指令。'}
        </span>
      </div>
    </section>
  );
}
