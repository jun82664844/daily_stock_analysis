import type React from 'react';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Archive, ArchiveRestore, BarChart3, Check, Download, Eye, Flag, KeyRound, LogOut, MailCheck, Plus, RefreshCw, Save, Search, SlidersHorizontal, Sparkles, Star, UserRound } from 'lucide-react';
import { useLocation, useNavigate } from 'react-router-dom';
import { getParsedApiError, type ParsedApiError } from '../api/error';
import { analysisApi } from '../api/analysis';
import { historyApi } from '../api/history';
import { platformApi, type PlatformAccountSummary, type PlatformApiKeyItem, type PlatformAuthPayload, type PlatformQuota, type PlatformWatchlistRefreshResponse, type PlatformWatchlistResponse } from '../api/platform';
import { stocksApi, type BasicSnapshotOptions, type BasicStockSnapshot, type KronosForecastResponse } from '../api/stocks';
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
  fresh: '新鲜',
  stale: '过期',
  cached: '缓存',
  unknown: '未知',
  'Local news center': '本地资讯中心',
  'A-share enrichment': 'A股增强数据',
  'A-share quick reference': 'A股快速参考数据',
  'Market-moving news lane': '影响行情的资讯通道',
  'Announcements lane': '公告通道',
  'SEC filings lane': 'SEC 文件通道',
  'Financial snapshot lane': '财务快照通道',
  'Sector and peer lane': '板块与同业通道',
  'Data quality lane': '数据质量通道',
  'Announcements channel': '公告通道',
  'Fund-flow channel': '资金流通道',
  'Sector channel': '板块通道',
  'Research channel': '研报通道',
  'Dragon-tiger channel': '龙虎榜通道',
  'Price structure': '价格结构',
  'Volume activity': '量价活跃度',
  'Valuation snapshot': '估值快照',
  'Trend windows': '周期趋势',
  'Data quality': '数据质量',
  'Premium news': '高级 API 源',
  'BYOK or local model': '我的 API 或本地模型',
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
  'Nasdaq Composite': '纳斯达克综合指数',
  'Technology sector ETF': '科技行业 ETF',
  'Hang Seng Index': '恒生指数',
  'Tracker Fund': '盈富基金',
  'Tracker Fund of Hong Kong': '盈富基金',
  Ethereum: '以太坊',
  Bitcoin: '比特币',
  'Index lens': '指数参照',
  'Sector lens': '行业参照',
  'Peer asset': '同类资产',
  'Crypto benchmark': '加密参照',
  'Crypto beta': '加密参照',
  'Hong Kong market reference.': '香港市场参照。',
  'Hong Kong ETF market context.': '香港 ETF 市场参照。',
  'Crypto market beta reference.': '加密市场贝塔参照。',
  'Large-cap crypto rotation reference.': '大市值加密资产轮动参照。',
  'US market index context.': '美股指数参照。',
  'Sector context for Technology names.': '科技股行业参照。',
  'HKEX filings lane': '港交所公告通道',
  'Protocol and exchange events': '协议与交易所事件',
  'Hong Kong filings and corporate actions are reserved for configured deep sources. Free mode shows the lane without public search calls.': '港股公告和公司行动保留给已配置的深度数据源；免费模式展示该通道，但不发起公共搜索。',
  'Company profile exists, but key valuation and financial fields are unavailable in quick mode.': '公司资料存在，但快速模式暂未提供关键估值和财务字段。',
  'Equity financial statements do not apply to crypto assets; use trend, liquidity, and risk-event context instead.': '加密资产不适用股票财务报表；请改用趋势、流动性和风险事件背景。',
  'Equity filings do not apply to crypto. Free mode keeps an event lane for exchange notices, protocol risk, liquidity shifts, and regulatory headlines when configured.': '加密资产不适用股票公告；免费模式保留交易所通知、协议风险、流动性变化和监管新闻通道，待配置后使用。',
  'CSI 300': '沪深300',
  'SSE Composite': '上证指数',
  'Profile context': '资料背景',
  'A-share broad-market reference.': 'A股大盘参照。',
  'A-share market sentiment reference.': 'A股市场情绪参照。',
  Technology: '科技',
  'Consumer Electronics': '消费电子',
  'Technology / Consumer Electronics': '科技 / 消费电子',
  'United States': '美国',
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
  capital_flow: '资金流',
  research: '研报',
  dragon_tiger: '龙虎榜',
  price_structure: '价格结构',
  volume_activity: '量价活跃度',
  valuation_snapshot: '估值快照',
  trend_windows: '周期趋势',
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
  a_stock_data_poc_adapter: 'A股增强适配器',
  a_stock_data_poc_local_rules: 'A股本地增强规则',
  a_stock_data_cninfo_or_f10: '公告/F10来源',
  a_stock_data_eastmoney_fund_flow: '东财资金流',
  a_stock_data_eastmoney_concept_blocks: '东财概念板块',
  a_stock_data_eastmoney_reportapi: '东财研报',
  a_stock_data_eastmoney_datacenter: '东财数据中心',
  basic_quote_snapshot: '基础行情快照',
  basic_indicator_snapshot: '基础指标快照',
  basic_profile_snapshot: '基础资料快照',
  basic_data_quality_snapshot: '基础数据质量',
  local_kline_rules_kronos_ready: '本地K线规则',
  local_kline_rules_kronos_unavailable: '本地K线规则兜底',
  local_kline_rules_kronos_error: '本地K线错误兜底',
  kronos_model_local: '本地Kronos模型',
  a_share_market_data: 'A股行情数据',
  us_market_data: '美股行情数据',
  hk_market_data: '港股行情数据',
  crypto_market_data: '加密货币行情数据',
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
  a_share: 'A股',
  'hk equity': '港股',
  'crypto spot': '加密货币现货',
  'with incomplete MA20 context': 'MA20 背景不完整',
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

  let match = text.match(/^(.+?) quick reference uses quote, moving-average, volume, valuation, and freshness data\. External announcements, fund-flow, research, and dragon-tiger seats are not enabled in free quick mode\.$/);
  if (match) return `${match[1]} 快速参考使用行情、均线、量价、估值和数据新鲜度；免费快速模式暂未启用实时公告、资金流、研报和龙虎榜席位明细。`;
  match = text.match(/^Latest ([^,]+), change ([^,]+), open ([^,]+), high ([^,]+), low ([^;]+); price is (above|below) MA20 (.+?)\.$/);
  if (match) return `最新价 ${match[1]}，涨跌幅 ${match[2]}，开盘 ${match[3]}，最高 ${match[4]}，最低 ${match[5]}；价格${match[6] === 'above' ? '高于' : '低于'} MA20 ${match[7]}。`;
  match = text.match(/^Latest ([^,]+), change ([^,]+), open ([^,]+), high ([^,]+), low ([^;]+); MA20 context is incomplete\.$/);
  if (match) return `最新价 ${match[1]}，涨跌幅 ${match[2]}，开盘 ${match[3]}，最高 ${match[4]}，最低 ${match[5]}；MA20 背景暂不完整。`;
  match = text.match(/^Volume ([^,]+), amount ([^;]+); volume is (.+?) versus MA5\.$/);
  if (match) return `成交量 ${match[1]}，成交额 ${match[2]}；成交量相对 MA5 为 ${match[3]}。`;
  match = text.match(/^Volume ([^,]+), amount ([^;]+); volume versus MA5 is incomplete\.$/);
  if (match) return `成交量 ${match[1]}，成交额 ${match[2]}；成交量相对 MA5 暂不完整。`;
  match = text.match(/^Market cap ([^;]+); PE ([^;]+); PB ([^;]+); dividend yield ([^;]+); revenue ([^;]+); net profit (.+?)\.?$/);
  if (match) return `市值 ${match[1]}；市盈率 ${match[2]}；市净率 ${match[3]}；股息率 ${match[4]}；营收 ${match[5]}；净利润 ${match[6]}。`;
  match = text.match(/^Market cap ([^;]+); PE ([^;]+); PB (.+?)\.$/);
  if (match) return `市值 ${match[1]}；市盈率 ${match[2]}；市净率 ${match[3]}。`;
  match = text.match(/^Valuation fields are not available in the free quick snapshot\.$/);
  if (match) return '免费快速快照暂未取得估值字段。';
  match = text.match(/^5-day change ([^;]+); 20-day change ([^;]+); MA5 ([^,]+), MA10 ([^,]+), MA20 ([^;]+); last close (.+?)\.$/);
  if (match) return `5日涨跌 ${match[1]}；20日涨跌 ${match[2]}；MA5 ${match[3]}，MA10 ${match[4]}，MA20 ${match[5]}；最近收盘 ${match[6]}。`;
  match = text.match(/^Quote freshness ([^;]+); profile freshness ([^;]+); quote source (.+?)\.$/);
  if (match) return `行情新鲜度 ${localizeGeneratedStatus(match[1], language)}；资料新鲜度 ${localizeGeneratedStatus(match[2], language)}；行情来源 ${localizeGeneratedSource(match[3], language)}。`;
  match = text.match(/^Use this as a first-pass structure check for (.+?); refresh stale quotes before comparing intraday moves\.$/);
  if (match) return `先把它作为 ${match[1]} 的第一层结构检查；对比日内波动前先刷新过期行情。`;
  match = text.match(/^Use volume only as confirmation; price and source freshness come first\.$/);
  if (match) return '成交量只作为确认项；优先看价格位置和数据来源新鲜度。';
  match = text.match(/^Use valuation as context, not as a timing signal\.$/);
  if (match) return '估值只作为背景参考，不作为短线时点信号。';
  match = text.match(/^Compare short-window moves with MA20 before reading the trend as repaired\.$/);
  if (match) return '先把短周期涨跌与 MA20 对照，再判断趋势是否修复。';
  match = text.match(/^Treat stale or cached data as provisional and refresh before acting on changes\.$/);
  if (match) return '过期或缓存数据只作临时参考，解读变化前请先刷新。';
  match = text.match(/^Premium can add live announcements, fund-flow history, research PDFs, sector linkage, and dragon-tiger seat details\.$/);
  if (match) return '免费版展示同样A股增强入口并使用网络/本地公开源；高级版使用 API 获取实时公告、资金流历史、研报 PDF、板块联动和龙虎榜席位明细。';
  match = text.match(/^(.+?) has no usable sector tags yet; later versions can add Eastmoney concepts and industry mapping\.$/);
  if (match) return `${match[1]} 暂无可用板块标签；可切换数据源或刷新公司资料后再做同类股对比。`;
  match = text.match(/^Refresh profile data or enable sector sources before comparing peers\.$/);
  if (match) return '缺少板块标签时，先用行情、估值和公告通道做基础判断，不要直接做同业强弱结论。';
  match = text.match(/^(.+?) keeps a reserved CNINFO \/ TDX F10 announcements lane; quick mode shows the checklist entry only\.$/);
  if (match) return `${match[1]} 已预留公告通道；快速模式只展示检查清单，深度模式可展开公告原文和来源链接。`;
  match = text.match(/^(.+?) keeps a reserved Eastmoney fund-flow lane\. Current change is (.+?)\.$/);
  if (match) return `${match[1]} 已预留东方财富资金流通道；当前涨跌幅 ${match[2]}。`;
  match = text.match(/^(.+?) keeps a reserved Eastmoney fund-flow lane\.$/);
  if (match) return `${match[1]} 已预留东方财富资金流通道。`;
  match = text.match(/^(.+?) keeps a reserved Eastmoney \/ iFinD research lane; free quick mode does not fetch PDFs\.$/);
  if (match) return `${match[1]} 已预留研报通道；免费快速模式不拉取 PDF。`;
  match = text.match(/^(.+?) keeps a reserved dragon-tiger seat lane; seat details are not fetched in quick mode\.$/);
  if (match) return `${match[1]} 已预留龙虎榜席位通道；快速模式不拉取席位明细。`;
  match = text.match(/^Deep mode can fetch research sources by symbol and industry\.$/);
  if (match) return '深度模式可按代码和行业拉取研报来源。';
  match = text.match(/^Fetch seat details only after unusual moves or limit-up events to reduce source pressure\.$/);
  if (match) return '出现异动或涨跌停后再拉取席位明细，减少数据源压力。';

  match = text.match(/^(.+?) signal is ([0-9.]+)\/100 from trend, volume, data freshness, and profile completeness\. No AI or public search was used\.$/);
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
  match = text.match(/^Trend score is limited because latest price or MA20 is unavailable\.$/);
  if (match) return '最新价或 MA20 缺失，趋势评分受限。';
  match = text.match(/^Quote data is fresh for this quick snapshot\. (.+?) historical source timed out; moving averages may be incomplete\.$/);
  if (match) return `本次快速快照使用新鲜行情数据。${localizeGeneratedTerms(match[1], language)} 历史数据源超时，均线可能不完整。`;
  match = text.match(/^Quote data is fresh for this quick snapshot\. (.+?) historical source is cooling down after repeated failures; moving averages may be incomplete\.$/);
  if (match) return `本次快速快照使用新鲜行情数据。${localizeGeneratedTerms(match[1], language)} 历史数据源连续失败后暂时冷却，均线可能不完整。`;
  match = text.match(/^Quote data is fresh for this quick snapshot\. (.+?) historical bars are unavailable; moving averages may be incomplete\.$/);
  if (match) return `本次快速快照使用新鲜行情数据。${localizeGeneratedTerms(match[1], language)} 历史K线暂不可用，均线可能不完整。`;
  match = text.match(/^Quote data is fresh for this quick snapshot\.$/);
  if (match) return '本次快速快照使用的是新鲜行情数据。';
  match = text.match(/^Resolve data warning first: (.+?) historical source timed out; moving averages may be incomplete\.?$/);
  if (match) return `先处理数据警示：${localizeGeneratedTerms(match[1], language)} 历史数据源超时，均线可能不完整。`;
  match = text.match(/^Resolve data warning first: (.+?) historical source is cooling down after repeated failures; moving averages may be incomplete\.?$/);
  if (match) return `先处理数据警示：${localizeGeneratedTerms(match[1], language)} 历史数据源连续失败后暂时冷却，均线可能不完整。`;
  match = text.match(/^Resolve data warning first: (.+?) historical bars are unavailable; moving averages may be incomplete\.?$/);
  if (match) return `先处理数据警示：${localizeGeneratedTerms(match[1], language)} 历史K线暂不可用，均线可能不完整。`;
  match = text.match(/^(.+?) historical source timed out; moving averages may be incomplete\.$/);
  if (match) return `${localizeGeneratedTerms(match[1], language)} 历史数据源超时，均线可能不完整。`;
  match = text.match(/^(.+?) historical source is cooling down after repeated failures; moving averages may be incomplete\.$/);
  if (match) return `${localizeGeneratedTerms(match[1], language)} 历史数据源连续失败后暂时冷却，均线可能不完整。`;
  match = text.match(/^(.+?) historical bars are unavailable; moving averages may be incomplete\.$/);
  if (match) return `${localizeGeneratedTerms(match[1], language)} 历史K线暂不可用，均线可能不完整。`;
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
  match = text.match(/^(.+?) quick read: ([^,]+), with incomplete MA20 context\.?$/);
  if (match) return `${match[1]} 快速解读：${match[2]}，MA20 背景不完整。`;
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
  match = text.match(/^Refresh once before market action and confirm whether price stays with incomplete MA20 context\.?$/);
  if (match) return '先刷新一次行情；当前 MA20 背景不完整，确认后再解读价格位置。';
  match = text.match(/^Resolve data warning first: (.+?) historical source timed out; moving averages may be incomplete\.?$/);
  if (match) return `先处理数据警示：${localizeGeneratedTerms(match[1], language)} 历史数据源超时，均线可能不完整。`;
  match = text.match(/^Resolve data warning first: (.+?) historical source is cooling down after repeated failures; moving averages may be incomplete\.?$/);
  if (match) return `先处理数据警示：${localizeGeneratedTerms(match[1], language)} 历史数据源连续失败后暂时冷却，均线可能不完整。`;
  match = text.match(/^Resolve data warning first: (.+?) historical bars are unavailable; moving averages may be incomplete\.?$/);
  if (match) return `先处理数据警示：${localizeGeneratedTerms(match[1], language)} 历史K线暂不可用，均线可能不完整。`;
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
  match = text.match(/^(.+?) A-share enrichment for announcements, fund flow, sectors, research, and dragon-tiger data (is available through the local POC lane|is degraded through local rules)\.(?: Context: (.+?)\.)?(?: Last price (.+?)(?:, change (.+?))?)?$/);
  if (match) {
    const statusText = match[2] === 'is available through the local POC lane' ? '已接入本地 POC 通道' : '以本地规则降级展示';
    const contextText = match[3] ? `；背景：${localizeGeneratedTerms(match[3], language)}` : '';
    const priceText = match[4] ? `；最新价 ${match[4]}${match[5] ? `，涨跌幅 ${match[5]}` : ''}` : '';
    return `${match[1]} 的公告、资金流、板块、研报和龙虎榜增强数据${statusText}${contextText}${priceText}。`;
  }
  match = text.match(/^(.+?) keeps a reserved CNINFO \/ TDX F10 announcements lane; quick mode shows the checklist entry only\.$/);
  if (match) return `${match[1]} 已预留巨潮 / 通达信 F10 公告通道；当前快速模式只显示检查入口。`;
  match = text.match(/^Later versions can enable cached announcement fetching without calling external sources on every query\.$/);
  if (match) return '后续可开启公告抓取缓存，避免每次查询直连外部来源。';
  match = text.match(/^Main fund net inflow is (.+?)(?:, ratio (.+?))?\.$/);
  if (match) return `主力资金净流入 ${match[1]}${match[2] ? `，占比 ${match[2]}` : ''}。`;
  match = text.match(/^Check whether main fund inflow is continuous across several sessions, not only a single-day move\.$/);
  if (match) return '观察近几日主力净流入是否连续，而不是只看单日波动。';
  match = text.match(/^(.+?) keeps a reserved Eastmoney fund-flow lane\.(?: Current change is (.+?)\.)?$/);
  if (match) return `${match[1]} 已预留东财资金流通道。${match[2] ? `当前涨跌幅 ${match[2]}。` : ''}`;
  match = text.match(/^Later versions can add cached daily fund flow by main, large, medium, and small orders\.$/);
  if (match) return '后续可接入主力、大单、中单、小单日级资金流缓存。';
  match = text.match(/^(.+?) current context: (.+?)\.$/);
  if (match) return `${match[1]} 当前背景：${localizeGeneratedTerms(match[2], language)}。`;
  match = text.match(/^Compare move, valuation, and fund flow against the same sector\.$/);
  if (match) return '和同板块标的做涨跌、估值和资金流对比。';
  match = text.match(/^(.+?) has no usable sector tags yet; later versions can add Eastmoney concepts and industry mapping\.$/);
  if (match) return `${match[1]} 暂无可用板块标签，后续可接入东财概念和行业归属。`;
  match = text.match(/^Refresh profile data or enable sector sources before comparing peers\.$/);
  if (match) return '刷新公司资料或开启板块来源后再比较。';
  match = text.match(/^Latest research: (.+?)(?:; rating (.+?))?\.$/);
  if (match) return `最近研报：${match[1]}${match[2] ? `；评级 ${match[2]}` : ''}。`;
  match = text.match(/^Premium can expand research lists, PDFs, and institution forecast fields\.$/);
  if (match) return '免费版保留研报入口和摘要线索；高级版使用 API 展开研报列表、PDF 和机构预测字段。';
  match = text.match(/^(.+?) keeps a reserved Eastmoney \/ iFinD research lane; free quick mode does not fetch PDFs\.$/);
  if (match) return `${match[1]} 已预留东财 / iFinD 研报通道；免费快速模式不拉取 PDF。`;
  match = text.match(/^Deep mode can fetch research sources by symbol and industry\.$/);
  if (match) return '深度模式可按标的和行业拉取研报来源。';
  match = text.match(/^(.*?)Dragon-tiger list record exists(?:, net buy (.+?))?\.$/);
  if (match) return `${match[1] ? `${match[1]}` : ''}存在龙虎榜记录${match[2] ? `，净买入 ${match[2]}` : ''}。`;
  match = text.match(/^(.+?) keeps a reserved dragon-tiger seat lane; seat details are not fetched in quick mode\.$/);
  if (match) return `${match[1]} 已预留龙虎榜席位通道；当前快速模式不拉取席位明细。`;
  match = text.match(/^Focus on institution seats and brokerage buy\/sell direction\.$/);
  if (match) return '重点看机构席位和营业部买卖方向。';
  match = text.match(/^Fetch seat details only after unusual moves or limit-up events to reduce source pressure\.$/);
  if (match) return '出现异动或涨停时再拉取席位明细，降低来源压力。';
  match = text.match(/^Deep mode can expand original announcement text and source links\.$/);
  if (match) return '深度模式可展开公告原文和来源链接。';
  match = text.match(/^Premium can expand announcement source text, research PDFs, fund-flow history, sector linkage, and dragon-tiger seat details\.$/);
  if (match) return '免费版展示同样A股增强入口并使用网络/本地公开源；高级版使用 API 展开公告原文、研报 PDF、资金流历史、板块联动和龙虎榜席位明细。';
  match = text.match(/^(.+?) A-share enrichment is temporarily degraded; the basic quote snapshot remains available\.$/);
  if (match) return `${match[1]} 的 A股增强数据暂时降级；基础行情快照仍可继续使用。`;
  match = text.match(/^Premium can expand announcement, research, fund-flow, sector, and dragon-tiger sources\.$/);
  if (match) return '免费版保留同样来源入口；高级版使用 API 展开公告、研报、资金流、板块和龙虎榜来源。';

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
    .replace(/^Premium can add realtime news, filings, source links, sector comparison, and AI summaries\.$/, '免费版展示同样资讯入口并使用网络/本地公开源；高级版使用 API 获取实时新闻、公告、来源链接、板块对比和 AI 摘要。')
    .replace(/^Kronos adapter ready; local rules preview only; Kronos model not installed or invoked\.$/, 'Kronos 适配器已就绪；当前是本地规则预览，尚未运行 Kronos 模型。')
    .replace(/^Kronos adapter ready; local rules preview only\.$/, 'Kronos 适配器已就绪；当前是本地规则预览。')
    .replace(/^Kronos adapter ready; model not invoked because dependencies are missing: (.+)\.$/, 'Kronos 适配器已就绪；因依赖缺失尚未运行模型：$1。')
    .replace(/^Kronos model unavailable; missing dependencies: (.+)\.$/, 'Kronos 模型不可用；缺失依赖：$1。')
    .replace(/^Kronos market data fetch timed out; local rules fallback used\.$/, 'Kronos 行情数据获取超时，已使用本地规则兜底。')
    .replace(/^KRONOS_ENABLED is false; local rules fallback only\.$/, 'KRONOS_ENABLED 未开启，当前仅使用本地规则兜底。')
    .replace(/^K-line context is short; confidence is capped\.$/, 'K线上下文不足，置信度已降低。')
    .replace(/^Premium can run a configured Kronos or local-model forecast lane after model\/data approval\.$/, '免费版展示K线预测入口和本地规则预览；高级版使用 API 或已批准的本地模型运行更完整预测通道。')
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

const platformPlanLabel = (plan?: string | null, language = 'en'): string => {
  const value = String(plan || '-');
  if (language === 'en') return value;
  const zh: Record<string, string> = {
    free: '免费版',
    pro: '专业版',
    premium: '高级版',
  };
  return zh[value] || value;
};

const apiKeyModeLabel = (mode?: string | null, language = 'en'): string => {
  const isEnglish = language === 'en';
  if (mode === 'user') return isEnglish ? 'BYOK' : '我的 API';
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
    stale_disk_cache: '过期磁盘缓存',
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
    cache_first: '优先缓存',
    force_refresh: '强制刷新',
    refresh: '刷新',
    live: '实时',
    memory: '内存',
    disk: '磁盘',
    disk_cache: '磁盘缓存',
    local_json: '本地缓存',
    local_disk: '本地磁盘',
    cooling_down: '冷却中',
    timeout: '超时',
    failed: '失败',
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
    'Selected BYOK': '已选择我的 API',
    'BYOK ready': '我的 API 已就绪',
    'BYOK not set': '我的 API 未设置',
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

const isPlainRecord = (value: unknown): value is Record<string, unknown> => (
  typeof value === 'object' && value !== null
);

type AShareSourceMode = NonNullable<BasicSnapshotOptions['aShareSourceMode']>;

const A_SHARE_SOURCE_MODES: AShareSourceMode[] = ['poc', 'a_stock_data', 'off'];

const normalizeAShareSourceMode = (value: unknown): AShareSourceMode => (
  value === 'a_stock_data' || value === 'off' ? value : 'poc'
);

const shouldApplyAShareSourceMode = (value: string): boolean => {
  const normalized = value.trim().toUpperCase();
  if (!normalized) {
    return false;
  }
  if (/^\d{6}(\.(SH|SZ|SS))?$/.test(normalized)) {
    return true;
  }
  return /[\u4e00-\u9fff]/.test(normalized);
};

const aShareSourceModeLabel = (mode: AShareSourceMode, language: string): string => {
  const isEnglish = language === 'en';
  if (mode === 'a_stock_data') return isEnglish ? 'a-stock-data' : 'a-stock-data适配';
  if (mode === 'off') return isEnglish ? 'Off' : '关闭';
  return isEnglish ? 'Local rules' : '本地规则';
};

const getRecordField = (record: Record<string, unknown>, key: string): Record<string, unknown> => {
  const value = record[key];
  return isPlainRecord(value) && !Array.isArray(value) ? value : {};
};

const asDisplayNumber = (value: unknown): string => (
  typeof value === 'number' && Number.isFinite(value) ? String(value) : '0'
);

const formatAShareCacheDiagnostics = (diagnostics: Record<string, unknown>, language: string): string => {
  const cache = getRecordField(diagnostics, 'cache');
  const label = language === 'en' ? 'cache' : '缓存';
  return `${label} H${asDisplayNumber(cache.hits)} / M${asDisplayNumber(cache.misses)} / S${asDisplayNumber(cache.staleHits)}`;
};

const formatAShareSkillRevision = (skill: Record<string, unknown>, language: string): string => {
  const revision = typeof skill.revision === 'string' && skill.revision.trim() ? skill.revision.trim() : '-';
  return `${language === 'en' ? 'repo' : '仓库'} ${revision}`;
};

const formatAShareRateLimited = (diagnostics: Record<string, unknown>, language: string): string => {
  const value = diagnostics.rateLimitedChannels;
  const count = Array.isArray(value) ? value.length : 0;
  return `${language === 'en' ? 'rate limited' : '限流通道'} ${count}`;
};

const getPlatformAuthErrorCode = (error: unknown): string | null => {
  if (!isPlainRecord(error)) {
    return null;
  }
  const response = error.response;
  if (!isPlainRecord(response)) {
    return null;
  }
  const data = response.data;
  if (!isPlainRecord(data)) {
    return null;
  }
  const detail = data.detail;
  if (isPlainRecord(detail) && typeof detail.error === 'string') {
    return detail.error;
  }
  return typeof data.error === 'string' ? data.error : null;
};

const localizePlatformAuthError = (
  error: unknown,
  language: string,
  fallback: string,
): string => {
  const isEnglish = language === 'en';
  const code = getPlatformAuthErrorCode(error);
  const messages: Record<string, { en: string; zh: string }> = {
    email_exists: {
      en: 'Email already exists. Sign in instead.',
      zh: '该邮箱已注册，请直接登录',
    },
    invalid_credentials: {
      en: 'Invalid email or password.',
      zh: '邮箱或密码不正确，请检查后再登录',
    },
    invalid_verification_code: {
      en: 'Invalid or expired verification code. Send a new code and try again.',
      zh: '验证码无效或已过期，请重新发送验证码',
    },
    verification_required: {
      en: 'Enter the email verification code first.',
      zh: '请先输入邮箱验证码',
    },
    platform_auth_disabled: {
      en: 'Account login is currently disabled.',
      zh: '账号登录功能暂未开启',
    },
    rate_limited: {
      en: 'Too many attempts. Please wait and try again.',
      zh: '尝试次数过多，请稍后再试',
    },
  };
  if (code && messages[code]) {
    return isEnglish ? messages[code].en : messages[code].zh;
  }

  const parsed = getParsedApiError(error);
  if (isEnglish) {
    return parsed.message || fallback;
  }
  const raw = `${parsed.rawMessage} ${parsed.message}`.toLowerCase();
  if (raw.includes('invalid email')) return '邮箱格式不正确';
  if (raw.includes('password must be at least')) return '密码至少需要 8 位';
  return fallback;
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

type BasicSnapshotViewMode = 'query' | 'quick';

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
  const [basicSnapshotViewMode, setBasicSnapshotViewMode] = useState<BasicSnapshotViewMode>('query');
  const [aShareSourceMode, setAShareSourceMode] = useState<AShareSourceMode>('a_stock_data');
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
  const [basicPremiumPreviewOpen, setBasicPremiumPreviewOpen] = useState(false);
  const [basicEventCenterActiveIndex, setBasicEventCenterActiveIndex] = useState(0);
  const [basicQueryError, setBasicQueryError] = useState<ParsedApiError | null>(null);
  const [kronosForecast, setKronosForecast] = useState<KronosForecastResponse | null>(null);
  const [isRunningKronosForecast, setIsRunningKronosForecast] = useState(false);
  const [kronosForecastError, setKronosForecastError] = useState('');
  const [basicRetentionBusy, setBasicRetentionBusy] = useState(false);
  const [basicRetentionStatus, setBasicRetentionStatus] = useState('');
  const [basicRetentionError, setBasicRetentionError] = useState('');
  const [deepAnalysisNotice, setDeepAnalysisNotice] = useState('');
  const [deepAnalysisInlineNotice, setDeepAnalysisInlineNotice] = useState('');
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
  const [authPasswordConfirm, setAuthPasswordConfirm] = useState('');
  const [authVerificationCode, setAuthVerificationCode] = useState('');
  const [authVerificationStatus, setAuthVerificationStatus] = useState('');
  const [authError, setAuthError] = useState('');
  const [authBusy, setAuthBusy] = useState(false);
  const [authVerificationBusy, setAuthVerificationBusy] = useState(false);
  const [apiKeyDraft, setApiKeyDraft] = useState('');
  const [apiKeyProvider, setApiKeyProvider] = useState('deepseek');
  const [apiKeyModel, setApiKeyModel] = useState('deepseek/deepseek-v4-flash');
  const [apiKeySaving, setApiKeySaving] = useState(false);
  const marketReviewPollTimer = useRef<number | null>(null);
  const dashboardScrollRef = useRef<HTMLElement | null>(null);
  const basicSnapshotRef = useRef<HTMLDivElement | null>(null);
  const platformAuthPanelRef = useRef<HTMLDivElement | null>(null);
  const deepInlineGuardRef = useRef<HTMLDivElement | null>(null);
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
    const verificationCode = authVerificationCode.trim();
    if (authMode === 'register') {
      if (!authPasswordConfirm) {
        setAuthError(uiLanguage === 'en' ? 'Confirm the password first.' : '请再次输入密码');
        platformAuthPanelRef.current?.querySelector<HTMLInputElement>('[data-testid="platform-auth-confirm-password"]')?.focus();
        return;
      }
      if (authPassword !== authPasswordConfirm) {
        setAuthError(uiLanguage === 'en' ? 'The two passwords do not match.' : '两次输入的密码不一致');
        platformAuthPanelRef.current?.querySelector<HTMLInputElement>('[data-testid="platform-auth-confirm-password"]')?.focus();
        return;
      }
      if (!verificationCode) {
        setAuthError(uiLanguage === 'en' ? 'Enter the email verification code first.' : '请先输入邮箱验证码');
        platformAuthPanelRef.current?.querySelector<HTMLInputElement>('[data-testid="platform-auth-verification-code"]')?.focus();
        return;
      }
    }
    setAuthBusy(true);
    setAuthError('');
    try {
      const retainedQuery = basicSnapshot?.stockCode || query;
      const payload = authMode === 'register'
        ? await platformApi.register(email, authPassword, verificationCode)
        : await platformApi.login(email, authPassword);
      await loadPlatformAccount(payload);
      setAuthPassword('');
      setAuthPasswordConfirm('');
      setAuthVerificationCode('');
      setAuthVerificationStatus('');
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
      setAuthError(localizePlatformAuthError(
        err,
        uiLanguage,
        uiLanguage === 'en' ? 'Account sign-in failed.' : '账号登录失败',
      ));
    } finally {
      setAuthBusy(false);
    }
  }, [authEmail, authMode, authPassword, authPasswordConfirm, authVerificationCode, basicSnapshot?.stockCode, loadInitialHistory, loadMarketReviewHistory, loadPlatformAccount, loadStockBar, query, refreshActiveTasks, resetDashboardState, setQuery, uiLanguage]);

  const handleRequestRegistrationCode = useCallback(async () => {
    const email = authEmail.trim();
    if (!email) {
      setAuthError(uiLanguage === 'en' ? 'Enter an email first.' : '请先输入邮箱');
      platformAuthPanelRef.current?.querySelector<HTMLInputElement>('[data-testid="platform-auth-email"]')?.focus();
      return;
    }
    setAuthVerificationBusy(true);
    setAuthError('');
    setAuthVerificationStatus('');
    try {
      const response = await platformApi.requestRegistrationCode(email);
      setAuthError('');
      setAuthVerificationCode(response.devCode || '');
      const devCodeText = response.devCode
        ? (uiLanguage === 'en' ? ` Local code auto-filled: ${response.devCode}` : `本地验证码已自动填入：${response.devCode}`)
        : '';
      setAuthVerificationStatus(
        uiLanguage === 'en'
          ? `Verification code generated.${devCodeText}`
          : `验证码已生成。${devCodeText}`,
      );
      window.setTimeout(() => {
        platformAuthPanelRef.current?.querySelector<HTMLInputElement>('[data-testid="platform-auth-verification-code"]')?.focus();
      }, 0);
    } catch (err: unknown) {
      setAuthError(localizePlatformAuthError(
        err,
        uiLanguage,
        uiLanguage === 'en' ? 'Failed to send verification code' : '验证码发送失败',
      ));
    } finally {
      setAuthVerificationBusy(false);
    }
  }, [authEmail, uiLanguage]);

  const handlePlatformAuthModeChange = useCallback((mode: 'login' | 'register') => {
    setAuthMode(mode);
    setAuthError('');
    setAuthPassword('');
    setAuthPasswordConfirm('');
    setAuthVerificationCode('');
    setAuthVerificationStatus('');
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
    setAuthPassword('');
    setAuthPasswordConfirm('');
    setAuthVerificationCode('');
    setAuthVerificationStatus('');
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
    if (!platformSession) {
      setAuthMode('register');
      setPlatformWatchlistError('');
      setBasicRetentionStatus('');
      setBasicRetentionError(uiLanguage === 'en' ? 'Register or login to save this watchlist item.' : '注册或登录后可保存自选。');
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
  }, [basicSnapshot?.stockCode, platformSession, platformWatchlistBusy, query, uiLanguage]);

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
    ? (uiLanguage === 'en' ? `BYOK ready ${primaryApiKey.maskedKey}` : `我的 API 已就绪 ${primaryApiKey.maskedKey}`)
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
        ? (isEnglish ? 'Quote is not fresh; refresh before making comparisons.' : '行情不是最新，比较前应先刷新确认。')
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
          ? 'Use API-backed channels when the same modules need fresher news, filings, fundamentals, sector comparison, or a longer AI report.'
          : '同样模块需要更实时的资讯、公告、基本面、行业对比或 AI 长报告时，再使用 API 通道。',
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
  const basicFreeCompleteRead = useMemo(() => {
    if (!basicSnapshot || !basicFreeReport) {
      return null;
    }
    const isEnglish = uiLanguage === 'en';
    const sourceLane = basicSnapshot.route?.dataSourceLane
      || basicSnapshot.route?.channel
      || basicSnapshot.diagnostics?.routeLane
      || `${basicSnapshot.market.toUpperCase()} market data`;
    const freshness = localizeRuntimeLabel(basicSnapshot.quote.freshness, uiLanguage);
    const watchPoints = basicSnapshot.intelligence?.watchPoints ?? [];
    const watchSummary = watchPoints.length > 0
      ? watchPoints.slice(0, 2).map((item) => {
          if (isEnglish) {
            return `${item.title}: ${item.detail}`;
          }
          if (item.category === 'trend') {
            return `趋势修复：观察价格能否改善均线位置，先确认${basicFreeReport.productBrief.shortStatus} / ${basicFreeReport.productBrief.midStatus}`;
          }
          if (item.category === 'volume') {
            return '量能确认：观察成交量能否改善，避免只看价格波动';
          }
          if (item.category === 'risk') {
            return '风险边界：先处理数据警示，再看支撑压力是否有效';
          }
          return localizeGeneratedText(item.detail || item.title, uiLanguage);
        }).join('；')
      : (isEnglish
          ? 'Refresh once and compare price position, volume confirmation, and broad-market references.'
          : '先刷新行情，再观察价格位置、量能确认和大盘参照是否同步。');
    const riskSummary = basicFreeReport.productBrief.risks.length > 0
      ? basicFreeReport.productBrief.risks.slice(0, 2).map((risk) => localizeGeneratedText(risk, uiLanguage)).join(' ')
      : (isEnglish
          ? 'No major quick-rule risk was detected, but this remains an information-only snapshot.'
          : '快速规则未发现明显风险项，但当前仍只是信息分析快照。');
    const supportPressure = isEnglish
      ? `Support ${basicFreeReport.productBrief.supportLevels}; resistance ${basicFreeReport.productBrief.pressureLevels}.`
      : `支撑 ${basicFreeReport.productBrief.supportLevels}；压力 ${basicFreeReport.productBrief.pressureLevels}。`;
    const channelDifference = isEnglish
      ? 'Free shows the same modules with web/local public sources; premium uses platform API, user API, or local models for fresher, steadier, and deeper reads.'
      : '免费版看同样模块，使用网络/本地公开数据；高级版使用 API、我的 API 或本地模型提升实时性、稳定性和深度。';
    return {
      title: isEnglish ? 'Complete free quick read' : '免费版完整速读',
      subtitle: isEnglish
        ? 'A richer first-screen report using quote, trend, volume, profile, local news lanes, and K-line preview without spending AI quota.'
        : '不消耗 AI 额度，把行情、趋势、量价、公司资料、本地资讯通道和K线预览整理成一屏可读报告。',
      items: [
        {
          label: isEnglish ? 'Opportunity lens' : '机会看点',
          body: `${localizeGeneratedText(basicFreeReport.productBrief.conclusion, uiLanguage)} ${supportPressure}`,
        },
        {
          label: isEnglish ? 'Risk boundary' : '风险边界',
          body: riskSummary,
        },
        {
          label: isEnglish ? 'Next watchlist' : '下一步观察',
          body: watchSummary,
        },
        {
          label: isEnglish ? 'Data source' : '数据来源',
          body: isEnglish
            ? `${localizeGeneratedSource(sourceLane, uiLanguage)}; quote freshness: ${freshness}; AI not used.`
            : `${localizeGeneratedSource(sourceLane, uiLanguage)}；行情状态：${freshness}；未使用 AI。`,
        },
        {
          label: isEnglish ? 'Version difference' : '版本差异',
          body: channelDifference,
        },
      ],
    };
  }, [basicFreeReport, basicSnapshot, uiLanguage]);
  const basicBrokerCockpit = useMemo(() => {
    if (!basicSnapshot || !basicFreeReport) {
      return null;
    }
    const isEnglish = uiLanguage === 'en';
    const sourceLane = basicSnapshot.route?.dataSourceLane
      || basicSnapshot.route?.channel
      || basicSnapshot.diagnostics?.routeLane
      || `${basicSnapshot.market.toUpperCase()} market data`;
    const currentPrice = toFiniteBasicNumber(basicSnapshot.quote.currentPrice);
    const ma20 = toFiniteBasicNumber(pickBasicIndicator(basicSnapshot.indicators, 'ma20', 'MA20'));
    const peerTargets = (basicSnapshot.intelligence?.comparisonTargets ?? [])
      .slice(0, 3)
      .map((item) => item.symbol || item.label)
      .filter((value): value is string => Boolean(value));
    const evidenceItems = [
      {
        label: isEnglish ? 'Price structure' : '价格结构',
        value: isEnglish
          ? `${formatBasicNumber(currentPrice)} vs MA20 ${formatBasicNumber(ma20)}`
          : `最新价 ${formatBasicNumber(currentPrice)} / MA20 ${formatBasicNumber(ma20)}`,
        detail: localizeGeneratedText(basicFreeReport.productBrief.conclusion, uiLanguage),
      },
      {
        label: isEnglish ? 'Peer reference' : '同业参照',
        value: peerTargets.length > 0 ? peerTargets.join(' / ') : basicSnapshot.stockCode,
        detail: isEnglish
          ? 'Read the stock against market and sector references before acting.'
          : '先和大盘、行业或同业参照比较，不孤立解读单只股票。',
      },
      {
        label: isEnglish ? 'Data channel' : '数据通道',
        value: localizeGeneratedSource(sourceLane, uiLanguage),
        detail: isEnglish
          ? `${localizeRuntimeLabel(basicSnapshot.quote.freshness, uiLanguage)} quote, no AI used in this quick read.`
          : `${localizeRuntimeLabel(basicSnapshot.quote.freshness, uiLanguage)}行情，快速研判未使用 AI。`,
      },
    ];
    const riskItems = [
      ...(basicFreeReport.productBrief.risks ?? []).slice(0, 2).map((risk) => localizeGeneratedText(risk, uiLanguage)),
      isEnglish
        ? `Support ${basicFreeReport.productBrief.supportLevels}; resistance ${basicFreeReport.productBrief.pressureLevels}.`
        : `支撑 ${basicFreeReport.productBrief.supportLevels}；压力 ${basicFreeReport.productBrief.pressureLevels}。`,
      isEnglish ? 'Information analysis only, not investment advice.' : '仅作信息分析，不构成投资建议。',
    ].filter(Boolean);
    return {
      title: isEnglish ? 'Broker first-screen read' : '经纪人首屏研判',
      question: isEnglish ? 'Is it worth continuing now?' : '现在值不值得继续看',
      verdictLabel: isEnglish ? 'Verdict' : '结论',
      verdict: localizeGeneratedText(basicFreeReport.productBrief.conclusion, uiLanguage),
      scoreLabel: isEnglish ? 'Research score' : '研究分',
      score: `${basicFreeReport.score}/100`,
      proofLabel: isEnglish ? 'Evidence chain' : '证据链',
      riskLabel: isEnglish ? 'Risk boundary' : '风险边界',
      upgradeLabel: isEnglish ? 'What upgrade solves' : '升级后解决什么',
      freePromise: isEnglish
        ? 'Free mode gives the complete research structure first.'
        : '免费版先给完整研究结构',
      premiumPromise: isEnglish
        ? 'Premium switches to real-time APIs, source links, and deeper models.'
        : '高级版换实时 API、来源链接和模型深度',
      evidenceItems,
      riskItems,
      upgradeItems: isEnglish
        ? ['Realtime news and filings', 'Steadier peer quotes', 'Kronos/API model depth', 'Saved history and watchlist tracking']
        : ['实时资讯和公告链接', '更稳定的同业行情', 'Kronos/API 模型深度', '历史与自选持续跟踪'],
      nextActions: isEnglish
        ? ['Check price versus MA20', 'Compare QQQ / sector', 'Open deep mode only when source links are needed']
        : ['先看价格是否守住 MA20', '再和 QQQ / 行业参照比较', '需要来源链接时再开深度模式'],
    };
  }, [basicFreeReport, basicSnapshot, uiLanguage]);
  const basicProDecisionCard = useMemo(() => {
    if (!basicSnapshot || !basicFreeReport || !basicBrokerCockpit) {
      return null;
    }
    const isEnglish = uiLanguage === 'en';
    const score = basicFreeReport.score;
    const priority = score >= 75
      ? (isEnglish ? 'High' : '高')
      : score >= 55
        ? (isEnglish ? 'Medium' : '中')
        : (isEnglish ? 'Watch first' : '先观察');
    return {
      title: isEnglish ? 'Professional decision overview' : '专业研判总览',
      priorityLabel: isEnglish ? 'Research priority' : '继续研究优先级',
      priorityValue: `${priority} · ${score}/100`,
      oneLineLabel: isEnglish ? 'One-line read' : '一句话结论',
      oneLine: localizeGeneratedText(basicFreeReport.productBrief.conclusion, uiLanguage),
      evidenceLabel: isEnglish ? 'Key evidence' : '关键证据',
      evidenceItems: basicBrokerCockpit.evidenceItems.slice(0, 3),
      riskLabel: isEnglish ? 'Check risks first' : '风险先看',
      riskItems: basicBrokerCockpit.riskItems.slice(0, 3),
      upgradeLabel: isEnglish ? 'Premium fills the gaps' : '升级后补齐',
      upgradeItems: isEnglish
        ? ['Realtime API', 'Source links', 'Model depth', 'Continuous tracking']
        : ['实时 API', '原文链接', '模型深度', '持续跟踪'],
      freeOpenLabel: isEnglish ? 'Free mode already includes' : '免费版已开放',
      freeOpenModules: isEnglish
        ? 'quote, technicals, news, K-line, peers, risk'
        : '行情、技术、资讯、K线、同业、风险',
      premiumLabel: isEnglish ? 'Premium improves' : '高级版增强',
      boundary: isEnglish ? 'Information analysis only, not investment advice.' : '仅作信息分析，不构成投资建议。',
    };
  }, [basicBrokerCockpit, basicFreeReport, basicSnapshot, uiLanguage]);
  const basicQuoteTrustPanel = useMemo(() => {
    if (!basicSnapshot) {
      return null;
    }
    const isEnglish = uiLanguage === 'en';
    const sourceLabel = (source: unknown): string => {
      const raw = String(source ?? '');
      if (raw === 'yahoo_chart') {
        return isEnglish ? 'Yahoo chart data' : 'Yahoo 图表数据';
      }
      if (raw === 'crypto_yahoo_chart') {
        return isEnglish ? 'Yahoo crypto chart data' : 'Yahoo 加密行情图表';
      }
      return localizeGeneratedSource(raw, uiLanguage);
    };
    const currentPrice = toFiniteBasicNumber(basicSnapshot.quote.currentPrice);
    const quoteFreshnessRaw = String(
      basicSnapshot.quote.freshness
      || basicSnapshot.diagnostics?.freshness?.quote
      || '',
    ).toLowerCase();
    const quoteCacheRaw = String(basicSnapshot.diagnostics?.cache?.quote || '').toLowerCase();
    const quoteFallbackRaw = String(basicSnapshot.diagnostics?.fallback?.quote || '').toLowerCase();
    const quoteHealthRaw = Object.values(basicSnapshot.diagnostics?.sourceHealth ?? {})
      .map((item) => String(item?.status || '').toLowerCase())
      .filter(Boolean);
    const refreshModeRaw = String(basicSnapshot.diagnostics?.refresh?.mode || '').toLowerCase();
    const isFreshQuote = ['fresh', 'live', 'realtime', 'real_time'].some((token) => quoteFreshnessRaw.includes(token));
    const usesCacheOrStale = [quoteFreshnessRaw, quoteCacheRaw, quoteFallbackRaw].some((value) => (
      value.includes('cache')
      || value.includes('cached')
      || value.includes('stale')
      || value.includes('expired')
      || value === 'hit'
    ));
    const hasSourceIssue = quoteHealthRaw.some((status) => !['ok', 'healthy', 'live', 'fresh', 'success'].includes(status));
    const forceRefreshRequested = basicSnapshot.diagnostics?.refresh?.requested === true || refreshModeRaw.includes('force');
    const dataStateValue = currentPrice === null
      ? (isEnglish ? 'Price missing, verify first' : '价格缺失，需复核')
      : isFreshQuote && !usesCacheOrStale && !hasSourceIssue
        ? (isEnglish ? 'Realtime quote available' : '实时行情可用')
        : (isEnglish ? 'Stale or cached quote' : '过期或缓存行情');
    const refreshActionValue = forceRefreshRequested
      ? (isEnglish ? 'Force refresh requested' : '已请求强制刷新')
      : isFreshQuote && !usesCacheOrStale
        ? (isEnglish ? 'Refresh again to confirm' : '可再次刷新确认')
        : (isEnglish ? 'Refresh before interpretation' : '先刷新再解读');
    const sourceLane = basicSnapshot.route?.dataSourceLane
      || basicSnapshot.route?.channel
      || basicSnapshot.diagnostics?.routeLane
      || `${basicSnapshot.market.toUpperCase()} market data`;
    const sourceCompareValue = `${sourceLabel(basicSnapshot.quote.source)} / ${marketLaneLabel(sourceLane, uiLanguage)}`;
    const analysisToneValue = dataStateValue === (isEnglish ? 'Realtime quote available' : '实时行情可用')
      ? (isEnglish ? 'Normal interpretation allowed' : '可正常解读')
      : (isEnglish ? 'Use as a watchlist checklist' : '先作为观察清单');
    const sourceHealthValue = quoteHealthRaw.length > 0
      ? Array.from(new Set(quoteHealthRaw.map((status) => localizeRuntimeLabel(status, uiLanguage)))).join(' / ')
      : localizeRuntimeLabel('unavailable', uiLanguage);
    const cards = [
      {
        label: isEnglish ? 'Data state' : '数据状态',
        value: dataStateValue,
        detail: isEnglish
          ? `Freshness ${localizeRuntimeLabel(quoteFreshnessRaw || 'unavailable', uiLanguage)}; source health ${sourceHealthValue}.`
          : `新鲜度 ${localizeRuntimeLabel(quoteFreshnessRaw || 'unavailable', uiLanguage)}；来源健康 ${sourceHealthValue}。`,
      },
      {
        label: isEnglish ? 'Refresh action' : '刷新动作',
        value: refreshActionValue,
        detail: isEnglish
          ? 'One click forces the quote/history lane to bypass cache when the backend supports it.'
          : '一键走强制刷新，在后端支持时绕过缓存重新取行情和历史。',
      },
      {
        label: isEnglish ? 'Source comparison' : '来源对照',
        value: sourceCompareValue,
        detail: isEnglish
          ? `Cache ${localizeRuntimeLabel(quoteCacheRaw || 'unavailable', uiLanguage)}; fallback ${localizeRuntimeLabel(quoteFallbackRaw || 'unavailable', uiLanguage)}.`
          : `缓存 ${localizeRuntimeLabel(quoteCacheRaw || 'unavailable', uiLanguage)}；兜底 ${localizeRuntimeLabel(quoteFallbackRaw || 'unavailable', uiLanguage)}。`,
      },
      {
        label: isEnglish ? 'Analysis tone' : '分析口吻',
        value: analysisToneValue,
        detail: isEnglish
          ? 'When the source is stale, the free report downgrades the language instead of pretending certainty.'
          : '如果行情过期，免费研判会降级表达，不会把临时数据说成确定结论。',
      },
    ];
    return {
      title: isEnglish ? 'Quote trust' : '行情可信度',
      subtitle: isEnglish
        ? 'Before reading signals, confirm whether the quote is fresh, cached, degraded, or worth refreshing.'
        : '读信号前先确认这次行情是实时、缓存、降级，还是应该先刷新。',
      statusValue: dataStateValue,
      refreshLabel: isEnglish ? 'Refresh live quote' : '刷新实时行情',
      upgradeLabel: isEnglish ? 'Premium fills the gaps' : '高级版补齐',
      upgradeItems: isEnglish
        ? ['Multi-source API comparison', 'Abnormal price review', 'Source links', 'Refresh history tracking']
        : ['多源 API 对照', '异常价格复核', '原文事件链接', '刷新历史追踪'],
      cards,
    };
  }, [basicSnapshot, uiLanguage]);
  const basicTodayBriefCard = useMemo(() => {
    if (!basicSnapshot || !basicFreeReport) {
      return null;
    }
    const isEnglish = uiLanguage === 'en';
    const currentPrice = toFiniteBasicNumber(basicSnapshot.quote.currentPrice);
    const changePercent = toFiniteBasicNumber(basicSnapshot.quote.changePercent);
    const ma20 = toFiniteBasicNumber(pickBasicIndicator(basicSnapshot.indicators, 'ma20', 'MA20'));
    const dataTrustValue = basicQuoteTrustPanel?.statusValue
      || (isEnglish ? 'Verify quote freshness' : '先确认行情新鲜度');
    const hasFreshQuote = dataTrustValue === (isEnglish ? 'Realtime quote available' : '实时行情可用');
    const ma20Text = formatBasicNumber(ma20);
    const score = basicFreeReport.score;
    const canReadValue = score >= 70 && hasFreshQuote
      ? (isEnglish ? 'Worth continuing' : '可以继续看')
      : score >= 55
        ? (isEnglish ? 'Watch, then verify' : '可以观察，先复核')
        : (isEnglish ? 'Verify first' : '先复核再看');
    const nextAction = hasFreshQuote
      ? (isEnglish
        ? `Refresh live quote, then watch whether price holds MA20 ${ma20Text}.`
        : `刷新实时行情后，观察价格能否继续守住 MA20 ${ma20Text}。`)
      : (isEnglish
        ? 'Refresh live quote before interpreting the signal and trend.'
        : '先刷新实时行情，再解读信号和趋势。');
    const riskText = localizeGeneratedText(
      basicFreeReport.productBrief.risks[0]
      || basicFreeReport.productBrief.midStatus
      || (isEnglish ? 'Use this as a watchlist checklist only.' : '仅作为观察清单使用。'),
      uiLanguage,
    );
    return {
      title: isEnglish ? 'Today quick brief' : '今日看点摘要',
      stockTitle: basicSnapshot.stockName
        ? `${basicSnapshot.stockName} · ${basicSnapshot.stockCode}`
        : basicSnapshot.stockCode,
      oneLineLabel: isEnglish ? 'One-line view' : '一句话看法',
      oneLine: localizeGeneratedText(basicFreeReport.productBrief.conclusion, uiLanguage),
      signalLabel: isEnglish ? 'Signal completeness' : '信号完整度',
      signalValue: `${score}/100`,
      priceLabel: isEnglish ? 'Price / change' : '价格 / 涨跌',
      priceValue: `${formatBasicNumber(currentPrice)} / ${formatSignedBasicPercent(changePercent)}`,
      dataTrustLabel: isEnglish ? 'Data trust' : '数据可信度',
      dataTrustValue,
      nextActionLabel: isEnglish ? 'Next action' : '下一步动作',
      nextAction,
      refreshLabel: isEnglish ? 'Refresh live quote' : '刷新实时行情',
      riskLabel: isEnglish ? 'Risk boundary' : '风险边界',
      riskText,
      freeLabel: isEnglish ? 'Free already gives' : '免费版已给出',
      freeItems: isEnglish
        ? ['Price and change', 'Trend and MA20', 'Data trust', 'Next action']
        : ['价格涨跌', '趋势均线', '数据可信度', '下一步动作'],
      premiumLabel: isEnglish ? 'Premium fills' : '高级版补齐',
      premiumItems: isEnglish
        ? ['Realtime news/API', 'Source links', 'Kronos/API model', 'Continuous tracking']
        : ['实时资讯/API', '来源链接', 'Kronos/API 模型', '持续跟踪'],
      premiumPreviewOpenLabel: isEnglish ? 'Preview what Premium adds' : '查看高级版会新增哪些内容',
      premiumPreviewCloseLabel: isEnglish ? 'Hide Premium preview' : '收起高级版预览',
      premiumPreviewTitle: isEnglish ? 'Premium report structure preview' : '高级版报告结构预览',
      premiumPreviewSubtitle: isEnglish
        ? 'Structure preview only; no quota is consumed.'
        : '只展示结构，不消耗额度。',
      premiumPreviewBoundary: isEnglish
        ? 'This preview does not run AI analysis and does not spend quota.'
        : '不会发起 AI 分析，不扣额度。',
      premiumConversionTitle: isEnglish ? 'Upgrade value preview' : '升级价值预览',
      premiumConversionSubtitle: isEnglish
        ? 'Free keeps the same visible workflow; Premium switches the same modules to API-backed sources, source links, and approved model lanes.'
        : '免费版同样可看完整流程；高级版把同样模块换成 API 数据源、原文链接和已批准模型通道。',
      premiumConversionBoundary: isEnglish
        ? 'Local preview only; real payment is not connected.'
        : '本地预览，不接真实支付。',
      premiumConversionColumns: {
        free: isEnglish ? 'Free remains useful' : '免费版同样可看',
        premium: isEnglish ? 'Premium switches to API sources' : '高级版换 API 数据源',
      },
      premiumConversionRows: [
        {
          title: isEnglish ? 'Realtime news originals' : '实时新闻原文',
          free: isEnglish
            ? 'Free keeps the event lane and first-pass checklist visible.'
            : '免费版保留事件通道和首轮检查清单。',
          premium: isEnglish
            ? 'Premium/API mode adds original article links, update time, and source health.'
            : '高级版/API 模式补原文链接、更新时间和来源健康。',
        },
        {
          title: isEnglish ? 'Filings / SEC original links' : '公告/SEC 原文链接',
          free: isEnglish
            ? 'Free shows the filings lane and flags whether deeper source work is needed.'
            : '免费版展示公告通道，并提示是否需要继续查来源。',
          premium: isEnglish
            ? 'Premium adds source documents, filings, and announcement detail when configured.'
            : '高级版在配置后补公告原文、SEC/交易所文件和细节字段。',
        },
        {
          title: isEnglish ? 'Peer strength API' : '同业强弱 API',
          free: isEnglish
            ? 'Free shows available peer or index references.'
            : '免费版展示可用同业或指数参照。',
          premium: isEnglish
            ? 'Premium/API mode compares peers, ETFs, sectors, and relative strength more reliably.'
            : '高级版/API 模式更稳定地对比同业、ETF、板块和相对强弱。',
        },
        {
          title: isEnglish ? 'Kronos/API forecast' : 'Kronos/API 预测',
          free: isEnglish
            ? 'Free keeps local K-line rules and forecast entry visible.'
            : '免费版保留本地 K 线规则和预测入口。',
          premium: isEnglish
            ? 'Premium can run approved Kronos, API, or local-model lanes after data checks.'
            : '高级版可在数据确认后运行已批准的 Kronos、API 或本地模型通道。',
        },
        {
          title: isEnglish ? 'Continuous tracking alerts' : '持续跟踪提醒',
          free: isEnglish
            ? 'Free lets users keep history, watchlist, and current snapshot context.'
            : '免费版可保留历史、自选和当前快照上下文。',
          premium: isEnglish
            ? 'Premium improves scheduled follow-up checks, refresh history, and alert confidence.'
            : '高级版增强定时复核、刷新历史和提醒可信度。',
        },
      ],
      premiumPreviewModules: [
        {
          title: isEnglish ? 'Realtime news/API' : '实时资讯/API',
          detail: isEnglish
            ? 'Switch the same report lane to API-backed news, filings, announcements, and fresher quote sources.'
            : '把同一份报告切到 API 支持的资讯、公告、文件和更稳定行情源。',
        },
        {
          title: isEnglish ? 'Source links' : '来源链接',
          detail: isEnglish
            ? 'Show source URL, update time, source health, and original-event context for easier verification.'
            : '展示来源链接、更新时间、来源健康和原始事件上下文，方便复核。',
        },
        {
          title: isEnglish ? 'Kronos/API model validation' : 'Kronos/API 模型验证',
          detail: isEnglish
            ? 'Use configured model lanes to validate K-line scenarios without turning them into trade instructions.'
            : '用已配置模型通道验证 K 线情景，但不把模型输出当成交易指令。',
        },
        {
          title: isEnglish ? 'Continuous tracking and history' : '持续跟踪与历史',
          detail: isEnglish
            ? 'Keep watchlist, historical snapshots, refresh state, and follow-up checkpoints together.'
            : '把自选、历史快照、刷新状态和后续观察点放在一起持续跟踪。',
        },
      ],
      brokerTitle: isEnglish ? 'Broker three-step view' : '经纪人三段判断',
      brokerFootnote: isEnglish
        ? 'Free gives the decision frame first; Premium adds verification depth.'
        : '免费版先给判断框架，高级版补齐验证深度。',
      brokerSteps: [
        {
          label: isEnglish ? 'Can I keep reading?' : '能不能看',
          value: canReadValue,
          detail: hasFreshQuote
            ? (isEnglish ? 'Quote is usable, so the first read can continue.' : '行情可用，可以继续读后面的结构。')
            : (isEnglish ? 'Data is degraded; refresh before deeper reading.' : '数据有降级，先刷新再做深读。'),
        },
        {
          label: isEnglish ? 'Why read it?' : '为什么看',
          value: `${isEnglish ? 'Signal completeness' : '信号完整度'} ${score}/100`,
          detail: localizeGeneratedText(basicFreeReport.productBrief.conclusion, uiLanguage),
        },
        {
          label: isEnglish ? 'When to upgrade?' : '什么时候升级',
          value: isEnglish
            ? 'Upgrade when realtime news/API, source links, or model validation are needed'
            : '需要实时资讯/API、来源链接或模型验证时升级',
          detail: isEnglish
            ? 'Use Premium when the next question is verification depth, not just first-pass structure.'
            : '当问题从“先看结构”变成“要验证来源和模型”时，再用高级版。',
        },
      ],
      boundary: isEnglish ? 'Information analysis only, not investment advice.' : '仅作信息分析，不构成投资建议。',
    };
  }, [basicFreeReport, basicQuoteTrustPanel, basicSnapshot, uiLanguage]);
  const basicNextActionsWorkflow = useMemo(() => {
    if (!basicSnapshot || !basicFreeReport) {
      return null;
    }
    const isEnglish = uiLanguage === 'en';
    return {
      title: isEnglish ? 'Next action workflow' : '下一步工作流',
      subtitle: isEnglish
        ? 'Keep reading without AI quota: refresh the quote, inspect news, compare peers, review K-line scenarios, or save the symbol.'
        : '不消耗 AI 额度继续阅读：刷新行情、查看资讯、对照同业、看 K 线情景，或保存自选。',
      boundary: isEnglish ? 'No AI, no quota' : '未用 AI，不扣额度',
      actions: [
        {
          key: 'refresh',
          label: isEnglish ? 'Refresh quote' : '刷新行情',
          detail: isEnglish ? 'Recheck price and freshness before reading.' : '先确认价格和新鲜度。',
        },
        {
          key: 'news',
          label: isEnglish ? 'Read news' : '看资讯',
          detail: isEnglish ? 'Jump to news and filing lanes.' : '跳到资讯/公告通道。',
        },
        {
          key: 'peers',
          label: isEnglish ? 'Compare peers' : '看同业',
          detail: isEnglish ? 'Jump to peer and index references.' : '跳到同业/指数参照。',
        },
        {
          key: 'kline',
          label: isEnglish ? 'Inspect K-line' : '看K线',
          detail: isEnglish ? 'Jump to the K-line forecast lab.' : '跳到 K 线预测实验室。',
        },
        {
          key: 'watchlist',
          label: isEnglish ? 'Save watchlist' : '保存自选',
          detail: isEnglish ? 'Login can persist watchlist state.' : '登录后保留自选状态。',
        },
      ],
    };
  }, [basicFreeReport, basicSnapshot, uiLanguage]);
  const basicFreeAnalystWorkbench = useMemo(() => {
    if (!basicSnapshot || !basicFreeReport) {
      return null;
    }
    const isEnglish = uiLanguage === 'en';
    const score = basicFreeReport.score;
    const dataTrust = basicQuoteTrustPanel?.statusValue
      || localizeRuntimeLabel(basicSnapshot.quote.freshness || 'unavailable', uiLanguage);
    const support = localizeGeneratedText(basicFreeReport.productBrief.supportLevels, uiLanguage);
    const resistance = localizeGeneratedText(basicFreeReport.productBrief.pressureLevels, uiLanguage);
    const conclusion = localizeGeneratedText(basicFreeReport.productBrief.conclusion, uiLanguage);
    const firstRisk = localizeGeneratedText(
      basicFreeReport.productBrief.risks[0]
      || basicFreeReport.productBrief.midStatus
      || (isEnglish ? 'Treat this as an observation checklist only.' : '先当作观察清单，不要直接下结论。'),
      uiLanguage,
    );
    const decisionValue = score >= 70
      ? (isEnglish ? 'Worth continuing' : '值得继续看')
      : score >= 55
        ? (isEnglish ? 'Readable, verify first' : '可看，先复核')
        : (isEnglish ? 'Verify data first' : '先复核数据');
    const peerRows = basicSnapshot.intelligence?.peerComparison?.rows ?? [];
    const comparisonTargets = basicSnapshot.intelligence?.comparisonTargets ?? [];
    const peerText = peerRows.length > 0
      ? peerRows.slice(0, 3).map((row) => row.symbol || row.label).filter(Boolean).join(' / ')
      : comparisonTargets.slice(0, 3).map((item) => item.symbol || item.label).filter(Boolean).join(' / ');
    const hasNews = Boolean(
      basicSnapshot.intelligence?.newsCenter?.items?.length
      || basicSnapshot.intelligence?.items?.length,
    );
    const klineDirection = localizeRuntimeLabel(
      basicSnapshot.intelligence?.klineForecast?.direction
      || basicSnapshot.intelligence?.klineForecast?.scenarios?.[0]?.direction
      || 'pending',
      uiLanguage,
    );
    const evidenceLine = isEnglish
      ? `Support ${support}; resistance ${resistance}; data trust ${dataTrust}.`
      : `支撑 ${support}；压力 ${resistance}；数据可信度 ${dataTrust}。`;
    return {
      title: isEnglish ? 'Free analyst workbench' : '免费研判工作台',
      subtitle: isEnglish
        ? 'Read it like a broker: conclusion, evidence, risk, and the next click first.'
        : '像经纪人一样先看结论、证据、风险和下一步，再决定是否继续深挖。',
      boundary: isEnglish ? 'No AI, no quota' : '未用 AI，不扣额度',
      cards: [
        {
          label: isEnglish ? 'Worth continuing?' : '是否值得继续看',
          value: decisionValue,
          detail: isEnglish
            ? `Signal completeness ${score}/100.`
            : `信号完整度 ${score}/100。`,
        },
        {
          label: isEnglish ? 'Main point now' : '当前最大看点',
          value: conclusion,
          detail: evidenceLine,
        },
        {
          label: isEnglish ? 'Biggest risk' : '最大风险',
          value: firstRisk,
          detail: isEnglish
            ? 'Refresh source freshness before treating the signal as stable.'
            : '先刷新来源新鲜度，再把信号当作稳定参考。',
        },
        {
          label: isEnglish ? 'Next path' : '下一步路径',
          value: isEnglish ? 'News -> Peers -> K-line' : '看资讯 -> 看同业 -> 看K线',
          detail: isEnglish
            ? 'Use the same free workflow before deciding whether API depth is needed.'
            : '先把免费工作流走完，再判断是否需要 API 深度。',
        },
      ],
      freeTitle: isEnglish ? 'Free already opens' : '免费版已经开放',
      premiumTitle: isEnglish ? 'Premium improves' : '高级版增强',
      freeModules: [
        isEnglish ? 'Quote and moving averages' : '行情与均线',
        hasNews ? (isEnglish ? 'News/event lane' : '资讯事件通道') : (isEnglish ? 'News lane status' : '资讯通道状态'),
        peerText ? `${isEnglish ? 'Peer reference' : '同业参照'} ${peerText}` : (isEnglish ? 'Peer/reference lane' : '同业参照通道'),
        `${isEnglish ? 'K-line scenario' : 'K线情景'} ${klineDirection}`,
        isEnglish ? 'Risk checklist' : '风险清单',
      ],
      premiumModules: isEnglish
        ? ['Realtime API sources', 'Original links', 'Model validation', 'Continuous alerts']
        : ['实时 API 数据源', '原文链接', '模型验证', '持续提醒'],
      actionLabels: {
        refresh: isEnglish ? 'Refresh quote' : '刷新行情',
        news: isEnglish ? 'Read news' : '看资讯',
        peers: isEnglish ? 'Compare peers' : '看同业',
        kline: isEnglish ? 'Inspect K-line' : '看K线',
      },
    };
  }, [basicFreeReport, basicQuoteTrustPanel, basicSnapshot, uiLanguage]);
  const basicVisualAnalystPage = useMemo(() => {
    if (!basicSnapshot || !basicFreeReport) {
      return null;
    }
    const isEnglish = uiLanguage === 'en';
    const indicators = basicSnapshot.indicators || {};
    const currentPrice = toFiniteBasicNumber(basicSnapshot.quote.currentPrice);
    const changePercent = toFiniteBasicNumber(basicSnapshot.quote.changePercent);
    const ma5 = toFiniteBasicNumber(pickBasicIndicator(indicators, 'ma5', 'MA5'));
    const ma20 = toFiniteBasicNumber(pickBasicIndicator(indicators, 'ma20', 'MA20'));
    const prevClose = toFiniteBasicNumber(basicSnapshot.quote.prevClose);
    const openPrice = toFiniteBasicNumber(basicSnapshot.quote.open);
    const highPrice = toFiniteBasicNumber(basicSnapshot.quote.high);
    const lowPrice = toFiniteBasicNumber(basicSnapshot.quote.low);
    const volumeChange = toFiniteBasicNumber(pickBasicIndicator(indicators, 'volumeChangeVsMa5', 'volume_change_vs_ma5'));
    const volumeMa5 = toFiniteBasicNumber(pickBasicIndicator(indicators, 'volumeMa5', 'volume_ma5'));
    const trendPoints = basicSnapshot.trend?.points ?? [];
    const fallbackTrendPoints = uniqueBasicLevels([prevClose, ma20, ma5, currentPrice])
      .map((close) => ({ close }));
    const sparkline = basicFreeReport.miniChart.sparkline
      || buildBasicSparkline(trendPoints.length >= 2 ? trendPoints : fallbackTrendPoints);
    const supportCandidates = uniqueBasicLevels([lowPrice, ma20, ma5, prevClose, openPrice]);
    const resistanceCandidates = uniqueBasicLevels([highPrice, openPrice, prevClose, ma5, ma20]);
    const supportNumber = currentPrice !== null
      ? supportCandidates.filter((level) => level <= currentPrice).sort((left, right) => right - left)[0] ?? null
      : supportCandidates.sort((left, right) => right - left)[0] ?? null;
    const resistanceNumber = currentPrice !== null
      ? resistanceCandidates.filter((level) => level >= currentPrice).sort((left, right) => left - right)[0] ?? null
      : resistanceCandidates.sort((left, right) => left - right)[0] ?? null;
    const rawVolumes = trendPoints
      .map((point) => ({
        label: String(point.date || '').slice(5) || (isEnglish ? 'day' : '日期'),
        value: toFiniteBasicNumber(point.volume),
      }))
      .filter((point): point is { label: string; value: number } => point.value !== null)
      .slice(-8);
    const fallbackVolumes = [
      volumeMa5 !== null ? { label: 'MA5', value: volumeMa5 } : null,
      toFiniteBasicNumber(basicSnapshot.quote.volume) !== null
        ? { label: isEnglish ? 'Now' : '当前', value: toFiniteBasicNumber(basicSnapshot.quote.volume) as number }
        : null,
    ].filter((point): point is { label: string; value: number } => Boolean(point));
    const volumeSource = rawVolumes.length >= 2 ? rawVolumes : fallbackVolumes;
    const maxVolume = Math.max(...volumeSource.map((point) => point.value), 1);
    const volumeBars = volumeSource.map((point, index) => ({
      ...point,
      height: Math.max(18, Math.round((point.value / maxVolume) * 100)),
      isLatest: index === volumeSource.length - 1,
    }));
    const trendStatus = currentPrice !== null && ma20 !== null
      ? currentPrice >= ma20
        ? (isEnglish ? 'Above MA20' : '站上 MA20')
        : (isEnglish ? 'Below MA20' : '低于 MA20')
      : (isEnglish ? 'MA20 incomplete' : 'MA20 不完整');
    const volumeStatus = volumeChange !== null
      ? volumeChange >= 20
        ? (isEnglish ? 'Volume expanding' : '量能放大')
        : volumeChange <= -20
          ? (isEnglish ? 'Volume shrinking' : '量能收缩')
          : (isEnglish ? 'Volume neutral' : '量能中性')
      : (isEnglish ? 'Volume incomplete' : '量能不完整');
    const scoreLabel = basicFreeReport.score >= 70
      ? (isEnglish ? 'Constructive' : '偏积极')
      : basicFreeReport.score >= 55
        ? (isEnglish ? 'Watchable' : '可观察')
        : (isEnglish ? 'Verify first' : '先复核');
    const nextStep = basicSnapshot.quote.freshness !== 'fresh'
      ? (isEnglish ? 'Refresh quote first, then read the signal.' : '先刷新行情，再解读信号。')
      : basicFreeReport.score >= 70
        ? (isEnglish ? 'Compare peers and inspect K-line triggers.' : '继续对比同业，并查看 K线触发条件。')
        : (isEnglish ? 'Check risks and wait for stronger confirmation.' : '先看风险边界，等待更强确认。');
    const sourceLane = basicSnapshot.route?.dataSourceLane
      || basicSnapshot.route?.channel
      || basicSnapshot.diagnostics?.routeLane
      || basicSnapshot.quote.source
      || 'free_source';
    return {
      title: isEnglish ? 'Visual analyst page' : '可视化研判页',
      subtitle: isEnglish
        ? 'See the chart first, then read the conclusion: trend, volume, support/resistance, and the next broker-style step.'
        : '先看图，再读结论：趋势、量价、支撑压力和经纪人下一步一次看清。',
      boundary: isEnglish ? 'No AI, no quota' : '未用 AI，不扣额度',
      source: localizeGeneratedSource(sourceLane, uiLanguage),
      trendTitle: isEnglish ? 'Trend track' : '趋势轨道',
      volumeTitle: isEnglish ? 'Volume-price confirmation' : '量价确认',
      levelTitle: isEnglish ? 'Support / resistance' : '支撑压力',
      nextTitle: isEnglish ? 'Broker next step' : '经纪人下一步',
      freeTitle: isEnglish ? 'Visible in free' : '免费版可见',
      premiumTitle: isEnglish ? 'Premium improves' : '高级版增强',
      scoreLabel,
      scoreValue: `${basicFreeReport.score}/100`,
      conclusion: localizeGeneratedText(basicFreeReport.productBrief.conclusion, uiLanguage),
      priceValue: `${formatBasicNumber(currentPrice)} / ${formatSignedBasicPercent(changePercent)}`,
      trendStatus,
      trendDetail: currentPrice !== null && ma20 !== null
        ? (isEnglish ? `Last ${formatBasicNumber(currentPrice)}, MA20 ${formatBasicNumber(ma20)}.` : `最新价 ${formatBasicNumber(currentPrice)}，MA20 ${formatBasicNumber(ma20)}。`)
        : (isEnglish ? 'Refresh or wait for more history to complete moving-average context.' : '刷新或等待更多历史数据补齐均线背景。'),
      volumeStatus,
      volumeDetail: volumeChange !== null
        ? (isEnglish ? `Volume versus MA5 ${formatSignedBasicPercent(volumeChange)}.` : `成交量相对 MA5 ${formatSignedBasicPercent(volumeChange)}。`)
        : (isEnglish ? 'Volume history is not complete yet.' : '成交量历史暂不完整。'),
      supportText: supportNumber !== null
        ? formatBasicNumber(supportNumber)
        : localizeGeneratedText(basicFreeReport.productBrief.supportLevels, uiLanguage),
      resistanceText: resistanceNumber !== null
        ? formatBasicNumber(resistanceNumber)
        : localizeGeneratedText(basicFreeReport.productBrief.pressureLevels, uiLanguage),
      levelDetail: isEnglish
        ? `Support ${localizeGeneratedText(basicFreeReport.productBrief.supportLevels, uiLanguage)}; resistance ${localizeGeneratedText(basicFreeReport.productBrief.pressureLevels, uiLanguage)}.`
        : `支撑 ${localizeGeneratedText(basicFreeReport.productBrief.supportLevels, uiLanguage)}；压力 ${localizeGeneratedText(basicFreeReport.productBrief.pressureLevels, uiLanguage)}。`,
      nextStep,
      sparkline,
      volumeBars,
      freeItems: isEnglish
        ? ['Trend chart', 'Volume bars', 'Support/resistance', 'News and peers', 'Risk checklist']
        : ['趋势图', '量价条', '支撑压力', '资讯同业', '风险清单'],
      premiumItems: isEnglish
        ? ['Realtime API', 'Source links', 'Longer history', 'Model validation', 'Continuous alerts']
        : ['实时 API', '原文链接', '更长历史', '模型验证', '持续提醒'],
      actionLabels: {
        refresh: isEnglish ? 'Refresh quote' : '刷新行情',
        news: isEnglish ? 'Read news' : '看资讯',
        peers: isEnglish ? 'Compare peers' : '看同业',
        kline: isEnglish ? 'Inspect K-line' : '看K线',
      },
    };
  }, [basicFreeReport, basicSnapshot, uiLanguage]);
  const basicReadingRoadmap = useMemo(() => {
    if (!basicSnapshot || !basicFreeReport) {
      return null;
    }
    const isEnglish = uiLanguage === 'en';
    const signalScore = `${basicFreeReport.score}/100`;
    const freshness = localizeRuntimeLabel(basicSnapshot.quote.freshness || 'unavailable', uiLanguage);
    const support = localizeGeneratedText(basicFreeReport.productBrief.supportLevels, uiLanguage);
    const resistance = localizeGeneratedText(basicFreeReport.productBrief.pressureLevels, uiLanguage);
    const conclusion = localizeGeneratedText(basicFreeReport.productBrief.conclusion, uiLanguage);
    const firstRisk = localizeGeneratedText(
      basicFreeReport.productBrief.risks[0]
      || basicSnapshot.warnings?.[0]?.message
      || (isEnglish ? 'Use the free report as an observation checklist.' : '先把免费报告当作观察清单。'),
      uiLanguage,
    );
    const peerRows = basicSnapshot.intelligence?.peerComparison?.rows ?? [];
    const comparisonTargets = basicSnapshot.intelligence?.comparisonTargets ?? [];
    const peers = (peerRows.length > 0
      ? peerRows.slice(0, 3).map((row) => row.symbol || row.label)
      : comparisonTargets.slice(0, 3).map((item) => item.symbol || item.label))
      .filter((value): value is string => Boolean(value))
      .join(' / ');
    const klineDirection = localizeRuntimeLabel(
      basicSnapshot.intelligence?.klineForecast?.direction
      || basicSnapshot.intelligence?.klineForecast?.scenarios?.[0]?.direction
      || 'pending',
      uiLanguage,
    );
    return {
      title: isEnglish ? '3-minute reading route' : '3分钟研判路线',
      subtitle: isEnglish
        ? 'Use the free report in order: conclusion, visual evidence, source checks, then K-line scenarios.'
        : '按顺序读免费报告：先看结论，再看图形证据，再核对资讯同业，最后看 K线情景。',
      boundary: isEnglish ? 'No AI, no quota' : '未用 AI，不扣额度',
      freeTitle: isEnglish ? 'Free complete read' : '免费版可完整阅读',
      premiumTitle: isEnglish ? 'Premium adds data sources' : '高级版补数据源',
      freeDetail: isEnglish
        ? 'The visible reading path is open to guests and free users.'
        : '游客和免费用户都能完整阅读这条可见研判路径。',
      premiumDetail: isEnglish
        ? 'Premium changes source freshness, original links, model validation, and alert continuity.'
        : '高级版补实时源、原文链接、模型验证和持续提醒。',
      actionLabels: {
        news: isEnglish ? 'Read news' : '看资讯',
        peers: isEnglish ? 'Compare peers' : '看同业',
        kline: isEnglish ? 'Inspect K-line' : '看K线',
      },
      steps: [
        {
          title: isEnglish ? 'Step 1: Read conclusion' : '第一步：看结论',
          detail: isEnglish
            ? `${conclusion} Signal completeness ${signalScore}.`
            : `${conclusion} 信号完整度 ${signalScore}。`,
          tag: isEnglish ? 'first read' : '先定方向',
        },
        {
          title: isEnglish ? 'Step 2: Read visual evidence' : '第二步：看图形证据',
          detail: isEnglish
            ? `Trend, volume, support ${support}, resistance ${resistance}, freshness ${freshness}.`
            : `趋势、量价、支撑 ${support}、压力 ${resistance}、新鲜度 ${freshness}。`,
          tag: isEnglish ? 'chart proof' : '图形证据',
        },
        {
          title: isEnglish ? 'Step 3: Check news and peers' : '第三步：核对资讯与同业',
          detail: isEnglish
            ? `Check source lanes and compare ${peers || basicSnapshot.market.toUpperCase()} before reading this symbol alone.`
            : `先看来源通道，再与 ${peers || basicSnapshot.market.toUpperCase()} 对比，避免孤立解读。`,
          tag: isEnglish ? 'source check' : '来源复核',
        },
        {
          title: isEnglish ? 'Step 4: Inspect K-line scenarios' : '第四步：看K线情景',
          detail: isEnglish
            ? `Use ${klineDirection} and risk notes as a next-refresh checklist.`
            : `把 ${klineDirection} 和风险点作为下一次刷新检查清单。`,
          tag: isEnglish ? 'scenario' : '情景推演',
        },
      ],
      risks: [
        firstRisk,
        isEnglish ? 'Information analysis only, not investment advice.' : '仅作信息分析，不构成投资建议。',
      ],
    };
  }, [basicFreeReport, basicSnapshot, uiLanguage]);
  const basicFreeEventCenter = useMemo(() => {
    if (!basicSnapshot || !basicFreeReport) {
      return null;
    }
    const isEnglish = uiLanguage === 'en';
    const symbol = basicSnapshot.stockCode;
    const currentPrice = toFiniteBasicNumber(basicSnapshot.quote.currentPrice);
    const changePercent = toFiniteBasicNumber(basicSnapshot.quote.changePercent);
    const ma20 = toFiniteBasicNumber(pickBasicIndicator(basicSnapshot.indicators, 'ma20', 'MA20'));
    const volumeChange = toFiniteBasicNumber(pickBasicIndicator(
      basicSnapshot.indicators,
      'volumeChangeVsMa5',
      'volume_change_vs_ma5',
    ));
    const marketCap = basicSnapshot.profile?.marketCap;
    const peRatio = basicSnapshot.profile?.peRatio;
    const newsItems = (
      basicSnapshot.intelligence?.newsCenter?.items?.length
        ? basicSnapshot.intelligence.newsCenter.items
        : basicSnapshot.intelligence?.items ?? []
    ).slice(0, 3);
    const firstNews = newsItems[0] ?? null;
    const peerRows = basicSnapshot.intelligence?.peerComparison?.rows ?? [];
    const comparisonTargets = basicSnapshot.intelligence?.comparisonTargets ?? [];
    const peerLabels = (peerRows.length > 0
      ? peerRows.slice(0, 3).map((row) => row.symbol || row.label)
      : comparisonTargets.slice(0, 3).map((item) => item.symbol || item.label))
      .filter((value): value is string => Boolean(value));
    const profileContext = [
      basicSnapshot.profile?.sector,
      basicSnapshot.profile?.industry,
    ]
      .filter((value): value is string => Boolean(value))
      .map((value) => localizeGeneratedTerms(value, uiLanguage));
    const sourceLane = basicSnapshot.route?.dataSourceLane
      || basicSnapshot.route?.channel
      || basicSnapshot.diagnostics?.routeLane
      || `${basicSnapshot.market.toUpperCase()} market data`;
    const freshness = localizeRuntimeLabel(basicSnapshot.quote.freshness, uiLanguage);
    const movementText = changePercent !== null
      ? (isEnglish
          ? `${symbol} moved ${formatSignedBasicPercent(changePercent)}; first check whether the move is backed by trend, volume, and event context.`
          : `${symbol} 涨跌幅 ${formatSignedBasicPercent(changePercent)}；先看这次波动是否有趋势、量能和事件背景支撑。`)
      : (isEnglish
          ? `${symbol} has no change percentage yet; treat the event read as provisional.`
          : `${symbol} 暂无涨跌幅；先把事件解读当作临时观察清单。`);
    const trendText = currentPrice !== null && ma20 !== null
      ? currentPrice >= ma20
        ? (isEnglish ? `Price is above MA20 ${formatBasicNumber(ma20)}.` : `价格站上 MA20 ${formatBasicNumber(ma20)}。`)
        : (isEnglish ? `Price is below MA20 ${formatBasicNumber(ma20)}.` : `价格低于 MA20 ${formatBasicNumber(ma20)}。`)
      : (isEnglish ? 'MA20 context is incomplete.' : 'MA20 背景暂不完整。');
    const volumeText = volumeChange !== null
      ? (isEnglish
          ? `Volume is ${formatBasicPercent(Math.abs(volumeChange))} ${volumeChange >= 0 ? 'above' : 'below'} MA5.`
          : `成交量较 MA5 ${volumeChange >= 0 ? '增加' : '减少'} ${formatBasicPercent(Math.abs(volumeChange))}。`)
      : (isEnglish ? 'Volume confirmation is incomplete.' : '量能确认暂不完整。');
    const newsTitle = firstNews
      ? localizeGeneratedText(firstNews.title, uiLanguage)
      : (isEnglish ? 'No realtime headline configured' : '未配置实时标题源');
    const newsSummary = firstNews
      ? localizeGeneratedText(firstNews.summary, uiLanguage)
      : (isEnglish
          ? 'Free mode keeps the news lane visible and avoids public search cost.'
          : '免费模式保留资讯通道，但不启用公共搜索成本。');
    const profileValue = profileContext.length > 0
      ? profileContext.join(' / ')
      : localizeGeneratedSource(sourceLane, uiLanguage);
    const fundamentalDetail = [
      marketCap ? `${isEnglish ? 'market cap' : '总市值'} ${formatBasicNumber(marketCap)}` : '',
      peRatio ? `${isEnglish ? 'PE' : '市盈率'} ${formatBasicNumber(peRatio)}` : '',
    ].filter(Boolean).join(isEnglish ? '; ' : '；') || (isEnglish ? 'Profile fields are limited.' : '公司资料字段有限。');
    const peerValue = peerLabels.length > 0
      ? peerLabels.join(' / ')
      : (isEnglish ? 'Market reference pending' : '市场参照待补充');
    const peerDetail = peerLabels.length > 0
      ? (isEnglish ? 'Use peers to avoid reading one stock in isolation.' : '用同业/指数参照，避免只看单只股票。')
      : (isEnglish ? 'Premium can add sector and peer APIs.' : '高级版可补充板块和同业 API。');
    const localizedSourceLane = localizeGeneratedSource(sourceLane, uiLanguage);
    const quoteSourceStatus = isEnglish
      ? `${localizedSourceLane}; quote freshness ${freshness}.`
      : `${localizedSourceLane}；行情状态：${freshness}。`;
    const newsSourceStatus = firstNews
      ? `${localizeGeneratedSource(firstNews.source, uiLanguage)} · ${basicIntelligenceStatusLabel(firstNews.status, uiLanguage)}`
      : (isEnglish
          ? 'Realtime public search is not enabled in free mode.'
          : '免费模式未开启实时公共搜索。');
    const fundamentalSourceStatus = basicSnapshot.profile?.source
      ? `${localizeGeneratedSource(basicSnapshot.profile.source, uiLanguage)} · ${localizeRuntimeLabel(basicSnapshot.profile.freshness || 'available', uiLanguage)}`
      : (isEnglish ? 'Profile fields come from the current quick snapshot.' : '公司资料来自当前快速快照。');
    const peerSourceStatus = peerLabels.length > 0
      ? (isEnglish ? `Current references: ${peerValue}.` : `当前参照：${peerValue}。`)
      : (isEnglish ? 'Peer references are pending in the free quick snapshot.' : '免费快照里的同业参照仍待补充。');
    const timeline = [
      {
        label: isEnglish ? 'Price move' : '价格异动',
        detailTitle: isEnglish ? 'Price move' : '价格异动',
        value: currentPrice !== null
          ? `${formatBasicNumber(currentPrice)} / ${formatSignedBasicPercent(changePercent)}`
          : formatSignedBasicPercent(changePercent),
        detail: `${movementText} ${trendText} ${volumeText}`,
        sourceStatus: quoteSourceStatus,
        freeNext: isEnglish
          ? 'Recheck price, MA20, and volume together before reading the rest.'
          : '先复核价格、MA20 和量能是否同向，再看后面的事件。',
        premiumVerify: isEnglish
          ? 'Premium can compare multi-source quotes and volume history.'
          : '高级版可用多源 API 校验价格和成交量历史。',
      },
      {
        label: isEnglish ? 'News / filings' : '资讯/公告',
        detailTitle: isEnglish ? 'News / filings' : '资讯/公告',
        value: newsTitle,
        detail: newsSummary,
        sourceStatus: newsSourceStatus,
        freeNext: isEnglish
          ? 'Treat this lane as a source checklist before deeper reading.'
          : '把资讯/公告通道当作来源检查清单，先判断是否需要深挖。',
        premiumVerify: isEnglish
          ? 'View source status and original links.'
          : '查看来源状态与原文链接。',
      },
      {
        label: isEnglish ? 'Fundamental backdrop' : '基本面背景',
        detailTitle: isEnglish ? 'Fundamental backdrop' : '基本面背景',
        value: profileValue,
        detail: fundamentalDetail,
        sourceStatus: fundamentalSourceStatus,
        freeNext: isEnglish
          ? 'Check whether valuation and business background explain the move.'
          : '先看估值和公司背景是否能解释这次价格波动。',
        premiumVerify: isEnglish
          ? 'Premium can add financial APIs, filings, and transcript context.'
          : '高级版可补财务 API、公告原文和业绩会背景。',
      },
      {
        label: isEnglish ? 'Peer reference' : '同业参照',
        detailTitle: isEnglish ? 'Peer reference' : '同业参照',
        value: peerValue,
        detail: peerDetail,
        sourceStatus: peerSourceStatus,
        freeNext: isEnglish
          ? 'Compare relative strength against peers or indexes.'
          : '对照同业/指数强弱。',
        premiumVerify: isEnglish
          ? 'Premium can run sector, ETF, and peer-relative API checks.'
          : '高级版可做行业、ETF 和同业相对强弱 API 校验。',
      },
    ];
    const activeIndex = Math.min(Math.max(basicEventCenterActiveIndex, 0), timeline.length - 1);
    return {
      title: isEnglish ? 'Free news and event center' : '免费资讯与事件中心',
      subtitle: isEnglish
        ? 'Free mode turns price movement, news lanes, fundamentals, peers, and source freshness into one event checklist.'
        : '免费版把价格波动、资讯公告、基本面、同业参照和数据新鲜度合并成一张事件清单。',
      whyTitle: isEnglish ? 'Why it is worth checking today' : '为什么今天值得看',
      whyText: localizeGeneratedText(basicFreeReport.productBrief.conclusion, uiLanguage),
      noAiLabel: isEnglish ? 'No AI, no quota' : '未用 AI，不扣额度',
      sourceLabel: isEnglish ? 'Free web/local sources' : '免费网络/本地源',
      sourceValue: localizeGeneratedSource(sourceLane, uiLanguage),
      freshnessLabel: isEnglish ? 'Freshness' : '新鲜度',
      freshnessValue: freshness,
      timelineTitle: isEnglish ? 'Event timeline' : '事件时间线',
      detailTitle: isEnglish ? 'Event details' : '事件详情',
      sourceStatusLabel: isEnglish ? 'Source status' : '来源状态',
      freeNextLabel: isEnglish ? 'Free next step' : '免费版下一步',
      premiumVerifyLabel: isEnglish ? 'Premium verification' : '高级版验证',
      freeTitle: isEnglish ? 'Free can do now' : '免费版可立即做',
      premiumTitle: isEnglish ? 'Premium verifies further' : '高级版补充验证',
      boundary: isEnglish ? 'Information analysis only, not investment advice.' : '仅作信息分析，不构成投资建议。',
      timeline,
      activeItem: timeline[activeIndex],
      freeActions: isEnglish
        ? [
            'Read the price move together with MA20 and volume.',
            'Use the visible news/filing lane as a source checklist.',
            'Compare peers before deciding whether to go deeper.',
          ]
        : [
            '把价格波动、MA20 和量能放在一起看。',
            '把资讯/公告通道当作来源复核清单。',
            '先对照同业/指数，再决定是否深挖。',
          ],
      premiumActions: isEnglish
        ? ['Realtime news/API', 'Source links', 'Kronos/API model', 'Continuous tracking']
        : ['实时资讯/API', '来源链接', 'Kronos/API 模型', '持续跟踪'],
    };
  }, [basicEventCenterActiveIndex, basicFreeReport, basicSnapshot, uiLanguage]);
  const basicSourceRecoveryPanel = useMemo(() => {
    if (!basicSnapshot) {
      return null;
    }
    const isEnglish = uiLanguage === 'en';
    const quoteFreshnessRaw = String(
      basicSnapshot.quote.freshness
      || basicSnapshot.diagnostics?.freshness?.quote
      || '',
    ).toLowerCase();
    const historyFreshnessRaw = String(basicSnapshot.diagnostics?.freshness?.history || '').toLowerCase();
    const quoteCacheRaw = String(basicSnapshot.diagnostics?.cache?.quote || '').toLowerCase();
    const historyCacheRaw = String(basicSnapshot.diagnostics?.cache?.history || '').toLowerCase();
    const quoteFallbackRaw = String(basicSnapshot.diagnostics?.fallback?.quote || '').toLowerCase();
    const historyFallbackRaw = String(basicSnapshot.diagnostics?.fallback?.history || '').toLowerCase();
    const healthStatuses = Object.values(basicSnapshot.diagnostics?.sourceHealth ?? {})
      .map((item) => String(item?.status || '').toLowerCase())
      .filter(Boolean);
    const hasStaleOrCache = [
      quoteFreshnessRaw,
      historyFreshnessRaw,
      quoteCacheRaw,
      historyCacheRaw,
      quoteFallbackRaw,
      historyFallbackRaw,
    ].some((value) => (
      value.includes('stale')
      || value.includes('cache')
      || value.includes('cached')
      || value.includes('expired')
      || value === 'hit'
    ));
    const hasCooldown = healthStatuses.some((status) => status.includes('cool') || status.includes('down') || status.includes('fail'));
    const sourceLane = basicSnapshot.route?.dataSourceLane
      || basicSnapshot.route?.channel
      || basicSnapshot.diagnostics?.routeLane
      || `${basicSnapshot.market.toUpperCase()} market data`;
    const reasonCards = [
      {
        label: isEnglish ? 'Why stale/cache is shown' : '为什么提示过期/缓存',
        value: hasStaleOrCache
          ? (isEnglish ? 'Cache or stale fallback is active' : '缓存或过期兜底已启用')
          : (isEnglish ? 'Live path looks available' : '实时路径看起来可用'),
        detail: isEnglish
          ? `Quote ${localizeRuntimeLabel(quoteFreshnessRaw || 'unavailable', uiLanguage)}, cache ${localizeRuntimeLabel(quoteCacheRaw || 'unavailable', uiLanguage)}, fallback ${localizeRuntimeLabel(quoteFallbackRaw || 'unavailable', uiLanguage)}.`
          : `行情 ${localizeRuntimeLabel(quoteFreshnessRaw || 'unavailable', uiLanguage)}，缓存 ${localizeRuntimeLabel(quoteCacheRaw || 'unavailable', uiLanguage)}，兜底 ${localizeRuntimeLabel(quoteFallbackRaw || 'unavailable', uiLanguage)}。`,
      },
      {
        label: isEnglish ? 'Affected lane' : '受影响通道',
        value: marketLaneLabel(sourceLane, uiLanguage),
        detail: isEnglish
          ? `History ${localizeRuntimeLabel(historyFreshnessRaw || 'unavailable', uiLanguage)}; fallback ${localizeRuntimeLabel(historyFallbackRaw || 'unavailable', uiLanguage)}.`
          : `历史 ${localizeRuntimeLabel(historyFreshnessRaw || 'unavailable', uiLanguage)}；兜底 ${localizeRuntimeLabel(historyFallbackRaw || 'unavailable', uiLanguage)}。`,
      },
      {
        label: isEnglish ? 'Recovery priority' : '修复优先级',
        value: hasCooldown
          ? (isEnglish ? 'Wait or retry after cooldown' : '等待冷却或稍后重试')
          : hasStaleOrCache
            ? (isEnglish ? 'Refresh before interpreting' : '先刷新再解读')
            : (isEnglish ? 'Normal monitoring' : '正常观察'),
        detail: isEnglish
          ? 'Free mode keeps usable cached data visible instead of blocking the whole report.'
          : '免费版会保留可用缓存数据，不会因为单个来源慢就让整份报告不可用。',
      },
    ];
    const freeActions = [
      isEnglish ? 'Click refresh live quote first' : '先点刷新实时行情',
      isEnglish ? 'Compare price, update time and moving averages before reading signals' : '对照价格、更新时间和均线后再读信号',
      isEnglish ? 'Retry later when network or proxy looks unstable' : '网络或代理异常时稍后重试',
      basicSnapshot.market === 'cn'
        ? (isEnglish ? 'For A-shares, compare the local rule lane with a-stock-data adapter' : 'A股可对照本地规则和 a-stock-data 适配通道')
        : (isEnglish ? 'Compare market ETF/index context before reading the stock alone' : '先对照指数/ETF 背景，不要只看单股'),
    ];
    const premiumItems = [
      isEnglish ? 'Multi-source API comparison' : '多源 API 对照',
      isEnglish ? 'Automatic prewarm and recovery' : '自动预热和恢复',
      isEnglish ? 'Abnormal price alert and audit trail' : '异常价格告警和审计轨迹',
      isEnglish ? 'Source links and realtime event feeds' : '原文链接和实时事件源',
    ];
    return {
      title: isEnglish ? 'Data source recovery guide' : '数据源修复建议',
      subtitle: isEnglish
        ? 'This panel turns stale/cache warnings into clear next actions so free users can still judge the snapshot.'
        : '把过期/缓存提示变成可执行步骤，让免费用户也知道下一步该怎么复核。',
      freeTitle: isEnglish ? 'Free mode can do now' : '免费版现在可做',
      premiumTitle: isEnglish ? 'Premium fills the gaps' : '高级版补齐',
      refreshLabel: isEnglish ? 'Refresh live quote' : '刷新实时行情',
      boundary: isEnglish ? 'Information analysis only, not investment advice.' : '仅作信息分析，不构成投资建议。',
      reasonCards,
      freeActions,
      premiumItems,
    };
  }, [basicSnapshot, uiLanguage]);
  const basicVerifiedDataBoard = useMemo(() => {
    if (!basicSnapshot) {
      return null;
    }
    const isEnglish = uiLanguage === 'en';
    const profile = basicSnapshot.profile;
    const sourceLane = basicSnapshot.route?.dataSourceLane
      || basicSnapshot.route?.channel
      || basicSnapshot.diagnostics?.routeLane
      || `${basicSnapshot.market.toUpperCase()} market data`;
    const sourceLabel = (source: unknown): string => {
      const raw = String(source ?? '');
      if (raw === 'yahoo_chart') {
        return isEnglish ? 'Yahoo chart data' : 'Yahoo 图表数据';
      }
      return localizeGeneratedSource(raw, uiLanguage);
    };
    const quoteFreshness = localizeRuntimeLabel(basicSnapshot.quote.freshness, uiLanguage);
    const profileFreshness = localizeRuntimeLabel(profile?.freshness || 'missing', uiLanguage);
    const cacheModes = [
      basicSnapshot.diagnostics?.cache?.quote,
      basicSnapshot.diagnostics?.cache?.history,
    ].filter((value): value is string => Boolean(value));
    const cacheValue = cacheModes.length > 0 && cacheModes.every((value) => value === 'miss')
      ? (isEnglish ? 'Live fetch' : '实时获取')
      : cacheModes.some((value) => value === 'hit')
        ? (isEnglish ? 'Cache hit' : '缓存命中')
        : localizeRuntimeLabel(cacheModes.join(' / ') || 'unavailable', uiLanguage);
    const sourceHealthItems = Object.values(basicSnapshot.diagnostics?.sourceHealth ?? {})
      .map((item) => localizeRuntimeLabel(item?.status || item?.source || '-', uiLanguage))
      .filter((value) => value && value !== '-');
    const sourceHealthValue = sourceHealthItems.length > 0
      ? Array.from(new Set(sourceHealthItems)).join(' / ')
      : localizeRuntimeLabel('unavailable', uiLanguage);
    const trustCards = [
      {
        label: isEnglish ? 'Quote source' : '行情源',
        value: `${sourceLabel(basicSnapshot.quote.source)} / ${quoteFreshness}`,
        detail: isEnglish
          ? 'Price, change, volume, moving-average context and refresh state are shown together.'
          : '行情、涨跌、成交量、均线背景和刷新状态放在一起看。',
      },
      {
        label: isEnglish ? 'Company profile source' : '公司资料源',
        value: `${sourceLabel(profile?.source)} / ${profileFreshness}`,
        detail: isEnglish
          ? 'Sector, industry and valuation fields explain what the price is being compared against.'
          : '板块、行业和估值字段用于解释价格处在什么背景里。',
      },
      {
        label: isEnglish ? 'Cache state' : '缓存状态',
        value: cacheValue,
        detail: isEnglish
          ? `Lane ${marketLaneLabel(sourceLane, uiLanguage)}; free mode keeps speed high with cache-aware fallback.`
          : `通道 ${marketLaneLabel(sourceLane, uiLanguage)}；免费版用缓存感知降级保证速度。`,
      },
      {
        label: isEnglish ? 'Source health' : '来源健康',
        value: sourceHealthValue,
        detail: isEnglish
          ? 'Treat degraded or stale sources as provisional until the next refresh.'
          : '来源降级或行情过期时，先当作临时参考，刷新后再解读。',
      },
    ];
    const financialMetrics = [
      {
        label: isEnglish ? 'Market cap' : '总市值',
        value: formatBasicCompactNumber(profile?.marketCap),
        detail: isEnglish ? 'Company size baseline' : '先判断公司体量',
      },
      {
        label: isEnglish ? 'PE ratio' : '市盈率',
        value: formatBasicNumber(profile?.peRatio),
        detail: isEnglish ? 'Profit valuation reference' : '盈利估值参考',
      },
      {
        label: isEnglish ? 'PB ratio' : '市净率',
        value: formatBasicNumber(profile?.pbRatio),
        detail: isEnglish ? 'Book valuation reference' : '账面估值参考',
      },
      {
        label: isEnglish ? 'Dividend yield' : '股息率',
        value: formatBasicPercent(profile?.dividendYield),
        detail: isEnglish ? 'Shareholder return context' : '股东回报背景',
      },
      {
        label: isEnglish ? 'Revenue' : '营收',
        value: formatBasicCompactNumber(profile?.revenue),
        detail: isEnglish ? 'Business scale context' : '业务规模背景',
      },
      {
        label: isEnglish ? 'Net profit' : '净利润',
        value: formatBasicCompactNumber(profile?.netProfit),
        detail: isEnglish ? 'Profit quality context' : '盈利质量背景',
      },
    ];
    const peerCandidates = [
      ...(basicSnapshot.intelligence?.peerComparison?.rows ?? []).map((row) => ({
        symbol: row.symbol,
        label: row.label,
        role: row.role,
        currentSignal: row.currentSignal,
        compareNext: row.compareNext,
        referenceQuote: row.referenceQuote,
      })),
      ...(basicSnapshot.intelligence?.comparisonTargets ?? []).map((item) => ({
        symbol: item.symbol,
        label: item.label,
        role: item.status,
        currentSignal: item.reason,
        compareNext: item.source,
        referenceQuote: item.referenceQuote,
      })),
    ];
    const seenPeers = new Set<string>();
    const peerRows = peerCandidates
      .filter((row) => {
        const key = row.symbol || row.label;
        if (!key || seenPeers.has(key)) {
          return false;
        }
        seenPeers.add(key);
        return true;
      })
      .slice(0, 5)
      .map((row) => {
        const quoteValue = row.referenceQuote
          ? `${formatBasicNumber(row.referenceQuote.currentPrice ?? row.referenceQuote.price)} / ${formatSignedBasicPercent(row.referenceQuote.changePercent)}`
          : (isEnglish ? 'Reference relation' : '参照关系');
        return {
          symbol: row.symbol || row.label,
          label: localizeGeneratedText(row.label, uiLanguage),
          role: localizeGeneratedText(row.role, uiLanguage),
          quoteValue,
          currentSignal: localizeGeneratedText(row.currentSignal, uiLanguage),
          compareNext: localizeGeneratedText(row.compareNext, uiLanguage),
        };
      });
    const newsItems = (
      basicSnapshot.intelligence?.newsCenter?.items?.length
        ? basicSnapshot.intelligence.newsCenter.items
        : basicSnapshot.intelligence?.items ?? []
    ).slice(0, 4);
    const newsCards = (newsItems.length > 0 ? newsItems : [
      {
        category: 'news',
        title: isEnglish ? 'News lane' : '资讯通道',
        summary: isEnglish ? 'Realtime public news is not enabled in free local mode.' : '免费本地模式暂未开启实时公共资讯。',
        status: 'degraded',
        source: 'free_rules',
        action: isEnglish ? 'Use configured feeds or deep mode for links.' : '需要链接时使用配置资讯源或深度模式。',
      },
      {
        category: 'announcements',
        title: isEnglish ? 'Filings lane' : '公告/文件通道',
        summary: isEnglish ? 'Filings and source links are reserved for configured feeds.' : '公告原文和来源链接留给已配置数据源。',
        status: 'degraded',
        source: 'free_rules',
        action: isEnglish ? 'Upgrade or configure a source before treating it as complete.' : '升级或配置来源后再当作完整信息。',
      },
    ]).map((item) => {
      const actionText = 'action' in item ? item.action : '';
      return {
        category: localizeGeneratedText(item.category, uiLanguage),
        title: localizeGeneratedText(item.title, uiLanguage),
        summary: localizeGeneratedText(item.summary, uiLanguage),
        status: basicIntelligenceStatusLabel(item.status, uiLanguage),
        source: sourceLabel(item.source),
        action: localizeGeneratedText(actionText, uiLanguage),
      };
    });
    return {
      title: isEnglish ? 'Verified free data' : '真实数据增强',
      subtitle: isEnglish
        ? 'Free mode now exposes the data chain behind the snapshot: source, freshness, peers, fundamentals and event lanes.'
        : '免费版把快照背后的数据链路直接展开：来源、新鲜度、同业、财务和资讯公告通道都能先看。',
      trustTitle: isEnglish ? 'Data credibility' : '数据可信度',
      peerTitle: isEnglish ? 'Peer and sector live context' : '同业/板块实况',
      financialTitle: isEnglish ? 'Financial basics' : '财务基础',
      newsTitle: isEnglish ? 'News and filings status' : '资讯/公告状态',
      freeLabel: isEnglish ? 'Free uses public/local sources' : '免费版使用公开/本地源',
      premiumLabel: isEnglish ? 'Premium uses APIs and source links' : '高级版使用 API 和原文链接',
      boundary: isEnglish ? 'Information analysis only, not investment advice.' : '仅作信息分析，不构成投资建议。',
      trustCards,
      financialMetrics,
      peerRows,
      newsCards,
    };
  }, [basicSnapshot, uiLanguage]);
  const basicEventRadar = useMemo(() => {
    if (!basicSnapshot || !basicFreeReport) {
      return null;
    }
    const isEnglish = uiLanguage === 'en';
    const symbol = basicSnapshot.stockCode;
    const changePercent = toFiniteBasicNumber(basicSnapshot.quote.changePercent);
    const currentPrice = toFiniteBasicNumber(basicSnapshot.quote.currentPrice);
    const ma20 = toFiniteBasicNumber(pickBasicIndicator(basicSnapshot.indicators, 'ma20', 'MA20'));
    const volumeChange = toFiniteBasicNumber(pickBasicIndicator(
      basicSnapshot.indicators,
      'volumeChangeVsMa5',
      'volume_change_vs_ma5',
    ));
    const comparisonPeerLabels = (basicSnapshot.intelligence?.comparisonTargets ?? [])
      .map((item) => item.symbol || item.label)
      .filter((value): value is string => Boolean(value));
    const routePeerLabels = (basicSnapshot.intelligence?.peerComparison?.rows ?? [])
      .map((row) => row.symbol || row.label)
      .filter((value): value is string => Boolean(value));
    const peerLabels = Array.from(new Set(
      (comparisonPeerLabels.length > 0 ? comparisonPeerLabels : routePeerLabels),
    )).slice(0, 2);
    const movementDirection = changePercent === null || changePercent === 0
      ? (isEnglish ? 'flat' : '震荡')
      : changePercent > 0
        ? (isEnglish ? 'rose' : '上涨')
        : (isEnglish ? 'fell' : '下跌');
    const movementText = changePercent === null
      ? (isEnglish ? `${symbol} has no change data yet` : `${symbol} 暂无涨跌幅数据`)
      : isEnglish
        ? `${symbol} ${movementDirection} ${formatBasicPercent(Math.abs(changePercent))}`
        : `${symbol} ${movementDirection} ${formatBasicPercent(Math.abs(changePercent))}`;
    const ma20Text = currentPrice !== null && ma20 !== null
      ? currentPrice >= ma20
        ? (isEnglish ? `Price is above MA20 ${formatBasicNumber(ma20)}` : `价格站上 MA20 ${formatBasicNumber(ma20)}`)
        : (isEnglish ? `Price is below MA20 ${formatBasicNumber(ma20)}` : `价格跌破 MA20 ${formatBasicNumber(ma20)}`)
      : (isEnglish ? 'MA20 context is incomplete' : 'MA20 背景暂不完整');
    const volumeText = volumeChange !== null
      ? volumeChange >= 0
        ? (isEnglish ? `Volume is ${formatBasicPercent(volumeChange)} above MA5` : `成交量较 MA5 增加 ${formatBasicPercent(volumeChange)}`)
        : (isEnglish ? `Volume is ${formatBasicPercent(Math.abs(volumeChange))} below MA5` : `成交量较 MA5 减少 ${formatBasicPercent(Math.abs(volumeChange))}`)
      : (isEnglish ? 'Volume confirmation is incomplete' : '量能确认暂不完整');
    const freshnessText = localizeRuntimeLabel(basicSnapshot.quote.freshness, uiLanguage);
    const dataText = isEnglish
      ? `Quote freshness: ${freshnessText}`
      : `行情新鲜度：${freshnessText}`;
    const supportText = localizeGeneratedText(basicFreeReport.productBrief.supportLevels, uiLanguage);
    const resistanceText = localizeGeneratedText(basicFreeReport.productBrief.pressureLevels, uiLanguage);
    const peerText = peerLabels.length > 0 ? peerLabels.join(' / ') : (isEnglish ? 'market reference' : '市场参照');
    const events = [
      {
        title: isEnglish ? 'Trend event' : '趋势事件',
        status: currentPrice !== null && ma20 !== null && currentPrice >= ma20
          ? (isEnglish ? 'positive' : '偏强')
          : (isEnglish ? 'watch' : '观察'),
        value: ma20Text,
        detail: isEnglish
          ? 'Read price location first, then confirm whether the next refresh keeps the same structure.'
          : '先看价格位置，再确认下一次刷新是否维持同样结构。',
      },
      {
        title: isEnglish ? 'Volume event' : '量能事件',
        status: volumeChange !== null && volumeChange > 0
          ? (isEnglish ? 'confirming' : '确认中')
          : (isEnglish ? 'weak' : '偏弱'),
        value: volumeText,
        detail: isEnglish
          ? 'Volume is only confirmation; do not read it without price and freshness.'
          : '量能只做确认项，不能脱离价格位置和数据新鲜度单独解读。',
      },
      {
        title: isEnglish ? 'Data event' : '数据事件',
        status: freshnessText,
        value: dataText,
        detail: isEnglish
          ? 'Refresh stale or cached data before comparing intraday moves.'
          : '如果是过期或缓存行情，先刷新，再比较日内波动。',
      },
    ];
    const whyLines = [
      movementText,
      ma20Text,
      volumeText,
      isEnglish ? `Compare against ${peerText} before reading it alone.` : `不要孤立解读，继续对比 ${peerText}。`,
    ];
    const nextSteps = [
      isEnglish ? 'Refresh quote once and check freshness again.' : '刷新一次行情，重新确认数据新鲜度。',
      isEnglish ? `Keep comparing ${peerText}.` : `继续对比 ${peerText}。`,
      isEnglish ? `Watch support ${supportText} and resistance ${resistanceText}.` : `观察支撑 ${supportText} 和压力 ${resistanceText} 是否被突破或跌破。`,
      isEnglish ? 'Use deep analysis when source links or filings are needed.' : '需要新闻公告原文时，再使用深度分析。',
    ];
    return {
      title: isEnglish ? 'Event radar' : '事件雷达',
      subtitle: isEnglish
        ? 'A no-AI event read that turns price, MA20, volume, freshness and peers into a next-step checklist.'
        : '不用 AI，把涨跌、MA20、量能、新鲜度和同业参照整理成下一步观察清单。',
      whyTitle: isEnglish ? 'Why it moved' : '为什么涨跌',
      eventTitle: isEnglish ? 'Key events' : '关键事件',
      nextTitle: isEnglish ? 'Next watchlist' : '下一步观察',
      upgradeTitle: isEnglish ? 'Premium fills in' : '高级版补齐',
      boundary: isEnglish ? 'Information analysis only, not investment advice.' : '仅作信息分析，不构成投资建议。',
      whyLines,
      events,
      nextSteps,
      upgradeItems: isEnglish
        ? ['Realtime news/API', 'Filing source links', 'Kronos/API model', 'Continuous alerts']
        : ['实时新闻/API', '公告原文链接', 'Kronos/API 模型', '持续跟踪提醒'],
      score: `${basicFreeReport.score}/100`,
      movementText,
    };
  }, [basicFreeReport, basicSnapshot, uiLanguage]);
  const basicCommercialJourney = useMemo(() => {
    if (!basicSnapshot || !basicFreeReport) {
      return null;
    }
    const isEnglish = uiLanguage === 'en';
    const sourceLane = basicSnapshot.route?.dataSourceLane
      || basicSnapshot.route?.channel
      || basicSnapshot.diagnostics?.routeLane
      || `${basicSnapshot.market.toUpperCase()} market data`;
    return {
      title: isEnglish ? 'Free query journey' : '免费查询完整路径',
      subtitle: isEnglish
        ? 'Free mode already shows the same visible research flow. Premium changes the data source and model depth, not the page structure.'
        : '免费版已开放同样的研究流程；高级版只换数据源和模型深度，不把核心页面结构藏起来。',
      badges: [
        isEnglish ? 'Guest query works' : '不登录也能查',
        basicSnapshot.aiUsed ? localizeRuntimeLabel('AI used', uiLanguage) : t('home.noAi'),
        isEnglish ? 'Free web source' : '免费网络源',
        localizeGeneratedSource(sourceLane, uiLanguage),
      ],
      steps: [
        {
          title: isEnglish ? 'Read the conclusion first' : '先看结论',
          body: isEnglish
            ? `${localizeGeneratedText(basicFreeReport.productBrief.conclusion, uiLanguage)} Check support and resistance before reading the rest.`
            : `${localizeGeneratedText(basicFreeReport.productBrief.conclusion, uiLanguage)} 先看支撑压力，再继续读研究模块。`,
        },
        {
          title: isEnglish ? 'Then inspect research' : '再看研究',
          body: isEnglish
            ? 'Quote, technicals, news, K-line, peers, and risk are visible in free mode.'
            : '行情、技术、资讯、K线、同业、风险这些模块免费版都能先看。',
        },
        {
          title: isEnglish ? 'Decide whether to go deep' : '最后决定是否深度分析',
          body: isEnglish
            ? 'Use deep analysis only when you need longer news, filings, fundamentals, or model reasoning.'
            : '只有需要更长资讯、公告、基本面或模型推理时，再点深度分析。',
        },
      ],
      upgradeTitle: isEnglish ? 'Premium changes data sources' : '高级版只换数据源',
      upgradeItems: isEnglish
        ? ['Realtime news API', 'Filings / SEC API', 'Kronos / API model', 'My API']
        : ['实时新闻 API', '公告/SEC API', 'Kronos/API 模型', '我的 API'],
      moduleText: isEnglish
        ? 'quote, technicals, news, K-line, peers, risk'
        : '行情、技术、资讯、K线、同业、风险',
    };
  }, [basicFreeReport, basicSnapshot, t, uiLanguage]);
  const basicDataDepthBoard = useMemo(() => {
    if (!basicSnapshot || !basicFreeReport) {
      return null;
    }
    const isEnglish = uiLanguage === 'en';
    const market = basicSnapshot.market.toLowerCase();
    const isAShare = market === 'cn' || market === 'a_share' || market === 'a-share';
    const isUs = market === 'us';
    const isHk = market === 'hk';
    const isCrypto = market === 'crypto';
    const sourceLane = basicSnapshot.route?.dataSourceLane
      || basicSnapshot.route?.channel
      || basicSnapshot.diagnostics?.routeLane
      || `${basicSnapshot.market.toUpperCase()} market data`;
    const newsItems = (basicSnapshot.intelligence?.newsCenter?.items ?? basicSnapshot.intelligence?.items ?? [])
      .slice(0, 4);
    const peerRows = basicSnapshot.intelligence?.peerComparison?.rows ?? [];
    const comparisonTargets = basicSnapshot.intelligence?.comparisonTargets ?? [];
    const peerLabels = (peerRows.length > 0
      ? peerRows.slice(0, 3).map((row) => row.symbol || row.label)
      : comparisonTargets.slice(0, 3).map((item) => item.symbol || item.label))
      .filter((value): value is string => Boolean(value));
    const profileContext = [
      basicSnapshot.profile?.sector,
      basicSnapshot.profile?.industry,
    ].filter((value): value is string => Boolean(value));
    const currentPrice = toFiniteBasicNumber(basicSnapshot.quote.currentPrice);
    const ma20 = toFiniteBasicNumber(pickBasicIndicator(basicSnapshot.indicators, 'ma20', 'MA20'));
    const forecastSupport = toFiniteBasicNumber(basicSnapshot.intelligence?.klineForecast?.support);
    const forecastResistance = toFiniteBasicNumber(basicSnapshot.intelligence?.klineForecast?.resistance);
    const supportValue = forecastSupport !== null
      ? formatBasicNumber(forecastSupport)
      : localizeGeneratedText(basicFreeReport.productBrief.supportLevels, uiLanguage);
    const resistanceValue = forecastResistance !== null
      ? formatBasicNumber(forecastResistance)
      : localizeGeneratedText(basicFreeReport.productBrief.pressureLevels, uiLanguage);
    const marketTitle = isAShare
      ? (isEnglish ? 'A-share key data' : 'A股重点数据')
      : isUs
        ? (isEnglish ? 'US equity key data' : '美股重点数据')
        : isHk
          ? (isEnglish ? 'HK equity key data' : '港股重点数据')
          : isCrypto
            ? (isEnglish ? 'Crypto key data' : '加密货币重点数据')
            : (isEnglish ? 'Market key data' : '市场重点数据');
    const sectorText = profileContext.length > 0
      ? profileContext.map((value) => localizeGeneratedTerms(value, uiLanguage)).join(' / ')
      : localizeGeneratedSource(sourceLane, uiLanguage);
    const eventPoints = newsItems.length > 0
      ? newsItems.map((item) => localizeGeneratedText(item.title, uiLanguage))
      : [
          isEnglish ? 'News lane' : '资讯通道',
          isEnglish ? 'Filings lane' : '公告通道',
          isEnglish ? 'Financial snapshot lane' : '财务快照通道',
        ];
    const riskPoints = [
      ...(basicFreeReport.productBrief.risks ?? []).slice(0, 2).map((risk) => localizeGeneratedText(risk, uiLanguage)),
      ...(basicSnapshot.warnings ?? []).slice(0, 2).map((warning) => localizeGeneratedText(warning.message, uiLanguage)),
      localizeGeneratedText(basicSnapshot.intelligence?.boundary || 'not investment advice', uiLanguage),
    ].filter(Boolean);
    const eventAction = (category: string, action?: string | null): string => {
      if (!isEnglish && category === 'news') {
        return '使用深度分析或配置资讯源';
      }
      return localizeGeneratedText(action || (isEnglish ? 'Check the source before interpreting.' : '解读前先确认来源。'), uiLanguage);
    };
    const eventDetails = newsItems.length > 0
      ? [
          isEnglish ? 'Event checklist' : '事件清单',
          ...newsItems.map((item) => (
            isEnglish
              ? `${localizeGeneratedText(item.title, uiLanguage)}: ${localizeGeneratedText(item.summary, uiLanguage)} Status: ${basicIntelligenceStatusLabel(item.status, uiLanguage)}. Next: ${eventAction(item.category)}.`
              : `${localizeGeneratedText(item.title, uiLanguage)}：${localizeGeneratedText(item.summary, uiLanguage)} 状态：${basicIntelligenceStatusLabel(item.status, uiLanguage)}。下一步：${eventAction(item.category)}。`
          )),
        ]
      : [
          isEnglish ? 'Event checklist' : '事件清单',
          isEnglish ? 'No realtime event source is enabled in free mode.' : '免费模式暂未启用实时事件源。',
        ];
    const fallbackPeerRows = (() => {
      const changeText = formatSignedBasicPercent(basicSnapshot.quote.changePercent);
      const trendText = currentPrice !== null && ma20 !== null && currentPrice >= ma20
        ? (isEnglish ? 'above MA20' : '高于 MA20')
        : (isEnglish ? 'below or near MA20' : '低于或接近 MA20');
      const currentSignal = isEnglish
        ? `${basicSnapshot.stockCode} is ${trendText} with ${changeText}; compare before reading it alone.`
        : `${basicSnapshot.stockCode} 当前${trendText}，涨跌幅 ${changeText}；解读前先做市场参照。`;
      const compareNext = isEnglish
        ? 'Refresh and compare relative strength again.'
        : '下次刷新时再比较相对强弱。';
      const rows = isAShare
        ? [
            { symbol: '000300.SH', label: isEnglish ? 'CSI 300' : '沪深300', role: isEnglish ? 'Broad market' : '大盘' },
            { symbol: '000001.SH', label: isEnglish ? 'SSE Composite' : '上证指数', role: isEnglish ? 'Index lens' : '指数参照' },
          ]
        : isUs
          ? [
              { symbol: 'QQQ', label: 'QQQ', role: isEnglish ? 'Broad market' : '大盘' },
              { symbol: '^IXIC', label: isEnglish ? 'Nasdaq Composite' : '纳斯达克综合指数', role: isEnglish ? 'Index lens' : '指数参照' },
              { symbol: 'XLK', label: isEnglish ? 'Technology sector ETF' : '科技行业 ETF', role: isEnglish ? 'Sector lens' : '行业参照' },
            ]
          : isHk
            ? [
                { symbol: '^HSI', label: isEnglish ? 'Hang Seng Index' : '恒生指数', role: isEnglish ? 'Broad market' : '大盘' },
                { symbol: '2800.HK', label: isEnglish ? 'Tracker Fund of Hong Kong' : '盈富基金', role: isEnglish ? 'Index lens' : '指数参照' },
              ]
            : isCrypto
              ? [
                  { symbol: 'ETH-USD', label: isEnglish ? 'Ethereum' : '以太坊', role: isEnglish ? 'Peer asset' : '同类资产' },
                  { symbol: 'BTC-USD', label: isEnglish ? 'Bitcoin' : '比特币', role: isEnglish ? 'Crypto benchmark' : '加密参照' },
                ]
              : [
                  { symbol: basicSnapshot.stockCode, label: basicSnapshot.stockName || basicSnapshot.stockCode, role: isEnglish ? 'Reference' : '参照' },
                ];
      return rows.slice(0, 3).map((row) => ({
        ...row,
        currentSignal,
        compareNext,
      }));
    })();
    const peerTableRows = peerRows.length > 0
      ? peerRows.slice(0, 3).map((row) => ({
          symbol: row.symbol,
          label: localizeGeneratedText(row.label, uiLanguage),
          role: localizeGeneratedText(row.role, uiLanguage),
          currentSignal: localizeGeneratedText(row.currentSignal, uiLanguage),
          compareNext: localizeGeneratedText(row.compareNext, uiLanguage),
        }))
      : comparisonTargets.length > 0
        ? comparisonTargets.slice(0, 3).map((item) => ({
            symbol: item.symbol,
            label: localizeGeneratedText(item.label, uiLanguage),
            role: localizeGeneratedText(item.status, uiLanguage),
            currentSignal: localizeGeneratedText(item.reason, uiLanguage),
            compareNext: isEnglish ? 'Refresh and compare again.' : '刷新后再对比强弱。',
          }))
        : fallbackPeerRows;
    const fallbackKlineScenarios = [
      {
        label: isEnglish ? 'Trend checklist' : '趋势观察',
        probability: currentPrice !== null && ma20 !== null && currentPrice >= ma20 ? 68 : 48,
        trigger: ma20 !== null
          ? (isEnglish ? `Watch whether price can hold MA20 ${formatBasicNumber(ma20)}.` : `观察价格能否守住 MA20 ${formatBasicNumber(ma20)}。`)
          : (isEnglish ? 'Wait for moving-average context before interpreting the next bars.' : '等待均线数据补齐后再解读后续K线。'),
        detail: isEnglish
          ? 'Local free rules only; not model inference.'
          : '免费版本地规则预览，不是模型推理。',
      },
      {
        label: isEnglish ? 'Breakout confirmation' : '突破确认',
        probability: currentPrice !== null && ma20 !== null && currentPrice >= ma20 ? 64 : 42,
        trigger: resistanceValue !== '-'
          ? (isEnglish ? `Price closes above resistance ${resistanceValue} with volume confirmation.` : `价格放量收在压力位 ${resistanceValue} 上方。`)
          : (isEnglish ? 'Use the next refreshed high as resistance reference.' : '以下次刷新后的高点作为压力参照。'),
        detail: isEnglish
          ? 'Treat this as a next-refresh checklist, not a trading instruction.'
          : '把它作为下一次刷新时的检查清单，不是交易指令。',
      },
      {
        label: isEnglish ? 'Pullback risk' : '回落风险',
        probability: currentPrice !== null && ma20 !== null && currentPrice >= ma20 ? 32 : 58,
        trigger: supportValue !== '-'
          ? (isEnglish ? `Price loses support ${supportValue} or source freshness degrades.` : `价格跌破支撑 ${supportValue}，或数据新鲜度下降。`)
          : (isEnglish ? 'Source freshness or missing history weakens interpretation.' : '数据新鲜度下降或历史数据缺失会削弱解读。'),
        detail: isEnglish
          ? 'Recheck quote freshness and market reference before reading weakness.'
          : '解读走弱前，先复核行情新鲜度和市场参照。',
      },
    ];
    const backendKlineScenarios = (basicSnapshot.intelligence?.klineForecast?.scenarios ?? []).slice(0, 3).map((scenario) => ({
      label: localizeGeneratedText(scenario.label, uiLanguage),
      probability: scenario.probability,
      trigger: localizeGeneratedText(scenario.trigger, uiLanguage),
      detail: localizeGeneratedText(scenario.detail, uiLanguage),
    }));
    const klineScenarios = backendKlineScenarios.length > 0 ? backendKlineScenarios : fallbackKlineScenarios;
    const sameModulesText = isEnglish
      ? 'Free mode shows concrete data first. Premium can switch the same cards to API-backed news, filings, funds, and model sources.'
      : '免费版先展示可用的真实数据；高级版可把同样卡片切换到 API 资讯、公告、资金流和模型数据源。';
    return {
      title: isEnglish ? 'Free data depth board' : '免费版真实数据面板',
      marketTitle,
      subtitle: isEnglish
        ? `${basicSnapshot.stockCode} data board with quote, technical structure, events, peers, and risk boundaries.`
        : `${basicSnapshot.stockCode} 数据面板：行情、技术结构、资讯事件、同业参照和风险边界一起看。`,
      tags: [
        marketTitle,
        basicSnapshot.aiUsed ? localizeRuntimeLabel('AI used', uiLanguage) : t('home.noAi'),
        localizeGeneratedSource(sourceLane, uiLanguage),
        isEnglish ? 'same visible modules' : '免费/高级同页面结构',
      ],
      cards: [
        {
          key: 'core',
          title: isEnglish ? 'Core data' : '核心数据',
          summary: sectorText,
          metrics: [
            { label: isEnglish ? 'Last price' : '最新价', value: formatBasicNumber(basicSnapshot.quote.currentPrice) },
            { label: isEnglish ? 'Change' : '涨跌幅', value: formatSignedBasicPercent(basicSnapshot.quote.changePercent) },
            { label: isEnglish ? 'Volume' : '成交量', value: formatBasicCompactNumber(basicSnapshot.quote.volume) },
            { label: isEnglish ? 'Turnover' : '成交额', value: formatBasicCompactNumber(basicSnapshot.quote.amount) },
            { label: isEnglish ? 'Market cap' : '总市值', value: formatBasicCompactNumber(basicSnapshot.profile?.marketCap) },
            { label: isEnglish ? 'PE ratio' : '市盈率', value: formatBasicNumber(basicSnapshot.profile?.peRatio) },
          ],
          details: [
            `${isEnglish ? 'Open' : '开盘'} ${formatBasicNumber(basicSnapshot.quote.open)}`,
            `${isEnglish ? 'High' : '最高'} ${formatBasicNumber(basicSnapshot.quote.high)}`,
            `${isEnglish ? 'Low' : '最低'} ${formatBasicNumber(basicSnapshot.quote.low)}`,
            `${isEnglish ? 'Previous close' : '昨收'} ${formatBasicNumber(basicSnapshot.quote.prevClose)}`,
            `${isEnglish ? 'Exchange' : '交易所'} ${basicSnapshot.profile?.exchange || '-'}`,
            `${isEnglish ? 'Currency' : '币种'} ${basicSnapshot.profile?.currency || '-'}`,
            `${isEnglish ? 'Country' : '地区'} ${localizeGeneratedText(basicSnapshot.profile?.country || '-', uiLanguage)}`,
          ],
          peerRows: [],
          scenarios: [],
        },
        {
          key: 'technical',
          title: isEnglish ? 'Technical structure' : '技术结构',
          summary: localizeGeneratedText(basicFreeReport.productBrief.conclusion, uiLanguage),
          metrics: [
            { label: 'MA5', value: formatBasicNumber(pickBasicIndicator(basicSnapshot.indicators, 'ma5', 'MA5')) },
            { label: 'MA20', value: formatBasicNumber(pickBasicIndicator(basicSnapshot.indicators, 'ma20', 'MA20')) },
            { label: isEnglish ? '5d change' : '5日涨跌', value: formatSignedBasicPercent(pickBasicIndicator(basicSnapshot.indicators, 'priceChange5D', 'price_change_5d')) },
            { label: isEnglish ? '20d change' : '20日涨跌', value: formatSignedBasicPercent(pickBasicIndicator(basicSnapshot.indicators, 'priceChange20D', 'price_change_20d')) },
            { label: isEnglish ? 'Support' : '支撑', value: supportValue },
            { label: isEnglish ? 'Resistance' : '压力', value: resistanceValue },
          ],
          details: [
            `${isEnglish ? 'Volume signal' : '量价信号'} ${volumePriceSignalLabel(pickBasicIndicator(basicSnapshot.indicators, 'volumePriceSignal', 'volume_price_signal'), uiLanguage)}`,
            `${isEnglish ? 'Volume vs MA5' : '量能相对 MA5'} ${formatSignedBasicPercent(pickBasicIndicator(basicSnapshot.indicators, 'volumeChangeVsMa5', 'volume_change_vs_ma5'))}`,
            `${isEnglish ? 'Trend window' : '趋势窗口'} ${basicSnapshot.trend?.window ?? '-'}`,
            `${isEnglish ? 'Range low' : '区间低点'} ${formatBasicNumber(basicSnapshot.trend?.minClose)}`,
            `${isEnglish ? 'Range high' : '区间高点'} ${formatBasicNumber(basicSnapshot.trend?.maxClose)}`,
          ],
          peerRows: [],
          scenarios: klineScenarios,
        },
        {
          key: 'events',
          title: isEnglish ? 'Events and filings' : '资讯与事件',
          summary: basicSnapshot.intelligence?.newsCenter?.summary
            ? localizeGeneratedText(basicSnapshot.intelligence.newsCenter.summary, uiLanguage)
            : (isEnglish ? 'Free mode keeps event lanes visible without public search or AI.' : '免费模式保留资讯事件通道，但默认不启用公共搜索或 AI。'),
          metrics: eventPoints.map((point, index) => ({
            label: isEnglish ? `Lane ${index + 1}` : `通道 ${index + 1}`,
            value: point,
          })),
          details: eventDetails,
          peerRows: [],
          scenarios: [],
        },
        {
          key: 'peer-risk',
          title: isEnglish ? 'Peers and risks' : '同业与风险',
          summary: basicSnapshot.intelligence?.peerComparison?.summary
            ? localizeGeneratedText(basicSnapshot.intelligence.peerComparison.summary, uiLanguage)
            : (isEnglish ? 'Read the symbol against broad-market and sector references.' : '不要孤立看单只标的，先和大盘、行业或同业参照对比。'),
          metrics: [
            { label: isEnglish ? 'Peers' : '同业参照', value: peerLabels.length > 0 ? peerLabels.join(' / ') : basicSnapshot.stockCode },
            { label: isEnglish ? 'Signal score' : '信号完整度', value: `${basicFreeReport.score}/100` },
            { label: isEnglish ? 'Boundary' : '边界', value: isEnglish ? 'information analysis only' : '仅作信息分析，不构成投资建议' },
          ],
          points: riskPoints,
          details: riskPoints.length > 0
            ? riskPoints
            : [isEnglish ? 'Use this as a risk checklist, not a trading instruction.' : '把这里作为风险清单，不作为交易指令。'],
          peerRows: peerTableRows,
          scenarios: [],
        },
      ],
      footer: sameModulesText,
    };
  }, [basicFreeReport, basicSnapshot, t, uiLanguage]);
  const basicProfessionalOverview = useMemo(() => {
    if (!basicSnapshot || !basicFreeReport) {
      return null;
    }
    const isEnglish = uiLanguage === 'en';
    const sourceLane = basicSnapshot.route?.dataSourceLane
      || basicSnapshot.route?.channel
      || basicSnapshot.diagnostics?.routeLane
      || `${basicSnapshot.market.toUpperCase()} market data`;
    const hasDegradation = Boolean(
      basicSnapshot.degradation
        && basicSnapshot.degradation.status
        && basicSnapshot.degradation.status !== 'ok',
    );
    const warningCount = (basicSnapshot.warnings ?? [])
      .filter((warning) => warning.severity && warning.severity !== 'info')
      .length;
    const isFresh = basicSnapshot.quote.freshness === 'fresh';
    const riskLevel = basicFreeReport.score >= 75 && isFresh && !hasDegradation && warningCount === 0
      ? {
          label: isEnglish ? 'Low' : '低',
          tone: isEnglish ? 'Stable first read' : '首轮判断较稳',
        }
      : basicFreeReport.score >= 55 || (!hasDegradation && warningCount <= 1)
        ? {
            label: isEnglish ? 'Medium' : '中',
            tone: isEnglish ? 'Confirm freshness and volume' : '先确认新鲜度与量能',
          }
        : {
            label: isEnglish ? 'High' : '高',
            tone: isEnglish ? 'Repair data before reading' : '先修复数据再解读',
          };
    const sourceTone = hasDegradation || !isFresh || warningCount > 0
      ? (isEnglish ? 'some lanes degraded' : '部分通道降级')
      : (isEnglish ? 'public lanes available' : '公开通道可用');
    const moduleNav = [
      {
        label: isEnglish ? 'Quote overview' : '行情概览',
        detail: isEnglish ? 'price, change, MA, profile' : '价格、涨跌、均线、资料',
      },
      {
        label: isEnglish ? 'Technical view' : '技术面',
        detail: isEnglish ? 'trend, volume, support/resistance' : '趋势、量价、支撑压力',
      },
      {
        label: isEnglish ? 'News center' : '资讯中心',
        detail: isEnglish ? 'news, filings, fundamentals lanes' : '资讯、公告、财务通道',
      },
      {
        label: isEnglish ? 'K-line forecast' : 'K线预测',
        detail: isEnglish ? 'local rules or configured model' : '本地规则或已配置模型',
      },
    ];
    return {
      title: isEnglish ? 'Professional overview' : '专业速览',
      subtitle: isEnglish
        ? 'Free mode shows the full dashboard structure. Premium mode upgrades the same modules with API-backed data sources.'
        : '免费版展示完整看板结构；高级版在同样模块里切换到 API 数据源，提升实时性、稳定性和深度。',
      stats: [
        {
          label: isEnglish ? 'Trend score' : '趋势评分',
          value: `${basicFreeReport.score}/100`,
          detail: localizeGeneratedText(basicFreeReport.productBrief.conclusion, uiLanguage),
        },
        {
          label: isEnglish ? 'Risk level' : '风险等级',
          value: riskLevel.label,
          detail: riskLevel.tone,
        },
        {
          label: isEnglish ? 'Support / resistance' : '支撑 / 压力',
          value: `${localizeGeneratedText(basicFreeReport.productBrief.supportLevels, uiLanguage)} / ${localizeGeneratedText(basicFreeReport.productBrief.pressureLevels, uiLanguage)}`,
          detail: isEnglish ? 'quick-rule levels' : '免费规则价位',
        },
        {
          label: isEnglish ? 'Data channel' : '数据通道',
          value: isEnglish ? 'Free web source' : '免费网络源',
          detail: isEnglish
            ? `Premium API source available; current lane ${localizeGeneratedSource(sourceLane, uiLanguage)}.`
            : `高级 API 源可用；当前通道 ${localizeGeneratedSource(sourceLane, uiLanguage)}。`,
        },
      ],
      moduleNav,
      channels: [
        {
          label: isEnglish ? 'Free web source' : '免费网络源',
          detail: `${localizeGeneratedSource(sourceLane, uiLanguage)} · ${sourceTone}`,
        },
        {
          label: isEnglish ? 'Premium API source' : '高级 API 源',
          detail: isEnglish ? 'platform API, user API, or local model' : '平台 API、我的 API 或本地模型',
        },
      ],
    };
  }, [basicFreeReport, basicSnapshot, uiLanguage]);
  const basicFreeResearchBoard = useMemo(() => {
    if (!basicSnapshot || !basicFreeReport) {
      return null;
    }
    const isEnglish = uiLanguage === 'en';
    const newsCenter = basicSnapshot.intelligence?.newsCenter ?? null;
    const klineForecast = basicSnapshot.intelligence?.klineForecast ?? null;
    const peerRows = basicSnapshot.intelligence?.peerComparison?.rows ?? [];
    const comparisonTargets = basicSnapshot.intelligence?.comparisonTargets ?? [];
    const riskWatchPoints = (basicSnapshot.intelligence?.watchPoints ?? [])
      .filter((item) => item.category === 'risk')
      .map((item) => item.detail);
    const pullbackScenarios = (klineForecast?.scenarios ?? [])
      .filter((scenario) => scenario.direction === 'downside_risk')
      .map((scenario) => scenario.trigger);
    const newsItems = (newsCenter?.items ?? basicSnapshot.intelligence?.items ?? []).slice(0, 4);
    const peerLabels = peerRows.length > 0
      ? peerRows.slice(0, 3).map((row) => row.symbol || row.label)
      : comparisonTargets.slice(0, 3).map((item) => item.symbol || item.label);
    const profileContext = [basicSnapshot.profile?.sector, basicSnapshot.profile?.industry]
      .filter(Boolean)
      .map((value) => localizeGeneratedTerms(value, uiLanguage))
      .join(' / ');
    const riskLines = [
      ...basicFreeReport.productBrief.risks.slice(0, 2),
      newsCenter?.premiumUnlock,
      ...riskWatchPoints.slice(0, 1),
      ...pullbackScenarios.slice(0, 1),
      klineForecast?.boundary,
    ].filter((line): line is string => Boolean(line));
    return {
      title: isEnglish ? 'Free research board' : '免费研究看板',
      subtitle: isEnglish
        ? 'The same visible content is available in free mode; premium switches these lanes to API-backed data sources.'
        : '同样内容，高级版换用 API 数据源；免费版先用网络/本地公开源把可读结论展示出来。',
      channelTag: isEnglish ? 'No AI quick board' : '未用 AI 快速看板',
      cards: [
        {
          key: 'news',
          title: isEnglish ? 'Research radar' : '资讯雷达',
          headline: newsCenter
            ? localizeGeneratedText(newsCenter.title, uiLanguage)
            : (isEnglish ? 'Local information lanes' : '本地资讯通道'),
          body: newsCenter
            ? localizeGeneratedText(newsCenter.summary, uiLanguage)
            : (isEnglish ? 'Use free public/local lanes first; configure sources when realtime links are required.' : '先使用免费公开/本地通道；需要实时链接时再配置资讯源。'),
          points: newsItems.map((item) => localizeGeneratedText(item.title, uiLanguage)),
        },
        {
          key: 'kline',
          title: isEnglish ? 'K-line read' : 'K线推演',
          headline: klineForecast
            ? `${localizeGeneratedHorizon(klineForecast.horizon, uiLanguage)} · ${localizeGeneratedStatus(klineForecast.direction, uiLanguage)}`
            : (isEnglish ? 'Local rule preview' : '本地规则预览'),
          body: klineForecast
            ? localizeGeneratedText(klineForecast.adapterStatus, uiLanguage)
            : (isEnglish ? 'K-line preview waits for enough price history or configured model data.' : 'K线预览等待足够历史行情或已配置模型数据。'),
          points: [
            `${isEnglish ? 'Support' : '支撑'} ${formatBasicNumber(klineForecast?.support)}`,
            `${isEnglish ? 'Resistance' : '压力'} ${formatBasicNumber(klineForecast?.resistance)}`,
            ...(klineForecast?.scenarios ?? []).slice(0, 2).map((scenario) => localizeGeneratedText(scenario.label, uiLanguage)),
          ],
        },
        {
          key: 'peer',
          title: isEnglish ? 'Peers / sector' : '同业/板块',
          headline: profileContext || (isEnglish ? `${basicSnapshot.market.toUpperCase()} references` : `${basicSnapshot.market.toUpperCase()} 参照`),
          body: basicSnapshot.intelligence?.peerComparison?.summary
            ? localizeGeneratedText(basicSnapshot.intelligence.peerComparison.summary, uiLanguage)
            : (isEnglish ? 'Compare the symbol against broad-market and sector references before reading it alone.' : '解读单只股票前，先和大盘、行业或同业参照对比。'),
          points: peerLabels.length > 0 ? peerLabels : [basicSnapshot.stockCode],
        },
        {
          key: 'risk',
          title: isEnglish ? 'Risk explanation' : '风险解释',
          headline: isEnglish ? 'Read limits before acting' : '先看边界再解读',
          body: riskLines.length > 0
            ? localizeGeneratedText(riskLines[0], uiLanguage)
            : (isEnglish ? 'Free quick mode is a checklist, not a trading instruction.' : '免费快速模式是检查清单，不是交易指令。'),
          points: riskLines.slice(1, 4).map((line) => localizeGeneratedText(line, uiLanguage)),
        },
      ],
    };
  }, [basicFreeReport, basicSnapshot, uiLanguage]);
  const platformWatchlistItems = platformWatchlist?.items ?? [];
  const platformWatchlistPreview = platformWatchlistItems.slice(0, 6);
  const platformWatchlistBoardItems = platformWatchlistRefresh?.items ?? [];
  const platformWatchlistCount = platformWatchlist?.total ?? platformWatchlistItems.length;
  const workspaceHistoryCountText = uiLanguage === 'en'
    ? `${stockHistoryTotal ?? 0} reports`
    : `${stockHistoryTotal ?? 0} 份报告`;
  const workspaceAiModeText = apiKeyMode === 'user'
    ? (uiLanguage === 'en' ? 'Selected BYOK' : '已选择我的 API')
    : apiKeyMode === 'local'
      ? (uiLanguage === 'en' ? 'Selected local model' : '已选择本地模型')
      : (uiLanguage === 'en' ? 'Selected Platform API' : '已选择平台 API');
  const workspaceByokText = primaryApiKey
    ? (uiLanguage === 'en' ? 'BYOK ready' : '我的 API 已就绪')
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

  const handleBasicQuery = useCallback(async (
    stockCode?: string,
    _stockName?: string,
    forceRefresh = false,
    sourceModeOverride?: AShareSourceMode,
    viewMode: BasicSnapshotViewMode = 'query',
  ) => {
    const target = (stockCode || query).trim();
    if (!target || isQueryingBasic) {
      return null;
    }

    setBasicSnapshotViewMode(viewMode);
    setAutocompleteCloseSignal((current) => current + 1);
    setIsQueryingBasic(true);
    setBasicQueryError(null);
    setDeepAnalysisNotice('');
    setDeepAnalysisInlineNotice('');
    setBasicRetentionStatus('');
    setBasicRetentionError('');
    setKronosForecastError('');
    setBasicPremiumPreviewOpen(false);
    setBasicEventCenterActiveIndex(0);
    if (!forceRefresh) {
      setBasicSnapshot(null);
      setKronosForecast(null);
    }
    clearMarketReviewState();
    if (stockCode) {
      setQuery(stockCode);
    }

    try {
      const selectedAShareSourceMode = sourceModeOverride ?? aShareSourceMode;
      const options: BasicSnapshotOptions = {};
      if (forceRefresh) {
        options.refresh = true;
      }
      if (selectedAShareSourceMode !== 'poc' && shouldApplyAShareSourceMode(target)) {
        options.aShareSourceMode = selectedAShareSourceMode;
      }
      const snapshot = Object.keys(options).length > 0
        ? await stocksApi.snapshot(target, options)
        : await stocksApi.snapshot(target);
      setBasicSnapshot(snapshot);
      clearError();
      return snapshot;
    } catch (err: unknown) {
      setBasicQueryError(getParsedApiError(err));
      return null;
    } finally {
      setIsQueryingBasic(false);
    }
  }, [aShareSourceMode, clearError, clearMarketReviewState, isQueryingBasic, query, setQuery]);

  useEffect(() => {
    const snapshotSourceMode = basicSnapshot?.intelligence?.aShareEnrichment?.sourceMode;
    if (!snapshotSourceMode) {
      return;
    }
    setAShareSourceMode(normalizeAShareSourceMode(snapshotSourceMode));
  }, [basicSnapshot?.intelligence?.aShareEnrichment?.sourceMode]);

  const handleAShareSourceModeSelect = useCallback((mode: AShareSourceMode) => {
    setAShareSourceMode(mode);
    const currentAShareCode = basicSnapshot?.market === 'cn' ? basicSnapshot.stockCode : '';
    if (currentAShareCode) {
      void handleBasicQuery(currentAShareCode, undefined, true, mode, basicSnapshotViewMode);
    }
  }, [basicSnapshot?.market, basicSnapshot?.stockCode, basicSnapshotViewMode, handleBasicQuery]);

  const handleAShareSourceProbe = useCallback((symbol: string) => {
    setQuery(symbol);
    void handleBasicQuery(symbol, undefined, true, aShareSourceMode, basicSnapshotViewMode);
  }, [aShareSourceMode, basicSnapshotViewMode, handleBasicQuery, setQuery]);

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

  const handleBasicFeatureJump = useCallback((testId: string) => {
    const target = document.querySelector(`[data-testid="${testId}"]`);
    if (target instanceof HTMLElement && typeof target.scrollIntoView === 'function') {
      target.scrollIntoView({ behavior: 'auto', block: 'center' });
    }
  }, []);

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
      setDeepAnalysisNotice('');
      setDeepAnalysisInlineNotice('');
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

  const handleDeepAnalyze = useCallback(
    (
      stockCode?: string,
      stockName?: string,
      selectionSource?: 'manual' | 'autocomplete' | 'import' | 'image',
    ) => {
      if (platformEnabled && !platformSession) {
        const loginNotice = uiLanguage === 'en'
          ? 'Deep analysis requires login and a selected Platform API, user API, or local model. Free query and quick analysis remain available without AI.'
          : '深度分析需要先登录，并选择平台 API、我的 API 或本地模型。免费查询和快速分析可继续使用，不消耗 AI。';
        setAuthMode('login');
        setAuthError('');
        setDeepAnalysisNotice(loginNotice);
        setDeepAnalysisInlineNotice(loginNotice);
        window.setTimeout(() => {
          const inlineTarget = deepInlineGuardRef.current;
          if (typeof inlineTarget?.scrollIntoView === 'function') {
            inlineTarget.scrollIntoView({ behavior: 'smooth', block: 'center' });
          } else if (typeof platformAuthPanelRef.current?.scrollIntoView === 'function') {
            platformAuthPanelRef.current.scrollIntoView({ behavior: 'smooth', block: 'center' });
          }
          platformAuthPanelRef.current?.querySelector<HTMLInputElement>('[data-testid="platform-auth-email"]')?.focus();
        }, 0);
        return;
      }

      handleSubmitAnalysis(stockCode, stockName, selectionSource, 'deep');
    },
    [handleSubmitAnalysis, platformEnabled, platformSession, uiLanguage],
  );

  const handleQuickAnalyze = useCallback(
    (
      stockCode?: string,
      stockName?: string,
      _selectionSource?: 'manual' | 'autocomplete' | 'import' | 'image',
    ) => {
      void handleBasicQuery(stockCode, stockName, false, undefined, 'quick');
    },
    [handleBasicQuery],
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

  const aShareEnrichment = basicSnapshot?.intelligence?.aShareEnrichment ?? null;
  const aShareDiagnosticsValue = aShareEnrichment?.diagnostics;
  const aShareSkillValue = aShareEnrichment?.skill;
  const aShareEnrichmentDiagnostics = isPlainRecord(aShareDiagnosticsValue) && !Array.isArray(aShareDiagnosticsValue)
    ? aShareDiagnosticsValue
    : {};
  const aShareEnrichmentSkill = isPlainRecord(aShareSkillValue) && !Array.isArray(aShareSkillValue)
    ? aShareSkillValue
    : {};

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
                disabled={!query || isQueryingBasic}
                onClick={() => handleQuickAnalyze(undefined, undefined, 'manual')}
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
                onClick={() => handleDeepAnalyze(undefined, undefined, 'manual')}
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
            <div className={`flex flex-col gap-2 rounded-lg border border-subtle bg-surface/70 px-3 py-2 text-xs text-secondary-text ${platformSession ? 'md:items-stretch' : 'md:flex-row md:items-center md:justify-between'}`}>
              {platformSession ? (
                <>
                  <div data-testid="platform-signed-in-panel" className="flex min-w-0 w-full flex-col gap-2">
                    <div
                      data-testid="platform-query-status"
                      className="flex min-w-0 flex-wrap items-center gap-2 text-xs text-secondary-text"
                    >
                      <span className="inline-flex min-w-0 items-center gap-1.5 whitespace-nowrap font-medium text-foreground">
                        <UserRound className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />
                        <span className="max-w-[14rem] truncate">
                          {uiLanguage === 'en' ? 'Signed in' : '已登录'} {platformSession.user.email}
                        </span>
                      </span>
                      <span data-testid="platform-status-plan" className="whitespace-nowrap rounded-md border border-subtle px-2 py-1">
                        {uiLanguage === 'en' ? 'Plan' : '套餐'} {platformPlanLabel(platformSession.user.plan, uiLanguage)}
                      </span>
                      <span data-testid="platform-status-weekly" className="whitespace-nowrap rounded-md border border-subtle px-2 py-1">
                        {uiLanguage === 'en' ? 'Weekly free' : '每周免费'} {accountQuotaText}
                      </span>
                      <span data-testid="platform-status-basic-quota" className="whitespace-nowrap rounded-md border border-subtle px-2 py-1">
                        {uiLanguage === 'en' ? 'No-AI quick' : '免费快照'} {basicQuotaText}
                      </span>
                      <span data-testid="platform-status-byok" className="whitespace-nowrap rounded-md border border-subtle px-2 py-1">{byokStatusText}</span>
                      <span data-testid="platform-status-recommended" className="whitespace-nowrap rounded-md border border-subtle px-2 py-1">{recommendedModeText}</span>
                      <Button
                        type="button"
                        variant="secondary"
                        size="sm"
                        onClick={() => void handlePlatformLogout()}
                        data-testid="platform-logout-button"
                        className="ml-auto"
                      >
                        <LogOut className="h-3.5 w-3.5" aria-hidden="true" />
                        {uiLanguage === 'en' ? 'Sign out' : '退出'}
                      </Button>
                    </div>
                    <div
                      data-testid="platform-ai-cost-warning"
                      className="text-xs text-secondary-text"
                    >
                      {uiLanguage === 'en'
                        ? 'Quick snapshot stays no-AI. Quick/Deep AI uses selected quota: platform API, BYOK, or local model. Historical reports stay separate from current snapshots.'
                        : '快速快照保持未用 AI；快速/深度 AI 会使用所选额度：平台 API、我的 API 或本地模型。历史报告和当前快照单独保存。'}
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
                        <span className="rounded-md border border-subtle px-2 py-1">
                          {uiLanguage === 'en' ? 'Empty' : '暂无'}
                        </span>
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
                        {uiLanguage === 'en' ? 'Add current' : '加入当前'}
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
                  <div
                    data-testid="platform-query-mode-panel"
                    className="flex min-w-0 flex-wrap items-center gap-2 border-t border-subtle/70 pt-2"
                  >
                    <span className="whitespace-nowrap text-xs font-medium text-foreground">
                      {uiLanguage === 'en' ? 'Analysis channel' : '分析通道'}
                    </span>
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
                      className="h-8 w-full min-w-[12rem] max-w-[22rem] flex-1 rounded-lg border border-subtle bg-surface px-2 text-foreground placeholder:text-muted-text md:w-56 md:flex-none"
                    />
                    <input
                      type="password"
                      value={apiKeyDraft}
                      onChange={(event) => setApiKeyDraft(event.target.value)}
                      data-testid="platform-api-key-secret"
                      placeholder={platformKeys[0]?.maskedKey || 'API Key'}
                      className="h-8 w-full min-w-[10rem] max-w-[18rem] flex-1 rounded-lg border border-subtle bg-surface px-2 text-foreground placeholder:text-muted-text md:w-40 md:flex-none"
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
                      {uiLanguage === 'en' ? 'Save key' : '保存密钥'}
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
                      name="dsa-platform-email"
                      autoComplete="off"
                      autoCorrect="off"
                      spellCheck={false}
                      value={authEmail}
                      onChange={(event) => {
                        setAuthEmail(event.target.value);
                        setAuthError('');
                      }}
                      data-testid="platform-auth-email"
                      placeholder="邮箱"
                      className="h-8 w-44 rounded-lg border border-subtle bg-surface px-2 text-foreground placeholder:text-muted-text"
                    />
                    <input
                      type="password"
                      name="dsa-platform-password"
                      autoComplete="new-password"
                      value={authPassword}
                      onChange={(event) => {
                        setAuthPassword(event.target.value);
                        setAuthError('');
                      }}
                      data-testid="platform-auth-password"
                      placeholder="密码"
                      className="h-8 w-36 rounded-lg border border-subtle bg-surface px-2 text-foreground placeholder:text-muted-text"
                    />
                    {authMode === 'register' ? (
                      <>
                        <input
                          type="password"
                          name="dsa-platform-password-confirm"
                          autoComplete="new-password"
                          value={authPasswordConfirm}
                          onChange={(event) => {
                            setAuthPasswordConfirm(event.target.value);
                            setAuthError('');
                          }}
                          data-testid="platform-auth-confirm-password"
                          placeholder={uiLanguage === 'en' ? 'Confirm' : '确认密码'}
                          className="h-8 w-36 rounded-lg border border-subtle bg-surface px-2 text-foreground placeholder:text-muted-text"
                        />
                        <input
                          type="text"
                          inputMode="numeric"
                          name="dsa-platform-verification-code"
                          autoComplete="one-time-code"
                          value={authVerificationCode}
                          onChange={(event) => {
                            setAuthVerificationCode(event.target.value);
                            setAuthError('');
                          }}
                          data-testid="platform-auth-verification-code"
                          placeholder={uiLanguage === 'en' ? 'Code' : '验证码'}
                          className="h-8 w-24 rounded-lg border border-subtle bg-surface px-2 text-foreground placeholder:text-muted-text"
                        />
                        <Button
                          type="button"
                          variant="secondary"
                          size="sm"
                          isLoading={authVerificationBusy}
                          disabled={authVerificationBusy}
                          onClick={() => void handleRequestRegistrationCode()}
                          data-testid="platform-auth-send-code"
                        >
                          <MailCheck className="h-3.5 w-3.5" aria-hidden="true" />
                          {uiLanguage === 'en' ? 'Send code' : '发送验证码'}
                        </Button>
                      </>
                    ) : null}
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
                    {authMode === 'register' && authVerificationStatus ? (
                      <span className="text-success" data-testid="platform-auth-verification-status">
                        {authVerificationStatus}
                      </span>
                    ) : null}
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

            {deepAnalysisNotice ? (
              <div
                data-testid="deep-analysis-guard"
                role="alert"
                className="mb-3 rounded-xl border border-primary/40 bg-primary/10 px-4 py-3 text-sm text-foreground"
              >
                <div className="font-semibold text-primary">
                  {uiLanguage === 'en' ? 'Deep analysis is an account feature' : '深度分析是登录后的增强功能'}
                </div>
                <div className="mt-1 leading-relaxed text-secondary-text">
                  {deepAnalysisNotice}
                </div>
              </div>
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
                {basicSnapshotViewMode === 'query' ? (
                  <section
                    data-testid="basic-query-compact-overview"
                    className="mb-4 rounded-lg border border-primary/35 bg-primary/10 p-3"
                  >
                    <div className="flex min-w-0 flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                      <div className="min-w-0">
                        <div className="text-xs font-medium text-primary">
                          {uiLanguage === 'en' ? 'Quote lookup' : '行情速查'}
                        </div>
                        <h3 className="mt-1 text-base font-semibold leading-snug text-foreground">
                          {uiLanguage === 'en'
                            ? 'Core quote is ready. Open quick analysis for the complete free research read.'
                            : '核心行情已就绪，点击快速分析查看完整免费研判。'}
                        </h3>
                        <p className="mt-1 text-xs leading-relaxed text-secondary-text">
                          {uiLanguage === 'en'
                            ? 'Lookup keeps the page light: price, movement, moving averages, source and freshness. Quick analysis expands news, K-line forecast, peer comparison and risk checklist without using AI quota.'
                            : '查询只保留价格、涨跌、均线、来源和新鲜度；快速分析会展开资讯、K线预测、同业对比和风险清单，仍不消耗 AI 额度。'}
                        </p>
                      </div>
                      <Button
                        type="button"
                        variant="secondary"
                        size="sm"
                        className="shrink-0"
                        disabled={isQueryingBasic}
                        onClick={() => handleQuickAnalyze(basicSnapshot.stockCode, basicSnapshot.stockName || undefined, 'manual')}
                      >
                        <Sparkles className="h-4 w-4" aria-hidden="true" />
                        {uiLanguage === 'en' ? 'Open quick analysis' : '查看快速分析'}
                      </Button>
                    </div>
                    <div className="mt-3 grid gap-2 md:grid-cols-3">
                      <div className="min-w-0 rounded-md border border-subtle/80 bg-background/35 p-2.5">
                        <div className="text-[11px] text-secondary-text">{uiLanguage === 'en' ? 'Price / change' : '价格 / 涨跌'}</div>
                        <div className="mt-1 text-sm font-semibold text-foreground">
                          {formatBasicNumber(basicSnapshot.quote.currentPrice)} / {formatSignedBasicPercent(basicSnapshot.quote.changePercent)}
                        </div>
                      </div>
                      <div className="min-w-0 rounded-md border border-subtle/80 bg-background/35 p-2.5">
                        <div className="text-[11px] text-secondary-text">{uiLanguage === 'en' ? 'Moving averages' : '均线'}</div>
                        <div className="mt-1 text-sm font-semibold text-foreground">
                          MA5 {formatBasicNumber(basicSnapshot.indicators['ma5'])} / MA20 {formatBasicNumber(basicSnapshot.indicators['ma20'])}
                        </div>
                      </div>
                      <div className="min-w-0 rounded-md border border-subtle/80 bg-background/35 p-2.5">
                        <div className="text-[11px] text-secondary-text">{uiLanguage === 'en' ? 'Source / freshness' : '来源 / 新鲜度'}</div>
                        <div className="mt-1 truncate text-sm font-semibold text-foreground">
                          {localizeGeneratedSource(basicSnapshot.quote.source, uiLanguage)} / {localizeRuntimeLabel(basicSnapshot.quote.freshness, uiLanguage)}
                        </div>
                      </div>
                    </div>
                  </section>
                ) : null}
                {basicSnapshotViewMode === 'quick' ? (
                  <section
                    data-testid="basic-query-mode-banner"
                    className="mb-4 rounded-lg border border-primary/35 bg-primary/10 p-3"
                  >
                    <div className="flex min-w-0 flex-col gap-2 lg:flex-row lg:items-center lg:justify-between">
                      <div className="min-w-0">
                        <div className="text-xs font-medium text-primary">
                          {uiLanguage === 'en' ? 'Quick analysis mode' : '快速分析模式'}
                        </div>
                        <p className="mt-1 text-xs leading-relaxed text-secondary-text">
                          {uiLanguage === 'en'
                            ? 'This view expands the current free web/local snapshot into a rule-based first read. It does not use AI quota.'
                            : '已把当前免费网络/本地快照展开成规则化首轮研判，不使用 AI，也不消耗额度。'}
                        </p>
                      </div>
                      <div className="flex shrink-0 flex-wrap gap-1.5 text-[11px] text-secondary-text">
                        <span className="rounded-md border border-primary/40 bg-background/35 px-2 py-1 font-medium text-primary">
                          {uiLanguage === 'en' ? 'No AI' : '未用 AI'}
                        </span>
                        <span className="rounded-md border border-subtle/80 bg-background/35 px-2 py-1">
                          {uiLanguage === 'en' ? 'Free rule read' : '免费规则研判'}
                        </span>
                        <span className="rounded-md border border-subtle/80 bg-background/35 px-2 py-1">
                          {uiLanguage === 'en' ? 'Deep analysis optional' : '可继续深度分析'}
                        </span>
                      </div>
                    </div>
                    {basicFreeReport ? (
                      <div className="mt-3 grid gap-2 md:grid-cols-3">
                        <div className="min-w-0 rounded-md border border-subtle/80 bg-background/35 p-2.5">
                          <div className="text-[11px] font-medium text-primary">
                            {uiLanguage === 'en' ? 'First read' : '首轮结论'}
                          </div>
                          <div className="mt-1 line-clamp-2 text-sm font-semibold leading-snug text-foreground">
                            {localizeGeneratedText(basicFreeReport.productBrief.conclusion, uiLanguage)}
                          </div>
                          <div className="mt-1 text-[11px] text-secondary-text">
                            {uiLanguage === 'en' ? 'Signal' : '信号'} {basicFreeReport.score}/100
                          </div>
                        </div>
                        <div className="min-w-0 rounded-md border border-subtle/80 bg-background/35 p-2.5">
                          <div className="text-[11px] font-medium text-primary">
                            {uiLanguage === 'en' ? 'Price map' : '价位地图'}
                          </div>
                          <div className="mt-1 truncate text-sm font-semibold text-foreground">
                            {uiLanguage === 'en' ? 'Support' : '支撑'} {localizeGeneratedText(basicFreeReport.productBrief.supportLevels, uiLanguage)}
                          </div>
                          <div className="mt-1 truncate text-sm font-semibold text-foreground">
                            {uiLanguage === 'en' ? 'Resistance' : '压力'} {localizeGeneratedText(basicFreeReport.productBrief.pressureLevels, uiLanguage)}
                          </div>
                        </div>
                        <div className="min-w-0 rounded-md border border-subtle/80 bg-background/35 p-2.5">
                          <div className="text-[11px] font-medium text-primary">
                            {uiLanguage === 'en' ? 'Next check' : '下一步观察'}
                          </div>
                          <div className="mt-1 line-clamp-2 text-sm font-semibold leading-snug text-foreground">
                            {localizeGeneratedText(basicFreeReport.productBrief.shortStatus, uiLanguage)}
                          </div>
                          <div className="mt-1 line-clamp-2 text-[11px] text-secondary-text">
                            {localizeGeneratedText(basicFreeReport.productBrief.risks[0] || basicFreeReport.productBrief.midStatus, uiLanguage)}
                          </div>
                        </div>
                      </div>
                    ) : null}
                  </section>
                ) : null}
                {basicSnapshotViewMode === 'quick' && basicNextActionsWorkflow ? (
                  <section
                    data-testid="basic-query-next-actions-v85"
                    className="mb-4 rounded-lg border border-primary/40 bg-primary/10 p-3 shadow-soft-card"
                  >
                    <div className="flex min-w-0 flex-col gap-2 lg:flex-row lg:items-start lg:justify-between">
                      <div className="min-w-0">
                        <div className="text-xs font-semibold text-primary">{basicNextActionsWorkflow.title}</div>
                        <p className="mt-1 text-xs leading-relaxed text-secondary-text">
                          {basicNextActionsWorkflow.subtitle}
                        </p>
                      </div>
                      <span className="inline-flex shrink-0 items-center gap-1 rounded-md border border-primary/45 bg-background/35 px-2 py-1 text-[11px] font-medium text-primary">
                        <Check className="h-3.5 w-3.5" aria-hidden="true" />
                        {basicNextActionsWorkflow.boundary}
                      </span>
                    </div>
                    <div className="mt-3 grid gap-2 md:grid-cols-5">
                      {basicNextActionsWorkflow.actions.map((action) => {
                        const Icon = action.key === 'refresh'
                          ? RefreshCw
                          : action.key === 'news'
                            ? Search
                            : action.key === 'peers'
                              ? BarChart3
                              : action.key === 'kline'
                                ? Sparkles
                                : Plus;
                        const disabled = action.key === 'refresh'
                          ? isQueryingBasic
                          : action.key === 'watchlist'
                            ? platformWatchlistBusy
                            : false;
                        const onActionClick = () => {
                          if (action.key === 'refresh') {
                            void handleBasicQuery(basicSnapshot.stockCode, undefined, true, undefined, basicSnapshotViewMode);
                            return;
                          }
                          if (action.key === 'news') {
                            handleBasicFeatureJump('basic-query-news-center');
                            return;
                          }
                          if (action.key === 'peers') {
                            handleBasicFeatureJump('basic-query-peer-table');
                            return;
                          }
                          if (action.key === 'kline') {
                            handleBasicFeatureJump('basic-query-kline-forecast-lab');
                            return;
                          }
                          void handleAddCurrentQueryToPlatformWatchlist();
                        };
                        return (
                          <div key={action.key} className="min-w-0 rounded-md border border-subtle/75 bg-background/35 p-2.5">
                            <Button
                              type="button"
                              variant="secondary"
                              size="sm"
                              className="h-9 w-full justify-start"
                              disabled={disabled}
                              onClick={onActionClick}
                              data-testid={`basic-query-next-action-${action.key}`}
                            >
                              <Icon className="h-4 w-4 shrink-0" aria-hidden="true" />
                              <span className="truncate">{action.label}</span>
                            </Button>
                            <p className="mt-2 line-clamp-2 text-[11px] leading-relaxed text-secondary-text">
                              {action.detail}
                            </p>
                          </div>
                        );
                      })}
                    </div>
                    {basicRetentionError || platformWatchlistError || basicRetentionStatus ? (
                      <div
                        data-testid="basic-query-next-actions-status"
                        className={`mt-3 rounded-md border px-3 py-2 text-xs ${
                          basicRetentionError || platformWatchlistError
                            ? 'border-danger/50 bg-danger/10 text-danger'
                            : 'border-success/45 bg-success/10 text-success'
                        }`}
                      >
                        {basicRetentionError || platformWatchlistError || basicRetentionStatus}
                      </div>
                    ) : null}
                  </section>
                ) : null}
                {basicSnapshotViewMode === 'quick' && basicFreeAnalystWorkbench ? (
                  <section
                    data-testid="basic-query-free-analyst-workbench-v86"
                    className="mb-4 rounded-lg border border-primary/45 bg-gradient-to-br from-primary/14 via-surface/75 to-background/40 p-3 shadow-soft-card"
                  >
                    <div className="flex min-w-0 flex-col gap-3 xl:flex-row xl:items-start xl:justify-between">
                      <div className="min-w-0">
                        <div className="flex min-w-0 flex-wrap items-center gap-2">
                          <span className="rounded-md border border-primary/45 bg-primary/12 px-2 py-1 text-xs font-semibold text-primary">
                            {basicFreeAnalystWorkbench.title}
                          </span>
                          <span className="rounded-md border border-subtle/75 bg-background/35 px-2 py-1 text-[11px] text-secondary-text">
                            {basicFreeAnalystWorkbench.boundary}
                          </span>
                        </div>
                        <p className="mt-2 max-w-3xl text-sm leading-relaxed text-secondary-text">
                          {basicFreeAnalystWorkbench.subtitle}
                        </p>
                      </div>
                      <div className="flex shrink-0 flex-wrap gap-2">
                        <Button
                          type="button"
                          variant="secondary"
                          size="sm"
                          disabled={isQueryingBasic}
                          onClick={() => void handleBasicQuery(basicSnapshot.stockCode, undefined, true, undefined, basicSnapshotViewMode)}
                        >
                          <RefreshCw className="h-4 w-4" aria-hidden="true" />
                          {basicFreeAnalystWorkbench.actionLabels.refresh}
                        </Button>
                        <Button
                          type="button"
                          variant="secondary"
                          size="sm"
                          onClick={() => handleBasicFeatureJump('basic-query-news-center')}
                        >
                          <Search className="h-4 w-4" aria-hidden="true" />
                          {basicFreeAnalystWorkbench.actionLabels.news}
                        </Button>
                        <Button
                          type="button"
                          variant="secondary"
                          size="sm"
                          onClick={() => handleBasicFeatureJump('basic-query-peer-table')}
                        >
                          <BarChart3 className="h-4 w-4" aria-hidden="true" />
                          {basicFreeAnalystWorkbench.actionLabels.peers}
                        </Button>
                        <Button
                          type="button"
                          variant="secondary"
                          size="sm"
                          onClick={() => handleBasicFeatureJump('basic-query-kline-forecast-lab')}
                        >
                          <Sparkles className="h-4 w-4" aria-hidden="true" />
                          {basicFreeAnalystWorkbench.actionLabels.kline}
                        </Button>
                      </div>
                    </div>
                    <div className="mt-3 grid gap-2 lg:grid-cols-4">
                      {basicFreeAnalystWorkbench.cards.map((card) => (
                        <div key={card.label} className="min-w-0 rounded-md border border-subtle/75 bg-background/35 p-3">
                          <div className="text-[11px] font-semibold text-primary">{card.label}</div>
                          <div className="mt-1 line-clamp-2 text-sm font-semibold leading-snug text-foreground">{card.value}</div>
                          <p className="mt-2 line-clamp-3 text-xs leading-relaxed text-secondary-text">{card.detail}</p>
                        </div>
                      ))}
                    </div>
                    <div className="mt-3 grid gap-2 lg:grid-cols-2">
                      <div className="min-w-0 rounded-md border border-primary/30 bg-background/35 p-3">
                        <div className="text-xs font-semibold text-primary">{basicFreeAnalystWorkbench.freeTitle}</div>
                        <div className="mt-2 flex min-w-0 flex-wrap gap-1.5 text-[11px] text-secondary-text">
                          {basicFreeAnalystWorkbench.freeModules.map((item) => (
                            <span key={`free-${item}`} className="max-w-full truncate rounded-md border border-subtle/70 px-2 py-1">
                              {item}
                            </span>
                          ))}
                        </div>
                      </div>
                      <div className="min-w-0 rounded-md border border-primary/35 bg-primary/10 p-3">
                        <div className="text-xs font-semibold text-primary">{basicFreeAnalystWorkbench.premiumTitle}</div>
                        <div className="mt-2 flex min-w-0 flex-wrap gap-1.5 text-[11px] text-primary">
                          {basicFreeAnalystWorkbench.premiumModules.map((item) => (
                            <span key={`premium-${item}`} className="max-w-full truncate rounded-md border border-primary/35 bg-background/35 px-2 py-1">
                              {item}
                            </span>
                          ))}
                        </div>
                      </div>
                    </div>
                  </section>
                ) : null}
                {basicSnapshotViewMode === 'quick' && basicVisualAnalystPage ? (
                  <section
                    data-testid="basic-query-visual-analyst-page-v87"
                    className="mb-4 rounded-lg border border-primary/50 bg-gradient-to-br from-background/75 via-primary/10 to-surface/70 p-3 shadow-soft-card"
                  >
                    <div className="flex min-w-0 flex-col gap-3 xl:flex-row xl:items-start xl:justify-between">
                      <div className="min-w-0">
                        <div className="flex min-w-0 flex-wrap items-center gap-2">
                          <span className="rounded-md border border-primary/50 bg-primary/14 px-2 py-1 text-xs font-semibold text-primary">
                            {basicVisualAnalystPage.title}
                          </span>
                          <span className="rounded-md border border-subtle/75 bg-background/35 px-2 py-1 text-[11px] text-secondary-text">
                            {basicVisualAnalystPage.boundary}
                          </span>
                          <span className="rounded-md border border-subtle/75 bg-background/35 px-2 py-1 text-[11px] text-secondary-text">
                            {basicVisualAnalystPage.source}
                          </span>
                        </div>
                        <h3 className="mt-2 text-lg font-semibold leading-snug text-foreground">
                          {basicVisualAnalystPage.subtitle}
                        </h3>
                        <p className="mt-1 text-xs leading-relaxed text-secondary-text">
                          {basicVisualAnalystPage.conclusion}
                        </p>
                      </div>
                      <div className="grid shrink-0 grid-cols-2 gap-2 sm:grid-cols-4 xl:grid-cols-2">
                        <div className="rounded-md border border-primary/35 bg-primary/10 px-3 py-2">
                          <div className="text-[11px] text-secondary-text">{basicVisualAnalystPage.scoreLabel}</div>
                          <div className="mt-1 text-lg font-semibold text-primary">{basicVisualAnalystPage.scoreValue}</div>
                        </div>
                        <div className="rounded-md border border-subtle/75 bg-background/35 px-3 py-2">
                          <div className="text-[11px] text-secondary-text">{uiLanguage === 'en' ? 'Price / change' : '价格 / 涨跌'}</div>
                          <div className="mt-1 text-sm font-semibold text-foreground">{basicVisualAnalystPage.priceValue}</div>
                        </div>
                      </div>
                    </div>
                    <div className="mt-3 grid gap-3 xl:grid-cols-[minmax(0,1.2fr)_minmax(18rem,0.8fr)]">
                      <div className="min-w-0 rounded-md border border-primary/35 bg-background/35 p-3">
                        <div className="flex min-w-0 items-center justify-between gap-2">
                          <div className="text-sm font-semibold text-foreground">{basicVisualAnalystPage.trendTitle}</div>
                          <span className="rounded-md border border-primary/35 bg-primary/10 px-2 py-1 text-[11px] text-primary">
                            {basicVisualAnalystPage.trendStatus}
                          </span>
                        </div>
                        <div className="mt-3 h-32 rounded-md border border-subtle/60 bg-surface/45 p-2 text-primary">
                          {basicVisualAnalystPage.sparkline ? (
                            <svg
                              aria-label={basicVisualAnalystPage.trendTitle}
                              className="h-full w-full overflow-visible"
                              preserveAspectRatio="none"
                              role="img"
                              viewBox="0 0 220 72"
                            >
                              <line className="stroke-subtle" x1="6" x2="214" y1="18" y2="18" strokeWidth="1" strokeDasharray="4 4" />
                              <line className="stroke-subtle" x1="6" x2="214" y1="54" y2="54" strokeWidth="1" strokeDasharray="4 4" />
                              <polygon
                                className="fill-primary/10"
                                points={basicVisualAnalystPage.sparkline.areaPoints}
                              />
                              <polyline
                                className="fill-none stroke-primary"
                                points={basicVisualAnalystPage.sparkline.linePoints}
                                strokeLinecap="round"
                                strokeLinejoin="round"
                                strokeWidth="3"
                              />
                            </svg>
                          ) : (
                            <div className="flex h-full items-center justify-center text-xs text-secondary-text">
                              {uiLanguage === 'en' ? 'Trend chart awaits more history' : '趋势图等待更多历史数据'}
                            </div>
                          )}
                        </div>
                        <p className="mt-2 text-xs leading-relaxed text-secondary-text">
                          {basicVisualAnalystPage.trendDetail}
                        </p>
                      </div>
                      <div className="grid min-w-0 gap-3">
                        <div className="rounded-md border border-subtle/75 bg-background/35 p-3">
                          <div className="text-sm font-semibold text-foreground">{basicVisualAnalystPage.levelTitle}</div>
                          <div className="mt-2 grid grid-cols-2 gap-2">
                            <div className="min-w-0 rounded-md border border-success/35 bg-success/10 px-3 py-2">
                              <div className="text-[11px] text-secondary-text">{uiLanguage === 'en' ? 'Support' : '支撑'}</div>
                              <div className="mt-1 truncate text-lg font-semibold text-foreground">{basicVisualAnalystPage.supportText}</div>
                            </div>
                            <div className="min-w-0 rounded-md border border-warning/35 bg-warning/10 px-3 py-2">
                              <div className="text-[11px] text-secondary-text">{uiLanguage === 'en' ? 'Resistance' : '压力'}</div>
                              <div className="mt-1 truncate text-lg font-semibold text-foreground">{basicVisualAnalystPage.resistanceText}</div>
                            </div>
                          </div>
                          <p className="mt-2 line-clamp-2 text-xs leading-relaxed text-secondary-text">
                            {basicVisualAnalystPage.levelDetail}
                          </p>
                        </div>
                        <div className="rounded-md border border-subtle/75 bg-background/35 p-3">
                          <div className="flex items-center justify-between gap-2">
                            <div className="text-sm font-semibold text-foreground">{basicVisualAnalystPage.volumeTitle}</div>
                            <span className="rounded-md border border-primary/35 bg-primary/10 px-2 py-1 text-[11px] text-primary">
                              {basicVisualAnalystPage.volumeStatus}
                            </span>
                          </div>
                          <div className="mt-3 flex h-20 items-end gap-1.5 rounded-md border border-subtle/60 bg-surface/35 px-2 py-2">
                            {basicVisualAnalystPage.volumeBars.length > 0 ? (
                              basicVisualAnalystPage.volumeBars.map((bar) => (
                                <div key={`${bar.label}-${bar.value}`} className="flex h-full min-w-0 flex-1 flex-col justify-end">
                                  <div
                                    className={`rounded-t-sm ${bar.isLatest ? 'bg-primary' : 'bg-primary/45'}`}
                                    style={{ height: `${bar.height}%` }}
                                    title={`${bar.label}: ${formatBasicCompactNumber(bar.value)}`}
                                  />
                                </div>
                              ))
                            ) : (
                              <div className="flex h-full flex-1 items-center justify-center text-xs text-secondary-text">
                                {uiLanguage === 'en' ? 'Volume bars await history' : '量价条等待历史数据'}
                              </div>
                            )}
                          </div>
                          <p className="mt-2 line-clamp-2 text-xs leading-relaxed text-secondary-text">
                            {basicVisualAnalystPage.volumeDetail}
                          </p>
                        </div>
                      </div>
                    </div>
                    <div className="mt-3 grid gap-3 lg:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)]">
                      <div className="min-w-0 rounded-md border border-primary/35 bg-primary/10 p-3">
                        <div className="text-sm font-semibold text-foreground">{basicVisualAnalystPage.nextTitle}</div>
                        <p className="mt-2 text-sm leading-relaxed text-secondary-text">
                          {basicVisualAnalystPage.nextStep}
                        </p>
                        <div className="mt-3 flex flex-wrap gap-2">
                          <Button
                            type="button"
                            variant="secondary"
                            size="sm"
                            disabled={isQueryingBasic}
                            onClick={() => void handleBasicQuery(basicSnapshot.stockCode, undefined, true, undefined, basicSnapshotViewMode)}
                          >
                            <RefreshCw className="h-4 w-4" aria-hidden="true" />
                            {basicVisualAnalystPage.actionLabels.refresh}
                          </Button>
                          <Button
                            type="button"
                            variant="secondary"
                            size="sm"
                            onClick={() => handleBasicFeatureJump('basic-query-news-center')}
                          >
                            <Search className="h-4 w-4" aria-hidden="true" />
                            {basicVisualAnalystPage.actionLabels.news}
                          </Button>
                          <Button
                            type="button"
                            variant="secondary"
                            size="sm"
                            onClick={() => handleBasicFeatureJump('basic-query-peer-table')}
                          >
                            <BarChart3 className="h-4 w-4" aria-hidden="true" />
                            {basicVisualAnalystPage.actionLabels.peers}
                          </Button>
                          <Button
                            type="button"
                            variant="secondary"
                            size="sm"
                            onClick={() => handleBasicFeatureJump('basic-query-kline-forecast-lab')}
                          >
                            <Sparkles className="h-4 w-4" aria-hidden="true" />
                            {basicVisualAnalystPage.actionLabels.kline}
                          </Button>
                        </div>
                      </div>
                      <div className="grid min-w-0 gap-2 sm:grid-cols-2">
                        <div className="min-w-0 rounded-md border border-subtle/75 bg-background/35 p-3">
                          <div className="text-xs font-semibold text-primary">{basicVisualAnalystPage.freeTitle}</div>
                          <div className="mt-2 flex flex-wrap gap-1.5 text-[11px] text-secondary-text">
                            {basicVisualAnalystPage.freeItems.map((item, index) => (
                              <span key={`v87-free-${index}-${item}`} className="rounded-md border border-subtle/70 px-2 py-1">
                                {item}
                              </span>
                            ))}
                          </div>
                        </div>
                        <div className="min-w-0 rounded-md border border-primary/35 bg-background/35 p-3">
                          <div className="text-xs font-semibold text-primary">{basicVisualAnalystPage.premiumTitle}</div>
                          <div className="mt-2 flex flex-wrap gap-1.5 text-[11px] text-primary">
                            {basicVisualAnalystPage.premiumItems.map((item, index) => (
                              <span key={`v87-premium-${index}-${item}`} className="rounded-md border border-primary/35 bg-primary/10 px-2 py-1">
                                {item}
                              </span>
                            ))}
                          </div>
                        </div>
                      </div>
                    </div>
                  </section>
                ) : null}
                {basicSnapshotViewMode === 'quick' && basicReadingRoadmap ? (
                  <section
                    data-testid="basic-query-reading-roadmap-v88"
                    className="mb-4 rounded-lg border border-primary/45 bg-surface/70 p-3 shadow-soft-card"
                  >
                    <div className="flex min-w-0 flex-col gap-3 xl:flex-row xl:items-start xl:justify-between">
                      <div className="min-w-0">
                        <div className="flex min-w-0 flex-wrap items-center gap-2 text-[11px]">
                          <span className="rounded-md border border-primary/45 bg-primary/12 px-2 py-1 font-semibold text-primary">
                            {basicReadingRoadmap.title}
                          </span>
                          <span className="rounded-md border border-subtle/75 bg-background/35 px-2 py-1 text-secondary-text">
                            {basicReadingRoadmap.boundary}
                          </span>
                          <span className="rounded-md border border-primary/35 bg-background/35 px-2 py-1 text-primary">
                            {basicReadingRoadmap.freeTitle}
                          </span>
                          <span className="rounded-md border border-warning/35 bg-warning/10 px-2 py-1 text-warning">
                            {basicReadingRoadmap.premiumTitle}
                          </span>
                        </div>
                        <p className="mt-2 max-w-4xl text-sm leading-relaxed text-secondary-text">
                          {basicReadingRoadmap.subtitle}
                        </p>
                      </div>
                      <div className="flex shrink-0 flex-wrap gap-2">
                        <Button
                          type="button"
                          variant="secondary"
                          size="sm"
                          onClick={() => handleBasicFeatureJump('basic-query-news-center')}
                        >
                          <Search className="h-4 w-4" aria-hidden="true" />
                          {basicReadingRoadmap.actionLabels.news}
                        </Button>
                        <Button
                          type="button"
                          variant="secondary"
                          size="sm"
                          onClick={() => handleBasicFeatureJump('basic-query-peer-table')}
                        >
                          <BarChart3 className="h-4 w-4" aria-hidden="true" />
                          {basicReadingRoadmap.actionLabels.peers}
                        </Button>
                        <Button
                          type="button"
                          variant="secondary"
                          size="sm"
                          onClick={() => handleBasicFeatureJump('basic-query-kline-forecast-lab')}
                        >
                          <Sparkles className="h-4 w-4" aria-hidden="true" />
                          {basicReadingRoadmap.actionLabels.kline}
                        </Button>
                      </div>
                    </div>
                    <div className="mt-3 grid gap-2 lg:grid-cols-4">
                      {basicReadingRoadmap.steps.map((step, index) => (
                        <div
                          key={step.title}
                          className="min-w-0 rounded-md border border-subtle/80 bg-background/35 p-3"
                        >
                          <div className="flex items-start gap-2">
                            <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md border border-primary/45 bg-primary/12 text-sm font-semibold text-primary">
                              {index + 1}
                            </span>
                            <div className="min-w-0">
                              <div className="text-sm font-semibold text-foreground">{step.title}</div>
                              <div className="mt-1 text-[11px] font-medium text-primary">{step.tag}</div>
                            </div>
                          </div>
                          <p className="mt-2 line-clamp-4 text-xs leading-relaxed text-secondary-text">
                            {step.detail}
                          </p>
                        </div>
                      ))}
                    </div>
                    <div className="mt-3 grid gap-2 md:grid-cols-2">
                      <div className="rounded-md border border-subtle/75 bg-background/35 p-3">
                        <div className="text-xs font-semibold text-primary">{basicReadingRoadmap.freeTitle}</div>
                        <p className="mt-1 text-xs leading-relaxed text-secondary-text">
                          {basicReadingRoadmap.freeDetail}
                        </p>
                      </div>
                      <div className="rounded-md border border-primary/35 bg-primary/8 p-3">
                        <div className="text-xs font-semibold text-primary">{basicReadingRoadmap.premiumTitle}</div>
                        <p className="mt-1 text-xs leading-relaxed text-secondary-text">
                          {basicReadingRoadmap.premiumDetail}
                        </p>
                      </div>
                    </div>
                    <div className="mt-3 flex flex-wrap gap-1.5 text-[11px] text-secondary-text">
                      {basicReadingRoadmap.risks.map((risk, index) => (
                        <span
                          key={`v88-risk-${index}-${risk}`}
                          className="rounded-md border border-subtle/70 bg-background/35 px-2 py-1"
                        >
                          {risk}
                        </span>
                      ))}
                    </div>
                  </section>
                ) : null}
                {basicSnapshotViewMode === 'quick' && basicTodayBriefCard ? (
                  <section
                    data-testid="basic-query-today-brief-card"
                    className="mb-4 rounded-lg border border-primary/50 bg-gradient-to-br from-primary/14 via-surface/70 to-surface/45 p-3 shadow-soft-card"
                  >
                    <div className="flex min-w-0 flex-col gap-3 xl:flex-row xl:items-start xl:justify-between">
                      <div className="min-w-0">
                        <div className="flex min-w-0 flex-wrap items-center gap-2 text-[11px]">
                          <span className="rounded-md border border-primary/45 bg-primary/12 px-2 py-1 font-semibold text-primary">
                            {basicTodayBriefCard.title}
                          </span>
                          <span className="rounded-md border border-subtle/80 bg-background/35 px-2 py-1 text-secondary-text">
                            {basicTodayBriefCard.stockTitle}
                          </span>
                          <span className="rounded-md border border-primary/35 bg-background/35 px-2 py-1 text-primary">
                            {basicTodayBriefCard.signalLabel} {basicTodayBriefCard.signalValue}
                          </span>
                          <span className="rounded-md border border-subtle/70 bg-background/35 px-2 py-1 text-secondary-text">
                            {basicTodayBriefCard.boundary}
                          </span>
                        </div>
                        <div className="mt-3">
                          <div className="text-xs font-medium text-primary">{basicTodayBriefCard.oneLineLabel}</div>
                          <h3 className="mt-1 text-xl font-semibold leading-snug text-foreground">
                            {basicTodayBriefCard.oneLine}
                          </h3>
                        </div>
                      </div>
                      <Button
                        type="button"
                        variant="secondary"
                        size="sm"
                        className="shrink-0"
                        disabled={isQueryingBasic}
                        onClick={() => void handleBasicQuery(basicSnapshot.stockCode, undefined, true, undefined, basicSnapshotViewMode)}
                      >
                        <RefreshCw className="h-4 w-4" aria-hidden="true" />
                        {basicTodayBriefCard.refreshLabel}
                      </Button>
                    </div>
                    <div className="mt-3 grid gap-2 md:grid-cols-3">
                      <div className="min-w-0 rounded-md border border-subtle/80 bg-background/35 p-2.5">
                        <div className="text-[11px] font-medium text-secondary-text">{basicTodayBriefCard.priceLabel}</div>
                        <div className="mt-1 truncate text-lg font-semibold text-foreground">{basicTodayBriefCard.priceValue}</div>
                      </div>
                      <div className="min-w-0 rounded-md border border-subtle/80 bg-background/35 p-2.5">
                        <div className="text-[11px] font-medium text-secondary-text">{basicTodayBriefCard.dataTrustLabel}</div>
                        <div className="mt-1 truncate text-lg font-semibold text-foreground">{basicTodayBriefCard.dataTrustValue}</div>
                      </div>
                      <div className="min-w-0 rounded-md border border-subtle/80 bg-background/35 p-2.5">
                        <div className="text-[11px] font-medium text-secondary-text">{basicTodayBriefCard.nextActionLabel}</div>
                        <div className="mt-1 line-clamp-2 text-sm font-semibold leading-snug text-foreground">{basicTodayBriefCard.nextAction}</div>
                      </div>
                    </div>
                    <div
                      data-testid="basic-query-broker-three-step-card"
                      className="mt-3 rounded-lg border border-primary/35 bg-background/35 p-3"
                    >
                      <div className="flex min-w-0 flex-col gap-2 md:flex-row md:items-center md:justify-between">
                        <div className="text-sm font-semibold text-foreground">{basicTodayBriefCard.brokerTitle}</div>
                        <div className="text-xs leading-relaxed text-secondary-text">{basicTodayBriefCard.brokerFootnote}</div>
                      </div>
                      <div className="mt-3 grid gap-2 md:grid-cols-3">
                        {basicTodayBriefCard.brokerSteps.map((step) => (
                          <div key={step.label} className="min-w-0 rounded-md border border-subtle/80 bg-surface/45 p-2.5">
                            <div className="text-[11px] font-medium text-primary">{step.label}</div>
                            <div className="mt-1 text-sm font-semibold leading-snug text-foreground">{step.value}</div>
                            <p className="mt-1 line-clamp-3 text-xs leading-relaxed text-secondary-text">{step.detail}</p>
                          </div>
                        ))}
                      </div>
                    </div>
                    <div className="mt-3 grid gap-2 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_minmax(0,1.15fr)]">
                      <div className="min-w-0 rounded-md border border-warning/35 bg-warning/10 p-2.5">
                        <div className="text-xs font-semibold text-warning">{basicTodayBriefCard.riskLabel}</div>
                        <p className="mt-1 line-clamp-3 text-xs leading-relaxed text-secondary-text">{basicTodayBriefCard.riskText}</p>
                      </div>
                      <div className="min-w-0 rounded-md border border-primary/30 bg-background/35 p-2.5">
                        <div className="text-xs font-semibold text-primary">{basicTodayBriefCard.freeLabel}</div>
                        <div className="mt-2 flex min-w-0 flex-wrap gap-1.5 text-[11px] text-secondary-text">
                          {basicTodayBriefCard.freeItems.map((item) => (
                            <span key={item} className="max-w-full rounded-md border border-subtle/70 px-1.5 py-0.5">
                              {item}
                            </span>
                          ))}
                        </div>
                      </div>
                      <div className="min-w-0 rounded-md border border-primary/35 bg-primary/10 p-2.5">
                        <div className="text-xs font-semibold text-primary">{basicTodayBriefCard.premiumLabel}</div>
                        <div className="mt-2 flex min-w-0 flex-wrap gap-1.5 text-[11px] text-secondary-text">
                          {basicTodayBriefCard.premiumItems.map((item) => (
                            <span key={item} className="max-w-full rounded-md border border-primary/35 bg-background/35 px-1.5 py-0.5 text-primary">
                              {item}
                            </span>
                          ))}
                        </div>
                        <Button
                          type="button"
                          variant="secondary"
                          size="sm"
                          className="mt-2"
                          onClick={() => setBasicPremiumPreviewOpen((open) => !open)}
                        >
                          <Sparkles className="h-4 w-4" aria-hidden="true" />
                          {basicPremiumPreviewOpen
                            ? basicTodayBriefCard.premiumPreviewCloseLabel
                            : basicTodayBriefCard.premiumPreviewOpenLabel}
                        </Button>
                      </div>
                    </div>
                    {basicPremiumPreviewOpen ? (
                      <div
                        data-testid="basic-query-premium-preview-panel"
                        className="mt-3 rounded-lg border border-primary/45 bg-surface/70 p-3"
                      >
                        <div className="flex min-w-0 flex-col gap-2 md:flex-row md:items-start md:justify-between">
                          <div className="min-w-0">
                            <div className="text-sm font-semibold text-foreground">{basicTodayBriefCard.premiumPreviewTitle}</div>
                            <p className="mt-1 text-xs leading-relaxed text-secondary-text">{basicTodayBriefCard.premiumPreviewSubtitle}</p>
                          </div>
                          <span className="shrink-0 rounded-md border border-primary/35 bg-primary/10 px-2 py-1 text-xs font-medium text-primary">
                            {basicTodayBriefCard.premiumPreviewBoundary}
                          </span>
                        </div>
                        <div className="mt-3 grid gap-2 md:grid-cols-2 xl:grid-cols-4">
                          {basicTodayBriefCard.premiumPreviewModules.map((module) => (
                            <div key={module.title} className="min-w-0 rounded-md border border-subtle/80 bg-background/35 p-2.5">
                              <div className="text-xs font-semibold text-primary">{module.title}</div>
                              <p className="mt-1 line-clamp-4 text-xs leading-relaxed text-secondary-text">{module.detail}</p>
                            </div>
                          ))}
                        </div>
                        <div
                          data-testid="basic-query-premium-conversion-v84"
                          className="mt-3 rounded-lg border border-primary/35 bg-primary/10 p-3"
                        >
                          <div className="flex min-w-0 flex-col gap-2 lg:flex-row lg:items-start lg:justify-between">
                            <div className="min-w-0">
                              <div className="text-sm font-semibold text-foreground">
                                {basicTodayBriefCard.premiumConversionTitle}
                              </div>
                              <p className="mt-1 text-xs leading-relaxed text-secondary-text">
                                {basicTodayBriefCard.premiumConversionSubtitle}
                              </p>
                            </div>
                            <span className="shrink-0 rounded-md border border-primary/35 bg-background/35 px-2 py-1 text-xs font-medium text-primary">
                              {basicTodayBriefCard.premiumConversionBoundary}
                            </span>
                          </div>
                          <div className="mt-3 grid gap-2 md:grid-cols-2">
                            <div className="rounded-md border border-subtle/70 bg-background/35 px-2.5 py-2 text-xs font-semibold text-secondary-text">
                              {basicTodayBriefCard.premiumConversionColumns.free}
                            </div>
                            <div className="rounded-md border border-primary/35 bg-background/45 px-2.5 py-2 text-xs font-semibold text-primary">
                              {basicTodayBriefCard.premiumConversionColumns.premium}
                            </div>
                          </div>
                          <div className="mt-2 divide-y divide-subtle/70 rounded-md border border-subtle/70 bg-background/25">
                            {basicTodayBriefCard.premiumConversionRows.map((row) => (
                              <div key={row.title} className="grid gap-2 p-2.5 md:grid-cols-[minmax(8rem,0.7fr)_minmax(0,1fr)_minmax(0,1fr)]">
                                <div className="text-xs font-semibold text-foreground">
                                  {row.title}
                                </div>
                                <p className="text-xs leading-relaxed text-secondary-text">
                                  {row.free}
                                </p>
                                <p className="text-xs leading-relaxed text-primary">
                                  {row.premium}
                                </p>
                              </div>
                            ))}
                          </div>
                        </div>
                      </div>
                    ) : null}
                  </section>
                ) : null}
                {basicSnapshotViewMode === 'quick' && basicFreeEventCenter ? (
                  <section
                    data-testid="basic-query-free-event-center-v82"
                    className="mb-4 rounded-lg border border-primary/45 bg-surface/60 p-3 shadow-soft-card"
                  >
                    <div className="flex min-w-0 flex-col gap-3 xl:flex-row xl:items-start xl:justify-between">
                      <div className="min-w-0">
                        <div className="flex min-w-0 flex-wrap items-center gap-2 text-[11px]">
                          <span className="rounded-md border border-primary/45 bg-primary/12 px-2 py-1 font-semibold text-primary">
                            {basicFreeEventCenter.title}
                          </span>
                          <span className="rounded-md border border-primary/35 bg-background/35 px-2 py-1 text-primary">
                            {basicFreeEventCenter.noAiLabel}
                          </span>
                          <span className="rounded-md border border-subtle/80 bg-background/35 px-2 py-1 text-secondary-text">
                            {basicFreeEventCenter.sourceLabel}: {basicFreeEventCenter.sourceValue}
                          </span>
                          <span className="rounded-md border border-subtle/80 bg-background/35 px-2 py-1 text-secondary-text">
                            {basicFreeEventCenter.freshnessLabel}: {basicFreeEventCenter.freshnessValue}
                          </span>
                        </div>
                        <h3 className="mt-3 text-lg font-semibold leading-snug text-foreground">
                          {basicFreeEventCenter.subtitle}
                        </h3>
                      </div>
                      <span className="shrink-0 rounded-md border border-subtle/80 bg-background/35 px-2 py-1 text-xs text-secondary-text">
                        {basicFreeEventCenter.boundary}
                      </span>
                    </div>
                    <div className="mt-3 grid gap-3 xl:grid-cols-[minmax(0,0.85fr)_minmax(0,1.15fr)]">
                      <div className="min-w-0 rounded-lg border border-primary/30 bg-primary/10 p-3">
                        <div className="text-xs font-semibold text-primary">{basicFreeEventCenter.whyTitle}</div>
                        <p className="mt-2 text-sm font-semibold leading-relaxed text-foreground">
                          {basicFreeEventCenter.whyText}
                        </p>
                      </div>
                      <div className="min-w-0 rounded-lg border border-subtle/80 bg-background/35 p-3">
                        <div className="text-xs font-semibold text-foreground">{basicFreeEventCenter.timelineTitle}</div>
                        <div className="mt-2 grid gap-2 md:grid-cols-2">
                          {basicFreeEventCenter.timeline.map((item, index) => (
                            <button
                              key={`${index}-${item.label}`}
                              type="button"
                              data-testid={`basic-query-free-event-timeline-${index}`}
                              aria-pressed={basicEventCenterActiveIndex === index}
                              onClick={() => setBasicEventCenterActiveIndex(index)}
                              className={`min-w-0 rounded-md border p-2.5 text-left transition-colors ${
                                basicEventCenterActiveIndex === index
                                  ? 'border-primary/55 bg-primary/12 shadow-soft-card'
                                  : 'border-subtle/70 bg-surface/35 hover:border-primary/40 hover:bg-primary/5'
                              }`}
                            >
                              <div className="text-[11px] font-medium text-primary">{item.label}</div>
                              <div className="mt-1 line-clamp-2 text-sm font-semibold leading-snug text-foreground">{item.value}</div>
                              <p className="mt-1 line-clamp-3 text-xs leading-relaxed text-secondary-text">{item.detail}</p>
                            </button>
                          ))}
                        </div>
                        {basicFreeEventCenter.activeItem ? (
                          <div
                            data-testid="basic-query-free-event-detail-v83"
                            className="mt-3 rounded-lg border border-primary/35 bg-primary/10 p-3"
                          >
                            <div className="text-xs font-semibold text-primary">
                              {basicFreeEventCenter.detailTitle}
                            </div>
                            <div className="mt-1 text-sm font-semibold text-foreground">
                              {basicFreeEventCenter.activeItem.detailTitle}
                            </div>
                            <p className="mt-2 text-xs leading-relaxed text-secondary-text">
                              {basicFreeEventCenter.activeItem.detail}
                            </p>
                            <div className="mt-3 grid gap-2 md:grid-cols-3">
                              <div className="min-w-0 rounded-md border border-subtle/70 bg-background/35 p-2">
                                <div className="text-[11px] font-medium text-primary">
                                  {basicFreeEventCenter.sourceStatusLabel}
                                </div>
                                <p className="mt-1 text-xs leading-relaxed text-secondary-text">
                                  {basicFreeEventCenter.activeItem.sourceStatus}
                                </p>
                              </div>
                              <div className="min-w-0 rounded-md border border-subtle/70 bg-background/35 p-2">
                                <div className="text-[11px] font-medium text-primary">
                                  {basicFreeEventCenter.freeNextLabel}
                                </div>
                                <p className="mt-1 text-xs leading-relaxed text-secondary-text">
                                  {basicFreeEventCenter.activeItem.freeNext}
                                </p>
                              </div>
                              <div className="min-w-0 rounded-md border border-primary/35 bg-background/45 p-2">
                                <div className="text-[11px] font-medium text-primary">
                                  {basicFreeEventCenter.premiumVerifyLabel}
                                </div>
                                <p className="mt-1 text-xs leading-relaxed text-secondary-text">
                                  {basicFreeEventCenter.activeItem.premiumVerify}
                                </p>
                              </div>
                            </div>
                          </div>
                        ) : null}
                      </div>
                    </div>
                    <div className="mt-3 grid gap-3 xl:grid-cols-2">
                      <div className="min-w-0 rounded-lg border border-subtle/80 bg-background/35 p-3">
                        <div className="text-sm font-semibold text-foreground">{basicFreeEventCenter.freeTitle}</div>
                        <div className="mt-2 grid gap-2">
                          {basicFreeEventCenter.freeActions.map((item, index) => (
                            <div
                              key={`${index}-${item}`}
                              className="flex min-w-0 items-start gap-2 rounded-md border border-subtle/70 bg-surface/35 px-2.5 py-2 text-xs leading-relaxed text-secondary-text"
                            >
                              <Check className="mt-0.5 h-3.5 w-3.5 shrink-0 text-primary" aria-hidden="true" />
                              <span>{item}</span>
                            </div>
                          ))}
                        </div>
                      </div>
                      <div className="min-w-0 rounded-lg border border-primary/35 bg-primary/10 p-3">
                        <div className="text-sm font-semibold text-primary">{basicFreeEventCenter.premiumTitle}</div>
                        <div className="mt-2 grid gap-2 sm:grid-cols-2">
                          {basicFreeEventCenter.premiumActions.map((item, index) => (
                            <div
                              key={`${index}-${item}`}
                              className="rounded-md border border-primary/25 bg-background/35 px-2.5 py-2 text-xs font-medium text-primary"
                            >
                              {item}
                            </div>
                          ))}
                        </div>
                      </div>
                    </div>
                  </section>
                ) : null}
                {basicSnapshotViewMode === 'quick' && basicProDecisionCard ? (
                  <section
                    data-testid="basic-query-pro-decision-card"
                    className="mb-4 rounded-lg border border-primary/45 bg-primary/10 p-3"
                  >
                    <div className="grid gap-3 xl:grid-cols-[minmax(0,1.2fr)_minmax(18rem,0.8fr)]">
                      <div className="min-w-0">
                        <div className="flex min-w-0 flex-wrap items-center gap-2">
                          <span className="rounded-md border border-primary/40 bg-background/40 px-2 py-1 text-xs font-semibold text-primary">
                            {basicProDecisionCard.title}
                          </span>
                          <span className="rounded-md border border-subtle/80 bg-background/35 px-2 py-1 text-xs text-secondary-text">
                            {basicProDecisionCard.priorityLabel}
                            <span className="ml-1 font-semibold text-foreground">{basicProDecisionCard.priorityValue}</span>
                          </span>
                          <span className="rounded-md border border-subtle/80 bg-background/35 px-2 py-1 text-xs text-secondary-text">
                            {basicProDecisionCard.boundary}
                          </span>
                        </div>
                        <div className="mt-3 rounded-lg border border-subtle/80 bg-background/35 p-3">
                          <div className="text-xs font-medium text-primary">{basicProDecisionCard.oneLineLabel}</div>
                          <h3 className="mt-1 text-xl font-semibold leading-snug text-foreground">
                            {basicProDecisionCard.oneLine}
                          </h3>
                        </div>
                        <div className="mt-3 grid gap-2 md:grid-cols-3">
                          {basicProDecisionCard.evidenceItems.map((item) => (
                            <div key={item.label} className="min-w-0 rounded-md border border-subtle/80 bg-background/35 p-2.5">
                              <div className="text-xs font-medium text-primary">{item.label}</div>
                              <div className="mt-1 truncate text-sm font-semibold text-foreground">{item.value}</div>
                              <p className="mt-1 line-clamp-3 text-xs leading-relaxed text-secondary-text">{item.detail}</p>
                            </div>
                          ))}
                        </div>
                      </div>
                      <div className="min-w-0 space-y-2">
                        <div className="rounded-lg border border-subtle/80 bg-background/35 p-3">
                          <div className="text-xs font-medium text-primary">{basicProDecisionCard.evidenceLabel}</div>
                          <div className="mt-2 flex min-w-0 flex-wrap gap-1.5 text-[11px] text-secondary-text">
                            {basicProDecisionCard.evidenceItems.map((item) => (
                              <span key={`${item.label}-${item.value}`} className="max-w-full rounded-md border border-subtle/70 px-1.5 py-0.5">
                                {item.label}
                              </span>
                            ))}
                          </div>
                        </div>
                        <div className="rounded-lg border border-warning/35 bg-warning/10 p-3">
                          <div className="text-xs font-medium text-warning">{basicProDecisionCard.riskLabel}</div>
                          <div className="mt-2 grid gap-1.5 text-xs leading-relaxed text-secondary-text">
                            {basicProDecisionCard.riskItems.map((item, index) => (
                              <div key={`${index}-${item}`} className="rounded-md border border-subtle/70 bg-background/30 px-2 py-1">
                                {item}
                              </div>
                            ))}
                          </div>
                        </div>
                        <div className="rounded-lg border border-primary/30 bg-surface/45 p-3">
                          <div className="text-xs font-medium text-primary">{basicProDecisionCard.upgradeLabel}</div>
                          <div className="mt-2 flex min-w-0 flex-wrap gap-1.5 text-[11px] text-secondary-text">
                            <span className="max-w-full rounded-md border border-primary/35 bg-primary/10 px-1.5 py-0.5 text-primary">
                              {basicProDecisionCard.freeOpenLabel}: {basicProDecisionCard.freeOpenModules}
                            </span>
                            <span className="max-w-full rounded-md border border-subtle/70 px-1.5 py-0.5">
                              {basicProDecisionCard.premiumLabel}
                            </span>
                            {basicProDecisionCard.upgradeItems.map((item) => (
                              <span key={item} className="max-w-full rounded-md border border-subtle/70 px-1.5 py-0.5">
                                {item}
                              </span>
                            ))}
                          </div>
                        </div>
                      </div>
                    </div>
                  </section>
                ) : null}
                {basicSnapshotViewMode === 'quick' && basicQuoteTrustPanel ? (
                  <section
                    data-testid="basic-query-quote-trust-panel"
                    className="mb-4 rounded-lg border border-primary/40 bg-surface/55 p-3"
                  >
                    <div className="flex min-w-0 flex-col gap-3 xl:flex-row xl:items-start xl:justify-between">
                      <div className="min-w-0">
                        <div className="text-xs font-semibold text-primary">{basicQuoteTrustPanel.title}</div>
                        <h3 className="mt-1 text-lg font-semibold leading-snug text-foreground">
                          {basicQuoteTrustPanel.subtitle}
                        </h3>
                      </div>
                      <div className="flex shrink-0 flex-wrap items-center gap-2 xl:justify-end">
                        <span className="rounded-md border border-primary/40 bg-primary/10 px-2 py-1 text-xs font-semibold text-primary">
                          {basicQuoteTrustPanel.statusValue}
                        </span>
                        <Button
                          type="button"
                          variant="secondary"
                          size="sm"
                          disabled={isQueryingBasic}
                          onClick={() => void handleBasicQuery(basicSnapshot.stockCode, undefined, true, undefined, basicSnapshotViewMode)}
                        >
                          <RefreshCw className="h-4 w-4" aria-hidden="true" />
                          {basicQuoteTrustPanel.refreshLabel}
                        </Button>
                      </div>
                    </div>
                    <div className="mt-3 grid gap-2 md:grid-cols-2 xl:grid-cols-4">
                      {basicQuoteTrustPanel.cards.map((card) => (
                        <div key={card.label} className="min-w-0 rounded-md border border-subtle/75 bg-background/35 p-2.5">
                          <div className="text-xs font-medium text-primary">{card.label}</div>
                          <div className="mt-1 truncate text-sm font-semibold text-foreground">{card.value}</div>
                          <p className="mt-1 line-clamp-3 text-xs leading-relaxed text-secondary-text">
                            {card.detail}
                          </p>
                        </div>
                      ))}
                    </div>
                    <div className="mt-3 flex min-w-0 flex-col gap-2 rounded-md border border-primary/30 bg-primary/10 p-2.5 sm:flex-row sm:items-center sm:justify-between">
                      <div className="text-xs font-semibold text-primary">{basicQuoteTrustPanel.upgradeLabel}</div>
                      <div className="flex min-w-0 flex-wrap gap-1.5 text-[11px] text-secondary-text sm:justify-end">
                        {basicQuoteTrustPanel.upgradeItems.map((item) => (
                          <span key={item} className="max-w-full rounded-md border border-primary/25 bg-background/35 px-1.5 py-0.5 text-primary">
                            {item}
                          </span>
                        ))}
                      </div>
                    </div>
                  </section>
                ) : null}
                {basicSnapshotViewMode === 'quick' && basicSourceRecoveryPanel ? (
                  <section
                    data-testid="basic-query-source-recovery-panel"
                    className="mb-4 rounded-lg border border-warning/35 bg-warning/10 p-3"
                  >
                    <div className="flex min-w-0 flex-col gap-3 xl:flex-row xl:items-start xl:justify-between">
                      <div className="min-w-0">
                        <div className="text-xs font-semibold text-warning">{basicSourceRecoveryPanel.title}</div>
                        <h3 className="mt-1 text-lg font-semibold leading-snug text-foreground">
                          {basicSourceRecoveryPanel.subtitle}
                        </h3>
                      </div>
                      <div className="flex shrink-0 flex-wrap items-center gap-2 xl:justify-end">
                        <span className="rounded-md border border-subtle/75 bg-background/35 px-2 py-1 text-xs text-secondary-text">
                          {basicSourceRecoveryPanel.boundary}
                        </span>
                        <Button
                          type="button"
                          variant="secondary"
                          size="sm"
                          data-testid="basic-query-source-recovery-refresh"
                          disabled={isQueryingBasic}
                          onClick={() => void handleBasicQuery(basicSnapshot.stockCode, undefined, true, undefined, basicSnapshotViewMode)}
                        >
                          <RefreshCw className="h-4 w-4" aria-hidden="true" />
                          {basicSourceRecoveryPanel.refreshLabel}
                        </Button>
                      </div>
                    </div>
                    <div className="mt-3 grid gap-2 lg:grid-cols-3">
                      {basicSourceRecoveryPanel.reasonCards.map((card) => (
                        <div key={card.label} className="min-w-0 rounded-md border border-subtle/75 bg-background/35 p-2.5">
                          <div className="text-xs font-medium text-warning">{card.label}</div>
                          <div className="mt-1 text-sm font-semibold text-foreground">{card.value}</div>
                          <p className="mt-1 line-clamp-3 text-xs leading-relaxed text-secondary-text">
                            {card.detail}
                          </p>
                        </div>
                      ))}
                    </div>
                    <div className="mt-3 grid gap-3 xl:grid-cols-2">
                      <div className="min-w-0 rounded-md border border-subtle/75 bg-background/35 p-3">
                        <div className="text-sm font-semibold text-foreground">{basicSourceRecoveryPanel.freeTitle}</div>
                        <div className="mt-2 grid gap-2 sm:grid-cols-2">
                          {basicSourceRecoveryPanel.freeActions.map((item, index) => (
                            <div
                              key={`${index}-${item}`}
                              className="flex min-w-0 items-start gap-2 rounded-md border border-subtle/70 bg-surface/35 px-2.5 py-2 text-xs leading-relaxed text-secondary-text"
                            >
                              <Check className="mt-0.5 h-3.5 w-3.5 shrink-0 text-primary" aria-hidden="true" />
                              <span>{item}</span>
                            </div>
                          ))}
                        </div>
                      </div>
                      <div className="min-w-0 rounded-md border border-primary/35 bg-primary/10 p-3">
                        <div className="text-sm font-semibold text-primary">{basicSourceRecoveryPanel.premiumTitle}</div>
                        <div className="mt-2 grid gap-2 sm:grid-cols-2">
                          {basicSourceRecoveryPanel.premiumItems.map((item, index) => (
                            <div
                              key={`${index}-${item}`}
                              className="rounded-md border border-primary/25 bg-background/35 px-2.5 py-2 text-xs font-medium text-primary"
                            >
                              {item}
                            </div>
                          ))}
                        </div>
                      </div>
                    </div>
                  </section>
                ) : null}
                {basicSnapshotViewMode === 'quick' && basicVerifiedDataBoard ? (
                  <section
                    data-testid="basic-query-verified-data-board"
                    className="mb-4 rounded-lg border border-primary/40 bg-surface/50 p-3"
                  >
                    <div className="flex min-w-0 flex-col gap-3 xl:flex-row xl:items-start xl:justify-between">
                      <div className="min-w-0">
                        <div className="text-xs font-semibold text-primary">{basicVerifiedDataBoard.title}</div>
                        <h3 className="mt-1 text-lg font-semibold leading-snug text-foreground">
                          {basicVerifiedDataBoard.subtitle}
                        </h3>
                      </div>
                      <div className="flex shrink-0 flex-wrap gap-1.5 text-[11px] text-secondary-text xl:max-w-sm xl:justify-end">
                        <span className="rounded-md border border-primary/35 bg-primary/10 px-2 py-1 text-primary">
                          {basicVerifiedDataBoard.freeLabel}
                        </span>
                        <span className="rounded-md border border-subtle/80 bg-background/35 px-2 py-1">
                          {basicVerifiedDataBoard.premiumLabel}
                        </span>
                        <span className="rounded-md border border-subtle/80 bg-background/35 px-2 py-1">
                          {basicVerifiedDataBoard.boundary}
                        </span>
                      </div>
                    </div>
                    <div className="mt-3 grid gap-3 xl:grid-cols-[minmax(0,1.05fr)_minmax(0,0.95fr)]">
                      <div className="min-w-0 rounded-lg border border-subtle/80 bg-background/35 p-3">
                        <div className="text-sm font-semibold text-foreground">{basicVerifiedDataBoard.trustTitle}</div>
                        <div className="mt-2 grid gap-2 sm:grid-cols-2">
                          {basicVerifiedDataBoard.trustCards.map((card) => (
                            <div key={card.label} className="min-w-0 rounded-md border border-subtle/70 bg-surface/35 p-2.5">
                              <div className="text-xs font-medium text-primary">{card.label}</div>
                              <div className="mt-1 truncate text-sm font-semibold text-foreground">{card.value}</div>
                              <p className="mt-1 line-clamp-2 text-xs leading-relaxed text-secondary-text">
                                {card.detail}
                              </p>
                            </div>
                          ))}
                        </div>
                      </div>
                      <div className="min-w-0 rounded-lg border border-subtle/80 bg-background/35 p-3">
                        <div className="text-sm font-semibold text-foreground">{basicVerifiedDataBoard.financialTitle}</div>
                        <div className="mt-2 grid gap-2 sm:grid-cols-2">
                          {basicVerifiedDataBoard.financialMetrics.map((metric) => (
                            <div key={metric.label} className="min-w-0 rounded-md border border-subtle/70 bg-surface/35 px-2.5 py-2">
                              <div className="truncate text-[11px] text-secondary-text">{metric.label}</div>
                              <div className="mt-0.5 truncate text-sm font-semibold text-foreground">{metric.value}</div>
                              <div className="mt-0.5 truncate text-[11px] text-secondary-text">{metric.detail}</div>
                            </div>
                          ))}
                        </div>
                      </div>
                    </div>
                    <div className="mt-3 grid gap-3 xl:grid-cols-[minmax(0,1.05fr)_minmax(0,0.95fr)]">
                      <div className="min-w-0 rounded-lg border border-subtle/80 bg-background/35 p-3">
                        <div className="text-sm font-semibold text-foreground">{basicVerifiedDataBoard.peerTitle}</div>
                        <div className="mt-2 grid gap-1.5 text-xs text-secondary-text">
                          {basicVerifiedDataBoard.peerRows.length > 0 ? basicVerifiedDataBoard.peerRows.map((row) => (
                            <div
                              key={`${row.symbol}-${row.label}`}
                              className="grid gap-1 rounded-md border border-subtle/70 bg-surface/35 px-2.5 py-2 md:grid-cols-[0.75fr_0.85fr_1fr_1.1fr]"
                            >
                              <span className="min-w-0">
                                <span className="block truncate font-semibold text-foreground">{row.symbol}</span>
                                <span className="block truncate text-[11px]">{row.label}</span>
                              </span>
                              <span className="min-w-0 truncate">{row.role}</span>
                              <span className="min-w-0 truncate font-medium text-foreground">{row.quoteValue}</span>
                              <span className="min-w-0 line-clamp-2">{row.currentSignal || row.compareNext}</span>
                            </div>
                          )) : (
                            <div className="rounded-md border border-subtle/70 bg-surface/35 px-2.5 py-2">
                              {uiLanguage === 'en' ? 'No peer reference is available yet.' : '暂无同业参照，先用行情和财务基础判断。'}
                            </div>
                          )}
                        </div>
                      </div>
                      <div className="min-w-0 rounded-lg border border-subtle/80 bg-background/35 p-3">
                        <div className="text-sm font-semibold text-foreground">{basicVerifiedDataBoard.newsTitle}</div>
                        <div className="mt-2 grid gap-2">
                          {basicVerifiedDataBoard.newsCards.map((item, index) => (
                            <div key={`${item.title}-${index}`} className="min-w-0 rounded-md border border-subtle/70 bg-surface/35 p-2.5">
                              <div className="flex min-w-0 items-center justify-between gap-2">
                                <div className="min-w-0 truncate text-xs font-semibold text-foreground">{item.title}</div>
                                <span className="shrink-0 rounded-md border border-subtle/70 px-1.5 py-0.5 text-[10px] text-secondary-text">
                                  {item.status}
                                </span>
                              </div>
                              <p className="mt-1 line-clamp-2 text-xs leading-relaxed text-secondary-text">
                                {item.summary}
                              </p>
                              <div className="mt-2 flex min-w-0 flex-wrap gap-1.5 text-[11px] text-secondary-text">
                                <span className="rounded-md border border-primary/30 bg-primary/10 px-1.5 py-0.5 text-primary">
                                  {item.category}
                                </span>
                                <span className="rounded-md border border-subtle/70 px-1.5 py-0.5">
                                  {item.source}
                                </span>
                                {item.action ? (
                                  <span className="max-w-full truncate rounded-md border border-subtle/70 px-1.5 py-0.5">
                                    {item.action}
                                  </span>
                                ) : null}
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>
                    </div>
                  </section>
                ) : null}
                {basicSnapshotViewMode === 'quick' && basicEventRadar ? (
                  <section
                    data-testid="basic-query-event-radar"
                    className="mb-4 rounded-lg border border-primary/45 bg-primary/10 p-3"
                  >
                    <div className="flex min-w-0 flex-col gap-3 xl:flex-row xl:items-start xl:justify-between">
                      <div className="min-w-0">
                        <div className="text-xs font-semibold text-primary">{basicEventRadar.title}</div>
                        <h3 className="mt-1 text-lg font-semibold leading-snug text-foreground">
                          {basicEventRadar.subtitle}
                        </h3>
                      </div>
                      <div className="flex shrink-0 flex-wrap gap-1.5 text-[11px] text-secondary-text xl:max-w-sm xl:justify-end">
                        <span className="rounded-md border border-primary/35 bg-background/35 px-2 py-1 text-primary">
                          {basicEventRadar.score}
                        </span>
                        <span className="rounded-md border border-subtle/80 bg-background/35 px-2 py-1">
                          {basicEventRadar.boundary}
                        </span>
                      </div>
                    </div>
                    <div className="mt-3 grid gap-3 xl:grid-cols-[minmax(0,1.05fr)_minmax(0,0.95fr)]">
                      <div className="min-w-0 rounded-lg border border-subtle/80 bg-background/35 p-3">
                        <div className="text-sm font-semibold text-foreground">{basicEventRadar.whyTitle}</div>
                        <div className="mt-2 grid gap-2">
                          {basicEventRadar.whyLines.map((line, index) => (
                            <div key={`${index}-${line}`} className="rounded-md border border-subtle/70 bg-surface/35 px-2.5 py-2 text-sm leading-relaxed text-secondary-text">
                              {line}
                            </div>
                          ))}
                        </div>
                      </div>
                      <div className="min-w-0 rounded-lg border border-subtle/80 bg-background/35 p-3">
                        <div className="text-sm font-semibold text-foreground">{basicEventRadar.eventTitle}</div>
                        <div className="mt-2 grid gap-2">
                          {basicEventRadar.events.map((event) => (
                            <div key={event.title} className="min-w-0 rounded-md border border-subtle/70 bg-surface/35 p-2.5">
                              <div className="flex min-w-0 items-center justify-between gap-2">
                                <div className="truncate text-xs font-semibold text-foreground">{event.title}</div>
                                <span className="shrink-0 rounded-md border border-primary/30 bg-primary/10 px-1.5 py-0.5 text-[10px] text-primary">
                                  {event.status}
                                </span>
                              </div>
                              <div className="mt-1 text-sm font-semibold text-foreground">{event.value}</div>
                              <p className="mt-1 line-clamp-2 text-xs leading-relaxed text-secondary-text">
                                {event.detail}
                              </p>
                            </div>
                          ))}
                        </div>
                      </div>
                    </div>
                    <div className="mt-3 grid gap-3 xl:grid-cols-[minmax(0,1.05fr)_minmax(0,0.95fr)]">
                      <div className="min-w-0 rounded-lg border border-subtle/80 bg-background/35 p-3">
                        <div className="text-sm font-semibold text-foreground">{basicEventRadar.nextTitle}</div>
                        <div className="mt-2 grid gap-2 sm:grid-cols-2">
                          {basicEventRadar.nextSteps.map((step, index) => (
                            <div key={`${index}-${step}`} className="flex min-w-0 items-start gap-2 rounded-md border border-subtle/70 bg-surface/35 px-2.5 py-2 text-xs leading-relaxed text-secondary-text">
                              <Check className="mt-0.5 h-3.5 w-3.5 shrink-0 text-primary" aria-hidden="true" />
                              <span>{step}</span>
                            </div>
                          ))}
                        </div>
                      </div>
                      <div className="min-w-0 rounded-lg border border-primary/35 bg-background/35 p-3">
                        <div className="text-sm font-semibold text-primary">{basicEventRadar.upgradeTitle}</div>
                        <div className="mt-2 grid gap-2 sm:grid-cols-2">
                          {basicEventRadar.upgradeItems.map((item) => (
                            <div key={item} className="rounded-md border border-primary/25 bg-primary/10 px-2.5 py-2 text-xs font-medium text-primary">
                              {item}
                            </div>
                          ))}
                        </div>
                      </div>
                    </div>
                  </section>
                ) : null}
                {basicSnapshotViewMode === 'quick' && basicBrokerCockpit ? (
                  <section
                    data-testid="basic-query-broker-cockpit"
                    className="mb-4 rounded-lg border border-primary/40 bg-primary/10 p-3"
                  >
                    <div className="grid gap-3 xl:grid-cols-[minmax(0,1.15fr)_minmax(18rem,0.85fr)]">
                      <div className="min-w-0">
                        <div className="flex min-w-0 flex-wrap items-center gap-2">
                          <span className="rounded-md border border-primary/40 bg-background/40 px-2 py-1 text-xs font-medium text-primary">
                            {basicBrokerCockpit.title}
                          </span>
                          <span className="rounded-md border border-subtle/80 bg-background/30 px-2 py-1 text-xs text-secondary-text">
                            {basicBrokerCockpit.question}
                          </span>
                          <span className="rounded-md border border-primary/35 bg-background/30 px-2 py-1 text-xs font-medium text-primary">
                            {basicBrokerCockpit.scoreLabel} {basicBrokerCockpit.score}
                          </span>
                        </div>
                        <div className="mt-3 rounded-lg border border-subtle/80 bg-background/35 p-3">
                          <div className="text-xs font-medium text-primary">{basicBrokerCockpit.verdictLabel}</div>
                          <h3 className="mt-1 text-xl font-semibold leading-snug text-foreground">
                            {basicBrokerCockpit.verdict}
                          </h3>
                          <p className="mt-2 text-xs leading-relaxed text-secondary-text">
                            {basicBrokerCockpit.freePromise}；{basicBrokerCockpit.premiumPromise}。
                          </p>
                        </div>
                        <div className="mt-3 grid gap-2 md:grid-cols-3">
                          {basicBrokerCockpit.evidenceItems.map((item) => (
                            <div key={item.label} className="min-w-0 rounded-md border border-subtle/70 bg-background/30 p-2.5">
                              <div className="text-xs font-medium text-primary">{item.label}</div>
                              <div className="mt-1 truncate text-sm font-semibold text-foreground">{item.value}</div>
                              <p className="mt-1 line-clamp-3 text-xs leading-relaxed text-secondary-text">{item.detail}</p>
                            </div>
                          ))}
                        </div>
                      </div>
                      <div className="min-w-0 space-y-2">
                        <div className="rounded-lg border border-subtle/80 bg-background/35 p-3">
                          <div className="text-xs font-medium text-primary">{basicBrokerCockpit.proofLabel}</div>
                          <div className="mt-2 grid gap-1.5">
                            {basicBrokerCockpit.nextActions.map((item) => (
                              <div key={item} className="flex min-w-0 items-start gap-2 text-xs leading-relaxed text-secondary-text">
                                <Check className="mt-0.5 h-3.5 w-3.5 shrink-0 text-primary" aria-hidden="true" />
                                <span>{item}</span>
                              </div>
                            ))}
                          </div>
                        </div>
                        <div className="rounded-lg border border-subtle/80 bg-background/35 p-3">
                          <div className="text-xs font-medium text-primary">{basicBrokerCockpit.riskLabel}</div>
                          <div className="mt-2 flex min-w-0 flex-wrap gap-1.5 text-[11px] text-secondary-text">
                            {basicBrokerCockpit.riskItems.slice(0, 4).map((item) => (
                              <span key={item} className="max-w-full rounded-md border border-subtle/70 px-1.5 py-0.5">
                                {item}
                              </span>
                            ))}
                          </div>
                        </div>
                        <div className="rounded-lg border border-primary/30 bg-surface/40 p-3">
                          <div className="text-xs font-medium text-primary">{basicBrokerCockpit.upgradeLabel}</div>
                          <div className="mt-2 grid gap-1.5 sm:grid-cols-2 xl:grid-cols-1">
                            {basicBrokerCockpit.upgradeItems.map((item) => (
                              <div key={item} className="rounded-md border border-subtle/70 bg-background/30 px-2 py-1.5 text-xs text-secondary-text">
                                {item}
                              </div>
                            ))}
                          </div>
                        </div>
                      </div>
                    </div>
                  </section>
                ) : null}
                {basicSnapshotViewMode === 'quick' && basicCommercialJourney ? (
                  <section
                    data-testid="basic-query-commercial-journey"
                    className="mb-4 rounded-lg border border-primary/35 bg-primary/10 p-3"
                  >
                    <div className="flex min-w-0 flex-col gap-3 xl:flex-row xl:items-start xl:justify-between">
                      <div className="min-w-0">
                        <div className="text-xs font-medium text-primary">{basicCommercialJourney.title}</div>
                        <h3 className="mt-1 text-lg font-semibold leading-snug text-foreground">
                          {basicCommercialJourney.subtitle}
                        </h3>
                        <div className="mt-2 flex min-w-0 flex-wrap gap-1.5 text-[11px] text-secondary-text">
                          {basicCommercialJourney.badges.map((badge) => (
                            <span key={badge} className="max-w-full truncate rounded-md border border-primary/30 bg-background/35 px-2 py-1">
                              {badge}
                            </span>
                          ))}
                        </div>
                      </div>
                      <div className="shrink-0 rounded-md border border-primary/30 bg-background/35 px-3 py-2 text-xs leading-relaxed text-secondary-text xl:w-72">
                        <div className="font-medium text-primary">{basicCommercialJourney.upgradeTitle}</div>
                        <div className="mt-2 flex min-w-0 flex-wrap gap-1.5">
                          {basicCommercialJourney.upgradeItems.map((item) => (
                            <span key={item} className="max-w-full truncate rounded-md border border-subtle/70 px-1.5 py-0.5">
                              {item}
                            </span>
                          ))}
                        </div>
                      </div>
                    </div>
                    <div className="mt-3 grid gap-2 md:grid-cols-3">
                      {basicCommercialJourney.steps.map((step) => (
                        <div key={step.title} className="min-w-0 rounded-md border border-subtle/70 bg-background/35 p-2.5">
                          <div className="text-xs font-semibold text-foreground">{step.title}</div>
                          <p className="mt-1 line-clamp-3 text-xs leading-relaxed text-secondary-text">
                            {step.body}
                          </p>
                        </div>
                      ))}
                    </div>
                    <div className="mt-3 rounded-md border border-primary/25 bg-background/35 px-3 py-2 text-xs leading-relaxed text-secondary-text">
                      {uiLanguage === 'en'
                        ? `Free mode keeps ${basicCommercialJourney.moduleText} visible first; premium/API mode improves freshness, source links, and model depth.`
                        : `免费版已开放 ${basicCommercialJourney.moduleText}；高级版/API 模式提升实时性、来源链接和模型深度。`}
                    </div>
                  </section>
                ) : null}
                {basicSnapshotViewMode === 'quick' && basicDataDepthBoard ? (
                  <section
                    data-testid="basic-query-data-depth-board"
                    className="mb-4 rounded-lg border border-primary/35 bg-surface/45 p-3"
                  >
                    <div className="flex min-w-0 flex-col gap-3 xl:flex-row xl:items-start xl:justify-between">
                      <div className="min-w-0">
                        <div className="text-xs font-medium text-primary">{basicDataDepthBoard.title}</div>
                        <h3 className="mt-1 text-lg font-semibold leading-snug text-foreground">
                          {basicDataDepthBoard.marketTitle}
                        </h3>
                        <p className="mt-1 max-w-3xl text-xs leading-relaxed text-secondary-text">
                          {basicDataDepthBoard.subtitle}
                        </p>
                      </div>
                      <div className="flex shrink-0 flex-wrap gap-1.5 text-[11px] text-secondary-text xl:max-w-sm xl:justify-end">
                        {basicDataDepthBoard.tags.map((tag) => (
                          <span key={tag} className="max-w-full truncate rounded-md border border-primary/30 bg-primary/10 px-2 py-1">
                            {tag}
                          </span>
                        ))}
                      </div>
                    </div>
                    <div className="mt-3 grid gap-2 md:grid-cols-2 xl:grid-cols-4">
                      {basicDataDepthBoard.cards.map((card) => (
                        <div
                          key={card.key}
                          data-testid={`basic-query-data-depth-${card.key}`}
                          className="min-w-0 rounded-lg border border-subtle/80 bg-background/35 p-3"
                        >
                          <div className="text-sm font-semibold text-foreground">{card.title}</div>
                          <p className="mt-1 line-clamp-3 text-xs leading-relaxed text-secondary-text">
                            {card.summary}
                          </p>
                          <div className="mt-3 grid gap-2">
                            {card.metrics.map((metric) => (
                              <div key={`${card.key}-${metric.label}`} className="min-w-0 rounded-md border border-subtle/70 bg-surface/35 px-2.5 py-2">
                                <div className="truncate text-[11px] text-secondary-text">{metric.label}</div>
                                <div className="mt-0.5 truncate text-sm font-semibold text-foreground">{metric.value}</div>
                              </div>
                            ))}
                          </div>
                          {card.points?.length ? (
                            <div className="mt-3 flex min-w-0 flex-wrap gap-1.5 text-[11px] text-secondary-text">
                              {card.points.slice(0, 4).map((point, index) => (
                                <span key={`${card.key}-${index}-${point}`} className="max-w-full truncate rounded-md border border-subtle/70 px-1.5 py-0.5">
                                  {point}
                                </span>
                              ))}
                            </div>
                          ) : null}
                          {card.details?.length ? (
                            <details
                              data-testid={
                                card.key === 'core'
                                  ? 'basic-query-data-detail-core'
                                  : card.key === 'events'
                                    ? 'basic-query-data-detail-events'
                                    : `basic-query-data-detail-${card.key}`
                              }
                              className="mt-3 rounded-md border border-subtle/70 bg-surface/30 p-2.5"
                            >
                              <summary className="cursor-pointer text-xs font-medium text-primary">
                                {uiLanguage === 'en' ? 'Expand details' : '展开详情'}
                              </summary>
                              <div className="mt-2 grid gap-1.5 text-[11px] leading-relaxed text-secondary-text">
                                {card.details.slice(0, 7).map((detail, index) => (
                                  <div
                                    key={`${card.key}-detail-${index}`}
                                    className="min-w-0 rounded-md border border-subtle/60 bg-background/25 px-2 py-1"
                                  >
                                    {detail}
                                  </div>
                                ))}
                              </div>
                            </details>
                          ) : null}
                          {card.scenarios?.length ? (
                            <div
                              data-testid="basic-query-kline-triggers"
                              className="mt-3 rounded-md border border-primary/25 bg-primary/10 p-2.5"
                            >
                              <div className="text-xs font-medium text-primary">
                                {uiLanguage === 'en' ? 'K-line triggers' : 'K线触发条件'}
                              </div>
                              <div className="mt-2 grid gap-2">
                                {card.scenarios.map((scenario) => (
                                  <div
                                    key={`${card.key}-${scenario.label}`}
                                    className="min-w-0 rounded-md border border-subtle/70 bg-background/35 px-2 py-1.5"
                                  >
                                    <div className="flex min-w-0 items-center justify-between gap-2">
                                      <span className="min-w-0 truncate text-xs font-semibold text-foreground">
                                        {scenario.label}
                                      </span>
                                      <span className="shrink-0 rounded-md border border-primary/30 px-1.5 py-0.5 text-[10px] text-primary">
                                        {scenario.probability}%
                                      </span>
                                    </div>
                                    <div className="mt-1 text-[11px] leading-relaxed text-secondary-text">
                                      {scenario.trigger}
                                    </div>
                                    <div className="mt-1 line-clamp-2 text-[11px] leading-relaxed text-secondary-text">
                                      {scenario.detail}
                                    </div>
                                  </div>
                                ))}
                              </div>
                            </div>
                          ) : null}
                          {card.peerRows?.length ? (
                            <div
                              data-testid="basic-query-peer-table"
                              className="mt-3 rounded-md border border-primary/25 bg-primary/10 p-2.5"
                            >
                              <div className="text-xs font-medium text-primary">
                                {uiLanguage === 'en' ? 'Peer comparison table' : '同业对比表'}
                              </div>
                              <div className="mt-2 grid gap-1.5 text-[11px] text-secondary-text">
                                <div className="grid gap-1 rounded-md border border-subtle/70 bg-background/35 px-2 py-1 font-medium text-foreground sm:grid-cols-2 xl:grid-cols-[0.9fr_1fr_1.25fr_1.25fr]">
                                  <span>{uiLanguage === 'en' ? 'Symbol' : '标的'}</span>
                                  <span>{uiLanguage === 'en' ? 'Role' : '角色'}</span>
                                  <span>{uiLanguage === 'en' ? 'Current signal' : '当前信号'}</span>
                                  <span>{uiLanguage === 'en' ? 'Next compare' : '下次对比'}</span>
                                </div>
                                {card.peerRows.map((row) => (
                                  <div
                                    key={`${card.key}-${row.symbol}`}
                                    className="grid gap-1 rounded-md border border-subtle/70 bg-background/25 px-2 py-1 sm:grid-cols-2 xl:grid-cols-[0.9fr_1fr_1.25fr_1.25fr]"
                                  >
                                    <span className="min-w-0">
                                      <span className="block truncate font-medium text-foreground">{row.symbol}</span>
                                      <span className="block truncate text-[10px] text-secondary-text">{row.label}</span>
                                    </span>
                                    <span className="min-w-0 truncate">{row.role}</span>
                                    <span className="min-w-0 line-clamp-2">{row.currentSignal}</span>
                                    <span className="min-w-0 line-clamp-2">{row.compareNext}</span>
                                  </div>
                                ))}
                              </div>
                            </div>
                          ) : null}
                        </div>
                      ))}
                    </div>
                    <div className="mt-3 rounded-md border border-primary/25 bg-background/35 px-3 py-2 text-xs leading-relaxed text-secondary-text">
                      {basicDataDepthBoard.footer}
                    </div>
                  </section>
                ) : null}
                {basicSnapshotViewMode === 'quick' && basicProfessionalOverview ? (
                  <section
                    data-testid="basic-query-professional-overview"
                    className="mb-4 rounded-lg border border-primary/30 bg-background/35 p-3"
                  >
                    <div className="flex min-w-0 flex-col gap-2 lg:flex-row lg:items-start lg:justify-between">
                      <div className="min-w-0">
                        <div className="text-xs font-medium text-primary">{basicProfessionalOverview.title}</div>
                        <p className="mt-1 max-w-3xl text-xs leading-relaxed text-secondary-text">
                          {basicProfessionalOverview.subtitle}
                        </p>
                      </div>
                      <div className="flex shrink-0 flex-wrap gap-2 text-[11px] text-secondary-text">
                        {basicProfessionalOverview.channels.map((channel) => (
                          <span key={channel.label} className="inline-flex max-w-full flex-col rounded-md border border-primary/30 bg-primary/10 px-2 py-1">
                            <span className="font-medium text-primary">{channel.label}</span>
                            <span className="max-w-[13rem] truncate">{channel.detail}</span>
                          </span>
                        ))}
                      </div>
                    </div>
                    <div className="mt-3 grid gap-2 md:grid-cols-2 xl:grid-cols-4">
                      {basicProfessionalOverview.stats.map((item) => (
                        <div key={item.label} className="min-w-0 rounded-md border border-subtle/70 bg-surface/45 p-2.5">
                          <div className="truncate text-xs text-secondary-text">{item.label}</div>
                          <div className="mt-1 truncate text-lg font-semibold text-foreground">{item.value}</div>
                          <div className="mt-1 line-clamp-2 text-[11px] leading-relaxed text-secondary-text">{item.detail}</div>
                        </div>
                      ))}
                    </div>
                    <div className="mt-3 rounded-md border border-subtle/70 bg-surface/35 p-2.5">
                      <div className="text-xs font-medium text-primary">
                        {uiLanguage === 'en' ? 'Module navigation' : '模块导航'}
                      </div>
                      <div className="mt-2 grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
                        {basicProfessionalOverview.moduleNav.map((item) => (
                          <div key={item.label} className="min-w-0 rounded-md border border-subtle/70 bg-background/30 px-2.5 py-2">
                            <div className="truncate text-xs font-semibold text-foreground">{item.label}</div>
                            <div className="mt-1 line-clamp-2 text-[11px] leading-relaxed text-secondary-text">{item.detail}</div>
                          </div>
                        ))}
                      </div>
                    </div>
                  </section>
                ) : null}
                {basicSnapshotViewMode === 'quick' && basicFreeResearchBoard ? (
                  <section
                    data-testid="basic-query-free-research-board"
                    className="mb-4 rounded-lg border border-primary/30 bg-surface/45 p-3"
                  >
                    <div className="flex min-w-0 flex-col gap-2 lg:flex-row lg:items-start lg:justify-between">
                      <div className="min-w-0">
                        <div className="text-xs font-medium text-primary">{basicFreeResearchBoard.title}</div>
                        <p className="mt-1 max-w-3xl text-xs leading-relaxed text-secondary-text">
                          {basicFreeResearchBoard.subtitle}
                        </p>
                      </div>
                      <span className="inline-flex shrink-0 rounded-md border border-primary/35 bg-primary/10 px-2 py-1 text-[11px] font-medium text-primary">
                        {basicFreeResearchBoard.channelTag}
                      </span>
                    </div>
                    <div className="mt-3 grid gap-2 md:grid-cols-2 xl:grid-cols-4">
                      {basicFreeResearchBoard.cards.map((card) => (
                        <div
                          key={card.key}
                          data-testid={`basic-query-free-research-${card.key}`}
                          className="min-w-0 rounded-lg border border-subtle/80 bg-background/35 p-3"
                        >
                          <div className="text-xs font-medium text-primary">{card.title}</div>
                          <h4 className="mt-1 line-clamp-2 text-sm font-semibold leading-snug text-foreground">
                            {card.headline}
                          </h4>
                          <p className="mt-2 line-clamp-4 text-xs leading-relaxed text-secondary-text">
                            {card.body}
                          </p>
                          <div className="mt-3 flex min-w-0 flex-wrap gap-1.5 text-[11px] text-secondary-text">
                            {card.points.filter(Boolean).slice(0, 5).map((point) => (
                              <span key={point} className="max-w-full truncate rounded-md border border-subtle/70 px-1.5 py-0.5">
                                {point}
                              </span>
                            ))}
                          </div>
                        </div>
                      ))}
                    </div>
                    <div className="mt-3 rounded-md border border-primary/25 bg-primary/5 px-3 py-2 text-xs leading-relaxed text-secondary-text">
                      {uiLanguage === 'en'
                        ? 'Free mode keeps these reads as local/public-data checklists. API modes improve freshness, source links, and model depth. Informational only, not investment advice.'
                        : '免费版把这些内容作为本地/公开数据检查清单；API 模式提升实时性、来源链接和模型深度。仅作信息分析，不构成投资建议。'}
                    </div>
                  </section>
                ) : null}
                {basicSnapshotViewMode === 'quick' && basicFreeReport ? (
                  <section
                    data-testid="basic-query-free-value-summary"
                    className="mb-4 rounded-lg border border-primary/35 bg-primary/10 p-3"
                  >
                    <div className="flex min-w-0 flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                      <div className="min-w-0">
                        <div className="text-xs font-medium text-primary">
                          {uiLanguage === 'en' ? 'Free value summary' : '免费版重点结论'}
                        </div>
                        <h3 className="mt-1 text-lg font-semibold leading-snug text-foreground">
                          {localizeGeneratedText(basicFreeReport.productBrief.conclusion, uiLanguage)}
                        </h3>
                        <p className="mt-2 text-xs leading-relaxed text-secondary-text">
                          {uiLanguage === 'en'
                            ? 'Free and premium show the same visible modules here; free uses web/local public sources, while API modes improve freshness, stability, and depth.'
                            : '免费版和高级版在这里看到同样模块；免费版使用网络/本地数据，高级版使用 API 或模型通道提升实时性、稳定性和深度。'}
                        </p>
                      </div>
                      <div className="flex shrink-0 flex-wrap gap-2 text-xs">
                        <span className="rounded-md border border-primary/40 bg-primary/10 px-2 py-1 font-medium text-primary">
                          {t('home.noAi')}
                        </span>
                        <span className="rounded-md border border-subtle px-2 py-1 text-secondary-text">
                          {uiLanguage === 'en' ? 'Information only' : '仅作信息分析'}
                        </span>
                      </div>
                    </div>
                    {basicFreeCompleteRead ? (
                      <div
                        data-testid="basic-query-free-complete-read"
                        className="mt-3 rounded-lg border border-primary/25 bg-background/35 p-3"
                      >
                        <div className="flex min-w-0 flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
                          <div className="min-w-0">
                            <div className="text-xs font-medium text-primary">
                              {basicFreeCompleteRead.title}
                            </div>
                            <p className="mt-1 text-xs leading-relaxed text-secondary-text">
                              {basicFreeCompleteRead.subtitle}
                            </p>
                          </div>
                          <span className="inline-flex shrink-0 items-center gap-1 rounded-md border border-primary/40 bg-primary/10 px-2 py-1 text-[11px] font-medium text-primary">
                            <Check className="h-3.5 w-3.5" aria-hidden="true" />
                            {uiLanguage === 'en' ? 'No AI cost' : '不消耗AI'}
                          </span>
                        </div>
                        <div className="mt-3 grid gap-2 lg:grid-cols-5">
                          {basicFreeCompleteRead.items.map((item) => (
                            <div key={item.label} className="min-w-0 rounded-md border border-subtle/70 bg-background/30 p-2.5">
                              <div className="text-xs font-medium text-primary">{item.label}</div>
                              <p className="mt-1 line-clamp-4 text-xs leading-relaxed text-secondary-text">
                                {item.body}
                              </p>
                            </div>
                          ))}
                        </div>
                      </div>
                    ) : null}
                    <div
                      data-testid="basic-query-free-feature-entry"
                      className="mt-3 flex min-w-0 flex-col gap-2 rounded-lg border border-primary/25 bg-background/35 p-3 sm:flex-row sm:items-center sm:justify-between"
                    >
                      <div className="min-w-0">
                        <div className="text-xs font-medium text-primary">
                          {uiLanguage === 'en' ? 'Free feature entry' : '免费功能入口'}
                        </div>
                        <p className="mt-1 text-xs leading-relaxed text-secondary-text">
                          {uiLanguage === 'en'
                            ? 'News and K-line forecast are available below; jump straight to the feature you want to inspect.'
                            : '资讯中心和K线预测已经在本次免费查询里开放，可直接跳到对应功能查看。'}
                        </p>
                      </div>
                      <div className="flex shrink-0 flex-wrap gap-2">
                        <Button
                          type="button"
                          variant="secondary"
                          size="sm"
                          data-testid="basic-query-feature-entry-news"
                          onClick={() => handleBasicFeatureJump('basic-query-news-center')}
                        >
                          <Search className="h-4 w-4" aria-hidden="true" />
                          {uiLanguage === 'en' ? 'News center' : '资讯中心'}
                        </Button>
                        <Button
                          type="button"
                          variant="secondary"
                          size="sm"
                          data-testid="basic-query-feature-entry-kline"
                          onClick={() => handleBasicFeatureJump('basic-query-kline-forecast-lab')}
                        >
                          <BarChart3 className="h-4 w-4" aria-hidden="true" />
                          {uiLanguage === 'en' ? 'K-line forecast' : 'K线预测'}
                        </Button>
                      </div>
                    </div>
                    <div className="mt-3 grid gap-2 md:grid-cols-3">
                      <div className="min-w-0 rounded-lg border border-subtle bg-background/35 p-3">
                        <div className="text-xs font-medium text-primary">
                          {uiLanguage === 'en' ? 'What matters now' : '当前看点'}
                        </div>
                        <div className="mt-2 space-y-1 text-sm font-medium text-foreground">
                          <div className="truncate">
                            {uiLanguage === 'en' ? 'Support' : '支撑'} {localizeGeneratedText(basicFreeReport.productBrief.supportLevels, uiLanguage)}
                          </div>
                          <div className="truncate">
                            {uiLanguage === 'en' ? 'Resistance' : '压力'} {localizeGeneratedText(basicFreeReport.productBrief.pressureLevels, uiLanguage)}
                          </div>
                        </div>
                        <p className="mt-2 text-xs leading-relaxed text-secondary-text">
                          {localizeGeneratedText(basicFreeReport.productBrief.shortStatus, uiLanguage)}
                        </p>
                      </div>
                      <div className="min-w-0 rounded-lg border border-subtle bg-background/35 p-3">
                        <div className="text-xs font-medium text-primary">
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
                      <div className="min-w-0 rounded-lg border border-primary/30 bg-background/35 p-3">
                        <div className="text-xs font-medium text-primary">
                          {uiLanguage === 'en' ? 'Data channel difference' : '数据通道差异'}
                        </div>
                        <p className="mt-2 text-xs leading-relaxed text-secondary-text">
                          {uiLanguage === 'en'
                            ? 'Free keeps the same feature entries with web/local public sources; premium uses platform API, user API, or approved local models for realtime news, filings, fundamentals, and longer reports.'
                            : '免费版保留同样功能入口，默认走网络/本地公开数据；高级版走平台 API、我的 API 或本地模型，适合实时资讯、公告、基本面和长报告。'}
                        </p>
                        <Button
                          type="button"
                          variant="secondary"
                          size="sm"
                          className="mt-3"
                          disabled={isAnalyzing}
                          onClick={() => handleDeepAnalyze(basicSnapshot.stockCode, basicSnapshot.stockName || undefined, 'manual')}
                        >
                          <SlidersHorizontal className="h-4 w-4" aria-hidden="true" />
                          {t('home.deepAnalyze')}
                        </Button>
                      </div>
                    </div>
                  </section>
                ) : null}
                {basicSnapshotViewMode === 'quick' && basicFreeReport ? (
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
                    {basicSnapshotViewMode === 'quick' && basicSnapshot.intelligence?.retentionBrief ? (
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
                    {basicSnapshotViewMode === 'quick' && basicSnapshot.intelligence?.newsCenter ? (
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
                    {basicSnapshotViewMode === 'quick' && basicSnapshot.intelligence?.aShareEnrichment ? (
                      <div
                        data-testid="basic-query-a-share-enrichment"
                        className="mb-3 rounded-lg border border-primary/30 bg-background/40 p-3"
                      >
                        <div className="mb-3 flex min-w-0 flex-col gap-2 lg:flex-row lg:items-start lg:justify-between">
                          <div className="min-w-0">
                            <div className="text-xs font-medium text-primary">
                              {uiLanguage === 'en' ? 'A-share data expansion' : 'A股数据扩展'}
                            </div>
                            <h4 className="mt-1 text-base font-semibold text-foreground">
                              {localizeGeneratedText(basicSnapshot.intelligence.aShareEnrichment.title, uiLanguage)}
                            </h4>
                            <p className="mt-1 text-xs leading-relaxed text-secondary-text">
                              {localizeGeneratedText(basicSnapshot.intelligence.aShareEnrichment.summary, uiLanguage)}
                            </p>
                          </div>
                          <div className="flex shrink-0 flex-wrap gap-1.5 text-[11px]">
                            <span className="rounded-md border border-primary/35 bg-primary/10 px-2 py-1 font-medium text-primary">
                              {localizeGeneratedStatus(basicSnapshot.intelligence.aShareEnrichment.status, uiLanguage)}
                            </span>
                            <span className="rounded-md border border-subtle px-2 py-1 text-secondary-text">
                              {localizeGeneratedSource(basicSnapshot.intelligence.aShareEnrichment.source, uiLanguage)}
                            </span>
                            <span className="rounded-md border border-primary/35 bg-primary/10 px-2 py-1 font-medium text-primary">
                              {basicSnapshot.intelligence.aShareEnrichment.aiUsed
                                ? (uiLanguage === 'en' ? 'AI used' : '已使用 AI')
                                : t('home.noAi')}
                            </span>
                            <span className="rounded-md border border-subtle px-2 py-1 text-secondary-text">
                              {basicSnapshot.intelligence.aShareEnrichment.publicSearchUsed
                                ? (uiLanguage === 'en' ? 'Public search' : '公共搜索')
                                : (uiLanguage === 'en' ? 'No public search' : '未用公共搜索')}
                            </span>
                          </div>
                        </div>
                        <div
                          data-testid="a-share-source-control"
                          className="mb-3 rounded-lg border border-subtle/80 bg-surface/35 p-3"
                        >
                          <div className="flex min-w-0 flex-col gap-2 lg:flex-row lg:items-center lg:justify-between">
                            <div className="min-w-0">
                              <div className="text-sm font-semibold text-foreground">
                                {uiLanguage === 'en' ? 'A-share source' : 'A股数据源'}
                              </div>
                              <div className="mt-1 text-[11px] leading-relaxed text-secondary-text">
                                {uiLanguage === 'en'
                                  ? 'Switch local rules, the a-stock-data adapter, or turn the enrichment lane off for comparison.'
                                  : '可切换本地规则、a-stock-data 适配器或关闭增强通道，用于对比数据差异。'}
                              </div>
                            </div>
                            <div className="flex shrink-0 flex-wrap gap-1.5">
                              {A_SHARE_SOURCE_MODES.map((mode) => (
                                <button
                                  key={mode}
                                  type="button"
                                  data-testid={`a-share-source-mode-${mode}`}
                                  onClick={() => handleAShareSourceModeSelect(mode)}
                                  disabled={isQueryingBasic}
                                  className={[
                                    'rounded-md border px-2.5 py-1.5 text-xs font-medium transition-colors',
                                    aShareSourceMode === mode
                                      ? 'border-primary/60 bg-primary/15 text-primary'
                                      : 'border-subtle text-secondary-text hover:border-primary/40 hover:text-primary',
                                    isQueryingBasic ? 'opacity-60' : '',
                                  ].join(' ')}
                                >
                                  {aShareSourceModeLabel(mode, uiLanguage)}
                                </button>
                              ))}
                            </div>
                          </div>
                          <div className="mt-2 flex min-w-0 flex-wrap gap-1.5 text-[11px] text-secondary-text">
                            <span className="rounded-md border border-subtle/70 px-1.5 py-0.5">
                              {formatAShareCacheDiagnostics(aShareEnrichmentDiagnostics, uiLanguage)}
                            </span>
                            <span className="rounded-md border border-subtle/70 px-1.5 py-0.5">
                              {formatAShareSkillRevision(aShareEnrichmentSkill, uiLanguage)}
                            </span>
                            <span className="rounded-md border border-subtle/70 px-1.5 py-0.5">
                              {formatAShareRateLimited(aShareEnrichmentDiagnostics, uiLanguage)}
                            </span>
                            <span className="rounded-md border border-subtle/70 px-1.5 py-0.5">
                              {uiLanguage === 'en' ? 'mode' : '模式'} {aShareSourceModeLabel(normalizeAShareSourceMode(aShareEnrichment?.sourceMode), uiLanguage)}
                            </span>
                            {aShareEnrichment?.updatedAt ? (
                              <span className="max-w-full truncate rounded-md border border-subtle/70 px-1.5 py-0.5">
                                {aShareEnrichment.updatedAt}
                              </span>
                            ) : null}
                          </div>
                          <div className="mt-2 flex min-w-0 flex-wrap items-center gap-1.5 text-xs">
                            <span className="text-secondary-text">{uiLanguage === 'en' ? 'Probe' : '实测'}</span>
                            {['600519', '000001'].map((symbol) => (
                              <button
                                key={symbol}
                                type="button"
                                data-testid={`a-share-source-probe-${symbol}`}
                                onClick={() => handleAShareSourceProbe(symbol)}
                                disabled={isQueryingBasic}
                                className="rounded-md border border-primary/35 bg-primary/10 px-2 py-1 font-medium text-primary transition-colors hover:bg-primary/15 disabled:opacity-60"
                              >
                                {symbol}
                              </button>
                            ))}
                          </div>
                        </div>
                        {basicSnapshot.intelligence.aShareEnrichment.readerSummary ? (
                          <div
                            data-testid="basic-query-a-share-reader-summary"
                            className="mb-3 rounded-lg border border-primary/25 bg-background/35 p-3"
                          >
                            <div className="mb-3 flex min-w-0 flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
                              <div className="min-w-0">
                                <div className="text-xs font-medium text-primary">
                                  {uiLanguage === 'en' ? 'Useful readout' : '为什么值得看'}
                                </div>
                                <h5 className="mt-1 text-sm font-semibold text-foreground">
                                  {localizeGeneratedText(basicSnapshot.intelligence.aShareEnrichment.readerSummary.headline, uiLanguage)}
                                </h5>
                              </div>
                              <span className="shrink-0 rounded-md border border-subtle/70 px-2 py-1 text-[11px] text-secondary-text">
                                {localizeGeneratedText(basicSnapshot.intelligence.aShareEnrichment.readerSummary.boundary, uiLanguage)}
                              </span>
                            </div>
                            <p className="mb-3 text-xs leading-relaxed text-secondary-text">
                              {localizeGeneratedText(basicSnapshot.intelligence.aShareEnrichment.readerSummary.whyRead, uiLanguage)}
                            </p>
                            <div className="mb-3 grid gap-2 md:grid-cols-2 xl:grid-cols-4">
                              {(basicSnapshot.intelligence.aShareEnrichment.readerSummary.keyFacts ?? []).map((item, index) => (
                                <div
                                  key={`${item.label || 'fact'}-${index}`}
                                  className="min-w-0 rounded-lg border border-subtle/70 bg-surface/35 p-2.5"
                                >
                                  <div className="text-[11px] text-primary">
                                    {localizeGeneratedText(item.label, uiLanguage)}
                                  </div>
                                  <div className="mt-1 truncate text-sm font-semibold text-foreground">
                                    {localizeGeneratedText(item.value, uiLanguage)}
                                  </div>
                                  <p className="mt-1 line-clamp-2 text-[11px] leading-relaxed text-secondary-text">
                                    {localizeGeneratedText(item.detail, uiLanguage)}
                                  </p>
                                </div>
                              ))}
                            </div>
                            <div className="grid gap-2 lg:grid-cols-2">
                              <div className="rounded-lg border border-subtle/70 bg-surface/25 p-2.5">
                                <div className="mb-2 text-xs font-semibold text-foreground">
                                  {uiLanguage === 'en' ? 'Missing or degraded notes' : '未命中说明'}
                                </div>
                                {(basicSnapshot.intelligence.aShareEnrichment.readerSummary.missExplanations ?? []).length > 0 ? (
                                  <div className="space-y-2">
                                    {(basicSnapshot.intelligence.aShareEnrichment.readerSummary.missExplanations ?? []).map((item, index) => (
                                      <div key={`${item.title || 'miss'}-${index}`} className="text-xs leading-relaxed text-secondary-text">
                                        <span className="font-medium text-foreground">
                                          {localizeGeneratedText(item.title, uiLanguage)}
                                        </span>
                                        <span>：{localizeGeneratedText(item.explanation, uiLanguage)}</span>
                                        {item.nextStep ? (
                                          <span className="block text-[11px] text-muted-text">
                                            {localizeGeneratedText(item.nextStep, uiLanguage)}
                                          </span>
                                        ) : null}
                                      </div>
                                    ))}
                                  </div>
                                ) : (
                                  <p className="text-xs text-secondary-text">
                                    {uiLanguage === 'en' ? 'No obvious missing lane in this quick view.' : '本次快速视图没有明显缺口。'}
                                  </p>
                                )}
                              </div>
                              <div className="rounded-lg border border-primary/25 bg-primary/5 p-2.5">
                                <div className="mb-2 text-xs font-semibold text-foreground">
                                  {uiLanguage === 'en' ? 'Version difference' : '版本差异'}
                                </div>
                                <div className="flex min-w-0 flex-wrap gap-1.5 text-[11px] text-secondary-text">
                                  {(basicSnapshot.intelligence.aShareEnrichment.readerSummary.premiumFeatures ?? []).map((feature) => (
                                    <span
                                      key={feature}
                                      className="rounded-md border border-primary/25 bg-background/30 px-2 py-1"
                                    >
                                      {localizeGeneratedText(feature, uiLanguage)}
                                    </span>
                                  ))}
                                </div>
                              </div>
                            </div>
                          </div>
                        ) : null}
                        <div className="grid gap-2 md:grid-cols-2 xl:grid-cols-5">
                          {basicSnapshot.intelligence.aShareEnrichment.channels.map((item) => (
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
                              {(item.details ?? []).length > 0 ? (
                                <div
                                  data-testid={`a-share-channel-details-${item.category}`}
                                  className="mt-2 grid min-w-0 gap-1.5"
                                >
                                  {(item.details ?? []).slice(0, 4).map((detail, index) => (
                                    <div
                                      key={`${detail.label || 'detail'}-${index}`}
                                      className="min-w-0 rounded-md border border-subtle/70 bg-background/30 px-2 py-1.5"
                                    >
                                      <div className="truncate text-[11px] text-secondary-text">
                                        {localizeGeneratedText(detail.label || '-', uiLanguage)}
                                      </div>
                                      <div className="mt-0.5 truncate text-xs font-semibold text-foreground">
                                        {localizeGeneratedText(detail.value || '-', uiLanguage)}
                                      </div>
                                      {detail.detail ? (
                                        <div className="mt-0.5 line-clamp-1 text-[11px] text-muted-text">
                                          {localizeGeneratedText(detail.detail, uiLanguage)}
                                        </div>
                                      ) : null}
                                    </div>
                                  ))}
                                </div>
                              ) : null}
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
                            {localizeGeneratedText(basicSnapshot.intelligence.aShareEnrichment.premiumUnlock, uiLanguage)}
                          </span>
                          <span className="shrink-0 rounded-md border border-subtle/70 px-2 py-1">
                            {localizeGeneratedText(basicSnapshot.intelligence.aShareEnrichment.boundary, uiLanguage)}
                          </span>
                        </div>
                      </div>
                    ) : null}
                    {basicSnapshotViewMode === 'quick' && basicSnapshot.intelligence?.klineForecast ? (
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
                              <div className="font-semibold">
                                {uiLanguage === 'en' ? 'Kronos did not finish this run' : 'Kronos 本次没有跑通'}
                              </div>
                              <p className="mt-1 leading-relaxed">
                                {uiLanguage === 'en'
                                  ? 'This is usually a local model, proxy, or dependency timeout. The page keeps the local K-line rules preview, and free quote lookup is not affected.'
                                  : '这通常是本地模型、网络代理或依赖超时导致；页面会保留本地K线规则预览，不影响免费行情查询。'}
                              </p>
                              <p className="mt-1 leading-relaxed text-danger/90">
                                {kronosForecastError}
                              </p>
                            </div>
                          ) : null}
                          {kronosForecast ? (
                            <div data-testid="basic-query-kronos-live-result" className="mt-3 space-y-3">
                              <div
                                data-testid="basic-query-kronos-readiness-summary"
                                className="rounded-lg border border-primary/30 bg-primary/5 p-3 text-xs text-secondary-text"
                              >
                                <div className="font-semibold text-primary">
                                  {uiLanguage === 'en' ? 'This is not a failed run' : '这不是运行失败'}
                                </div>
                                <p className="mt-1 leading-relaxed">
                                  {kronosForecast.kronosModelUsed
                                    ? (uiLanguage === 'en'
                                      ? 'The real Kronos model responded for this check; keep treating it as an experimental model preview.'
                                      : '真实 Kronos 模型已响应本次检查；仍按实验性模型预览理解。')
                                    : (uiLanguage === 'en'
                                      ? 'Using local K-line rules fallback. Real Kronos model is not enabled yet.'
                                      : '当前使用本地K线规则兜底。真实 Kronos 模型尚未启用。')}
                                </p>
                                <p className="mt-1 leading-relaxed">
                                  {uiLanguage === 'en'
                                    ? 'Premium can run the full forecast after model or API lane approval; this preview remains informational only, not investment advice.'
                                    : '高级版可在模型或 API 通道确认后启用完整预测；当前预览仅作信息分析，不构成投资建议。'}
                                </p>
                              </div>
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
                    {basicSnapshotViewMode === 'quick' && (basicSnapshot.intelligence?.newsCenter || basicSnapshot.intelligence?.aShareEnrichment || basicSnapshot.intelligence?.klineForecast) ? (
                      <div
                        data-testid="basic-query-premium-feature-ladder"
                        className="mb-3 grid gap-2 rounded-lg border border-primary/25 bg-background/35 p-3 md:grid-cols-4"
                      >
                        {[
                          [
                            uiLanguage === 'en' ? 'Same modules' : '同样功能',
                            uiLanguage === 'en' ? 'Free and premium both show quote, news, A-share enrichment, K-line forecast, history, and watchlist entries.' : '免费版和高级版都展示行情、资讯、A股增强、K线预测、历史和自选入口。',
                          ],
                          [
                            uiLanguage === 'en' ? 'Free web sources' : '免费网络源',
                            uiLanguage === 'en' ? 'Free mode uses web/local public sources, so cache, degraded lanes, or incomplete sources may appear.' : '免费版默认走网络/本地公开数据，可能出现缓存、降级或来源不完整提示。',
                          ],
                          [
                            uiLanguage === 'en' ? 'Premium API sources' : '高级 API 源',
                            uiLanguage === 'en' ? 'Premium uses platform API, user API, or authorized feeds to improve realtime news, filings, and reliability.' : '高级版走平台 API、我的 API 或授权数据源，优先解决实时资讯、公告和稳定性。',
                          ],
                          [
                            uiLanguage === 'en' ? 'BYOK or local model' : '我的 API 或本地模型',
                            uiLanguage === 'en' ? 'Kronos-ready forecasts and deeper AI reads can use user API, platform API, or approved local model quota.' : 'Kronos 已就绪后可运行预测；更深 AI 分析可使用我的 API、平台 API 或已批准的本地模型额度。',
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
                    {basicSnapshotViewMode === 'quick' && basicSnapshot.intelligence?.items?.length ? (
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
                    {basicSnapshotViewMode === 'quick' && basicSnapshot.intelligence?.marketBrief ? (
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
                    {basicSnapshotViewMode === 'quick' && basicSnapshot.intelligence?.freeInsights?.length ? (
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
                    {basicSnapshotViewMode === 'quick' && basicSnapshot.intelligence?.peerComparison?.rows?.length ? (
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
                          <div className="hidden grid-cols-[minmax(7rem,0.75fr)_minmax(8rem,0.75fr)_minmax(9rem,0.85fr)_minmax(12rem,1.2fr)_minmax(12rem,1.1fr)] gap-2 border-b border-subtle/70 bg-surface/35 px-3 py-2 text-[11px] font-medium text-secondary-text md:grid">
                            <div>{uiLanguage === 'en' ? 'Reference' : '参照对象'}</div>
                            <div>{uiLanguage === 'en' ? 'Role' : '角色'}</div>
                            <div>{uiLanguage === 'en' ? 'Ref quote' : '参照行情'}</div>
                            <div>{uiLanguage === 'en' ? 'Current signal' : '本股位置'}</div>
                            <div>{uiLanguage === 'en' ? 'Next check' : '下一步对比'}</div>
                          </div>
                          <div className="divide-y divide-subtle/70">
                            {basicSnapshot.intelligence.peerComparison.rows.map((row) => (
                              <div
                                key={`${row.symbol}-${row.role}`}
                                className="grid gap-2 px-3 py-3 text-xs md:grid-cols-[minmax(7rem,0.75fr)_minmax(8rem,0.75fr)_minmax(9rem,0.85fr)_minmax(12rem,1.2fr)_minmax(12rem,1.1fr)]"
                              >
                                <div className="min-w-0">
                                  <div className="font-semibold text-foreground">{row.symbol}</div>
                                  <div className="mt-0.5 truncate text-[11px] text-secondary-text">{localizeGeneratedText(row.label, uiLanguage)}</div>
                                </div>
                                <div className="min-w-0 text-secondary-text">
                                  <span className="rounded-md border border-subtle/70 px-1.5 py-0.5">{localizeGeneratedText(row.role, uiLanguage)}</span>
                                </div>
                                <div className="min-w-0 leading-relaxed text-secondary-text">
                                  {row.referenceQuote?.status === 'available' ? (
                                    <div className="space-y-0.5">
                                      <div className="font-medium text-foreground">
                                        {uiLanguage === 'en' ? 'Price' : '参照价'} {formatBasicNumber(row.referenceQuote.currentPrice ?? row.referenceQuote.price)}
                                      </div>
                                      <div>
                                        {uiLanguage === 'en' ? 'Chg' : '涨跌'} {formatSignedBasicPercent(row.referenceQuote.changePercent)}
                                      </div>
                                      <div className="truncate text-[11px]">
                                        {localizeRuntimeLabel(row.referenceQuote.freshness, uiLanguage)}
                                      </div>
                                    </div>
                                  ) : (
                                    <span className="text-[11px] text-secondary-text">
                                      {uiLanguage === 'en' ? 'Quote unavailable' : '参照行情暂不可用'}
                                    </span>
                                  )}
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
                    {basicSnapshotViewMode === 'quick' && (basicSnapshot.intelligence?.watchPoints?.length || basicSnapshot.intelligence?.comparisonTargets?.length) ? (
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
                          <div className="mt-2 grid gap-2">
                            {(basicSnapshot.intelligence?.comparisonTargets ?? []).map((item) => (
                              <div
                                key={`${item.symbol}-${item.label}`}
                                className="min-w-0 rounded-lg border border-subtle/80 bg-background/45 px-2.5 py-2 text-[11px] text-secondary-text"
                                title={localizeGeneratedText(item.reason, uiLanguage)}
                              >
                                <div className="flex min-w-0 items-start justify-between gap-2">
                                  <div className="min-w-0">
                                    <div className="truncate font-medium text-foreground">
                                      {item.symbol}
                                      <span className="ml-1 text-secondary-text">{localizeGeneratedText(item.label, uiLanguage)}</span>
                                    </div>
                                    <div className="mt-0.5 truncate">{localizeGeneratedText(item.reason, uiLanguage)}</div>
                                  </div>
                                  <span className="shrink-0 rounded-md border border-subtle/80 px-1.5 py-0.5">
                                    {localizeRuntimeLabel(item.referenceQuote?.freshness || item.status, uiLanguage)}
                                  </span>
                                </div>
                                {item.referenceQuote?.status === 'available' ? (
                                  <div className="mt-2 grid grid-cols-2 gap-1.5">
                                    <div className="rounded-md border border-subtle/70 bg-surface/35 px-2 py-1">
                                      <div className="text-[10px] text-secondary-text">{uiLanguage === 'en' ? 'Price' : '参照价'}</div>
                                      <div className="text-sm font-semibold text-foreground">{formatBasicNumber(item.referenceQuote.currentPrice ?? item.referenceQuote.price)}</div>
                                    </div>
                                    <div className="rounded-md border border-subtle/70 bg-surface/35 px-2 py-1">
                                      <div className="text-[10px] text-secondary-text">{uiLanguage === 'en' ? 'Change' : '涨跌幅'}</div>
                                      <div className="text-sm font-semibold text-foreground">{formatSignedBasicPercent(item.referenceQuote.changePercent)}</div>
                                    </div>
                                  </div>
                                ) : (
                                  <div className="mt-2 rounded-md border border-subtle/70 bg-surface/35 px-2 py-1 text-[11px]">
                                    {uiLanguage === 'en' ? 'Reference quote is temporarily unavailable.' : '参照行情暂不可用，刷新后可再对比。'}
                                  </div>
                                )}
                              </div>
                            ))}
                          </div>
                          <div className="mt-3 text-[11px] leading-relaxed text-secondary-text">
                            {uiLanguage === 'en'
                              ? 'Free mode shows available public reference quotes; premium can switch the same comparison to steadier API-backed sources.'
                              : '免费版会显示可用的公共参照行情；高级版可把同一对比切换到更稳定的 API 数据源。'}
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
                              {uiLanguage === 'en'
                                ? 'Use deep analysis when the same module needs API-backed freshness, source links, fundamentals, or a longer AI-written report.'
                                : '当同样模块需要 API 级实时性、来源链接、基本面或更长 AI 报告时，再使用深度分析。'}
                            </div>
                          </div>
                          <Button
                            type="button"
                            variant="secondary"
                            size="sm"
                            disabled={isAnalyzing}
                            onClick={() => handleDeepAnalyze(basicSnapshot.stockCode, basicSnapshot.stockName || undefined, 'manual')}
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
                {basicSnapshotViewMode === 'quick' ? (
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
                ) : null}
                {basicSnapshotViewMode === 'quick' && basicSnapshot.profile ? (
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
                            {uiLanguage === 'en' ? `BYOK ${byokStatusText}; quick bucket ${byokAiQuotaText}` : `${byokStatusText}；快速额度 ${byokAiQuotaText}`}
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
                              {uiLanguage === 'en' ? 'BYOK' : '我的 API'}
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
                      onClick={() => void handleBasicQuery(basicSnapshot.stockCode, undefined, true, undefined, basicSnapshotViewMode)}
                    >
                      <RefreshCw className="h-4 w-4" aria-hidden="true" />
                      {uiLanguage === 'en' ? 'Refresh quote' : '刷新行情'}
                    </Button>
                    <Button
                      type="button"
                      variant="secondary"
                      size="sm"
                      disabled={isQueryingBasic}
                      onClick={() => handleQuickAnalyze(basicSnapshot.stockCode, basicSnapshot.stockName || undefined, 'manual')}
                    >
                      <Sparkles className="h-4 w-4" aria-hidden="true" />
                      {t('home.quickAnalyze')}
                    </Button>
                    <Button
                      type="button"
                      variant="secondary"
                      size="sm"
                      disabled={isAnalyzing}
                      onClick={() => handleDeepAnalyze(basicSnapshot.stockCode, basicSnapshot.stockName || undefined, 'manual')}
                    >
                      <SlidersHorizontal className="h-4 w-4" aria-hidden="true" />
                      {t('home.deepAnalyze')}
                    </Button>
                  </div>
                </div>
                {deepAnalysisInlineNotice ? (
                  <div
                    ref={deepInlineGuardRef}
                    data-testid="basic-query-deep-inline-guard"
                    role="alert"
                    className="mt-3 rounded-lg border border-primary/35 bg-primary/5 px-3 py-2 text-xs text-secondary-text"
                  >
                    <div className="font-semibold text-primary">
                      {uiLanguage === 'en' ? 'Deep analysis needs an account' : '深度分析需要先登录'}
                    </div>
                    <p className="mt-1 leading-relaxed">
                      {deepAnalysisInlineNotice}
                    </p>
                    <div className="mt-2 flex min-w-0 flex-wrap gap-2">
                      <span className="rounded-md border border-subtle/70 px-2 py-1">
                        {uiLanguage === 'en'
                          ? 'Choose Platform API, BYOK, or local model after login'
                          : '登录后可选择平台 API、我的 API 或本地模型'}
                      </span>
                      <span className="rounded-md border border-subtle/70 px-2 py-1">
                        {uiLanguage === 'en'
                          ? 'Free query and quick analysis remain available'
                          : '当前免费查询和快速分析仍可继续使用'}
                      </span>
                    </div>
                  </div>
                ) : null}
                <div className="mt-3 text-xs text-secondary-text">
                  {t('home.basicSource')}: {localizeGeneratedSource(basicSnapshot.quote.source, uiLanguage)}
                  {basicSnapshot.route ? (
                    <span data-testid="basic-query-route" className="ml-2">
                      {uiLanguage === 'en' ? 'Lane' : '通道'}: {marketLaneLabel(basicSnapshot.route.dataSourceLane, uiLanguage)} / {basicSnapshot.route.channel}
                    </span>
                  ) : null}
                </div>
                {basicSnapshot.diagnostics ? (
                  <details
                    data-testid="basic-query-diagnostics-details"
                    className="mt-3 rounded-lg border border-subtle bg-background/25 px-3 py-2 text-xs text-secondary-text"
                  >
                    <summary className="cursor-pointer font-medium text-secondary-text hover:text-foreground">
                      {uiLanguage === 'en' ? 'Data diagnostics' : '数据诊断'}
                    </summary>
                    <div data-testid="basic-query-diagnostics" className="mt-2 flex flex-wrap gap-2">
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
                  </details>
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
