import { ArrowUpRight, Database, RefreshCw, X } from 'lucide-react';
import { Line, LineChart, Tooltip, XAxis, YAxis } from 'recharts';
import type { MarketSecurityItem, SymbolWorkspaceResponse } from '../../api/marketWorkspace';
import {
  formatMarketNumber,
  formatMarketTimestamp,
  formatSourceLabel,
  formatSourceStatus,
} from '../market-workspace/marketWorkspaceFormat';

type Props = {
  language: 'zh' | 'en';
  item: MarketSecurityItem;
  detail: SymbolWorkspaceResponse | null;
  loading: boolean;
  error: string;
  onRetry: () => void;
  onClose: () => void;
  onOpenFull: (symbol: string) => void;
};

type Metric = {
  label: string;
  value: string;
  tone?: string;
};

const numberFrom = (record: Record<string, unknown> | null | undefined, ...keys: string[]) => {
  for (const key of keys) {
    const value = record?.[key];
    if (value !== null && value !== undefined && value !== '' && Number.isFinite(Number(value))) {
      return Number(value);
    }
  }
  return null;
};

const stringFrom = (record: Record<string, unknown> | null | undefined, ...keys: string[]) => {
  for (const key of keys) {
    const value = String(record?.[key] ?? '').trim();
    if (value) return value;
  }
  return '';
};

const percent = (value: number | null, language: 'zh' | 'en') => {
  if (value == null) return language === 'en' ? 'Unavailable' : '暂不可用';
  return `${value > 0 ? '+' : ''}${value.toLocaleString(language === 'en' ? 'en-US' : 'zh-CN', { maximumFractionDigits: 2 })}%`;
};

const compactNumber = (value: number | null, language: 'zh' | 'en') => {
  if (value == null) return language === 'en' ? 'Unavailable' : '暂不可用';
  const abs = Math.abs(value);
  if (language === 'zh') {
    if (abs >= 1_0000_0000) return `${(value / 1_0000_0000).toLocaleString('zh-CN', { maximumFractionDigits: 2 })}亿`;
    if (abs >= 1_0000) return `${(value / 1_0000).toLocaleString('zh-CN', { maximumFractionDigits: 1 })}万`;
    return value.toLocaleString('zh-CN', { maximumFractionDigits: 2 });
  }
  if (abs >= 1_000_000_000_000) return `${(value / 1_000_000_000_000).toLocaleString('en-US', { maximumFractionDigits: 2 })}T`;
  if (abs >= 1_000_000_000) return `${(value / 1_000_000_000).toLocaleString('en-US', { maximumFractionDigits: 2 })}B`;
  if (abs >= 1_000_000) return `${(value / 1_000_000).toLocaleString('en-US', { maximumFractionDigits: 1 })}M`;
  return value.toLocaleString('en-US', { maximumFractionDigits: 2 });
};

function positionSummary(
  currentPrice: number | null,
  ma20: number | null,
  volumeChange: number | null,
  language: 'zh' | 'en',
) {
  if (currentPrice == null || ma20 == null || ma20 === 0) {
    return language === 'en'
      ? 'Moving-average context is incomplete; no future direction is inferred.'
      : '均线背景数据不完整，不据此推断未来方向。';
  }
  const distance = ((currentPrice - ma20) / ma20) * 100;
  const priceText = language === 'en'
    ? `The latest price is ${Math.abs(distance).toFixed(2)}% ${distance >= 0 ? 'above' : 'below'} MA20.`
    : `最新价较 MA20 ${distance >= 0 ? '高' : '低'} ${Math.abs(distance).toFixed(2)}%。`;
  const volumeText = volumeChange == null
    ? (language === 'en' ? ' Volume comparison is unavailable.' : ' 成交量对比暂不可用。')
    : (language === 'en'
      ? ` Volume is ${Math.abs(volumeChange).toFixed(2)}% ${volumeChange >= 0 ? 'above' : 'below'} its five-day average.`
      : ` 成交量较五日均量${volumeChange >= 0 ? '增加' : '减少'} ${Math.abs(volumeChange).toFixed(2)}%。`);
  return `${priceText}${volumeText} ${language === 'en' ? 'This is an objective position description, not a forecast.' : '这是客观位置描述，不是方向预测。'}`;
}

export default function PublicMarketStockPreviewV121({
  language,
  item,
  detail,
  loading,
  error,
  onRetry,
  onClose,
  onOpenFull,
}: Props) {
  const en = language === 'en';
  const unavailable = en ? 'Unavailable' : '暂不可用';

  if (loading) {
    return (
      <section className="border-y border-primary/30 bg-primary/5 px-4 py-5" data-testid="public-market-stock-preview-loading-v121" aria-label={en ? `${item.symbol} data preview` : `${item.symbol} 数据预览`}>
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0">
            <p className="text-xs font-medium text-primary">{en ? 'Ranking data available now' : '榜单数据已就绪'}</p>
            <h4 className="mt-1 truncate text-lg font-semibold text-foreground">{item.name || item.symbol} {en ? 'data preview' : '数据详情'}</h4>
            <p className="mt-1 text-xs text-secondary-text">{item.symbol} · {item.currency ?? '-'}</p>
          </div>
          <div className="flex items-center gap-2">
            <span className="rounded-md border border-primary/35 px-2 py-1 text-xs text-primary">{en ? 'No AI used' : '未使用 AI'}</span>
            <button type="button" onClick={onClose} className="inline-flex h-9 w-9 items-center justify-center rounded-md border border-border text-secondary-text hover:text-foreground" aria-label={en ? 'Close data preview' : '关闭数据详情'}>
              <X className="h-4 w-4" aria-hidden="true" />
            </button>
          </div>
        </div>
        <div className="mt-4 grid grid-cols-3 gap-px overflow-hidden rounded-md border border-border/70 bg-border/70">
          <div className="min-w-0 bg-surface px-3 py-2">
            <span className="block text-[11px] text-secondary-text">{en ? 'Latest' : '最新价'}</span>
            <strong className="mt-1 block truncate text-sm text-foreground">{formatMarketNumber(item.currentPrice, language)}</strong>
          </div>
          <div className="min-w-0 bg-surface px-3 py-2">
            <span className="block text-[11px] text-secondary-text">{en ? 'Change' : '涨跌幅'}</span>
            <strong className="mt-1 block truncate text-sm text-foreground">{percent(item.changePercent ?? null, language)}</strong>
          </div>
          <div className="min-w-0 bg-surface px-3 py-2">
            <span className="block text-[11px] text-secondary-text">{en ? 'Turnover' : '成交额'}</span>
            <strong className="mt-1 block truncate text-sm text-foreground">{compactNumber(item.turnover ?? null, language)}</strong>
          </div>
        </div>
        <p className="mt-3 flex items-center gap-2 text-sm text-secondary-text" role="status">
          <RefreshCw className="h-4 w-4 animate-spin" aria-hidden="true" />
          {en ? 'Adding moving averages, history and company profile...' : '正在补充均线、历史曲线和公司资料...'}
        </p>
        <p className="mt-2 text-xs text-secondary-text">
          {en ? 'Ranking source' : '榜单来源'}：{formatSourceLabel(item.sourceState.source, language)} · {formatSourceStatus(item.sourceState.status, language)} · {formatMarketTimestamp(item.sourceState.observedAt ?? item.sourceState.fetchedAt, language)}
        </p>
      </section>
    );
  }

  if (error || !detail) {
    return (
      <section className="border-y border-danger/35 bg-danger/5 px-4 py-5" aria-label={en ? `${item.symbol} data preview` : `${item.symbol} 数据预览`}>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h4 className="font-semibold text-foreground">{en ? 'Public data temporarily unavailable' : '公开数据暂时不可用'}</h4>
            <p className="mt-1 text-sm text-secondary-text">
              {en ? 'The ranking remains available. Retry the detail request without using AI quota.' : '榜单仍可继续使用；可重新请求详情，且不会消耗 AI 额度。'}
            </p>
          </div>
          <div className="flex items-center gap-2">
            <button type="button" onClick={onRetry} className="inline-flex h-9 items-center gap-2 rounded-md border border-border px-3 text-sm text-foreground hover:border-primary/60 hover:text-primary" aria-label={en ? 'Reload data preview' : '重新加载数据详情'}>
              <RefreshCw className="h-4 w-4" aria-hidden="true" />
              {en ? 'Retry' : '重试'}
            </button>
            <button type="button" onClick={onClose} className="inline-flex h-9 w-9 items-center justify-center rounded-md border border-border text-secondary-text hover:text-foreground" aria-label={en ? 'Close data preview' : '关闭数据详情'}>
              <X className="h-4 w-4" aria-hidden="true" />
            </button>
          </div>
        </div>
      </section>
    );
  }

  const quote = detail.quote ?? {};
  const indicators = detail.indicators ?? {};
  const profile = detail.profile ?? {};
  const currentPrice = item.currentPrice ?? numberFrom(quote, 'currentPrice', 'current_price');
  const changePercent = item.changePercent ?? numberFrom(quote, 'changePercent', 'change_percent');
  const headlineAsOf = item.sourceState.observedAt ?? item.sourceState.fetchedAt ?? detail.asOf;
  const ma20 = numberFrom(indicators, 'ma20');
  const volumeChange = numberFrom(indicators, 'volumeChangeVsMa5', 'volume_change_vs_ma5');
  const quoteMetrics: Metric[] = [
    { label: en ? 'Open' : '开盘', value: formatMarketNumber(numberFrom(quote, 'open'), language) },
    { label: en ? 'High' : '最高', value: formatMarketNumber(numberFrom(quote, 'high'), language) },
    { label: en ? 'Low' : '最低', value: formatMarketNumber(numberFrom(quote, 'low'), language) },
    { label: en ? 'Previous close' : '昨收', value: formatMarketNumber(numberFrom(quote, 'prevClose', 'prev_close'), language) },
    { label: en ? 'Volume' : '成交量', value: compactNumber(numberFrom(quote, 'volume'), language) },
    { label: en ? 'Turnover' : '成交额', value: compactNumber(numberFrom(quote, 'amount') ?? item.turnover ?? null, language) },
  ].map((metric) => ({ ...metric, value: metric.value === '-' ? unavailable : metric.value }));
  const trendMetrics: Metric[] = [
    { label: 'MA5', value: formatMarketNumber(numberFrom(indicators, 'ma5'), language) },
    { label: 'MA10', value: formatMarketNumber(numberFrom(indicators, 'ma10'), language) },
    { label: 'MA20', value: formatMarketNumber(ma20, language) },
    { label: en ? '5-day change' : '5日变化', value: percent(numberFrom(indicators, 'priceChange5d', 'price_change_5d'), language) },
    { label: en ? '20-day change' : '20日变化', value: percent(numberFrom(indicators, 'priceChange20d', 'price_change_20d'), language) },
    { label: en ? 'Volume vs MA5' : '量能对比', value: percent(volumeChange, language) },
  ].map((metric) => ({ ...metric, value: metric.value === '-' ? unavailable : metric.value }));
  const history = (detail.history ?? []).map((point) => ({
    date: stringFrom(point, 'date', 'time', 'datetime'),
    close: numberFrom(point, 'close', 'price'),
  })).filter((point): point is { date: string; close: number } => Boolean(point.date) && point.close != null);
  const sector = stringFrom(profile, 'sector');
  const industry = stringFrom(profile, 'industry');
  const profileLabel = [sector, industry].filter(Boolean).join(' / ') || unavailable;
  const marketCap = compactNumber(numberFrom(profile, 'marketCap', 'market_cap'), language);
  const detailSource = detail.sources?.[0];
  const rankingSource = item.sourceState;

  return (
    <section
      className="border-y border-primary/35 bg-primary/5 px-4 py-5"
      data-testid="public-market-stock-preview-v121"
      aria-label={en ? `${item.symbol} data preview` : `${item.symbol} 数据预览`}
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="flex items-center gap-1.5 text-xs font-medium text-primary">
            <Database className="h-3.5 w-3.5" aria-hidden="true" />
            {en ? 'Public data preview' : '公开数据预览'}
          </p>
          <h4 className="mt-1 truncate text-lg font-semibold text-foreground">{detail.name || item.name || item.symbol} {en ? 'data preview' : '数据详情'}</h4>
          <p className="mt-1 text-xs text-secondary-text">{detail.symbol} · {detail.currency ?? item.currency ?? '-'}</p>
        </div>
        <div className="flex items-center gap-2">
          <span className="rounded-md border border-primary/35 px-2 py-1 text-xs text-primary">{en ? 'No AI used' : '未使用 AI'}</span>
          <button type="button" onClick={onClose} className="inline-flex h-9 w-9 items-center justify-center rounded-md border border-border text-secondary-text hover:text-foreground" aria-label={en ? 'Close data preview' : '关闭数据详情'}>
            <X className="h-4 w-4" aria-hidden="true" />
          </button>
        </div>
      </div>

      <div className="mt-4 grid gap-4 xl:grid-cols-[minmax(0,1.15fr)_minmax(18rem,.85fr)]">
        <div className="min-w-0">
          <div className="flex flex-wrap items-end gap-x-4 gap-y-1 border-b border-border/70 pb-3">
            <strong className="text-2xl text-foreground">{formatMarketNumber(currentPrice, language)}</strong>
            <span className={changePercent == null ? 'text-secondary-text' : changePercent >= 0 ? 'text-success' : 'text-danger'}>{percent(changePercent, language)}</span>
            <span className="text-xs text-secondary-text">{en ? 'As of' : '数据时间'} {formatMarketTimestamp(headlineAsOf, language)}</span>
          </div>
          <div className="mt-3 grid grid-cols-2 gap-px overflow-hidden rounded-md border border-border/70 bg-border/70 sm:grid-cols-3">
            {quoteMetrics.map((metric) => (
              <div key={metric.label} className="min-w-0 bg-surface px-3 py-2">
                <span className="block text-[11px] text-secondary-text">{metric.label}</span>
                <strong className="mt-1 block truncate text-sm text-foreground">{metric.value}</strong>
              </div>
            ))}
          </div>
          <div className="mt-3 grid grid-cols-2 gap-px overflow-hidden rounded-md border border-border/70 bg-border/70 sm:grid-cols-3">
            {trendMetrics.map((metric) => (
              <div key={metric.label} className="min-w-0 bg-surface px-3 py-2">
                <span className="block text-[11px] text-secondary-text">{metric.label}</span>
                <strong className="mt-1 block truncate text-sm text-foreground">{metric.value}</strong>
              </div>
            ))}
          </div>
        </div>

        <div className="min-w-0 border-t border-border/70 pt-4 xl:border-l xl:border-t-0 xl:pl-4 xl:pt-0">
          <div className="h-40 w-full" aria-label={en ? `${item.symbol} recent close chart` : `${item.symbol} 近期收盘曲线`}>
            {history.length ? (
              <LineChart responsive data={history} style={{ width: '100%', height: '100%' }} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
                <XAxis dataKey="date" hide />
                <YAxis domain={['auto', 'auto']} width={52} tick={{ fontSize: 10 }} />
                <Tooltip />
                <Line type="monotone" dataKey="close" stroke="hsl(var(--primary))" strokeWidth={2} dot={false} />
              </LineChart>
            ) : (
              <p className="flex h-full items-center justify-center text-sm text-secondary-text">{en ? 'History unavailable' : '历史数据暂不可用'}</p>
            )}
          </div>
          <div className="mt-3 grid grid-cols-2 gap-3 border-t border-border/70 pt-3 text-sm">
            <div className="min-w-0">
              <span className="block text-xs text-secondary-text">{en ? 'Sector / industry' : '板块 / 行业'}</span>
              <strong className="mt-1 block break-words text-foreground">{profileLabel}</strong>
            </div>
            <div className="min-w-0">
              <span className="block text-xs text-secondary-text">{en ? 'Market cap' : '总市值'}</span>
              <strong className="mt-1 block truncate text-foreground">{marketCap}</strong>
            </div>
          </div>
        </div>
      </div>

      <div className="mt-4 border-y border-border/70 py-3">
        <h5 className="text-sm font-semibold text-foreground">{en ? 'Objective data position' : '客观数据位置'}</h5>
        <p className="mt-1 text-sm leading-6 text-secondary-text">{positionSummary(currentPrice, ma20, volumeChange, language)}</p>
      </div>

      <div className="mt-3 flex flex-wrap items-center justify-between gap-3">
        <div className="min-w-0 text-xs text-secondary-text">
          <p>
            {detailSource
              ? `${en ? 'Detail source' : '详情来源'}：${formatSourceLabel(detailSource.source, language)} · ${formatSourceStatus(detailSource.status, language)} · ${formatMarketTimestamp(detailSource.observedAt ?? detailSource.fetchedAt, language)}`
              : `${en ? 'Detail source' : '详情来源'}：${unavailable}`}
          </p>
          {(!detailSource || detailSource.status === 'unavailable') && rankingSource ? (
            <p className="mt-1">
              {en ? 'Ranking source' : '榜单来源'}：{formatSourceLabel(rankingSource.source, language)} · {formatSourceStatus(rankingSource.status, language)} · {formatMarketTimestamp(rankingSource.observedAt ?? rankingSource.fetchedAt, language)}
            </p>
          ) : null}
        </div>
        <button type="button" onClick={() => onOpenFull(item.symbol)} className="inline-flex h-9 items-center gap-2 rounded-md bg-primary px-3 text-sm font-semibold text-primary-foreground hover:brightness-105" aria-label={en ? 'Open full query' : '进入完整查询'}>
          {en ? 'Open full query' : '进入完整查询'}
          <ArrowUpRight className="h-4 w-4" aria-hidden="true" />
        </button>
      </div>
      <p className="mt-3 text-xs leading-5 text-secondary-text">
        {en
          ? 'Information and data only. No investment advice, target price or return forecast.'
          : '仅提供资讯和数据，不构成投资建议，不提供目标价或收益预测。'}
      </p>
    </section>
  );
}
