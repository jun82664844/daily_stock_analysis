import { AlertTriangle, RefreshCw } from 'lucide-react';
import { useCallback, useEffect, useState } from 'react';
import type { MarketCode, MarketDailyBriefResponse, MarketSearchItem, MarketWorkspaceOverview, SymbolWorkspaceResponse } from '../api/marketWorkspace';
import { marketWorkspaceApi } from '../api/marketWorkspace';
import { platformApi } from '../api/platform';
import { AppPage } from '../components/common';
import GlobalStockCommandV113 from '../components/market-workspace/GlobalStockCommandV113';
import MarketHeatmapV113 from '../components/market-workspace/MarketHeatmapV113';
import MarketMoversV113 from '../components/market-workspace/MarketMoversV113';
import MarketNewsTimelineV113 from '../components/market-workspace/MarketNewsTimelineV113';
import MarketPulseV113 from '../components/market-workspace/MarketPulseV113';
import SymbolWorkspaceV113 from '../components/market-workspace/SymbolWorkspaceV113';
import WatchlistBriefV113 from '../components/market-workspace/WatchlistBriefV113';
import { useUiLanguage } from '../contexts/UiLanguageContext';

const MARKET_LABELS: Record<MarketCode, { zh: string; en: string }> = { cn: { zh: 'A股', en: 'A-shares' }, hk: { zh: '港股', en: 'Hong Kong' }, us: { zh: '美股', en: 'US stocks' } };

export default function MarketWorkspacePage() {
  const { language } = useUiLanguage();
  const en = language === 'en';
  const [market, setMarket] = useState<MarketCode>('cn');
  const [overview, setOverview] = useState<MarketWorkspaceOverview | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [searching, setSearching] = useState(false);
  const [results, setResults] = useState<MarketSearchItem[]>([]);
  const [symbolLoading, setSymbolLoading] = useState(false);
  const [symbolData, setSymbolData] = useState<SymbolWorkspaceResponse | null>(null);
  const [brief, setBrief] = useState<MarketDailyBriefResponse | null>(null);
  const [loginRequired, setLoginRequired] = useState(false);
  const [actionNotice, setActionNotice] = useState('');

  const loadOverview = useCallback(async (nextMarket: MarketCode) => {
    setLoading(true);
    setError('');
    try {
      const payload = await marketWorkspaceApi.getOverview(nextMarket);
      setOverview(payload);
    } catch {
      setError(en ? 'Market data is temporarily unavailable. Existing public stock queries remain available.' : '市场工作台数据暂不可用，现有公开个股查询仍可继续使用。');
    } finally {
      setLoading(false);
    }
  }, [en]);

  useEffect(() => { void loadOverview(market); }, [loadOverview, market]);
  useEffect(() => {
    let active = true;
    marketWorkspaceApi.getDailyBrief().then((payload) => { if (active) setBrief(payload); }).catch(() => { if (active) setLoginRequired(true); });
    return () => { active = false; };
  }, []);

  const search = async (query: string) => {
    setSearching(true);
    try { setResults((await marketWorkspaceApi.search(query)).items); } catch { setResults([]); } finally { setSearching(false); }
  };

  const openSymbol = async (symbol: string) => {
    setSymbolLoading(true);
    try { setSymbolData(await marketWorkspaceApi.getSymbol(symbol)); } catch { setError(en ? 'This symbol is temporarily unavailable.' : '该证券数据暂不可用。'); } finally { setSymbolLoading(false); }
  };

  const selectSearchResult = (item: MarketSearchItem) => {
    setMarket(item.market);
    void openSymbol(item.symbol);
  };

  const addCurrentToWatchlist = async () => {
    if (!symbolData) return;
    setActionNotice('');
    try {
      await platformApi.addWatchlistItem(symbolData.symbol);
      setActionNotice(en ? 'Added to your watchlist.' : '已加入自选。');
      setLoginRequired(false);
    } catch {
      setActionNotice(en ? 'Sign in to save this stock.' : '登录后可保存该股票。');
      setLoginRequired(true);
    }
  };

  const saveCurrentAlert = async (ruleType: 'price_above' | 'price_below', threshold: number) => {
    if (!symbolData) return;
    setActionNotice('');
    try {
      await platformApi.saveWatchlistAlertRule({ stockCode: symbolData.symbol, ruleType, threshold, enabled: true });
      setActionNotice(en ? 'Condition alert saved.' : '条件提醒已保存。');
      setLoginRequired(false);
    } catch {
      setActionNotice(en ? 'Sign in to save condition alerts.' : '登录后可保存条件提醒。');
      setLoginRequired(true);
    }
  };

  return (
    <AppPage className="max-w-[1500px]">
      <header className="flex flex-col gap-4 pb-4 md:flex-row md:items-end md:justify-between">
        <div><span className="text-xs uppercase text-primary">DSA V113</span><h1 className="mt-1 text-3xl font-semibold text-foreground">{en ? 'Market workspace' : '市场工作台'}</h1><p className="mt-2 max-w-3xl text-sm text-secondary-text">{en ? 'Public market overview, stock search, company data, information timeline and private watchlist brief without mandatory AI.' : '无需强制使用 AI，即可查看公开市场总览、股票搜索、公司资料、资讯时间线和私人自选简报。'}</p></div>
        <button type="button" onClick={() => void loadOverview(market)} disabled={loading} className="btn-secondary"><RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />{en ? 'Refresh' : '刷新'}</button>
      </header>

      <div className="flex flex-wrap gap-2 border-y border-border/70 py-3" role="group" aria-label={en ? 'Select market' : '选择市场'}>{(['cn', 'hk', 'us'] as MarketCode[]).map((item) => <button type="button" key={item} aria-pressed={market === item} onClick={() => setMarket(item)} className={market === item ? 'btn-primary' : 'btn-secondary'}>{MARKET_LABELS[item][language]}</button>)}</div>
      <GlobalStockCommandV113 language={language} loading={searching} results={results} onSearch={search} onSelect={selectSearchResult} />
      {error ? <div className="my-4 flex items-start gap-2 rounded-lg border border-amber-500/40 bg-amber-500/10 p-4 text-sm text-amber-200"><AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />{error}</div> : null}
      {symbolLoading ? <p className="py-8 text-center text-secondary-text">{en ? 'Loading symbol data...' : '正在加载股票数据...'}</p> : symbolData ? <SymbolWorkspaceV113 key={symbolData.symbol} language={language} data={symbolData} onAddWatchlist={addCurrentToWatchlist} onSaveAlert={saveCurrentAlert} actionNotice={actionNotice} /> : null}
      {loading && !overview ? <p className="py-16 text-center text-secondary-text">{en ? 'Loading market data...' : '正在加载市场数据...'}</p> : overview ? <div key={overview.market}><MarketPulseV113 language={language} overview={overview} />{overview.warnings.length ? <p className="mt-3 text-sm text-amber-300">{en ? 'Degraded modules: ' : '降级模块：'}{overview.warnings.join(', ')}</p> : null}<MarketHeatmapV113 language={language} items={overview.heatmap} onSelect={(symbol) => void openSymbol(symbol)} /><MarketMoversV113 language={language} items={overview.movers} onSelect={(symbol) => void openSymbol(symbol)} /><MarketNewsTimelineV113 language={language} items={overview.headlines} /></div> : null}
      <WatchlistBriefV113 language={language} brief={brief} loginRequired={loginRequired} />
      <footer className="border-t border-border/70 py-5 text-sm text-secondary-text">{en ? 'Information and data only. No investment advice. Data may be delayed or unavailable; verify against authorized sources.' : '本页面只提供市场资讯、客观数据和用户自定义条件提醒，不提供投资建议、交易指令、目标价或收益预测。数据可能延迟或缺失，请以授权来源为准。'}</footer>
    </AppPage>
  );
}
