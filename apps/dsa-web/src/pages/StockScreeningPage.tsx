import type React from 'react';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  Activity,
  Bookmark,
  Building2,
  CheckCircle2,
  ChevronDown,
  CircleAlert,
  Clock3,
  Droplet,
  Factory,
  Flame,
  Gem,
  Landmark,
  Pickaxe,
  Plane,
  Play,
  PlusCircle,
  RefreshCw,
  Search,
  Shield,
  SlidersHorizontal,
  Stethoscope,
  Trees,
  Utensils,
  Wrench,
} from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import {
  alphasiftApi,
  type AlphaSiftCandidate,
  type AlphaSiftHotspotDetail,
  type AlphaSiftHotspot,
  type AlphaSiftHotspotsResponse,
  type AlphaSiftScreenResponse,
  type AlphaSiftScreenTaskStatus,
  type AlphaSiftStrategy,
} from '../api/alphasift';
import { formatParsedApiError, getParsedApiError, toApiErrorMessage, type ParsedApiError } from '../api/error';
import { platformApi } from '../api/platform';
import { AppPage, Button, InlineAlert } from '../components/common';
import MarketScreeningCardV104, { type ScreeningWatchlistState } from '../components/screening/MarketScreeningCardV104';
import ScreeningCompareTrayV104 from '../components/screening/ScreeningCompareTrayV104';
import ScreeningReminderPanelV104, {
  type ScreeningReminderSavePayload,
  type ScreeningReminderState,
} from '../components/screening/ScreeningReminderPanelV104';
import {
  MAX_SCREENING_COMPARE,
  strategyPresentation,
  toggleComparedCodes,
} from '../components/screening/screeningModelV104';
import { useUiLanguage } from '../contexts/UiLanguageContext';

const marketLabel = (language: 'zh' | 'en') => (language === 'en' ? 'A-share' : 'A 股');
const SCREEN_TASK_STORAGE_KEY = 'dsa.alphasift.activeScreenTask.v1';
const SCREEN_TASK_POLL_INTERVAL_MS = 2000;

type PersistedScreenTask = {
  taskId: string;
  market: string;
  strategy: string;
  maxResults: number;
};

const readPersistedScreenTask = (): PersistedScreenTask | null => {
  if (typeof window === 'undefined') {
    return null;
  }
  try {
    const raw = window.sessionStorage.getItem(SCREEN_TASK_STORAGE_KEY);
    if (!raw) {
      return null;
    }
    const parsed = JSON.parse(raw) as Partial<PersistedScreenTask>;
    if (typeof parsed.taskId !== 'string' || !parsed.taskId.trim()) {
      return null;
    }
    const restoredMaxResults = Number(parsed.maxResults);
    return {
      taskId: parsed.taskId,
      market: typeof parsed.market === 'string' && parsed.market.trim() ? parsed.market : 'cn',
      strategy: typeof parsed.strategy === 'string' && parsed.strategy.trim() ? parsed.strategy : 'dual_low',
      maxResults: Number.isFinite(restoredMaxResults) ? Math.min(100, Math.max(1, restoredMaxResults)) : 3,
    };
  } catch {
    return null;
  }
};

const persistScreenTask = (task: PersistedScreenTask) => {
  try {
    window.sessionStorage.setItem(SCREEN_TASK_STORAGE_KEY, JSON.stringify(task));
  } catch {
    // Session storage is best-effort; polling still works while the page stays mounted.
  }
};

const clearPersistedScreenTask = () => {
  try {
    window.sessionStorage.removeItem(SCREEN_TASK_STORAGE_KEY);
  } catch {
    // Ignore storage cleanup failures.
  }
};

const isUnrecoverableScreenTaskError = (error: ParsedApiError) =>
  error.title === '筛选任务不可恢复';

const formatNumber = (value: unknown, digits = 2) => {
  if (value == null || value === '' || Number.isNaN(Number(value))) {
    return '-';
  }
  return Number(value).toFixed(digits);
};

const formatPercent = (value: unknown) => {
  if (value == null || value === '' || Number.isNaN(Number(value))) {
    return '-';
  }
  return `${(Number(value) * 100).toFixed(0)}%`;
};

const toMessageList = (values: string[] | undefined) =>
  Array.isArray(values) ? values.map((value) => String(value).trim()).filter(Boolean) : [];

const KNOWN_SNAPSHOT_SOURCES = new Set(['tushare', 'efinance', 'akshare_em', 'em_datacenter', 'baostock']);
const MAX_MESSAGE_DETAIL_LENGTH = 96;

const truncateMessageDetail = (value: string, maxLength = MAX_MESSAGE_DETAIL_LENGTH) => {
  const text = value.replace(/\s+/g, ' ').trim();
  if (text.length <= maxLength) {
    return text;
  }
  return `${text.slice(0, maxLength - 1)}…`;
};

const summarizeAlphaSiftDiagnostic = (detail: string) => {
  if (/trade_cal returned no open trading days/i.test(detail)) {
    return '交易日历暂无可用开市日';
  }
  if (/too many requests|rate limit|http\s*429/i.test(detail)) {
    return '请求过于频繁';
  }
  if (/403 forbidden|forbidden|access denied/i.test(detail)) {
    return '访问被拒绝';
  }
  if (/timeout|timed out/i.test(detail)) {
    return '请求超时';
  }
  if (/RemoteDisconnected|Connection aborted|ProtocolError|ConnectionPool|Max retries exceeded|ProxyError|NameResolutionError/i.test(detail)) {
    return '网络连接中断';
  }
  if (/missing .*api key|GEMINI_API_KEY|GOOGLE_API_KEY|gemini_api_key/i.test(detail)) {
    return '缺少可用 LLM API Key';
  }
  if (/returned no data|empty/i.test(detail)) {
    return '未返回可用数据';
  }

  const withoutUrl = detail
    .replace(/https?:\/\/\S+/gi, 'URL')
    .replace(/\bwith url:\s*\S+/gi, 'with url: URL')
    .replace(/\burl:\s*\S+/gi, 'url: URL');
  return truncateMessageDetail(withoutUrl);
};

const parseSourceDiagnostic = (value: string) => {
  const match = value.match(/^([a-zA-Z0-9_-]+)\s*[:：]\s*(.+)$/);
  if (!match) {
    return null;
  }
  return {
    source: match[1],
    detail: match[2],
  };
};

const normalizeScreenMessageKey = (value: string) => {
  const formatted = formatScreenMessage(value);
  return formatted ? formatted.trim().toLowerCase() : value.trim().toLowerCase();
};

const formatScreenMessage = (value: string) => {
  if (/^DSA provider context applied \d+ of \d+ candidates/i.test(value)) {
    return '';
  }
  if (/^LLM ranking failed/i.test(value)) {
    return `LLM 重排失败：${summarizeAlphaSiftDiagnostic(value)}，已回退到本地因子评分。`;
  }

  const snapshotFallback = value.match(/^Snapshot source fallback:\s*(.+)$/i);
  if (snapshotFallback) {
    const parsed = parseSourceDiagnostic(snapshotFallback[1]);
    if (parsed) {
      return `数据源降级：${parsed.source}（${summarizeAlphaSiftDiagnostic(parsed.detail)}）`;
    }
    return `数据源降级：${summarizeAlphaSiftDiagnostic(snapshotFallback[1])}`;
  }

  const parsed = parseSourceDiagnostic(value);
  if (parsed && KNOWN_SNAPSHOT_SOURCES.has(parsed.source.toLowerCase())) {
    return `数据源降级：${parsed.source}（${summarizeAlphaSiftDiagnostic(parsed.detail)}）`;
  }
  return truncateMessageDetail(value);
};

const getScreenMessages = (meta: AlphaSiftScreenResponse | null) => {
  if (!meta) {
    return [];
  }
  const messages: string[] = [];
  const seen = new Set<string>();
  [...toMessageList(meta.warnings), ...toMessageList(meta.sourceErrors), ...toMessageList(meta.llmParseErrors)].forEach(
    (value) => {
      const key = normalizeScreenMessageKey(value);
      if (seen.has(key)) {
        return;
      }
      const message = formatScreenMessage(value);
      if (!message) {
        return;
      }
      seen.add(key);
      messages.push(message);
    },
  );
  return messages;
};

const isRunningScreenTask = (status: string | undefined | null) => status === 'pending' || status === 'processing';

const formatScreenTaskFailure = (value: string | null | undefined, language: 'zh' | 'en') => {
  const text = String(value || '').trim();
  if (!text) {
    return language === 'en' ? 'The screening task failed. Please try again later.' : '筛选任务失败，请稍后重试。';
  }
  return language === 'en'
    ? `Screening task failed: ${text}`
    : `筛选任务失败：${summarizeAlphaSiftDiagnostic(text)}`;
};

const ALPHASIFT_HOTSPOT_NO_CACHE_HINT = 'No cached AlphaSift hotspot snapshot. Click refresh to fetch live hotspots.';
const ALPHASIFT_HOTSPOT_UNAVAILABLE_CODE = 'eastmoney_hotspot_unavailable';

const formatHotspotEmptyMessage = (result: AlphaSiftHotspotsResponse, language: 'zh' | 'en') => {
  const message = String(result.message || '').trim();
  const sourceErrors = result.sourceErrors || [];
  if (message && sourceErrors.includes(ALPHASIFT_HOTSPOT_UNAVAILABLE_CODE)) {
    return message;
  }
  if (message === ALPHASIFT_HOTSPOT_NO_CACHE_HINT) {
    return language === 'en'
      ? 'No cached market themes. Expand this section and refresh to request live data.'
      : '暂无缓存热点题材，展开后可点击刷新拉取实时数据。';
  }
  const sourceError = sourceErrors[0];
  if (sourceError) {
    return language === 'en'
      ? `Market theme data is temporarily unavailable: ${sourceError}`
      : `热点题材暂未返回数据：${summarizeAlphaSiftDiagnostic(sourceError)}`;
  }
  return language === 'en' ? 'Market theme data is temporarily unavailable.' : '热点题材暂未返回数据';
};

const ScreenAlertMessage: React.FC<{ messages: string[] }> = ({ messages }) => {
  if (messages.length <= 1) {
    return <span>{messages[0]}</span>;
  }
  return (
    <ul className="list-disc space-y-1 pl-4">
      {messages.map((message) => (
        <li key={message}>{message}</li>
      ))}
    </ul>
  );
};

const getRouteTimeLabel = (item: AlphaSiftHotspotDetail['route'][number], language: 'zh' | 'en') => {
  const rawTime = item.publishedAt || item.date || item.time || '';
  if (!rawTime) {
    return item.source || (language === 'en' ? 'Pending verification' : '待确认');
  }
  if (/^\d{4}-\d{2}-\d{2}$/.test(rawTime)) {
    return rawTime;
  }
  const parsed = new Date(rawTime);
  if (!Number.isNaN(parsed.getTime())) {
    return parsed.toLocaleString(language === 'en' ? 'en-US' : 'zh-CN', {
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      hour12: false,
    });
  }
  return rawTime;
};

const getHotspotRouteItems = (detail: AlphaSiftHotspotDetail) => {
  const route = detail.route || [];
  if (route.length > 0) {
    return route;
  }
  return detail.timeline || [];
};

const formatHotspotMetric = (value: unknown, language: 'zh' | 'en', digits = 1) => {
  const formatted = formatNumber(value, digits);
  return formatted === '-' ? (language === 'en' ? 'Pending' : '观察中') : formatted;
};

const getHotspotLeadersText = (item: AlphaSiftHotspot, language: 'zh' | 'en') => {
  const leaders = (item.leaders || []).map((value) => String(value).trim()).filter(Boolean);
  if (leaders.length > 0) {
    return leaders.slice(0, 2).join('、');
  }
  return language === 'en' ? 'Pending' : '观察中';
};

const getHotspotSampleText = (item: AlphaSiftHotspot, language: 'zh' | 'en') => {
  if (item.sampleStockCount == null || Number.isNaN(Number(item.sampleStockCount))) {
    return language === 'en' ? 'Active symbols pending' : '活跃股观察中';
  }
  return language === 'en' ? `${item.sampleStockCount} symbols` : `覆盖 ${item.sampleStockCount} 股`;
};

const formatStockChangeText = (value: unknown, language: 'zh' | 'en') => {
  const formatted = formatNumber(value);
  return formatted === '-' ? (language === 'en' ? 'Quote pending' : '行情待取') : `${formatted}%`;
};

const formatHotspotUpdatedAt = (value: string | null, language: 'zh' | 'en') => {
  if (!value) {
    return language === 'en' ? 'Pending refresh' : '待刷新';
  }
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }
  return parsed.toLocaleString(language === 'en' ? 'en-US' : 'zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  });
};

const getHotspotStrength = (item: AlphaSiftHotspot, index: number, language: 'zh' | 'en') => {
  const heat = Number(item.heatScore ?? 0);
  const changePct = Number(item.changePct ?? 0);
  if (index === 0 || heat >= 90 || changePct >= 8) {
    return { label: language === 'en' ? 'Highest activity' : '强势领先', className: 'bg-red-500/10 text-red-500' };
  }
  if (heat >= 80 || changePct >= 5) {
    return { label: language === 'en' ? 'High activity' : '强势', className: 'bg-blue-500/10 text-blue-500' };
  }
  return { label: language === 'en' ? 'Active' : '较强', className: 'bg-cyan/10 text-cyan' };
};

const HOTSPOT_ICON_RULES: Array<{
  pattern: RegExp;
  icon: React.ComponentType<{ className?: string }>;
  className: string;
}> = [
  { pattern: /金|银|铜|铝|铅|锌|钼|钴|镍|贵金属|矿|有色/, icon: Pickaxe, className: 'bg-orange-500/10 text-orange-500' },
  { pattern: /黄金|珠宝/, icon: Gem, className: 'bg-amber-500/10 text-amber-500' },
  { pattern: /油|气|能源|煤/, icon: Droplet, className: 'bg-yellow-700/10 text-yellow-700' },
  { pattern: /金融|券商|银行|保险|资本/, icon: Landmark, className: 'bg-orange-500/10 text-orange-500' },
  { pattern: /航空|机场|航天|运输/, icon: Plane, className: 'bg-blue-500/10 text-blue-500' },
  { pattern: /林业|农业|种植/, icon: Trees, className: 'bg-emerald-500/10 text-emerald-500' },
  { pattern: /医疗|诊断|卫生|医药/, icon: Stethoscope, className: 'bg-teal-500/10 text-teal-500' },
  { pattern: /食品|餐饮|酒/, icon: Utensils, className: 'bg-violet-500/10 text-violet-500' },
  { pattern: /工业|制造|修理|机械|设备/, icon: Wrench, className: 'bg-blue-500/10 text-blue-500' },
  { pattern: /租赁|地产|建筑/, icon: Building2, className: 'bg-emerald-500/10 text-emerald-500' },
  { pattern: /电|芯片|算力|AI|机器人/, icon: Factory, className: 'bg-indigo-500/10 text-indigo-500' },
  { pattern: /保险|安全/, icon: Shield, className: 'bg-blue-500/10 text-blue-500' },
];

const getHotspotIcon = (topic: string) => {
  const match = HOTSPOT_ICON_RULES.find((rule) => rule.pattern.test(topic));
  return match || { icon: Activity, className: 'bg-cyan/10 text-cyan' };
};

const MiniSparkline: React.FC<{ score?: number | null; selected?: boolean }> = ({ score, selected }) => {
  const normalizedScore = Number.isFinite(Number(score)) ? Math.max(0, Math.min(100, Number(score))) : 65;
  const lift = Math.max(0, Math.min(16, normalizedScore / 7));
  const path = `M2 35 C12 ${32 - lift / 4}, 16 ${34 - lift / 2}, 24 ${28 - lift / 3} S38 ${29 - lift}, 46 ${23 - lift / 2} S62 ${24 - lift}, 72 ${16 - lift / 3} S86 ${15 - lift}, 94 ${7}`;
  return (
    <svg className="h-8 w-20" viewBox="0 0 96 40" aria-hidden="true">
      <path d={`${path} L94 40 L2 40 Z`} fill={selected ? 'rgba(249,115,22,0.14)' : 'rgba(59,130,246,0.12)'} />
      <path d={path} fill="none" stroke={selected ? '#f97316' : '#3b82f6'} strokeLinecap="round" strokeWidth="2" />
    </svg>
  );
};

const StockScreeningPage: React.FC = () => {
  const navigate = useNavigate();
  const { language } = useUiLanguage();
  const [restoredTask] = useState<PersistedScreenTask | null>(() => readPersistedScreenTask());
  const [enabled, setEnabled] = useState(false);
  const [available, setAvailable] = useState(false);
  const [market, setMarket] = useState(restoredTask?.market || 'cn');
  const [strategy, setStrategy] = useState(restoredTask?.strategy || 'dual_low');
  const [strategies, setStrategies] = useState<AlphaSiftStrategy[]>([]);
  const [maxResults, setMaxResults] = useState(restoredTask?.maxResults || 3);
  const [candidates, setCandidates] = useState<AlphaSiftCandidate[]>([]);
  const [hotspots, setHotspots] = useState<AlphaSiftHotspot[]>([]);
  const [hotspotsUpdatedAt, setHotspotsUpdatedAt] = useState<string | null>(null);
  const [hotspotsExpanded, setHotspotsExpanded] = useState(false);
  const [selectedHotspotTopic, setSelectedHotspotTopic] = useState<string | null>(null);
  const selectedHotspotTopicRef = useRef<string | null>(null);
  const hotspotDetailRequestIdRef = useRef(0);
  const hotspotDetailsByTopicRef = useRef<Record<string, AlphaSiftHotspotDetail>>({});
  const [hotspotDetail, setHotspotDetail] = useState<AlphaSiftHotspotDetail | null>(null);
  const [loadingHotspotDetail, setLoadingHotspotDetail] = useState(false);
  const [hotspotDetailError, setHotspotDetailError] = useState('');
  const [loadingHotspots, setLoadingHotspots] = useState(false);
  const [hotspotError, setHotspotError] = useState('');
  const [screenMeta, setScreenMeta] = useState<AlphaSiftScreenResponse | null>(null);
  const [platformUserId, setPlatformUserId] = useState<number | null>(null);
  const [selectedCompareCodes, setSelectedCompareCodes] = useState<string[]>([]);
  const [watchlistStates, setWatchlistStates] = useState<Record<string, ScreeningWatchlistState>>({});
  const [reminderCode, setReminderCode] = useState<string | null>(null);
  const [reminderState, setReminderState] = useState<ScreeningReminderState>('idle');
  const [screeningActionMessage, setScreeningActionMessage] = useState('');
  const [loading, setLoading] = useState(Boolean(restoredTask?.taskId));
  const [enabling, setEnabling] = useState(false);
  const [loadingStrategies, setLoadingStrategies] = useState(false);
  const [error, setError] = useState('');
  const [strategyLoadError, setStrategyLoadError] = useState('');
  const [activeTaskId, setActiveTaskId] = useState<string | null>(restoredTask?.taskId ?? null);
  const [taskProgress, setTaskProgress] = useState(restoredTask?.taskId ? 10 : 0);
  const [taskMessage, setTaskMessage] = useState(restoredTask?.taskId ? '正在恢复筛选任务状态...' : '');

  useEffect(() => {
    let active = true;
    void platformApi.current()
      .then((payload) => {
        if (active) setPlatformUserId(payload?.user.id ?? null);
      })
      .catch(() => {
        if (active) setPlatformUserId(null);
      });
    return () => {
      active = false;
    };
  }, []);

  const selectedStrategy = useMemo(() => strategies.find((item) => item.id === strategy), [strategies, strategy]);
  const selectedStrategyView = strategyPresentation(strategy, language, {
    name: selectedStrategy?.name || selectedStrategy?.title,
    description: selectedStrategy?.description,
    category: selectedStrategy?.category || selectedStrategy?.tag || selectedStrategy?.tags?.[0],
  });
  const selectedStrategyTitle = selectedStrategyView.name;
  const selectedStrategyTag = selectedStrategyView.category;
  const displayedStrategy = selectedStrategy ? selectedStrategyTitle : `${selectedStrategyTitle} (${strategy})`;
  const screenMessages = useMemo(() => getScreenMessages(screenMeta), [screenMeta]);
  const llmDegraded = screenMeta?.llmRanked === false && screenMessages.some((message) => /LLM|API Key|模型/i.test(message));
  const alertMessages = llmDegraded
    ? screenMessages.length > 0
      ? screenMessages
      : ['LLM 重排未完成或未返回判断，当前候选来自 AlphaSift 本地因子评分。']
    : screenMessages;
  const isScreeningEnabled = enabled && available;
  const statusText = language === 'en'
    ? isScreeningEnabled ? 'Screening available' : 'Screening unavailable'
    : isScreeningEnabled ? '筛选已开启' : '筛选未开启';
  const markets = [{ id: 'cn', label: marketLabel(language) }];
  const localizedTaskMessage = language === 'en'
    ? taskProgress >= 75
      ? 'Organizing quote and source states'
      : taskProgress >= 60
        ? 'Checking candidate data coverage'
        : taskProgress >= 45
          ? 'Applying metric filters'
          : taskProgress >= 30
            ? 'Reading the full-market snapshot'
            : 'Submitting the market-data screen'
    : taskMessage;

  useEffect(() => {
    setScreeningActionMessage('');
  }, [language]);

  const applyScreenResult = useCallback((result: AlphaSiftScreenResponse) => {
    const nextCandidates = result.candidates || [];
    setScreenMeta(result);
    setCandidates(nextCandidates);
    setSelectedCompareCodes((current) => current.filter((code) => nextCandidates.some((item) => item.code === code)));
    setReminderCode(null);
    setReminderState('idle');
  }, []);

  const clearScreeningResults = () => {
    setCandidates([]);
    setScreenMeta(null);
    setSelectedCompareCodes([]);
    setReminderCode(null);
    setReminderState('idle');
    setScreeningActionMessage('');
  };

  const handleToggleCompare = (code: string) => {
    setSelectedCompareCodes((current) => toggleComparedCodes(current, code));
  };

  const handleAddWatchlist = async (code: string) => {
    if (!platformUserId) {
      setWatchlistStates((current) => ({ ...current, [code]: 'login-required' }));
      setScreeningActionMessage(language === 'en' ? 'Login to save a private watchlist.' : '登录后可保存个人自选。');
      return;
    }
    setWatchlistStates((current) => ({ ...current, [code]: 'saving' }));
    setScreeningActionMessage('');
    try {
      await platformApi.addWatchlistItem(code);
      setWatchlistStates((current) => ({ ...current, [code]: 'saved' }));
      setScreeningActionMessage(language === 'en' ? `${code} saved to watchlist.` : `${code} 已加入自选。`);
    } catch (err) {
      setWatchlistStates((current) => ({ ...current, [code]: 'error' }));
      setScreeningActionMessage(getParsedApiError(err).message || (language === 'en' ? 'Watchlist update failed.' : '自选保存失败。'));
    }
  };

  const handleOpenReminder = (code: string) => {
    setReminderCode(code);
    setReminderState(platformUserId ? 'idle' : 'login-required');
    setScreeningActionMessage('');
  };

  const handleSaveReminder = async (payload: ScreeningReminderSavePayload) => {
    if (!platformUserId) {
      setReminderState('login-required');
      return;
    }
    setReminderState('saving');
    try {
      await platformApi.saveWatchlistAlertRule({ ...payload, enabled: true });
      setReminderState('saved');
      setScreeningActionMessage(language === 'en' ? `${payload.stockCode} alert saved.` : `${payload.stockCode} 条件提醒已保存。`);
    } catch (err) {
      setReminderState('error');
      setScreeningActionMessage(getParsedApiError(err).message || (language === 'en' ? 'Alert save failed.' : '提醒保存失败。'));
    }
  };

  const handleOpenCandidateData = (code: string) => {
    const candidate = candidates.find((item) => item.code === code);
    navigate('/', {
      state: {
        stockCode: code,
        stockName: candidate?.name || '',
        autoAnalyze: false,
        selectionSource: 'market_screening',
      },
    });
  };

  const loadHotspotDetail = useCallback(async (topic: string, options: { refresh?: boolean } = {}) => {
    if (!topic) {
      return;
    }
    const cachedDetail = !options.refresh ? hotspotDetailsByTopicRef.current[topic] : null;
    if (cachedDetail) {
      setHotspotDetail(cachedDetail);
      setHotspotDetailError('');
      setLoadingHotspotDetail(false);
      return;
    }
    const requestId = hotspotDetailRequestIdRef.current + 1;
    hotspotDetailRequestIdRef.current = requestId;
    const isCurrentRequest = () => hotspotDetailRequestIdRef.current === requestId;
    const canApplyRequest = () => isCurrentRequest() && selectedHotspotTopicRef.current === topic;
    setLoadingHotspotDetail(true);
    setHotspotDetail((currentDetail) => (currentDetail?.topic === topic ? currentDetail : null));
    setHotspotDetailError('');
    try {
      const detail = await alphasiftApi.getHotspotDetail({ topic, provider: 'akshare', refresh: options.refresh ?? false });
      if (!canApplyRequest()) {
        return;
      }
      hotspotDetailsByTopicRef.current = {
        ...hotspotDetailsByTopicRef.current,
        [topic]: detail,
      };
      setHotspotDetail(detail);
    } catch (err) {
      if (!canApplyRequest()) {
        return;
      }
      setHotspotDetail(null);
      setHotspotDetailError(toApiErrorMessage(err, language === 'en' ? 'Market theme details failed to load. Please try again later.' : '热点题材详情加载失败，请稍后重试。'));
    } finally {
      if (isCurrentRequest()) {
        setLoadingHotspotDetail(false);
      }
    }
  }, [language]);

  const loadStrategies = useCallback(async () => {
    setLoadingStrategies(true);
    try {
      setStrategyLoadError('');
      const result = await alphasiftApi.getStrategies();
      const loadedStrategies = result.strategies || [];
      setStrategies(loadedStrategies);
      if (loadedStrategies.length > 0) {
        setStrategy((currentStrategy) =>
          loadedStrategies.some((item) => item.id === currentStrategy) ? currentStrategy : loadedStrategies[0].id,
        );
      }
    } catch (err) {
      setStrategies([]);
      setStrategyLoadError(err instanceof Error ? err.message : language === 'en' ? 'AlphaSift strategy list failed to load.' : 'AlphaSift 策略列表加载失败');
    } finally {
      setLoadingStrategies(false);
    }
  }, [language]);

  const loadHotspots = useCallback(async (refresh = false) => {
    setLoadingHotspots(true);
    setHotspotError('');
    try {
      const result = await alphasiftApi.getHotspots({ provider: 'akshare', top: 12, refresh });
      const nextHotspots = result.hotspots || [];
      const nextDetails = result.details || {};
      hotspotDetailsByTopicRef.current = {
        ...hotspotDetailsByTopicRef.current,
        ...nextDetails,
      };
      const currentTopic = selectedHotspotTopicRef.current;
      const retainedTopic = Boolean(currentTopic && nextHotspots.some((item) => item.topic === currentTopic));
      const nextTopic = retainedTopic ? currentTopic : null;
      setHotspots(nextHotspots);
      setHotspotsUpdatedAt(result.cachedAt || (nextHotspots.length > 0 ? new Date().toISOString() : null));
      setSelectedHotspotTopic(nextTopic);
      selectedHotspotTopicRef.current = nextTopic;
      if (nextTopic && nextDetails[nextTopic]) {
        setHotspotDetail(nextDetails[nextTopic]);
        setLoadingHotspotDetail(false);
      } else if (retainedTopic && refresh && nextTopic) {
        void loadHotspotDetail(nextTopic, { refresh: true });
      } else if (!retainedTopic) {
        setHotspotDetail(null);
      }
      setHotspotDetailError('');
      if (nextHotspots.length === 0) {
        setHotspotError(formatHotspotEmptyMessage(result, language));
      }
    } catch (err) {
      setHotspotError(toApiErrorMessage(err, language === 'en' ? 'Market themes failed to load. Please try again later.' : '热点题材加载失败，请稍后重试。'));
    } finally {
      setLoadingHotspots(false);
    }
  }, [language, loadHotspotDetail]);

  const handleHotspotSelect = useCallback((topic: string) => {
    selectedHotspotTopicRef.current = topic;
    setSelectedHotspotTopic(topic);
    const cachedDetail = hotspotDetailsByTopicRef.current[topic];
    if (cachedDetail) {
      setHotspotDetail(cachedDetail);
      setHotspotDetailError('');
      setLoadingHotspotDetail(false);
    } else {
      setHotspotDetail((currentDetail) => (currentDetail?.topic === topic ? currentDetail : null));
    }
  }, []);

  const toggleHotspotsExpanded = useCallback(() => {
    setHotspotsExpanded((expanded) => {
      const nextExpanded = !expanded;
      if (!nextExpanded) {
        selectedHotspotTopicRef.current = null;
        setSelectedHotspotTopic(null);
        setHotspotDetail(null);
        setHotspotDetailError('');
      }
      return nextExpanded;
    });
  }, []);

  const handleAnalyzeHotspotStock = useCallback((stock: AlphaSiftHotspotDetail['stocks'][number]) => {
    const stockCode = String(stock.code || '').trim();
    if (!stockCode) {
      return;
    }
    const stockName = String(stock.name || stockCode).trim();
    navigate('/', {
      state: {
        stockCode,
        stockName,
        autoAnalyze: true,
        selectionSource: 'alphasift_hotspot',
      },
    });
  }, [navigate]);

  useEffect(() => {
    selectedHotspotTopicRef.current = selectedHotspotTopic;
  }, [selectedHotspotTopic]);

  useEffect(() => {
    if (!selectedHotspotTopic) {
      return;
    }
    void loadHotspotDetail(selectedHotspotTopic);
  }, [loadHotspotDetail, selectedHotspotTopic]);

  useEffect(() => {
    let active = true;
    alphasiftApi
      .getStatus()
      .then((status) => {
        if (!active) {
          return;
        }
        setEnabled(status.enabled);
        setAvailable(status.available);
        if (status.enabled && status.available) {
          void loadStrategies();
          void loadHotspots(false);
        }
      })
      .catch(() => {
        if (active) {
          setEnabled(false);
          setAvailable(false);
        }
      });
    return () => {
      active = false;
    };
  }, [loadHotspots, loadStrategies]);

  useEffect(() => {
    if (!activeTaskId) {
      return undefined;
    }

    const pollingTaskId = activeTaskId;
    let active = true;
    let timer: number | undefined;

    function finishTask() {
      clearPersistedScreenTask();
      setActiveTaskId(null);
      setLoading(false);
    }

    function applyTaskStatus(task: AlphaSiftScreenTaskStatus) {
      const nextProgress = Number(task.progress ?? 0);
      setTaskProgress(Number.isFinite(nextProgress) ? nextProgress : 0);
      setTaskMessage(task.message || '');

      if (task.status === 'completed') {
        if (task.result) {
          applyScreenResult(task.result);
          setError('');
        } else {
          setError(language === 'en' ? 'The screen completed without a result payload.' : '筛选任务已完成，但服务端未返回候选结果。');
          setCandidates([]);
          setScreenMeta(null);
        }
        finishTask();
        return;
      }

      if (task.status === 'failed') {
        setCandidates([]);
        setScreenMeta(null);
        setSelectedCompareCodes([]);
        setReminderCode(null);
        setReminderState('idle');
        setError(formatScreenTaskFailure(task.error || task.message, language));
        finishTask();
        return;
      }

      if (isRunningScreenTask(task.status)) {
        setLoading(true);
        timer = window.setTimeout(pollTask, SCREEN_TASK_POLL_INTERVAL_MS);
        return;
      }

      setError(language === 'en' ? `Unknown screening task state: ${task.status || 'unknown'}` : `筛选任务返回未知状态：${task.status || 'unknown'}`);
      finishTask();
    }

    async function pollTask() {
      try {
        const task = await alphasiftApi.getScreenTask(pollingTaskId);
        if (!active) {
          return;
        }
        applyTaskStatus(task);
      } catch (err) {
        if (!active) {
          return;
        }
        const parsedError = getParsedApiError(err);
        setError(formatParsedApiError(parsedError) || (language === 'en' ? 'Screening task status is temporarily unavailable; retrying automatically.' : '暂时无法获取筛选任务状态，稍后将自动重试。'));
        if (isUnrecoverableScreenTaskError(parsedError)) {
          setCandidates([]);
          setScreenMeta(null);
          finishTask();
          return;
        }
        setLoading(true);
        timer = window.setTimeout(pollTask, SCREEN_TASK_POLL_INTERVAL_MS);
      }
    }

    void pollTask();

    return () => {
      active = false;
      if (timer) {
        window.clearTimeout(timer);
      }
    };
  }, [activeTaskId, applyScreenResult, language]);

  const handleEnable = async () => {
    setEnabling(true);
    setError('');
    try {
      await alphasiftApi.enable();
      setEnabled(true);
      setAvailable(true);
      await loadStrategies();
    } catch (err) {
      try {
        const status = await alphasiftApi.getStatus();
        setEnabled(status.enabled);
        setAvailable(status.available);
      } catch {
        setEnabled(false);
        setAvailable(false);
      }
      setError(err instanceof Error ? err.message : '开启 AlphaSift 失败');
    } finally {
      setEnabling(false);
    }
  };

  const handleStrategyChange = (nextStrategy: string) => {
    if (nextStrategy !== strategy) {
      clearScreeningResults();
    }
    setStrategy(nextStrategy);
  };

  const handleMarketChange = (nextMarket: string) => {
    if (nextMarket !== market) {
      clearScreeningResults();
    }
    setMarket(nextMarket);
  };

  const handleMaxResultsChange = (nextMaxResults: number) => {
    if (nextMaxResults !== maxResults) {
      clearScreeningResults();
    }
    setMaxResults(nextMaxResults);
  };

  const handleSubmit = async () => {
    setLoading(true);
    setError('');
    setScreenMeta(null);
    setTaskProgress(0);
    setTaskMessage(language === 'en' ? 'Submitting the market-data screen...' : '正在提交筛选任务...');
    try {
      const task = await alphasiftApi.startScreen({ market, strategy, maxResults });
      persistScreenTask({
        taskId: task.taskId,
        market,
        strategy,
        maxResults,
      });
      setActiveTaskId(task.taskId);
      setTaskProgress(0);
      setTaskMessage(task.message || (language === 'en' ? 'AlphaSift market-data screen submitted' : 'AlphaSift 数据筛选任务已提交'));
    } catch (err) {
      setCandidates([]);
      setLoading(false);
      setError(toApiErrorMessage(err, language === 'en' ? 'The screening task could not be submitted. Please try again later.' : '筛选任务提交失败，请稍后重试。'));
    }
  };

  return (
    <AppPage className="max-w-6xl space-y-6 pb-12 pt-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div className="flex items-center gap-3">
          <span className="grid h-7 w-7 place-items-center rounded-full border-2 border-cyan text-cyan shadow-[0_0_24px_hsl(var(--primary)/0.18)]">
            <PlusCircle className="h-4 w-4" />
          </span>
          <div>
            <h1 className="text-2xl font-bold tracking-normal text-foreground">
              {language === 'en' ? 'Market data screening' : '市场数据筛选'}
            </h1>
            <p className="mt-1 text-sm text-secondary-text">
              {language === 'en'
                ? 'Filter factual market data, compare results and create user-defined condition alerts.'
                : '按事实型市场数据筛选、横向比较，并设置用户自定义条件提醒。'}
            </p>
          </div>
        </div>

        <div className="inline-flex w-fit items-center gap-2 rounded-2xl border border-border/70 bg-card/80 px-4 py-2 text-sm shadow-soft-card">
          <span className={`h-2.5 w-2.5 rounded-full ${isScreeningEnabled ? 'bg-success' : 'bg-warning'}`} />
          <span className="font-medium text-secondary-text">{statusText}</span>
        </div>
      </div>

      {!enabled ? (
        <InlineAlert
          variant="info"
          title={language === 'en' ? 'AlphaSift is disabled' : 'AlphaSift 未开启'}
          message={language === 'en' ? 'Enable the local AlphaSift adapter. If the dependency is missing, update the backend environment first.' : '点击后写入 ALPHASIFT_ENABLED=true；AlphaSift 已随后端依赖安装，若适配层缺失请先更新依赖或重建后端。'}
          action={
            <Button size="sm" isLoading={enabling} loadingText={language === 'en' ? 'Enabling...' : '开启中...'} onClick={() => void handleEnable()}>
              {language === 'en' ? 'Enable AlphaSift' : '开启 AlphaSift'}
            </Button>
          }
        />
      ) : null}

      {enabled && !available ? (
        <InlineAlert
          variant="warning"
          title={language === 'en' ? 'AlphaSift adapter unavailable' : 'AlphaSift 适配层不可用'}
          message={language === 'en' ? 'Confirm that the backend dependency is installed and restart the local service.' : '适配层当前不可用，请先确认后端已安装依赖并重启服务，必要时执行 pip install -r requirements.txt 或使用设置页/服务端 /install 接口进行修复安装。'}
        />
      ) : null}

      <InlineAlert
        variant="warning"
        title={language === 'en' ? 'Information and data boundary' : '资讯与数据边界提醒'}
        message={language === 'en'
          ? 'This page provides market information, observed data and user-defined alerts only. It does not provide investment advice, trading instructions, target prices or return forecasts.'
          : '本页只提供市场资讯、已观测数据和用户自定义提醒，不提供投资建议、交易指令、目标价或收益预测。'}
      />

      {loading ? (
        <InlineAlert
          variant="info"
          title={language === 'en' ? 'Screening task in progress' : '筛选任务运行中'}
          message={`${localizedTaskMessage || (language === 'en' ? 'Running the market-data screen' : '正在执行市场数据筛选')} · ${language === 'en' ? 'Task' : '任务 ID'}: ${activeTaskId ? activeTaskId.slice(0, 12) : '-'}`}
        />
      ) : null}

      {error ? <InlineAlert variant="danger" title={language === 'en' ? 'Request failed' : '调用失败'} message={error} /> : null}

      <section className="rounded-2xl border border-border/80 bg-card/95 p-4 shadow-soft-card">
        <div className="mb-4 flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
          <div className="flex items-start gap-3">
            <span className="grid h-10 w-10 shrink-0 place-items-center rounded-full bg-orange-500/10 text-orange-500 shadow-[0_10px_30px_rgba(249,115,22,0.16)]">
              <Flame className="h-5 w-5" />
            </span>
            <div>
              <h2 className="text-lg font-bold tracking-normal text-foreground">{language === 'en' ? 'Market themes' : '热点题材'}</h2>
              <p className="mt-1 text-xs leading-5 text-secondary-text">
                {language === 'en' ? 'AlphaSift theme-activity data provides a factual market context for supported filters.' : '来自 AlphaSift 最新热点数据；部分筛选条件会把题材活跃度纳入指标。'}
              </p>
            </div>
          </div>
          <div className="flex flex-col items-start gap-2 lg:items-end">
            <div className="flex flex-wrap items-center gap-2">
              <Button
                size="sm"
                variant="secondary"
                disabled={!isScreeningEnabled}
                onClick={toggleHotspotsExpanded}
              >
                <Bookmark className="h-4 w-4" />
                {hotspotsExpanded
                  ? language === 'en' ? 'Collapse market themes' : '收起热点题材'
                  : language === 'en' ? `Expand market themes${hotspots.length ? ` (${hotspots.length})` : ''}` : `展开热点题材${hotspots.length ? `（${hotspots.length}）` : ''}`}
                <ChevronDown className={`h-4 w-4 transition-transform ${hotspotsExpanded ? 'rotate-180' : ''}`} />
              </Button>
              {hotspotsExpanded ? (
              <Button
                size="sm"
                variant="secondary"
                isLoading={loadingHotspots}
                loadingText={language === 'en' ? 'Refreshing...' : '刷新中...'}
                disabled={!isScreeningEnabled || loadingHotspots}
                onClick={() => void loadHotspots(true)}
              >
                <RefreshCw className="h-4 w-4" />
                {language === 'en' ? 'Refresh themes' : '刷新热点题材'}
              </Button>
              ) : null}
            </div>
            <p className="text-xs text-secondary-text">{language === 'en' ? 'Updated: ' : '更新时间：'}{formatHotspotUpdatedAt(hotspotsUpdatedAt, language)}</p>
          </div>
        </div>

        {hotspotError ? (
          <p className="mb-3 rounded-xl border border-warning/30 bg-warning/10 px-3 py-2 text-xs text-warning">
            {hotspotError}
          </p>
        ) : null}

        {!hotspotsExpanded ? (
          <div className="flex flex-col gap-2 rounded-xl border border-border/70 bg-surface/70 px-4 py-3 text-sm text-secondary-text sm:flex-row sm:items-center sm:justify-between">
            <span>
              {hotspots.length > 0
                ? language === 'en' ? `${hotspots.length} market themes cached. Expand to inspect activity and source details.` : `已缓存 ${hotspots.length} 个热点题材，展开后可查看热度、阶段和来源。`
                : language === 'en' ? 'Market themes are collapsed by default. Expand to read cache or refresh for live data.' : '热点题材默认折叠；展开后可读取缓存，点击刷新才拉取实时数据。'}
            </span>
            <span className="text-xs">{language === 'en' ? 'Details load after selecting a theme' : '实时详情会在选择具体题材后加载'}</span>
          </div>
        ) : hotspots.length === 0 ? (
          <div className="rounded-xl border border-dashed border-border bg-surface/70 px-4 py-6 text-sm text-secondary-text">
            {language === 'en' ? 'Refresh requests current concept and industry rankings, activity metrics and representative symbols.' : '点击刷新后会拉取热点概念/行业排行、活跃度指标和代表性股票。'}
          </div>
        ) : (
          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4">
            {hotspots.map((item, index) => {
              const selected = selectedHotspotTopic === item.topic;
              const strength = getHotspotStrength(item, index, language);
              const iconMeta = getHotspotIcon(item.name || item.topic);
              const Icon = iconMeta.icon;
              return (
              <button
                key={`${item.topic}-${item.rank ?? ''}`}
                className={`group relative min-h-[116px] overflow-hidden rounded-xl border px-3 py-3 text-left transition-all ${
                  selected
                    ? 'border-orange-400 bg-gradient-to-br from-orange-500/10 via-card to-card shadow-[0_0_0_1px_rgba(249,115,22,0.16),0_18px_44px_rgba(249,115,22,0.14)]'
                    : 'border-border/80 bg-card hover:-translate-y-0.5 hover:border-orange-300/70 hover:shadow-soft-card'
                }`}
                type="button"
                onClick={() => handleHotspotSelect(item.topic)}
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="flex min-w-0 items-start gap-3">
                    <span
                      className={`grid h-6 w-6 shrink-0 place-items-center rounded-full text-xs font-bold ${
                        index < 3 ? 'bg-orange-500 text-white shadow-[0_8px_24px_rgba(249,115,22,0.24)]' : 'bg-surface text-secondary-text'
                      }`}
                    >
                      {index + 1}
                    </span>
                    <span className={`grid h-9 w-9 shrink-0 place-items-center rounded-full ${iconMeta.className}`}>
                      <Icon className="h-5 w-5" />
                    </span>
                    <div className="min-w-0">
                      <p className="truncate text-sm font-bold text-foreground">{item.name || item.topic}</p>
                      <span className={`mt-1 inline-flex rounded-md px-1.5 py-0.5 text-[11px] font-semibold ${strength.className}`}>
                        {strength.label}
                      </span>
                    </div>
                  </div>
                  <span className="shrink-0 text-2xl font-black leading-none text-orange-500">
                    {formatNumber(item.heatScore, 0)}
                  </span>
                </div>
                <div className="mt-4 grid max-w-[72%] gap-1 text-[11px] text-secondary-text">
                  <span>{language === 'en' ? 'Change' : '涨跌幅'} <strong className="font-semibold text-foreground">{formatHotspotMetric(item.changePct, language)}%</strong></span>
                  <span>{language === 'en' ? 'Trend' : '趋势'} <strong className="font-semibold text-foreground">{formatHotspotMetric(item.trendScore, language)}</strong> · {language === 'en' ? 'Persistence' : '持续'} <strong className="font-semibold text-foreground">{formatHotspotMetric(item.persistenceScore, language)}</strong></span>
                  <span>{getHotspotSampleText(item, language)} · {language === 'en' ? 'Representatives' : '代表'} {getHotspotLeadersText(item, language)}</span>
                </div>
                <div className="absolute bottom-3 right-3 opacity-95 transition-transform group-hover:scale-105">
                  <MiniSparkline score={item.heatScore} selected={selected} />
                </div>
              </button>
              );
            })}
          </div>
        )}

        {hotspotsExpanded && selectedHotspotTopic ? (
          <div className="mt-4 rounded-xl border border-border/80 bg-surface/80 p-4">
            <div className="mb-3 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <h3 className="text-sm font-semibold text-foreground">
                  {hotspotDetail?.name || selectedHotspotTopic}
                </h3>
                <p className="mt-1 text-xs leading-5 text-secondary-text">
                  {loadingHotspotDetail
                    ? language === 'en' ? 'Loading source timeline and related symbols...' : '正在读取来源时间线与相关股票...'
                    : hotspotDetail?.summary || (language === 'en' ? 'Select a theme to inspect its source timeline and related symbols.' : '点击题材查看来源时间线与相关股票。')}
                </p>
                {hotspotDetail?.canonicalTopic && hotspotDetail.canonicalTopic !== selectedHotspotTopic ? (
                  <p className="mt-1 text-[11px] text-secondary-text">{language === 'en' ? 'Canonical theme: ' : '标准题材：'}{hotspotDetail.canonicalTopic}</p>
                ) : null}
              </div>
              <div className="flex flex-wrap items-center gap-2">
                {hotspotDetail?.qualityStatus ? (
                  <span className="w-fit rounded-full bg-warning/10 px-3 py-1 text-xs font-semibold text-warning">
                    {language === 'en' ? 'Quality' : '质量'} {hotspotDetail.qualityStatus}
                  </span>
                ) : null}
                {hotspotDetail?.fallbackUsed || hotspotDetail?.stale ? (
                  <span className="w-fit rounded-full bg-warning/10 px-3 py-1 text-xs font-semibold text-warning">
                    {hotspotDetail.staleAgeHours != null
                      ? language === 'en' ? `Cached fallback ${formatNumber(hotspotDetail.staleAgeHours, 1)}h` : `缓存回退 ${formatNumber(hotspotDetail.staleAgeHours, 1)}h`
                      : language === 'en' ? 'Cached fallback' : '缓存回退'}
                  </span>
                ) : null}
                {hotspotDetail?.stockCount != null ? (
                  <span className="w-fit rounded-full bg-orange-500/10 px-3 py-1 text-xs font-semibold text-orange-500">
                    {language === 'en' ? 'Related symbols' : '相关股票'} {hotspotDetail.stockCount}
                  </span>
                ) : null}
              </div>
            </div>

            {hotspotDetailError ? (
              <p className="mb-3 rounded-xl border border-warning/30 bg-warning/10 px-3 py-2 text-xs text-warning">
                {hotspotDetailError}
              </p>
            ) : null}

            {hotspotDetail && ((hotspotDetail.missingFields || []).length > 0 || (hotspotDetail.sourceErrors || []).length > 0) ? (
              <details className="mb-3 rounded-xl border border-warning/30 bg-warning/10 px-3 py-2 text-xs text-warning">
                <summary className="cursor-pointer font-semibold">{language === 'en' ? 'Theme details are degraded; expand for diagnostics' : '详情数据已降级，展开查看原因'}</summary>
                <div className="mt-2 space-y-1 leading-5">
                  {(hotspotDetail.missingFields || []).length > 0 ? (
                    <p>{language === 'en' ? 'Missing fields: ' : '缺失字段：'}{(hotspotDetail.missingFields || []).join(', ')}</p>
                  ) : null}
                  {(hotspotDetail.sourceErrors || []).slice(0, 4).map((message, index) => (
                    <p key={`${message}-${index}`}>{message}</p>
                  ))}
                </div>
              </details>
            ) : null}

            {hotspotDetail ? (
              <div className="grid gap-4 lg:grid-cols-[1fr_1.3fr]">
                <div>
                  <p className="mb-3 flex items-center gap-1.5 text-xs font-semibold text-secondary-text">
                    <Clock3 className="h-3.5 w-3.5 text-orange-500" />
                    {language === 'en' ? 'Source timeline' : '来源时间线'}
                  </p>
                  <div className="relative space-y-0 pl-4 before:absolute before:bottom-3 before:left-[5px] before:top-2 before:w-px before:bg-border">
                    {getHotspotRouteItems(hotspotDetail).map((item, index) => (
                      <div key={`${item.title}-${index}`} className="relative pb-4 last:pb-0">
                        <span className="absolute -left-4 top-1 h-2.5 w-2.5 rounded-full border border-orange-400 bg-card" />
                        <div className="rounded-lg border border-border/70 bg-card/80 p-3">
                          <p className="text-[11px] font-semibold text-orange-500">{getRouteTimeLabel(item, language)}</p>
                          <p className="mt-1 text-xs font-semibold text-foreground">{item.title}</p>
                          <p className="mt-1 text-xs leading-5 text-secondary-text">{item.description}</p>
                          {item.source ? <p className="mt-2 text-[11px] text-secondary-text">{language === 'en' ? 'Source' : '来源'} {item.source}</p> : null}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
                <div>
                  <p className="mb-2 text-xs font-semibold text-secondary-text">{language === 'en' ? 'Related symbols' : '相关股票'}</p>
                  <div className="grid gap-2 sm:grid-cols-2">
                    {(hotspotDetail.stocks || []).slice(0, 10).map((stock) => (
                      <div key={`${stock.code || stock.name}`} className="rounded-lg border border-border/70 bg-card/80 p-3">
                        <div className="flex items-start justify-between gap-2">
                          <div className="min-w-0">
                            <p className="truncate text-xs font-semibold text-foreground">{stock.name || stock.code || '-'}</p>
                            <p className="mt-1 text-[11px] text-secondary-text">{stock.code || '-'}</p>
                          </div>
                          <div className="flex shrink-0 items-center gap-1">
                            <span className="rounded-full bg-cyan/10 px-2 py-1 text-[11px] font-semibold text-cyan">
                              {stock.role || (language === 'en' ? 'Related symbol' : '相关股票')}
                            </span>
                            {stock.code ? (
                              <button
                                type="button"
                                aria-label={`${language === 'en' ? 'Open data for' : '打开数据'} ${stock.name || stock.code}`}
                                className="inline-flex h-7 items-center gap-1 rounded-full border border-cyan/30 bg-cyan/10 px-2 text-[11px] font-semibold text-cyan transition-colors hover:border-cyan hover:bg-cyan/15 hover:text-foreground"
                                onClick={() => handleAnalyzeHotspotStock(stock)}
                              >
                                <Play className="h-3 w-3" />
                                {language === 'en' ? 'Open data' : '打开数据'}
                              </button>
                            ) : null}
                          </div>
                        </div>
                        <p className="mt-2 text-[11px] text-secondary-text">
                          {language === 'en' ? 'Change' : '涨跌幅'} {formatStockChangeText(stock.changePct, language)} · {language === 'en' ? 'Activity' : '活跃度'} {formatNumber(stock.hotStockScore, 0)}
                        </p>
                        {stock.source || stock.sourceConfidence != null || stock.fallbackUsed ? (
                          <p className="mt-1 text-[11px] text-secondary-text">
                            {language === 'en' ? 'Source' : '来源'} {stock.source || '-'}
                            {stock.sourceConfidence != null ? ` · ${language === 'en' ? 'confidence' : '置信'} ${formatPercent(stock.sourceConfidence)}` : ''}
                            {stock.fallbackUsed ? ` · ${language === 'en' ? 'fallback' : '回退'}` : ''}
                          </p>
                        ) : null}
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            ) : null}
          </div>
        ) : null}
      </section>

      <section className="rounded-2xl border border-cyan/35 bg-card/95 p-4 shadow-soft-card">
        <div className="mb-4 flex items-center justify-between gap-3">
          <div>
            <h2 className="text-sm font-semibold text-foreground">{language === 'en' ? 'Choose a data filter' : '选择筛选条件'}</h2>
            <p className="mt-1 text-xs text-secondary-text">{language === 'en' ? 'Filters come from AlphaSift; DSA adds quote, profile and source-availability data.' : '筛选条件来自 AlphaSift；DSA 会补充行情、公司资料和来源状态。'}</p>
          </div>
          <span className="rounded-full border border-cyan/30 bg-cyan/10 px-3 py-1 text-xs font-semibold text-cyan">
            {selectedStrategyTag}
          </span>
        </div>

        <div className="grid gap-2 md:grid-cols-2 xl:grid-cols-4">
          {loadingStrategies ? (
            <div className="rounded-xl border border-dashed border-border bg-surface/70 p-4 text-sm text-secondary-text">
              {language === 'en' ? 'Loading available filters...' : '正在读取可用筛选条件...'}
            </div>
          ) : strategies.length === 0 ? (
            <div className="rounded-xl border border-dashed border-border bg-surface/70 p-4 text-sm text-secondary-text">
              {strategyLoadError || (language === 'en' ? 'AlphaSift filters are unavailable; enter a filter id below.' : 'AlphaSift 筛选条件暂未载入，可在下方手动输入筛选参数。')}
            </div>
          ) : (
            strategies.map((item) => {
              const selected = item.id === strategy;
              const itemView = strategyPresentation(item.id, language, {
                name: item.name || item.title,
                description: item.description,
                category: item.category || item.tag || item.tags?.[0],
              });
              return (
                <button
                  key={item.id}
                  className={`min-h-28 rounded-xl border p-4 text-left transition-all ${
                    selected
                      ? 'border-cyan bg-cyan/10 shadow-[0_0_0_1px_hsl(var(--primary)/0.15),0_16px_36px_hsl(var(--primary)/0.12)]'
                      : 'border-border/80 bg-surface/70 hover:border-cyan/45 hover:bg-hover/70'
                  }`}
                  type="button"
                  disabled={loading}
                  onClick={() => handleStrategyChange(item.id)}
                >
                  <span className="text-base font-semibold text-foreground">{itemView.name}</span>
                  <span className="mt-2 block text-sm leading-6 text-secondary-text">{itemView.description}</span>
                  <span className="mt-3 inline-flex text-xs font-semibold text-cyan">
                    {itemView.category}
                  </span>
                </button>
              );
            })
          )}
        </div>
      </section>

      {screenMeta ? (
      <section className="rounded-lg border border-border bg-card/95 p-4 shadow-soft-card">
        <div className="mb-5 flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <h2 className="text-base font-semibold text-foreground">
              {language === 'en' ? 'Market data screening results' : '市场数据筛选结果'}
            </h2>
            <p className="mt-2 max-w-3xl text-sm leading-6 text-secondary-text">
              {language === 'en'
                ? 'Review matched conditions, observed metrics, source freshness and data coverage. This page provides information and data only.'
                : '查看条件匹配、观测指标、来源新鲜度和数据覆盖。本页仅提供资讯与数据，不提供投资建议。'}
            </p>
          </div>
          <div className="flex items-center gap-2 rounded-lg border border-border bg-surface px-3 py-2 text-xs text-secondary-text">
            <Search className="h-4 w-4 text-cyan" />
            {language === 'en' ? `${candidates.length} results` : `${candidates.length} 条结果`}
          </div>
        </div>

        {screeningActionMessage ? (
          <p className="mb-4 rounded-lg border border-border bg-surface px-3 py-2 text-sm text-secondary-text" role="status">
            {screeningActionMessage}
          </p>
        ) : null}

        <ScreeningCompareTrayV104
          candidates={candidates}
          selectedCodes={selectedCompareCodes}
          language={language}
          onRemove={handleToggleCompare}
          onClear={() => setSelectedCompareCodes([])}
          onOpenData={handleOpenCandidateData}
        />

        {reminderCode ? (
          <div className="mb-4">
            <ScreeningReminderPanelV104
              key={reminderCode}
              stockCode={reminderCode}
              language={language}
              state={reminderState}
              onClose={() => {
                setReminderCode(null);
                setReminderState('idle');
              }}
              onSave={handleSaveReminder}
            />
          </div>
        ) : null}

        {candidates.length === 0 ? (
          <div className="rounded-lg border border-dashed border-border bg-surface/70 px-5 py-10 text-center">
            <p className="text-sm font-medium text-foreground">{language === 'en' ? 'No results yet' : '暂无结果'}</p>
            <p className="mt-2 text-sm text-secondary-text">
              {language === 'en' ? 'Run a data screen to generate a factual candidate list.' : '运行数据筛选后生成事实型候选列表。'}
            </p>
          </div>
        ) : (
          <div className="grid gap-4 xl:grid-cols-2">
            {candidates.map((candidate) => (
              <MarketScreeningCardV104
                key={`${candidate.rank}-${candidate.code}`}
                candidate={candidate}
                language={language}
                selected={selectedCompareCodes.includes(candidate.code)}
                compareDisabled={selectedCompareCodes.length >= MAX_SCREENING_COMPARE}
                watchlistState={watchlistStates[candidate.code] || 'idle'}
                onToggleCompare={handleToggleCompare}
                onAddWatchlist={(code) => void handleAddWatchlist(code)}
                onOpenData={handleOpenCandidateData}
                onOpenReminder={handleOpenReminder}
              />
            ))}
          </div>
        )}
      </section>
      ) : null}

      <section className="rounded-2xl border border-border bg-card/95 p-4 shadow-soft-card">
        <div className="mb-4 flex items-center gap-2 text-sm font-semibold text-foreground">
          <SlidersHorizontal className="h-4 w-4 text-cyan" />
          {language === 'en' ? 'Filter settings' : '筛选设置'}
        </div>

        <div className="grid gap-4 lg:grid-cols-[1fr_1.2fr_180px_auto] lg:items-end">
          <label className="space-y-2 text-xs font-medium text-secondary-text">
            {language === 'en' ? 'Market' : '市场'}
            <select
              className="h-11 w-full rounded-xl border border-border bg-surface px-3 text-sm text-foreground outline-none transition-colors focus:border-cyan"
              value={market}
              disabled={loading}
              onChange={(event) => handleMarketChange(event.target.value)}
            >
              {markets.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.label}
                </option>
              ))}
            </select>
          </label>

          <label className="space-y-2 text-xs font-medium text-secondary-text">
            {language === 'en' ? 'Filter id' : '筛选参数'}
            <input
              className="h-11 w-full rounded-xl border border-border bg-surface px-3 text-sm text-foreground outline-none transition-colors focus:border-cyan"
              value={strategy}
              disabled={loading}
              onChange={(event) => handleStrategyChange(event.target.value)}
            />
          </label>

          <label className="space-y-2 text-xs font-medium text-secondary-text">
            {language === 'en' ? 'Result count' : '返回数量'}
            <input
              className="h-11 w-full rounded-xl border border-border bg-surface px-3 text-sm text-foreground outline-none transition-colors focus:border-cyan"
              type="number"
              min={1}
              max={100}
              value={maxResults}
              disabled={loading}
              onChange={(event) => handleMaxResultsChange(Number(event.target.value))}
            />
          </label>

          <Button
            className="h-11 min-w-40"
            isLoading={loading}
            loadingText={language === 'en' ? 'Screening...' : '筛选中...'}
            disabled={!isScreeningEnabled || loading}
            onClick={() => void handleSubmit()}
          >
            <Play className="h-4 w-4" />
            {language === 'en' ? 'Run screen' : '运行筛选'}
          </Button>
        </div>
      </section>

      <section className="rounded-2xl border border-border bg-card/95 p-4 shadow-soft-card">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-center gap-3">
            <span
              className={`grid h-7 w-7 place-items-center rounded-full ${
                candidates.length > 0 ? 'text-success' : isScreeningEnabled ? 'text-cyan' : 'text-warning'
              }`}
            >
              {candidates.length > 0 ? <CheckCircle2 className="h-5 w-5" /> : <CircleAlert className="h-5 w-5" />}
            </span>
            <div>
              <h2 className="text-sm font-semibold text-foreground">
                {language === 'en'
                  ? loading ? 'Screening in progress' : candidates.length > 0 ? 'Screening complete' : isScreeningEnabled ? 'Ready to run' : 'Waiting for availability'
                  : loading ? '筛选运行中' : candidates.length > 0 ? '筛选完成' : isScreeningEnabled ? '等待运行' : '等待开启'}
              </h2>
              <p className="mt-1 text-xs text-secondary-text">
                {loading
                  ? `${localizedTaskMessage || (language === 'en' ? 'Running the market-data screen' : '正在执行市场数据筛选')} · ${taskProgress}%`
                  : `${language === 'en' ? 'Current filter: ' : '当前筛选：'}${displayedStrategy} · ${markets.find((item) => item.id === market)?.label}`}
              </p>
            </div>
          </div>
          <div className="grid gap-1 text-xs text-secondary-text sm:text-right">
            <span>{language === 'en' ? 'Task: ' : '任务：'}{activeTaskId ? activeTaskId.slice(0, 12) : '-'}</span>
            <span>Run ID{language === 'en' ? ': ' : '：'}{screenMeta?.runId || '-'}</span>
            <span>
              {language === 'en' ? 'Snapshot' : '快照'} {screenMeta?.snapshotCount ?? '-'} · {language === 'en' ? 'Matched' : '过滤后'} {screenMeta?.afterFilterCount ?? '-'} · {language === 'en' ? 'Results' : '结果'} {screenMeta?.candidateCount ?? candidates.length}
            </span>
            <span>
              AI: {screenMeta?.llmRanked ? language === 'en' ? 'Used for ordering' : '已用于排序' : screenMeta ? llmDegraded ? language === 'en' ? 'Degraded to local metrics' : '已降级为本地评分' : language === 'en' ? 'Not used' : '未使用' : '-'}
              {screenMeta?.llmCoverage != null ? ` · ${language === 'en' ? 'coverage' : '覆盖'} ${formatPercent(screenMeta.llmCoverage)}` : ''}
            </span>
            <span>
              {language === 'en' ? 'DSA data enrichment: ' : 'DSA数据补充：'}{screenMeta?.dsaEnrichment?.enrichedCount ?? '-'} / {screenMeta?.dsaEnrichment?.requestedCount ?? '-'}
            </span>
          </div>
        </div>
      </section>

      {screenMeta && alertMessages.length > 0 ? (
        <InlineAlert
          variant={llmDegraded ? 'warning' : 'info'}
          title={llmDegraded ? language === 'en' ? 'LLM degraded' : 'LLM 已降级' : language === 'en' ? 'AlphaSift notice' : 'AlphaSift 提示'}
          message={<ScreenAlertMessage messages={alertMessages} />}
        />
      ) : null}

    </AppPage>
  );
};

export default StockScreeningPage;
