import type { SourceStatus } from '../../api/marketWorkspace';

const STATUS_LABELS: Record<SourceStatus, { zh: string; en: string }> = {
  fresh: { zh: '新鲜', en: 'Fresh' },
  cached: { zh: '缓存', en: 'Cached' },
  stale: { zh: '过期', en: 'Stale' },
  unavailable: { zh: '不可用', en: 'Unavailable' },
};

const SOURCE_LABELS: Record<string, { zh: string; en: string }> = {
  yahoo_chart_reference: { zh: 'Yahoo 图表', en: 'Yahoo Chart' },
  yahoo_chart_history: { zh: 'Yahoo 历史行情', en: 'Yahoo History' },
  cn_quote: { zh: 'A股行情', en: 'A-share quote' },
  hk_quote: { zh: '港股行情', en: 'Hong Kong quote' },
  us_quote: { zh: '美股行情', en: 'US quote' },
  hk_realtime: { zh: '港股行情', en: 'Hong Kong quote' },
  us_realtime: { zh: '美股行情', en: 'US quote' },
  a_share_realtime: { zh: 'A股行情', en: 'A-share quote' },
  cn_market_snapshot: { zh: 'A股市场快照', en: 'A-share market snapshot' },
  hk_market_snapshot: { zh: '港股市场快照', en: 'Hong Kong market snapshot' },
  us_market_snapshot: { zh: '美股市场快照', en: 'US market snapshot' },
  market_news_pool: { zh: '市场资讯源', en: 'Market news' },
};

export const formatSourceStatus = (status: string | null | undefined, language: 'zh' | 'en') => {
  const normalized = String(status || '') as SourceStatus;
  return STATUS_LABELS[normalized]?.[language] ?? (status || '-');
};

export const formatSourceLabel = (source: string | null | undefined, language: 'zh' | 'en') => {
  const normalized = String(source || '').trim();
  return SOURCE_LABELS[normalized]?.[language] ?? (normalized || '-');
};

const WARNING_LABELS: Record<string, { zh: string; en: string }> = {
  market_news_unavailable: {
    zh: '\u6388\u6743\u8d44\u8baf\u6e90\u6682\u4e0d\u53ef\u7528',
    en: 'Authorized news source unavailable',
  },
  market_quotes_unavailable: {
    zh: '\u884c\u60c5\u6570\u636e\u6682\u4e0d\u53ef\u7528',
    en: 'Market quote data unavailable',
  },
};

export const formatMarketWarning = (warning: string | null | undefined, language: 'zh' | 'en') => {
  const normalized = String(warning || '').trim();
  const timeoutPrefix = 'market_symbol_timeout:';
  if (normalized.startsWith(timeoutPrefix)) {
    const symbol = normalized.slice(timeoutPrefix.length) || '-';
    return language === 'en' ? `${symbol} quote request timed out` : `${symbol} \u884c\u60c5\u8bf7\u6c42\u8d85\u65f6`;
  }
  return WARNING_LABELS[normalized]?.[language]
    ?? (language === 'en' ? 'Some market data is degraded' : '\u90e8\u5206\u5e02\u573a\u6570\u636e\u5df2\u964d\u7ea7');
};

export const formatMarketTimestamp = (value: string | null | undefined, language: 'zh' | 'en') => {
  const raw = String(value || '').trim();
  if (!raw) return '-';
  const epoch = /^\d{10,13}$/.test(raw) ? Number(raw) : null;
  const parsed = new Date(epoch == null ? raw : epoch * (raw.length === 10 ? 1000 : 1));
  if (Number.isNaN(parsed.getTime())) return raw;
  return parsed.toLocaleString(language === 'en' ? 'en-US' : 'zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  });
};

export const formatMarketNumber = (
  value: unknown,
  language: 'zh' | 'en',
  maximumFractionDigits?: number,
) => {
  if (value == null || value === '' || !Number.isFinite(Number(value))) return '-';
  const parsed = Number(value);
  const digits = maximumFractionDigits ?? (Math.abs(parsed) < 1 ? 4 : 2);
  return parsed.toLocaleString(language === 'en' ? 'en-US' : 'zh-CN', {
    maximumFractionDigits: digits,
  });
};
