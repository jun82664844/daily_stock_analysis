import { useCallback, useEffect, useMemo, useState } from 'react';
import { BookOpenText, Database, RefreshCw, Search, ShieldCheck } from 'lucide-react';
import {
  researchWorkflowsApi,
  type FinancialResearchFact,
  type FinancialResearchWorkflowResponse,
} from '../api/researchWorkflows';
import { useUiLanguage } from '../contexts/UiLanguageContext';

const missingLabels: Record<string, [string, string]> = {
  current_price: ['最新价格', 'latest price'],
  market_cap: ['总市值', 'market cap'],
  pe_ratio: ['市盈率', 'P/E ratio'],
  revenue: ['营业收入', 'revenue'],
  net_profit: ['净利润', 'net profit'],
  revenue_growth: ['收入增长率', 'revenue growth'],
  earnings_growth: ['利润增长率', 'earnings growth'],
  sector: ['板块', 'sector'],
  industry: ['行业', 'industry'],
  events: ['公开事件', 'public events'],
};

const sourceLabels: Record<string, [string, string]> = {
  us_realtime: ['实时行情', 'Realtime quote'],
  a_share_realtime: ['A股行情', 'A-share quote'],
  hk_realtime: ['港股行情', 'Hong Kong quote'],
  crypto_realtime: ['加密行情', 'Crypto quote'],
  crypto_yahoo_chart: ['加密行情', 'Crypto quote'],
  yahoo_chart: ['行情图表', 'Market chart'],
  yfinance_profile: ['公司资料', 'Company profile'],
  no_ai_news_center_rules: ['资讯清单', 'News checklist'],
};

const freshnessLabels: Record<string, [string, string]> = {
  fresh: ['新鲜', 'Fresh'],
  cached: ['缓存', 'Cached'],
  available: ['可用', 'Available'],
  degraded: ['降级', 'Degraded'],
  stale: ['过期', 'Stale'],
  missing: ['缺失', 'Missing'],
};

const workflowSourceLabels: Record<string, [string, string]> = {
  company_snapshot: ['参考工作流：公司与估值概览', 'Reference workflow: company and valuation'],
  earnings_review: ['参考工作流：经营数据复盘', 'Reference workflow: operating data review'],
  sector_overview: ['参考工作流：行业与板块概览', 'Reference workflow: sector and industry'],
  catalyst_calendar: ['参考工作流：公开事件日历', 'Reference workflow: public event calendar'],
};

const localizedFactValues: Record<string, string> = {
  Technology: '科技',
  'Consumer Electronics': '消费电子',
  'Market-moving news lane': '市场影响资讯通道',
  'Announcements lane': '公告通道',
  'SEC filings lane': 'SEC 文件通道',
  'Financial snapshot lane': '财务快照通道',
  'Sector and peer lane': '板块与同业通道',
  'Data quality lane': '数据质量通道',
};

function formatFactValue(fact: FinancialResearchFact, language: 'zh' | 'en'): string {
  if (typeof fact.value !== 'number') {
    const value = String(fact.value ?? '-');
    return language === 'zh' ? localizedFactValues[value] || value : value;
  }
  if (['change_percent'].includes(fact.code)) return `${fact.value.toFixed(2)}%`;
  if (['revenue_growth', 'earnings_growth'].includes(fact.code)) return `${fact.value.toFixed(2)}%`;
  const absolute = Math.abs(fact.value);
  let formatted: string;
  if (language === 'zh') {
    if (absolute >= 1e8) formatted = `${(fact.value / 1e8).toFixed(2)}亿`;
    else if (absolute >= 1e4) formatted = `${(fact.value / 1e4).toFixed(2)}万`;
    else formatted = new Intl.NumberFormat('zh-CN', { maximumFractionDigits: 4 }).format(fact.value);
  } else {
    if (absolute >= 1e12) formatted = `${(fact.value / 1e12).toFixed(2)}T`;
    else if (absolute >= 1e9) formatted = `${(fact.value / 1e9).toFixed(2)}B`;
    else if (absolute >= 1e6) formatted = `${(fact.value / 1e6).toFixed(2)}M`;
    else formatted = new Intl.NumberFormat('en-US', { maximumFractionDigits: 4 }).format(fact.value);
  }
  const currencyLabels: Record<string, [string, string]> = {
    USD: ['美元', 'USD'],
    CNY: ['人民币', 'CNY'],
    HKD: ['港元', 'HKD'],
  };
  const unitLabels: Record<string, [string, string]> = {
    shares: ['股', 'shares'],
    units: ['个', 'units'],
  };
  const suffix = fact.currency
    ? currencyLabels[fact.currency]?.[language === 'en' ? 1 : 0] || fact.currency
    : unitLabels[fact.unit]?.[language === 'en' ? 1 : 0] || '';
  return suffix ? `${formatted} ${suffix}` : formatted;
}

function localizedSource(source: string, language: 'zh' | 'en'): string {
  return sourceLabels[source]?.[language === 'en' ? 1 : 0]
    || (language === 'en' ? source.replaceAll('_', ' ') : '数据来源');
}

function localizedFreshness(freshness: string, language: 'zh' | 'en'): string {
  return freshnessLabels[freshness]?.[language === 'en' ? 1 : 0]
    || (language === 'en' ? freshness.replaceAll('_', ' ') : '状态未知');
}

export default function ResearchWorkflowsPage() {
  const { language } = useUiLanguage();
  const en = language === 'en';
  const [symbol, setSymbol] = useState('AAPL');
  const [refresh, setRefresh] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [result, setResult] = useState<FinancialResearchWorkflowResponse | null>(null);

  const runResearch = useCallback(async (requestedSymbol: string, forceRefresh: boolean) => {
    const normalized = requestedSymbol.trim().toUpperCase();
    if (!normalized) return;
    setLoading(true);
    setError('');
    try {
      setResult(await researchWorkflowsApi.get(normalized, { refresh: forceRefresh }));
    } catch (caught) {
      const message = caught instanceof Error ? caught.message : String(caught);
      setError(message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void runResearch('AAPL', false);
  }, [runResearch]);

  const availableCount = useMemo(
    () => result?.workflows.filter((item) => item.status === 'available').length ?? 0,
    [result],
  );

  return (
    <div className="mx-auto w-full max-w-[1500px] px-4 py-6 sm:px-6 lg:px-8">
      <header className="border-b border-border pb-5">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="min-w-0">
            <p className="text-sm font-medium text-cyan">{en ? 'No-AI research workflows' : '无AI研究工作流'}</p>
            <h1 className="mt-1 text-2xl font-semibold text-foreground">{en ? 'Financial research center' : '金融研究中心'}</h1>
            <p className="mt-2 max-w-3xl text-sm leading-6 text-secondary-text">
              {en
                ? 'Turn the existing DSA quote and company fields into four factual review checklists. No external agent or paid connector runs on this page.'
                : '把DSA现有行情和公司资料整理为四类事实研究清单。本页面不运行外部Agent，也不调用付费连接器。'}
            </p>
          </div>
          <div className="flex items-center gap-2 text-xs text-secondary-text">
            <span className="rounded-full border border-cyan/40 px-3 py-1 text-cyan">{en ? 'No AI used' : '未使用AI'}</span>
            <span className="rounded-full border border-border px-3 py-1">{en ? 'Public access' : '游客可用'}</span>
          </div>
        </div>
      </header>

      <form
        className="grid gap-3 border-b border-border py-5 md:grid-cols-[minmax(0,1fr)_auto_auto] md:items-end"
        onSubmit={(event) => {
          event.preventDefault();
          void runResearch(symbol, refresh);
        }}
      >
        <label className="space-y-2 text-sm font-medium text-foreground">
          {en ? 'Stock code' : '股票代码'}
          <div className="relative">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-secondary-text" />
            <input
              className="h-11 w-full rounded-lg border border-border bg-surface pl-10 pr-3 text-sm text-foreground outline-none focus:border-cyan"
              value={symbol}
              onChange={(event) => setSymbol(event.target.value)}
              placeholder={en ? 'Enter a code, such as 600519.SH or AAPL' : '输入股票代码，如 600519.SH、AAPL'}
            />
          </div>
        </label>
        <label className="inline-flex min-h-11 items-center gap-2 text-sm text-secondary-text">
          <input
            type="checkbox"
            checked={refresh}
            onChange={(event) => setRefresh(event.target.checked)}
            aria-label={en ? 'Force refresh existing market data' : '强制刷新现有行情数据'}
          />
          {en ? 'Refresh market data' : '刷新行情'}
        </label>
        <button
          type="submit"
          disabled={loading || !symbol.trim()}
          className="inline-flex h-11 items-center justify-center gap-2 rounded-lg bg-cyan px-5 text-sm font-semibold text-slate-950 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {loading ? <RefreshCw className="h-4 w-4 animate-spin" /> : <BookOpenText className="h-4 w-4" />}
          {loading ? (en ? 'Loading' : '加载中') : (en ? 'Build research checklist' : '生成研究清单')}
        </button>
      </form>

      {error ? (
        <p role="alert" className="my-4 rounded-lg border border-red-500/40 bg-red-500/10 px-4 py-3 text-sm text-red-300">
          {en ? `Unable to load research data: ${error}` : `无法加载研究资料：${error}`}
        </p>
      ) : null}

      {result ? (
        <>
          <section className="grid gap-4 border-b border-border py-5 lg:grid-cols-[1fr_auto] lg:items-center">
            <div>
              <div className="flex flex-wrap items-center gap-2">
                <Database className="h-5 w-5 text-cyan" />
                <h2 className="text-lg font-semibold text-foreground">{result.stockName || result.stockCode}</h2>
                <span className="text-sm text-secondary-text">{result.stockCode} · {result.market.toUpperCase()}</span>
              </div>
              <p className="mt-2 text-sm text-secondary-text">
                <span>{result.source.installed
                  ? (en ? 'Anthropic financial workflow source installed' : 'Anthropic 金融工作流来源已安装')
                  : (en ? 'Reference source unavailable; DSA facts remain visible' : '研究来源未安装；仍展示DSA已有事实')}</span>
                <span>{' · '}{result.source.license}{result.source.commit ? ` · ${result.source.commit.slice(0, 8)}` : ''}</span>
              </p>
            </div>
            <div className="flex flex-wrap items-center gap-2 text-xs">
              <span className="rounded-full border border-border px-3 py-1 text-secondary-text">
                {en ? `${availableCount}/4 complete workflows` : `${availableCount}/4 项资料完整`}
              </span>
              <span className="rounded-full border border-emerald-500/40 px-3 py-1 text-emerald-300">
                {en ? 'External connectors disabled' : '外部连接器未启用'}
              </span>
              <span className="rounded-full border border-border px-3 py-1 text-secondary-text">
                {en ? 'External code not executed' : '未执行外部代码'}
              </span>
            </div>
          </section>

          <section className="grid gap-4 py-5 xl:grid-cols-2" aria-label={en ? 'Research workflows' : '研究工作流'}>
            {result.workflows.map((workflow) => (
              <article key={workflow.id} className="rounded-lg border border-border bg-card p-5">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <h2 className="text-lg font-semibold text-foreground">{en ? workflow.titleEn : workflow.titleZh}</h2>
                    <p className="mt-2 text-sm leading-6 text-secondary-text">{en ? workflow.purposeEn : workflow.purposeZh}</p>
                  </div>
                  <span className={`shrink-0 rounded-full border px-2.5 py-1 text-xs ${workflow.status === 'available' ? 'border-emerald-500/40 text-emerald-300' : 'border-amber-500/40 text-amber-300'}`}>
                    {workflow.status === 'available' ? (en ? 'Available' : '可用') : (en ? 'Partial' : '部分可用')}
                  </span>
                </div>

                {workflow.facts.length ? (
                  <dl className="mt-4 divide-y divide-border border-y border-border">
                    {workflow.facts.map((fact) => (
                      <div key={`${workflow.id}-${fact.code}`} className="grid gap-1 py-3 sm:grid-cols-[150px_1fr_auto] sm:items-center">
                        <dt className="text-xs text-secondary-text">{en ? fact.labelEn : fact.labelZh}</dt>
                        <dd className="min-w-0 break-words text-sm font-medium text-foreground">{formatFactValue(fact, language)}</dd>
                        <dd className="text-xs text-secondary-text">
                          {localizedSource(fact.source, language)} · {localizedFreshness(fact.freshness, language)}
                        </dd>
                      </div>
                    ))}
                  </dl>
                ) : (
                  <p className="mt-4 border-y border-border py-4 text-sm text-secondary-text">
                    {en ? 'No verified facts are available for this workflow yet.' : '该工作流暂时没有可核验事实。'}
                  </p>
                )}

                {workflow.missingData.length ? (
                  <p className="mt-3 text-xs text-amber-300">
                    {en ? 'Missing: ' : '缺少：'}
                    {workflow.missingData.map((code) => missingLabels[code]?.[en ? 1 : 0] || code).join(en ? ', ' : '、')}
                  </p>
                ) : null}
                <p className="mt-3 text-[11px] text-secondary-text" title={workflow.sourceReference}>
                  {workflowSourceLabels[workflow.id]?.[en ? 1 : 0] || (en ? 'Reference workflow' : '参考工作流')}
                </p>
              </article>
            ))}
          </section>

          <footer className="flex items-start gap-3 border-t border-border py-5 text-sm text-secondary-text">
            <ShieldCheck className="mt-0.5 h-5 w-5 shrink-0 text-cyan" />
            <p>{en ? result.boundaryEn : result.boundaryZh}</p>
          </footer>
        </>
      ) : null}
    </div>
  );
}
