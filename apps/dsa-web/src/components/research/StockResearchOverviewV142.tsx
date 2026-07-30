import {
  BookOpenCheck,
  ChartCandlestick,
  ChevronDown,
  ChevronUp,
  ExternalLink,
  Landmark,
  LoaderCircle,
  Newspaper,
  RefreshCw,
  ShieldCheck,
  Users,
} from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import {
  stocksApi,
  type BasicStockSnapshot,
  type PublicStockResearchOverview,
} from '../../api/stocks';
import { Button } from '../common';

type Language = 'zh' | 'en';
type TabKey = 'overview' | 'financials' | 'peers' | 'events' | 'kline' | 'sources';

type Props = {
  snapshot: BasicStockSnapshot;
  language: Language;
  detailsExpanded: boolean;
  onToggleDetails: () => void;
};

const finite = (value: unknown): number | null => {
  if (value === null || value === undefined || value === '') return null;
  const numeric = Number(value);
  return Number.isFinite(numeric) ? numeric : null;
};

const safePublicUrl = (item: unknown): string | null => {
  if (!item || typeof item !== 'object' || !('url' in item)) return null;
  const value = (item as { url?: unknown }).url;
  return typeof value === 'string' && /^https?:\/\//i.test(value) ? value : null;
};

const pickIndicator = (snapshot: BasicStockSnapshot, ...keys: string[]): number | null => {
  for (const key of keys) {
    const value = finite(snapshot.indicators[key]);
    if (value !== null) return value;
  }
  return null;
};

const formatNumber = (value: unknown, digits = 2): string => {
  const numeric = finite(value);
  if (numeric === null) return '-';
  return new Intl.NumberFormat('en-US', {
    maximumFractionDigits: digits,
    minimumFractionDigits: 0,
  }).format(numeric);
};

const formatCompact = (value: unknown, language: Language): string => {
  const numeric = finite(value);
  if (numeric === null) return '-';
  return new Intl.NumberFormat(language === 'en' ? 'en-US' : 'zh-CN', {
    notation: 'compact',
    maximumFractionDigits: 2,
  }).format(numeric);
};

const formatPercent = (value: unknown): string => {
  const numeric = finite(value);
  if (numeric === null) return '-';
  return `${numeric > 0 ? '+' : ''}${numeric.toFixed(2)}%`;
};

const sourceLabel = (source: string | null | undefined, language: Language): string => {
  const value = String(source || 'unavailable');
  const labels: Record<string, [string, string]> = {
    a_share_realtime: ['A股公开行情', 'A-share public quote'],
    us_realtime: ['美股公开行情', 'US public quote'],
    hk_realtime: ['港股公开行情', 'Hong Kong public quote'],
    crypto_realtime: ['加密货币公开行情', 'Crypto public quote'],
    yahoo_chart: ['Yahoo 行情', 'Yahoo quote'],
    yahoo_chart_reference: ['Yahoo 参照行情', 'Yahoo reference quote'],
    yahoo_chart_history: ['Yahoo 历史行情', 'Yahoo history'],
    yahoo_finance_search_feed: ['Yahoo 财经资讯', 'Yahoo Finance news'],
    yfinance_profile: ['Yahoo 公司资料', 'Yahoo company profile'],
    yfinance_public_financials: ['Yahoo 公共财务报表', 'Yahoo public financials'],
    sec_edgar_submissions: ['SEC EDGAR 文件', 'SEC EDGAR filings'],
    company_release: ['公司公告', 'Company release'],
    public_news: ['公开资讯源', 'Public news source'],
    no_ai_news_center_rules: ['本地资讯规则', 'Local news rules'],
    no_ai_route_rules: ['本地市场参照规则', 'Local market reference rules'],
    unavailable: ['暂不可用', 'Unavailable'],
  };
  return labels[value]?.[language === 'en' ? 1 : 0] || value;
};

const peerRoleLabel = (role: string | null | undefined, language: Language): string => {
  const value = String(role || 'unavailable');
  const labels: Record<string, [string, string]> = {
    'Broad market': ['大盘', 'Broad market'],
    'Index lens': ['指数参照', 'Index lens'],
    'Sector lens': ['行业参照', 'Sector lens'],
    unavailable: ['暂不可用', 'Unavailable'],
  };
  return labels[value]?.[language === 'en' ? 1 : 0] || value;
};

const profileContextLabel = (value: string): string => {
  const labels: Record<string, string> = {
    Technology: '科技',
    'Consumer Electronics': '消费电子',
    'Technology / Consumer Electronics': '科技 / 消费电子',
  };
  return labels[value] || value;
};

const eventTitleLabel = (
  title: string,
  source: string | null | undefined,
  language: Language,
): string => {
  if (language === 'en') return title;
  const labels: Record<string, string> = {
    'Financial snapshot lane': '财务快照通道',
    'Sector and peer lane': '板块与同业通道',
  };
  if (labels[title]) return labels[title];
  if (source === 'sec_edgar_submissions') return title.replace(' - ', ' · ');
  return title;
};

const eventSummaryLabel = (
  summary: string,
  source: string | null | undefined,
  language: Language,
): string => {
  if (language === 'en') return summary;
  if (source === 'yfinance_profile') {
    return summary
      .replace(/^Market cap /, '总市值 ')
      .replace(/; PE /g, '；市盈率 ')
      .replace(/; PB /g, '；市净率 ')
      .replace(/; dividend yield /gi, '；股息率 ')
      .replace(/; revenue /gi, '；营收 ')
      .replace(/; net profit /gi, '；净利润 ');
  }
  if (source === 'sec_edgar_submissions') {
    const match = summary.match(/^Filed ([^;]+); report date ([^.]+)\.?$/i);
    if (match) return `提交日期 ${match[1]}；报告期 ${match[2]}。`;
  }
  if (source === 'no_ai_news_center_rules') {
    const context = summary.match(/^Context is ([^.]+)\./i)?.[1];
    const signal = summary.match(/volume-price signal is ([^.]+)\./i)?.[1];
    const signalLabels: Record<string, string> = {
      'price above trend volume soft': '价格位于趋势上方、量能偏弱',
      'price volume confirmed': '价格与量能相互确认',
    };
    if (context) {
      const localizedSignal = signal ? signalLabels[signal] || '量价状态已记录' : '量价状态暂不可用';
      return `公司背景为 ${profileContextLabel(context)}；当前${localizedSignal}。请结合大盘和行业参照核对，不要孤立解读。`;
    }
  }
  return summary;
};

const statusMessage = (message: string, language: Language): string => {
  if (!message || language === 'en') return message;
  const normalized = message.trim().toLowerCase();
  const labels: Record<string, string> = {
    'market data ready': '当前市场数据已就绪',
    'quote is stale': '当前行情已过期，请核对更新时间',
    'quote data is stale': '当前行情已过期，请核对更新时间',
    'public search unavailable': '公共资讯搜索暂不可用',
  };
  if (labels[normalized]) return labels[normalized];
  return /^[\x00-\x7f]+$/.test(message)
    ? '来源状态已记录，请在“来源与边界”中核对。'
    : message;
};

const freshnessLabel = (freshness: string | null | undefined, language: Language): string => {
  const value = String(freshness || 'unavailable').toLowerCase();
  const labels: Record<string, [string, string]> = {
    fresh: ['新鲜', 'Fresh'],
    cached: ['缓存', 'Cached'],
    stale: ['过期', 'Stale'],
    unavailable: ['不可用', 'Unavailable'],
  };
  return labels[value]?.[language === 'en' ? 1 : 0] || value;
};

const positionLabel = (
  position: PublicStockResearchOverview['valuationPosition'],
  language: Language,
): string => {
  const value = position?.position || 'unavailable';
  const labels: Record<string, [string, string]> = {
    lower_range: ['样本区间较低位置', 'Lower observed range'],
    middle_range: ['样本区间中部', 'Middle observed range'],
    upper_range: ['样本区间较高位置', 'Upper observed range'],
    unavailable: ['样本不足', 'Insufficient samples'],
  };
  return labels[value]?.[language === 'en' ? 1 : 0] || value;
};

const buildLinePoints = (snapshot: BasicStockSnapshot): string => {
  const closes = (snapshot.trend?.points || [])
    .map((point) => finite(point.close))
    .filter((value): value is number => value !== null);
  if (closes.length < 2) return '';
  const minimum = Math.min(...closes);
  const maximum = Math.max(...closes);
  const range = Math.max(maximum - minimum, 0.0001);
  return closes.map((value, index) => {
    const x = (index / Math.max(closes.length - 1, 1)) * 420;
    const y = 104 - ((value - minimum) / range) * 88;
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  }).join(' ');
};

export function StockResearchOverviewV142({
  snapshot,
  language,
  detailsExpanded,
  onToggleDetails,
}: Props) {
  const isEnglish = language === 'en';
  const [activeTab, setActiveTab] = useState<TabKey>('overview');
  const [research, setResearch] = useState<PublicStockResearchOverview | null>(null);
  const [financialLoading, setFinancialLoading] = useState(false);
  const [financialError, setFinancialError] = useState(false);
  const [financialAttempt, setFinancialAttempt] = useState(0);

  useEffect(() => {
    setActiveTab('overview');
    setResearch(null);
    setFinancialLoading(false);
    setFinancialError(false);
    setFinancialAttempt(0);
  }, [snapshot.stockCode]);

  useEffect(() => {
    if (activeTab !== 'financials' || research || financialError) {
      return;
    }
    let active = true;
    setFinancialLoading(true);
    void stocksApi.researchOverview(snapshot.stockCode)
      .then((payload) => {
        if (!active) return;
        setResearch(payload);
        setFinancialError(false);
      })
      .catch(() => {
        if (!active) return;
        setFinancialError(true);
      })
      .finally(() => {
        if (active) setFinancialLoading(false);
      });
    return () => {
      active = false;
    };
  }, [
    activeTab,
    financialAttempt,
    financialError,
    research,
    snapshot.stockCode,
  ]);

  const tabs = useMemo(() => ([
    { key: 'overview' as const, label: isEnglish ? 'Research overview' : '研究总览', icon: BookOpenCheck },
    { key: 'financials' as const, label: isEnglish ? 'Financial trends' : '财务趋势', icon: Landmark },
    { key: 'peers' as const, label: isEnglish ? 'Peer comparison' : '同业对比', icon: Users },
    { key: 'events' as const, label: isEnglish ? 'News and events' : '资讯事件', icon: Newspaper },
    { key: 'kline' as const, label: isEnglish ? 'K-line samples' : 'K线样本', icon: ChartCandlestick },
    { key: 'sources' as const, label: isEnglish ? 'Sources and boundaries' : '来源与边界', icon: ShieldCheck },
  ]), [isEnglish]);

  const peerRows = snapshot.intelligence?.peerComparison?.rows || [];
  const newsItems = snapshot.intelligence?.newsCenter?.items?.length
    ? snapshot.intelligence.newsCenter.items
    : snapshot.intelligence?.items || [];
  const trendPoints = snapshot.trend?.points || [];
  const linePoints = buildLinePoints(snapshot);
  const currentPrice = finite(snapshot.quote.currentPrice);
  const ma20 = pickIndicator(snapshot, 'ma20', 'MA20');
  const latestRevenue = finite(snapshot.profile?.revenue);
  const latestProfit = finite(snapshot.profile?.netProfit);
  const conflictCount = snapshot.canonicalData?.conflicts?.length || 0;
  const selectedSources = Object.entries(snapshot.canonicalData?.selectedSources || {});
  const firstWarning = snapshot.warnings?.[0]?.message || snapshot.degradation?.message || '';

  const factualSummary = currentPrice !== null && ma20 !== null
    ? (
        isEnglish
          ? `Latest price ${formatNumber(currentPrice)} is ${currentPrice >= ma20 ? 'above' : 'below'} MA20 ${formatNumber(ma20)}.`
          : `最新价 ${formatNumber(currentPrice)}，位于 MA20 ${formatNumber(ma20)} ${currentPrice >= ma20 ? '上方' : '下方'}。`
      )
    : (
        isEnglish
          ? 'Moving-average context is incomplete; use the available quote and source status first.'
          : '均线背景尚不完整，先查看可用行情和来源状态。'
      );

  const renderOverview = () => (
    <div role="tabpanel" aria-label={tabs[0].label} className="space-y-4">
      <div className="grid min-w-0 gap-px overflow-hidden rounded-lg border border-subtle bg-subtle md:grid-cols-4">
        {[
          {
            label: isEnglish ? 'Price / change' : '价格 / 涨跌',
            value: `${formatNumber(snapshot.quote.currentPrice)} / ${formatPercent(snapshot.quote.changePercent)}`,
            detail: snapshot.profile?.currency || snapshot.market.toUpperCase(),
          },
          {
            label: isEnglish ? 'MA5 / MA20' : 'MA5 / MA20',
            value: `${formatNumber(pickIndicator(snapshot, 'ma5', 'MA5'))} / ${formatNumber(ma20)}`,
            detail: isEnglish ? 'Observed moving averages' : '已观测均线',
          },
          {
            label: isEnglish ? 'Revenue / net income' : '营收 / 净利润',
            value: `${formatCompact(latestRevenue, language)} / ${formatCompact(latestProfit, language)}`,
            detail: sourceLabel(snapshot.profile?.source, language),
          },
          {
            label: isEnglish ? 'Data state' : '数据状态',
            value: freshnessLabel(snapshot.quote.freshness, language),
            detail: sourceLabel(snapshot.quote.source, language),
          },
        ].map((item) => (
          <div key={item.label} className="min-w-0 bg-background/70 px-3 py-3">
            <div className="text-[11px] text-secondary-text">{item.label}</div>
            <div className="mt-1 truncate text-base font-semibold text-foreground">{item.value}</div>
            <div className="mt-1 truncate text-[11px] text-muted-text">{item.detail}</div>
          </div>
        ))}
      </div>

      <div className="grid min-w-0 gap-4 lg:grid-cols-[1.35fr_0.65fr]">
        <div className="min-w-0 border-l-2 border-primary pl-3">
          <div className="text-xs font-semibold text-primary">
            {isEnglish ? 'What the current data shows' : '当前数据呈现的事实'}
          </div>
          <p className="mt-2 text-sm leading-6 text-foreground">{factualSummary}</p>
          <p className="mt-1 text-xs leading-5 text-secondary-text">
            {isEnglish
              ? `The visible series contains ${trendPoints.length} price samples. Peer and event lanes are separated below for independent verification.`
              : `当前可见序列包含 ${trendPoints.length} 个价格样本；同业和事件通道在独立标签中展示，便于分别核对。`}
          </p>
        </div>
        <div className="min-w-0 border-l border-subtle pl-3">
          <div className="text-xs font-semibold text-foreground">
            {isEnglish ? 'Completeness' : '资料完整度'}
          </div>
          <div className="mt-2 text-2xl font-semibold text-primary">
            {snapshot.intelligence?.signalScore?.score ?? (
              [
                currentPrice,
                ma20,
                latestRevenue,
                peerRows.length ? 1 : null,
                newsItems.length ? 1 : null,
              ].filter((value) => value !== null).length * 20
            )}/100
          </div>
          <p className="mt-1 text-xs leading-5 text-secondary-text">
            {firstWarning
              ? statusMessage(firstWarning, language)
              : (isEnglish ? 'No material source warning is reported.' : '当前未报告重要来源警示。')}
          </p>
        </div>
      </div>
    </div>
  );

  const renderFinancials = () => {
    if (financialLoading) {
      return (
        <div role="tabpanel" aria-label={tabs[1].label} className="flex min-h-56 items-center justify-center gap-2 text-sm text-secondary-text">
          <LoaderCircle className="h-4 w-4 animate-spin" aria-hidden="true" />
          {isEnglish ? 'Loading public annual financial facts...' : '正在加载公开年度财务数据...'}
        </div>
      );
    }
    if (financialError) {
      return (
        <div role="tabpanel" aria-label={tabs[1].label} className="min-h-48 border-l-2 border-danger pl-4">
          <h4 className="text-sm font-semibold text-foreground">
            {isEnglish ? 'Public financial data is temporarily unavailable.' : '公开财务数据暂时不可用。'}
          </h4>
          <p className="mt-2 text-xs leading-5 text-secondary-text">
            {isEnglish
              ? 'The quote and other research tabs remain available. No valuation conclusion is generated from missing data.'
              : '行情和其他研究标签仍可使用；数据缺失时不会生成估值结论。'}
          </p>
          <Button
            type="button"
            variant="secondary"
            size="sm"
            className="mt-3"
            onClick={() => {
              setFinancialError(false);
              setFinancialAttempt((value) => value + 1);
            }}
          >
            <RefreshCw className="h-4 w-4" aria-hidden="true" />
            {isEnglish ? 'Retry' : '重试'}
          </Button>
        </div>
      );
    }
    if (!research || research.status === 'unavailable' || research.status === 'not_applicable') {
      return (
        <div role="tabpanel" aria-label={tabs[1].label} className="min-h-48 border-l-2 border-subtle pl-4">
          <h4 className="text-sm font-semibold text-foreground">
            {isEnglish ? 'Financial trend is not available for this symbol.' : '该标的暂无可用财务趋势。'}
          </h4>
          <p className="mt-2 text-xs leading-5 text-secondary-text">
            {research?.warnings?.[0] || (isEnglish ? 'No annual statement sample was returned.' : '公开源未返回年度报表样本。')}
          </p>
        </div>
      );
    }

    const maximumRevenue = Math.max(
      ...research.financialYears.map((item) => finite(item.revenue) || 0),
      1,
    );
    return (
      <div role="tabpanel" aria-label={tabs[1].label} className="space-y-4">
        <div className="flex min-w-0 flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
          <div className="min-w-0">
            <h4 className="text-sm font-semibold text-foreground">
              {isEnglish ? 'Five-year financial trends' : '五年财务趋势'}
            </h4>
            <p className="mt-1 text-xs leading-5 text-secondary-text">
              {isEnglish
                ? 'Observed annual revenue, net income, diluted EPS, and operating cash flow where available.'
                : '展示公开源可取得的年度营收、净利润、摊薄每股收益和经营现金流。'}
            </p>
          </div>
          <span className="shrink-0 rounded-md border border-subtle px-2 py-1 text-[11px] text-secondary-text">
            {sourceLabel(research.source, language)}
          </span>
        </div>

        {research.warnings.length > 0 ? (
          <div
            role="status"
            className="border-l-2 border-warning/70 bg-warning/5 px-3 py-2 text-xs leading-5 text-secondary-text"
          >
            {isEnglish
              ? `The public source returned ${research.financialYears.length} fiscal-year samples; the five-year view is incomplete.`
              : research.warnings.join('；')}
          </div>
        ) : null}

        <div className="overflow-x-auto border-y border-subtle">
          <table className="w-full min-w-[46rem] text-left text-xs">
            <thead className="text-secondary-text">
              <tr>
                <th className="px-2 py-2 font-medium">{isEnglish ? 'Fiscal year' : '财年'}</th>
                <th className="px-2 py-2 font-medium">{isEnglish ? 'Revenue' : '营收'}</th>
                <th className="px-2 py-2 font-medium">{isEnglish ? 'Revenue change' : '营收变化'}</th>
                <th className="px-2 py-2 font-medium">{isEnglish ? 'Net income' : '净利润'}</th>
                <th className="px-2 py-2 font-medium">{isEnglish ? 'Net income change' : '净利润变化'}</th>
                <th className="px-2 py-2 font-medium">{isEnglish ? 'Diluted EPS' : '摊薄每股收益'}</th>
                <th className="px-2 py-2 font-medium">{isEnglish ? 'Observed P/E' : '历史市盈率样本'}</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-subtle">
              {research.financialYears.map((item) => (
                <tr key={item.periodEnd} className="text-foreground">
                  <td className="px-2 py-2 font-semibold">{item.fiscalYear}</td>
                  <td className="px-2 py-2">
                    <div>{formatCompact(item.revenue, language)}</div>
                    <div className="mt-1 h-1.5 w-24 overflow-hidden rounded bg-subtle">
                      <div
                        className="h-full bg-primary"
                        style={{ width: `${Math.max(3, ((finite(item.revenue) || 0) / maximumRevenue) * 100)}%` }}
                      />
                    </div>
                  </td>
                  <td className="px-2 py-2">{formatPercent(item.revenueGrowth)}</td>
                  <td className="px-2 py-2">{formatCompact(item.netIncome, language)}</td>
                  <td className="px-2 py-2">{formatPercent(item.netIncomeGrowth)}</td>
                  <td className="px-2 py-2">{formatNumber(item.dilutedEps)}</td>
                  <td className="px-2 py-2">{formatNumber(item.observedPe)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="grid min-w-0 gap-4 border-t border-subtle pt-4 lg:grid-cols-[0.7fr_1.3fr]">
          <div className="min-w-0">
            <div className="text-xs font-semibold text-primary">
              {isEnglish ? 'Historical P/E position' : '历史市盈率位置'}
            </div>
            <div className="mt-2 text-2xl font-semibold text-foreground">
              {research.valuationPosition?.percentile !== null && research.valuationPosition?.percentile !== undefined
                ? `${formatNumber(research.valuationPosition.percentile, 0)}%`
                : '-'}
            </div>
            <div className="mt-1 text-xs text-secondary-text">
              {positionLabel(research.valuationPosition, language)}
            </div>
          </div>
          <div className="min-w-0 text-xs leading-5 text-secondary-text">
            <div className="grid grid-cols-3 gap-2 text-foreground">
              <span>{isEnglish ? 'Low' : '最低'} {formatNumber(research.valuationPosition?.minimum)}</span>
              <span>{isEnglish ? 'Median' : '中位'} {formatNumber(research.valuationPosition?.median)}</span>
              <span>{isEnglish ? 'High' : '最高'} {formatNumber(research.valuationPosition?.maximum)}</span>
            </div>
            <p className="mt-2">
              {isEnglish
                ? 'Method: fiscal-year-end price / annual diluted EPS. This is an observed historical sample, not realtime or forecast valuation.'
                : '口径：财年末价格 / 当年摊薄每股收益。这里只是历史观测样本，不是实时估值、预测估值或目标估值。'}
            </p>
          </div>
        </div>
      </div>
    );
  };

  const renderPeers = () => (
    <div role="tabpanel" aria-label={tabs[2].label}>
      <div className="mb-3 text-xs leading-5 text-secondary-text">
        {isEnglish
          ? 'Compare observed price movement with broad-market or sector references. Missing peer quotes remain explicitly unavailable.'
          : '把当前涨跌与大盘或行业参照并列查看；同业行情缺失时明确显示不可用。'}
      </div>
      <div data-testid="research-overview-peer-table-v142" className="overflow-x-auto border-y border-subtle">
        <table className="w-full min-w-[42rem] text-left text-xs">
          <thead className="text-secondary-text">
            <tr>
              <th className="px-2 py-2 font-medium">{isEnglish ? 'Symbol' : '标的'}</th>
              <th className="px-2 py-2 font-medium">{isEnglish ? 'Role' : '参照角色'}</th>
              <th className="px-2 py-2 font-medium">{isEnglish ? 'Price' : '价格'}</th>
              <th className="px-2 py-2 font-medium">{isEnglish ? 'Change' : '涨跌'}</th>
              <th className="px-2 py-2 font-medium">{isEnglish ? 'Freshness' : '新鲜度'}</th>
              <th className="px-2 py-2 font-medium">{isEnglish ? 'Source' : '来源'}</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-subtle">
            <tr className="text-foreground">
              <td className="px-2 py-2">
                <div className="font-semibold">{snapshot.stockCode}</div>
                <div className="text-[11px] text-secondary-text">{snapshot.stockName}</div>
              </td>
              <td className="px-2 py-2">{isEnglish ? 'Current symbol' : '当前标的'}</td>
              <td className="px-2 py-2">{formatNumber(snapshot.quote.currentPrice)}</td>
              <td className="px-2 py-2">{formatPercent(snapshot.quote.changePercent)}</td>
              <td className="px-2 py-2">{freshnessLabel(snapshot.quote.freshness, language)}</td>
              <td className="px-2 py-2">{sourceLabel(snapshot.quote.source, language)}</td>
            </tr>
            {peerRows.map((row) => (
              <tr key={`${row.symbol}-${row.role}`} className="text-foreground">
                <td className="px-2 py-2">
                  <div className="font-semibold">{row.symbol}</div>
                  <div className="text-[11px] text-secondary-text">{row.label}</div>
                </td>
                <td className="px-2 py-2">{peerRoleLabel(row.role, language)}</td>
                <td className="px-2 py-2">{formatNumber(row.referenceQuote?.currentPrice ?? row.referenceQuote?.price)}</td>
                <td className="px-2 py-2">{formatPercent(row.referenceQuote?.changePercent)}</td>
                <td className="px-2 py-2">{freshnessLabel(row.referenceQuote?.freshness, language)}</td>
                <td className="px-2 py-2">{sourceLabel(row.referenceQuote?.source || row.source, language)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {peerRows.length === 0 ? (
        <p className="mt-3 text-xs text-secondary-text">
          {isEnglish ? 'No peer quote is available yet.' : '当前暂无可用同业行情参照。'}
        </p>
      ) : null}
    </div>
  );

  const renderEvents = () => (
    <div role="tabpanel" aria-label={tabs[3].label}>
      <div className="divide-y divide-subtle border-y border-subtle">
        {newsItems.map((item, index) => {
          const sourceUrl = safePublicUrl(item);
          return (
          <article key={`${item.category}-${item.title}-${index}`} className="grid min-w-0 gap-2 py-3 md:grid-cols-[1fr_auto]">
            <div className="min-w-0">
              <div className="flex min-w-0 flex-wrap items-center gap-2">
                <h4 className="min-w-0 font-semibold text-foreground">
                  {eventTitleLabel(item.title, item.source, language)}
                </h4>
                <span className="rounded-md border border-subtle px-1.5 py-0.5 text-[10px] text-secondary-text">
                  {sourceLabel(item.source, language)}
                </span>
              </div>
              <p className="mt-1 text-xs leading-5 text-secondary-text">
                {eventSummaryLabel(item.summary, item.source, language)}
              </p>
              <div className="mt-1 text-[11px] text-muted-text">
                {item.updatedAt || (isEnglish ? 'Update time unavailable' : '更新时间暂不可用')}
              </div>
            </div>
            {sourceUrl ? (
              <a
                href={sourceUrl}
                target="_blank"
                rel="noreferrer"
                className="inline-flex h-8 items-center gap-1 self-start text-xs font-medium text-primary hover:underline"
              >
                {isEnglish ? 'Open source' : '打开来源'}
                <ExternalLink className="h-3.5 w-3.5" aria-hidden="true" />
              </a>
            ) : null}
          </article>
          );
        })}
      </div>
      {newsItems.length === 0 ? (
        <p className="py-6 text-sm text-secondary-text">
          {isEnglish
            ? 'No realtime event item is available. The lane remains visible and is not presented as complete.'
            : '当前没有可用实时事件条目；通道保留，但不会被标示为资料完整。'}
        </p>
      ) : null}
    </div>
  );

  const renderKline = () => (
    <div
      role="tabpanel"
      aria-label={tabs[4].label}
      data-testid="research-overview-kline-v142"
      className="grid min-w-0 gap-4 lg:grid-cols-[1.4fr_0.6fr]"
    >
      <div className="min-w-0">
        <div className="flex items-center justify-between gap-3">
          <div>
            <h4 className="text-sm font-semibold text-foreground">
              {isEnglish ? 'Observed close-price samples' : '已观测收盘价样本'}
            </h4>
            <p className="mt-1 text-xs text-secondary-text">
              {isEnglish ? `${trendPoints.length} close samples` : `${trendPoints.length} 个收盘样本`}
            </p>
          </div>
          <span className="text-lg font-semibold text-primary">{formatPercent(snapshot.trend?.changePercent)}</span>
        </div>
        <div className="mt-3 h-32 border-y border-subtle py-2">
          {linePoints ? (
            <svg viewBox="0 0 420 120" className="h-full w-full" role="img" aria-label={isEnglish ? 'Observed close-price line' : '已观测收盘价曲线'}>
              <polyline
                fill="none"
                stroke="currentColor"
                strokeWidth="3"
                vectorEffect="non-scaling-stroke"
                points={linePoints}
                className="text-primary"
              />
            </svg>
          ) : (
            <div className="flex h-full items-center justify-center text-xs text-secondary-text">
              {isEnglish ? 'At least two close samples are required.' : '至少需要两个收盘样本。'}
            </div>
          )}
        </div>
      </div>
      <dl className="grid grid-cols-2 gap-px overflow-hidden rounded-lg border border-subtle bg-subtle text-xs">
        {[
          [isEnglish ? 'Window' : '样本窗口', String(snapshot.trend?.window ?? trendPoints.length)],
          [isEnglish ? 'Low' : '区间低点', formatNumber(snapshot.trend?.minClose)],
          [isEnglish ? 'High' : '区间高点', formatNumber(snapshot.trend?.maxClose)],
          [isEnglish ? 'Source' : '来源', sourceLabel(snapshot.trend?.source, language)],
        ].map(([label, value]) => (
          <div key={label} className="min-w-0 bg-background/70 px-3 py-3">
            <dt className="text-secondary-text">{label}</dt>
            <dd className="mt-1 truncate font-semibold text-foreground">{value}</dd>
          </div>
        ))}
      </dl>
    </div>
  );

  const renderSources = () => (
    <div role="tabpanel" aria-label={tabs[5].label} data-testid="research-overview-sources-v142" className="space-y-4">
      <div className="grid min-w-0 gap-3 md:grid-cols-3">
        <div className="min-w-0 border-l-2 border-primary pl-3">
          <div className="text-xs text-secondary-text">{isEnglish ? 'Quote source' : '行情来源'}</div>
          <div className="mt-1 font-semibold text-foreground">{sourceLabel(snapshot.quote.source, language)}</div>
          <div className="mt-1 text-xs text-secondary-text">{freshnessLabel(snapshot.quote.freshness, language)}</div>
        </div>
        <div className="min-w-0 border-l border-subtle pl-3">
          <div className="text-xs text-secondary-text">{isEnglish ? 'History source' : '历史来源'}</div>
          <div className="mt-1 font-semibold text-foreground">{sourceLabel(snapshot.trend?.source, language)}</div>
          <div className="mt-1 text-xs text-secondary-text">{snapshot.quote.updateTime || '-'}</div>
        </div>
        <div className="min-w-0 border-l border-subtle pl-3">
          <div className="text-xs text-secondary-text">{isEnglish ? 'Source conflicts' : '来源冲突'}</div>
          <div className="mt-1 font-semibold text-foreground">
            {conflictCount > 0
              ? (isEnglish ? `${conflictCount} differences reported` : `已报告 ${conflictCount} 项差异`)
              : (isEnglish ? 'No source conflict reported' : '未发现来源冲突')}
          </div>
          <div className="mt-1 text-xs text-secondary-text">
            {isEnglish ? 'Differences are retained instead of silently overwritten.' : '多来源差异会保留，不会被悄悄覆盖。'}
          </div>
        </div>
      </div>

      {selectedSources.length > 0 ? (
        <div className="overflow-x-auto border-y border-subtle">
          <table className="w-full min-w-[34rem] text-left text-xs">
            <thead className="text-secondary-text">
              <tr>
                <th className="px-2 py-2 font-medium">{isEnglish ? 'Domain' : '数据域'}</th>
                <th className="px-2 py-2 font-medium">{isEnglish ? 'Selected source' : '当前来源'}</th>
                <th className="px-2 py-2 font-medium">{isEnglish ? 'Freshness' : '新鲜度'}</th>
                <th className="px-2 py-2 font-medium">{isEnglish ? 'Observed at' : '观测时间'}</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-subtle">
              {selectedSources.map(([domain, source]) => (
                <tr key={domain}>
                  <td className="px-2 py-2 font-semibold text-foreground">{domain}</td>
                  <td className="px-2 py-2 text-foreground">{sourceLabel(source.source, language)}</td>
                  <td className="px-2 py-2 text-foreground">{freshnessLabel(source.freshness, language)}</td>
                  <td className="px-2 py-2 text-secondary-text">{source.observedAt || '-'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}

      <div className="border-l-2 border-primary pl-3 text-xs leading-5 text-secondary-text">
        {isEnglish
          ? 'Information and data only; not investment advice or a trading instruction. Missing data remains missing, and no AI is used in this overview.'
          : '仅提供资讯和数据，不构成投资建议或交易指令。缺失数据保持缺失，本研究总览不使用 AI。'}
      </div>
    </div>
  );

  const content = activeTab === 'overview'
    ? renderOverview()
    : activeTab === 'financials'
      ? renderFinancials()
      : activeTab === 'peers'
        ? renderPeers()
        : activeTab === 'events'
          ? renderEvents()
          : activeTab === 'kline'
            ? renderKline()
            : renderSources();

  return (
    <section
      data-testid="basic-query-research-overview-v142"
      className="mb-4 overflow-hidden rounded-lg border border-primary/35 bg-background/45"
    >
      <header className="flex min-w-0 flex-col gap-3 border-b border-subtle px-4 py-4 lg:flex-row lg:items-start lg:justify-between">
        <div className="min-w-0">
          <div className="text-xs font-semibold text-primary">V142</div>
          <h3 className="mt-1 text-lg font-semibold text-foreground">
            {isEnglish ? 'Stock research overview' : '个股研究总览'}
          </h3>
          <p className="mt-1 max-w-3xl text-xs leading-5 text-secondary-text">
            {isEnglish
              ? 'Facts first: quote, financial trends, peers, events, K-line samples, and source boundaries in one reading path.'
              : '事实优先：把行情、财务趋势、同业、事件、K线样本和来源边界整合为一条阅读路径。'}
          </p>
        </div>
        <div className="flex shrink-0 flex-wrap gap-2 text-[11px]">
          <span className="rounded-md border border-primary/40 bg-primary/10 px-2 py-1 font-medium text-primary">
            {isEnglish ? 'Guest available' : '游客可用'}
          </span>
          <span className="rounded-md border border-primary/40 bg-primary/10 px-2 py-1 font-medium text-primary">
            {isEnglish ? 'No AI' : '未用 AI'}
          </span>
          <span className="rounded-md border border-subtle px-2 py-1 text-secondary-text">
            {sourceLabel(snapshot.quote.source, language)}
          </span>
        </div>
      </header>

      <div className="overflow-x-auto border-b border-subtle px-2">
        <div role="tablist" aria-label={isEnglish ? 'Research sections' : '研究栏目'} className="flex min-w-max items-center gap-1">
          {tabs.map((tab) => {
            const Icon = tab.icon;
            const selected = activeTab === tab.key;
            return (
              <button
                key={tab.key}
                type="button"
                role="tab"
                aria-selected={selected}
                className={`inline-flex h-11 items-center gap-1.5 border-b-2 px-3 text-xs font-medium transition-colors ${
                  selected
                    ? 'border-primary text-primary'
                    : 'border-transparent text-secondary-text hover:text-foreground'
                }`}
                onClick={() => setActiveTab(tab.key)}
              >
                <Icon className="h-3.5 w-3.5" aria-hidden="true" />
                {tab.label}
              </button>
            );
          })}
        </div>
      </div>

      <div className="min-h-[17rem] px-4 py-4">{content}</div>

      <footer className="flex min-w-0 flex-col gap-2 border-t border-subtle bg-surface/30 px-4 py-3 sm:flex-row sm:items-center sm:justify-between">
        <p className="min-w-0 text-[11px] leading-5 text-secondary-text">
          {isEnglish
            ? 'The previous detailed modules remain available below and can be expanded when a full audit trail is needed.'
            : '旧版详细模块仍保留；需要查看完整明细和操作入口时可展开。'}
        </p>
        <Button type="button" variant="secondary" size="sm" className="shrink-0" onClick={onToggleDetails}>
          {detailsExpanded ? (
            <ChevronUp className="h-4 w-4" aria-hidden="true" />
          ) : (
            <ChevronDown className="h-4 w-4" aria-hidden="true" />
          )}
          {detailsExpanded
            ? (isEnglish ? 'Hide detailed modules' : '收起详细模块')
            : (isEnglish ? 'Show all detailed modules' : '展开全部详细模块')}
        </Button>
      </footer>
    </section>
  );
}
