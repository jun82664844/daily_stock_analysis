import type React from 'react';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Archive, ArchiveRestore, BarChart3, Check, Download, Eye, Flag, KeyRound, LogOut, Plus, RefreshCw, Save, Search, SlidersHorizontal, Sparkles, Star, UserRound } from 'lucide-react';
import { useLocation, useNavigate } from 'react-router-dom';
import { getParsedApiError, type ParsedApiError } from '../api/error';
import { analysisApi } from '../api/analysis';
import { historyApi } from '../api/history';
import { platformApi, type PlatformAccountSummary, type PlatformApiKeyItem, type PlatformAuthPayload, type PlatformQuota, type PlatformWatchlistRefreshResponse, type PlatformWatchlistResponse } from '../api/platform';
import { stocksApi, type BasicStockSnapshot } from '../api/stocks';
import { agentApi, type SkillInfo } from '../api/agent';
import { systemConfigApi } from '../api/systemConfig';
import { ApiErrorAlert, Button, Drawer, EmptyState, InlineAlert } from '../components/common';
import { DashboardStateBlock } from '../components/dashboard';
import { StockAutocomplete } from '../components/StockAutocomplete';
import { HistoryList, StockHistoryTrendDrawer, StockBar } from '../components/history';
import { ReportMarkdownDrawer } from '../components/report/ReportMarkdownDrawer';
import { MarketReviewReportView } from '../components/report/MarketReviewReportView';
import { ReportSummary } from '../components/report/ReportSummary';
import { RunFlowPanel } from '../components/run-flow';
import { TaskPanel } from '../components/tasks';
import { useDashboardLifecycle, useHomeDashboardState } from '../hooks';
import { useWatchlist } from '../hooks/useWatchlist';
import { useUiLanguage } from '../contexts/UiLanguageContext';
import type { SetupStatusResponse } from '../types/systemConfig';
import { normalizeReportLanguage } from '../utils/reportLanguage';
import type { AnalysisDepth, AnalysisReport, ApiKeyMode, HistoryFilters, HistoryItem, HistoryStateUpdatePayload, MarketReviewPayload, ReportType, StockBarItem, TaskInfo } from '../types/analysis';
import type { RunFlowSnapshotSource } from '../types/runFlow';
import { getRecentStartDate, getTodayInShanghai } from '../utils/format';
import { downloadTextFile } from '../utils/downloadText';

const formatBasicNumber = (value: unknown): string => (
  typeof value === 'number' && Number.isFinite(value)
    ? value.toLocaleString(undefined, { maximumFractionDigits: 4 })
    : '-'
);

const formatBasicCompactNumber = (value: unknown): string => (
  typeof value === 'number' && Number.isFinite(value)
    ? new Intl.NumberFormat('en-US', { notation: 'compact', maximumFractionDigits: 2 }).format(value)
    : '-'
);

const formatBasicPercent = (value: unknown): string => {
  const formatted = formatBasicNumber(value);
  return formatted === '-' ? '-' : `${formatted}%`;
};

const volumePriceSignalLabel = (value: unknown, language: string): string => {
  const signal = typeof value === 'string' ? value : '';
  const isEnglish = language === 'en';
  if (signal === 'price_volume_confirmed') return isEnglish ? 'Price-volume confirmed' : '价量确认';
  if (signal === 'price_above_trend_volume_soft') return isEnglish ? 'Price above trend' : '价在趋势上方';
  if (signal === 'volume_expanded_price_below_trend') return isEnglish ? 'Volume expanded' : '放量但价弱';
  if (signal === 'neutral') return isEnglish ? 'Neutral' : '中性';
  if (signal === 'insufficient_data') return isEnglish ? 'Insufficient data' : '数据不足';
  return signal || '-';
};

const pickBasicIndicator = (indicators: Record<string, unknown>, ...keys: string[]): unknown => {
  for (const key of keys) {
    if (indicators[key] !== undefined && indicators[key] !== null) {
      return indicators[key];
    }
  }
  return undefined;
};

const formatQuotaLeft = (quota?: Pick<PlatformQuota, 'weeklyLimit' | 'remaining' | 'used'> | null): string => {
  if (!quota) {
    return 'unavailable';
  }
  if (quota.weeklyLimit === null) {
    return `${quota.used}/unlimited used`;
  }
  return `${quota.remaining ?? 0}/${quota.weeklyLimit} left`;
};

const apiKeyModeLabel = (mode?: string | null): string => {
  if (mode === 'user') return 'BYOK';
  if (mode === 'local') return 'local model';
  return 'platform API';
};

const marketLaneLabel = (lane?: string | null): string => {
  if (lane === 'a_share_market_data') return 'A-share market data';
  if (lane === 'us_market_data') return 'US market data';
  if (lane === 'hk_market_data') return 'HK market data';
  if (lane === 'crypto_market_data') return 'Crypto market data';
  return lane || 'market data';
};

type HistoryCenterMarketFilter = 'all' | 'cn' | 'us' | 'hk' | 'crypto';
type HistoryCenterReportFilter = 'all' | 'stock' | ReportType;
type HistoryCenterRefreshFilter = 'all' | 'refreshed' | 'not_refreshed';
type HistoryCenterStateFilter = 'all' | 'favorite' | 'important' | 'archived' | 'active' | 'has_note' | 'unread' | 'read';
type HistoryCenterRangeFilter = 'all' | '7d' | '30d' | '90d';
type HistoryCenterSort = 'newest' | 'oldest';

type HistoryCenterFilters = {
  market: HistoryCenterMarketFilter;
  reportType: HistoryCenterReportFilter;
  refreshStatus: HistoryCenterRefreshFilter;
  state: HistoryCenterStateFilter;
  range: HistoryCenterRangeFilter;
  sort: HistoryCenterSort;
  code: string;
  noteSearch: string;
};

type HistoryReportSearchSegment = {
  key: string;
  label: string;
  text: string;
};

const HISTORY_REPORT_SECTIONS = [
  { id: 'overview', label: 'Summary' },
  { id: 'strategy', label: 'Strategy' },
  { id: 'news', label: 'News' },
  { id: 'diagnostics', label: 'Diagnostics' },
  { id: 'details', label: 'Details' },
] as const;

const DEFAULT_HISTORY_CENTER_FILTERS: HistoryCenterFilters = {
  market: 'all',
  reportType: 'all',
  refreshStatus: 'all',
  state: 'active',
  range: 'all',
  sort: 'newest',
  code: '',
  noteSearch: '',
};

const HISTORY_CENTER_FILTERS_STORAGE_KEY = 'dsa-history-center-filters-v1';
const HISTORY_CENTER_MARKET_FILTERS: readonly HistoryCenterMarketFilter[] = ['all', 'cn', 'us', 'hk', 'crypto'];
const HISTORY_CENTER_REPORT_FILTERS: readonly HistoryCenterReportFilter[] = ['all', 'simple', 'detailed', 'full', 'brief', 'market_review'];
const HISTORY_CENTER_REFRESH_FILTERS: readonly HistoryCenterRefreshFilter[] = ['all', 'refreshed', 'not_refreshed'];
const HISTORY_CENTER_STATE_FILTERS: readonly HistoryCenterStateFilter[] = ['all', 'favorite', 'important', 'archived', 'active', 'has_note', 'unread', 'read'];
const HISTORY_CENTER_RANGE_FILTERS: readonly HistoryCenterRangeFilter[] = ['all', '7d', '30d', '90d'];
const HISTORY_CENTER_SORT_FILTERS: readonly HistoryCenterSort[] = ['newest', 'oldest'];

const isOneOf = <T extends string>(value: unknown, options: readonly T[]): value is T => (
  typeof value === 'string' && options.includes(value as T)
);

const normalizeStoredHistoryCenterFilters = (value: unknown): HistoryCenterFilters => {
  const raw = value && typeof value === 'object'
    ? value as Partial<Record<keyof HistoryCenterFilters, unknown>>
    : {};

  return {
    market: isOneOf(raw.market, HISTORY_CENTER_MARKET_FILTERS) ? raw.market : DEFAULT_HISTORY_CENTER_FILTERS.market,
    reportType: isOneOf(raw.reportType, HISTORY_CENTER_REPORT_FILTERS) ? raw.reportType : DEFAULT_HISTORY_CENTER_FILTERS.reportType,
    refreshStatus: isOneOf(raw.refreshStatus, HISTORY_CENTER_REFRESH_FILTERS) ? raw.refreshStatus : DEFAULT_HISTORY_CENTER_FILTERS.refreshStatus,
    state: isOneOf(raw.state, HISTORY_CENTER_STATE_FILTERS) ? raw.state : DEFAULT_HISTORY_CENTER_FILTERS.state,
    range: isOneOf(raw.range, HISTORY_CENTER_RANGE_FILTERS) ? raw.range : DEFAULT_HISTORY_CENTER_FILTERS.range,
    sort: isOneOf(raw.sort, HISTORY_CENTER_SORT_FILTERS) ? raw.sort : DEFAULT_HISTORY_CENTER_FILTERS.sort,
    code: typeof raw.code === 'string' ? raw.code.slice(0, 80) : DEFAULT_HISTORY_CENTER_FILTERS.code,
    noteSearch: typeof raw.noteSearch === 'string' ? raw.noteSearch.slice(0, 120) : DEFAULT_HISTORY_CENTER_FILTERS.noteSearch,
  };
};

const readStoredHistoryCenterFilters = (): { filters: HistoryCenterFilters; restored: boolean } => {
  if (typeof window === 'undefined') {
    return { filters: DEFAULT_HISTORY_CENTER_FILTERS, restored: false };
  }
  const stored = window.localStorage.getItem(HISTORY_CENTER_FILTERS_STORAGE_KEY);
  if (!stored) {
    return { filters: DEFAULT_HISTORY_CENTER_FILTERS, restored: false };
  }
  try {
    return {
      filters: normalizeStoredHistoryCenterFilters(JSON.parse(stored)),
      restored: true,
    };
  } catch {
    return { filters: DEFAULT_HISTORY_CENTER_FILTERS, restored: false };
  }
};

const persistHistoryCenterFilters = (filters: HistoryCenterFilters): void => {
  if (typeof window === 'undefined') {
    return;
  }
  try {
    window.localStorage.setItem(HISTORY_CENTER_FILTERS_STORAGE_KEY, JSON.stringify(filters));
  } catch {
    // Keep filtering usable when localStorage is unavailable.
  }
};

const toHistoryCenterApiFilters = (filters: HistoryCenterFilters): HistoryFilters => {
  const params: HistoryFilters = { sort: filters.sort };
  const code = filters.code.trim();
  if (code) {
    params.stockCode = code;
  }
  const noteSearch = filters.noteSearch.trim();
  if (noteSearch) {
    params.noteSearch = noteSearch;
  }
  if (filters.market !== 'all') {
    params.market = filters.market;
  }
  if (filters.refreshStatus !== 'all') {
    params.refreshStatus = filters.refreshStatus;
  }
  if (filters.state !== 'all') {
    params.state = filters.state;
  }
  if (filters.reportType !== 'all' && filters.reportType !== 'stock') {
    params.reportType = filters.reportType;
  }
  if (filters.range !== 'all') {
    const days = Number.parseInt(filters.range.replace('d', ''), 10);
    if (Number.isFinite(days)) {
      params.startDate = getRecentStartDate(days);
      params.endDate = getTodayInShanghai();
    }
  }
  return params;
};

const reportSearchText = (value: unknown): string => {
  if (typeof value === 'string') {
    return value.trim();
  }
  if (typeof value === 'number' || typeof value === 'boolean') {
    return String(value);
  }
  if (Array.isArray(value)) {
    return value.map(reportSearchText).filter(Boolean).join(' ');
  }
  return '';
};

const collectHistoryReportSearchSegments = (report?: AnalysisReport | null): HistoryReportSearchSegment[] => {
  if (!report) {
    return [];
  }
  const segments: HistoryReportSearchSegment[] = [];
  const push = (key: string, label: string, values: unknown[]) => {
    const text = values.map(reportSearchText).filter(Boolean).join(' ');
    if (text) {
      segments.push({ key, label, text });
    }
  };

  push('summary', 'Summary', [
    report.summary?.analysisSummary,
    report.summary?.operationAdvice,
    report.summary?.trendPrediction,
  ]);
  push('strategy', 'Strategy', [
    report.strategy?.idealBuy,
    report.strategy?.secondaryBuy,
    report.strategy?.stopLoss,
    report.strategy?.takeProfit,
  ]);
  push('news', 'News', [report.details?.newsContent]);
  push('context', 'Context', [
    report.details?.belongBoards?.map((board) => board.name).join(' '),
    report.details?.sectorRankings?.top?.map((item) => item.name).join(' '),
    report.details?.sectorRankings?.bottom?.map((item) => item.name).join(' '),
  ]);
  return segments;
};

const buildHistoryReportMatchSnippet = (text: string, needle: string): string => {
  const lowerText = text.toLowerCase();
  const lowerNeedle = needle.toLowerCase();
  const index = lowerText.indexOf(lowerNeedle);
  if (index < 0) {
    return text.slice(0, 120);
  }
  const start = Math.max(0, index - 36);
  const end = Math.min(text.length, index + needle.length + 64);
  return `${start > 0 ? '...' : ''}${text.slice(start, end)}${end < text.length ? '...' : ''}`;
};

const normalizeTimelineCode = (code?: string | null): string => (
  String(code || '').trim().toUpperCase()
);

const historyTimelineDate = (createdAt?: string): string => {
  const datePart = String(createdAt || '').slice(0, 10);
  return /^\d{4}-\d{2}-\d{2}$/.test(datePart) ? datePart : 'Unknown date';
};

type MarketReviewNotice = {
  variant: 'success' | 'warning' | 'danger';
  title: string;
  message: string;
} | null;

type RunFlowDrawerState =
  | { open: false }
  | { open: true; source: RunFlowSnapshotSource; title: string };

type StockAnalysisNavigationState = {
  stockCode?: string;
  stockName?: string;
  autoAnalyze?: boolean;
  selectionSource?: string;
};

const HomePage: React.FC = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const { language: uiLanguage, t } = useUiLanguage();
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [isSubmittingMarketReview, setIsSubmittingMarketReview] = useState(false);
  const [marketReviewNotice, setMarketReviewNotice] = useState<MarketReviewNotice>(null);
  const [marketReviewError, setMarketReviewError] = useState<ParsedApiError | null>(null);
  const [marketReviewReport, setMarketReviewReport] = useState<string | null>(null);
  const [marketReviewPayload, setMarketReviewPayload] = useState<MarketReviewPayload | null>(null);
  const [basicSnapshot, setBasicSnapshot] = useState<BasicStockSnapshot | null>(null);
  const restoredHistoryCenterFiltersRef = useRef(false);
  const appliedInitialHistoryCenterFiltersRef = useRef(false);
  const [historyCenterFilters, setHistoryCenterFilters] = useState<HistoryCenterFilters>(() => {
    const restored = readStoredHistoryCenterFilters();
    restoredHistoryCenterFiltersRef.current = restored.restored;
    return restored.filters;
  });
  const [refreshedHistoryRecordIds, setRefreshedHistoryRecordIds] = useState<Set<number>>(() => new Set());
  const [isExportingHistory, setIsExportingHistory] = useState(false);
  const [historyExportStatus, setHistoryExportStatus] = useState('');
  const [isUpdatingHistoryState, setIsUpdatingHistoryState] = useState(false);
  const [historyStateStatus, setHistoryStateStatus] = useState('');
  const [historyStateNoteDraft, setHistoryStateNoteDraft] = useState('');
  const [historyReportSearch, setHistoryReportSearch] = useState('');
  const [historyReportMatchIndex, setHistoryReportMatchIndex] = useState(0);
  const [historyReportSectionStatus, setHistoryReportSectionStatus] = useState('');
  const [isQueryingBasic, setIsQueryingBasic] = useState(false);
  const [basicQueryError, setBasicQueryError] = useState<ParsedApiError | null>(null);
  const [analysisSkills, setAnalysisSkills] = useState<SkillInfo[]>([]);
  const [selectedStrategyId, setSelectedStrategyId] = useState('');
  const [strategyMenuOpen, setStrategyMenuOpen] = useState(false);
  const [runFlowDrawer, setRunFlowDrawer] = useState<RunFlowDrawerState>({ open: false });
  const [platformEnabled, setPlatformEnabled] = useState(false);
  const [platformSession, setPlatformSession] = useState<PlatformAuthPayload | null>(null);
  const [platformAccount, setPlatformAccount] = useState<PlatformAccountSummary | null>(null);
  const [platformKeys, setPlatformKeys] = useState<PlatformApiKeyItem[]>([]);
  const [platformWatchlist, setPlatformWatchlist] = useState<PlatformWatchlistResponse | null>(null);
  const [platformWatchlistRefresh, setPlatformWatchlistRefresh] = useState<PlatformWatchlistRefreshResponse | null>(null);
  const [platformWatchlistBusy, setPlatformWatchlistBusy] = useState(false);
  const [platformWatchlistError, setPlatformWatchlistError] = useState('');
  const [authMode, setAuthMode] = useState<'login' | 'register'>('login');
  const [authEmail, setAuthEmail] = useState('');
  const [authPassword, setAuthPassword] = useState('');
  const [authError, setAuthError] = useState('');
  const [authBusy, setAuthBusy] = useState(false);
  const [apiKeyDraft, setApiKeyDraft] = useState('');
  const [apiKeyProvider, setApiKeyProvider] = useState('deepseek');
  const [apiKeyModel, setApiKeyModel] = useState('deepseek/deepseek-v4-flash');
  const [apiKeySaving, setApiKeySaving] = useState(false);
  const marketReviewPollTimer = useRef<number | null>(null);
  const dashboardScrollRef = useRef<HTMLElement | null>(null);
  const strategyMenuRef = useRef<HTMLDivElement | null>(null);
  const strategyButtonRef = useRef<HTMLButtonElement | null>(null);
  const strategyItemRefs = useRef<Array<HTMLButtonElement | null>>([]);
  const strategyInitialFocusIndexRef = useRef<number | null>(null);

  const stopMarketReviewPolling = useCallback(() => {
    if (marketReviewPollTimer.current !== null) {
      window.clearInterval(marketReviewPollTimer.current);
      marketReviewPollTimer.current = null;
    }
  }, []);

  const scrollMarketReviewFeedbackIntoView = useCallback(() => {
    const scrollContainer = dashboardScrollRef.current;
    if (!scrollContainer) {
      return;
    }

    if (typeof scrollContainer.scrollTo === 'function') {
      scrollContainer.scrollTo({ top: 0, behavior: 'smooth' });
      return;
    }

    scrollContainer.scrollTop = 0;
  }, []);

  useEffect(() => stopMarketReviewPolling, [stopMarketReviewPolling]);
  const [setupStatus, setSetupStatus] = useState<SetupStatusResponse | null>(null);

  const {
    query,
    inputError,
    duplicateError,
    error,
    isAnalyzing,
    historyItems,
    historyTotal,
    selectedIds,
    isDeletingHistory,
    isLoadingHistory,
    isLoadingMore,
    hasMore,
    selectedReport,
    isLoadingReport,
    isHistoryTrendOpen,
    marketReviewHistoryItems,
    stockHistoryItems,
    stockHistoryTotal,
    stockHistoryHasMore,
    isLoadingStockHistory,
    isLoadingMoreStockHistory,
    stockHistoryError,
    stockHistoryFilters,
    activeTasks,
    markdownDrawerOpen,
    setQuery,
    clearError,
    loadInitialHistory,
    refreshHistory,
    loadMoreHistory,
    setHistoryFilters,
    loadMarketReviewHistory,
    refreshMarketReviewHistory,
    selectHistoryItem,
    toggleHistorySelection,
    toggleSelectAllVisible,
    deleteSelectedHistory,
    submitAnalysis,
    notify,
    setNotify,
    apiKeyMode,
    setApiKeyMode,
    resetDashboardState,
    syncTaskCreated,
    syncTaskUpdated,
    syncTaskFailed,
    refreshActiveTasks,
    removeTask,
    openMarkdownDrawer,
    closeMarkdownDrawer,
    openHistoryTrend,
    closeHistoryTrend,
    setStockHistoryRange,
    loadMoreStockHistory,
    stockBarItems,
    isLoadingStockBar,
    loadStockBar,
    refreshStockBar,
  } = useHomeDashboardState();

  useEffect(() => {
    if (appliedInitialHistoryCenterFiltersRef.current && !restoredHistoryCenterFiltersRef.current) {
      return;
    }
    appliedInitialHistoryCenterFiltersRef.current = true;
    restoredHistoryCenterFiltersRef.current = false;
    void setHistoryFilters(toHistoryCenterApiFilters(historyCenterFilters));
  }, [historyCenterFilters, setHistoryFilters]);

  useEffect(() => {
    document.title = t('home.pageTitle');
  }, [t]);

  useEffect(() => {
    void stocksApi.prewarm(['600519', 'AAPL', 'HK00700', 'BTC-USD']).catch(() => undefined);
  }, []);

  const loadPlatformWatchlist = useCallback(async () => {
    try {
      const list = await platformApi.watchlist();
      setPlatformWatchlist(list);
      setPlatformWatchlistError('');
    } catch {
      setPlatformWatchlist(null);
    }
  }, []);

  const loadPlatformAccount = useCallback(async (session: PlatformAuthPayload | null) => {
    if (!session) {
      setPlatformSession(null);
      setPlatformAccount(null);
      setPlatformKeys([]);
      setPlatformWatchlist(null);
      setPlatformWatchlistRefresh(null);
      setPlatformWatchlistError('');
      setApiKeyMode('platform');
      return;
    }

    setPlatformSession(session);
    try {
      const account = await platformApi.account();
      setPlatformAccount(account);
      setPlatformSession({ user: account.user, quota: account.quota });
      setPlatformKeys(account.apiKeys);
    } catch {
      setPlatformAccount(null);
      setPlatformKeys(await platformApi.listApiKeys());
    }
    await loadPlatformWatchlist();
  }, [loadPlatformWatchlist, setApiKeyMode]);

  const refreshPlatformSession = useCallback(async () => {
    const session = await platformApi.current();
    await loadPlatformAccount(session);
  }, [loadPlatformAccount]);

  useEffect(() => {
    let active = true;
    platformApi.status()
      .then(async (status) => {
        if (!active) return;
        setPlatformEnabled(status.platformAuthEnabled);
        if (status.platformAuthEnabled) {
          await refreshPlatformSession();
        }
      })
      .catch(() => {
        if (active) {
          setPlatformEnabled(false);
        }
      });

    return () => {
      active = false;
    };
  }, [refreshPlatformSession]);

  const handlePlatformAuth = useCallback(async () => {
    setAuthBusy(true);
    setAuthError('');
    try {
      const payload = authMode === 'register'
        ? await platformApi.register(authEmail.trim(), authPassword)
        : await platformApi.login(authEmail.trim(), authPassword);
      await loadPlatformAccount(payload);
      setAuthPassword('');
      resetDashboardState();
      await Promise.all([
        loadInitialHistory(),
        loadStockBar(),
        loadMarketReviewHistory(),
        refreshActiveTasks(),
      ]);
    } catch (err: unknown) {
      setAuthError(getParsedApiError(err).message || '账号登录失败');
    } finally {
      setAuthBusy(false);
    }
  }, [authEmail, authMode, authPassword, loadInitialHistory, loadMarketReviewHistory, loadPlatformAccount, loadStockBar, refreshActiveTasks, resetDashboardState]);

  const handlePlatformLogout = useCallback(async () => {
    await platformApi.logout();
    setPlatformSession(null);
    setPlatformAccount(null);
    setPlatformKeys([]);
    setPlatformWatchlist(null);
    setPlatformWatchlistRefresh(null);
    setPlatformWatchlistError('');
    setApiKeyMode('platform');
    resetDashboardState();
  }, [resetDashboardState, setApiKeyMode]);

  const handleSaveApiKey = useCallback(async () => {
    const secret = apiKeyDraft.trim();
    if (!secret) return;
    setApiKeySaving(true);
    try {
      await platformApi.saveApiKey({
        provider: apiKeyProvider,
        apiKey: secret,
        model: apiKeyModel.trim() || undefined,
      });
      setApiKeyDraft('');
      if (platformSession) {
        await loadPlatformAccount(platformSession);
      } else {
        setPlatformKeys(await platformApi.listApiKeys());
      }
      setApiKeyMode('user');
    } finally {
      setApiKeySaving(false);
    }
  }, [apiKeyDraft, apiKeyModel, apiKeyProvider, loadPlatformAccount, platformSession, setApiKeyMode]);

  const handleAddCurrentQueryToPlatformWatchlist = useCallback(async () => {
    const target = query.trim();
    if (!target || platformWatchlistBusy) {
      return;
    }
    setPlatformWatchlistBusy(true);
    setPlatformWatchlistError('');
    try {
      const list = await platformApi.addWatchlistItem(target);
      setPlatformWatchlist(list);
      setPlatformWatchlistRefresh(null);
    } catch (err: unknown) {
      setPlatformWatchlistError(getParsedApiError(err).message || 'Watchlist update failed');
    } finally {
      setPlatformWatchlistBusy(false);
    }
  }, [platformWatchlistBusy, query]);

  const handleRefreshPlatformWatchlist = useCallback(async () => {
    if (platformWatchlistBusy) {
      return;
    }
    setPlatformWatchlistBusy(true);
    setPlatformWatchlistError('');
    try {
      const summary = await platformApi.refreshWatchlist();
      setPlatformWatchlistRefresh(summary);
    } catch (err: unknown) {
      setPlatformWatchlistError(getParsedApiError(err).message || 'Watchlist refresh failed');
    } finally {
      setPlatformWatchlistBusy(false);
    }
  }, [platformWatchlistBusy]);

  useEffect(() => {
    let active = true;
    systemConfigApi.getSetupStatus()
      .then((status) => {
        if (active) {
          setSetupStatus(status);
        }
      })
      .catch(() => {
        if (active) {
          setSetupStatus(null);
        }
      });

    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    let active = true;
    agentApi.getSkills()
      .then((response) => {
        if (active) {
          setAnalysisSkills(response.skills);
        }
      })
      .catch(() => {
        if (active) {
          setAnalysisSkills([]);
        }
      });

    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    if (!strategyMenuOpen) {
      return;
    }

    const handlePointerDown = (event: MouseEvent) => {
      const target = event.target;
      if (target instanceof Node && strategyMenuRef.current?.contains(target)) {
        return;
      }
      setStrategyMenuOpen(false);
    };

    document.addEventListener('mousedown', handlePointerDown);
    return () => document.removeEventListener('mousedown', handlePointerDown);
  }, [strategyMenuOpen]);

  useEffect(() => {
    if (selectedStrategyId && !analysisSkills.some((skill) => skill.id === selectedStrategyId)) {
      setSelectedStrategyId('');
    }
  }, [analysisSkills, selectedStrategyId]);

  const reportLanguage = normalizeReportLanguage(selectedReport?.meta.reportLanguage);
  const liveMarketReviewLanguage = normalizeReportLanguage(marketReviewPayload?.language);
  const isMarketReviewHistoryReport = selectedReport?.meta.reportType === 'market_review';
  const isHistoryTrendUnavailable = !selectedReport || !selectedReport.meta.stockCode;
  const selectedHistoryStateItem = useMemo(() => {
    const recordId = selectedReport?.meta.id;
    if (recordId === undefined) {
      return undefined;
    }
    return [...historyItems, ...marketReviewHistoryItems, ...stockHistoryItems]
      .find((item) => item.id === recordId);
  }, [historyItems, marketReviewHistoryItems, selectedReport?.meta.id, stockHistoryItems]);
  const selectedHistoryState = {
    favorite: Boolean(selectedHistoryStateItem?.favorite),
    important: Boolean(selectedHistoryStateItem?.important),
    archived: Boolean(selectedHistoryStateItem?.archived),
    read: Boolean(selectedHistoryStateItem?.read),
    note: selectedHistoryStateItem?.note ?? '',
  };

  useEffect(() => {
    setHistoryStateNoteDraft(selectedHistoryState.note);
    setHistoryStateStatus('');
  }, [selectedReport?.meta.id, selectedHistoryState.note]);

  useEffect(() => {
    setHistoryReportSearch('');
    setHistoryReportMatchIndex(0);
    setHistoryReportSectionStatus('');
  }, [selectedReport?.meta.id]);

  const historyReportSearchSegments = useMemo(
    () => collectHistoryReportSearchSegments(selectedReport),
    [selectedReport],
  );
  const historyReportSearchMatches = useMemo(() => {
    const needle = historyReportSearch.trim().toLowerCase();
    if (!needle) {
      return [];
    }
    return historyReportSearchSegments.filter((segment) => segment.text.toLowerCase().includes(needle));
  }, [historyReportSearch, historyReportSearchSegments]);

  useEffect(() => {
    if (historyReportMatchIndex >= historyReportSearchMatches.length) {
      setHistoryReportMatchIndex(0);
    }
  }, [historyReportMatchIndex, historyReportSearchMatches.length]);

  const activeHistoryReportMatch = historyReportSearchMatches[historyReportMatchIndex];

  const historyReportSectionPrefix = selectedReport?.meta.id !== undefined
    ? `history-report-${selectedReport.meta.id}`
    : 'history-report-current';

  const handleHistoryReportJump = useCallback((sectionId: string, label: string) => {
    setHistoryReportSectionStatus(label);
    const target = document.getElementById(`${historyReportSectionPrefix}-${sectionId}`);
    if (typeof target?.scrollIntoView === 'function') {
      target.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  }, [historyReportSectionPrefix]);

  const sameStockTimelineItems = useMemo<HistoryItem[]>(() => {
    if (!selectedReport || selectedReport.meta.reportType === 'market_review' || selectedReport.meta.id === undefined) {
      return [];
    }
    const selectedCode = normalizeTimelineCode(selectedReport.meta.stockCode);
    if (!selectedCode) {
      return [];
    }
    const byId = new Map<number, HistoryItem>();
    const addItem = (item: HistoryItem) => {
      if (normalizeTimelineCode(item.stockCode) === selectedCode) {
        byId.set(item.id, item);
      }
    };
    historyItems.forEach(addItem);
    const selectedRecordId = selectedReport.meta.id;
    if (!byId.has(selectedRecordId)) {
      byId.set(selectedRecordId, {
        id: selectedRecordId,
        queryId: selectedReport.meta.queryId,
        stockCode: selectedReport.meta.stockCode,
        stockName: selectedReport.meta.stockName,
        reportType: selectedReport.meta.reportType,
        trendPrediction: selectedReport.summary.trendPrediction,
        analysisSummary: selectedReport.summary.analysisSummary,
        sentimentScore: selectedReport.summary.sentimentScore,
        operationAdvice: selectedReport.summary.operationAdvice,
        createdAt: selectedReport.meta.createdAt,
      });
    }
    return Array.from(byId.values())
      .sort((left, right) => String(right.createdAt || '').localeCompare(String(left.createdAt || '')))
      .slice(0, 6);
  }, [historyItems, selectedReport]);

  useEffect(() => {
    if (!isHistoryTrendUnavailable || !isHistoryTrendOpen) {
      return;
    }
    closeHistoryTrend();
  }, [closeHistoryTrend, isHistoryTrendOpen, isHistoryTrendUnavailable]);

  const selectedStrategy = useMemo(
    () => analysisSkills.find((skill) => skill.id === selectedStrategyId),
    [analysisSkills, selectedStrategyId],
  );
  const hasUserApiKey = platformKeys.some((key) => key.enabled);
  const quotaText = platformSession
    ? platformSession.quota.weeklyLimit === null
      ? `${platformSession.quota.used}/∞`
      : `${platformSession.quota.remaining ?? 0}/${platformSession.quota.weeklyLimit}`
    : '';
  const handleApiKeyModeChange = useCallback((mode: ApiKeyMode) => {
    setApiKeyMode(mode);
  }, [setApiKeyMode]);
  const primaryApiKey = platformKeys.find((key) => key.enabled);
  const baseQuota = platformAccount?.quota ?? platformSession?.quota ?? null;
  const basicQueryQuota = platformAccount?.quotaBuckets.find((bucket) => bucket.quotaBucket === 'basic_query');
  const accountQuotaText = platformSession ? formatQuotaLeft(baseQuota) : 'unavailable';
  const basicQuotaText = basicQueryQuota ? formatQuotaLeft(basicQueryQuota) : 'unmetered locally';
  const byokStatusText = primaryApiKey
    ? `BYOK ready ${primaryApiKey.maskedKey}`
    : 'BYOK not set';
  const recommendedModeText = `Recommended ${apiKeyModeLabel(platformAccount?.recommendedQueryMode)}`;
  const basicSnapshotLane = basicSnapshot?.route?.dataSourceLane || basicSnapshot?.diagnostics?.routeLane || null;
  const basicSnapshotCacheMode = basicSnapshot?.diagnostics?.persistentCache?.mode;
  const basicQuoteDetailItems = useMemo(() => {
    if (!basicSnapshot) {
      return [];
    }
    const isEnglish = uiLanguage === 'en';
    return [
      { label: isEnglish ? 'Open' : '开盘', value: formatBasicNumber(basicSnapshot.quote.open) },
      { label: isEnglish ? 'High' : '最高', value: formatBasicNumber(basicSnapshot.quote.high) },
      { label: isEnglish ? 'Low' : '最低', value: formatBasicNumber(basicSnapshot.quote.low) },
      { label: isEnglish ? 'Prev close' : '昨收', value: formatBasicNumber(basicSnapshot.quote.prevClose) },
      { label: isEnglish ? 'Change' : '涨跌额', value: formatBasicNumber(basicSnapshot.quote.change) },
      { label: isEnglish ? 'Volume' : '成交量', value: formatBasicCompactNumber(basicSnapshot.quote.volume) },
      { label: isEnglish ? 'Turnover' : '成交额', value: formatBasicCompactNumber(basicSnapshot.quote.amount) },
      { label: isEnglish ? 'Updated' : '更新时间', value: basicSnapshot.quote.updateTime || '-' },
    ];
  }, [basicSnapshot, uiLanguage]);
  const basicTechnicalDetailItems = useMemo(() => {
    if (!basicSnapshot) {
      return [];
    }
    const isEnglish = uiLanguage === 'en';
    const indicators = basicSnapshot.indicators || {};
    return [
      { label: 'MA5', value: formatBasicNumber(indicators['ma5']) },
      { label: 'MA10', value: formatBasicNumber(indicators['ma10']) },
      { label: 'MA20', value: formatBasicNumber(indicators['ma20']) },
      { label: isEnglish ? '5d change' : '5日涨跌', value: formatBasicPercent(pickBasicIndicator(indicators, 'priceChange5D', 'priceChange5d', 'price_change_5d')) },
      { label: isEnglish ? '20d change' : '20日涨跌', value: formatBasicPercent(pickBasicIndicator(indicators, 'priceChange20D', 'priceChange20d', 'price_change_20d')) },
      { label: isEnglish ? 'Volume vs MA5' : '量能变化', value: formatBasicPercent(pickBasicIndicator(indicators, 'volumeChangeVsMa5', 'volume_change_vs_ma5')) },
      { label: isEnglish ? 'Volume MA5' : '5日均量', value: formatBasicCompactNumber(pickBasicIndicator(indicators, 'volumeMa5', 'volume_ma5')) },
      { label: isEnglish ? 'Price-volume signal' : '量价信号', value: volumePriceSignalLabel(pickBasicIndicator(indicators, 'volumePriceSignal', 'volume_price_signal'), uiLanguage) },
    ];
  }, [basicSnapshot, uiLanguage]);
  const platformWatchlistItems = platformWatchlist?.items ?? [];
  const platformWatchlistPreview = platformWatchlistItems.slice(0, 6);
  const platformWatchlistBoardItems = platformWatchlistRefresh?.items ?? [];
  const platformWatchlistCount = platformWatchlist?.total ?? platformWatchlistItems.length;
  const workspaceHistoryCountText = `${stockHistoryTotal ?? 0} reports`;
  const workspaceAiModeText = apiKeyMode === 'user'
    ? 'Selected BYOK'
    : apiKeyMode === 'local'
      ? 'Selected local model'
      : 'Selected Platform API';
  const workspaceByokText = primaryApiKey ? 'BYOK ready' : 'BYOK not set';
  const platformWatchlistLanes = Array.from(
    new Set((platformWatchlistRefresh?.items ?? []).map((item) => item.routeLane).filter(Boolean)),
  );
  const selectedAnalysisSkills = useMemo(
    () => (selectedStrategyId ? [selectedStrategyId] : undefined),
    [selectedStrategyId],
  );
  const strategyOptions = useMemo(
    () => [
      { id: '', name: t('home.defaultStrategyName'), description: t('home.defaultStrategyDescription') },
      ...analysisSkills.map((skill) => ({
        id: skill.id,
        name: skill.name,
        description: skill.description,
      })),
    ],
    [analysisSkills, t],
  );
  const closeStrategyMenu = useCallback((restoreFocus = false) => {
    setStrategyMenuOpen(false);
    if (restoreFocus) {
      strategyButtonRef.current?.focus();
    }
  }, []);
  const selectStrategy = useCallback((strategyId: string) => {
    setSelectedStrategyId(strategyId);
    setStrategyMenuOpen(false);
  }, []);
  const focusStrategyItem = useCallback((index: number) => {
    const itemCount = strategyOptions.length;
    if (itemCount === 0) {
      return;
    }
    const nextIndex = (index + itemCount) % itemCount;
    strategyItemRefs.current[nextIndex]?.focus();
  }, [strategyOptions.length]);
  const getSelectedStrategyIndex = useCallback(() => {
    const selectedIndex = strategyOptions.findIndex((option) => option.id === selectedStrategyId);
    return selectedIndex >= 0 ? selectedIndex : 0;
  }, [selectedStrategyId, strategyOptions]);
  useEffect(() => {
    strategyItemRefs.current = strategyItemRefs.current.slice(0, strategyOptions.length);
  }, [strategyOptions.length]);
  useEffect(() => {
    if (!strategyMenuOpen) {
      return undefined;
    }

    const targetIndex = strategyInitialFocusIndexRef.current ?? getSelectedStrategyIndex();
    strategyInitialFocusIndexRef.current = null;
    const timeout = window.setTimeout(() => focusStrategyItem(targetIndex), 0);
    return () => window.clearTimeout(timeout);
  }, [focusStrategyItem, getSelectedStrategyIndex, strategyMenuOpen]);
  const handleStrategyButtonKeyDown = useCallback((event: React.KeyboardEvent<HTMLButtonElement>) => {
    if (event.key !== 'ArrowDown' && event.key !== 'ArrowUp') {
      return;
    }

    event.preventDefault();
    const targetIndex = event.key === 'ArrowUp' ? strategyOptions.length - 1 : 0;
    if (strategyMenuOpen) {
      focusStrategyItem(targetIndex);
      return;
    }
    strategyInitialFocusIndexRef.current = targetIndex;
    setStrategyMenuOpen(true);
  }, [focusStrategyItem, strategyMenuOpen, strategyOptions.length]);
  const handleStrategyMenuKeyDown = useCallback((event: React.KeyboardEvent<HTMLDivElement>) => {
    const itemCount = strategyOptions.length;
    if (itemCount === 0) {
      return;
    }

    const currentIndex = strategyItemRefs.current.findIndex((item) => item === document.activeElement);
    switch (event.key) {
      case 'Escape':
        event.preventDefault();
        closeStrategyMenu(true);
        break;
      case 'ArrowDown':
        event.preventDefault();
        focusStrategyItem(currentIndex >= 0 ? currentIndex + 1 : 0);
        break;
      case 'ArrowUp':
        event.preventDefault();
        focusStrategyItem(currentIndex >= 0 ? currentIndex - 1 : itemCount - 1);
        break;
      case 'Home':
        event.preventDefault();
        focusStrategyItem(0);
        break;
      case 'End':
        event.preventDefault();
        focusStrategyItem(itemCount - 1);
        break;
      case 'Tab':
        setStrategyMenuOpen(false);
        break;
      default:
        break;
    }
  }, [closeStrategyMenu, focusStrategyItem, strategyOptions.length]);
  const setupNeedsAction = setupStatus ? !setupStatus.isComplete : false;
  const setupMissingLabels = useMemo(() => {
    if (!setupStatus) {
      return '';
    }
    const requiredNeedsAction = setupStatus.checks
      .filter((check) => check.required && check.status === 'needs_action')
      .map((check) => check.title);
    return requiredNeedsAction.slice(0, 3).join(uiLanguage === 'en' ? ', ' : '、');
  }, [setupStatus, uiLanguage]);

  useDashboardLifecycle({
    loadInitialHistory,
    refreshHistory,
    loadMarketReviewHistory,
    refreshMarketReviewHistory,
    loadStockBar,
    refreshStockBar,
    syncTaskCreated,
    syncTaskUpdated,
    syncTaskFailed,
    refreshActiveTasks,
    removeTask,
  });

  const watchlistState = useWatchlist();

  const clearMarketReviewState = useCallback(() => {
    stopMarketReviewPolling();
    setMarketReviewReport(null);
    setMarketReviewPayload(null);
    setMarketReviewNotice(null);
    setMarketReviewError(null);
  }, [stopMarketReviewPolling]);

  const handleBasicQuery = useCallback(async (stockCode?: string, _stockName?: string, forceRefresh = false) => {
    const target = (stockCode || query).trim();
    if (!target || isQueryingBasic) {
      return null;
    }

    setIsQueryingBasic(true);
    setBasicQueryError(null);
    if (!forceRefresh) {
      setBasicSnapshot(null);
    }
    clearMarketReviewState();
    if (stockCode) {
      setQuery(stockCode);
    }

    try {
      const snapshot = forceRefresh
        ? await stocksApi.snapshot(target, { refresh: true })
        : await stocksApi.snapshot(target);
      setBasicSnapshot(snapshot);
      return snapshot;
    } catch (err: unknown) {
      setBasicQueryError(getParsedApiError(err));
      return null;
    } finally {
      setIsQueryingBasic(false);
    }
  }, [clearMarketReviewState, isQueryingBasic, query, setQuery]);

  const markHistoryRecordRefreshed = useCallback((recordId?: number) => {
    if (typeof recordId !== 'number') {
      return;
    }
    setRefreshedHistoryRecordIds((current) => {
      const next = new Set(current);
      next.add(recordId);
      return next;
    });
  }, []);

  const handleRefreshCurrentQuoteFromHistory = useCallback(async () => {
    if (!selectedReport || selectedReport.meta.reportType === 'market_review') {
      return;
    }
    const refreshed = await handleBasicQuery(
      selectedReport.meta.stockCode,
      selectedReport.meta.stockName || undefined,
      true,
    );
    if (refreshed && typeof selectedReport.meta.id === 'number') {
      await historyApi.markCurrentQuoteRefreshed(selectedReport.meta.id, {
        stockCode: refreshed.stockCode || selectedReport.meta.stockCode,
        routeLane: refreshed.route?.dataSourceLane || refreshed.diagnostics?.routeLane || null,
        quoteSource: refreshed.quote?.source || refreshed.diagnostics?.sources?.quote || null,
        freshness: refreshed.quote?.freshness || refreshed.diagnostics?.freshness?.quote || null,
        aiUsed: refreshed.aiUsed ?? false,
        metadata: {
          market: refreshed.market,
          refreshMode: refreshed.diagnostics?.refresh?.mode,
        },
      });
      markHistoryRecordRefreshed(selectedReport.meta.id);
      await refreshHistory(true);
    }
  }, [handleBasicQuery, markHistoryRecordRefreshed, refreshHistory, selectedReport]);

  const handleHistoryItemClick = useCallback((recordId: number) => {
    clearMarketReviewState();
    setBasicSnapshot(null);
    setBasicQueryError(null);
    void selectHistoryItem(recordId);
    setSidebarOpen(false);
  }, [clearMarketReviewState, selectHistoryItem]);

  const [isDeletingStock, setIsDeletingStock] = useState(false);
  const handleDeleteStock = useCallback(async (stockCode: string) => {
    if (isDeletingStock) return;
    setIsDeletingStock(true);
    try {
      await historyApi.deleteByCode(stockCode);
      await refreshStockBar();
      await refreshHistory(true);
      if (stockCode === 'MARKET') {
        await refreshMarketReviewHistory(false);
      }
    } catch {
      // error silently ignored
    } finally {
      setIsDeletingStock(false);
    }
  }, [isDeletingStock, refreshMarketReviewHistory, refreshStockBar, refreshHistory]);

  const updateHistoryCenterFilter = useCallback((key: keyof HistoryCenterFilters, value: string) => {
    const next = {
      ...historyCenterFilters,
      [key]: value,
    } as HistoryCenterFilters;
    setHistoryCenterFilters(next);
    persistHistoryCenterFilters(next);
    void setHistoryFilters(toHistoryCenterApiFilters(next));
  }, [historyCenterFilters, setHistoryFilters]);

  const resetHistoryCenterFilters = useCallback(() => {
    setHistoryCenterFilters(DEFAULT_HISTORY_CENTER_FILTERS);
    persistHistoryCenterFilters(DEFAULT_HISTORY_CENTER_FILTERS);
    void setHistoryFilters(toHistoryCenterApiFilters(DEFAULT_HISTORY_CENTER_FILTERS));
  }, [setHistoryFilters]);

  const historyCenterItems = historyItems;

  const handleExportSelectedHistory = useCallback(async () => {
    const recordIds = Array.from(selectedIds).sort((left, right) => left - right);
    if (recordIds.length === 0 || isExportingHistory) {
      return;
    }

    setIsExportingHistory(true);
    setHistoryExportStatus('');
    try {
      const bundle = await historyApi.exportReports(recordIds, 'markdown');
      downloadTextFile(bundle.filename, bundle.content, 'text/markdown;charset=utf-8');
      setHistoryExportStatus(`Exported ${bundle.recordCount} local reports`);
    } catch (exportError) {
      const parsed = getParsedApiError(exportError);
      setHistoryExportStatus(parsed.message || 'History export failed');
    } finally {
      setIsExportingHistory(false);
    }
  }, [isExportingHistory, selectedIds]);

  const handleBatchHistoryState = useCallback(async (
    payload: Omit<HistoryStateUpdatePayload, 'note'>,
    successLabel: string,
  ) => {
    const recordIds = Array.from(selectedIds).sort((left, right) => left - right);
    if (recordIds.length === 0 || isUpdatingHistoryState) {
      return;
    }

    setIsUpdatingHistoryState(true);
    setHistoryStateStatus('');
    try {
      const result = await historyApi.batchUpdateState(recordIds, payload);
      setHistoryStateStatus(`${successLabel} ${result.updated} local reports`);
      await refreshHistory(true);
      if (historyCenterFilters.reportType === 'market_review') {
        await refreshMarketReviewHistory(false);
      }
    } catch (stateError) {
      const parsed = getParsedApiError(stateError);
      setHistoryStateStatus(parsed.message || 'History state update failed');
    } finally {
      setIsUpdatingHistoryState(false);
    }
  }, [
    historyCenterFilters.reportType,
    isUpdatingHistoryState,
    refreshHistory,
    refreshMarketReviewHistory,
    selectedIds,
  ]);

  const handleUpdateSelectedHistoryState = useCallback(async (payload: HistoryStateUpdatePayload) => {
    const recordId = selectedReport?.meta.id;
    if (recordId === undefined || isUpdatingHistoryState) {
      return;
    }

    setIsUpdatingHistoryState(true);
    setHistoryStateStatus('');
    try {
      await historyApi.updateState(recordId, payload);
      setHistoryStateStatus('Saved local history state');
      await refreshHistory(true);
      if (selectedReport?.meta.reportType === 'market_review') {
        await refreshMarketReviewHistory(false);
      }
    } catch (stateError) {
      const parsed = getParsedApiError(stateError);
      setHistoryStateStatus(parsed.message || 'History state update failed');
    } finally {
      setIsUpdatingHistoryState(false);
    }
  }, [
    isUpdatingHistoryState,
    refreshHistory,
    refreshMarketReviewHistory,
    selectedReport?.meta.id,
    selectedReport?.meta.reportType,
  ]);

  const historyCenterControls = useMemo(() => {
    const selectClass = 'h-8 min-w-0 rounded-lg border border-subtle bg-surface px-2 text-[11px] text-foreground';
    const textClass = 'h-8 min-w-0 rounded-lg border border-subtle bg-surface px-2 text-[11px] text-foreground placeholder:text-muted-text';
    const selectedCount = selectedIds.size;

    return (
      <div className="space-y-2">
        <div data-testid="history-center-filters" className="grid grid-cols-2 gap-2 text-[11px]">
          <label className="col-span-2 flex min-w-0 items-center gap-1.5 rounded-lg border border-subtle bg-surface px-2">
            <Search className="h-3.5 w-3.5 flex-shrink-0 text-muted-text" aria-hidden="true" />
            <span className="sr-only">Filter history by code or name</span>
            <input
              type="search"
              value={historyCenterFilters.code}
              onChange={(event) => updateHistoryCenterFilter('code', event.target.value)}
              data-testid="history-center-code-filter"
              placeholder="Code or name"
              className="h-8 min-w-0 flex-1 bg-transparent text-[11px] text-foreground outline-none placeholder:text-muted-text"
            />
          </label>
          <label className="col-span-2 flex min-w-0 items-center gap-1.5 rounded-lg border border-subtle bg-surface px-2">
            <Search className="h-3.5 w-3.5 flex-shrink-0 text-muted-text" aria-hidden="true" />
            <span className="sr-only">Filter history by local note</span>
            <input
              type="search"
              value={historyCenterFilters.noteSearch}
              onChange={(event) => updateHistoryCenterFilter('noteSearch', event.target.value)}
              data-testid="history-center-note-filter"
              placeholder="Search local notes"
              className="h-8 min-w-0 flex-1 bg-transparent text-[11px] text-foreground outline-none placeholder:text-muted-text"
            />
          </label>
          <select
            value={historyCenterFilters.market}
            onChange={(event) => updateHistoryCenterFilter('market', event.target.value)}
            data-testid="history-center-market-filter"
            aria-label="Filter history by market"
            className={selectClass}
          >
            <option value="all">All markets</option>
            <option value="cn">A-share</option>
            <option value="us">US</option>
            <option value="hk">HK</option>
            <option value="crypto">Crypto</option>
          </select>
          <select
            value={historyCenterFilters.reportType}
            onChange={(event) => updateHistoryCenterFilter('reportType', event.target.value)}
            data-testid="history-center-report-type-filter"
            aria-label="Filter history by report type"
            className={selectClass}
          >
            <option value="all">All stock reports</option>
            <option value="simple">Simple</option>
            <option value="detailed">Detailed</option>
            <option value="full">Full</option>
            <option value="brief">Brief</option>
            <option value="market_review">Market review</option>
          </select>
          <select
            value={historyCenterFilters.range}
            onChange={(event) => updateHistoryCenterFilter('range', event.target.value)}
            data-testid="history-center-range-filter"
            aria-label="Filter history by generated time range"
            className={selectClass}
          >
            <option value="all">Any time</option>
            <option value="7d">Last 7d</option>
            <option value="30d">Last 30d</option>
            <option value="90d">Last 90d</option>
          </select>
          <select
            value={historyCenterFilters.sort}
            onChange={(event) => updateHistoryCenterFilter('sort', event.target.value)}
            data-testid="history-center-time-filter"
            aria-label="Sort history by generated time"
            className={selectClass}
          >
            <option value="newest">Newest first</option>
            <option value="oldest">Oldest first</option>
          </select>
          <select
            value={historyCenterFilters.refreshStatus}
            onChange={(event) => updateHistoryCenterFilter('refreshStatus', event.target.value)}
            data-testid="history-center-refresh-filter"
            aria-label="Filter history by current quote refresh status"
            className={selectClass}
          >
            <option value="all">All refresh states</option>
            <option value="refreshed">Refreshed current quote</option>
            <option value="not_refreshed">Not refreshed</option>
          </select>
          <select
            value={historyCenterFilters.state}
            onChange={(event) => updateHistoryCenterFilter('state', event.target.value)}
            data-testid="history-center-state-filter"
            aria-label="Filter history by local state"
            className={selectClass}
          >
            <option value="all">All report states</option>
            <option value="favorite">Favorite</option>
            <option value="important">Important</option>
            <option value="active">Active</option>
            <option value="archived">Archived</option>
            <option value="has_note">Has note</option>
            <option value="unread">Unread</option>
            <option value="read">Read</option>
          </select>
          <button
            type="button"
            onClick={resetHistoryCenterFilters}
            data-testid="history-center-reset-filters"
            className={`${textClass} inline-flex items-center justify-center font-medium text-secondary-text hover:text-foreground`}
          >
            Reset filters
          </button>
        </div>
        <div className="flex flex-wrap items-center gap-2 text-[11px]">
          <button
            type="button"
            onClick={() => void handleExportSelectedHistory()}
            disabled={selectedCount === 0 || isExportingHistory}
            data-testid="history-center-export-selected"
            className="inline-flex h-8 min-w-0 items-center justify-center gap-1.5 rounded-lg border border-subtle bg-surface px-2 font-medium text-secondary-text hover:text-foreground disabled:cursor-not-allowed disabled:opacity-50"
          >
            <Download className="h-3.5 w-3.5 flex-shrink-0" aria-hidden="true" />
            {isExportingHistory ? 'Exporting' : 'Export selected'}
          </button>
          <button
            type="button"
            onClick={() => void handleBatchHistoryState({ important: true }, 'Marked important')}
            disabled={selectedCount === 0 || isUpdatingHistoryState}
            data-testid="history-center-important-selected"
            className="inline-flex h-8 min-w-0 items-center justify-center gap-1.5 rounded-lg border border-subtle bg-surface px-2 font-medium text-secondary-text hover:text-foreground disabled:cursor-not-allowed disabled:opacity-50"
          >
            <Flag className="h-3.5 w-3.5 flex-shrink-0" aria-hidden="true" />
            Important
          </button>
          <button
            type="button"
            onClick={() => void handleBatchHistoryState({ read: true }, 'Marked read')}
            disabled={selectedCount === 0 || isUpdatingHistoryState}
            data-testid="history-center-read-selected"
            className="inline-flex h-8 min-w-0 items-center justify-center gap-1.5 rounded-lg border border-subtle bg-surface px-2 font-medium text-secondary-text hover:text-foreground disabled:cursor-not-allowed disabled:opacity-50"
          >
            <Eye className="h-3.5 w-3.5 flex-shrink-0" aria-hidden="true" />
            Mark read
          </button>
          <button
            type="button"
            onClick={() => void handleBatchHistoryState({ archived: true }, 'Archived')}
            disabled={selectedCount === 0 || isUpdatingHistoryState}
            data-testid="history-center-archive-selected"
            className="inline-flex h-8 min-w-0 items-center justify-center gap-1.5 rounded-lg border border-subtle bg-surface px-2 font-medium text-secondary-text hover:text-foreground disabled:cursor-not-allowed disabled:opacity-50"
          >
            <Archive className="h-3.5 w-3.5 flex-shrink-0" aria-hidden="true" />
            {isUpdatingHistoryState ? 'Updating' : 'Archive'}
          </button>
          <button
            type="button"
            onClick={() => void handleBatchHistoryState({ archived: false }, 'Unarchived')}
            disabled={selectedCount === 0 || isUpdatingHistoryState}
            data-testid="history-center-unarchive-selected"
            className="inline-flex h-8 min-w-0 items-center justify-center gap-1.5 rounded-lg border border-subtle bg-surface px-2 font-medium text-secondary-text hover:text-foreground disabled:cursor-not-allowed disabled:opacity-50"
          >
            <ArchiveRestore className="h-3.5 w-3.5 flex-shrink-0" aria-hidden="true" />
            Restore
          </button>
          {historyExportStatus ? (
            <span data-testid="history-center-export-status" className="min-w-0 flex-1 text-muted-text">
              {historyExportStatus}
            </span>
          ) : null}
          {historyStateStatus ? (
            <span data-testid="history-center-state-status" className="min-w-0 flex-1 text-muted-text">
              {historyStateStatus}
            </span>
          ) : null}
        </div>
      </div>
    );
  }, [
    handleBatchHistoryState,
    handleExportSelectedHistory,
    historyCenterFilters,
    historyExportStatus,
    isExportingHistory,
    isUpdatingHistoryState,
    resetHistoryCenterFilters,
    selectedIds,
    historyStateStatus,
    updateHistoryCenterFilter,
  ]);

  const handleSubmitAnalysis = useCallback(
    (
      stockCode?: string,
      stockName?: string,
      selectionSource?: 'manual' | 'autocomplete' | 'import' | 'image',
      analysisDepth: AnalysisDepth = 'fast',
    ) => {
      void submitAnalysis({
        stockCode,
        stockName,
        originalQuery: query,
        selectionSource: selectionSource ?? 'manual',
        skills: selectedAnalysisSkills,
        analysisDepth,
      });
    },
    [query, selectedAnalysisSkills, submitAnalysis],
  );

  useEffect(() => {
    const state = location.state as StockAnalysisNavigationState | null;
    const stockCode = typeof state?.stockCode === 'string' ? state.stockCode.trim() : '';
    if (!stockCode) {
      return;
    }
    const stockName = typeof state?.stockName === 'string' ? state.stockName.trim() : '';
    setQuery(stockCode);
    navigate(location.pathname, { replace: true, state: null });
    if (state?.autoAnalyze) {
      handleSubmitAnalysis(stockCode, stockName || undefined, 'import');
    }
  }, [handleSubmitAnalysis, location.pathname, location.state, navigate, setQuery]);

  const handleAskFollowUp = useCallback(() => {
    if (selectedReport?.meta.id === undefined || selectedReport.meta.reportType === 'market_review') {
      return;
    }

    const code = selectedReport.meta.stockCode;
    const name = selectedReport.meta.stockName;
    const rid = selectedReport.meta.id;
    navigate(`/chat?stock=${encodeURIComponent(code)}&name=${encodeURIComponent(name)}&recordId=${rid}`);
  }, [navigate, selectedReport]);

  const handleReanalyze = useCallback(() => {
    if (!selectedReport || selectedReport.meta.reportType === 'market_review') {
      return;
    }

    void submitAnalysis({
      stockCode: selectedReport.meta.stockCode,
      stockName: selectedReport.meta.stockName,
      originalQuery: selectedReport.meta.stockCode,
      selectionSource: 'manual',
      forceRefresh: true,
      skills: selectedAnalysisSkills,
    });
  }, [selectedAnalysisSkills, selectedReport, submitAnalysis]);

  const openTaskRunFlow = useCallback((task: TaskInfo) => {
    const stock = task.stockName || task.stockCode || task.taskId;
    setRunFlowDrawer({
      open: true,
      source: { type: 'task', taskId: task.taskId },
      title: t('runFlow.taskDrawerTitle', { stock }),
    });
  }, [t]);

  const openHistoryRunFlow = useCallback((recordId: number) => {
    const meta = selectedReport?.meta.id === recordId ? selectedReport.meta : null;
    const stock = meta?.stockName || meta?.stockCode || String(recordId);
    setRunFlowDrawer({
      open: true,
      source: { type: 'history', recordId },
      title: t('runFlow.historyDrawerTitle', { stock }),
    });
  }, [selectedReport, t]);

  const closeRunFlowDrawer = useCallback(() => {
    setRunFlowDrawer({ open: false });
  }, []);

  const pollMarketReviewStatus = useCallback(
    async (taskId: string) => {
      stopMarketReviewPolling();

      const maxAttempts = 120;
      const intervalMs = 2000;
      let attempts = 0;

      const poll = async (): Promise<boolean> => {
        if (attempts >= maxAttempts) {
          stopMarketReviewPolling();
          setMarketReviewReport(null);
          setMarketReviewPayload(null);
          setMarketReviewNotice({
            variant: 'danger',
            title: t('home.marketReviewTimeout'),
            message: t('home.marketReviewTimeoutMessage'),
          });
          scrollMarketReviewFeedbackIntoView();
          return false;
        }

        attempts += 1;

        try {
          const status = await analysisApi.getStatus(taskId);
          if (status.status === 'pending' || status.status === 'processing') {
            setMarketReviewReport(null);
            setMarketReviewPayload(null);
            const progress = typeof status.progress === 'number'
              ? `${status.progress}%`
              : t('home.progressActive');
            setMarketReviewNotice({
              variant: 'warning',
              title: t('home.marketReviewInProgress'),
              message: t('home.taskStatus', { status: status.status, progress }),
            });
            return true;
          }

          if (status.status === 'completed') {
            stopMarketReviewPolling();
            const marketReviewText = typeof status.marketReviewReport === 'string'
              ? status.marketReviewReport
              : '';
            setMarketReviewReport(marketReviewText ? marketReviewText.trim() : null);
            setMarketReviewPayload(status.marketReviewPayload ?? null);
            setMarketReviewNotice({
              variant: 'success',
              title: t('home.marketReviewCompleted'),
              message: marketReviewText ? t('home.marketReviewCompletedWithReport') : t('home.marketReviewCompletedWithoutReport'),
            });
            setMarketReviewError(null);
            await refreshMarketReviewHistory(true);
            scrollMarketReviewFeedbackIntoView();
            return false;
          }

          if (status.status === 'failed') {
            stopMarketReviewPolling();
            setMarketReviewReport(null);
            setMarketReviewPayload(null);
            setMarketReviewError(
              getParsedApiError({
                response: {
                  status: 500,
                  data: {
                    error: 'market_review_failed',
                    message: status.error || t('home.marketReviewFailed'),
                  },
                },
              }),
            );
            setMarketReviewNotice(null);
            scrollMarketReviewFeedbackIntoView();
            return false;
          }

          stopMarketReviewPolling();
          setMarketReviewReport(null);
          setMarketReviewPayload(null);
          setMarketReviewNotice({
            variant: 'danger',
            title: t('home.marketReviewUnknownStatus'),
            message: t('home.unknownTaskStatus', { status: status.status }),
          });
          scrollMarketReviewFeedbackIntoView();
          return false;
        } catch (err: unknown) {
          const parsed = getParsedApiError(err);
          if (attempts >= maxAttempts) {
            stopMarketReviewPolling();
            setMarketReviewReport(null);
            setMarketReviewPayload(null);
            setMarketReviewError(parsed);
            setMarketReviewNotice(null);
            scrollMarketReviewFeedbackIntoView();
            return false;
          }
          return true;
        }

        return true;
      };

      if (await poll()) {
        marketReviewPollTimer.current = window.setInterval(() => {
          void poll().then((shouldContinue) => {
            if (!shouldContinue) {
              stopMarketReviewPolling();
            }
          });
        }, intervalMs);
      }
    },
    [refreshMarketReviewHistory, scrollMarketReviewFeedbackIntoView, stopMarketReviewPolling, t],
  );

  const handleTriggerMarketReview = useCallback(async () => {
    setIsSubmittingMarketReview(true);
    setMarketReviewNotice(null);
    setMarketReviewError(null);
    setMarketReviewReport(null);
    setMarketReviewPayload(null);
    scrollMarketReviewFeedbackIntoView();
    try {
      const result = await analysisApi.triggerMarketReview({ sendNotification: notify });
      setMarketReviewNotice({
        variant: 'success',
        title: t('home.marketReviewSubmitted'),
        message: result.message,
      });
      scrollMarketReviewFeedbackIntoView();

      if (result.taskId) {
        await pollMarketReviewStatus(result.taskId);
      }
    } catch (err: unknown) {
      setMarketReviewError(getParsedApiError(err));
      setMarketReviewNotice(null);
      scrollMarketReviewFeedbackIntoView();
    } finally {
      setIsSubmittingMarketReview(false);
    }
  }, [notify, pollMarketReviewStatus, scrollMarketReviewFeedbackIntoView, t]);

  const mergedStockBarItems = useMemo<StockBarItem[]>(() => {
    const latestMarketReview = marketReviewHistoryItems[0];
    const stockItems = stockBarItems.filter((item) => item.stockCode !== 'MARKET');
    if (!latestMarketReview) {
      return stockItems;
    }

    const marketReviewItem: StockBarItem = {
      id: latestMarketReview.id,
      stockCode: 'MARKET',
      stockName: latestMarketReview.stockName || t('home.marketReview'),
      reportType: 'market_review',
      sentimentScore: latestMarketReview.sentimentScore,
      operationAdvice: latestMarketReview.operationAdvice,
      analysisCount: Math.max(marketReviewHistoryItems.length, 1),
      lastAnalysisTime: latestMarketReview.createdAt,
      modelUsed: latestMarketReview.modelUsed,
      marketPhaseSummary: latestMarketReview.marketPhaseSummary,
    };

    return [marketReviewItem, ...stockItems].sort((left, right) => {
      const leftTime = left.lastAnalysisTime ? Date.parse(left.lastAnalysisTime) : 0;
      const rightTime = right.lastAnalysisTime ? Date.parse(right.lastAnalysisTime) : 0;
      return rightTime - leftTime;
    });
  }, [marketReviewHistoryItems, stockBarItems, t]);

  const sidebarContent = useMemo(
    () => (
      <div className="flex min-h-0 h-full flex-col gap-3 overflow-hidden">
        <TaskPanel tasks={activeTasks} onOpenRunFlow={openTaskRunFlow} />
        <HistoryList
          title={uiLanguage === 'en' ? 'History Center' : '历史报告中心'}
          items={historyCenterItems}
          isLoading={isLoadingHistory}
          isLoadingMore={isLoadingMore}
          hasMore={hasMore && historyCenterFilters.reportType !== 'market_review'}
          selectedId={selectedReport?.meta.id}
          selectedIds={selectedIds}
          isDeleting={isDeletingHistory}
          totalCount={historyTotal}
          onItemClick={handleHistoryItemClick}
          onLoadMore={loadMoreHistory}
          onToggleItemSelection={toggleHistorySelection}
          onToggleSelectAll={toggleSelectAllVisible}
          onDeleteSelected={() => void deleteSelectedHistory()}
          controls={historyCenterControls}
          selectable
          refreshedRecordIds={refreshedHistoryRecordIds}
          emptyTitle="No matching reports"
          emptyDescription="Adjust filters or load more local history."
          className="min-h-[18rem] flex-[1.15] overflow-hidden"
        />
        <StockBar
          items={mergedStockBarItems}
          isLoading={isLoadingStockBar}
          selectedStockCode={selectedReport?.meta.stockCode}
          selectedRecordId={selectedReport?.meta.id}
          onItemClick={handleHistoryItemClick}
          onDeleteStock={handleDeleteStock}
          isDeleting={isDeletingStock}
          className="min-h-[12rem] flex-[0.85] overflow-hidden"
        />
      </div>
    ),
    [
      activeTasks,
      deleteSelectedHistory,
      handleHistoryItemClick,
      hasMore,
      historyCenterControls,
      historyCenterFilters.reportType,
      historyCenterItems,
      historyTotal,
      isDeletingHistory,
      mergedStockBarItems,
      isLoadingHistory,
      isLoadingMore,
      isLoadingStockBar,
      handleDeleteStock,
      isDeletingStock,
      loadMoreHistory,
      openTaskRunFlow,
      refreshedHistoryRecordIds,
      selectedIds,
      selectedReport?.meta.stockCode,
      selectedReport?.meta.id,
      toggleHistorySelection,
      toggleSelectAllVisible,
      uiLanguage,
    ],
  );

  return (
    <div
      data-testid="home-dashboard"
      className="flex h-[calc(100vh-5rem)] w-full flex-col overflow-hidden md:flex-row sm:h-[calc(100vh-5.5rem)] lg:h-[calc(100vh-2rem)]"
    >
      <div className="flex-1 flex flex-col min-h-0 min-w-0 max-w-full lg:max-w-6xl mx-auto w-full">
        <header className="relative z-30 flex min-w-0 flex-shrink-0 items-center overflow-visible px-3 py-3 md:px-4 md:py-4">
          <div className="flex min-w-0 flex-1 flex-col gap-2.5 md:flex-row md:items-center">
            <div className="flex min-w-0 flex-1 items-center gap-2.5">
              <button
                onClick={() => setSidebarOpen(true)}
                className="md:hidden -ml-1 flex-shrink-0 rounded-lg p-1.5 text-secondary-text transition-colors hover:bg-hover hover:text-foreground"
                aria-label={t('home.historyButton')}
              >
                <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
                </svg>
              </button>
              <div className="relative min-w-0 flex-1">
                <StockAutocomplete
                  value={query}
                  onChange={setQuery}
                  onSubmit={(stockCode, stockName) => {
                    void handleBasicQuery(stockCode, stockName);
                  }}
                  placeholder={t('home.placeholder')}
                  disabled={isAnalyzing || isQueryingBasic}
                  className={inputError ? 'border-danger/50' : undefined}
                />
              </div>
              {analysisSkills.length > 0 ? (
                <div ref={strategyMenuRef} className="relative flex-shrink-0">
                  <button
                    ref={strategyButtonRef}
                    id="strategy-menu-button"
                    type="button"
                    aria-haspopup="menu"
                    aria-expanded={strategyMenuOpen}
                    aria-controls={strategyMenuOpen ? 'strategy-menu' : undefined}
                    onClick={() => setStrategyMenuOpen((open) => !open)}
                    onKeyDown={handleStrategyButtonKeyDown}
                    disabled={isAnalyzing || isQueryingBasic}
                    className="home-surface-button flex h-10 max-w-[8.5rem] items-center gap-1.5 rounded-xl px-3 text-xs text-foreground disabled:cursor-not-allowed disabled:opacity-60 sm:max-w-[11rem]"
                  >
                    <SlidersHorizontal className="h-4 w-4 flex-shrink-0" aria-hidden="true" />
                    <span className="truncate">{selectedStrategy?.name || t('home.strategy')}</span>
                  </button>
                  {strategyMenuOpen ? (
                    <div
                      id="strategy-menu"
                      role="menu"
                      aria-labelledby="strategy-menu-button"
                      onKeyDown={handleStrategyMenuKeyDown}
                      className="absolute right-0 top-11 z-[120] max-h-80 w-[min(18rem,calc(100vw-1.5rem))] overflow-y-auto rounded-xl border border-subtle bg-elevated p-1.5 text-sm text-foreground shadow-2xl"
                    >
                      {strategyOptions.map((option, index) => {
                        const selected = selectedStrategyId === option.id;
                        return (
                          <button
                            key={option.id || 'default'}
                            ref={(node) => {
                              strategyItemRefs.current[index] = node;
                            }}
                            type="button"
                            role="menuitemradio"
                            aria-checked={selected}
                            tabIndex={-1}
                            onClick={() => selectStrategy(option.id)}
                            className="flex w-full items-start gap-2 rounded-lg px-2.5 py-2 text-left transition-colors hover:bg-hover"
                          >
                            <Check className={`mt-0.5 h-4 w-4 flex-shrink-0 ${selected ? 'opacity-100' : 'opacity-0'}`} aria-hidden="true" />
                            <span className="min-w-0">
                              <span className="block font-medium">{option.name}</span>
                              <span className="mt-0.5 line-clamp-2 block text-xs leading-5 text-muted-text">{option.description}</span>
                            </span>
                          </button>
                        );
                      })}
                    </div>
                  ) : null}
                </div>
              ) : null}
            </div>
            <div className="flex min-w-0 flex-shrink-0 flex-wrap items-center gap-2.5">
              <label className="flex h-10 flex-shrink-0 cursor-pointer items-center gap-1.5 rounded-xl border border-subtle bg-surface/60 px-3 text-xs text-secondary-text select-none transition-colors hover:border-subtle-hover hover:text-foreground">
                <input
                  type="checkbox"
                  checked={notify}
                  onChange={(e) => setNotify(e.target.checked)}
                  className="h-3.5 w-3.5 rounded border-border accent-primary"
                />
                {t('home.notify')}
              </label>
              <Button
                type="button"
                variant="secondary"
                size="md"
                isLoading={isSubmittingMarketReview}
                loadingText={t('home.submitMarketReview')}
                onClick={() => void handleTriggerMarketReview()}
                className="h-10 flex-1 whitespace-nowrap md:flex-none"
              >
                <BarChart3 className="h-4 w-4" aria-hidden="true" />
                {t('home.marketReview')}
              </Button>
              <Button
                type="button"
                variant="secondary"
                size="md"
                disabled={!query || isAnalyzing}
                onClick={() => handleSubmitAnalysis(undefined, undefined, 'manual', 'fast')}
                className="h-10 flex-1 whitespace-nowrap md:flex-none"
              >
                <Sparkles className="h-4 w-4" aria-hidden="true" />
                {t('home.quickAnalyze')}
              </Button>
              <Button
                type="button"
                variant="secondary"
                size="md"
                disabled={!query || isAnalyzing}
                onClick={() => handleSubmitAnalysis(undefined, undefined, 'manual', 'deep')}
                className="h-10 flex-1 whitespace-nowrap md:flex-none"
              >
                <SlidersHorizontal className="h-4 w-4" aria-hidden="true" />
                {t('home.deepAnalyze')}
              </Button>
              <button
                type="button"
                onClick={() => void handleBasicQuery()}
                disabled={!query || isQueryingBasic}
                className="btn-primary flex h-10 flex-1 items-center justify-center gap-1.5 whitespace-nowrap md:flex-none"
              >
                {isQueryingBasic ? (
                  <>
                    <svg className="h-3.5 w-3.5 animate-spin" fill="none" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                    </svg>
                    {t('home.querying')}
                  </>
                ) : (
                  <>
                    <Search className="h-4 w-4" aria-hidden="true" />
                    {t('home.query')}
                  </>
                )}
              </button>
            </div>
          </div>
        </header>

        {platformEnabled ? (
          <div className="px-3 pb-2 md:px-4">
            <div className="flex flex-col gap-2 rounded-lg border border-subtle bg-surface/70 px-3 py-2 text-xs text-secondary-text md:flex-row md:items-center md:justify-between">
              {platformSession ? (
                <>
                  <div className="flex min-w-0 flex-1 flex-col gap-1">
                    <div
                      data-testid="platform-query-status"
                      className="flex min-w-0 flex-wrap items-center gap-2 text-xs text-secondary-text"
                    >
                      <span className="inline-flex min-w-0 items-center gap-1.5 font-medium text-foreground">
                        <UserRound className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />
                        <span className="max-w-[14rem] truncate">Signed in {platformSession.user.email}</span>
                      </span>
                      <span className="rounded-md border border-subtle px-2 py-1">Plan {platformSession.user.plan}</span>
                      <span className="rounded-md border border-subtle px-2 py-1">Weekly free {accountQuotaText}</span>
                      <span className="rounded-md border border-subtle px-2 py-1">No-AI quick {basicQuotaText}</span>
                      <span className="rounded-md border border-subtle px-2 py-1">{byokStatusText}</span>
                      <span className="rounded-md border border-subtle px-2 py-1">{recommendedModeText}</span>
                    </div>
                    <div
                      data-testid="platform-ai-cost-warning"
                      className="text-xs text-secondary-text"
                    >
                      Quick snapshot stays no-AI. Quick/Deep AI uses selected quota: platform API, BYOK, or local model. Historical reports stay separate from current snapshots.
                    </div>
                    <div
                      data-testid="platform-watchlist-panel"
                      className="flex min-w-0 flex-wrap items-center gap-2 text-xs text-secondary-text"
                    >
                      <span className="rounded-md border border-subtle px-2 py-1 font-medium text-foreground">
                        Watchlist {platformWatchlist?.total ?? platformWatchlistItems.length}
                      </span>
                      {platformWatchlistPreview.length > 0 ? platformWatchlistPreview.map((item) => (
                        <button
                          key={`${item.stockCode}-${item.market}`}
                          type="button"
                          onClick={() => void handleBasicQuery(item.stockCode)}
                          className="rounded-md border border-subtle px-2 py-1 text-secondary-text hover:text-foreground"
                        >
                          {item.stockCode}
                        </button>
                      )) : (
                        <span className="rounded-md border border-subtle px-2 py-1">empty</span>
                      )}
                      <Button
                        type="button"
                        variant="secondary"
                        size="sm"
                        disabled={!query.trim() || platformWatchlistBusy}
                        onClick={() => void handleAddCurrentQueryToPlatformWatchlist()}
                        data-testid="platform-watchlist-add-current"
                      >
                        <Plus className="h-3.5 w-3.5" aria-hidden="true" />
                        Add current
                      </Button>
                      <Button
                        type="button"
                        variant="secondary"
                        size="sm"
                        isLoading={platformWatchlistBusy}
                        loadingText="Refreshing"
                        onClick={() => void handleRefreshPlatformWatchlist()}
                        data-testid="platform-watchlist-refresh"
                      >
                        <RefreshCw className="h-3.5 w-3.5" aria-hidden="true" />
                        Refresh watchlist
                      </Button>
                    </div>
                    {platformWatchlistRefresh ? (
                      <div
                        data-testid="platform-watchlist-refresh-summary"
                        className="flex min-w-0 flex-wrap items-center gap-2 text-xs text-secondary-text"
                      >
                        <span className="rounded-md border border-subtle px-2 py-1">No AI used</span>
                        <span className="rounded-md border border-subtle px-2 py-1">
                          refreshed {platformWatchlistRefresh.refreshed}/{platformWatchlistRefresh.requested}
                        </span>
                        <span className="rounded-md border border-subtle px-2 py-1">
                          degraded {platformWatchlistRefresh.degraded}
                        </span>
                        {platformWatchlistLanes.map((lane) => (
                          <span key={lane} className="rounded-md border border-subtle px-2 py-1">{lane}</span>
                        ))}
                      </div>
                    ) : null}
                    {platformWatchlistBoardItems.length > 0 ? (
                      <div
                        data-testid="platform-watchlist-board"
                        className="grid min-w-0 gap-2 text-xs text-secondary-text sm:grid-cols-2 xl:grid-cols-4"
                      >
                        {platformWatchlistBoardItems.map((item) => (
                          <div
                            key={`${item.stockCode}-${item.routeLane ?? item.market}`}
                            className="min-w-0 rounded-lg border border-subtle bg-surface/70 p-2"
                          >
                            <div className="flex min-w-0 items-start justify-between gap-2">
                              <div className="min-w-0">
                                <button
                                  type="button"
                                  onClick={() => void handleBasicQuery(item.stockCode)}
                                  data-testid={`platform-watchlist-board-query-${item.stockCode}`}
                                  className="flex min-w-0 items-center gap-1 text-left font-medium text-foreground hover:text-primary"
                                >
                                  <Search className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />
                                  <span className="truncate">{item.stockCode}</span>
                                </button>
                                <div className="truncate text-[11px] text-secondary-text">
                                  {item.stockName || item.market}
                                </div>
                              </div>
                              <span className="rounded-md border border-subtle px-1.5 py-0.5 text-[11px] uppercase">
                                {item.market}
                              </span>
                            </div>
                            <div className="mt-2 grid grid-cols-2 gap-1 text-[11px]">
                              <span className="rounded-md border border-subtle px-1.5 py-1">
                                Price {formatBasicNumber(item.currentPrice)}
                              </span>
                              <span className="rounded-md border border-subtle px-1.5 py-1">
                                Chg {formatBasicNumber(item.changePercent)}%
                              </span>
                            </div>
                            <div className="mt-2 flex min-w-0 flex-wrap gap-1">
                              <span className="rounded-md border border-subtle px-1.5 py-0.5">{item.routeLane || 'unknown_lane'}</span>
                              <span className="rounded-md border border-subtle px-1.5 py-0.5">{item.freshness}</span>
                              <span className="rounded-md border border-subtle px-1.5 py-0.5">{item.degradationStatus}</span>
                              <span className="rounded-md border border-subtle px-1.5 py-0.5">{item.aiUsed ? 'AI used' : 'No AI'}</span>
                              {item.warningCodes.map((warning) => (
                                <span key={warning} className="rounded-md border border-warning/40 px-1.5 py-0.5 text-warning">
                                  {warning}
                                </span>
                              ))}
                            </div>
                          </div>
                        ))}
                      </div>
                    ) : null}
                    {platformWatchlistError ? (
                      <div className="text-xs text-danger" role="alert">{platformWatchlistError}</div>
                    ) : null}
                  </div>
                  <div className="flex min-w-0 flex-wrap items-center gap-2">
                    <span className="inline-flex items-center gap-1.5 font-medium text-foreground">
                      <UserRound className="h-3.5 w-3.5" aria-hidden="true" />
                      <span className="max-w-[11rem] truncate">{platformSession.user.email}</span>
                    </span>
                    <span className="rounded-md border border-subtle px-2 py-1">{platformSession.user.plan}</span>
                    <span className="rounded-md border border-subtle px-2 py-1">额度 {quotaText}</span>
                  </div>
                  <div className="flex min-w-0 flex-wrap items-center gap-2">
                    <div className="inline-flex overflow-hidden rounded-lg border border-subtle">
                      <button
                        type="button"
                        onClick={() => handleApiKeyModeChange('platform')}
                        data-testid="platform-mode-platform"
                        className={`px-2.5 py-1 ${apiKeyMode === 'platform' ? 'bg-primary text-primary-foreground' : 'bg-surface text-secondary-text hover:text-foreground'}`}
                      >
                        平台 API
                      </button>
                      <button
                        type="button"
                        disabled={!hasUserApiKey}
                        onClick={() => handleApiKeyModeChange('user')}
                        data-testid="platform-mode-user"
                        className={`px-2.5 py-1 disabled:cursor-not-allowed disabled:opacity-50 ${apiKeyMode === 'user' ? 'bg-primary text-primary-foreground' : 'bg-surface text-secondary-text hover:text-foreground'}`}
                      >
                        我的 API
                      </button>
                      <button
                        type="button"
                        onClick={() => handleApiKeyModeChange('local')}
                        data-testid="platform-mode-local"
                        className={`px-2.5 py-1 ${apiKeyMode === 'local' ? 'bg-primary text-primary-foreground' : 'bg-surface text-secondary-text hover:text-foreground'}`}
                      >
                        本地模型
                      </button>
                    </div>
                    <select
                      value={apiKeyProvider}
                      onChange={(event) => setApiKeyProvider(event.target.value)}
                      data-testid="platform-api-key-provider"
                      className="h-8 rounded-lg border border-subtle bg-surface px-2 text-foreground"
                    >
                      <option value="deepseek">DeepSeek</option>
                      <option value="openai">OpenAI</option>
                      <option value="anthropic">Anthropic</option>
                      <option value="gemini">Gemini</option>
                    </select>
                    <input
                      type="text"
                      value={apiKeyModel}
                      onChange={(event) => setApiKeyModel(event.target.value)}
                      data-testid="platform-api-key-model"
                      placeholder={platformKeys[0]?.model || '模型名'}
                      className="h-8 w-56 rounded-lg border border-subtle bg-surface px-2 text-foreground placeholder:text-muted-text"
                    />
                    <input
                      type="password"
                      value={apiKeyDraft}
                      onChange={(event) => setApiKeyDraft(event.target.value)}
                      data-testid="platform-api-key-secret"
                      placeholder={platformKeys[0]?.maskedKey || 'API Key'}
                      className="h-8 w-40 rounded-lg border border-subtle bg-surface px-2 text-foreground placeholder:text-muted-text"
                    />
                    <Button
                      type="button"
                      variant="secondary"
                      size="sm"
                      isLoading={apiKeySaving}
                      disabled={!apiKeyDraft.trim()}
                      onClick={() => void handleSaveApiKey()}
                      data-testid="platform-api-key-save"
                    >
                      <KeyRound className="h-3.5 w-3.5" aria-hidden="true" />
                      保存
                    </Button>
                    <Button type="button" variant="secondary" size="sm" onClick={() => void handlePlatformLogout()} data-testid="platform-logout-button">
                      <LogOut className="h-3.5 w-3.5" aria-hidden="true" />
                      退出
                    </Button>
                  </div>
                </>
              ) : (
                <>
                  <div className="flex min-w-0 flex-wrap items-center gap-2">
                    <button
                      type="button"
                      onClick={() => setAuthMode('login')}
                      data-testid="platform-auth-login-tab"
                      className={`rounded-md px-2 py-1 ${authMode === 'login' ? 'bg-primary text-primary-foreground' : 'text-secondary-text hover:text-foreground'}`}
                    >
                      登录
                    </button>
                    <button
                      type="button"
                      onClick={() => setAuthMode('register')}
                      data-testid="platform-auth-register-tab"
                      className={`rounded-md px-2 py-1 ${authMode === 'register' ? 'bg-primary text-primary-foreground' : 'text-secondary-text hover:text-foreground'}`}
                    >
                      注册
                    </button>
                    {authError ? <span className="text-danger">{authError}</span> : null}
                  </div>
                  <div className="flex min-w-0 flex-wrap items-center gap-2">
                    <input
                      type="email"
                      value={authEmail}
                      onChange={(event) => setAuthEmail(event.target.value)}
                      data-testid="platform-auth-email"
                      placeholder="邮箱"
                      className="h-8 w-44 rounded-lg border border-subtle bg-surface px-2 text-foreground placeholder:text-muted-text"
                    />
                    <input
                      type="password"
                      value={authPassword}
                      onChange={(event) => setAuthPassword(event.target.value)}
                      data-testid="platform-auth-password"
                      placeholder="密码"
                      className="h-8 w-36 rounded-lg border border-subtle bg-surface px-2 text-foreground placeholder:text-muted-text"
                    />
                    <Button
                      type="button"
                      variant="secondary"
                      size="sm"
                      isLoading={authBusy}
                      disabled={!authEmail.trim() || !authPassword}
                      onClick={() => void handlePlatformAuth()}
                      data-testid="platform-auth-submit"
                    >
                      {authMode === 'register' ? '注册' : '登录'}
                    </Button>
                  </div>
                </>
              )}
            </div>
          </div>
        ) : null}

        {inputError || duplicateError ? (
          <div className="px-3 pb-2 md:px-4">
            {inputError ? (
              <InlineAlert
                variant="danger"
                title={t('home.inputInvalid')}
                message={inputError}
                className="rounded-xl px-3 py-2 text-xs shadow-none"
              />
            ) : null}
            {!inputError && duplicateError ? (
              <InlineAlert
                variant="warning"
                title={t('home.duplicateTask')}
                message={duplicateError}
                className="rounded-xl px-3 py-2 text-xs shadow-none"
              />
            ) : null}
          </div>
        ) : null}

        {setupNeedsAction ? (
          <div className="px-3 pb-2 md:px-4">
            <InlineAlert
              variant="warning"
              title={t('home.setupIncomplete')}
              message={
                setupMissingLabels
                  ? t('home.setupMissingWithLabels', { labels: setupMissingLabels })
                  : t('home.setupMissingGeneric')
              }
              action={(
                <Button
                  type="button"
                  variant="secondary"
                  size="sm"
                  onClick={() => navigate('/settings')}
                >
                  {t('home.goSettings')}
                </Button>
              )}
              className="rounded-xl px-3 py-2 text-xs shadow-none"
            />
          </div>
        ) : null}

        <div className="flex-1 flex min-h-0 overflow-hidden">
          <div className="hidden min-h-0 w-64 shrink-0 flex-col overflow-hidden pl-4 pb-4 md:flex lg:w-72">
            {sidebarContent}
          </div>

          {sidebarOpen ? (
            <div className="fixed inset-0 z-40 md:hidden" onClick={() => setSidebarOpen(false)}>
              <div className="page-drawer-overlay absolute inset-0" />
              <div
                className="dashboard-card absolute bottom-0 left-0 top-0 flex w-72 flex-col overflow-hidden !rounded-none !rounded-r-xl p-3 shadow-2xl"
                onClick={(event) => event.stopPropagation()}
              >
                {sidebarContent}
              </div>
            </div>
          ) : null}

          <section
            ref={dashboardScrollRef}
            data-testid="home-dashboard-scroll"
            className="flex-1 min-w-0 min-h-0 overflow-x-auto overflow-y-auto px-3 pb-4 md:px-6 touch-pan-y"
          >
            {marketReviewNotice ? (
              <div className="mb-3">
                <InlineAlert
                  variant={marketReviewNotice.variant}
                  title={marketReviewNotice.title}
                  message={marketReviewNotice.message}
                  className="rounded-xl px-3 py-2 text-xs shadow-none"
                />
              </div>
            ) : null}

            {marketReviewError ? (
              <div className="mb-3">
                <ApiErrorAlert
                  error={marketReviewError}
                  className="mb-1"
                  onDismiss={() => setMarketReviewError(null)}
                />
              </div>
            ) : null}

            {marketReviewReport ? (
              <MarketReviewReportView
                content={marketReviewReport}
                payload={marketReviewPayload}
                reportLanguage={liveMarketReviewLanguage}
                className="mb-3"
              />
            ) : null}

            {error ? (
              <ApiErrorAlert
                error={error}
                className="mb-3"
                onDismiss={clearError}
              />
            ) : null}

            {basicQueryError ? (
              <ApiErrorAlert
                error={basicQueryError}
                className="mb-3"
                onDismiss={() => setBasicQueryError(null)}
              />
            ) : null}

            {basicSnapshot && !marketReviewReport ? (
              <div data-testid="basic-query-snapshot" className="mb-4 max-w-4xl rounded-xl border border-subtle bg-surface/75 p-4 shadow-soft-card">
                <div
                  data-testid="basic-query-primary-summary"
                  className="mb-4 flex flex-col gap-3 border-b border-subtle pb-4 lg:flex-row lg:items-end lg:justify-between"
                >
                  <div className="min-w-0">
                    <div className="mb-2 flex flex-wrap items-center gap-2 text-xs text-secondary-text">
                      <span className="rounded-md border border-primary/40 bg-primary/10 px-2 py-1 font-medium text-primary">
                        {uiLanguage === 'en' ? 'Queried' : '已查询'}
                      </span>
                      <span className="rounded-md border border-subtle px-2 py-1">{basicSnapshot.market.toUpperCase()}</span>
                      <span className="rounded-md border border-subtle px-2 py-1">{basicSnapshot.quote.freshness}</span>
                      <span className="rounded-md border border-primary/40 bg-primary/10 px-2 py-1 text-primary">{t('home.noAi')}</span>
                    </div>
                    <h2 className="truncate text-2xl font-semibold text-foreground">{basicSnapshot.stockName || basicSnapshot.stockCode}</h2>
                    <p className="mt-1 text-sm text-secondary-text">{basicSnapshot.stockCode}</p>
                  </div>
                  <div className="grid min-w-0 gap-3 sm:grid-cols-2 lg:min-w-[26rem] lg:grid-cols-4">
                    <div className="min-w-0 border-l border-primary/50 pl-3">
                      <div className="text-xs text-secondary-text">{t('home.basicCurrentPrice')}</div>
                      <div className="mt-1 text-xl font-semibold text-foreground">{formatBasicNumber(basicSnapshot.quote.currentPrice)}</div>
                    </div>
                    <div className="min-w-0 border-l border-subtle pl-3">
                      <div className="text-xs text-secondary-text">{t('home.basicChangePercent')}</div>
                      <div className="mt-1 text-xl font-semibold text-foreground">{formatBasicNumber(basicSnapshot.quote.changePercent)}%</div>
                    </div>
                    <div className="min-w-0 border-l border-subtle pl-3">
                      <div className="text-xs text-secondary-text">MA5</div>
                      <div className="mt-1 text-xl font-semibold text-foreground">{formatBasicNumber(basicSnapshot.indicators['ma5'])}</div>
                    </div>
                    <div className="min-w-0 border-l border-subtle pl-3">
                      <div className="text-xs text-secondary-text">MA20</div>
                      <div className="mt-1 text-xl font-semibold text-foreground">{formatBasicNumber(basicSnapshot.indicators['ma20'])}</div>
                    </div>
                  </div>
                </div>
                <div className="mb-4 grid gap-3 lg:grid-cols-2">
                  <section
                    data-testid="basic-query-quote-details"
                    className="min-w-0 rounded-lg border border-subtle bg-background/25 p-3"
                  >
                    <h3 className="mb-3 text-sm font-semibold text-foreground">
                      {uiLanguage === 'en' ? 'Quote details' : '行情明细'}
                    </h3>
                    <div className="grid gap-2 sm:grid-cols-2">
                      {basicQuoteDetailItems.map((item) => (
                        <div key={item.label} className="min-w-0 rounded-md border border-subtle/70 px-3 py-2">
                          <div className="text-xs text-secondary-text">{item.label}</div>
                          <div className="mt-1 truncate text-sm font-medium text-foreground">{item.value}</div>
                        </div>
                      ))}
                    </div>
                  </section>
                  <section
                    data-testid="basic-query-technical-details"
                    className="min-w-0 rounded-lg border border-subtle bg-background/25 p-3"
                  >
                    <h3 className="mb-3 text-sm font-semibold text-foreground">
                      {uiLanguage === 'en' ? 'Technical overview' : '技术概览'}
                    </h3>
                    <div className="grid gap-2 sm:grid-cols-2">
                      {basicTechnicalDetailItems.map((item) => (
                        <div key={item.label} className="min-w-0 rounded-md border border-subtle/70 px-3 py-2">
                          <div className="text-xs text-secondary-text">{item.label}</div>
                          <div className="mt-1 truncate text-sm font-medium text-foreground">{item.value}</div>
                        </div>
                      ))}
                    </div>
                  </section>
                </div>
                <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                  <div className="min-w-0">
                    <div className="mb-2 flex flex-wrap items-center gap-2 text-xs text-secondary-text">
                      <span className="rounded-md border border-subtle px-2 py-1">{t('home.basicSnapshotTitle')}</span>
                      <span className="rounded-md border border-subtle px-2 py-1">{basicSnapshot.market.toUpperCase()}</span>
                      <span className="rounded-md border border-subtle px-2 py-1">{basicSnapshot.quote.freshness}</span>
                      <span className="rounded-md border border-primary/40 bg-primary/10 px-2 py-1 text-primary">{t('home.noAi')}</span>
                    </div>
                    <div
                      data-testid="basic-query-user-guardrails"
                      className="mb-2 flex flex-wrap items-center gap-2 text-xs text-secondary-text"
                    >
                      <span className="rounded-md border border-subtle px-2 py-1">Current quick snapshot</span>
                      <span className="rounded-md border border-subtle px-2 py-1">
                        {basicSnapshot.aiUsed ? 'AI used' : 'No AI used'}
                      </span>
                      <span className="rounded-md border border-subtle px-2 py-1">{marketLaneLabel(basicSnapshotLane)}</span>
                      <span className="rounded-md border border-subtle px-2 py-1">Historical reports stay separate</span>
                      {basicSnapshotCacheMode ? (
                        <span className="rounded-md border border-subtle px-2 py-1">Cache {String(basicSnapshotCacheMode)}</span>
                      ) : null}
                    </div>
                    <div
                      data-testid="basic-query-workspace-lanes"
                      className="mb-3 grid min-w-0 gap-2 border-y border-subtle py-2 text-xs text-secondary-text sm:grid-cols-2 lg:grid-cols-4"
                    >
                      <div className="min-w-0">
                        <div className="font-medium text-foreground">Current Snapshot</div>
                        <div className="mt-1 flex min-w-0 flex-wrap gap-1">
                          <span className="rounded-md border border-subtle px-1.5 py-0.5">{basicSnapshot.aiUsed ? 'AI used' : 'No AI'}</span>
                          <span className="rounded-md border border-subtle px-1.5 py-0.5">{marketLaneLabel(basicSnapshotLane)}</span>
                        </div>
                      </div>
                      <div className="min-w-0">
                        <div className="font-medium text-foreground">Watchlist</div>
                        <div className="mt-1 flex min-w-0 flex-wrap gap-1">
                          <span className="rounded-md border border-subtle px-1.5 py-0.5">{platformWatchlistCount} symbols</span>
                          <span className="rounded-md border border-subtle px-1.5 py-0.5">private</span>
                        </div>
                      </div>
                      <div className="min-w-0">
                        <div className="font-medium text-foreground">History Reports</div>
                        <div className="mt-1 flex min-w-0 flex-wrap gap-1">
                          <span className="rounded-md border border-subtle px-1.5 py-0.5">{workspaceHistoryCountText}</span>
                          <span className="rounded-md border border-subtle px-1.5 py-0.5">separate</span>
                        </div>
                      </div>
                      <div className="min-w-0">
                        <div className="font-medium text-foreground">AI Analysis</div>
                        <div className="mt-1 flex min-w-0 flex-wrap gap-1">
                          <span className="rounded-md border border-subtle px-1.5 py-0.5">{workspaceAiModeText}</span>
                          <span className="rounded-md border border-subtle px-1.5 py-0.5">{workspaceByokText}</span>
                        </div>
                      </div>
                    </div>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    <Button
                      type="button"
                      variant="secondary"
                      size="sm"
                      data-testid="basic-query-refresh-market"
                      disabled={isQueryingBasic}
                      onClick={() => void handleBasicQuery(basicSnapshot.stockCode, undefined, true)}
                    >
                      <RefreshCw className="h-4 w-4" aria-hidden="true" />
                      {uiLanguage === 'en' ? 'Refresh quote' : '刷新行情'}
                    </Button>
                    <Button
                      type="button"
                      variant="secondary"
                      size="sm"
                      disabled={isAnalyzing}
                      onClick={() => handleSubmitAnalysis(basicSnapshot.stockCode, basicSnapshot.stockName || undefined, 'manual', 'fast')}
                    >
                      <Sparkles className="h-4 w-4" aria-hidden="true" />
                      {t('home.quickAnalyze')}
                    </Button>
                    <Button
                      type="button"
                      variant="secondary"
                      size="sm"
                      disabled={isAnalyzing}
                      onClick={() => handleSubmitAnalysis(basicSnapshot.stockCode, basicSnapshot.stockName || undefined, 'manual', 'deep')}
                    >
                      <SlidersHorizontal className="h-4 w-4" aria-hidden="true" />
                      {t('home.deepAnalyze')}
                    </Button>
                  </div>
                </div>
                <div className="mt-3 text-xs text-secondary-text">
                  {t('home.basicSource')}: {basicSnapshot.quote.source}
                  {basicSnapshot.route ? (
                    <span data-testid="basic-query-route" className="ml-2">
                      Lane: {basicSnapshot.route.dataSourceLane} / {basicSnapshot.route.channel}
                    </span>
                  ) : null}
                </div>
                {basicSnapshot.diagnostics ? (
                  <div data-testid="basic-query-diagnostics" className="mt-2 flex flex-wrap gap-2 text-xs text-secondary-text">
                    <span className="rounded-md border border-subtle px-2 py-1">
                      {t('home.basicDiagnostics')}: {formatBasicNumber(basicSnapshot.diagnostics.elapsedMs)}ms
                    </span>
                    <span className="rounded-md border border-subtle px-2 py-1">
                      {t('home.basicCache')}: Q {basicSnapshot.diagnostics.cache.quote || '-'} / H {basicSnapshot.diagnostics.cache.history || '-'}
                    </span>
                    <span className="rounded-md border border-subtle px-2 py-1">
                      {t('home.basicFallback')}: Q {basicSnapshot.diagnostics.fallback?.quote || '-'} / H {basicSnapshot.diagnostics.fallback?.history || '-'}
                    </span>
                    <span className="rounded-md border border-subtle px-2 py-1">
                      {t('home.basicSourceHealth')}: Q {basicSnapshot.diagnostics.sourceHealth?.quote?.status || '-'} / H {basicSnapshot.diagnostics.sourceHealth?.history?.status || '-'}
                    </span>
                    <span className="rounded-md border border-subtle px-2 py-1">
                      {t('home.basicPersistentCache')}: Q {String(basicSnapshot.diagnostics.persistentCache?.quote || '-')} / H {String(basicSnapshot.diagnostics.persistentCache?.history || '-')}
                    </span>
                    {basicSnapshot.diagnostics.refresh ? (
                      <span className="rounded-md border border-subtle px-2 py-1">
                        Refresh: {String(basicSnapshot.diagnostics.refresh.mode || '-')}
                      </span>
                    ) : null}
                    <span className="rounded-md border border-subtle px-2 py-1">
                      {t('home.basicPerformance')}: {String(basicSnapshot.diagnostics.performance.status || '-')}
                    </span>
                  </div>
                ) : null}
                {basicSnapshot.degradation && basicSnapshot.degradation.status !== 'ok' ? (
                  <div
                    data-testid="basic-query-degradation"
                    role="alert"
                    className="mt-3 rounded-lg border border-warning/40 bg-warning/10 px-3 py-2 text-sm text-foreground"
                  >
                    <div className="font-medium">{basicSnapshot.degradation.message}</div>
                    {basicSnapshot.warnings?.length ? (
                      <ul className="mt-1 space-y-1 text-xs text-secondary-text">
                        {basicSnapshot.warnings.map((warning) => (
                          <li key={`${warning.code}-${warning.message}`}>
                            {warning.code}: {warning.message}
                          </li>
                        ))}
                      </ul>
                    ) : null}
                  </div>
                ) : null}
              </div>
            ) : null}

            {!marketReviewReport && !basicSnapshot && isLoadingReport ? (
              <div className="flex h-full flex-col items-center justify-center">
                <DashboardStateBlock title={t('home.loadingReport')} loading />
              </div>
            ) : !marketReviewReport && !basicSnapshot && selectedReport ? (
              <div className={isHistoryTrendOpen ? 'max-w-6xl space-y-4 pb-8' : 'max-w-4xl space-y-4 pb-8'}>
                <div className="flex flex-wrap items-center justify-end gap-2">
                  {!isMarketReviewHistoryReport ? (
                    <>
                      <Button
                        variant="home-action-ai"
                        size="sm"
                        disabled={isAnalyzing || selectedReport.meta.id === undefined}
                        onClick={handleReanalyze}
                      >
                        <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                        </svg>
                        {t('home.reanalyze')}
                      </Button>
                      <Button
                        variant="home-action-ai"
                        size="sm"
                        disabled={selectedReport.meta.id === undefined}
                        onClick={handleAskFollowUp}
                      >
                        <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
                        </svg>
                        {t('home.askAi')}
                      </Button>
                    </>
                  ) : (
                    <Button
                      variant="home-action-ai"
                      size="sm"
                      disabled={isSubmittingMarketReview}
                      isLoading={isSubmittingMarketReview}
                      loadingText={t('home.submitMarketReview')}
                      onClick={() => void handleTriggerMarketReview()}
                    >
                      <BarChart3 className="h-4 w-4" />
                      {t('home.rerunMarketReview')}
                    </Button>
                  )}
                  <Button
                    variant="home-action-ai"
                    size="sm"
                    disabled={selectedReport.meta.id === undefined || isHistoryTrendUnavailable}
                    className={isHistoryTrendOpen ? 'border-primary/70 bg-primary/15 text-primary shadow-glow-cyan' : undefined}
                    onClick={() => {
                      if (isHistoryTrendOpen) {
                        closeHistoryTrend();
                        return;
                      }
                      void openHistoryTrend();
                    }}
                  >
                    <BarChart3 className="h-4 w-4" />
                    {t('home.historyTrend')}
                  </Button>
                  <Button
                    variant="home-action-ai"
                    size="sm"
                    disabled={selectedReport.meta.id === undefined}
                    onClick={openMarkdownDrawer}
                  >
                    <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                    </svg>
                    {t('home.fullReport')}
                  </Button>
                </div>
                <div
                  data-testid="history-report-freshness-boundary"
                  className="flex flex-col gap-3 rounded-lg border border-warning/40 bg-warning/10 px-4 py-3 text-sm text-foreground sm:flex-row sm:items-center sm:justify-between"
                >
                  <div className="min-w-0">
                    <div className="font-medium">
                      Historical AI report · not current quote
                    </div>
                    <div className="mt-1 text-xs text-secondary-text">
                      这是历史 AI 报告，行情不会自动更新。需要当前行情时，请刷新实时快照。
                    </div>
                  </div>
                  {!isMarketReviewHistoryReport ? (
                    <Button
                      type="button"
                      variant="secondary"
                      size="sm"
                      disabled={isQueryingBasic}
                      isLoading={isQueryingBasic}
                      loadingText={uiLanguage === 'en' ? 'Refreshing quote' : '刷新中'}
                      data-testid="history-report-refresh-current"
                      onClick={() => void handleRefreshCurrentQuoteFromHistory()}
                    >
                      <RefreshCw className="h-4 w-4" aria-hidden="true" />
                      {uiLanguage === 'en' ? 'Refresh current quote' : '刷新当前行情'}
                    </Button>
                  ) : null}
                </div>
                {!isMarketReviewHistoryReport ? (
                  <div
                    data-testid="history-report-tools"
                    className="rounded-lg border border-subtle bg-surface/70 px-4 py-3"
                  >
                    <div className="grid gap-3 lg:grid-cols-[minmax(0,1.15fr)_minmax(0,0.85fr)]">
                      <div className="min-w-0 space-y-2">
                        <label className="flex min-w-0 items-center gap-2 rounded-lg border border-subtle bg-background/40 px-3">
                          <Search className="h-4 w-4 flex-shrink-0 text-muted-text" aria-hidden="true" />
                          <span className="sr-only">Search report</span>
                          <input
                            value={historyReportSearch}
                            onChange={(event) => {
                              setHistoryReportSearch(event.target.value);
                              setHistoryReportMatchIndex(0);
                            }}
                            data-testid="history-report-search"
                            placeholder="Search report"
                            className="h-9 min-w-0 flex-1 bg-transparent text-sm text-foreground outline-none placeholder:text-muted-text"
                          />
                          <span data-testid="history-report-search-count" className="flex-shrink-0 text-xs text-muted-text">
                            {historyReportSearch.trim()
                              ? `${historyReportSearchMatches.length ? historyReportMatchIndex + 1 : 0}/${historyReportSearchMatches.length}`
                              : '0/0'}
                          </span>
                        </label>
                        <div className="flex flex-wrap items-center gap-2 text-xs">
                          <button
                            type="button"
                            data-testid="history-report-search-prev"
                            disabled={historyReportSearchMatches.length === 0}
                            onClick={() => setHistoryReportMatchIndex((index) => (
                              historyReportSearchMatches.length
                                ? (index - 1 + historyReportSearchMatches.length) % historyReportSearchMatches.length
                                : 0
                            ))}
                            className="rounded-md border border-subtle px-2 py-1 text-secondary-text hover:text-foreground disabled:cursor-not-allowed disabled:opacity-40"
                          >
                            Prev
                          </button>
                          <button
                            type="button"
                            data-testid="history-report-search-next"
                            disabled={historyReportSearchMatches.length === 0}
                            onClick={() => setHistoryReportMatchIndex((index) => (
                              historyReportSearchMatches.length
                                ? (index + 1) % historyReportSearchMatches.length
                                : 0
                            ))}
                            className="rounded-md border border-subtle px-2 py-1 text-secondary-text hover:text-foreground disabled:cursor-not-allowed disabled:opacity-40"
                          >
                            Next
                          </button>
                          {activeHistoryReportMatch && historyReportSearch.trim() ? (
                            <span data-testid="history-report-search-hit" className="min-w-0 flex-1 text-secondary-text">
                              {activeHistoryReportMatch.label}: {buildHistoryReportMatchSnippet(activeHistoryReportMatch.text, historyReportSearch.trim())}
                            </span>
                          ) : (
                            <span data-testid="history-report-search-hit" className="text-muted-text">
                              No match
                            </span>
                          )}
                        </div>
                        <div className="flex flex-wrap items-center gap-2">
                          {HISTORY_REPORT_SECTIONS.map((section) => (
                            <button
                              key={section.id}
                              type="button"
                              data-testid={`history-report-jump-${section.id}`}
                              onClick={() => handleHistoryReportJump(section.id, section.label)}
                              className="rounded-md border border-subtle px-2 py-1 text-xs font-medium text-secondary-text hover:text-foreground"
                            >
                              {section.label}
                            </button>
                          ))}
                          {historyReportSectionStatus ? (
                            <span data-testid="history-report-section-status" className="text-xs text-muted-text">
                              {historyReportSectionStatus}
                            </span>
                          ) : null}
                        </div>
                      </div>
                      <div data-testid="history-report-stock-timeline" className="min-w-0 space-y-2">
                        <div className="flex items-center gap-2 text-xs font-medium uppercase tracking-[0.16em] text-muted-text">
                          <BarChart3 className="h-3.5 w-3.5" aria-hidden="true" />
                          {selectedReport.meta.stockCode}
                        </div>
                        <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-1">
                          {sameStockTimelineItems.map((item) => {
                            const isCurrent = item.id === selectedReport.meta.id;
                            return (
                              <button
                                key={item.id}
                                type="button"
                                data-testid={`history-report-timeline-${item.id}`}
                                disabled={isCurrent}
                                onClick={() => void handleHistoryItemClick(item.id)}
                                className="min-w-0 rounded-lg border border-subtle bg-background/40 px-3 py-2 text-left text-xs text-secondary-text hover:text-foreground disabled:cursor-default disabled:border-primary/40 disabled:bg-primary/10 disabled:text-primary"
                              >
                                <span className="block truncate font-medium">
                                  {isCurrent ? 'Current' : historyTimelineDate(item.createdAt)}
                                </span>
                                <span className="block truncate">
                                  {item.stockCode} - {item.reportType || 'report'}
                                </span>
                              </button>
                            );
                          })}
                        </div>
                      </div>
                    </div>
                  </div>
                ) : null}
                <div className="rounded-lg border border-subtle bg-surface/70 px-4 py-3" data-testid="history-state-panel">
                  <div className="flex flex-wrap items-center gap-2">
                    <Button
                      type="button"
                      variant="secondary"
                      size="sm"
                      disabled={selectedReport.meta.id === undefined || isUpdatingHistoryState}
                      data-testid="history-state-favorite"
                      className={selectedHistoryState.favorite ? 'border-amber-400/50 bg-amber-500/10 text-amber-300' : undefined}
                      onClick={() => void handleUpdateSelectedHistoryState({ favorite: !selectedHistoryState.favorite })}
                    >
                      <Star className="h-4 w-4" aria-hidden="true" />
                      Favorite
                    </Button>
                    <Button
                      type="button"
                      variant="secondary"
                      size="sm"
                      disabled={selectedReport.meta.id === undefined || isUpdatingHistoryState}
                      data-testid="history-state-important"
                      className={selectedHistoryState.important ? 'border-rose-400/50 bg-rose-500/10 text-rose-300' : undefined}
                      onClick={() => void handleUpdateSelectedHistoryState({ important: !selectedHistoryState.important })}
                    >
                      <Flag className="h-4 w-4" aria-hidden="true" />
                      Important
                    </Button>
                    <Button
                      type="button"
                      variant="secondary"
                      size="sm"
                      disabled={selectedReport.meta.id === undefined || isUpdatingHistoryState}
                      data-testid="history-state-read"
                      className={selectedHistoryState.read ? 'border-emerald-400/50 bg-emerald-500/10 text-emerald-300' : undefined}
                      onClick={() => void handleUpdateSelectedHistoryState({ read: !selectedHistoryState.read })}
                    >
                      <Eye className="h-4 w-4" aria-hidden="true" />
                      {selectedHistoryState.read ? 'Read' : 'Unread'}
                    </Button>
                    <Button
                      type="button"
                      variant="secondary"
                      size="sm"
                      disabled={selectedReport.meta.id === undefined || isUpdatingHistoryState}
                      data-testid="history-state-archive"
                      className={selectedHistoryState.archived ? 'border-slate-400/50 bg-slate-500/10 text-slate-300' : undefined}
                      onClick={() => void handleUpdateSelectedHistoryState({ archived: !selectedHistoryState.archived })}
                    >
                      {selectedHistoryState.archived ? (
                        <ArchiveRestore className="h-4 w-4" aria-hidden="true" />
                      ) : (
                        <Archive className="h-4 w-4" aria-hidden="true" />
                      )}
                      {selectedHistoryState.archived ? 'Restore' : 'Archive'}
                    </Button>
                  </div>
                  <div className="mt-3 flex flex-col gap-2 sm:flex-row sm:items-start">
                    <label className="min-w-0 flex-1">
                      <span className="sr-only">Local history note</span>
                      <textarea
                        value={historyStateNoteDraft}
                        onChange={(event) => setHistoryStateNoteDraft(event.target.value)}
                        data-testid="history-state-note-input"
                        maxLength={1000}
                        rows={2}
                        placeholder="Local note for this historical report"
                        className="min-h-16 w-full resize-y rounded-lg border border-subtle bg-surface px-3 py-2 text-sm text-foreground outline-none placeholder:text-muted-text focus:border-primary/60"
                      />
                    </label>
                    <Button
                      type="button"
                      variant="secondary"
                      size="sm"
                      disabled={selectedReport.meta.id === undefined || isUpdatingHistoryState}
                      data-testid="history-state-note-save"
                      onClick={() => void handleUpdateSelectedHistoryState({ note: historyStateNoteDraft })}
                    >
                      <Save className="h-4 w-4" aria-hidden="true" />
                      Save note
                    </Button>
                  </div>
                  {historyStateStatus ? (
                    <div data-testid="history-state-status" className="mt-2 text-xs text-secondary-text">
                      {historyStateStatus}
                    </div>
                  ) : null}
                </div>
                {isHistoryTrendOpen ? (
                  <StockHistoryTrendDrawer
                    key={`stock-history-${selectedReport.meta.id}`}
                    report={selectedReport}
                    items={stockHistoryItems}
                    total={stockHistoryTotal}
                    hasMore={stockHistoryHasMore}
                    isLoading={isLoadingStockHistory}
                    isLoadingMore={isLoadingMoreStockHistory}
                    error={stockHistoryError}
                    filters={stockHistoryFilters}
                    onClose={closeHistoryTrend}
                    onRangeChange={(range) => void setStockHistoryRange(range)}
                    onLoadMore={() => void loadMoreStockHistory()}
                    onSelectRecord={(recordId) => void selectHistoryItem(recordId)}
                    onRetry={() => void openHistoryTrend()}
                  />
                ) : (
                  <ReportSummary
                    data={selectedReport}
                    isHistory
                    sectionIdPrefix={historyReportSectionPrefix}
                    onOpenRunFlow={openHistoryRunFlow}
                    watchlist={{
                      isInWatchlist: watchlistState.isInWatchlist,
                      onToggle: watchlistState.toggleWatchlist,
                      isActioning: watchlistState.isActioning,
                      actionMessage: watchlistState.actionMessage,
                    }}
                  />
                )}
              </div>
            ) : !marketReviewReport && !basicSnapshot ? (
              <div className="flex h-full items-center justify-center">
                <EmptyState
                  title={t('home.startAnalysisTitle')}
                  description={t('home.startAnalysisDescription')}
                  className="max-w-xl border-dashed"
                  icon={(
                    <svg className="h-6 w-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
                    </svg>
                  )}
                />
              </div>
            ) : null}
          </section>
        </div>
      </div>

      {markdownDrawerOpen && selectedReport?.meta.id ? (
        <ReportMarkdownDrawer
          key={selectedReport.meta.id}
          recordId={selectedReport.meta.id}
          stockName={selectedReport.meta.stockName || ''}
          stockCode={selectedReport.meta.stockCode}
          reportLanguage={reportLanguage}
          onClose={closeMarkdownDrawer}
        />
      ) : null}

      {runFlowDrawer.open ? (
        <Drawer
          isOpen={runFlowDrawer.open}
          onClose={closeRunFlowDrawer}
          title={t('runFlow.drawerTitle')}
          width="max-w-[96vw]"
          zIndex={80}
        >
          <RunFlowPanel
            key={`${runFlowDrawer.source.type}-${runFlowDrawer.source.type === 'task' ? runFlowDrawer.source.taskId : runFlowDrawer.source.recordId}`}
            source={runFlowDrawer.source}
            title={runFlowDrawer.title}
          />
        </Drawer>
      ) : null}

    </div>
  );
};

export default HomePage;
