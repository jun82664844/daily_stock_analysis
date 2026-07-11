import { useEffect, useMemo, useState } from 'react';
import { Bar, BarChart, CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { BarChart3, RefreshCw } from 'lucide-react';
import { stocksApi, type StockHistoryPoint, type StockHistoryResponse } from '../../api/stocks';

type Language = 'zh' | 'en';
type RangeDays = 30 | 90 | 180 | 365;

interface FreeKlineResearchV101Props {
  stockCode: string;
  stockName?: string | null;
  language: Language;
  initialTrend?: {
    window?: number;
    source: string;
    points: Array<{ date?: string | null; close: number; volume?: number | null }>;
  } | null;
}

interface ChartPoint extends StockHistoryPoint {
  dateLabel: string;
  ma5: number | null;
  ma20: number | null;
}

const RANGE_OPTIONS: RangeDays[] = [30, 90, 180, 365];

const isFiniteNumber = (value: unknown): value is number =>
  typeof value === 'number' && Number.isFinite(value);

const movingAverage = (values: number[], index: number, window: number): number | null => {
  if (index + 1 < window) return null;
  const slice = values.slice(index + 1 - window, index + 1);
  return slice.reduce((sum, value) => sum + value, 0) / window;
};

const formatNumber = (value: number | null | undefined, digits = 2): string =>
  isFiniteNumber(value)
    ? value.toLocaleString(undefined, { maximumFractionDigits: digits })
    : '-';

const formatPercent = (value: number | null | undefined): string => {
  if (!isFiniteNumber(value)) return '-';
  return `${value > 0 ? '+' : ''}${value.toFixed(2)}%`;
};

const formatCompact = (value: number | null | undefined): string =>
  isFiniteNumber(value)
    ? new Intl.NumberFormat('en-US', { notation: 'compact', maximumFractionDigits: 1 }).format(value)
    : '-';

const sourceLabel = (source: string | null | undefined, language: Language): string => {
  const normalized = String(source || '').toLowerCase();
  if (normalized.startsWith('snapshot_')) return language === 'en' ? 'Quick snapshot close series' : '快速快照收盘线';
  if (normalized.includes('yahoo')) return language === 'en' ? 'Yahoo public history' : 'Yahoo 公共历史行情';
  if (normalized.includes('akshare')) return language === 'en' ? 'AkShare public history' : 'AkShare 公共历史行情';
  if (normalized.includes('efinance')) return language === 'en' ? 'Efinance public history' : 'Efinance 公共历史行情';
  return language === 'en' ? 'Public/local history source' : '公开/本地历史行情源';
};

const buildKlineResearchModel = (response: StockHistoryResponse, limit: number) => {
  const rows = (response.data || [])
    .filter((row) => [row.open, row.high, row.low, row.close].every(isFiniteNumber))
    .sort((a, b) => a.date.localeCompare(b.date))
    .slice(-limit);
  const closes = rows.map((row) => row.close);
  const chartData: ChartPoint[] = rows.map((row, index) => ({
    ...row,
    dateLabel: row.date.slice(5),
    ma5: movingAverage(closes, index, 5),
    ma20: movingAverage(closes, index, 20),
  }));
  const first = chartData[0];
  const last = chartData.at(-1);
  let peak = first?.close ?? 0;
  let maxDrawdown = 0;
  closes.forEach((close) => {
    peak = Math.max(peak, close);
    if (peak > 0) maxDrawdown = Math.min(maxDrawdown, ((close / peak) - 1) * 100);
  });
  const recentVolumes = chartData.slice(-5).map((row) => row.volume).filter(isFiniteNumber);
  const averageVolume5 = recentVolumes.length
    ? recentVolumes.reduce((sum, value) => sum + value, 0) / recentVolumes.length
    : null;
  const lastVolume = last?.volume;
  const volumeRatio = isFiniteNumber(lastVolume) && isFiniteNumber(averageVolume5) && averageVolume5 > 0
    ? lastVolume / averageVolume5
    : null;
  const periodReturn = first && last && first.close !== 0
    ? ((last.close / first.close) - 1) * 100
    : null;
  const high = chartData.length ? Math.max(...chartData.map((row) => row.high)) : null;
  const low = chartData.length ? Math.min(...chartData.map((row) => row.low)) : null;
  const latestMa20 = last?.ma20 ?? null;

  return {
    chartData,
    first,
    last,
    periodReturn,
    maxDrawdown,
    high,
    low,
    averageVolume5,
    volumeRatio,
    latestMa20,
  };
};

export function FreeKlineResearchV101({ stockCode, stockName, language, initialTrend }: FreeKlineResearchV101Props) {
  const [days, setDays] = useState<RangeDays>(90);
  const initialResponse = useMemo<StockHistoryResponse | null>(() => {
    const points = (initialTrend?.points || []).filter((point) => isFiniteNumber(point.close));
    if (points.length < 2) return null;
    return {
      stockCode,
      stockName,
      period: 'daily',
      source: `snapshot_${initialTrend?.source || 'history'}`,
      data: points.map((point) => ({
        date: String(point.date || ''),
        open: point.close,
        high: point.close,
        low: point.close,
        close: point.close,
        volume: point.volume ?? null,
        amount: null,
        changePercent: null,
      })),
    };
  }, [initialTrend, stockCode, stockName]);
  const requestKey = `${stockCode}:${days}`;
  const [fetchState, setFetchState] = useState<{
    key: string;
    response: StockHistoryResponse | null;
    failed: boolean;
  }>({ key: '', response: null, failed: false });

  useEffect(() => {
    let active = true;
    stocksApi.history(stockCode, days)
      .then((value) => {
        if (!active) return;
        if ((value.data || []).length < 2 && initialResponse) {
          setFetchState({ key: requestKey, response: initialResponse, failed: true });
          return;
        }
        setFetchState({ key: requestKey, response: value, failed: false });
      })
      .catch(() => {
        if (!active) return;
        setFetchState({ key: requestKey, response: initialResponse, failed: true });
      });
    return () => {
      active = false;
    };
  }, [days, initialResponse, requestKey, stockCode]);

  const loading = fetchState.key !== requestKey;
  const failed = fetchState.key === requestKey && fetchState.failed;
  const response = fetchState.key === requestKey
    ? (fetchState.response || initialResponse)
    : initialResponse;

  const model = useMemo(
    () => response ? buildKlineResearchModel(response, days) : null,
    [days, response],
  );
  const isEnglish = language === 'en';

  if (failed && !model) {
    return (
      <section data-testid="free-kline-research-error" className="mb-3 rounded-lg border border-warning/35 bg-warning/10 p-4">
        <div className="flex items-start gap-3">
          <RefreshCw className="mt-0.5 h-4 w-4 shrink-0 text-warning" aria-hidden="true" />
          <div>
            <h3 className="text-sm font-semibold text-foreground">
              {isEnglish ? 'Historical chart is temporarily unavailable' : '历史走势图暂时不可用'}
            </h3>
            <p className="mt-1 text-xs leading-relaxed text-secondary-text">
              {isEnglish
                ? 'The public history source timed out or returned no usable response. The quote result remains available; retry the range later.'
                : '公开历史行情源超时或未返回可用结果。当前行情仍可查看，可稍后重新选择区间。'}
            </p>
          </div>
        </div>
      </section>
    );
  }

  if (loading && !model) {
    return (
      <section data-testid="free-kline-research-loading" className="mb-3 min-h-[22rem] animate-pulse rounded-lg border border-primary/25 bg-primary/5 p-4">
        <div className="h-5 w-44 rounded bg-primary/15" />
        <div className="mt-4 h-64 rounded bg-background/35" />
      </section>
    );
  }

  if (!model || model.chartData.length < 2) {
    return (
      <section data-testid="free-kline-research-empty" className="mb-3 rounded-lg border border-subtle bg-background/35 p-4">
        <h3 className="text-sm font-semibold text-foreground">
          {isEnglish ? 'Not enough historical bars yet' : '历史 K 线数据暂不足'}
        </h3>
        <p className="mt-1 text-xs text-secondary-text">
          {isEnglish ? 'Keep the current quote and retry this evidence panel later.' : '当前行情仍然保留，可稍后重试这块走势图证据。'}
        </p>
      </section>
    );
  }

  const trendAbove = isFiniteNumber(model.latestMa20) && isFiniteNumber(model.last?.close)
    ? model.last.close >= model.latestMa20
    : null;
  const watchItems = [
    trendAbove === null
      ? (isEnglish ? 'Wait for enough bars to form MA20.' : '等待足够历史数据形成 MA20。')
      : trendAbove
        ? (isEnglish ? `Watch whether price holds MA20 ${formatNumber(model.latestMa20)}.` : `观察价格能否守住 MA20 ${formatNumber(model.latestMa20)}。`)
        : (isEnglish ? `Watch whether price reclaims MA20 ${formatNumber(model.latestMa20)}.` : `观察价格能否收复 MA20 ${formatNumber(model.latestMa20)}。`),
    isEnglish
      ? `Range resistance ${formatNumber(model.high)}; support reference ${formatNumber(model.low)}.`
      : `区间压力参考 ${formatNumber(model.high)}；支撑参考 ${formatNumber(model.low)}。`,
    isEnglish
      ? `Latest volume is ${isFiniteNumber(model.volumeRatio) ? model.volumeRatio.toFixed(2) : '-'}x the 5-day average.`
      : `最新成交量约为 5 日均量的 ${isFiniteNumber(model.volumeRatio) ? model.volumeRatio.toFixed(2) : '-'} 倍。`,
  ];
  const closeOnly = String(response?.source || '').startsWith('snapshot_');
  const displayName = isEnglish ? stockCode : (response?.stockName || stockName || stockCode);

  return (
    <section data-testid="free-kline-research-v101" className="mb-3 overflow-hidden rounded-lg border border-primary/30 bg-primary/5 p-3 sm:p-4">
      <div className="flex min-w-0 flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
        <div className="min-w-0">
          <div className="flex items-center gap-2 text-xs font-medium text-primary">
            <BarChart3 className="h-4 w-4" aria-hidden="true" />
            {isEnglish ? 'Free price evidence' : '免费价格证据'}
          </div>
          <h3 className="mt-1 text-base font-semibold text-foreground">
            {isEnglish ? 'Free historical trend research' : '免费历史走势研究台'}
          </h3>
          <p className="mt-1 text-xs leading-relaxed text-secondary-text">
            {closeOnly
              ? (isEnglish
                ? `${displayName} close-price snapshot is visible now while full OHLCV history refreshes.`
                : `${displayName} 的收盘价快照已即时显示，完整 OHLCV 历史正在后台补齐。`)
              : (isEnglish
                ? `${displayName} actual daily history with price, MA5, MA20 and volume. No AI used.`
                : `${displayName} 的真实日线历史，包含价格、MA5、MA20 和成交量。未使用 AI。`)}
          </p>
          {loading || failed ? (
            <div className={`mt-1 text-[11px] ${failed ? 'text-warning' : 'text-primary'}`}>
              {failed
                ? (isEnglish ? 'Full history degraded; keeping the quick snapshot evidence.' : '完整历史源已降级，继续保留快速快照证据。')
                : (isEnglish ? 'Refreshing full history' : '完整历史更新中')}
            </div>
          ) : null}
        </div>
        <div className="flex min-w-0 flex-wrap gap-1.5" aria-label={isEnglish ? 'History range' : '历史区间'}>
          {RANGE_OPTIONS.map((option) => (
            <button
              key={option}
              type="button"
              aria-pressed={days === option}
              onClick={() => setDays(option)}
              className={`h-8 rounded-md border px-2.5 text-xs font-medium transition-colors ${days === option ? 'border-primary/60 bg-primary/15 text-primary' : 'border-subtle bg-background/35 text-secondary-text hover:text-foreground'}`}
            >
              {option}{isEnglish ? 'D' : '日'}
            </button>
          ))}
        </div>
      </div>

      <div className="mt-3 grid grid-cols-2 gap-2 lg:grid-cols-5">
        {[
          [isEnglish ? 'Range return' : '区间涨跌', formatPercent(model.periodReturn)],
          [isEnglish ? (closeOnly ? 'Close high' : 'Range high') : (closeOnly ? '收盘高点' : '区间高点'), formatNumber(model.high)],
          [isEnglish ? (closeOnly ? 'Close low' : 'Range low') : (closeOnly ? '收盘低点' : '区间低点'), formatNumber(model.low)],
          [isEnglish ? 'Max drawdown' : '最大回撤', formatPercent(model.maxDrawdown)],
          ['MA20', formatNumber(model.latestMa20)],
        ].map(([label, value]) => (
          <div key={label} className="min-w-0 rounded-md border border-subtle/75 bg-background/35 p-2.5">
            <div className="truncate text-[11px] text-secondary-text">{label}</div>
            <div className="mt-1 truncate text-sm font-semibold text-foreground">{value}</div>
          </div>
        ))}
      </div>

      <div className="mt-3 grid min-w-0 gap-3 xl:grid-cols-[minmax(0,2fr)_minmax(16rem,1fr)]">
        <div className="min-w-0 rounded-md border border-subtle/75 bg-background/30 p-2">
          <div className="h-64 w-full min-w-0" data-testid="free-kline-price-chart">
            <ResponsiveContainer width="100%" height="100%" minWidth={0}>
              <LineChart data={model.chartData} margin={{ top: 8, right: 10, left: 0, bottom: 0 }}>
                <CartesianGrid stroke="rgba(148, 163, 184, 0.12)" vertical={false} />
                <XAxis dataKey="dateLabel" minTickGap={28} tick={{ fill: '#94a3b8', fontSize: 10 }} />
                <YAxis domain={['auto', 'auto']} width={52} tick={{ fill: '#94a3b8', fontSize: 10 }} />
                <Tooltip />
                <Legend wrapperStyle={{ fontSize: 11 }} />
                <Line type="monotone" dataKey="close" name={isEnglish ? 'Close' : '收盘价'} stroke="#22d3ee" dot={false} strokeWidth={2} />
                <Line type="monotone" dataKey="ma5" name="MA5" stroke="#f59e0b" dot={false} strokeWidth={1.4} connectNulls />
                <Line type="monotone" dataKey="ma20" name="MA20" stroke="#a78bfa" dot={false} strokeWidth={1.4} connectNulls />
              </LineChart>
            </ResponsiveContainer>
          </div>
          <div className="mt-2 h-24 w-full min-w-0" data-testid="free-kline-volume-chart">
            <ResponsiveContainer width="100%" height="100%" minWidth={0}>
              <BarChart data={model.chartData} margin={{ top: 2, right: 10, left: 0, bottom: 0 }}>
                <XAxis dataKey="dateLabel" hide />
                <YAxis tickFormatter={formatCompact} width={52} tick={{ fill: '#94a3b8', fontSize: 10 }} />
                <Tooltip formatter={(value) => formatCompact(typeof value === 'number' ? value : Number(value))} />
                <Bar dataKey="volume" name={isEnglish ? 'Volume' : '成交量'} fill="#0ea5e9" opacity={0.55} radius={[2, 2, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="min-w-0 rounded-md border border-subtle/75 bg-background/30 p-3">
          <h4 className="text-sm font-semibold text-foreground">
            {isEnglish ? 'What to verify next' : '下一步重点验证'}
          </h4>
          <div className="mt-2 space-y-2">
            {watchItems.map((item) => (
              <p key={item} className="rounded-md border border-subtle/70 bg-surface/30 px-2.5 py-2 text-xs leading-relaxed text-secondary-text">
                {item}
              </p>
            ))}
          </div>
          <div className="mt-3 flex min-w-0 flex-wrap gap-1.5 text-[11px] text-secondary-text">
            <span className="rounded-md border border-subtle px-2 py-1">{sourceLabel(response?.source, language)}</span>
            <span className="rounded-md border border-primary/30 bg-primary/10 px-2 py-1 text-primary">
              {isEnglish ? 'No AI used' : '未使用 AI'}
            </span>
            <span className="rounded-md border border-subtle px-2 py-1">
              {model.chartData.length} {isEnglish ? 'bars' : '根日线'}
            </span>
          </div>
        </div>
      </div>

      <p className="mt-3 text-[11px] leading-relaxed text-muted-text">
        {isEnglish
          ? 'Historical public data may be delayed or incomplete. This is information analysis only, not investment advice.'
          : '公开历史行情可能延迟或不完整。仅供信息分析，不构成投资建议。'}
      </p>
    </section>
  );
}
