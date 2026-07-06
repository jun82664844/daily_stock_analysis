import type React from 'react';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Archive, ArchiveRestore, BarChart3, Check, Download, Eye, Flag, KeyRound, LogOut, Plus, RefreshCw, Save, Search, SlidersHorizontal, Sparkles, Star, UserRound } from 'lucide-react';
import { useLocation, useNavigate } from 'react-router-dom';
import { getParsedApiError, type ParsedApiError } from '../api/error';
import { analysisApi } from '../api/analysis';
import { historyApi } from '../api/history';
import { platformApi, type PlatformAccountSummary, type PlatformApiKeyItem, type PlatformAuthPayload, type PlatformQuota, type PlatformWatchlistRefreshResponse, type PlatformWatchlistResponse } from '../api/platform';
import { stocksApi, type BasicStockSnapshot, type KronosForecastResponse } from '../api/stocks';
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

const toFiniteBasicNumber = (value: unknown): number | null => (
  typeof value === 'number' && Number.isFinite(value) ? value : null
);

const clampBasicScore = (value: unknown): number => {
  const numberValue = toFiniteBasicNumber(value);
  if (numberValue === null) {
    return 0;
  }
  return Math.max(0, Math.min(100, Math.round(numberValue)));
};

const formatSignedBasicPercent = (value: unknown): string => {
  const numberValue = toFiniteBasicNumber(value);
  if (numberValue === null) {
    return '-';
  }
  const formatted = formatBasicPercent(numberValue);
  return numberValue > 0 ? `+${formatted}` : formatted;
};

const formatSignedBasicTrendPercent = (value: unknown): string => {
  const numberValue = toFiniteBasicNumber(value);
  if (numberValue === null) {
    return '-';
  }
  const formatted = `${numberValue.toLocaleString(undefined, { maximumFractionDigits: 2 })}%`;
  return numberValue > 0 ? `+${formatted}` : formatted;
};

const uniqueBasicLevels = (values: Array<number | null>): number[] => {
  const rounded = new Map<string, number>();
  values.forEach((value) => {
    if (value === null || !Number.isFinite(value)) {
      return;
    }
    const key = value.toFixed(4);
    if (!rounded.has(key)) {
      rounded.set(key, value);
    }
  });
  return Array.from(rounded.values());
};

const buildBasicSparkline = (
  points: Array<{ close?: number | null }>,
): {
  linePoints: string;
  areaPoints: string;
  minClose: number;
  maxClose: number;
  changePercent: number | null;
} | null => {
  const closes = points
    .map((point) => toFiniteBasicNumber(point.close))
    .filter((value): value is number => value !== null);
  if (closes.length < 2) {
    return null;
  }
  const width = 220;
  const height = 72;
  const padding = 6;
  const minClose = Math.min(...closes);
  const maxClose = Math.max(...closes);
  const spread = maxClose - minClose || Math.max(Math.abs(maxClose), 1) * 0.01;
  const linePoints = closes.map((close, index) => {
    const x = padding + (index / Math.max(closes.length - 1, 1)) * (width - padding * 2);
    const y = height - padding - ((close - minClose) / spread) * (height - padding * 2);
    return `${x.toFixed(2)},${y.toFixed(2)}`;
  }).join(' ');
  const firstClose = closes[0];
  const lastClose = closes[closes.length - 1];
  return {
    linePoints,
    areaPoints: `${padding},${height - padding} ${linePoints} ${width - padding},${height - padding}`,
    minClose,
    maxClose,
    changePercent: firstClose === 0 ? null : ((lastClose - firstClose) / firstClose) * 100,
  };
};

const volumePriceSignalLabel = (value: unknown, language: string): string => {
  const signal = typeof value === 'string' ? value : '';
  const isEnglish = language === 'en';
  if (signal === 'price_volume_confirmed') return isEnglish ? 'Price-volume confirmed' : '价量确认';
  if (signal === 'price_above_trend_volume_soft') return isEnglish ? 'Price above trend' : '价在趋势上方';
  if (signal === 'price above trend volume soft') return isEnglish ? 'Price above trend, soft volume' : '价格位于趋势上方但量能偏弱';
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

const basicIntelligenceCategoryLabel = (category: string, fallback: string, language: string): string => {
  const isEnglish = language === 'en';
  if (category === 'news') return isEnglish ? 'News' : '新闻';
  if (category === 'announcements') return isEnglish ? 'Announcements' : '公告';
  if (category === 'financials') return isEnglish ? 'Financial snapshot' : '财报';
  return fallback || category || '-';
};

const basicIntelligenceStatusLabel = (status: string, language: string): string => {
  const isEnglish = language === 'en';
  if (status === 'available') return isEnglish ? 'available' : '可用';
  if (status === 'degraded') return isEnglish ? 'degraded' : '降级';
  if (status === 'unavailable') return isEnglish ? 'unavailable' : '暂无';
  return status || '-';
};

const basicWatchPriorityLabel = (priority: string, language: string): string => {
  const isEnglish = language === 'en';
  if (priority === 'high') return isEnglish ? 'high' : '重点';
  if (priority === 'medium') return isEnglish ? 'medium' : '关注';
  if (priority === 'low') return isEnglish ? 'low' : '参考';
  return priority || '-';
};

const GENERATED_TEXT_ZH: Record<string, string> = {
  'Weak quick signal': '快速信号偏弱',
  'Strong quick signal': '快速信号较强',
  Trend: '趋势',
  Volume: '量价',
  'Data freshness': '数据新鲜度',
  'Profile completeness': '资料完整度',
  warning: '警示',
  neutral: '中性',
  positive: '正面',
  available: '可用',
  degraded: '降级',
  unavailable: '不可用',
  'Local news center': '本地资讯中心',
  'Market-moving news lane': '影响行情的资讯通道',
  'Announcements lane': '公告通道',
  'SEC filings lane': 'SEC 文件通道',
  'Financial snapshot lane': '财务快照通道',
  'Sector and peer lane': '板块与同业通道',
  'Data quality lane': '数据质量通道',
  'Premium news': '高级资讯',
  'BYOK or local model': 'BYOK 或本地模型',
  'Move explanation': '波动解释',
  'Peer context': '同业背景',
  'Key risks': '关键风险',
  'US equity quick view': '美股快速视图',
  'A-share quick view': 'A股快速视图',
  'Price versus MA20': '价格相对 MA20',
  'Volume confirmation': '量能确认',
  'Nasdaq and sector ETF context': '纳指与行业 ETF 背景',
  'CSI 300 and SSE Composite context': '沪深300与上证指数背景',
  'Announcements require deep mode or configured sources': '公告需要深度模式或已配置的数据源',
  'Broad market': '大盘',
  'Index lens': '指数参照',
  'Sector lens': '行业参照',
  'CSI 300': '沪深300',
  'SSE Composite': '上证指数',
  'Profile context': '资料背景',
  'A-share broad-market reference.': 'A股大盘参照。',
  'A-share market sentiment reference.': 'A股市场情绪参照。',
  Technology: '科技',
  'Consumer Electronics': '消费电子',
  'Technology / Consumer Electronics': '科技 / 消费电子',
  'price above trend volume soft': '价格位于趋势上方但量能偏弱',
  'Constructive quick signal': '快速信号偏积极',
  'Mixed quick signal': '快速信号混合',
  'Trend confirmation': '趋势确认',
  'Trend repair': '趋势修复',
  'Risk boundary': '风险边界',
  'No AI': '未用 AI',
  'No AI used': '未用 AI',
  'Information analysis only': '仅作信息分析',
  'not investment advice': '不构成投资建议',
  info: '信息',
  news: '资讯',
  announcements: '公告',
  financials: '财务',
  sector: '板块',
  data_quality: '数据质量',
  'K-line forecast lab': 'K线预测实验室',
  'Kronos-ready': 'Kronos 已就绪',
  Horizon: '周期',
  Confidence: '置信度',
  Direction: '方向',
  Support: '支撑',
  Resistance: '压力',
  Source: '来源',
  'Downside-risk preview': '下行风险预览',
  'Upside-biased preview': '上行倾向预览',
  'Breakout confirmation': '突破确认',
  'Pullback risk': '回落风险',
  downside_risk: '下行风险',
  upside_bias: '上行倾向',
  model_ready: '模型已就绪',
  model_unavailable: '模型不可用',
  model_disabled: '模型未启用',
  model_error: '模型错误',
  premium_required: '需要高级权限',
  'Real Kronos model': '真实 Kronos 模型',
  'Local rules fallback': '本地规则兜底',
  ready: '已就绪',
  missing: '缺失',
  Model: '模型',
  Forecast: '预测',
  'Backtest records': '回测记录',
};

const SOURCE_ZH: Record<string, string> = {
  no_ai_rules: '免费规则',
  no_ai_retention_rules: '免费留存规则',
  no_ai_news_center_rules: '免费资讯规则',
  no_ai_quick_snapshot: '免费快照',
  no_ai_route_rules: '免费市场通道规则',
  local_kline_rules_kronos_ready: '本地K线规则',
  local_kline_rules_kronos_unavailable: '本地K线规则兜底',
  local_kline_rules_kronos_error: '本地K线错误兜底',
  kronos_model_local: '本地Kronos模型',
  a_share_realtime: 'A股实时行情',
  a_share_history: 'A股历史行情',
  us_realtime: '美股实时行情',
  yahoo_chart: 'Yahoo行情',
  yfinance: 'Yahoo历史行情',
  us_history: '美股历史行情',
  unit_quote: '行情源',
  unit_history: '历史行情',
  yfinance_profile: '公司资料',
  unit_profile: '公司资料',
};

const GENERATED_TERM_ZH: Record<string, string> = {
  'Technology / Consumer Electronics': '科技 / 消费电子',
  'Consumer Electronics': '消费电子',
  Technology: '科技',
  'price above trend volume soft': '价格位于趋势上方但量能偏弱',
  yfinance_profile: '公司资料',
};

const localizeGeneratedTerms = (value: unknown, language: string): string => {
  const text = String(value ?? '');
  if (language === 'en' || !text) return text;
  return Object.entries(GENERATED_TERM_ZH)
    .sort((a, b) => b[0].length - a[0].length)
    .reduce((result, [source, target]) => result.replaceAll(source, target), text);
};

const localizeGeneratedStatus = (value: unknown, language: string): string => {
  const text = String(value ?? '');
  if (language === 'en') return text || '-';
  return GENERATED_TEXT_ZH[text] || text || '-';
};

const localizeGeneratedSource = (value: unknown, language: string): string => {
  const text = String(value ?? '');
  if (language === 'en') return text || '-';
  return SOURCE_ZH[text] || GENERATED_TEXT_ZH[text] || text || '-';
};

const localizeGeneratedHorizon = (value: unknown, language: string): string => {
  const text = String(value ?? '');
  if (language === 'en') return text || '-';
  const match = text.match(/^next_(\d+)_bars$/);
  return match ? `未来 ${match[1]} 根K线` : text || '-';
};

const localizeGeneratedText = (value: unknown, language: string): string => {
  const text = String(value ?? '');
  if (language === 'en' || !text) return text;
  if (GENERATED_TEXT_ZH[text]) return GENERATED_TEXT_ZH[text];
  if (SOURCE_ZH[text]) return SOURCE_ZH[text];

  let match = text.match(/^(.+?) signal is ([0-9.]+)\/100 from trend, volume, data freshness, and profile completeness\. No AI or public search was used\.$/);
  if (match) return `${match[1]} 信号评分为 ${match[2]}/100，来自趋势、量价、数据新鲜度和资料完整度；未使用 AI 或公共搜索。`;
  match = text.match(/^(.+?) signal is ([0-9.]+)\/100 from trend, volume, data freshness, and profile completeness\.$/);
  if (match) return `${match[1]} 信号评分为 ${match[2]}/100，来自趋势、量价、数据新鲜度和资料完整度。`;
  match = text.match(/^Price ([^ ]+) is above MA5 ([^ ]+) and MA20 (.+?)\.$/);
  if (match) return `价格 ${match[1]} 高于 MA5 ${match[2]} 和 MA20 ${match[3]}。`;
  match = text.match(/^Price holds above MA20 ([^,]+), but short-term confirmation is mixed\.$/);
  if (match) return `价格守在 MA20 ${match[1]} 上方，但短期确认仍然混合。`;
  match = text.match(/^Price is above MA5 ([^ ]+) but below MA20 (.+?)\.$/);
  if (match) return `价格高于 MA5 ${match[1]}，但低于 MA20 ${match[2]}。`;
  match = text.match(/^Price and volume confirm each other in the quick rules\. Volume is (.+?) versus MA5\.$/);
  if (match) return `价格和成交量在快速规则中相互确认。成交量相对 MA5 为 ${match[1]}。`;
  match = text.match(/^Price and volume confirm each other in the quick rules\.$/);
  if (match) return '价格和成交量在快速规则中相互确认。';
  match = text.match(/^Price is above trend, while volume confirmation is still soft\. Volume is (.+?) versus MA5\.$/);
  if (match) return `价格位于趋势上方，但量能确认仍偏弱。成交量相对 MA5 为 ${match[1]}。`;
  match = text.match(/^Price is above trend, while volume confirmation is still soft\.$/);
  if (match) return '价格位于趋势上方，但量能确认仍偏弱。';
  match = text.match(/^Volume expanded while price remains below trend, so confirmation is mixed\. Volume is (.+?) versus MA5\.$/);
  if (match) return `价格仍在趋势下方但成交量放大，确认信号仍然混合。成交量相对 MA5 为 ${match[1]}。`;
  match = text.match(/^Volume expanded while price remains below trend, so confirmation is mixed\.$/);
  if (match) return '价格仍在趋势下方但成交量放大，确认信号仍然混合。';
  match = text.match(/^Volume-price score is limited because recent volume history is incomplete\.$/);
  if (match) return '近期成交量历史不完整，量价评分受限。';
  match = text.match(/^Quote data is fresh for this quick snapshot\.$/);
  if (match) return '本次快速快照使用的是新鲜行情数据。';
  match = text.match(/^Quote data came from cache; refresh before comparing intraday moves\.$/);
  if (match) return '行情数据来自缓存；对比日内波动前请先刷新。';
  match = text.match(/^Latest quote is unavailable; signal confidence is limited\.$/);
  if (match) return '最新行情暂不可用，信号置信度受限。';
  match = text.match(/^Crypto assets do not use stock fundamentals; quick context uses market lane and quote data\.$/);
  if (match) return '加密资产不使用股票基本面；快速背景使用市场通道和行情数据。';
  match = text.match(/^Basic company name is available, but valuation and sector fields are limited\.$/);
  if (match) return '已有基础公司名称，但估值和板块字段有限。';
  match = text.match(/^Company profile is unavailable in quick mode; deep mode can add fuller context\.$/);
  if (match) return '快速模式下公司资料暂不可用；深度模式可补充更完整背景。';
  match = text.match(/^(.+?) quick read: ([^,]+), (below|above|低于|高于) MA20 (.+?)\.?$/);
  if (match) return `${match[1]} 快速解读：${match[2]}，${match[3] === 'below' || match[3] === '低于' ? '低于' : '高于'} MA20 ${match[4]}。`;
  match = text.match(/^support ([^;]+); resistance (.+)$/);
  if (match) return `支撑 ${match[1]}；压力 ${match[2]}`;
  match = text.match(/^Price is below MA20 ([^;]+); trend repair still needs confirmation\.$/);
  if (match) return `价格低于 MA20 ${match[1]}，趋势修复仍需确认。`;
  match = text.match(/^Price closes above resistance ([^ ]+) with expanding volume\.$/);
  if (match) return `价格放量收在压力位 ${match[1]} 上方。`;
  match = text.match(/^Hold above MA20 ([^ ]+) and keep volume change near ([^.]+)\.$/);
  if (match) return `守住 MA20 ${match[1]}，并观察量能变化是否维持在 ${match[2]} 附近。`;
  match = text.match(/^Local rules read support near ([^ ]+) and resistance near (.+?)\. This is not Kronos inference\.$/);
  if (match) return `本地规则读取到支撑约 ${match[1]}、压力约 ${match[2]}。这不是 Kronos 模型推理。`;
  match = text.match(/^Market cap ([^;]+); PE ([^;]+); PB ([^;]+); dividend yield ([^;]+); revenue ([^;]+); net profit (.+?)\.?$/);
  if (match) return `总市值 ${match[1]}；市盈率 ${match[2]}；市净率 ${match[3]}；股息率 ${match[4]}；营收 ${match[5]}；净利润 ${match[6]}。`;
  match = text.match(/^Market cap ([^;]+); PE ([^;]+); PB (.+?)\.?$/);
  if (match) return `总市值 ${match[1]}；市盈率 ${match[2]}；市净率 ${match[3]}。`;
  match = text.match(/^Market cap ([^;]+); PE ([^;]+); dividend yield (.+?)\.?$/);
  if (match) return `总市值 ${match[1]}；市盈率 ${match[2]}；股息率 ${match[3]}。`;
  match = text.match(/^Refresh once before market action and confirm whether price stays (below|above|低于|高于) MA20 (.+?)\.?$/);
  if (match) return `先刷新一次行情，并确认价格是否仍然${match[1] === 'below' || match[1] === '低于' ? '低于' : '高于'} MA20 ${match[2]}。`;
  match = text.match(/^Price is ([^ ]+) and holds (below|above) MA20 with positive short-term confirmation\.$/);
  if (match) return `价格为 ${match[1]}，并保持${match[2] === 'below' ? '低于' : '高于'} MA20，短期确认偏积极。`;
  match = text.match(/^Hold above MA20 ([^ ]+) and keep volume change near (.+?)\.?$/);
  if (match) return `守住 MA20 ${match[1]}，并观察量能变化是否维持在 ${match[2]} 附近。`;
  match = text.match(/^Compare (.+?) against (.+?) and (.+?) before reading it in isolation\.$/);
  if (match) return `解读 ${match[1]} 前，先对比 ${match[2]} 和 ${match[3]}。`;
  match = text.match(/^(.+?) is (below|above) MA20 with positive change\.$/);
  if (match) return `${match[1]} 当前${match[2] === 'below' ? '低于' : '高于'} MA20，且涨跌表现为正。`;
  match = text.match(/^Check whether (.+?) confirms faster or weaker than (.+?) on the next refresh\.$/);
  if (match) return `下次刷新时，检查 ${match[1]} 相对 ${match[2]} 是更强确认还是转弱。`;
  match = text.match(/^Watch whether price can hold (below|above) MA20\.$/);
  if (match) return `观察价格能否守住${match[1] === 'below' ? '低于' : '高于'} MA20 的位置。`;
  match = text.match(/^Compare (.+?) against (.+?) before reading it in isolation\.$/);
  if (match) return `解读 ${match[1]} 前，先对比 ${match[2]}。`;
  match = text.match(/^Context is (.+?)\. Current volume-price signal is (.+?)\. Compare against route-based peers before reading this symbol in isolation\.?$/);
  if (match) return `当前背景为 ${match[1] === 'a share' ? 'A股' : localizeGeneratedTerms(match[1], language)}；量价信号为 ${volumePriceSignalLabel(match[2], language)}。解读该标的前，先与市场通道给出的同类参照对比。`;
  match = text.match(/^Context is (.+?); current volume-price signal is (.+?)\. Compare against route-based peers before reading this symbol in isolation\.?$/);
  if (match) return `当前背景为 ${match[1] === 'a share' ? 'A股' : localizeGeneratedTerms(match[1], language)}；量价信号为 ${volumePriceSignalLabel(match[2], language)}。解读该标的前，先与市场通道给出的同类参照对比。`;
  match = text.match(/^Context is (.+?)\. Current volume-price signal is ([^.]+)\.$/);
  if (match) return `当前背景为 ${match[1] === 'a share' ? 'A股' : localizeGeneratedTerms(match[1], language)}；量价信号为 ${volumePriceSignalLabel(match[2], language)}。`;
  match = text.match(/^Context is (.+?); current volume-price signal is ([^.]+)\.$/);
  if (match) return `当前背景为 ${match[1] === 'a share' ? 'A股' : localizeGeneratedTerms(match[1], language)}；量价信号为 ${volumePriceSignalLabel(match[2], language)}。`;
  match = text.match(/^Today's quick read: price changed (.+?), stays (.+?), and volume is (.+?) versus MA5\.$/);
  if (match) return `今日快速解读：价格变化 ${match[1]}，当前 ${match[2].replace(/^below MA20/, '低于 MA20').replace(/^above MA20/, '高于 MA20')}，成交量相对 MA5 为 ${match[3]}。`;
  match = text.match(/^Today's quick read: price changed (.+?), holds above MA20 (.+?), and volume is (.+?) versus MA5\.$/);
  if (match) return `今日快速解读：价格变化 ${match[1]}，当前高于 MA20 ${match[2]}，成交量相对 MA5 为 ${match[3]}。`;
  match = text.match(/^Today's quick read: price changed (.+?), stays (.+?), and volume is (.+?)\.$/);
  if (match) return `今日快速解读：价格变化 ${match[1]}，当前 ${match[2].replace(/^below MA20/, '低于 MA20').replace(/^above MA20/, '高于 MA20')}，成交量 ${match[3]}。`;
  match = text.match(/^Today's quick read: price changed (.+?), holds above MA20 (.+?), and volume is (.+?)\.$/);
  if (match) return `今日快速解读：价格变化 ${match[1]}，当前高于 MA20 ${match[2]}，成交量 ${match[3]}。`;
  match = text.match(/^Last price (.+?)$/);
  if (match) return `最新价 ${match[1]}`;
  match = text.match(/^stays (.+?)$/);
  if (match) return `当前${match[1].replace(/^below MA20/, '低于 MA20').replace(/^above MA20/, '高于 MA20')}`;
  match = text.match(/^holds above MA20 (.+?)$/);
  if (match) return `当前高于 MA20 ${match[1]}`;
  match = text.match(/^volume is (.+?) versus MA5$/);
  if (match) return `成交量相对 MA5 为 ${match[1]}`;
  match = text.match(/^Read this move against (.+?); quick profile context is (.+?)\.$/);
  if (match) return `结合 ${match[1]} 阅读本次波动；快速资料背景为 ${match[2] === 'a share' ? 'A股' : localizeGeneratedTerms(match[2], language)}。`;
  match = text.match(/^Data warning: Quote is stale; quick view uses cached quote and latest available history\.$/);
  if (match) return '数据警示：行情已过期；快速视图使用缓存行情和最新可用历史。';
  match = text.match(/^Lane (.+?)$/);
  if (match) return `通道 ${marketLaneLabel(match[1], language)}`;
  match = text.match(/^(.+?) is (.+?) with (.+?); volume signal is (.+?)\.$/);
  if (match) return `${match[1]} 当前${match[2].replace(/^below MA20/, '低于 MA20').replace(/^above MA20/, '高于 MA20')}，涨跌幅 ${match[3]}；量价信号为 ${volumePriceSignalLabel(match[4], language)}。`;
  match = text.match(/^Watch whether price can reclaim MA20 (.+?) before treating the structure as repaired\.$/);
  if (match) return `观察价格能否重新站回 MA20 ${match[1]}，再判断结构是否修复。`;
  match = text.match(/^Company profile is available; compare valuation fields before relying on price signals alone\.$/);
  if (match) return '公司资料可用；不要只依赖价格信号，还要对比估值字段。';
  match = text.match(/^(.+?) information lanes for (.+?): news, announcements, financials, sector context, and data quality\. No AI or public search was used\.$/);
  if (match) return `${match[1]} 的 ${localizeGeneratedTerms(match[2], language)} 信息通道：资讯、公告、财务、板块背景和数据质量。未使用 AI 或公共搜索。`;
  match = text.match(/^SEC filings, earnings call notes, and source links are reserved for deep mode or configured feeds\. Free mode avoids public search and AI cost\.$/);
  if (match) return 'SEC 文件、业绩电话会纪要和来源链接保留给深度模式或已配置资讯源；免费模式避免公共搜索和 AI 成本。';

  return localizeGeneratedTerms(text
    .replace(/^Price is above MA20 and short-term trend remains constructive\.$/, '价格位于 MA20 上方，短期趋势结构仍偏积极。')
    .replace(/^Volume-price behavior is neutral in the quick rules\. Volume is ([^ ]+) versus MA5\.$/, '量价行为在快速规则中为中性；成交量相对 MA5 为 $1。')
    .replace(/^Volume is above recent average but still needs follow-through\.$/, '成交量高于近期均量，但仍需要后续确认。')
    .replace(/^Volume is ([^ ]+) versus MA5; momentum confirmation is weaker\.$/, '成交量相对 MA5 为 $1，动能确认偏弱。')
    .replace(/^Quote data is stale; treat the quick signal as provisional\. Quote is stale; quick view uses cached quote and latest available history\.$/, '行情数据偏旧；快速信号仅作临时参考。当前使用缓存行情和最新可用历史数据。')
    .replace(/^Quote and history are fresh\.$/, '行情和历史数据均为最新。')
    .replace(/^Company profile has usable valuation or financial fields\.$/, '公司资料包含可用的估值或财务字段。')
    .replace(/^Company sector, industry, and valuation fields are available\.$/, '公司板块、行业和估值字段可用。')
    .replace(/^This free snapshot turns quote, moving averages, volume and a share context into a first-pass checklist without spending AI quota\.$/, '这个免费快照把行情、均线、量价和A股背景整理成初筛清单，不消耗 AI 额度。')
    .replace(/^This free snapshot turns quote, moving averages, volume and (.+?) context into a first-pass checklist without spending AI quota\.$/, '这个免费快照把行情、均线、量价和 $1 背景整理成初筛清单，不消耗 AI 额度。')
    .replace(/^Resolve data warning first: Quote is stale; quick view uses cached quote and latest available history\.$/, '先处理数据警示：当前使用缓存行情和最新可用历史数据。')
    .replace(/^Refresh once$/, '先刷新一次行情。')
    .replace(/^Refresh once before market action and confirm whether price stays (below|above) MA20\.$/, (_, direction: string) => `先刷新一次行情，并确认价格是否仍然${direction === 'below' ? '低于' : '高于'} MA20。`)
    .replace(/^Refresh once before market action and confirm whether price stays (below|above) MA20 ([^.]+)\.$/, '先刷新一次行情，并确认价格是否仍然$1 MA20 $2。')
    .replace('below MA20', '低于 MA20')
    .replace('above MA20', '高于 MA20')
    .replace(/^Compare this move with (.+?) instead of reading it alone\.$/, '把这次波动与 $1 对比，不要孤立解读。')
    .replace(/^Compare this move with (.+?) and (.+?) before reading (.+?) in isolation\.$/, '解读 $3 前，先把这次波动与 $1 和 $2 对比。')
    .replace(/^No-AI quick view does not include realtime news, filings, or external search\.$/, '未用 AI 快速视图不包含实时新闻、公告文件或外部搜索。')
    .replace(/^US equity lane uses quote, history, profile, Nasdaq and sector references without AI\.$/, '美股通道使用行情、历史、公司资料、纳指和行业参照，不调用 AI。')
    .replace(/^Deep analysis can add news, filings, sector comparison, and AI report\.$/, '深度分析可增加新闻、公告文件、行业对比和 AI 报告。')
    .replace(/^Deep analysis can add announcements, fundamentals, sector flow, and longer AI report\.$/, '深度分析可增加公告、基本面、板块资金流和更完整的 AI 报告。')
    .replace(/^Volume expansion would improve confirmation quality\.$/, '放量会提高确认质量。')
    .replace(/^Keep the analysis informational and not investment advice\.$/, '保持信息分析边界，不构成投资建议。')
    .replace(/^Use deep analysis only when you need news, filings, fundamentals, or a longer AI-written report\.$/, '只有需要新闻、公告、基本面或更长 AI 报告时，再使用深度分析。')
    .replace(/^Use deep analysis only when you need filings or a longer AI-written report\.$/, '只有需要公告文件或更长 AI 报告时，再使用深度分析。')
    .replace(/^Login to save history, build a watchlist, keep quota state, and unlock deeper analysis when needed\.$/, '登录后可保存历史、建立自选股、保留额度状态，并在需要时解锁更深分析。')
    .replace(/^Information analysis only; not investment advice\.$/, '仅作信息分析，不构成投资建议。')
    .replace(/^Experimental model preview; information analysis only; not investment advice\.$/, '实验性模型预览；仅作信息分析，不构成投资建议。')
    .replace(/^(.+?) information lanes for a share: news, announcements, financials, sector context, and data quality\. No AI or public search was used\.$/, '$1 的A股信息通道：资讯、公告、财务、板块背景和数据质量。未使用 AI 或公共搜索。')
    .replace(/^(.+?) information lanes for (.+?): news, announcements, financials, sector context, and data quality\. No AI or public search was used\.$/, '$1 的 $2 信息通道：资讯、公告、财务、板块背景和数据质量。未使用 AI 或公共搜索。')
    .replace(/^Realtime public news\/search is off in free local mode, so this lane is a checklist placeholder\.$/, '免费本地模式未开启实时公共新闻/搜索，此通道作为检查清单占位。')
    .replace(/^(.+?) is at (.+?) with (.+?)\. Realtime public news\/search is off in free local mode, so this lane is a checklist placeholder\.$/, '$1 当前价格 $2，涨跌幅 $3。免费本地模式未开启实时公共新闻/搜索，此通道作为检查清单占位。')
    .replace(/^A-share announcements and exchange filings are reserved for configured deep sources\. Free mode keeps the lane visible so users know what deeper analysis will add\.$/, 'A股公告和交易所文件保留给已配置的深度数据源；免费模式保留此通道，让用户知道深度分析会补充什么。')
    .replace(/^Use deep analysis or configured news feeds for realtime links\.$/, '如需实时链接，请使用深度分析或配置资讯源。')
    .replace(/^SEC filings, earnings call notes, and source links are reserved for deep mode or configured feeds\.$/, 'SEC 文件、业绩会纪要和来源链接保留给深度模式或已配置资讯源。')
    .replace(/^Upgrade or configure a filings source when source links are required\.$/, '需要来源链接时，请升级或配置公告/文件来源。')
    .replace(/^Compare valuation and fundamentals before relying on price action alone\.$/, '不要只看价格波动，还要对比估值和基本面。')
    .replace(/^Context is (.+?)\. Current volume-price signal is (.+?)\.$/, (_, context: string, signal: string) => `当前背景为 ${context}；量价信号为 ${volumePriceSignalLabel(signal, language)}。`)
    .replace(/^Context is (.+?)\. Current volume-price signal is (.+?)\. Compare against route-based peers before reading this symbol in isolation\.?$/, (_, context: string, signal: string) => `当前背景为 ${context}；量价信号为 ${volumePriceSignalLabel(signal, language)}。解读该标的前，先与市场通道给出的同类参照对比。`)
    .replace(/^Open peer comparison or deep sector view for richer cross-asset context\.$/, '可打开同业对比或深度板块视图，获得更完整的跨资产背景。')
    .replace(/^No realtime news source is enabled in free no-AI mode\.$/, '免费未用 AI 模式未启用实时新闻源。')
    .replace(/^No realtime news source is enabled in free no-AI mode for (.+?)\. No AI or public search was used\. Current market data is degraded\.$/, '免费未用 AI 模式暂未启用 $1 实时新闻源；未使用 AI 或公共搜索，当前行情数据存在降级。')
    .replace(/^No filing or announcement source is enabled in free no-AI mode\.$/, '免费未用 AI 模式未启用公告或文件来源。')
    .replace(/^No filing or announcement source is enabled in free no-AI mode for (.+?)\. Deep analysis can add filings, announcements, and source links when configured\.$/, '免费未用 AI 模式暂未启用 $1 公告或文件来源；配置后深度分析可补充公告、文件和来源链接。')
    .replace(/^Quote is stale; quick view uses cached quote and latest available history\.$/, '行情已过期；快速视图使用缓存行情和最新可用历史。')
    .replace(/^Refresh market data before treating the quick snapshot as current\.$/, '先刷新行情，再把快速快照当作当前数据解读。')
    .replace(/^Premium can add realtime news, filings, source links, sector comparison, and AI summaries\.$/, '高级版可增加实时新闻、公告、来源链接、板块对比和 AI 摘要。')
    .replace(/^Kronos adapter ready; local rules preview only; Kronos model not installed or invoked\.$/, 'Kronos 适配器已就绪；当前是本地规则预览，尚未运行 Kronos 模型。')
    .replace(/^Kronos adapter ready; local rules preview only\.$/, 'Kronos 适配器已就绪；当前是本地规则预览。')
    .replace(/^Kronos adapter ready; model not invoked because dependencies are missing: (.+)\.$/, 'Kronos 适配器已就绪；因依赖缺失尚未运行模型：$1。')
    .replace(/^Kronos model unavailable; missing dependencies: (.+)\.$/, 'Kronos 模型不可用；缺失依赖：$1。')
    .replace(/^Premium can run a configured Kronos or local-model forecast lane after model\/data approval\.$/, '高级版可在模型和数据确认后运行 Kronos 或本地模型预测通道。')
    .replace(/^A-share lane focuses on quote, moving averages, volume-price behavior, and broad-market context without AI\.$/, 'A股通道聚焦行情、均线、量价行为和大盘背景，不调用 AI。')
    .replace(/^Today's quick read: price changed (.+?), stays (.+?), and volume is (.+?)\.$/, '今日快速解读：价格变化 $1，当前 $2，成交量 $3。')
    .replace(/^Lane (.+?) No AI used Information analysis only$/, (_, lane: string) => `通道 ${marketLaneLabel(lane, language)}；未用 AI；仅作信息分析`)
    .replace(/^Run the local adapter probe\. If the real Kronos runtime is unavailable, this stays on the local rules fallback\.$/, '运行本地 Kronos 模型检查；如果模型运行环境不可用，则保持本地规则兜底。')
    .replace(/^Treat this as a checklist for the next refresh, not a trade instruction\.$/, '把它作为下一次刷新时的检查清单，不是交易指令。')
    .replace(/^Price loses support ([^ ]+) or data freshness degrades\.$/, '价格跌破支撑 $1，或数据新鲜度继续下降。')
    .replace(/^Recheck source freshness and broad-market references before interpreting weakness\.$/, '解读走弱前，先复核数据新鲜度和大盘参照。')
    .replace(/^Forecast lab output is experimental information analysis only; not investment advice\.$/, '预测实验室输出仅作实验性信息分析，不构成投资建议。'), language);
};

const historyCenterMarketLabel = (value: HistoryCenterMarketFilter, language: string): string => {
  if (language === 'en') {
    return ({ all: 'All markets', cn: 'A-share', us: 'US', hk: 'HK', crypto: 'Crypto' } as Record<HistoryCenterMarketFilter, string>)[value];
  }
  return ({ all: '全部市场', cn: 'A股', us: '美股', hk: '港股', crypto: '加密货币' } as Record<HistoryCenterMarketFilter, string>)[value];
};

const historyCenterReportLabel = (value: HistoryCenterReportFilter, language: string): string => {
  const en: Record<HistoryCenterReportFilter, string> = { all: 'All stock reports', stock: 'Stock reports', simple: 'Simple', detailed: 'Detailed', full: 'Full', brief: 'Brief', market_review: 'Market review' };
  const zh: Record<HistoryCenterReportFilter, string> = { all: '全部个股报告', stock: '个股报告', simple: '简版', detailed: '详细', full: '完整版', brief: '简报', market_review: '大盘复盘' };
  return (language === 'en' ? en : zh)[value];
};

const historyCenterRangeLabel = (value: HistoryCenterRangeFilter, language: string): string => {
  const en: Record<HistoryCenterRangeFilter, string> = { all: 'Any time', '7d': 'Last 7d', '30d': 'Last 30d', '90d': 'Last 90d' };
  const zh: Record<HistoryCenterRangeFilter, string> = { all: '任意时间', '7d': '近7天', '30d': '近30天', '90d': '近90天' };
  return (language === 'en' ? en : zh)[value];
};

const historyCenterSortLabel = (value: HistoryCenterSort, language: string): string => {
  const en: Record<HistoryCenterSort, string> = { newest: 'Newest first', oldest: 'Oldest first' };
  const zh: Record<HistoryCenterSort, string> = { newest: '最新优先', oldest: '最早优先' };
  return (language === 'en' ? en : zh)[value];
};

const historyCenterRefreshLabel = (value: HistoryCenterRefreshFilter, language: string): string => {
  const en: Record<HistoryCenterRefreshFilter, string> = { all: 'All refresh states', refreshed: 'Refreshed current quote', not_refreshed: 'Not refreshed' };
  const zh: Record<HistoryCenterRefreshFilter, string> = { all: '全部刷新状态', refreshed: '已刷新当前行情', not_refreshed: '未刷新' };
  return (language === 'en' ? en : zh)[value];
};

const historyCenterStateLabel = (value: HistoryCenterStateFilter, language: string): string => {
  const en: Record<HistoryCenterStateFilter, string> = { all: 'All report states', favorite: 'Favorite', important: 'Important', active: 'Active', archived: 'Archived', has_note: 'Has note', unread: 'Unread', read: 'Read' };
  const zh: Record<HistoryCenterStateFilter, string> = { all: '全部报告状态', favorite: '收藏', important: '重要', active: '有效', archived: '已归档', has_note: '有备注', unread: '未读', read: '已读' };
  return (language === 'en' ? en : zh)[value];
};

const formatQuotaLeft = (quota?: Pick<PlatformQuota, 'weeklyLimit' | 'remaining' | 'used'> | null, language = 'en'): string => {
  const isEnglish = language === 'en';
  if (!quota) {
    return isEnglish ? 'unavailable' : '暂不可用';
  }
  if (quota.weeklyLimit === null) {
    return isEnglish ? `${quota.used}/unlimited used` : `已用 ${quota.used}/不限`;
  }
  return isEnglish ? `${quota.remaining ?? 0}/${quota.weeklyLimit} left` : `剩余 ${quota.remaining ?? 0}/${quota.weeklyLimit}`;
};

const apiKeyModeLabel = (mode?: string | null, language = 'en'): string => {
  const isEnglish = language === 'en';
  if (mode === 'user') return 'BYOK';
  if (mode === 'local') return isEnglish ? 'local model' : '本地模型';
  return isEnglish ? 'platform API' : '平台 API';
};

const marketLaneLabel = (lane?: string | null, language = 'en'): string => {
  const isEnglish = language === 'en';
  if (lane === 'a_share_market_data') return isEnglish ? 'A-share market data' : 'A股行情数据';
  if (lane === 'us_market_data') return isEnglish ? 'US market data' : '美股行情数据';
  if (lane === 'hk_market_data') return isEnglish ? 'HK market data' : '港股行情数据';
  if (lane === 'crypto_market_data') return isEnglish ? 'Crypto market data' : '加密货币行情数据';
  return lane || (isEnglish ? 'market data' : '行情数据');
};

const localizeRuntimeLabel = (value: unknown, language: string): string => {
  const text = String(value ?? '');
  if (language === 'en' || !text) return text || '-';
  const zh: Record<string, string> = {
    fresh: '新鲜',
    stale: '过期',
    stale_cache: '过期缓存',
    stale_quote: '行情过期',
    delayed: '延迟',
    missing: '缺失',
    ok: '正常',
    warning: '警告',
    degraded: '降级',
    available: '可用',
    unavailable: '不可用',
    hit: '命中',
    miss: '未命中',
    cache: '缓存',
    live: '实时',
    memory: '内存',
    disk: '磁盘',
    local_json: '本地缓存',
    local_disk: '本地磁盘',
    private: '私有',
    separate: '独立',
    unknown_lane: '未知通道',
    no_ai_low_cost: '低成本未用 AI',
    'AI used': '已使用 AI',
    'No AI': '未用 AI',
    'No AI used': '未用 AI',
    'Platform API': '平台 API',
    'Selected Platform API': '已选择平台 API',
    'Selected local model': '已选择本地模型',
    'Selected BYOK': '已选择 BYOK',
    'BYOK ready': 'BYOK 已就绪',
    'BYOK not set': 'BYOK 未设置',
  };
  if (zh[text]) return zh[text];
  const reports = text.match(/^(\d+) reports$/);
  if (reports) return `${reports[1]} 份报告`;
  const symbols = text.match(/^(\d+) symbols$/);
  if (symbols) return `${symbols[1]} 只标的`;
  const cache = text.match(/^Cache (.+)$/);
  if (cache) return `缓存 ${localizeRuntimeLabel(cache[1], language)}`;
  return localizeGeneratedSource(text, language);
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
const GUEST_QUERY_EXAMPLES = [
  { symbol: 'AAPL', label: 'Apple', market: 'US' },
  { symbol: '600519', label: '贵州茅台', market: 'A-share' },
  { symbol: '00700.HK', label: '腾讯控股', market: 'HK' },
  { symbol: 'BTC-USD', label: 'Bitcoin', market: 'Crypto' },
] as const;

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
  const [autocompleteCloseSignal, setAutocompleteCloseSignal] = useState(0);
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
  const [kronosForecast, setKronosForecast] = useState<KronosForecastResponse | null>(null);
  const [isRunningKronosForecast, setIsRunningKronosForecast] = useState(false);
  const [kronosForecastError, setKronosForecastError] = useState('');
  const [basicRetentionBusy, setBasicRetentionBusy] = useState(false);
  const [basicRetentionStatus, setBasicRetentionStatus] = useState('');
  const [basicRetentionError, setBasicRetentionError] = useState('');
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
  const basicSnapshotRef = useRef<HTMLDivElement | null>(null);
  const platformAuthPanelRef = useRef<HTMLDivElement | null>(null);
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
    const email = authEmail.trim();
    if (!email) {
      setAuthError(uiLanguage === 'en' ? 'Enter an email first.' : '请先输入邮箱');
      platformAuthPanelRef.current?.querySelector<HTMLInputElement>('[data-testid="platform-auth-email"]')?.focus();
      return;
    }
    if (!authPassword) {
      setAuthError(uiLanguage === 'en' ? 'Enter a password first.' : '请先输入密码');
      platformAuthPanelRef.current?.querySelector<HTMLInputElement>('[data-testid="platform-auth-password"]')?.focus();
      return;
    }
    setAuthBusy(true);
    setAuthError('');
    try {
      const retainedQuery = basicSnapshot?.stockCode || query;
      const payload = authMode === 'register'
        ? await platformApi.register(email, authPassword)
        : await platformApi.login(email, authPassword);
      await loadPlatformAccount(payload);
      setAuthPassword('');
      resetDashboardState();
      if (retainedQuery.trim()) {
        setQuery(retainedQuery.trim());
      }
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
  }, [authEmail, authMode, authPassword, basicSnapshot?.stockCode, loadInitialHistory, loadMarketReviewHistory, loadPlatformAccount, loadStockBar, query, refreshActiveTasks, resetDashboardState, setQuery, uiLanguage]);

  const handlePlatformAuthModeChange = useCallback((mode: 'login' | 'register') => {
    setAuthMode(mode);
    setAuthError('');
    window.setTimeout(() => {
      platformAuthPanelRef.current?.querySelector<HTMLInputElement>('[data-testid="platform-auth-email"]')?.focus();
    }, 0);
  }, []);

  const handlePlatformLogout = useCallback(async () => {
    await platformApi.logout();
    setPlatformSession(null);
    setPlatformAccount(null);
    setPlatformKeys([]);
    setPlatformWatchlist(null);
    setPlatformWatchlistRefresh(null);
    setPlatformWatchlistError('');
    setApiKeyMode('platform');
    setBasicSnapshot(null);
    setBasicRetentionStatus('');
    setBasicRetentionError('');
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
    const target = (basicSnapshot?.stockCode || query).trim();
    if (!target || platformWatchlistBusy) {
      return;
    }
    setPlatformWatchlistBusy(true);
    setPlatformWatchlistError('');
    setBasicRetentionError('');
    try {
      const list = await platformApi.addWatchlistItem(target);
      setPlatformWatchlist(list);
      setPlatformWatchlistRefresh(null);
      setBasicRetentionStatus(uiLanguage === 'en' ? 'Added to watchlist' : '已加入自选');
    } catch (err: unknown) {
      const message = getParsedApiError(err).message || (uiLanguage === 'en' ? 'Watchlist update failed' : '自选更新失败');
      setPlatformWatchlistError(message);
      setBasicRetentionError(message);
    } finally {
      setPlatformWatchlistBusy(false);
    }
  }, [basicSnapshot?.stockCode, platformWatchlistBusy, query, uiLanguage]);

  const handleSaveCurrentBasicSnapshotToHistory = useCallback(async () => {
    if (!basicSnapshot || basicRetentionBusy) {
      return;
    }
    if (!platformSession) {
      setAuthMode('register');
      setBasicRetentionStatus('');
      setBasicRetentionError(uiLanguage === 'en' ? 'Register or login to save this no-AI snapshot.' : '注册或登录后可保存这份未用 AI 快照。');
      return;
    }
    setBasicRetentionBusy(true);
    setBasicRetentionStatus('');
    setBasicRetentionError('');
    try {
      await platformApi.saveSnapshotToHistory(basicSnapshot);
      setBasicRetentionStatus(uiLanguage === 'en' ? 'Saved to history' : '已保存到历史');
      await Promise.all([
        refreshHistory(),
        loadStockBar(),
      ]);
    } catch (err: unknown) {
      setBasicRetentionError(getParsedApiError(err).message || (uiLanguage === 'en' ? 'Snapshot save failed' : '快照保存失败'));
    } finally {
      setBasicRetentionBusy(false);
    }
  }, [basicRetentionBusy, basicSnapshot, loadStockBar, platformSession, refreshHistory, uiLanguage]);

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
      setPlatformWatchlistError(getParsedApiError(err).message || (uiLanguage === 'en' ? 'Watchlist refresh failed' : '自选刷新失败'));
    } finally {
      setPlatformWatchlistBusy(false);
    }
  }, [platformWatchlistBusy, uiLanguage]);

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
  const platformAiQuickQuota = platformAccount?.quotaBuckets.find((bucket) => bucket.quotaBucket === 'ai_quick');
  const byokAiQuickQuota = platformAccount?.quotaBuckets.find((bucket) => bucket.quotaBucket === 'ai_quick_user_key');
  const localAiQuota = platformAccount?.quotaBuckets.find((bucket) => bucket.quotaBucket === 'ai_local');
  const accountQuotaText = platformSession ? formatQuotaLeft(baseQuota, uiLanguage) : localizeRuntimeLabel('unavailable', uiLanguage);
  const basicQuotaText = basicQueryQuota ? formatQuotaLeft(basicQueryQuota, uiLanguage) : (uiLanguage === 'en' ? 'unmetered locally' : '本地不限量');
  const platformAiQuotaText = platformAiQuickQuota ? formatQuotaLeft(platformAiQuickQuota, uiLanguage) : accountQuotaText;
  const byokAiQuotaText = byokAiQuickQuota ? formatQuotaLeft(byokAiQuickQuota, uiLanguage) : (uiLanguage === 'en' ? 'available after saving a user key' : '保存用户 API Key 后可用');
  const localModelQuotaText = localAiQuota ? formatQuotaLeft(localAiQuota, uiLanguage) : (uiLanguage === 'en' ? 'local capacity gate' : '本地算力限制');
  const byokStatusText = primaryApiKey
    ? (uiLanguage === 'en' ? `BYOK ready ${primaryApiKey.maskedKey}` : `BYOK 已就绪 ${primaryApiKey.maskedKey}`)
    : localizeRuntimeLabel('BYOK not set', uiLanguage);
  const recommendedModeText = uiLanguage === 'en'
    ? `Recommended ${apiKeyModeLabel(platformAccount?.recommendedQueryMode, uiLanguage)}`
    : `推荐 ${apiKeyModeLabel(platformAccount?.recommendedQueryMode, uiLanguage)}`;
  const basicSnapshotLane = basicSnapshot?.route?.dataSourceLane || basicSnapshot?.diagnostics?.routeLane || null;
  const basicSnapshotCacheMode = basicSnapshot?.diagnostics?.persistentCache?.mode;
  const autocompleteInputKey = basicSnapshot
    ? `snapshot-${basicSnapshot.stockCode}-${basicSnapshot.quote.updateTime || basicSnapshot.quote.source || 'quote'}`
    : 'search';
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
  const basicProfileDetailItems = useMemo(() => {
    if (!basicSnapshot?.profile) {
      return [];
    }
    const isEnglish = uiLanguage === 'en';
    const profile = basicSnapshot.profile;
    return [
      { label: isEnglish ? 'Sector' : '板块', value: isEnglish ? profile.sector || '-' : localizeGeneratedTerms(profile.sector || '-', uiLanguage) },
      { label: isEnglish ? 'Industry' : '行业', value: isEnglish ? profile.industry || '-' : localizeGeneratedTerms(profile.industry || '-', uiLanguage) },
      { label: isEnglish ? 'Exchange' : '交易所', value: profile.exchange || '-' },
      { label: isEnglish ? 'Currency' : '币种', value: profile.currency || '-' },
      { label: isEnglish ? 'Country / region' : '国家/地区', value: profile.country || '-' },
      { label: isEnglish ? 'Market cap' : '总市值', value: formatBasicCompactNumber(profile.marketCap) },
      { label: isEnglish ? 'PE ratio' : '市盈率', value: formatBasicNumber(profile.peRatio) },
      { label: isEnglish ? 'PB ratio' : '市净率', value: formatBasicNumber(profile.pbRatio) },
      { label: isEnglish ? 'Dividend yield' : '股息率', value: formatBasicPercent(profile.dividendYield) },
      { label: isEnglish ? 'Revenue' : '营收', value: formatBasicCompactNumber(profile.revenue) },
      { label: isEnglish ? 'Net profit' : '净利润', value: formatBasicCompactNumber(profile.netProfit) },
      { label: isEnglish ? 'Revenue growth' : '营收增速', value: formatBasicPercent(profile.revenueGrowth) },
      { label: isEnglish ? 'Earnings growth' : '盈利增速', value: formatBasicPercent(profile.earningsGrowth) },
    ];
  }, [basicSnapshot, uiLanguage]);
  const basicProfileSummaryItems = useMemo(() => {
    if (!basicSnapshot?.profile) {
      return [];
    }
    const isEnglish = uiLanguage === 'en';
    const profile = basicSnapshot.profile;
    return [
      { label: isEnglish ? 'Sector' : '板块', value: isEnglish ? profile.sector || '-' : localizeGeneratedTerms(profile.sector || '-', uiLanguage) },
      { label: isEnglish ? 'Industry' : '行业', value: isEnglish ? profile.industry || '-' : localizeGeneratedTerms(profile.industry || '-', uiLanguage) },
      { label: isEnglish ? 'Market cap' : '总市值', value: formatBasicCompactNumber(profile.marketCap) },
      { label: isEnglish ? 'PE' : '市盈率', value: formatBasicNumber(profile.peRatio) },
    ].filter((item) => item.value !== '-');
  }, [basicSnapshot, uiLanguage]);
  const basicFreeReport = useMemo(() => {
    if (!basicSnapshot) {
      return null;
    }
    const isEnglish = uiLanguage === 'en';
    const indicators = basicSnapshot.indicators || {};
    const currentPrice = toFiniteBasicNumber(basicSnapshot.quote.currentPrice);
    const ma5 = toFiniteBasicNumber(indicators['ma5']);
    const ma10 = toFiniteBasicNumber(indicators['ma10']);
    const ma20 = toFiniteBasicNumber(indicators['ma20']);
    const openPrice = toFiniteBasicNumber(basicSnapshot.quote.open);
    const highPrice = toFiniteBasicNumber(basicSnapshot.quote.high);
    const lowPrice = toFiniteBasicNumber(basicSnapshot.quote.low);
    const prevClose = toFiniteBasicNumber(basicSnapshot.quote.prevClose);
    const changePercent = toFiniteBasicNumber(basicSnapshot.quote.changePercent);
    const change5d = toFiniteBasicNumber(pickBasicIndicator(indicators, 'priceChange5D', 'priceChange5d', 'price_change_5d'));
    const change20d = toFiniteBasicNumber(pickBasicIndicator(indicators, 'priceChange20D', 'priceChange20d', 'price_change_20d'));
    const volumeChange = toFiniteBasicNumber(pickBasicIndicator(indicators, 'volumeChangeVsMa5', 'volume_change_vs_ma5'));
    const aboveMa5 = currentPrice !== null && ma5 !== null && currentPrice >= ma5;
    const aboveMa20 = currentPrice !== null && ma20 !== null && currentPrice >= ma20;
    const trendHeadline = currentPrice === null || ma5 === null || ma20 === null
      ? (isEnglish ? 'Trend context needs more history' : '趋势上下文仍需更多历史数据')
      : aboveMa5 && aboveMa20
        ? (isEnglish ? 'Price above MA5 and MA20' : '价格站上 MA5 与 MA20')
        : !aboveMa5 && !aboveMa20
          ? (isEnglish ? 'Price below MA5 and MA20' : '价格低于 MA5 与 MA20')
          : (isEnglish ? 'Price between short and medium trend' : '价格位于短中期均线之间');
    const momentumHeadline = change5d === null && change20d === null
      ? (isEnglish ? 'Momentum data is limited' : '动能数据有限')
      : `${isEnglish ? '5d' : '5日'} ${formatSignedBasicPercent(change5d)} / ${isEnglish ? '20d' : '20日'} ${formatSignedBasicPercent(change20d)}`;
    const volumeHeadline = volumePriceSignalLabel(
      pickBasicIndicator(indicators, 'volumePriceSignal', 'volume_price_signal'),
      uiLanguage,
    );
    const profile = basicSnapshot.profile;
    const profileHeadline = profile
      ? [profile.sector, profile.industry].filter(Boolean).map((value) => localizeGeneratedTerms(value, uiLanguage)).join(' · ') || (isEnglish ? 'Company profile available' : '公司资料可用')
      : (isEnglish ? 'Company profile not available yet' : '公司资料暂不可用');
    let score = 50;
    if (aboveMa5) score += 10;
    if (aboveMa20) score += 15;
    if (changePercent !== null && changePercent > 0) score += 5;
    if (change5d !== null) score += change5d > 0 ? 8 : -6;
    if (change5d !== null && change5d > 10) score += 4;
    if (change20d !== null) score += change20d > 0 ? 6 : -4;
    if (volumeChange !== null && volumeChange > 20) score += 5;
    if (volumeChange !== null && volumeChange < -20) score -= 3;
    score = Math.max(0, Math.min(100, Math.round(score)));
    const supportCandidates = uniqueBasicLevels([ma5, ma10, ma20, prevClose, lowPrice, openPrice]);
    const pressureCandidates = uniqueBasicLevels([highPrice, openPrice, prevClose, ma5, ma10, ma20]);
    const supportLevels = (
      currentPrice !== null
        ? supportCandidates.filter((level) => level <= currentPrice).sort((left, right) => right - left)
        : supportCandidates.sort((left, right) => right - left)
    ).slice(0, 2);
    const pressureLevels = (
      currentPrice !== null
        ? pressureCandidates.filter((level) => level >= currentPrice).sort((left, right) => left - right)
        : pressureCandidates.sort((left, right) => left - right)
    ).slice(0, 2);
    const conclusion = score >= 75
      ? (isEnglish ? 'Trend is constructive with confirmed momentum.' : '趋势偏强，动能和价格结构占优。')
      : score >= 55
        ? (isEnglish ? 'Structure is neutral; wait for stronger confirmation.' : '结构偏中性，仍需等待量价继续确认。')
        : (isEnglish ? 'Structure is defensive; prioritize risk boundary checks.' : '结构偏防守，先看趋势修复和风险边界。');
    const shortStatus = currentPrice === null || ma5 === null
      ? (isEnglish ? 'Short-term signal incomplete' : '短线信号不完整')
      : aboveMa5
        ? (isEnglish ? 'Short-term above MA5' : '短线站上 MA5')
        : (isEnglish ? 'Short-term below MA5' : '短线低于 MA5');
    const midStatus = currentPrice === null || ma20 === null
      ? (isEnglish ? 'Medium-term signal incomplete' : '中线信号不完整')
      : aboveMa20
        ? (isEnglish ? 'Medium-term above MA20' : '中线在 MA20 上方')
        : (isEnglish ? 'Medium-term below MA20' : '中线低于 MA20');
    const riskNotes = [
      basicSnapshot.quote.freshness !== 'fresh'
        ? (isEnglish ? 'Quote is not fresh; refresh before making comparisons.' : '行情不是 fresh，比较前应先刷新确认。')
        : null,
      basicSnapshot.degradation && basicSnapshot.degradation.status !== 'ok'
        ? basicSnapshot.degradation.message
        : null,
      volumeChange !== null && volumeChange < -20
        ? (isEnglish ? 'Volume is below its short-term average; breakout confidence is limited.' : '量能低于短期均量，突破确认度有限。')
        : null,
      isEnglish ? 'Information analysis only, not investment advice.' : '仅作信息分析，不构成投资建议。',
    ].filter((note): note is string => Boolean(note));
    const trendPoints = basicSnapshot.trend?.points ?? [];
    const fallbackTrendPoints = uniqueBasicLevels([prevClose, ma20, ma10, ma5, currentPrice])
      .map((close) => ({ close }));
    const hasHistoricalTrend = trendPoints.length >= 2;
    const sparkline = buildBasicSparkline(hasHistoricalTrend ? trendPoints : fallbackTrendPoints);
    const trendWindow = basicSnapshot.trend?.window || (hasHistoricalTrend ? trendPoints.length : fallbackTrendPoints.length);
    const trendChange = toFiniteBasicNumber(basicSnapshot.trend?.changePercent)
      ?? sparkline?.changePercent
      ?? change20d
      ?? change5d;
    const backendSignalScore = basicSnapshot.intelligence?.signalScore ?? null;
    const normalizedSignalScore = backendSignalScore
      ? {
          score: clampBasicScore(backendSignalScore.score),
          label: localizeGeneratedText(backendSignalScore.label || (isEnglish ? 'Quick signal score' : '快速信号评分'), uiLanguage),
          summary: localizeGeneratedText(backendSignalScore.summary || '', uiLanguage),
          source: localizeGeneratedSource(backendSignalScore.source || 'no_ai_rules', uiLanguage),
          aiUsed: Boolean(backendSignalScore.aiUsed),
          components: (backendSignalScore.components ?? []).map((component) => ({
            key: component.key || component.label,
            label: localizeGeneratedText(component.label || component.key || '-', uiLanguage),
            score: clampBasicScore(component.score),
            status: localizeGeneratedStatus(component.status || 'neutral', uiLanguage),
            detail: localizeGeneratedText(component.detail || '', uiLanguage),
          })),
        }
      : null;

    return {
      score: normalizedSignalScore?.score ?? score,
      signalScore: normalizedSignalScore,
      miniChart: {
        title: hasHistoricalTrend
          ? (isEnglish ? `${trendWindow}d trend` : `${trendWindow}日趋势`)
          : (isEnglish ? 'Price structure' : '价位结构'),
        changeText: formatSignedBasicTrendPercent(trendChange),
        minText: formatBasicNumber(toFiniteBasicNumber(basicSnapshot.trend?.minClose) ?? sparkline?.minClose ?? null),
        maxText: formatBasicNumber(toFiniteBasicNumber(basicSnapshot.trend?.maxClose) ?? sparkline?.maxClose ?? null),
        source: hasHistoricalTrend ? basicSnapshot.trend?.source || 'history' : 'price levels',
        sparkline,
        isHistorical: hasHistoricalTrend,
      },
      productBrief: {
        conclusion,
        supportLevels: supportLevels.map(formatBasicNumber).join(' / ') || '-',
        pressureLevels: pressureLevels.map(formatBasicNumber).join(' / ') || '-',
        shortStatus,
        midStatus,
        risks: riskNotes,
        upgradeText: isEnglish
          ? 'Unlock news, filings, fundamentals, sector comparison, and a longer AI report.'
          : '可解锁新闻、公告、基本面、行业对比和 AI 长报告。',
      },
      cards: [
        {
          title: isEnglish ? 'Trend setup' : '趋势结构',
          headline: trendHeadline,
          details: [
            `${isEnglish ? 'Last' : '最新价'} ${formatBasicNumber(currentPrice)}`,
            `MA5 ${formatBasicNumber(ma5)}`,
            `MA20 ${formatBasicNumber(ma20)}`,
          ],
        },
        {
          title: isEnglish ? 'Momentum' : '动能节奏',
          headline: momentumHeadline,
          details: [
            `${isEnglish ? 'Day change' : '当日涨跌'} ${formatSignedBasicPercent(changePercent)}`,
            `${isEnglish ? '5d change' : '5日涨跌'} ${formatSignedBasicPercent(change5d)}`,
            `${isEnglish ? '20d change' : '20日涨跌'} ${formatSignedBasicPercent(change20d)}`,
          ],
        },
        {
          title: isEnglish ? 'Volume-price' : '量价配合',
          headline: volumeHeadline,
          details: [
            `${isEnglish ? 'Volume vs MA5' : '量能变化'} ${formatSignedBasicPercent(volumeChange)}`,
            `${isEnglish ? 'Volume' : '成交量'} ${formatBasicCompactNumber(basicSnapshot.quote.volume)}`,
          ],
        },
        {
          title: isEnglish ? 'Business profile' : '基本面轮廓',
          headline: profileHeadline,
          details: [
            `${isEnglish ? 'Market cap' : '总市值'} ${formatBasicCompactNumber(profile?.marketCap)}`,
            `PE ${formatBasicNumber(profile?.peRatio)}`,
            `${isEnglish ? 'Revenue' : '营收'} ${formatBasicCompactNumber(profile?.revenue)}`,
          ],
        },
        {
          title: isEnglish ? 'Free-tier boundary' : '免费版边界',
          headline: isEnglish ? 'No AI quick snapshot' : '未用 AI 快照研判',
          details: [
            basicSnapshot.aiUsed ? localizeRuntimeLabel('AI used', uiLanguage) : t('home.noAi'),
            localizeRuntimeLabel(basicSnapshot.quote.freshness, uiLanguage),
            isEnglish ? 'Information analysis, not investment advice' : '仅作信息分析，不构成投资建议',
          ],
        },
      ],
    };
  }, [basicSnapshot, uiLanguage]);
  const platformWatchlistItems = platformWatchlist?.items ?? [];
  const platformWatchlistPreview = platformWatchlistItems.slice(0, 6);
  const platformWatchlistBoardItems = platformWatchlistRefresh?.items ?? [];
  const platformWatchlistCount = platformWatchlist?.total ?? platformWatchlistItems.length;
  const workspaceHistoryCountText = uiLanguage === 'en'
    ? `${stockHistoryTotal ?? 0} reports`
    : `${stockHistoryTotal ?? 0} 份报告`;
  const workspaceAiModeText = apiKeyMode === 'user'
    ? (uiLanguage === 'en' ? 'Selected BYOK' : '已选择 BYOK')
    : apiKeyMode === 'local'
      ? (uiLanguage === 'en' ? 'Selected local model' : '已选择本地模型')
      : (uiLanguage === 'en' ? 'Selected Platform API' : '已选择平台 API');
  const workspaceByokText = primaryApiKey
    ? (uiLanguage === 'en' ? 'BYOK ready' : 'BYOK 已就绪')
    : localizeRuntimeLabel('BYOK not set', uiLanguage);
  const showGuestQueryEntry = !platformSession
    && !basicSnapshot
    && !marketReviewReport
    && stockBarItems.length === 0
    && historyItems.length === 0
    && stockHistoryItems.length === 0
    && marketReviewHistoryItems.length === 0;
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

    setAutocompleteCloseSignal((current) => current + 1);
    setIsQueryingBasic(true);
    setBasicQueryError(null);
    setBasicRetentionStatus('');
    setBasicRetentionError('');
    setKronosForecastError('');
    if (!forceRefresh) {
      setBasicSnapshot(null);
      setKronosForecast(null);
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

  const handleRunKronosForecast = useCallback(async (requireModel = false) => {
    if (!basicSnapshot?.stockCode || isRunningKronosForecast) {
      return;
    }
    setIsRunningKronosForecast(true);
    setKronosForecastError('');
    try {
      const result = await stocksApi.kronosForecast(basicSnapshot.stockCode, {
        lookback: 120,
        horizon: 5,
        requireModel,
      });
      setKronosForecast(result);
    } catch (err: unknown) {
      setKronosForecastError(getParsedApiError(err).message);
    } finally {
      setIsRunningKronosForecast(false);
    }
  }, [basicSnapshot?.stockCode, isRunningKronosForecast]);

  useEffect(() => {
    if (!basicSnapshot || marketReviewReport) {
      return;
    }
    const target = basicSnapshotRef.current;
    if (typeof target?.scrollIntoView === 'function') {
      target.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  }, [basicSnapshot, marketReviewReport]);

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
      setHistoryExportStatus(uiLanguage === 'en'
        ? `Exported ${bundle.recordCount} local reports`
        : `已导出 ${bundle.recordCount} 份本地报告`);
    } catch (exportError) {
      const parsed = getParsedApiError(exportError);
      setHistoryExportStatus(parsed.message || (uiLanguage === 'en' ? 'History export failed' : '历史导出失败'));
    } finally {
      setIsExportingHistory(false);
    }
  }, [isExportingHistory, selectedIds, uiLanguage]);

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
      const zhAction = ({
        'Marked important': '已标为重要',
        'Marked read': '已标为已读',
        Archived: '已归档',
        Unarchived: '已恢复',
      } as Record<string, string>)[successLabel] || successLabel;
      setHistoryStateStatus(uiLanguage === 'en'
        ? `${successLabel} ${result.updated} local reports`
        : `${zhAction} ${result.updated} 份本地报告`);
      await refreshHistory(true);
      if (historyCenterFilters.reportType === 'market_review') {
        await refreshMarketReviewHistory(false);
      }
    } catch (stateError) {
      const parsed = getParsedApiError(stateError);
      setHistoryStateStatus(parsed.message || (uiLanguage === 'en' ? 'History state update failed' : '历史状态更新失败'));
    } finally {
      setIsUpdatingHistoryState(false);
    }
  }, [
    historyCenterFilters.reportType,
    isUpdatingHistoryState,
    refreshHistory,
    refreshMarketReviewHistory,
    selectedIds,
    uiLanguage,
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
      setHistoryStateStatus(uiLanguage === 'en' ? 'Saved local history state' : '已保存本地历史状态');
      await refreshHistory(true);
      if (selectedReport?.meta.reportType === 'market_review') {
        await refreshMarketReviewHistory(false);
      }
    } catch (stateError) {
      const parsed = getParsedApiError(stateError);
      setHistoryStateStatus(parsed.message || (uiLanguage === 'en' ? 'History state update failed' : '历史状态更新失败'));
    } finally {
      setIsUpdatingHistoryState(false);
    }
  }, [
    isUpdatingHistoryState,
    refreshHistory,
    refreshMarketReviewHistory,
    selectedReport?.meta.id,
    selectedReport?.meta.reportType,
    uiLanguage,
  ]);

  const historyCenterControls = useMemo(() => {
    const selectClass = 'h-8 min-w-0 rounded-lg border border-subtle bg-surface px-2 text-[11px] text-foreground';
    const textClass = 'h-8 min-w-0 rounded-lg border border-subtle bg-surface px-2 text-[11px] text-foreground placeholder:text-muted-text';
    const selectedCount = selectedIds.size;
    const isEnglish = uiLanguage === 'en';

    return (
      <div className="space-y-2">
        <div data-testid="history-center-filters" className="grid grid-cols-2 gap-2 text-[11px]">
          <label className="col-span-2 flex min-w-0 items-center gap-1.5 rounded-lg border border-subtle bg-surface px-2">
            <Search className="h-3.5 w-3.5 flex-shrink-0 text-muted-text" aria-hidden="true" />
            <span className="sr-only">{isEnglish ? 'Filter history by code or name' : '按代码或名称筛选历史报告'}</span>
            <input
              type="search"
              value={historyCenterFilters.code}
              onChange={(event) => updateHistoryCenterFilter('code', event.target.value)}
              data-testid="history-center-code-filter"
              placeholder={isEnglish ? 'Code or name' : '代码或名称'}
              className="h-8 min-w-0 flex-1 bg-transparent text-[11px] text-foreground outline-none placeholder:text-muted-text"
            />
          </label>
          <label className="col-span-2 flex min-w-0 items-center gap-1.5 rounded-lg border border-subtle bg-surface px-2">
            <Search className="h-3.5 w-3.5 flex-shrink-0 text-muted-text" aria-hidden="true" />
            <span className="sr-only">{isEnglish ? 'Filter history by local note' : '按本地备注筛选历史报告'}</span>
            <input
              type="search"
              value={historyCenterFilters.noteSearch}
              onChange={(event) => updateHistoryCenterFilter('noteSearch', event.target.value)}
              data-testid="history-center-note-filter"
              placeholder={isEnglish ? 'Search local notes' : '搜索本地备注'}
              className="h-8 min-w-0 flex-1 bg-transparent text-[11px] text-foreground outline-none placeholder:text-muted-text"
            />
          </label>
          <select
            value={historyCenterFilters.market}
            onChange={(event) => updateHistoryCenterFilter('market', event.target.value)}
            data-testid="history-center-market-filter"
            aria-label={isEnglish ? 'Filter history by market' : '按市场筛选历史报告'}
            className={selectClass}
          >
            {HISTORY_CENTER_MARKET_FILTERS.map((value) => (
              <option key={value} value={value}>{historyCenterMarketLabel(value, uiLanguage)}</option>
            ))}
          </select>
          <select
            value={historyCenterFilters.reportType}
            onChange={(event) => updateHistoryCenterFilter('reportType', event.target.value)}
            data-testid="history-center-report-type-filter"
            aria-label={isEnglish ? 'Filter history by report type' : '按报告类型筛选历史报告'}
            className={selectClass}
          >
            {HISTORY_CENTER_REPORT_FILTERS.map((value) => (
              <option key={value} value={value}>{historyCenterReportLabel(value, uiLanguage)}</option>
            ))}
          </select>
          <select
            value={historyCenterFilters.range}
            onChange={(event) => updateHistoryCenterFilter('range', event.target.value)}
            data-testid="history-center-range-filter"
            aria-label={isEnglish ? 'Filter history by generated time range' : '按生成时间筛选历史报告'}
            className={selectClass}
          >
            {HISTORY_CENTER_RANGE_FILTERS.map((value) => (
              <option key={value} value={value}>{historyCenterRangeLabel(value, uiLanguage)}</option>
            ))}
          </select>
          <select
            value={historyCenterFilters.sort}
            onChange={(event) => updateHistoryCenterFilter('sort', event.target.value)}
            data-testid="history-center-time-filter"
            aria-label={isEnglish ? 'Sort history by generated time' : '按生成时间排序历史报告'}
            className={selectClass}
          >
            {HISTORY_CENTER_SORT_FILTERS.map((value) => (
              <option key={value} value={value}>{historyCenterSortLabel(value, uiLanguage)}</option>
            ))}
          </select>
          <select
            value={historyCenterFilters.refreshStatus}
            onChange={(event) => updateHistoryCenterFilter('refreshStatus', event.target.value)}
            data-testid="history-center-refresh-filter"
            aria-label={isEnglish ? 'Filter history by current quote refresh status' : '按当前行情刷新状态筛选历史报告'}
            className={selectClass}
          >
            {HISTORY_CENTER_REFRESH_FILTERS.map((value) => (
              <option key={value} value={value}>{historyCenterRefreshLabel(value, uiLanguage)}</option>
            ))}
          </select>
          <select
            value={historyCenterFilters.state}
            onChange={(event) => updateHistoryCenterFilter('state', event.target.value)}
            data-testid="history-center-state-filter"
            aria-label={isEnglish ? 'Filter history by local state' : '按本地状态筛选历史报告'}
            className={selectClass}
          >
            {HISTORY_CENTER_STATE_FILTERS.map((value) => (
              <option key={value} value={value}>{historyCenterStateLabel(value, uiLanguage)}</option>
            ))}
          </select>
          <button
            type="button"
            onClick={resetHistoryCenterFilters}
            data-testid="history-center-reset-filters"
            className={`${textClass} inline-flex items-center justify-center font-medium text-secondary-text hover:text-foreground`}
          >
            {isEnglish ? 'Reset filters' : '重置筛选'}
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
            {isExportingHistory
              ? (isEnglish ? 'Exporting' : '导出中')
              : (isEnglish ? 'Export selected' : '导出已选')}
          </button>
          <button
            type="button"
            onClick={() => void handleBatchHistoryState({ important: true }, 'Marked important')}
            disabled={selectedCount === 0 || isUpdatingHistoryState}
            data-testid="history-center-important-selected"
            className="inline-flex h-8 min-w-0 items-center justify-center gap-1.5 rounded-lg border border-subtle bg-surface px-2 font-medium text-secondary-text hover:text-foreground disabled:cursor-not-allowed disabled:opacity-50"
          >
            <Flag className="h-3.5 w-3.5 flex-shrink-0" aria-hidden="true" />
            {isEnglish ? 'Important' : '标为重要'}
          </button>
          <button
            type="button"
            onClick={() => void handleBatchHistoryState({ read: true }, 'Marked read')}
            disabled={selectedCount === 0 || isUpdatingHistoryState}
            data-testid="history-center-read-selected"
            className="inline-flex h-8 min-w-0 items-center justify-center gap-1.5 rounded-lg border border-subtle bg-surface px-2 font-medium text-secondary-text hover:text-foreground disabled:cursor-not-allowed disabled:opacity-50"
          >
            <Eye className="h-3.5 w-3.5 flex-shrink-0" aria-hidden="true" />
            {isEnglish ? 'Mark read' : '标为已读'}
          </button>
          <button
            type="button"
            onClick={() => void handleBatchHistoryState({ archived: true }, 'Archived')}
            disabled={selectedCount === 0 || isUpdatingHistoryState}
            data-testid="history-center-archive-selected"
            className="inline-flex h-8 min-w-0 items-center justify-center gap-1.5 rounded-lg border border-subtle bg-surface px-2 font-medium text-secondary-text hover:text-foreground disabled:cursor-not-allowed disabled:opacity-50"
          >
            <Archive className="h-3.5 w-3.5 flex-shrink-0" aria-hidden="true" />
            {isUpdatingHistoryState
              ? (isEnglish ? 'Updating' : '更新中')
              : (isEnglish ? 'Archive' : '归档')}
          </button>
          <button
            type="button"
            onClick={() => void handleBatchHistoryState({ archived: false }, 'Unarchived')}
            disabled={selectedCount === 0 || isUpdatingHistoryState}
            data-testid="history-center-unarchive-selected"
            className="inline-flex h-8 min-w-0 items-center justify-center gap-1.5 rounded-lg border border-subtle bg-surface px-2 font-medium text-secondary-text hover:text-foreground disabled:cursor-not-allowed disabled:opacity-50"
          >
            <ArchiveRestore className="h-3.5 w-3.5 flex-shrink-0" aria-hidden="true" />
            {isEnglish ? 'Restore' : '恢复'}
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
    uiLanguage,
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
          emptyTitle={uiLanguage === 'en' ? 'No matching reports' : '没有匹配的报告'}
          emptyDescription={uiLanguage === 'en' ? 'Adjust filters or load more local history.' : '可以调整筛选条件，或加载更多本地历史。'}
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
                  key={autocompleteInputKey}
                  value={query}
                  onChange={setQuery}
                  onSubmit={(stockCode, stockName) => {
                    void handleBasicQuery(stockCode, stockName);
                  }}
                  placeholder={t('home.placeholder')}
                  disabled={isAnalyzing || isQueryingBasic}
                  className={inputError ? 'border-danger/50' : undefined}
                  closeSignal={autocompleteCloseSignal}
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

        {platformEnabled && !basicQueryError && !marketReviewReport && (!platformSession || !basicSnapshot) ? (
          <div ref={platformAuthPanelRef} className="px-3 pb-2 md:px-4">
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
                      {uiLanguage === 'en'
                        ? 'Quick snapshot stays no-AI. Quick/Deep AI uses selected quota: platform API, BYOK, or local model. Historical reports stay separate from current snapshots.'
                        : '快速快照保持未用 AI；快速/深度 AI 会使用所选额度：平台 API、BYOK 或本地模型。历史报告和当前快照单独保存。'}
                    </div>
                    <div
                      data-testid="platform-watchlist-panel"
                      className="flex min-w-0 flex-wrap items-center gap-2 text-xs text-secondary-text"
                    >
                      <span className="rounded-md border border-subtle px-2 py-1 font-medium text-foreground">
                        {uiLanguage === 'en'
                          ? `Watchlist ${platformWatchlist?.total ?? platformWatchlistItems.length}`
                          : `自选 ${platformWatchlist?.total ?? platformWatchlistItems.length}`}
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
                        loadingText={uiLanguage === 'en' ? 'Refreshing' : '刷新中'}
                        onClick={() => void handleRefreshPlatformWatchlist()}
                        data-testid="platform-watchlist-refresh"
                      >
                        <RefreshCw className="h-3.5 w-3.5" aria-hidden="true" />
                        {uiLanguage === 'en' ? 'Refresh watchlist' : '刷新自选'}
                      </Button>
                    </div>
                    {platformWatchlistRefresh ? (
                      <div
                        data-testid="platform-watchlist-refresh-summary"
                        className="flex min-w-0 flex-wrap items-center gap-2 text-xs text-secondary-text"
                      >
                        <span className="rounded-md border border-subtle px-2 py-1">{t('home.noAi')}</span>
                        <span className="rounded-md border border-subtle px-2 py-1">
                          {uiLanguage === 'en'
                            ? `refreshed ${platformWatchlistRefresh.refreshed}/${platformWatchlistRefresh.requested}`
                            : `已刷新 ${platformWatchlistRefresh.refreshed}/${platformWatchlistRefresh.requested}`}
                        </span>
                        <span className="rounded-md border border-subtle px-2 py-1">
                          {uiLanguage === 'en'
                            ? `degraded ${platformWatchlistRefresh.degraded}`
                            : `降级 ${platformWatchlistRefresh.degraded}`}
                        </span>
                        {platformWatchlistLanes.map((lane) => (
                          <span key={lane} className="rounded-md border border-subtle px-2 py-1">
                            {marketLaneLabel(lane, uiLanguage)}
                          </span>
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
                                {uiLanguage === 'en' ? 'Price' : '价格'} {formatBasicNumber(item.currentPrice)}
                              </span>
                              <span className="rounded-md border border-subtle px-1.5 py-1">
                                {uiLanguage === 'en' ? 'Chg' : '涨跌'} {formatBasicNumber(item.changePercent)}%
                              </span>
                            </div>
                            <div className="mt-2 flex min-w-0 flex-wrap gap-1">
                              <span className="rounded-md border border-subtle px-1.5 py-0.5">{marketLaneLabel(item.routeLane || 'unknown_lane', uiLanguage)}</span>
                              <span className="rounded-md border border-subtle px-1.5 py-0.5">{localizeRuntimeLabel(item.freshness, uiLanguage)}</span>
                              <span className="rounded-md border border-subtle px-1.5 py-0.5">{localizeRuntimeLabel(item.degradationStatus, uiLanguage)}</span>
                              <span className="rounded-md border border-subtle px-1.5 py-0.5">{item.aiUsed ? localizeRuntimeLabel('AI used', uiLanguage) : t('home.noAi')}</span>
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
                      onClick={() => handlePlatformAuthModeChange('login')}
                      data-testid="platform-auth-login-tab"
                      className={`rounded-md px-2 py-1 ${authMode === 'login' ? 'bg-primary text-primary-foreground' : 'text-secondary-text hover:text-foreground'}`}
                    >
                      登录
                    </button>
                    <button
                      type="button"
                      onClick={() => handlePlatformAuthModeChange('register')}
                      data-testid="platform-auth-register-tab"
                      className={`rounded-md px-2 py-1 ${authMode === 'register' ? 'bg-primary text-primary-foreground' : 'text-secondary-text hover:text-foreground'}`}
                    >
                      注册
                    </button>
                    {authError ? <span className="text-danger" data-testid="platform-auth-error">{authError}</span> : null}
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
                      disabled={authBusy}
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

        {showGuestQueryEntry ? (
          <div className="px-3 pb-3 md:px-4">
            <section
              data-testid="guest-query-entry"
              className="border-y border-subtle bg-surface/35 px-3 py-3 text-sm text-secondary-text md:px-4"
            >
              <div className="flex min-w-0 flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2 text-xs">
                    <span className="rounded-md border border-primary/40 bg-primary/10 px-2 py-1 font-medium text-primary">
                      {uiLanguage === 'en' ? 'No login required' : '无需登录'}
                    </span>
                    <span className="rounded-md border border-subtle px-2 py-1">
                      {uiLanguage === 'en' ? 'No AI quick check' : '免费快速查询'}
                    </span>
                    <span className="rounded-md border border-subtle px-2 py-1">
                      {uiLanguage === 'en' ? 'A-share / US / HK / Crypto' : 'A股 / 美股 / 港股 / 加密货币'}
                    </span>
                  </div>
                  <div className="mt-2 text-base font-semibold text-foreground">
                    先免费查一只标的，再决定是否登录保存历史和自选。
                  </div>
                  <p className="mt-1 max-w-3xl text-xs leading-5 text-secondary-text">
                    输入代码即可查看行情、均线、量价、信号评分和观察点；登录只用于保存历史、自选股和额度管理，不阻断当前查询。
                  </p>
                </div>
                <div className="flex min-w-0 flex-wrap gap-2">
                  {GUEST_QUERY_EXAMPLES.map((item) => (
                    <button
                      key={item.symbol}
                      type="button"
                      data-testid={`guest-example-${item.symbol}`}
                      disabled={isQueryingBasic}
                      onClick={() => void handleBasicQuery(item.symbol)}
                      className="inline-flex min-w-[7.5rem] items-center justify-between gap-2 rounded-lg border border-subtle bg-surface/70 px-3 py-2 text-left text-xs text-secondary-text transition-colors hover:border-primary/60 hover:text-foreground disabled:cursor-not-allowed disabled:opacity-60"
                    >
                      <span className="min-w-0">
                        <span className="block font-medium text-foreground">{item.symbol}</span>
                        <span className="block truncate">{item.label}</span>
                      </span>
                      <span className="shrink-0 rounded-md border border-subtle px-1.5 py-0.5 text-[11px] uppercase">
                        {item.market}
                      </span>
                    </button>
                  ))}
                </div>
              </div>
            </section>
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
              <div ref={basicSnapshotRef} data-testid="basic-query-snapshot" className="mb-4 max-w-4xl scroll-mt-4 rounded-xl border border-subtle bg-surface/75 p-4 shadow-soft-card">
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
                      <span className="rounded-md border border-subtle px-2 py-1">{localizeRuntimeLabel(basicSnapshot.quote.freshness, uiLanguage)}</span>
                      <span className="rounded-md border border-primary/40 bg-primary/10 px-2 py-1 text-primary">{t('home.noAi')}</span>
                    </div>
                    <h2 className="truncate text-2xl font-semibold text-foreground">{basicSnapshot.stockName || basicSnapshot.stockCode}</h2>
                    <p className="mt-1 text-sm text-secondary-text">{basicSnapshot.stockCode}</p>
                    {basicProfileSummaryItems.length > 0 ? (
                      <div
                        data-testid="basic-query-profile-highlights"
                        className="mt-3 flex min-w-0 flex-wrap gap-2 text-xs text-secondary-text"
                      >
                        {basicProfileSummaryItems.map((item) => (
                          <span
                            key={item.label}
                            className="inline-flex max-w-full items-center gap-1 rounded-md border border-subtle bg-background/25 px-2 py-1"
                          >
                            <span className="shrink-0 text-secondary-text">{item.label}</span>
                            <span className="min-w-0 truncate font-medium text-foreground">{item.value}</span>
                          </span>
                        ))}
                      </div>
                    ) : null}
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
                {basicFreeReport ? (
                  <section
                    data-testid="basic-query-free-report"
                    className="mb-4 rounded-lg border border-primary/30 bg-primary/5 p-3"
                  >
                    <div className="mb-3 flex min-w-0 flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
                      <div className="min-w-0">
                        <h3 className="text-sm font-semibold text-foreground">
                          {uiLanguage === 'en' ? 'Free no-AI briefing' : '免费轻量研判'}
                        </h3>
                        <p className="mt-1 text-xs text-secondary-text">
                          {uiLanguage === 'en'
                            ? 'Generated from quote, moving averages, volume-price behavior, and company profile. No AI quota is consumed.'
                            : '基于行情、均线、量价和公司资料生成，不消耗 AI 次数。'}
                        </p>
                      </div>
                      <div className="flex shrink-0 flex-wrap gap-2 text-xs">
                        <span className="rounded-md border border-primary/40 bg-primary/10 px-2 py-1 font-medium text-primary">
                          {uiLanguage === 'en' ? 'Signal' : '信号完整度'} {basicFreeReport.score}/100
                        </span>
                        <span className="rounded-md border border-primary/40 bg-primary/10 px-2 py-1 text-primary">
                          {t('home.noAi')}
                        </span>
                      </div>
                    </div>
                    <div
                      data-testid="basic-query-mini-chart"
                      className="mb-3 grid gap-3 rounded-lg border border-primary/25 bg-background/35 p-3 lg:grid-cols-[minmax(0,1.2fr)_minmax(13rem,0.8fr)]"
                    >
                      <div className="min-w-0">
                        <div className="flex min-w-0 flex-wrap items-center justify-between gap-2">
                          <div>
                            <div className="text-xs font-medium text-primary">
                              {basicFreeReport.miniChart.title}
                            </div>
                            <div className="mt-1 text-xl font-semibold text-foreground">
                              {basicFreeReport.miniChart.changeText}
                            </div>
                          </div>
                          <span className="rounded-md border border-subtle/70 px-2 py-1 text-[11px] text-secondary-text">
                            {basicFreeReport.miniChart.isHistorical
                              ? (uiLanguage === 'en' ? 'Historical closes' : '历史收盘')
                              : (uiLanguage === 'en' ? 'Level fallback' : '价位降级')}
                          </span>
                        </div>
                        <div className="mt-3 h-[5rem] text-primary">
                          {basicFreeReport.miniChart.sparkline ? (
                            <svg
                              aria-label={basicFreeReport.miniChart.title}
                              className="h-full w-full overflow-visible"
                              preserveAspectRatio="none"
                              role="img"
                              viewBox="0 0 220 72"
                            >
                              <polygon
                                className="fill-primary/10"
                                points={basicFreeReport.miniChart.sparkline.areaPoints}
                              />
                              <polyline
                                className="fill-none stroke-primary"
                                points={basicFreeReport.miniChart.sparkline.linePoints}
                                strokeLinecap="round"
                                strokeLinejoin="round"
                                strokeWidth="3"
                              />
                            </svg>
                          ) : (
                            <div className="flex h-full items-center justify-center rounded-md border border-dashed border-subtle text-xs text-secondary-text">
                              {uiLanguage === 'en' ? 'Trend data unavailable' : '趋势数据暂不可用'}
                            </div>
                          )}
                        </div>
                      </div>
                      <div className="grid min-w-0 gap-2 sm:grid-cols-3 lg:grid-cols-1">
                        <div className="min-w-0 rounded-md border border-subtle/70 px-3 py-2">
                          <div className="text-xs text-secondary-text">{uiLanguage === 'en' ? 'Range low' : '区间低点'}</div>
                          <div className="mt-1 truncate text-sm font-semibold text-foreground">{basicFreeReport.miniChart.minText}</div>
                        </div>
                        <div className="min-w-0 rounded-md border border-subtle/70 px-3 py-2">
                          <div className="text-xs text-secondary-text">{uiLanguage === 'en' ? 'Range high' : '区间高点'}</div>
                          <div className="mt-1 truncate text-sm font-semibold text-foreground">{basicFreeReport.miniChart.maxText}</div>
                        </div>
                        <div className="min-w-0 rounded-md border border-subtle/70 px-3 py-2">
                          <div className="text-xs text-secondary-text">{uiLanguage === 'en' ? 'Source' : '来源'}</div>
                          <div className="mt-1 truncate text-sm font-semibold text-foreground">{localizeGeneratedSource(basicFreeReport.miniChart.source, uiLanguage)}</div>
                        </div>
                      </div>
                    </div>
                    {basicFreeReport.signalScore ? (
                      <div
                        data-testid="basic-query-signal-score"
                        className="mb-3 rounded-lg border border-primary/30 bg-background/35 p-3"
                      >
                        <div className="flex min-w-0 flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                          <div className="min-w-0">
                            <div className="text-xs font-medium text-primary">
                              {uiLanguage === 'en' ? 'Signal score' : '信号评分'}
                            </div>
                            <h4 className="mt-1 text-base font-semibold text-foreground">
                              {basicFreeReport.signalScore.label}
                            </h4>
                            <p className="mt-1 text-xs leading-relaxed text-secondary-text">
                              {basicFreeReport.signalScore.summary}
                            </p>
                          </div>
                          <div className="shrink-0 rounded-lg border border-primary/35 bg-primary/10 px-4 py-3 text-center">
                            <div className="text-2xl font-semibold text-primary">
                              {basicFreeReport.signalScore.score}/100
                            </div>
                            <div className="mt-1 text-[11px] text-secondary-text">{t('home.noAi')}</div>
                          </div>
                        </div>
                        <div className="mt-3 h-2 overflow-hidden rounded-full bg-surface">
                          <div
                            className="h-full rounded-full bg-primary"
                            style={{ width: `${basicFreeReport.signalScore.score}%` }}
                          />
                        </div>
                        <div className="mt-3 grid gap-2 md:grid-cols-2 xl:grid-cols-4">
                          {basicFreeReport.signalScore.components.map((component) => (
                            <div
                              key={`${component.key}-${component.label}`}
                              className="min-w-0 rounded-lg border border-subtle/80 bg-surface/35 p-3"
                            >
                              <div className="flex min-w-0 items-start justify-between gap-2">
                                <div className="min-w-0">
                                  <div className="truncate text-sm font-semibold text-foreground">
                                    {component.label}
                                  </div>
                                  <div className="mt-1 truncate text-[11px] text-secondary-text">
                                    {component.status}
                                  </div>
                                </div>
                                <span className="shrink-0 rounded-md border border-primary/35 bg-primary/10 px-1.5 py-0.5 text-[11px] font-medium text-primary">
                                  {component.score}
                                </span>
                              </div>
                              <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-background">
                                <div
                                  className="h-full rounded-full bg-primary/80"
                                  style={{ width: `${component.score}%` }}
                                />
                              </div>
                              <p className="mt-2 line-clamp-3 text-xs leading-relaxed text-secondary-text">
                                {component.detail}
                              </p>
                            </div>
                          ))}
                        </div>
                        <div className="mt-3 flex min-w-0 flex-wrap gap-1.5 text-[11px] text-secondary-text">
                          <span className="rounded-md border border-subtle/70 px-1.5 py-0.5">
                            {basicFreeReport.signalScore.source}
                          </span>
                          <span className="rounded-md border border-subtle/70 px-1.5 py-0.5">
                            {uiLanguage === 'en' ? 'Information analysis only' : '仅作信息分析'}
                          </span>
                        </div>
                      </div>
                    ) : null}
                    {basicSnapshot.intelligence?.retentionBrief ? (
                      <div
                        data-testid="basic-query-retention-brief"
                        className="mb-3 rounded-lg border border-primary/30 bg-background/45 p-3"
                      >
                        <div className="flex min-w-0 flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                          <div className="min-w-0">
                            <div className="text-xs font-medium text-primary">
                              {uiLanguage === 'en' ? 'Why keep reading' : '为什么值得继续看'}
                            </div>
                            <h4 className="mt-1 text-base font-semibold text-foreground">
                              {localizeGeneratedText(basicSnapshot.intelligence.retentionBrief.headline, uiLanguage)}
                            </h4>
                            <p className="mt-2 text-xs leading-relaxed text-secondary-text">
                              {localizeGeneratedText(basicSnapshot.intelligence.retentionBrief.whyItMatters, uiLanguage)}
                            </p>
                          </div>
                          <div className="shrink-0 rounded-lg border border-primary/35 bg-primary/10 px-3 py-2 text-xs text-primary">
                            {t('home.noAi')}
                          </div>
                        </div>
                        <div className="mt-3 grid gap-2 lg:grid-cols-[minmax(12rem,0.9fr)_minmax(0,1.2fr)]">
                          <div className="min-w-0 rounded-lg border border-subtle/80 bg-surface/35 p-3">
                            <div className="text-xs text-secondary-text">
                              {uiLanguage === 'en' ? 'Support / resistance' : '支撑 / 压力'}
                            </div>
                            <div className="mt-1 text-sm font-semibold text-foreground">
                              {localizeGeneratedText(basicSnapshot.intelligence.retentionBrief.supportResistance, uiLanguage)}
                            </div>
                            <div className="mt-2 text-[11px] text-secondary-text">
                              {localizeGeneratedSource(basicSnapshot.intelligence.retentionBrief.source, uiLanguage)}
                            </div>
                          </div>
                          <div className="min-w-0 rounded-lg border border-subtle/80 bg-surface/35 p-3">
                            <div className="text-xs text-secondary-text">
                              {uiLanguage === 'en' ? 'Next checks' : '下一步关注'}
                            </div>
                            <div className="mt-2 grid gap-1.5 text-xs leading-relaxed text-secondary-text md:grid-cols-3">
                              {basicSnapshot.intelligence.retentionBrief.nextSteps.map((step) => (
                                <div key={step} className="rounded-md border border-subtle/70 px-2 py-1.5">
                                  {localizeGeneratedText(step, uiLanguage)}
                                </div>
                              ))}
                            </div>
                          </div>
                        </div>
                        <div className="mt-3 flex min-w-0 flex-col gap-2 rounded-lg border border-primary/25 bg-primary/5 px-3 py-2 text-xs text-secondary-text sm:flex-row sm:items-center sm:justify-between">
                          <span className="min-w-0 leading-relaxed">
                            {localizeGeneratedText(basicSnapshot.intelligence.retentionBrief.upgradeHint, uiLanguage)}
                          </span>
                          <span className="shrink-0 rounded-md border border-subtle/70 px-2 py-1">
                            {localizeGeneratedText(basicSnapshot.intelligence.retentionBrief.boundary, uiLanguage)}
                          </span>
                        </div>
                      </div>
                    ) : null}
                    {basicSnapshot.intelligence?.newsCenter ? (
                      <div
                        data-testid="basic-query-news-center"
                        className="mb-3 rounded-lg border border-primary/30 bg-background/40 p-3"
                      >
                        <div className="mb-3 flex min-w-0 flex-col gap-2 lg:flex-row lg:items-start lg:justify-between">
                          <div className="min-w-0">
                            <div className="text-xs font-medium text-primary">
                              {uiLanguage === 'en' ? 'News center' : '资讯中心'}
                            </div>
                            <h4 className="mt-1 text-base font-semibold text-foreground">
                              {localizeGeneratedText(basicSnapshot.intelligence.newsCenter.title, uiLanguage)}
                            </h4>
                            <p className="mt-1 text-xs leading-relaxed text-secondary-text">
                              {localizeGeneratedText(basicSnapshot.intelligence.newsCenter.summary, uiLanguage)}
                            </p>
                          </div>
                          <div className="flex shrink-0 flex-wrap gap-1.5 text-[11px]">
                            <span className="rounded-md border border-primary/35 bg-primary/10 px-2 py-1 font-medium text-primary">
                              {basicSnapshot.intelligence.newsCenter.aiUsed
                                ? (uiLanguage === 'en' ? 'AI used' : '已使用 AI')
                                : t('home.noAi')}
                            </span>
                            <span className="rounded-md border border-subtle px-2 py-1 text-secondary-text">
                              {basicSnapshot.intelligence.newsCenter.publicSearchUsed
                                ? (uiLanguage === 'en' ? 'Public search' : '公共搜索')
                                : (uiLanguage === 'en' ? 'No public search' : '未用公共搜索')}
                            </span>
                          </div>
                        </div>
                        <div className="grid gap-2 md:grid-cols-2 xl:grid-cols-4">
                          {basicSnapshot.intelligence.newsCenter.items.map((item) => (
                            <div
                              key={`${item.category}-${item.title}`}
                              className="min-w-0 rounded-lg border border-subtle/80 bg-surface/35 p-3"
                            >
                              <div className="flex min-w-0 items-start justify-between gap-2">
                                <div className="min-w-0">
                                  <div className="truncate text-sm font-semibold text-foreground">
                                    {localizeGeneratedText(item.title, uiLanguage)}
                                  </div>
                                  <div className="mt-1 truncate text-[11px] text-primary">
                                    {localizeGeneratedText(item.category, uiLanguage)}
                                  </div>
                                </div>
                                <span className="shrink-0 rounded-md border border-subtle px-1.5 py-0.5 text-[11px] text-secondary-text">
                                  {localizeGeneratedStatus(item.status, uiLanguage)}
                                </span>
                              </div>
                              <p className="mt-2 line-clamp-3 text-xs leading-relaxed text-secondary-text">
                                {localizeGeneratedText(item.summary, uiLanguage)}
                              </p>
                              <p className="mt-2 line-clamp-2 text-[11px] leading-relaxed text-secondary-text">
                                {localizeGeneratedText(item.action, uiLanguage)}
                              </p>
                              <div className="mt-2 flex min-w-0 flex-wrap gap-1.5 text-[11px] text-secondary-text">
                                <span className="max-w-full truncate rounded-md border border-subtle/70 px-1.5 py-0.5">
                                  {localizeGeneratedSource(item.source, uiLanguage)}
                                </span>
                                {item.updatedAt ? (
                                  <span className="max-w-full truncate rounded-md border border-subtle/70 px-1.5 py-0.5">
                                    {item.updatedAt}
                                  </span>
                                ) : null}
                              </div>
                            </div>
                          ))}
                        </div>
                        <div className="mt-3 flex min-w-0 flex-col gap-2 rounded-lg border border-primary/25 bg-primary/5 px-3 py-2 text-xs text-secondary-text sm:flex-row sm:items-center sm:justify-between">
                          <span className="min-w-0 leading-relaxed">
                            {localizeGeneratedText(basicSnapshot.intelligence.newsCenter.premiumUnlock, uiLanguage)}
                          </span>
                          <span className="shrink-0 rounded-md border border-subtle/70 px-2 py-1">
                            {localizeGeneratedText(basicSnapshot.intelligence.newsCenter.boundary, uiLanguage)}
                          </span>
                        </div>
                      </div>
                    ) : null}
                    {basicSnapshot.intelligence?.klineForecast ? (
                      <div
                        data-testid="basic-query-kline-forecast-lab"
                        className="mb-3 rounded-lg border border-primary/30 bg-primary/5 p-3"
                      >
                        <div className="mb-3 flex min-w-0 flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                          <div className="min-w-0">
                            <div className="text-xs font-medium text-primary">
                              {localizeGeneratedText('Kronos-ready', uiLanguage)}
                            </div>
                            <h4 className="mt-1 text-base font-semibold text-foreground">
                              {localizeGeneratedText(basicSnapshot.intelligence.klineForecast.title, uiLanguage)}
                            </h4>
                            <p className="mt-1 text-xs leading-relaxed text-secondary-text">
                              {localizeGeneratedText(basicSnapshot.intelligence.klineForecast.adapterStatus, uiLanguage)}
                            </p>
                          </div>
                          <div className="grid shrink-0 grid-cols-3 gap-2 text-center text-xs">
                            <div className="rounded-lg border border-primary/35 bg-primary/10 px-3 py-2">
                              <div className="text-[11px] text-secondary-text">{localizeGeneratedText('Horizon', uiLanguage)}</div>
                              <div className="mt-1 font-semibold text-primary">
                                {localizeGeneratedHorizon(basicSnapshot.intelligence.klineForecast.horizon, uiLanguage)}
                              </div>
                            </div>
                            <div className="rounded-lg border border-primary/35 bg-primary/10 px-3 py-2">
                              <div className="text-[11px] text-secondary-text">{localizeGeneratedText('Confidence', uiLanguage)}</div>
                              <div className="mt-1 font-semibold text-primary">
                                {basicSnapshot.intelligence.klineForecast.confidence}/100
                              </div>
                            </div>
                            <div className="rounded-lg border border-primary/35 bg-primary/10 px-3 py-2">
                              <div className="text-[11px] text-secondary-text">{localizeGeneratedText('Direction', uiLanguage)}</div>
                              <div className="mt-1 font-semibold text-primary">
                                {localizeGeneratedStatus(basicSnapshot.intelligence.klineForecast.direction, uiLanguage)}
                              </div>
                            </div>
                          </div>
                        </div>
                        <div className="mb-3 grid gap-2 md:grid-cols-3">
                          <div className="rounded-lg border border-subtle/80 bg-background/35 p-3">
                            <div className="text-xs text-secondary-text">{localizeGeneratedText('Support', uiLanguage)}</div>
                            <div className="mt-1 text-sm font-semibold text-foreground">
                              {formatBasicNumber(basicSnapshot.intelligence.klineForecast.support)}
                            </div>
                          </div>
                          <div className="rounded-lg border border-subtle/80 bg-background/35 p-3">
                            <div className="text-xs text-secondary-text">{localizeGeneratedText('Resistance', uiLanguage)}</div>
                            <div className="mt-1 text-sm font-semibold text-foreground">
                              {formatBasicNumber(basicSnapshot.intelligence.klineForecast.resistance)}
                            </div>
                          </div>
                          <div className="rounded-lg border border-subtle/80 bg-background/35 p-3">
                            <div className="text-xs text-secondary-text">{localizeGeneratedText('Source', uiLanguage)}</div>
                            <div className="mt-1 truncate text-sm font-semibold text-foreground">
                              {localizeGeneratedSource(basicSnapshot.intelligence.klineForecast.source, uiLanguage)}
                            </div>
                          </div>
                        </div>
                        <div className="grid gap-2 lg:grid-cols-3">
                          {basicSnapshot.intelligence.klineForecast.scenarios.map((scenario) => (
                            <div
                              key={`${scenario.label}-${scenario.direction}`}
                              className="min-w-0 rounded-lg border border-subtle/80 bg-background/35 p-3"
                            >
                              <div className="flex min-w-0 items-start justify-between gap-2">
                                <div className="min-w-0">
                                  <div className="truncate text-sm font-semibold text-foreground">
                                    {localizeGeneratedText(scenario.label, uiLanguage)}
                                  </div>
                                  <div className="mt-1 truncate text-[11px] text-primary">
                                    {localizeGeneratedStatus(scenario.direction, uiLanguage)}
                                  </div>
                                </div>
                                <span className="shrink-0 rounded-md border border-primary/35 bg-primary/10 px-1.5 py-0.5 text-[11px] font-medium text-primary">
                                  {scenario.probability}%
                                </span>
                              </div>
                              <p className="mt-2 text-xs leading-relaxed text-secondary-text">
                                {localizeGeneratedText(scenario.trigger, uiLanguage)}
                              </p>
                              <p className="mt-2 line-clamp-2 text-[11px] leading-relaxed text-secondary-text">
                                {localizeGeneratedText(scenario.detail, uiLanguage)}
                              </p>
                            </div>
                          ))}
                        </div>
                        <div className="mt-3 rounded-lg border border-primary/25 bg-background/35 p-3" data-testid="basic-query-kronos-sandbox">
                          <div className="flex min-w-0 flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                            <div className="min-w-0">
                              <div className="text-xs font-medium text-primary">
                                {uiLanguage === 'en' ? 'Kronos sandbox' : 'Kronos 沙箱'}
                              </div>
                              <p className="mt-1 text-xs leading-relaxed text-secondary-text">
                                {localizeGeneratedText('Run the local adapter probe. If the real Kronos runtime is unavailable, this stays on the local rules fallback.', uiLanguage)}
                              </p>
                            </div>
                            <Button
                              type="button"
                              variant="secondary"
                              size="sm"
                              onClick={() => void handleRunKronosForecast(false)}
                              isLoading={isRunningKronosForecast}
                              loadingText={uiLanguage === 'en' ? 'Checking Kronos' : '正在运行 Kronos'}
                              data-testid="basic-query-kronos-run"
                            >
                              <Sparkles className="h-4 w-4" />
                              {uiLanguage === 'en' ? 'Check Kronos' : '运行 Kronos 模型'}
                            </Button>
                          </div>
                          {kronosForecastError ? (
                            <div data-testid="basic-query-kronos-error" className="mt-3 rounded-lg border border-danger/40 bg-danger/10 px-3 py-2 text-xs text-danger">
                              {kronosForecastError}
                            </div>
                          ) : null}
                          {kronosForecast ? (
                            <div data-testid="basic-query-kronos-live-result" className="mt-3 space-y-3">
                              <div className="flex min-w-0 flex-wrap gap-2 text-xs text-secondary-text">
                                <span className="rounded-md border border-subtle/70 px-2 py-1">
                                  {localizeGeneratedStatus(kronosForecast.status, uiLanguage)}
                                </span>
                                <span className="rounded-md border border-subtle/70 px-2 py-1">
                                  {localizeGeneratedText(kronosForecast.kronosModelUsed ? 'Real Kronos model' : 'Local rules fallback', uiLanguage)}
                                </span>
                                <span className="rounded-md border border-subtle/70 px-2 py-1">
                                  {localizeGeneratedSource(kronosForecast.source, uiLanguage)}
                                </span>
                                <span className="rounded-md border border-subtle/70 px-2 py-1">
                                  {kronosForecast.elapsedMs.toLocaleString(undefined, { maximumFractionDigits: 1 })}ms
                                </span>
                              </div>
                              <div className="grid gap-2 md:grid-cols-3">
                                <div className="rounded-lg border border-subtle/80 bg-surface/35 p-3">
                                  <div className="text-xs text-secondary-text">{localizeGeneratedText('Model', uiLanguage)}</div>
                                  <div className="mt-1 truncate text-sm font-semibold text-foreground">
                                    {kronosForecast.modelId}
                                  </div>
                                  <div className="mt-1 truncate text-[11px] text-secondary-text">
                                    {kronosForecast.tokenizerId}
                                  </div>
                                </div>
                                <div className="rounded-lg border border-subtle/80 bg-surface/35 p-3">
                                  <div className="text-xs text-secondary-text">{localizeGeneratedText('Forecast', uiLanguage)}</div>
                                  <div className="mt-1 text-sm font-semibold text-foreground">
                                    {localizeGeneratedStatus(kronosForecast.direction, uiLanguage)} / {kronosForecast.confidence}/100
                                  </div>
                                  <div className="mt-1 text-[11px] text-secondary-text">
                                    {localizeGeneratedHorizon(kronosForecast.horizon, uiLanguage)}
                                    {uiLanguage === 'en' ? `, lookback ${kronosForecast.lookback}` : `，回看 ${kronosForecast.lookback} 根`}
                                  </div>
                                </div>
                                <div className="rounded-lg border border-subtle/80 bg-surface/35 p-3" data-testid="basic-query-kronos-backtest-summary">
                                  <div className="text-xs text-secondary-text">{localizeGeneratedText('Backtest records', uiLanguage)}</div>
                                  <div className="mt-1 text-sm font-semibold text-foreground">
                                    {uiLanguage === 'en'
                                      ? `${kronosForecast.backtestSummary.records} records`
                                      : `${kronosForecast.backtestSummary.records} 条记录`}
                                  </div>
                                  <div className="mt-1 text-[11px] text-secondary-text">
                                    {uiLanguage === 'en' ? 'hit rate' : '命中率'} {kronosForecast.backtestSummary.hitRate ?? '-'}
                                  </div>
                                </div>
                              </div>
                              <div data-testid="basic-query-kronos-dependency-status" className="flex min-w-0 flex-wrap gap-2 text-xs">
                                {Object.entries(kronosForecast.dependencyStatus).map(([name, available]) => (
                                  <span
                                    key={name}
                                    className={`rounded-md border px-2 py-1 ${available ? 'border-success/40 bg-success/10 text-success' : 'border-warning/40 bg-warning/10 text-warning'}`}
                                  >
                                    {localizeGeneratedSource(name, uiLanguage)}: {localizeGeneratedText(available ? 'ready' : 'missing', uiLanguage)}
                                  </span>
                                ))}
                              </div>
                              {kronosForecast.missingDependencies.length ? (
                                <div className="rounded-lg border border-warning/35 bg-warning/10 px-3 py-2 text-xs text-warning">
                                  {uiLanguage === 'en' ? 'Missing' : '缺失'}: {kronosForecast.missingDependencies.join(', ')}
                                </div>
                              ) : null}
                              {kronosForecast.forecastPoints.length ? (
                                <div className="grid gap-2 md:grid-cols-5" data-testid="basic-query-kronos-forecast-points">
                                  {kronosForecast.forecastPoints.slice(0, 5).map((point) => (
                                    <div key={point.timestamp} className="min-w-0 rounded-lg border border-subtle/80 bg-surface/35 p-2">
                                      <div className="truncate text-[11px] text-secondary-text">{point.timestamp}</div>
                                      <div className="mt-1 text-sm font-semibold text-foreground">
                                        {formatBasicNumber(point.close)}
                                      </div>
                                    </div>
                                  ))}
                                </div>
                              ) : null}
                              {kronosForecast.warnings.length ? (
                                <div className="space-y-1 text-xs text-secondary-text">
                                  {kronosForecast.warnings.slice(0, 3).map((warning) => (
                                    <div key={warning} className="rounded-md border border-subtle/70 px-2 py-1">
                                      {localizeGeneratedText(warning, uiLanguage)}
                                    </div>
                                  ))}
                                </div>
                              ) : null}
                            </div>
                          ) : null}
                        </div>
                        <div className="mt-3 flex min-w-0 flex-col gap-2 rounded-lg border border-primary/25 bg-background/35 px-3 py-2 text-xs text-secondary-text sm:flex-row sm:items-center sm:justify-between">
                          <span className="min-w-0 leading-relaxed">
                            {localizeGeneratedText(basicSnapshot.intelligence.klineForecast.premiumUnlock, uiLanguage)}
                          </span>
                          <span className="shrink-0 rounded-md border border-subtle/70 px-2 py-1">
                            {localizeGeneratedText(basicSnapshot.intelligence.klineForecast.boundary, uiLanguage)}
                          </span>
                        </div>
                      </div>
                    ) : null}
                    {(basicSnapshot.intelligence?.newsCenter || basicSnapshot.intelligence?.klineForecast) ? (
                      <div
                        data-testid="basic-query-premium-feature-ladder"
                        className="mb-3 grid gap-2 rounded-lg border border-primary/25 bg-background/35 p-3 md:grid-cols-4"
                      >
                        {[
                          [
                            uiLanguage === 'en' ? 'Free no-AI' : '免费无AI',
                            uiLanguage === 'en' ? 'Quote, MA, volume, profile, local information lanes.' : '行情、均线、成交量、公司资料和本地信息通道。',
                          ],
                          [
                            uiLanguage === 'en' ? 'Premium news' : '高级资讯',
                            uiLanguage === 'en' ? 'Realtime news, filings, source links, sector context.' : '实时资讯、公告、来源链接和板块背景。',
                          ],
                          [
                            localizeGeneratedText('Kronos-ready', uiLanguage),
                            uiLanguage === 'en' ? 'K-line forecast adapter lane after local model approval.' : '本地模型确认后可使用K线预测适配通道。',
                          ],
                          [
                            uiLanguage === 'en' ? 'BYOK or local model' : '自带Key或本地模型',
                            uiLanguage === 'en' ? 'Use platform API, user API key, or approved local model quota.' : '可使用平台 API、用户自带 API Key 或已批准的本地模型额度。',
                          ],
                        ].map(([title, detail]) => (
                          <div key={title} className="min-w-0 rounded-lg border border-subtle/80 bg-surface/35 p-3">
                            <div className="truncate text-sm font-semibold text-foreground">{title}</div>
                            <div className="mt-1 line-clamp-3 text-xs leading-relaxed text-secondary-text">
                              {detail}
                            </div>
                          </div>
                        ))}
                      </div>
                    ) : null}
                    {basicSnapshot.intelligence?.items?.length ? (
                      <div
                        data-testid="basic-query-intelligence-panel"
                        className="mb-3 rounded-lg border border-subtle bg-background/35 p-3"
                      >
                        <div className="mb-3 flex min-w-0 flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
                          <div className="min-w-0">
                            <h4 className="text-sm font-semibold text-foreground">
                              {uiLanguage === 'en' ? 'Information digest' : '资讯摘要'}
                            </h4>
                            <p className="mt-1 text-xs leading-relaxed text-secondary-text">
                              {uiLanguage === 'en'
                                ? 'Low-cost facts from market data and cached company profile; realtime search and AI remain off.'
                                : '基于行情与公司资料生成的低成本摘要；实时搜索和 AI 仍保持关闭。'}
                            </p>
                          </div>
                          <div className="flex shrink-0 flex-wrap gap-2 text-xs">
                            <span className="rounded-md border border-primary/40 bg-primary/10 px-2 py-1 font-medium text-primary">
                              {t('home.noAi')}
                            </span>
                            <span className="rounded-md border border-subtle px-2 py-1 text-secondary-text">
                              {localizeRuntimeLabel(basicSnapshot.intelligence.mode, uiLanguage)}
                            </span>
                          </div>
                        </div>
                        <div className="grid gap-2 md:grid-cols-3">
                          {basicSnapshot.intelligence.items.map((item) => (
                            <div
                              key={`${item.category}-${item.title}`}
                              className="min-w-0 rounded-lg border border-subtle/80 bg-surface/35 p-3"
                            >
                              <div className="flex min-w-0 items-center justify-between gap-2">
                                <div className="truncate text-xs font-medium text-primary">
                                  {basicIntelligenceCategoryLabel(item.category, item.title, uiLanguage)}
                                </div>
                                <span className="shrink-0 rounded-md border border-subtle px-1.5 py-0.5 text-[11px] text-secondary-text">
                                  {basicIntelligenceStatusLabel(item.status, uiLanguage)}
                                </span>
                              </div>
                              <div className="mt-2 line-clamp-3 text-xs leading-relaxed text-secondary-text">
                                {localizeGeneratedText(item.summary, uiLanguage)}
                              </div>
                              <div className="mt-2 flex min-w-0 flex-wrap gap-1.5 text-[11px] text-secondary-text">
                                <span className="max-w-full truncate rounded-md border border-subtle/70 px-1.5 py-0.5">
                                  {localizeGeneratedSource(item.source, uiLanguage)}
                                </span>
                                {item.updatedAt ? (
                                  <span className="max-w-full truncate rounded-md border border-subtle/70 px-1.5 py-0.5">
                                    {item.updatedAt}
                                  </span>
                                ) : null}
                              </div>
                            </div>
                          ))}
                        </div>
                        {basicSnapshot.intelligence.boundary ? (
                          <div className="mt-3 text-[11px] leading-relaxed text-secondary-text">
                            {localizeGeneratedText(basicSnapshot.intelligence.boundary, uiLanguage)}
                          </div>
                        ) : null}
                      </div>
                    ) : null}
                    {basicSnapshot.intelligence?.marketBrief ? (
                      <div
                        data-testid="basic-query-market-brief"
                        className="mb-3 rounded-lg border border-primary/25 bg-primary/5 p-3"
                      >
                        <div className="flex min-w-0 flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                          <div className="min-w-0">
                            <div className="text-xs font-medium text-primary">
                              {uiLanguage === 'en' ? 'Market lane' : '市场通道'}
                            </div>
                            <h4 className="mt-1 text-sm font-semibold text-foreground">
                              {localizeGeneratedText(basicSnapshot.intelligence.marketBrief.title, uiLanguage)}
                            </h4>
                            <p className="mt-1 text-xs leading-relaxed text-secondary-text">
                              {localizeGeneratedText(basicSnapshot.intelligence.marketBrief.summary, uiLanguage)}
                            </p>
                          </div>
                          <div className="flex shrink-0 flex-wrap gap-2 text-xs">
                            <span className="rounded-md border border-primary/35 bg-primary/10 px-2 py-1 font-medium text-primary">
                              {marketLaneLabel(basicSnapshot.intelligence.marketBrief.lane, uiLanguage)}
                            </span>
                            <span className="rounded-md border border-subtle px-2 py-1 text-secondary-text">
                              {basicSnapshot.intelligence.marketBrief.market.toUpperCase()}
                            </span>
                          </div>
                        </div>
                        <div className="mt-3 flex min-w-0 flex-wrap gap-1.5 text-[11px] text-secondary-text">
                              {basicSnapshot.intelligence.marketBrief.focusPoints.map((point) => (
                            <span key={point} className="max-w-full rounded-md border border-subtle/70 px-1.5 py-0.5">
                              {localizeGeneratedText(point, uiLanguage)}
                            </span>
                          ))}
                        </div>
                        <div className="mt-3 text-[11px] leading-relaxed text-secondary-text">
                          {localizeGeneratedText(basicSnapshot.intelligence.marketBrief.deepUnlock, uiLanguage)}
                        </div>
                      </div>
                    ) : null}
                    {basicSnapshot.intelligence?.freeInsights?.length ? (
                      <div
                        data-testid="basic-query-free-insights"
                        className="mb-3 rounded-lg border border-subtle bg-background/35 p-3"
                      >
                        <div className="mb-3 flex min-w-0 flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
                          <div className="min-w-0">
                            <h4 className="text-sm font-semibold text-foreground">
                              {uiLanguage === 'en' ? 'Free insights' : '免费洞察'}
                            </h4>
                            <p className="mt-1 text-xs leading-relaxed text-secondary-text">
                              {uiLanguage === 'en'
                                ? 'Rule-based movement, peer, and risk context generated from local market data only.'
                                : '仅基于本地行情规则生成涨跌、参照和风险解释，不调用 AI 或公共搜索。'}
                            </p>
                          </div>
                          <span className="shrink-0 rounded-md border border-primary/35 bg-primary/10 px-2 py-1 text-[11px] font-medium text-primary">
                            {t('home.noAi')}
                          </span>
                        </div>
                        <div className="grid gap-2 md:grid-cols-3">
                          {basicSnapshot.intelligence.freeInsights.map((item) => (
                            <div
                              key={`${item.category}-${item.title}`}
                              className="min-w-0 rounded-lg border border-subtle/80 bg-surface/35 p-3"
                            >
                              <div className="flex min-w-0 items-center justify-between gap-2">
                                <div className="truncate text-sm font-semibold text-foreground">{localizeGeneratedText(item.title, uiLanguage)}</div>
                                <span className="shrink-0 rounded-md border border-subtle px-1.5 py-0.5 text-[11px] text-secondary-text">
                                  {localizeGeneratedStatus(item.tone, uiLanguage)}
                                </span>
                              </div>
                              <div className="mt-2 text-xs leading-relaxed text-secondary-text">
                                {localizeGeneratedText(item.summary, uiLanguage)}
                              </div>
                              <div className="mt-3 flex min-w-0 flex-wrap gap-1.5 text-[11px] text-secondary-text">
                                {item.bullets.map((bullet) => (
                                  <span key={bullet} className="max-w-full truncate rounded-md border border-subtle/70 px-1.5 py-0.5">
                                    {localizeGeneratedText(bullet, uiLanguage)}
                                  </span>
                                ))}
                              </div>
                              <div className="mt-2 truncate text-[11px] text-secondary-text">
                                {localizeGeneratedSource(item.source, uiLanguage)}
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>
                    ) : null}
                    {basicSnapshot.intelligence?.peerComparison?.rows?.length ? (
                      <div
                        data-testid="basic-query-peer-comparison"
                        className="mb-3 rounded-lg border border-subtle bg-background/35 p-3"
                      >
                        <div className="mb-3 flex min-w-0 flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
                          <div className="min-w-0">
                            <h4 className="text-sm font-semibold text-foreground">
                              {uiLanguage === 'en' ? 'Peer / market comparison' : '同业/大盘对照'}
                            </h4>
                            <p className="mt-1 text-xs leading-relaxed text-secondary-text">
                              {localizeGeneratedText(basicSnapshot.intelligence.peerComparison.summary, uiLanguage)}
                            </p>
                          </div>
                          <span className="shrink-0 rounded-md border border-primary/35 bg-primary/10 px-2 py-1 text-[11px] font-medium text-primary">
                            {t('home.noAi')}
                          </span>
                        </div>
                        <div className="overflow-hidden rounded-lg border border-subtle/70">
                          <div className="hidden grid-cols-[minmax(7rem,0.8fr)_minmax(8rem,0.8fr)_minmax(12rem,1.3fr)_minmax(12rem,1.2fr)] gap-2 border-b border-subtle/70 bg-surface/35 px-3 py-2 text-[11px] font-medium text-secondary-text md:grid">
                            <div>{uiLanguage === 'en' ? 'Reference' : '参照对象'}</div>
                            <div>{uiLanguage === 'en' ? 'Role' : '角色'}</div>
                            <div>{uiLanguage === 'en' ? 'Current signal' : '本股位置'}</div>
                            <div>{uiLanguage === 'en' ? 'Next check' : '下一步对比'}</div>
                          </div>
                          <div className="divide-y divide-subtle/70">
                            {basicSnapshot.intelligence.peerComparison.rows.map((row) => (
                              <div
                                key={`${row.symbol}-${row.role}`}
                                className="grid gap-2 px-3 py-3 text-xs md:grid-cols-[minmax(7rem,0.8fr)_minmax(8rem,0.8fr)_minmax(12rem,1.3fr)_minmax(12rem,1.2fr)]"
                              >
                                <div className="min-w-0">
                                  <div className="font-semibold text-foreground">{row.symbol}</div>
                                  <div className="mt-0.5 truncate text-[11px] text-secondary-text">{localizeGeneratedText(row.label, uiLanguage)}</div>
                                </div>
                                <div className="min-w-0 text-secondary-text">
                                  <span className="rounded-md border border-subtle/70 px-1.5 py-0.5">{localizeGeneratedText(row.role, uiLanguage)}</span>
                                </div>
                                <div className="min-w-0 leading-relaxed text-secondary-text">
                                  {localizeGeneratedText(row.currentSignal, uiLanguage)}
                                </div>
                                <div className="min-w-0 leading-relaxed text-secondary-text">
                                  {localizeGeneratedText(row.compareNext, uiLanguage)}
                                </div>
                              </div>
                            ))}
                          </div>
                        </div>
                      </div>
                    ) : null}
                    {(basicSnapshot.intelligence?.watchPoints?.length || basicSnapshot.intelligence?.comparisonTargets?.length) ? (
                      <div
                        data-testid="basic-query-watch-points"
                        className="mb-3 grid gap-3 rounded-lg border border-primary/25 bg-background/35 p-3 lg:grid-cols-[minmax(0,1.25fr)_minmax(14rem,0.75fr)]"
                      >
                        <div className="min-w-0">
                          <div className="mb-2 flex min-w-0 items-center justify-between gap-2">
                            <h4 className="text-sm font-semibold text-foreground">
                              {uiLanguage === 'en' ? 'Next watch points' : '下一步观察'}
                            </h4>
                            <span className="shrink-0 rounded-md border border-primary/35 bg-primary/10 px-2 py-1 text-[11px] font-medium text-primary">
                              {t('home.noAi')}
                            </span>
                          </div>
                          <div className="grid gap-2 md:grid-cols-2">
                            {(basicSnapshot.intelligence?.watchPoints ?? []).map((item) => (
                              <div key={`${item.category}-${item.title}`} className="min-w-0 rounded-lg border border-subtle bg-surface/35 p-3">
                                <div className="flex min-w-0 items-start justify-between gap-2">
                                  <div className="min-w-0">
                                    <div className="truncate text-sm font-semibold text-foreground">{localizeGeneratedText(item.title, uiLanguage)}</div>
                                    <div className="mt-1 text-xs leading-relaxed text-secondary-text">{localizeGeneratedText(item.detail, uiLanguage)}</div>
                                  </div>
                                  <span className="shrink-0 rounded-md border border-subtle px-1.5 py-0.5 text-[11px] text-secondary-text">
                                    {basicWatchPriorityLabel(item.priority, uiLanguage)}
                                  </span>
                                </div>
                              </div>
                            ))}
                          </div>
                        </div>
                        <div className="min-w-0 rounded-lg border border-subtle bg-surface/35 p-3">
                          <div className="text-sm font-semibold text-foreground">
                            {uiLanguage === 'en' ? 'Compare with' : '对比参照'}
                          </div>
                          <div className="mt-2 flex min-w-0 flex-wrap gap-1.5">
                            {(basicSnapshot.intelligence?.comparisonTargets ?? []).map((item) => (
                              <span
                                key={`${item.symbol}-${item.label}`}
                                className="max-w-full rounded-md border border-subtle/80 px-2 py-1 text-[11px] text-secondary-text"
                                title={localizeGeneratedText(item.reason, uiLanguage)}
                              >
                                <span className="font-medium text-foreground">{item.symbol}</span>
                                <span className="ml-1">{localizeGeneratedText(item.label, uiLanguage)}</span>
                              </span>
                            ))}
                          </div>
                          <div className="mt-3 text-[11px] leading-relaxed text-secondary-text">
                            {uiLanguage === 'en'
                              ? 'Reference targets are route-based hints; realtime comparison values are reserved for a later deep view.'
                              : '对比对象是基于市场通道的参考提示；实时对比数值留给后续深度视图。'}
                          </div>
                        </div>
                      </div>
                    ) : null}
                    <div
                      data-testid="basic-query-product-brief"
                      className="mb-3 grid gap-2 md:grid-cols-2 xl:grid-cols-5"
                    >
                      <div className="min-w-0 rounded-lg border border-primary/35 bg-background/45 p-3 xl:col-span-2">
                        <div className="text-xs font-medium text-primary">
                          {uiLanguage === 'en' ? 'Key conclusion' : '关键结论'}
                        </div>
                        <div className="mt-1 text-sm font-semibold leading-snug text-foreground">
                          {localizeGeneratedText(basicFreeReport.productBrief.conclusion, uiLanguage)}
                        </div>
                        <div className="mt-2 flex flex-wrap gap-1.5 text-[11px] text-secondary-text">
                          <span className="rounded-md border border-primary/30 px-1.5 py-0.5">{t('home.noAi')}</span>
                          <span className="rounded-md border border-subtle/70 px-1.5 py-0.5">
                            {localizeGeneratedSource(basicSnapshot.quote.source, uiLanguage)}
                          </span>
                        </div>
                      </div>
                      <div className="min-w-0 rounded-lg border border-subtle bg-background/35 p-3">
                        <div className="text-xs text-secondary-text">
                          {uiLanguage === 'en' ? 'Support / resistance' : '支撑 / 压力'}
                        </div>
                        <div className="mt-2 space-y-1 text-sm font-medium text-foreground">
                          <div className="truncate">
                            {uiLanguage === 'en' ? 'Support' : '支撑'} {localizeGeneratedText(basicFreeReport.productBrief.supportLevels, uiLanguage)}
                          </div>
                          <div className="truncate">
                            {uiLanguage === 'en' ? 'Resistance' : '压力'} {localizeGeneratedText(basicFreeReport.productBrief.pressureLevels, uiLanguage)}
                          </div>
                        </div>
                      </div>
                      <div className="min-w-0 rounded-lg border border-subtle bg-background/35 p-3">
                        <div className="text-xs text-secondary-text">
                          {uiLanguage === 'en' ? 'Short / medium term' : '短线 / 中线'}
                        </div>
                        <div className="mt-2 space-y-1 text-sm font-medium text-foreground">
                          <div className="truncate">
                            {uiLanguage === 'en' ? 'Short' : '短线'} {localizeGeneratedText(basicFreeReport.productBrief.shortStatus, uiLanguage)}
                          </div>
                          <div className="truncate">
                            {uiLanguage === 'en' ? 'Medium' : '中线'} {localizeGeneratedText(basicFreeReport.productBrief.midStatus, uiLanguage)}
                          </div>
                        </div>
                      </div>
                      <div className="min-w-0 rounded-lg border border-subtle bg-background/35 p-3">
                        <div className="text-xs text-secondary-text">
                          {uiLanguage === 'en' ? 'Risk boundary' : '风险边界'}
                        </div>
                        <div className="mt-2 flex min-w-0 flex-wrap gap-1.5 text-[11px] text-secondary-text">
                          {basicFreeReport.productBrief.risks.slice(0, 3).map((risk) => (
                            <span key={risk} className="max-w-full truncate rounded-md border border-subtle/70 px-1.5 py-0.5">
                              {localizeGeneratedText(risk, uiLanguage)}
                            </span>
                          ))}
                        </div>
                      </div>
                      <div className="min-w-0 rounded-lg border border-primary/25 bg-primary/10 p-3 md:col-span-2 xl:col-span-5">
                        <div className="flex min-w-0 flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                          <div className="min-w-0">
                            <div className="text-xs font-medium text-primary">
                              {uiLanguage === 'en' ? 'Continue with deep analysis' : '继续深度分析'}
                            </div>
                            <div className="mt-1 text-xs leading-relaxed text-secondary-text">
                              {basicFreeReport.productBrief.upgradeText}
                            </div>
                          </div>
                          <Button
                            type="button"
                            variant="secondary"
                            size="sm"
                            disabled={isAnalyzing}
                            onClick={() => handleSubmitAnalysis(basicSnapshot.stockCode, basicSnapshot.stockName || undefined, 'manual', 'deep')}
                          >
                            <SlidersHorizontal className="h-4 w-4" aria-hidden="true" />
                            {uiLanguage === 'en' ? 'Deep analysis' : '深度分析'}
                          </Button>
                        </div>
                      </div>
                    </div>
                    <div className="grid gap-2 md:grid-cols-2 xl:grid-cols-5">
                      {basicFreeReport.cards.map((card) => (
                        <div key={card.title} className="min-w-0 rounded-lg border border-subtle bg-background/35 p-3">
                          <div className="text-xs text-secondary-text">{card.title}</div>
                          <div className="mt-1 min-h-[2.5rem] text-sm font-semibold leading-snug text-foreground">
                            {card.headline}
                          </div>
                          <div className="mt-2 flex min-w-0 flex-wrap gap-1.5 text-[11px] text-secondary-text">
                            {card.details.map((detail) => (
                              <span key={detail} className="max-w-full truncate rounded-md border border-subtle/70 px-1.5 py-0.5">
                                {detail}
                              </span>
                            ))}
                          </div>
                        </div>
                      ))}
                    </div>
                  </section>
                ) : null}
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
                {basicSnapshot.profile ? (
                  <section
                    data-testid="basic-query-company-profile"
                    className="mb-4 min-w-0 rounded-lg border border-subtle bg-background/25 p-3"
                  >
                    <div className="mb-3 flex min-w-0 flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                      <h3 className="text-sm font-semibold text-foreground">
                        {uiLanguage === 'en' ? 'Company profile' : '公司资料'}
                      </h3>
                      <div className="flex min-w-0 flex-wrap gap-2 text-xs text-secondary-text">
                        <span className="rounded-md border border-subtle px-2 py-1">
                          {localizeGeneratedSource(basicSnapshot.profile.source, uiLanguage)}
                        </span>
                        <span className="rounded-md border border-subtle px-2 py-1">
                          {localizeRuntimeLabel(basicSnapshot.profile.freshness, uiLanguage)}
                        </span>
                        <span className="rounded-md border border-primary/40 bg-primary/10 px-2 py-1 text-primary">
                          {t('home.noAi')}
                        </span>
                      </div>
                    </div>
                    <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
                      {basicProfileDetailItems.map((item) => (
                        <div key={item.label} className="min-w-0 rounded-md border border-subtle/70 px-3 py-2">
                          <div className="text-xs text-secondary-text">{item.label}</div>
                          <div className="mt-1 truncate text-sm font-medium text-foreground">{item.value}</div>
                        </div>
                      ))}
                    </div>
                    {basicSnapshot.profile.website ? (
                      <div className="mt-2 truncate text-xs text-secondary-text">
                        {uiLanguage === 'en' ? 'Website' : '官网'}: {basicSnapshot.profile.website}
                      </div>
                    ) : null}
                  </section>
                ) : null}
                <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                  <div className="min-w-0">
                    <div className="mb-2 flex flex-wrap items-center gap-2 text-xs text-secondary-text">
                      <span className="rounded-md border border-subtle px-2 py-1">{t('home.basicSnapshotTitle')}</span>
                      <span className="rounded-md border border-subtle px-2 py-1">{basicSnapshot.market.toUpperCase()}</span>
                      <span className="rounded-md border border-subtle px-2 py-1">{localizeRuntimeLabel(basicSnapshot.quote.freshness, uiLanguage)}</span>
                      <span className="rounded-md border border-primary/40 bg-primary/10 px-2 py-1 text-primary">{t('home.noAi')}</span>
                    </div>
                    <div
                      data-testid="basic-query-user-guardrails"
                      className="mb-2 flex flex-wrap items-center gap-2 text-xs text-secondary-text"
                    >
                      <span className="rounded-md border border-subtle px-2 py-1">
                        {uiLanguage === 'en' ? 'Current quick snapshot' : '当前快速快照'}
                      </span>
                      <span className="rounded-md border border-subtle px-2 py-1">
                        {basicSnapshot.aiUsed ? localizeRuntimeLabel('AI used', uiLanguage) : t('home.noAi')}
                      </span>
                      <span className="rounded-md border border-subtle px-2 py-1">{marketLaneLabel(basicSnapshotLane, uiLanguage)}</span>
                      <span className="rounded-md border border-subtle px-2 py-1">
                        {uiLanguage === 'en' ? 'Historical reports stay separate' : '历史报告单独保留'}
                      </span>
                      {basicSnapshotCacheMode ? (
                        <span className="rounded-md border border-subtle px-2 py-1">
                          {uiLanguage === 'en'
                            ? `Cache ${String(basicSnapshotCacheMode)}`
                            : `缓存 ${localizeRuntimeLabel(basicSnapshotCacheMode, uiLanguage)}`}
                        </span>
                      ) : null}
                    </div>
                    <div
                      data-testid="basic-query-workspace-lanes"
                      className="mb-3 grid min-w-0 gap-2 border-y border-subtle py-2 text-xs text-secondary-text sm:grid-cols-2 lg:grid-cols-4"
                    >
                      <div className="min-w-0">
                        <div className="font-medium text-foreground">{uiLanguage === 'en' ? 'Current Snapshot' : '当前快照'}</div>
                        <div className="mt-1 flex min-w-0 flex-wrap gap-1">
                          <span className="rounded-md border border-subtle px-1.5 py-0.5">{basicSnapshot.aiUsed ? localizeRuntimeLabel('AI used', uiLanguage) : t('home.noAi')}</span>
                          <span className="rounded-md border border-subtle px-1.5 py-0.5">{marketLaneLabel(basicSnapshotLane, uiLanguage)}</span>
                        </div>
                      </div>
                      <div className="min-w-0">
                        <div className="font-medium text-foreground">{uiLanguage === 'en' ? 'Watchlist' : '自选'}</div>
                        <div className="mt-1 flex min-w-0 flex-wrap gap-1">
                          <span className="rounded-md border border-subtle px-1.5 py-0.5">
                            {uiLanguage === 'en' ? `${platformWatchlistCount} symbols` : `${platformWatchlistCount} 只标的`}
                          </span>
                          <span className="rounded-md border border-subtle px-1.5 py-0.5">{localizeRuntimeLabel('private', uiLanguage)}</span>
                        </div>
                      </div>
                      <div className="min-w-0">
                        <div className="font-medium text-foreground">{uiLanguage === 'en' ? 'History Reports' : '历史报告'}</div>
                        <div className="mt-1 flex min-w-0 flex-wrap gap-1">
                          <span className="rounded-md border border-subtle px-1.5 py-0.5">{workspaceHistoryCountText}</span>
                          <span className="rounded-md border border-subtle px-1.5 py-0.5">{localizeRuntimeLabel('separate', uiLanguage)}</span>
                        </div>
                      </div>
                      <div className="min-w-0">
                        <div className="font-medium text-foreground">{uiLanguage === 'en' ? 'AI Analysis' : 'AI 分析'}</div>
                        <div className="mt-1 flex min-w-0 flex-wrap gap-1">
                          <span className="rounded-md border border-subtle px-1.5 py-0.5">{workspaceAiModeText}</span>
                          <span className="rounded-md border border-subtle px-1.5 py-0.5">{workspaceByokText}</span>
                        </div>
                      </div>
                    </div>
                    {platformSession ? (
                      <div
                        data-testid="basic-query-retention-mode-guide"
                        className="mb-3 rounded-lg border border-primary/30 bg-primary/5 p-3 text-xs text-secondary-text"
                      >
                        <div className="flex flex-wrap items-center gap-2">
                          <span className="rounded-md border border-primary/40 bg-primary/10 px-2 py-1 font-medium text-primary">
                            {uiLanguage === 'en' ? `Free no-AI ${basicQuotaText}` : `免费查询 ${basicQuotaText}`}
                          </span>
                          <span className="rounded-md border border-subtle px-2 py-1">
                            {uiLanguage === 'en' ? `Platform API quick AI ${platformAiQuotaText}` : `平台 API 快速 AI ${platformAiQuotaText}`}
                          </span>
                          <span className="rounded-md border border-subtle px-2 py-1">
                            {uiLanguage === 'en' ? `BYOK ${byokStatusText}; quick bucket ${byokAiQuotaText}` : `BYOK ${byokStatusText}；快速额度 ${byokAiQuotaText}`}
                          </span>
                          <span className="rounded-md border border-subtle px-2 py-1">
                            {uiLanguage === 'en' ? `Local model ${localModelQuotaText}` : `本地模型 ${localModelQuotaText}`}
                          </span>
                          <span className="rounded-md border border-subtle px-2 py-1">
                            {uiLanguage === 'en' ? 'Informational only; not investment advice' : '仅作信息分析，不构成投资建议'}
                          </span>
                        </div>
                        <div className="mt-3 flex min-w-0 flex-wrap items-center gap-2">
                          <div className="inline-flex overflow-hidden rounded-lg border border-subtle">
                            <button
                              type="button"
                              onClick={() => handleApiKeyModeChange('platform')}
                              data-testid="platform-mode-platform"
                              className={`px-2.5 py-1 ${apiKeyMode === 'platform' ? 'bg-primary text-primary-foreground' : 'bg-surface text-secondary-text hover:text-foreground'}`}
                            >
                              {uiLanguage === 'en' ? 'Platform API' : '平台 API'}
                            </button>
                            <button
                              type="button"
                              disabled={!hasUserApiKey}
                              onClick={() => handleApiKeyModeChange('user')}
                              data-testid="platform-mode-user"
                              className={`px-2.5 py-1 disabled:cursor-not-allowed disabled:opacity-50 ${apiKeyMode === 'user' ? 'bg-primary text-primary-foreground' : 'bg-surface text-secondary-text hover:text-foreground'}`}
                            >
                              BYOK
                            </button>
                            <button
                              type="button"
                              onClick={() => handleApiKeyModeChange('local')}
                              data-testid="platform-mode-local"
                              className={`px-2.5 py-1 ${apiKeyMode === 'local' ? 'bg-primary text-primary-foreground' : 'bg-surface text-secondary-text hover:text-foreground'}`}
                            >
                              {uiLanguage === 'en' ? 'Local model' : '本地模型'}
                            </button>
                          </div>
                          <Button
                            type="button"
                            variant="secondary"
                            size="sm"
                            data-testid="basic-query-save-current-history"
                            isLoading={basicRetentionBusy}
                            disabled={!basicSnapshot || basicSnapshot.aiUsed || basicRetentionBusy}
                            onClick={() => void handleSaveCurrentBasicSnapshotToHistory()}
                          >
                            <Save className="h-4 w-4" aria-hidden="true" />
                            {uiLanguage === 'en' ? 'Save to history' : '保存到历史'}
                          </Button>
                          <Button
                            type="button"
                            variant="secondary"
                            size="sm"
                            data-testid="basic-query-add-current-watchlist"
                            isLoading={platformWatchlistBusy}
                            disabled={!basicSnapshot || platformWatchlistBusy}
                            onClick={() => void handleAddCurrentQueryToPlatformWatchlist()}
                          >
                            <Plus className="h-4 w-4" aria-hidden="true" />
                            {uiLanguage === 'en' ? 'Add to watchlist' : '加入自选'}
                          </Button>
                          <Button type="button" variant="secondary" size="sm" onClick={() => void handlePlatformLogout()} data-testid="platform-logout-button">
                            <LogOut className="h-4 w-4" aria-hidden="true" />
                            {uiLanguage === 'en' ? 'Logout' : '退出登录'}
                          </Button>
                          {basicRetentionStatus ? (
                            <span data-testid="basic-query-retention-status" className="text-xs font-medium text-success">
                              {basicRetentionStatus}
                            </span>
                          ) : null}
                          {basicRetentionError ? (
                            <span data-testid="basic-query-retention-status" className="text-xs font-medium text-danger">
                              {basicRetentionError}
                            </span>
                          ) : null}
                        </div>
                      </div>
                    ) : null}
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
                  {t('home.basicSource')}: {localizeGeneratedSource(basicSnapshot.quote.source, uiLanguage)}
                  {basicSnapshot.route ? (
                    <span data-testid="basic-query-route" className="ml-2">
                      {uiLanguage === 'en' ? 'Lane' : '通道'}: {marketLaneLabel(basicSnapshot.route.dataSourceLane, uiLanguage)} / {basicSnapshot.route.channel}
                    </span>
                  ) : null}
                </div>
                {basicSnapshot.diagnostics ? (
                  <div data-testid="basic-query-diagnostics" className="mt-2 flex flex-wrap gap-2 text-xs text-secondary-text">
                    <span className="rounded-md border border-subtle px-2 py-1">
                      {t('home.basicDiagnostics')}: {formatBasicNumber(basicSnapshot.diagnostics.elapsedMs)}ms
                    </span>
                    <span className="rounded-md border border-subtle px-2 py-1">
                      {t('home.basicCache')}: Q {localizeRuntimeLabel(basicSnapshot.diagnostics.cache.quote || '-', uiLanguage)} / H {localizeRuntimeLabel(basicSnapshot.diagnostics.cache.history || '-', uiLanguage)}
                    </span>
                    <span className="rounded-md border border-subtle px-2 py-1">
                      {t('home.basicFallback')}: Q {localizeRuntimeLabel(basicSnapshot.diagnostics.fallback?.quote || '-', uiLanguage)} / H {localizeRuntimeLabel(basicSnapshot.diagnostics.fallback?.history || '-', uiLanguage)}
                    </span>
                    <span className="rounded-md border border-subtle px-2 py-1">
                      {t('home.basicSourceHealth')}: Q {localizeRuntimeLabel(basicSnapshot.diagnostics.sourceHealth?.quote?.status || '-', uiLanguage)} / H {localizeRuntimeLabel(basicSnapshot.diagnostics.sourceHealth?.history?.status || '-', uiLanguage)}
                    </span>
                    <span className="rounded-md border border-subtle px-2 py-1">
                      {t('home.basicPersistentCache')}: Q {localizeRuntimeLabel(basicSnapshot.diagnostics.persistentCache?.quote || '-', uiLanguage)} / H {localizeRuntimeLabel(basicSnapshot.diagnostics.persistentCache?.history || '-', uiLanguage)}
                    </span>
                    {basicSnapshot.diagnostics.refresh ? (
                      <span className="rounded-md border border-subtle px-2 py-1">
                        {uiLanguage === 'en' ? 'Refresh' : '刷新'}: {localizeRuntimeLabel(basicSnapshot.diagnostics.refresh.mode || '-', uiLanguage)}
                      </span>
                    ) : null}
                    <span className="rounded-md border border-subtle px-2 py-1">
                      {t('home.basicPerformance')}: {localizeRuntimeLabel(basicSnapshot.diagnostics.performance.status || '-', uiLanguage)}
                    </span>
                  </div>
                ) : null}
                {basicSnapshot.degradation && basicSnapshot.degradation.status !== 'ok' ? (
                  <div
                    data-testid="basic-query-degradation"
                    role="alert"
                    className="mt-3 rounded-lg border border-warning/40 bg-warning/10 px-3 py-2 text-sm text-foreground"
                  >
                    <div className="font-medium">{localizeGeneratedText(basicSnapshot.degradation.message, uiLanguage)}</div>
                    {basicSnapshot.warnings?.length ? (
                      <ul className="mt-1 space-y-1 text-xs text-secondary-text">
                        {basicSnapshot.warnings.map((warning) => (
                          <li key={`${warning.code}-${warning.message}`}>
                            {localizeRuntimeLabel(warning.code, uiLanguage)}: {localizeGeneratedText(warning.message, uiLanguage)}
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
                            {uiLanguage === 'en' ? 'Prev' : '上一个'}
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
                            {uiLanguage === 'en' ? 'Next' : '下一个'}
                          </button>
                          {activeHistoryReportMatch && historyReportSearch.trim() ? (
                            <span data-testid="history-report-search-hit" className="min-w-0 flex-1 text-secondary-text">
                              {activeHistoryReportMatch.label}: {buildHistoryReportMatchSnippet(activeHistoryReportMatch.text, historyReportSearch.trim())}
                            </span>
                          ) : (
                            <span data-testid="history-report-search-hit" className="text-muted-text">
                              {uiLanguage === 'en' ? 'No match' : '无匹配'}
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
                                  {isCurrent ? (uiLanguage === 'en' ? 'Current' : '当前') : historyTimelineDate(item.createdAt)}
                                </span>
                                <span className="block truncate">
                                  {item.stockCode} - {item.reportType || (uiLanguage === 'en' ? 'report' : '报告')}
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
                      {uiLanguage === 'en' ? 'Favorite' : '收藏'}
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
                      {uiLanguage === 'en' ? 'Important' : '重要'}
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
                      {selectedHistoryState.read
                        ? (uiLanguage === 'en' ? 'Read' : '已读')
                        : (uiLanguage === 'en' ? 'Unread' : '未读')}
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
                      {selectedHistoryState.archived
                        ? (uiLanguage === 'en' ? 'Restore' : '恢复')
                        : (uiLanguage === 'en' ? 'Archive' : '归档')}
                    </Button>
                  </div>
                  <div className="mt-3 flex flex-col gap-2 sm:flex-row sm:items-start">
                    <label className="min-w-0 flex-1">
                      <span className="sr-only">{uiLanguage === 'en' ? 'Local history note' : '本地历史备注'}</span>
                      <textarea
                        value={historyStateNoteDraft}
                        onChange={(event) => setHistoryStateNoteDraft(event.target.value)}
                        data-testid="history-state-note-input"
                        maxLength={1000}
                        rows={2}
                        placeholder={uiLanguage === 'en' ? 'Local note for this historical report' : '给这份历史报告添加本地备注'}
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
